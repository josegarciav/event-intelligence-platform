"""
ArtistEnricherAgent — enriches artist metadata via the MusicBrainz API.

MusicBrainz is a free, open music encyclopedia that does not require authentication.
For each artist found on an event, this agent looks up genre (from tags) using
the MusicBrainz artist search endpoint and merges the result back into ArtistInfo.

Rate-limiting: MusicBrainz requests a max of 1 req/s per user-agent. This agent
runs lookups sequentially per event batch which naturally keeps the rate low.
"""

import asyncio
import logging
import time
from typing import Any

import requests

from src.agents.base.base_agent import BaseAgent
from src.agents.base.task import AgentResult, AgentTask
from src.schemas.event import ArtistInfo

logger = logging.getLogger(__name__)

_MUSICBRAINZ_API = "https://musicbrainz.org/ws/2/artist/"
_MUSICBRAINZ_HEADERS = {
    "User-Agent": "PulsecityEventPlatform/1.0 (contact@pulsecity.ai)",
    "Accept": "application/json",
}
_CONFIDENCE_THRESHOLD = 70  # MusicBrainz match score (0–100); below this we skip


class ArtistEnricherAgent(BaseAgent):
    """
    Enriches artist metadata for events using the MusicBrainz open API.

    For every ArtistInfo entry on an event, queries MusicBrainz for:
    - Genre (derived from the highest-count tag on the artist record)

    Existing fields (soundcloud_url, spotify_url, instagram_url) are preserved.
    Lookups that fail or return low-confidence matches are silently skipped so
    the agent never degrades already-ingested data.
    """

    name = "artist_enricher"
    prompt_name = "artist_enrichment"

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._timeout: float = float(self._config.get("timeout_seconds", 5.0))

    async def run(self, task: AgentTask) -> AgentResult:
        if not self._config.get("enabled", True):
            return AgentResult(
                agent_name=self.name,
                prompt_name=self.prompt_name,
                prompt_version="skipped",
                events=task.events,
                errors=["Agent disabled in config"],
            )

        start = time.monotonic()
        errors: list[str] = []
        enriched_events = list(task.events)

        for i, event in enumerate(enriched_events):
            if not event.artists:
                continue

            enriched_artists: list[ArtistInfo] = []
            for artist in event.artists:
                try:
                    enriched = await asyncio.to_thread(self._lookup_artist, artist)
                    enriched_artists.append(enriched)
                except Exception as exc:
                    msg = f"artist='{artist.name}': {exc}"
                    logger.warning("%s error: %s", self.name, msg)
                    errors.append(msg)
                    enriched_artists.append(artist)

            enriched_events[i].artists = enriched_artists

        return AgentResult(
            agent_name=self.name,
            prompt_name=self.prompt_name,
            prompt_version="v1",
            events=enriched_events,
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

        # Derive genre from the highest-count tag
        genre = artist.genre
        tags = mb_artist.get("tags") or []
        if tags:
            top_tag = max(tags, key=lambda t: t.get("count", 0))
            genre = top_tag.get("name") or genre

        return ArtistInfo(
            name=artist.name,
            genre=genre,
            soundcloud_url=artist.soundcloud_url,
            spotify_url=artist.spotify_url,
            instagram_url=artist.instagram_url,
        )
