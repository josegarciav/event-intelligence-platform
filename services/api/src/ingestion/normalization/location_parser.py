"""
Location Parser.

Parses combined address strings into structured components and provides
Nominatim geocoding as a fallback when API coordinates are unavailable.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.schemas.event import Coordinates, LocationInfo

logger = logging.getLogger(__name__)

# Country name -> ISO 3166-1 alpha-2 code
COUNTRY_NAME_TO_CODE: dict[str, str] = {
    "spain": "ES",
    "españa": "ES",
    "germany": "DE",
    "deutschland": "DE",
    "france": "FR",
    "italy": "IT",
    "italia": "IT",
    "united kingdom": "GB",
    "uk": "GB",
    "england": "GB",
    "netherlands": "NL",
    "holland": "NL",
    "belgium": "BE",
    "portugal": "PT",
    "austria": "AT",
    "switzerland": "CH",
    "united states": "US",
    "usa": "US",
    "us": "US",
    "canada": "CA",
    "australia": "AU",
    "japan": "JP",
    "brazil": "BR",
    "mexico": "MX",
    "argentina": "AR",
    "colombia": "CO",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "finland": "FI",
    "poland": "PL",
    "czech republic": "CZ",
    "czechia": "CZ",
    "ireland": "IE",
    "greece": "GR",
    "turkey": "TR",
    "croatia": "HR",
    "romania": "RO",
    "hungary": "HU",
}

# Postal code regex patterns per country code
POSTAL_CODE_PATTERNS: dict[str, re.Pattern] = {
    "ES": re.compile(r"\b(\d{5})\b"),
    "DE": re.compile(r"\b(\d{5})\b"),
    "IT": re.compile(r"\b(\d{5})\b"),
    "FR": re.compile(r"\b(\d{5})\b"),
    "GB": re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", re.IGNORECASE),
    "US": re.compile(r"\b(\d{5}(?:-\d{4})?)\b"),
    "NL": re.compile(r"\b(\d{4}\s?[A-Z]{2})\b", re.IGNORECASE),
    "PT": re.compile(r"\b(\d{4}-\d{3})\b"),
    "AT": re.compile(r"\b(\d{4})\b"),
    "CH": re.compile(r"\b(\d{4})\b"),
    "BE": re.compile(r"\b(\d{4})\b"),
    "PL": re.compile(r"\b(\d{2}-\d{3})\b"),
    "CZ": re.compile(r"\b(\d{3}\s?\d{2})\b"),
    "SE": re.compile(r"\b(\d{3}\s?\d{2})\b"),
    "DK": re.compile(r"\b(\d{4})\b"),
    "NO": re.compile(r"\b(\d{4})\b"),
}

# Fallback: general 4-6 digit postal code
POSTAL_CODE_FALLBACK = re.compile(r"\b(\d{4,6})\b")


@dataclass
class ParsedAddress:
    """Structured address components extracted from a raw address string."""

    street_address: str | None = None
    city: str | None = None
    state_or_region: str | None = None
    postal_code: str | None = None
    country_code: str | None = None
    country_name: str | None = None


class LocationParser:
    """
    Parse combined address strings and optionally geocode via Nominatim.

    Address parsing is always free (no API calls). Geocoding only runs
    when ``geocoding_enabled=True`` and coordinates are missing.
    """

    def __init__(self, geocoding_enabled: bool = False) -> None:
        self.geocoding_enabled = geocoding_enabled
        self._geocoder = None
        self._rate_limiter = None

    # ------------------------------------------------------------------
    # Address parsing (no external calls)
    # ------------------------------------------------------------------

    def parse_address(
        self,
        raw: str,
        known_city: str | None = None,
        known_country_code: str | None = None,
    ) -> ParsedAddress:
        """
        Parse a combined address string into structured components.

        RA.co typically uses ``;`` as delimiter:
            ``"Carrer Nou de Sant Francesc, 5; 08002 Barcelona; Spain"``

        Falls back to ``,`` splitting when no ``;`` is present.
        """
        if not raw:
            return ParsedAddress()

        # Split on `;` first, then `,` fallback
        if ";" in raw:
            parts = [p.strip() for p in raw.split(";") if p.strip()]
        else:
            parts = [p.strip() for p in raw.split(",") if p.strip()]

        result = ParsedAddress()

        # --- Country detection (last segment) ---
        country_code = known_country_code
        country_name = None
        if parts:
            last = parts[-1].strip()
            detected_code = self._detect_country(last)
            if detected_code:
                country_code = detected_code
                country_name = last
                parts = parts[:-1]  # remove country from parts

        result.country_code = country_code.upper() if country_code else None
        result.country_name = country_name

        # --- Postal code extraction ---
        postal_code = self._extract_postal_code(
            " ".join(parts),
            country_code=country_code,
        )
        result.postal_code = postal_code

        # --- City detection ---
        city = known_city
        if not city and len(parts) >= 2:
            # City is usually the second-to-last segment (before country)
            candidate = parts[-1].strip()
            # Remove postal code from candidate if embedded
            if postal_code and postal_code in candidate:
                candidate = candidate.replace(postal_code, "").strip()
            if candidate:
                city = candidate
        result.city = city

        # --- Street address (remaining parts, excluding city/postal) ---
        street_parts = []
        for part in parts:
            part_clean = part.strip()
            if city and part_clean == city:
                continue
            if postal_code and postal_code in part_clean:
                # Remove postal code but keep remaining text
                remainder = part_clean.replace(postal_code, "").strip()
                # If remainder is the city, skip entirely
                if remainder and remainder != city:
                    street_parts.append(remainder)
                elif remainder == city:
                    continue
                continue
            street_parts.append(part_clean)

        if street_parts:
            result.street_address = ", ".join(street_parts)

        # --- State/region heuristic ---
        # For ES: province from postal code prefix
        if country_code and country_code.upper() == "ES" and postal_code and len(postal_code) == 5:
            result.state_or_region = self._spanish_province_from_postal(postal_code)

        return result

    # ------------------------------------------------------------------
    # Geocoding (Nominatim, rate-limited, cached)
    # ------------------------------------------------------------------

    def geocode(
        self,
        address: str,
        city: str | None = None,
        country_code: str | None = None,
    ) -> Coordinates | None:
        """
        Geocode an address string via Nominatim.

        Returns ``None`` immediately when ``self.geocoding_enabled`` is False,
        or when the geocoder fails or returns low-precision results.
        """
        if not self.geocoding_enabled:
            return None

        query = self._build_geocode_query(address, city, country_code)
        if not query:
            return None

        return self._geocode_cached(query, country_code)

    @lru_cache(maxsize=512)
    def _geocode_cached(
        self,
        query: str,
        country_code: str | None = None,
    ) -> Coordinates | None:
        """LRU-cached geocoding call."""
        try:
            geocoder = self._get_geocoder()
            if geocoder is None:
                return None

            kwargs = {"exactly_one": True}
            if country_code:
                kwargs["country_codes"] = country_code.upper()

            location = self._get_rate_limiter()(query, **kwargs)
            if location is None:
                logger.debug("Nominatim returned no result for query: %s", query)
                return None

            return self._validate_coordinates(location.latitude, location.longitude)

        except Exception:
            logger.warning("Geocoding failed for query: %s", query, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Location enrichment orchestrator
    # ------------------------------------------------------------------

    def enrich_location(self, location: LocationInfo) -> LocationInfo:
        """
        Enrich a LocationInfo object in-place.

        1. Always parse ``street_address`` to backfill ``postal_code`` / ``state_or_region``.
        2. If ``coordinates`` is still None **and** geocoding is enabled, try Nominatim.

        Returns the same (mutated) LocationInfo for convenience.
        """
        # --- Step 1: address parsing (free, no API calls) ---
        parsed = None
        if location.street_address:
            parsed = self.parse_address(
                raw=location.street_address,
                known_city=location.city,
                known_country_code=location.country_code,
            )
            if parsed.postal_code and not location.postal_code:
                location.postal_code = parsed.postal_code
            if parsed.state_or_region and not location.state_or_region:
                location.state_or_region = parsed.state_or_region
            # Update street_address to cleaned version (postal code, city, country stripped)
            if parsed.street_address:
                location.street_address = parsed.street_address

        # --- Step 2: geocoding fallback ---
        if location.coordinates is None and self.geocoding_enabled:
            # Try venue name first (Nominatim handles "Macarena Club, Barcelona" well).
            # Fall back to parsed street address if venue name fails.
            coords = None
            if location.venue_name:
                coords = self.geocode(
                    address=location.venue_name,
                    city=location.city,
                    country_code=location.country_code,
                )
            if coords is None and parsed and parsed.street_address:
                coords = self.geocode(
                    address=parsed.street_address,
                    city=location.city,
                    country_code=location.country_code,
                )
            if coords is not None:
                location.coordinates = coords

        return location

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_geocoder(self):
        """Lazy-initialize Nominatim geocoder."""
        if self._geocoder is None:
            try:
                from geopy.geocoders import Nominatim

                user_agent = os.environ.get("GEOCODING_API_KEY") or "pulsecity-event-platform"
                self._geocoder = Nominatim(user_agent=user_agent, timeout=10)
            except ImportError:
                logger.warning("geopy not installed; geocoding disabled")
                return None
        return self._geocoder

    def _get_rate_limiter(self):
        """Lazy-initialize rate limiter (1 req/sec for Nominatim ToS)."""
        if self._rate_limiter is None:
            from geopy.extra.rate_limiter import RateLimiter

            self._rate_limiter = RateLimiter(
                self._get_geocoder().geocode,
                min_delay_seconds=1.0,
            )
        return self._rate_limiter

    @staticmethod
    def _build_geocode_query(
        address: str,
        city: str | None,
        country_code: str | None,
    ) -> str:
        """Build a geocode query string from components."""
        parts = []
        if address:
            parts.append(address)
        if city:
            parts.append(city)
        return ", ".join(parts) if parts else ""

    @staticmethod
    def _validate_coordinates(lat: float, lng: float) -> Coordinates | None:
        """
        Validate and round coordinates.

        Only accepts coordinates with >= 4 decimal places of precision.
        Rounds to 6 decimal places (~0.11m precision).
        """
        from src.schemas.event import Coordinates

        lat_rounded = round(lat, 6)
        lng_rounded = round(lng, 6)

        # Check minimum precision (4 decimal places)
        lat_str = str(lat_rounded).split(".")[-1] if "." in str(lat_rounded) else ""
        lng_str = str(lng_rounded).split(".")[-1] if "." in str(lng_rounded) else ""

        if len(lat_str) < 4 or len(lng_str) < 4:
            logger.debug(
                "Coordinates have insufficient precision: lat=%s lng=%s",
                lat_rounded,
                lng_rounded,
            )
            return None

        try:
            return Coordinates(latitude=lat_rounded, longitude=lng_rounded)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _detect_country(text: str) -> str | None:
        """Detect ISO country code from text (country name or code)."""
        cleaned = text.strip().lower()
        # Direct code match (2-letter)
        if len(cleaned) == 2 and cleaned.upper() in {v for v in COUNTRY_NAME_TO_CODE.values()}:
            return cleaned.upper()
        return COUNTRY_NAME_TO_CODE.get(cleaned)

    @staticmethod
    def _extract_postal_code(text: str, country_code: str | None = None) -> str | None:
        """Extract postal code from text using country-aware patterns."""
        if not text:
            return None

        # Try country-specific pattern first
        if country_code:
            pattern = POSTAL_CODE_PATTERNS.get(country_code.upper())
            if pattern:
                match = pattern.search(text)
                if match:
                    return match.group(1)

        # Try all known patterns
        for pattern in POSTAL_CODE_PATTERNS.values():
            match = pattern.search(text)
            if match:
                return match.group(1)

        # Fallback
        match = POSTAL_CODE_FALLBACK.search(text)
        return match.group(1) if match else None

    @staticmethod
    def _spanish_province_from_postal(postal_code: str) -> str | None:
        """Map Spanish postal code prefix to province/community name."""
        prefix_map = {
            "01": "Araba/Alava",
            "02": "Albacete",
            "03": "Alicante",
            "04": "Almeria",
            "05": "Avila",
            "06": "Badajoz",
            "07": "Illes Balears",
            "08": "Barcelona",
            "09": "Burgos",
            "10": "Caceres",
            "11": "Cadiz",
            "12": "Castellon",
            "13": "Ciudad Real",
            "14": "Cordoba",
            "15": "A Coruna",
            "16": "Cuenca",
            "17": "Girona",
            "18": "Granada",
            "19": "Guadalajara",
            "20": "Gipuzkoa",
            "21": "Huelva",
            "22": "Huesca",
            "23": "Jaen",
            "24": "Leon",
            "25": "Lleida",
            "26": "La Rioja",
            "27": "Lugo",
            "28": "Madrid",
            "29": "Malaga",
            "30": "Murcia",
            "31": "Navarra",
            "32": "Ourense",
            "33": "Asturias",
            "34": "Palencia",
            "35": "Las Palmas",
            "36": "Pontevedra",
            "37": "Salamanca",
            "38": "Santa Cruz de Tenerife",
            "39": "Cantabria",
            "40": "Segovia",
            "41": "Sevilla",
            "42": "Soria",
            "43": "Tarragona",
            "44": "Teruel",
            "45": "Toledo",
            "46": "Valencia",
            "47": "Valladolid",
            "48": "Bizkaia",
            "49": "Zamora",
            "50": "Zaragoza",
            "51": "Ceuta",
            "52": "Melilla",
        }
        prefix = postal_code[:2]
        return prefix_map.get(prefix)
