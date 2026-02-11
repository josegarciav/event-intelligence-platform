"""
scrapping.ai.config_agent

Roadmap module: AI-assisted config generation.

Goal:
- Given one or multiple URLs, generate a *starting config* for each source:
    - engine choice (http/browser/hybrid)
    - discovery.link_extract (regex/css/xpath draft)
    - entrypoints paging defaults
    - parse selectors (optional)
    - QA and validation defaults
    - storage hints

V1 philosophy:
- Deterministic heuristics + templates (no LLM required)
- Allow optional "probe" results to refine config later
- Provide a clean API so you can later add an LLM agent (ConfigAgentLLM)
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

# We reuse canonical URL logic used elsewhere
from scrapping.extraction.transforms import canonicalize_url

# -----------------------------
# Data structures
# -----------------------------

@dataclass
class ConfigProposal:
    """
    The output of the agent: a source config dict + rationale and confidence.
    """
    source_config: dict[str, Any]
    rationale: list[str]
    confidence: float  # 0..1
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_config": self.source_config,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "warnings": self.warnings,
        }


@dataclass
class UrlHint:
    """
    Optional hints you can pass from a manual/automated probe step.
    (Later, tests_agent can generate this by fetching a sample page.)
    """
    url: str
    html_sample: str | None = None
    is_js_heavy: bool | None = None
    discovered_link_patterns: list[str] | None = None  # regexes
    title_selector_guess: str | None = None
    text_selector_guess: str | None = None
    language_guess: str | None = None


# -----------------------------
# Core Agent (heuristics)
# -----------------------------

class ConfigAgent:
    """
    Heuristic config generator.

    Later upgrade path:
    - add "probe_runner" to fetch sample HTML + detect JS + infer selectors automatically
    - add LLM refinement that outputs a final config matching schema.py
    """

    def __init__(self) -> None:
        pass

    def propose_for_urls(
        self,
        urls: Sequence[str],
        *,
        run_name: str | None = None,
        output_items_format: str = "jsonl",
        hints: Sequence[UrlHint] | None = None,
    ) -> dict[str, Any]:
        """
        Build a full config containing multiple sources from URLs.

        Strategy:
        - group URLs by domain
        - create one source per domain (V1 default)
        - add each URL as entrypoint
        """
        urls_norm = [canonicalize_url(u) for u in urls if u and str(u).strip()]
        grouped: dict[str, list[str]] = {}
        for u in urls_norm:
            dom = _domain(u) or "unknown"
            grouped.setdefault(dom, []).append(u)

        hint_map: dict[str, UrlHint] = {}
        if hints:
            for h in hints:
                if h.url:
                    hint_map[canonicalize_url(h.url)] = h

        sources: list[dict[str, Any]] = []
        for dom, dom_urls in grouped.items():
            proposal = self.propose_source(
                dom_urls,
                source_id=_make_source_id(dom),
                output_items_format=output_items_format,
                hints=[hint_map[u] for u in dom_urls if u in hint_map] or None,
            )
            sources.append(proposal.source_config)

        return {
            "run": {
                "name": run_name or "generated_by_config_agent",
                "generated_by": "scrapping.ai.config_agent.ConfigAgent",
                "version": "v1",
            },
            "sources": sources,
        }

    def propose_source(
        self,
        urls: Sequence[str],
        *,
        source_id: str | None = None,
        output_items_format: str = "jsonl",
        hints: Sequence[UrlHint] | None = None,
    ) -> ConfigProposal:
        """
        Create a single source config proposal given one/many URLs belonging to a site.
        """
        urls = [canonicalize_url(u) for u in urls if u and str(u).strip()]
        base = _guess_base(urls[0]) if urls else None
        dom = _domain(urls[0]) if urls else "unknown"
        sid = source_id or _make_source_id(dom)

        warnings: list[str] = []
        rationale: list[str] = []

        # Decide engine type
        engine_type, engine_conf, engine_reason = self._decide_engine(urls, hints=hints)
        rationale.extend(engine_reason)

        # Entry points
        entrypoints = [{"url": u, "paging": {"mode": "page", "pages": 1, "start": 1, "step": 1}} for u in urls]
        if len(entrypoints) > 5:
            rationale.append("Many URLs provided; grouped as multiple entrypoints in one source (V1).")

        # Discovery defaults: try to infer a regex pattern for links (very rough)
        link_extract, link_conf, link_reason = self._propose_link_extraction(dom, urls, base_url=base, hints=hints)
        rationale.extend(link_reason)

        # Parse hints
        parse_cfg: dict[str, Any] = {}
        if hints:
            # pick first non-null guess
            for h in hints:
                if h.title_selector_guess and "title_selector" not in parse_cfg:
                    parse_cfg["title_selector"] = h.title_selector_guess
                if h.text_selector_guess and "text_selector" not in parse_cfg:
                    parse_cfg["text_selector"] = h.text_selector_guess

        # Validation + QA defaults (conservative)
        validation_cfg = {
            "url_field": "url",
            "title_field": "title",
            "text_field": "text",
            "min_text_len": 200,
            "require_title": False,
            "require_text": False,
        }

        quality_cfg = {
            "min_text_len": 250,
            "min_title_len": 3,
            "max_boilerplate_ratio": 0.85,
            # If you know your target language per source, set language_allow.
            # We'll keep it open by default.
        }

        # Storage defaults
        storage_cfg = {
            "items_format": output_items_format,
            "save_raw_pages": True,
        }

        # Engine config template
        engine_cfg: dict[str, Any] = {
            "type": engine_type,
            "timeout_s": 20 if engine_type in ("browser", "hybrid") else 15,
            "verify_ssl": True,
            "retry_policy": {"max_retries": 3, "backoff": "exp", "retry_on_status": [429, 500, 502, 503, 504]},
            "rate_limit_policy": {"min_delay_s": 0.2, "jitter_s": 0.2},
        }
        if engine_type in ("browser", "hybrid"):
            engine_cfg["browser"] = {
                "browser_name": "chromium",
                "headless": True,
                "timeout_s": 30,
                "max_retries": 2,
                "backoff_mode": "exp",
            }

        # Compose source config
        src = {
            "source_id": sid,
            "labels": {
                "domain": dom,
                "base_url": base,
            },
            "engine": engine_cfg,
            "entrypoints": entrypoints,
            "discovery": {
                "wait_for": None,  # you can set CSS selector for browser rendering
                "link_extract": link_extract,
                "dedupe": {"content_fields": ["title", "text"]},
            },
            "actions": [],  # browser_actions/human_like later
            "parse": parse_cfg,
            "validation": validation_cfg,
            "quality": quality_cfg,
            "storage": storage_cfg,
        }

        # Confidence blends
        confidence = max(0.2, min(0.95, 0.45 * engine_conf + 0.55 * link_conf))

        # Safety warnings
        if engine_type in ("browser", "hybrid") and not base:
            warnings.append("Engine uses browser/hybrid but base_url could not be inferred; relative links may break.")
        if link_extract.get("method") == "regex" and not link_extract.get("pattern"):
            warnings.append("Link extraction regex pattern is empty; you must set discovery.link_extract.pattern.")
        if dom == "unknown":
            warnings.append("Domain could not be inferred; source_id may be generic and should be renamed.")

        return ConfigProposal(
            source_config=src,
            rationale=rationale,
            confidence=float(confidence),
            warnings=warnings,
        )

    # -----------------------------
    # Internal heuristics
    # -----------------------------

    def _decide_engine(self, urls: Sequence[str], *, hints: Sequence[UrlHint] | None = None) -> tuple[str, float, list[str]]:
        """
        Pick engine based on URL patterns and hints.
        """
        rationale: list[str] = []
        # If hints say JS heavy => browser/hybrid
        if hints:
            for h in hints:
                if h.is_js_heavy is True:
                    rationale.append("Hints indicate JS-heavy pages -> choosing hybrid engine.")
                    return "hybrid", 0.85, rationale

        # URL pattern heuristics: common SPA frameworks / dynamic search pages
        u = " ".join(urls).lower()
        spa_markers = ["#/","/app","/spa","?s=","?search=","/search","/jobs","/careers"]
        if any(m in u for m in spa_markers):
            rationale.append("URL patterns suggest search/listing pages; starting with http engine (upgrade to hybrid if blocked).")
            return "http", 0.55, rationale

        rationale.append("No strong JS signals; starting with http engine.")
        return "http", 0.6, rationale

    def _propose_link_extraction(
        self,
        domain: str,
        urls: Sequence[str],
        *,
        base_url: str | None,
        hints: Sequence[UrlHint] | None = None,
    ) -> tuple[dict[str, Any], float, list[str]]:
        """
        Draft discovery.link_extract config.
        """
        rationale: list[str] = []

        # If probe hints provided patterns, use them
        if hints:
            for h in hints:
                if h.discovered_link_patterns:
                    rationale.append("Using discovered_link_patterns from hints for regex extraction.")
                    # Use first pattern as primary; in V2 we can support multiple.
                    pat = h.discovered_link_patterns[0]
                    return (
                        {
                            "method": "regex",
                            "pattern": pat,
                            "identifier": None,
                        },
                        0.85,
                        rationale,
                    )

        # Heuristic: build a regex around the domain and "jobs/careers/listing" etc.
        # This is intentionally loose; user/team will refine.
        if domain and domain != "unknown":
            safe_dom = re.escape(domain)
            pat = rf"https?://(?:www\.)?{safe_dom}/[^\s\"\'<>]+"
            rationale.append("Default link extraction: broad domain URL regex (needs narrowing for precision).")
            return (
                {
                    "method": "regex",
                    "pattern": pat,
                    "identifier": None,
                },
                0.45,
                rationale,
            )

        rationale.append("Could not infer domain; leaving regex pattern empty.")
        return (
            {
                "method": "regex",
                "pattern": None,
                "identifier": None,
            },
            0.2,
            rationale,
        )


# -----------------------------
# Helpers
# -----------------------------

def _domain(url: str) -> str | None:
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def _guess_base(url: str) -> str | None:
    try:
        p = urlparse(url)
        if not p.scheme or not p.netloc:
            return None
        return f"{p.scheme}://{p.netloc}/"
    except Exception:
        return None


def _make_source_id(domain: str) -> str:
    dom = (domain or "unknown").lower().strip()
    dom = dom.replace("www.", "")
    dom = re.sub(r"[^a-z0-9]+", "_", dom).strip("_")
    return dom[:80] or "unknown_source"
