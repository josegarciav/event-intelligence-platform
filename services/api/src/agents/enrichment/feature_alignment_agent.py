"""
FeatureAlignmentAgent — fills core metadata, pricing, and artist genre fields.

Target fields
─────────────
Core metadata (EventSchema):
  event_type      — one of 15 types (concert, nightlife, festival, …, other)
  format          — in_person | virtual | hybrid | streamed
  tags            — 5–8 lowercase search/filter tags; merged with existing tags

Pricing (EventSchema.price — PriceInfo):
  is_free         — bool; detected from "free" / "gratis" keywords
  currency_code   — ISO 4217 (USD, EUR, GBP, …); inferred from symbol or text
  minimum_price   — lowest advertised ticket price
  maximum_price   — highest advertised ticket price
  early_bird_price — discounted advance price
  standard_price  — regular admission price
  vip_price       — premium/VIP price
  price_raw_text  — verbatim price string from event context

Artists (EventSchema.artists — ArtistInfo):
  genre  — single-word genre label from MusicBrainz top tag (fill-null-only)

Strategy
────────
All fields are fill-null-only: ingestion values are never overwritten.
For currency_code the sentinel is the default "USD" — if ingestion already
set a non-USD currency the agent skips it.

Implementation
──────────────
Events are processed in configurable batches (default 8) to reduce LLM
round-trips. Each chunk produces a single MissingFieldsExtractionBatch
response keyed by source_event_id. Gracefully skips if LLM is unavailable.

After the LLM batch loop, a synchronous MusicBrainz pass fills artist.genre
for any artist missing it (fill-null-only, no LLM, runs via asyncio.to_thread).
Rate-limiting: MusicBrainz requests a max of 1 req/s per user-agent. Sequential
lookups per batch naturally keep the rate low.
"""

import asyncio
import logging
import time
from typing import Any

import requests

from src.agents.base.base_agent import BaseAgent
from src.agents.base.output_models import MissingFieldsExtractionBatch
from src.agents.base.task import AgentResult, AgentTask
from src.agents.llm.provider_router import get_llm_client
from src.agents.registry.prompt_registry import get_prompt_registry
from src.schemas.event import ArtistInfo

logger = logging.getLogger(__name__)

_MUSICBRAINZ_API = "https://musicbrainz.org/ws/2/artist/"
_MUSICBRAINZ_HEADERS = {
    "User-Agent": "PulsecityEventPlatform/1.0 (contact@pulsecity.ai)",
    "Accept": "application/json",
}
_CONFIDENCE_THRESHOLD = 70  # MusicBrainz match score (0–100); below this we skip

# Multi-word genre names that map to a single canonical word.
_GENRE_MAP: dict[str, str] = {
    "hip hop": "hiphop",
    "hip-hop": "hiphop",
    "rhythm and blues": "rnb",
    "r&b": "rnb",
    "drum and bass": "dnb",
    "drum & bass": "dnb",
    "electronic dance music": "electronic",
    "hard rock": "rock",
    "soft rock": "rock",
    "indie rock": "indie",
    "indie pop": "indie",
    "heavy metal": "metal",
    "death metal": "metal",
    "black metal": "metal",
    "nu metal": "metal",
    "pop music": "pop",
    "folk music": "folk",
    "country music": "country",
    "trap music": "trap",
    "house music": "house",
}


def _normalize_genre(tag: str) -> str:
    """Return a single-word genre label from a MusicBrainz tag string."""
    normalized = tag.lower().strip()
    if normalized in _GENRE_MAP:
        return _GENRE_MAP[normalized]
    # Fall back to first word only
    return normalized.split()[0] if normalized else normalized


class FeatureAlignmentAgent(BaseAgent):
    """
    Fills event_type, format, tags, and all PriceInfo fields (prompt v2).

    See module docstring for the full field list and fill strategy.
    """

    name = "feature_alignment"
    prompt_name = "feature_alignment"

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the FeatureAlignmentAgent with optional config overrides."""
        self._config = config or {}
        self._llm = get_llm_client(
            provider=self._config.get("provider", "anthropic"),
            model_name=self._config.get("model", "claude-haiku-4-5-20251001"),
            temperature=self._config.get("temperature", 0.1),
        )
        self._registry = get_prompt_registry()
        self._timeout: float = float(self._config.get("timeout_seconds", 5.0))

    async def run(self, task: AgentTask) -> AgentResult:
        """Run feature alignment on the task's event batch and return enriched results."""
        if not self._config.get("enabled", True):
            return AgentResult(
                agent_name=self.name,
                prompt_name=self.prompt_name,
                prompt_version="skipped",
                events=task.events,
                errors=["Agent disabled in config"],
            )

        if not self._llm.is_available:
            logger.warning(f"{self.name}: LLM unavailable, skipping enrichment")
            return AgentResult(
                agent_name=self.name,
                prompt_name=self.prompt_name,
                prompt_version="skipped",
                events=task.events,
                errors=["LLM not available — check API key"],
            )

        prompt_version = self._registry.get_active_version(self.prompt_name)
        batch_size = self._config.get("batch_size", 8)
        start = time.monotonic()
        errors: list[str] = []
        total_tokens: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total": 0,
        }
        enriched_events = list(task.events)
        # Build an index so we can apply results back by source_event_id
        event_index = {
            str(e.source.source_event_id): i for i, e in enumerate(enriched_events)
        }

        for chunk in self._chunk(enriched_events, batch_size):
            batch_ctx = self._build_batch_context(chunk)
            chunk_ids = [str(e.source.source_event_id) for e in chunk]
            try:
                system_prompt, user_prompt = self._registry.render(
                    self.prompt_name,
                    version=task.prompt_version,
                    variables=batch_ctx,
                    agent_name=self.name,
                    batch=True,
                )
                result: MissingFieldsExtractionBatch = (
                    await self._llm.complete_structured(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        output_schema=MissingFieldsExtractionBatch,
                        temperature=self._config.get("temperature", 0.1),
                    )
                )

                for item in result.items:
                    sid = item.source_event_id
                    idx = event_index.get(sid)
                    if idx is None:
                        continue

                    event = enriched_events[idx]
                    if item.event_type and not event.event_type:
                        from src.schemas.event import EventType

                        try:
                            enriched_events[idx].event_type = EventType(item.event_type)
                        except ValueError:
                            pass
                    if item.tags:
                        existing = set(event.tags or [])
                        enriched_events[idx].tags = list(existing | set(item.tags))
                    if item.event_format and not event.format:
                        from src.schemas.event import EventFormat

                        try:
                            enriched_events[idx].format = EventFormat(item.event_format)
                        except ValueError:
                            pass

                    if item.pricing:
                        from decimal import Decimal

                        p = item.pricing
                        price = enriched_events[idx].price
                        if p.is_free is not None and price.is_free is None:
                            price.is_free = p.is_free
                        if p.currency_code and price.currency_code == "USD":
                            price.currency_code = p.currency_code
                        for field in (
                            "minimum_price",
                            "maximum_price",
                            "early_bird_price",
                            "standard_price",
                            "vip_price",
                        ):
                            if getattr(p, field) is not None and getattr(price, field) is None:
                                setattr(price, field, Decimal(str(getattr(p, field))))
                        if p.price_raw_text and not price.price_raw_text:
                            price.price_raw_text = p.price_raw_text

                usage = self._llm.get_token_usage()
                for k in total_tokens:
                    total_tokens[k] += usage.get(k, 0)

            except Exception as e:
                msg = f"batch {chunk_ids}: {e}"
                logger.warning(f"{self.name} batch error: {msg}")
                errors.append(msg)

        # MusicBrainz artist genre enrichment (fill-null-only, no LLM)
        for i, event in enumerate(enriched_events):
            if not event.artists:
                continue
            enriched_artists = []
            for artist in event.artists:
                try:
                    enriched_artists.append(
                        await asyncio.to_thread(self._lookup_artist, artist)
                    )
                except Exception as exc:
                    errors.append(f"artist='{artist.name}': {exc}")
                    enriched_artists.append(artist)
            enriched_events[i].artists = enriched_artists

        return AgentResult(
            agent_name=self.name,
            prompt_name=self.prompt_name,
            prompt_version=prompt_version,
            events=enriched_events,
            token_usage=total_tokens,
            errors=errors,
            duration_seconds=time.monotonic() - start,
        )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _lookup_artist(self, artist: ArtistInfo) -> ArtistInfo:
        """
        Synchronous MusicBrainz lookup — intended to run via asyncio.to_thread.

        Returns the original ArtistInfo unchanged if the lookup fails or the
        match confidence is below _CONFIDENCE_THRESHOLD.
        """
        try:
            resp = requests.get(
                _MUSICBRAINZ_API,
                params={"query": artist.name, "fmt": "json", "limit": 1},
                headers=_MUSICBRAINZ_HEADERS,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.debug("MusicBrainz request failed for '%s': %s", artist.name, exc)
            return artist

        data = resp.json()
        artists_found = data.get("artists") or []
        if not artists_found:
            return artist

        mb_artist = artists_found[0]
        score = int(mb_artist.get("score", 0))
        if score < _CONFIDENCE_THRESHOLD:
            logger.debug(
                "Low MusicBrainz confidence (%d) for '%s', skipping enrichment",
                score,
                artist.name,
            )
            return artist

        # Derive genre from the highest-count tag — normalize to single word
        genre = artist.genre
        tags = mb_artist.get("tags") or []
        if tags and not genre:
            top_tag = max(tags, key=lambda t: t.get("count", 0))
            raw = top_tag.get("name") or ""
            if raw:
                genre = _normalize_genre(raw)

        return ArtistInfo(
            name=artist.name,
            genre=genre,
            soundcloud_url=artist.soundcloud_url,
            spotify_url=artist.spotify_url,
            instagram_url=artist.instagram_url,
        )
