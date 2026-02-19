"""
Source Page Detection & Auto-Config Generation.

Probes a source URL to detect page characteristics (SPA vs static,
anti-bot protections, framework) and recommends scrapping engine config.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SPA / framework markers in raw HTML
# ---------------------------------------------------------------------------

_SPA_MARKERS: list[tuple[str, str]] = [
    (r'<div\s+id=["\']root["\']', "react"),
    (r'<div\s+id=["\']__next["\']', "nextjs"),
    (r"__NEXT_DATA__", "nextjs"),
    (r"window\.__INITIAL_STATE__", "react"),
    (r"window\.__NUXT__", "nuxt"),
    (r"\bng-app\b", "angular"),
    (r"\bng-version\b", "angular"),
    (r"\bdata-v-[0-9a-f]", "vue"),
    (r'<div\s+id=["\']app["\']>\s*</div>', "vue"),
    (r"_app\.js", "nextjs"),
    (r"/_next/static", "nextjs"),
]

_ANTI_BOT_MARKERS: list[str] = [
    r"cf-browser-verification",
    r"challenge-platform",
    r"cdn-cgi/challenge-platform",
    r"recaptcha/api",
    r"hcaptcha\.com",
    r"Checking your browser",
    r"__cf_bm",
    r"Attention Required! \| Cloudflare",
]

# CSS selectors that typically hold main content on common frameworks
_DEFAULT_WAIT_SELECTORS: dict[str, str] = {
    "react": "[id='root'] *",
    "nextjs": "[id='__next'] *",
    "vue": "[id='app'] *",
    "angular": "[ng-app] *",
}


@dataclass
class SourceDetection:
    """Result of probing a source URL."""

    url: str
    needs_javascript: bool = False
    recommended_engine: str = "http"
    has_anti_bot: bool = False
    wait_for_selector: str | None = None
    detected_framework: str | None = None
    content_type: str = "html"
    requires_actions: list[dict] = field(default_factory=list)
    meta_title: str | None = None
    robots_policy: str = "unknown"
    raw_html_length: int = 0
    extracted_text_length: int = 0
    detection_notes: list[str] = field(default_factory=list)


class SourceDetector:
    """
    Lightweight probe that visits a source URL to detect its characteristics
    and recommend scrapping engine configuration.
    """

    def __init__(
        self,
        *,
        timeout_s: float = 15.0,
        min_text_len: int = 200,
        spa_text_ratio_threshold: float = 0.02,
    ):
        self.timeout_s = timeout_s
        self.min_text_len = min_text_len
        self.spa_text_ratio_threshold = spa_text_ratio_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def probe(self, url: str) -> SourceDetection:
        """
        Probe *url* and return detection results with engine recommendation.

        The probe uses a simple HTTP GET (no JS rendering) and analyses the
        raw response to infer whether a browser engine is required.
        """
        detection = SourceDetection(url=url)

        # --- HTTP probe ---
        raw_html = self._http_get(url, detection)
        if raw_html is None:
            detection.detection_notes.append("HTTP probe failed; defaulting to browser")
            detection.needs_javascript = True
            detection.recommended_engine = "browser"
            return detection

        detection.raw_html_length = len(raw_html)

        # --- Content-type ---
        detection.content_type = self._detect_content_type(raw_html)

        # --- Meta / title ---
        detection.meta_title = self._extract_meta_title(raw_html)

        # --- Framework detection ---
        detection.detected_framework = self._detect_framework(raw_html, detection)

        # --- Anti-bot detection ---
        detection.has_anti_bot = self._detect_anti_bot(raw_html, detection)

        # --- Text extraction test ---
        extracted_text = self._try_text_extraction(raw_html, url, detection)

        # --- Robots policy ---
        detection.robots_policy = self._check_robots(url)

        # --- Engine recommendation ---
        self._recommend_engine(detection, extracted_text)

        return detection

    # ------------------------------------------------------------------
    # Internal detection helpers
    # ------------------------------------------------------------------

    def _http_get(self, url: str, detection: SourceDetection) -> str | None:
        """Perform a simple HTTP GET and return the response body."""
        try:
            import httpx

            with httpx.Client(
                timeout=self.timeout_s,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PulsecityBot/1.0)"},
            ) as client:
                resp = client.get(url)
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    detection.content_type = "json"
                elif "xml" in ct:
                    detection.content_type = "xml"
                return resp.text
        except ImportError:
            # httpx not available – fall back to urllib
            try:
                import urllib.request

                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; PulsecityBot/1.0)"
                    },
                )
                with urllib.request.urlopen(
                    req, timeout=self.timeout_s
                ) as resp:  # noqa: S310
                    return resp.read().decode("utf-8", errors="replace")
            except Exception as exc:
                logger.debug("HTTP probe (urllib) failed for %s: %s", url, exc)
                return None
        except Exception as exc:
            logger.debug("HTTP probe failed for %s: %s", url, exc)
            return None

    def _detect_content_type(self, html: str) -> str:
        if html.lstrip().startswith(("{", "[")):
            return "json"
        if html.lstrip().startswith("<?xml") or html.lstrip().startswith("<rss"):
            return "xml"
        return "html"

    def _extract_meta_title(self, html: str) -> str | None:
        # Try og:title first, then <title>
        og = re.search(
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
            html,
            re.I,
        )
        if og:
            return og.group(1).strip()
        title = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        if title:
            return title.group(1).strip()
        return None

    def _detect_framework(self, html: str, detection: SourceDetection) -> str | None:
        detected: str | None = None
        for pattern, framework in _SPA_MARKERS:
            if re.search(pattern, html, re.I):
                detection.detection_notes.append(
                    f"SPA marker matched: {pattern} -> {framework}"
                )
                detected = framework
                break  # first match wins (ordered by specificity)
        return detected

    def _detect_anti_bot(self, html: str, detection: SourceDetection) -> bool:
        for pattern in _ANTI_BOT_MARKERS:
            if re.search(pattern, html, re.I):
                detection.detection_notes.append(f"Anti-bot marker: {pattern}")
                return True
        return False

    def _try_text_extraction(
        self,
        html: str,
        url: str,
        detection: SourceDetection,
    ) -> str:
        """Run html_to_structured and record extracted text length."""
        try:
            from scrapping.processing.html_to_structured import html_to_structured

            doc = html_to_structured(html, url=url)
            text = doc.text or ""
        except ImportError:
            # Fallback: naive tag stripping
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
        except Exception as exc:
            logger.debug("Text extraction failed for %s: %s", url, exc)
            text = ""

        detection.extracted_text_length = len(text)
        return text

    def _check_robots(self, url: str) -> str:
        """Quick robots.txt check for the source domain."""
        try:
            parsed = urlparse(url)
            robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")

            try:
                import httpx

                with httpx.Client(timeout=5, follow_redirects=True) as client:
                    resp = client.get(robots_url)
                    if resp.status_code == 200:
                        body = resp.text.lower()
                        if "disallow: /" in body and "allow:" not in body:
                            return "restricted"
                        return "allowed"
                    return "unknown"
            except ImportError:
                return "unknown"
        except Exception:
            return "unknown"

    def _recommend_engine(
        self, detection: SourceDetection, extracted_text: str
    ) -> None:
        """Decide on engine recommendation based on all signals."""
        has_framework = detection.detected_framework is not None

        # Text-to-HTML ratio as SPA signal
        ratio = (
            len(extracted_text) / detection.raw_html_length
            if detection.raw_html_length > 0
            else 0.0
        )
        short_text = len(extracted_text) < self.min_text_len
        poor_ratio = (
            ratio < self.spa_text_ratio_threshold and detection.raw_html_length > 1000
        )

        detection.needs_javascript = (
            has_framework or short_text or poor_ratio or detection.has_anti_bot
        )

        if detection.has_anti_bot:
            detection.recommended_engine = "browser"
            detection.detection_notes.append("Anti-bot detected -> browser engine")
        elif has_framework and short_text:
            detection.recommended_engine = "browser"
            detection.detection_notes.append(
                f"SPA framework ({detection.detected_framework}) + short text ({len(extracted_text)} chars) -> browser"
            )
        elif has_framework:
            detection.recommended_engine = "hybrid"
            detection.detection_notes.append(
                f"SPA framework ({detection.detected_framework}) but decent text -> hybrid"
            )
        elif short_text or poor_ratio:
            detection.recommended_engine = "hybrid"
            detection.detection_notes.append(
                f"Short text ({len(extracted_text)} chars) or poor ratio ({ratio:.3f}) -> hybrid"
            )
        else:
            detection.recommended_engine = "http"
            detection.needs_javascript = False
            detection.detection_notes.append(
                "Static content with good extraction -> http"
            )

        # Wait-for selector
        if detection.needs_javascript and detection.detected_framework:
            detection.wait_for_selector = _DEFAULT_WAIT_SELECTORS.get(
                detection.detected_framework
            )
