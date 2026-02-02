"""
Ra.co HTML Parser.

BeautifulSoup-based parser for extracting event data from ra.co event pages.
"""

from __future__ import annotations

import re
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


logger = logging.getLogger(__name__)


class RaCoEventParser:
    """
    Parser for ra.co event pages.

    Extracts structured event data from HTML using BeautifulSoup.
    """

    def __init__(self):
        """Initialize the parser."""
        if BeautifulSoup is None:
            raise ImportError(
                "beautifulsoup4 is required for HTML parsing. "
                "Install it with: pip install beautifulsoup4 lxml"
            )

    def parse(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parse ra.co event page HTML.

        Args:
            html: Raw HTML content
            url: URL of the event page

        Returns:
            Dictionary with extracted event fields

        Raises:
            ValueError: If HTML cannot be parsed
        """
        if not html:
            raise ValueError("Empty HTML content")

        soup = BeautifulSoup(html, "lxml")

        # Extract event ID from URL
        source_event_id = self._extract_event_id(url)

        # Try to extract JSON-LD structured data first (most reliable)
        structured_data = self._extract_json_ld(soup)

        # Fall back to HTML parsing
        return {
            "source_event_id": source_event_id,
            "title": self._extract_title(soup, structured_data),
            "description": self._extract_description(soup, structured_data),
            "start_datetime": self._extract_start_datetime(soup, structured_data),
            "end_datetime": self._extract_end_datetime(soup, structured_data),
            "venue_name": self._extract_venue_name(soup, structured_data),
            "venue_address": self._extract_venue_address(soup, structured_data),
            "city": self._extract_city(soup, structured_data),
            "country_code": self._extract_country_code(soup, url),
            "artists": self._extract_artists(soup),
            "genres": self._extract_genres(soup),
            "price": self._extract_price(soup, structured_data),
            "image_url": self._extract_image(soup, structured_data),
            "source_url": url,
        }

    def _extract_event_id(self, url: str) -> str:
        """Extract event ID from URL."""
        # Ra.co URLs: https://ra.co/events/1234567
        match = re.search(r"/events/(\d+)", url)
        return match.group(1) if match else ""

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract JSON-LD structured data if available."""
        try:
            for script in soup.find_all("script", type="application/ld+json"):
                data = json.loads(script.string)
                # Handle array of items
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Event":
                            return item
                elif data.get("@type") == "Event":
                    return data
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass
        return None

    def _extract_title(
        self, soup: BeautifulSoup, structured_data: Optional[Dict]
    ) -> str:
        """Extract event title."""
        # Try structured data first
        if structured_data and structured_data.get("name"):
            return structured_data["name"]

        # Try common selectors
        selectors = [
            "h1",
            "[data-testid='event-title']",
            ".event-title",
            ".event-header h1",
            "meta[property='og:title']",
        ]

        for selector in selectors:
            if selector.startswith("meta"):
                elem = soup.select_one(selector)
                if elem and elem.get("content"):
                    return elem["content"]
            else:
                elem = soup.select_one(selector)
                if elem and elem.get_text(strip=True):
                    return elem.get_text(strip=True)

        return "Untitled Event"

    def _extract_description(
        self, soup: BeautifulSoup, structured_data: Optional[Dict]
    ) -> Optional[str]:
        """Extract event description."""
        # Try structured data first
        if structured_data and structured_data.get("description"):
            return structured_data["description"]

        # Try meta description
        meta_desc = soup.select_one("meta[name='description']")
        if meta_desc and meta_desc.get("content"):
            return meta_desc["content"]

        # Try common selectors
        selectors = [
            "[data-testid='event-description']",
            ".event-description",
            ".event-content",
            "article p",
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if len(text) > 50:  # Meaningful description
                    return text

        return None

    def _extract_start_datetime(
        self, soup: BeautifulSoup, structured_data: Optional[Dict]
    ) -> Optional[str]:
        """Extract event start datetime."""
        # Try structured data first
        if structured_data and structured_data.get("startDate"):
            return structured_data["startDate"]

        # Try time elements
        time_elem = soup.select_one("time[datetime]")
        if time_elem and time_elem.get("datetime"):
            return time_elem["datetime"]

        # Try common selectors
        selectors = [
            "[data-testid='event-date']",
            ".event-date",
            ".date-time",
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                # Try to parse date text
                text = elem.get_text(strip=True)
                return self._parse_date_text(text)

        return None

    def _extract_end_datetime(
        self, soup: BeautifulSoup, structured_data: Optional[Dict]
    ) -> Optional[str]:
        """Extract event end datetime."""
        if structured_data and structured_data.get("endDate"):
            return structured_data["endDate"]
        return None

    def _extract_venue_name(
        self, soup: BeautifulSoup, structured_data: Optional[Dict]
    ) -> Optional[str]:
        """Extract venue name."""
        # Try structured data first
        if structured_data:
            location = structured_data.get("location", {})
            if isinstance(location, dict):
                return location.get("name")

        # Try common selectors
        selectors = [
            "[data-testid='venue-name']",
            ".venue-name",
            ".venue a",
            ".location-name",
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text(strip=True):
                return elem.get_text(strip=True)

        return None

    def _extract_venue_address(
        self, soup: BeautifulSoup, structured_data: Optional[Dict]
    ) -> Optional[str]:
        """Extract venue address."""
        # Try structured data first
        if structured_data:
            location = structured_data.get("location", {})
            if isinstance(location, dict):
                address = location.get("address", {})
                if isinstance(address, dict):
                    parts = [
                        address.get("streetAddress", ""),
                        address.get("addressLocality", ""),
                        address.get("postalCode", ""),
                    ]
                    return ", ".join(p for p in parts if p)
                elif isinstance(address, str):
                    return address

        # Try common selectors
        selectors = [
            "[data-testid='venue-address']",
            ".venue-address",
            ".address",
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text(strip=True):
                return elem.get_text(strip=True)

        return None

    def _extract_city(
        self, soup: BeautifulSoup, structured_data: Optional[Dict]
    ) -> Optional[str]:
        """Extract city name."""
        # Try structured data first
        if structured_data:
            location = structured_data.get("location", {})
            if isinstance(location, dict):
                address = location.get("address", {})
                if isinstance(address, dict):
                    return address.get("addressLocality")

        # Try to extract from breadcrumbs or location text
        for selector in [".breadcrumb", ".location", ".area"]:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # Common cities in ra.co
                cities = ["Barcelona", "London", "Berlin", "Amsterdam", "Paris", "Madrid"]
                for city in cities:
                    if city.lower() in text.lower():
                        return city

        return None

    def _extract_country_code(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Extract country code from URL or content."""
        # Try to extract from URL: /events/es/barcelona or /events/gb/london
        match = re.search(r"/events/([a-z]{2})/", url)
        if match:
            return match.group(1).upper()

        # Try structured data
        # Default to ES for Spanish events
        return None

    def _extract_artists(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract artist lineup."""
        artists = []

        # Try common selectors
        selectors = [
            "[data-testid='lineup'] a",
            ".lineup a",
            ".artist-name",
            ".artists a",
            ".dj-name",
        ]

        seen_names = set()
        for selector in selectors:
            for elem in soup.select(selector):
                name = elem.get_text(strip=True)
                if name and name not in seen_names and len(name) > 1:
                    seen_names.add(name)
                    artists.append({"name": name})

        return artists

    def _extract_genres(self, soup: BeautifulSoup) -> List[str]:
        """Extract music genres/tags."""
        genres = []

        # Try common selectors
        selectors = [
            ".genre",
            ".tag",
            ".music-style",
            "[data-testid='genre']",
        ]

        seen = set()
        for selector in selectors:
            for elem in soup.select(selector):
                genre = elem.get_text(strip=True)
                if genre and genre not in seen:
                    seen.add(genre)
                    genres.append(genre)

        return genres

    def _extract_price(
        self, soup: BeautifulSoup, structured_data: Optional[Dict]
    ) -> str:
        """Extract price information."""
        # Try structured data first
        if structured_data:
            offers = structured_data.get("offers", {})
            if isinstance(offers, dict):
                price = offers.get("price")
                currency = offers.get("priceCurrency", "")
                if price:
                    return f"{currency}{price}"
            elif isinstance(offers, list) and offers:
                offer = offers[0]
                price = offer.get("price")
                currency = offer.get("priceCurrency", "")
                if price:
                    return f"{currency}{price}"

        # Try common selectors
        selectors = [
            "[data-testid='ticket-price']",
            ".price",
            ".cost",
            ".ticket-price",
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return text

        return ""

    def _extract_image(
        self, soup: BeautifulSoup, structured_data: Optional[Dict]
    ) -> Optional[str]:
        """Extract event image URL."""
        # Try structured data first
        if structured_data:
            image = structured_data.get("image")
            if isinstance(image, list) and image:
                return image[0]
            elif isinstance(image, str):
                return image

        # Try og:image
        og_image = soup.select_one("meta[property='og:image']")
        if og_image and og_image.get("content"):
            return og_image["content"]

        # Try common selectors
        selectors = [
            ".event-image img",
            ".flyer img",
            ".event-flyer img",
            "article img",
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                src = elem.get("src") or elem.get("data-src")
                if src and src.startswith("http"):
                    return src

        return None

    def _parse_date_text(self, text: str) -> Optional[str]:
        """
        Attempt to parse date from text.

        Args:
            text: Date text to parse

        Returns:
            ISO format datetime string or None
        """
        # This is a simplified parser - would need more robust handling
        # for ra.co's specific date formats
        text = text.strip()

        # Try common patterns
        patterns = [
            (r"(\d{1,2})\s+(\w+)\s+(\d{4})", "%d %B %Y"),
            (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),
        ]

        for pattern, fmt in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    dt = datetime.strptime(match.group(), fmt)
                    return dt.isoformat()
                except ValueError:
                    continue

        return None

    def parse_listing_page(self, html: str) -> List[str]:
        """
        Extract event URLs from a listing page.

        Args:
            html: HTML content of listing page

        Returns:
            List of event URLs
        """
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        urls = []

        # Find all event links
        for link in soup.select("a[href*='/events/']"):
            href = link.get("href", "")
            # Match event detail pages: /events/1234567
            if re.match(r"/events/\d+$", href):
                urls.append(f"https://ra.co{href}")

        return list(dict.fromkeys(urls))  # Dedupe while preserving order
