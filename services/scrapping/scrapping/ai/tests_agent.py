"""
scrapping.ai.tests_agent

Roadmap module: AI-assisted test generation for scraping configs.

Goal:
- Automatically generate "tests" that validate:
    - link extraction yields enough links
    - fetched pages look real (not blocked)
    - structured extraction returns text above thresholds
    - selectors/regex patterns still match after site changes
    - detect regression when a site deploys stronger anti-bot

V1 philosophy:
- Provide a test plan format (JSON-friendly)
- Provide a runner that can execute tests using existing engines + pipeline utilities
- Keep it deterministic, with optional "probe" mode for local CI

Later upgrade path:
- LLM agent that:
    - proposes improved selectors/patterns when tests fail
    - opens PRs with config migrations
    - maintains site-specific heuristics
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from scrapping.engines.browser import BrowserEngine, BrowserEngineOptions
from scrapping.engines.http import HttpEngine, HttpEngineOptions
from scrapping.engines.hybrid import HybridEngine, HybridEngineOptions
from scrapping.extraction.link_extractors import LinkExtractRequest, extract_links
from scrapping.processing.html_to_structured import html_to_structured
from scrapping.processing.quality_filters import evaluate_quality

# -----------------------------
# Test plan schema (V1)
# -----------------------------


@dataclass
class TestCase:
    test_id: str
    kind: str  # "listing_links" | "detail_quality" | "blocked_page" | "smoke_pipeline"
    target_url: str
    expectations: dict[str, Any]
    notes: str | None = None


@dataclass
class TestPlan:
    source_id: str
    created_at_s: float
    tests: list[TestCase]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "created_at_s": self.created_at_s,
            "tests": [
                {
                    "test_id": t.test_id,
                    "kind": t.kind,
                    "target_url": t.target_url,
                    "expectations": t.expectations,
                    "notes": t.notes,
                }
                for t in self.tests
            ],
        }


# -----------------------------
# Agent: generate tests from config
# -----------------------------


class TestsAgent:
    def __init__(self) -> None:
        pass

    def generate_plan(self, source_cfg: dict[str, Any]) -> TestPlan:
        """
        Generate a lightweight plan from a single source config.
        """
        source_id = str(source_cfg.get("source_id", "unknown_source"))
        entrypoints = source_cfg.get("entrypoints") or []
        first_url = None
        for ep in entrypoints:
            if isinstance(ep, dict) and ep.get("url"):
                first_url = str(ep["url"])
                break

        tests: list[TestCase] = []

        if first_url:
            tests.append(
                TestCase(
                    test_id=f"{source_id}:listing_links",
                    kind="listing_links",
                    target_url=first_url,
                    expectations={
                        "min_links": 5,
                        "max_links": 5000,
                    },
                    notes="Fetch listing page and ensure link extraction yields a reasonable count.",
                )
            )

        # If config provides known detail sample URLs, include them.
        detail_samples = source_cfg.get("test_samples") or {}
        detail_urls = (
            detail_samples.get("detail_urls")
            if isinstance(detail_samples, dict)
            else None
        )
        if isinstance(detail_urls, list):
            for i, u in enumerate(detail_urls[:5]):
                tests.append(
                    TestCase(
                        test_id=f"{source_id}:detail_quality:{i}",
                        kind="detail_quality",
                        target_url=str(u),
                        expectations={
                            "min_text_len": 250,
                            "max_boilerplate_ratio": float(
                                (source_cfg.get("quality") or {}).get(
                                    "max_boilerplate_ratio", 0.85
                                )
                            ),
                            "keep": True,
                        },
                        notes="Fetch detail page and ensure structured extraction passes QA.",
                    )
                )

        # Basic blocked-page detection on entrypoint (helps catch CAPTCHAs)
        if first_url:
            tests.append(
                TestCase(
                    test_id=f"{source_id}:blocked_page",
                    kind="blocked_page",
                    target_url=first_url,
                    expectations={
                        "blocked": False,
                    },
                    notes="Ensure listing page is not a captcha/login wall.",
                )
            )

        # Optional: smoke pipeline test (single URL run, single page)
        if first_url:
            tests.append(
                TestCase(
                    test_id=f"{source_id}:smoke_pipeline",
                    kind="smoke_pipeline",
                    target_url=first_url,
                    expectations={
                        "pipeline_ok": True,
                        "min_items_saved": 1,
                    },
                    notes="Runs a minimal pipeline-like sequence: fetch listing -> extract links -> fetch first detail -> parse+QA.",
                )
            )

        return TestPlan(source_id=source_id, created_at_s=time.time(), tests=tests)

    # -----------------------------
    # Runner: execute tests
    # -----------------------------

    def run_plan(
        self, source_cfg: dict[str, Any], plan: TestPlan, *, max_detail_fetch: int = 1
    ) -> dict[str, Any]:
        """
        Execute test plan against real network (CI / local).

        Returns report dict:
          { ok: bool, results: [...], failures: [...] }
        """
        engine = _build_engine(source_cfg)
        results: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []

        try:
            for t in plan.tests:
                try:
                    r = self._run_one_test(
                        source_cfg, engine, t, max_detail_fetch=max_detail_fetch
                    )
                    results.append(r)
                    if not r.get("ok", False):
                        failures.append(r)
                except Exception as e:
                    rr = {
                        "test_id": t.test_id,
                        "ok": False,
                        "error": f"{type(e).__name__}: {e}",
                    }
                    results.append(rr)
                    failures.append(rr)
        finally:
            try:
                engine.close()
            except Exception:
                pass

        return {
            "ok": len(failures) == 0,
            "source_id": plan.source_id,
            "created_at_s": plan.created_at_s,
            "results": results,
            "failures": failures,
        }

    def _run_one_test(
        self,
        source_cfg: dict[str, Any],
        engine: Any,
        test: TestCase,
        *,
        max_detail_fetch: int,
    ) -> dict[str, Any]:
        kind = test.kind
        url = test.target_url

        # fetch listing (rendered if browser/hybrid)
        rendered = str(
            (source_cfg.get("engine") or {}).get("type", "http")
        ).lower() in ("browser", "hybrid")
        fr = (
            engine.get_rendered(url, ctx=None)
            if rendered
            else engine.get(url, ctx=None)
        )

        if kind == "listing_links":
            if not fr.ok or not fr.text:
                return {
                    "test_id": test.test_id,
                    "ok": False,
                    "reason": "fetch_failed",
                    "status_code": fr.status_code,
                }

            le = (source_cfg.get("discovery") or {}).get("link_extract") or {}
            req = LinkExtractRequest(
                html=fr.text,
                base_url=_guess_base(url),
                method=str(le.get("method", "regex")),
                pattern=le.get("pattern"),
                selector=le.get("selector"),
                identifier=le.get("identifier"),
                normalize=True,
            )
            links = extract_links(req)
            n = len(links)

            mn = int(test.expectations.get("min_links", 1))
            mx = int(test.expectations.get("max_links", 10_000))
            ok = (n >= mn) and (n <= mx)

            return {
                "test_id": test.test_id,
                "ok": ok,
                "links_found": n,
                "min_links": mn,
                "max_links": mx,
                "sample": links[:10],
            }

        if kind == "blocked_page":
            if not fr.ok or not fr.text:
                return {"test_id": test.test_id, "ok": False, "reason": "fetch_failed"}

            item = {"url": url, "title": None, "text": fr.text}
            q = evaluate_quality(item, rules={"min_text_len": 50})
            blocked_expected = bool(test.expectations.get("blocked", False))
            blocked_detected = not q.keep and any(
                i.code == "blocked_page" for i in q.issues
            )

            ok = blocked_detected == blocked_expected
            return {
                "test_id": test.test_id,
                "ok": ok,
                "blocked_detected": blocked_detected,
                "expected_blocked": blocked_expected,
                "issues": [
                    {"level": i.level, "code": i.code, "message": i.message}
                    for i in q.issues
                ],
            }

        if kind == "detail_quality":
            if not fr.ok or not fr.text:
                return {"test_id": test.test_id, "ok": False, "reason": "fetch_failed"}

            parse_cfg = source_cfg.get("parse") or {}
            doc = html_to_structured(
                fr.text,
                url=url,
                title_selector=parse_cfg.get("title_selector"),
                text_selector=parse_cfg.get("text_selector"),
                prefer_trafilatura=True,
            )
            item = doc.as_item()

            rules = dict(source_cfg.get("quality") or {})
            # test expectations can override
            rules["min_text_len"] = int(
                test.expectations.get("min_text_len", rules.get("min_text_len", 250))
            )
            rules["max_boilerplate_ratio"] = float(
                test.expectations.get(
                    "max_boilerplate_ratio", rules.get("max_boilerplate_ratio", 0.85)
                )
            )

            q = evaluate_quality(item, rules=rules)

            expected_keep = bool(test.expectations.get("keep", True))
            ok = q.keep == expected_keep

            return {
                "test_id": test.test_id,
                "ok": ok,
                "keep": q.keep,
                "expected_keep": expected_keep,
                "text_len": len(item.get("text") or ""),
                "issues": [
                    {"level": i.level, "code": i.code, "message": i.message}
                    for i in q.issues
                ],
            }

        if kind == "smoke_pipeline":
            # minimal pipeline-like sequence on one listing + one detail
            if not fr.ok or not fr.text:
                return {
                    "test_id": test.test_id,
                    "ok": False,
                    "reason": "listing_fetch_failed",
                }

            le = (source_cfg.get("discovery") or {}).get("link_extract") or {}
            req = LinkExtractRequest(
                html=fr.text,
                base_url=_guess_base(url),
                method=str(le.get("method", "regex")),
                pattern=le.get("pattern"),
                selector=le.get("selector"),
                identifier=le.get("identifier"),
                normalize=True,
            )
            links = extract_links(req)
            if not links:
                return {
                    "test_id": test.test_id,
                    "ok": False,
                    "reason": "no_links_extracted",
                }

            # fetch first detail
            detail_url = links[0]
            fr2 = (
                engine.get_rendered(detail_url, ctx=None)
                if rendered
                else engine.get(detail_url, ctx=None)
            )
            if not fr2.ok or not fr2.text:
                return {
                    "test_id": test.test_id,
                    "ok": False,
                    "reason": "detail_fetch_failed",
                    "detail_url": detail_url,
                }

            parse_cfg = source_cfg.get("parse") or {}
            doc = html_to_structured(
                fr2.text,
                url=detail_url,
                title_selector=parse_cfg.get("title_selector"),
                text_selector=parse_cfg.get("text_selector"),
                prefer_trafilatura=True,
            )
            item = doc.as_item()

            q = evaluate_quality(item, rules=source_cfg.get("quality") or {})
            ok = q.keep

            mn_items = int(test.expectations.get("min_items_saved", 1))
            items_saved = 1 if q.keep else 0

            return {
                "test_id": test.test_id,
                "ok": ok and items_saved >= mn_items,
                "pipeline_ok": ok,
                "items_saved": items_saved,
                "min_items_saved": mn_items,
                "detail_url": detail_url,
                "issues": [
                    {"level": i.level, "code": i.code, "message": i.message}
                    for i in q.issues
                ],
            }

        return {
            "test_id": test.test_id,
            "ok": False,
            "reason": f"unknown_test_kind:{kind}",
        }


# -----------------------------
# Engine builder (local to tests)
# -----------------------------


def _build_engine(source_cfg: dict[str, Any]):
    eng = source_cfg.get("engine") or {}
    et = str(eng.get("type", "http")).lower().strip()

    timeout_s = float(eng.get("timeout_s", 15.0))
    verify_ssl = bool(eng.get("verify_ssl", True))
    user_agent = eng.get("user_agent")

    http_opts = HttpEngineOptions(
        timeout_s=timeout_s,
        verify_ssl=verify_ssl,
        max_retries=2,
        backoff_mode="exp",
        retry_on_status=(429, 500, 502, 503, 504),
        rps=None,
        burst=None,
        min_delay_s=0.0,
        jitter_s=0.0,
        user_agent=user_agent,
    )

    browser_cfg = eng.get("browser") or {}
    browser_opts = BrowserEngineOptions(
        browser_name=str(browser_cfg.get("browser_name", "chromium")),
        headless=bool(browser_cfg.get("headless", True)),
        timeout_s=float(browser_cfg.get("timeout_s", max(20.0, timeout_s))),
        max_retries=int(browser_cfg.get("max_retries", 1)),
        backoff_mode=str(browser_cfg.get("backoff_mode", "exp")),
        rps=None,
        burst=None,
        min_delay_s=float(browser_cfg.get("min_delay_s", 0.0)),
        jitter_s=float(browser_cfg.get("jitter_s", 0.2)),
        user_agent=user_agent,
    )

    if et == "http":
        return HttpEngine(options=http_opts)
    if et == "browser":
        return BrowserEngine(options=browser_opts)
    if et == "hybrid":
        return HybridEngine(
            options=HybridEngineOptions(http=http_opts, browser=browser_opts)
        )
    return HttpEngine(options=http_opts)


def _guess_base(url: str) -> str | None:
    try:
        from urllib.parse import urlparse

        p = urlparse(url)
        if not p.scheme or not p.netloc:
            return None
        return f"{p.scheme}://{p.netloc}/"
    except Exception:
        return None
