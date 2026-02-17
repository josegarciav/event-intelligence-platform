"""
Currency Parser.

Parses price strings and identifies currency (no conversion).
Keeps prices in their original currency.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


class CurrencyParser:
    """
    Parse price strings and identify currency.

    Does NOT convert currencies - keeps original values.
    """

    # Currency symbol to code mapping
    SYMBOL_TO_CODE = {
        "€": "EUR",
        "£": "GBP",
        "$": "USD",
        "¥": "JPY",
        "₹": "INR",
        "R$": "BRL",
        "A$": "AUD",
        "C$": "CAD",
        "CHF": "CHF",
        "kr": "SEK",  # Could also be NOK, DKK
        "zł": "PLN",
        "Kč": "CZK",
    }

    # Currency name/code patterns
    CURRENCY_PATTERNS = {
        "EUR": [r"\beur\b", r"\beuro\b", r"\beuros\b"],
        "GBP": [r"\bgbp\b", r"\bpound\b", r"\bpounds\b", r"\bsterling\b"],
        "USD": [r"\busd\b", r"\bdollar\b", r"\bdollars\b"],
        "JPY": [r"\bjpy\b", r"\byen\b"],
        "CHF": [r"\bchf\b", r"\bfranc\b", r"\bfrancs\b"],
    }

    @classmethod
    def parse_price_string(cls, price_str: str) -> tuple[Decimal | None, Decimal | None, str]:
        """
        Parse a price string into (min_price, max_price, currency_code).

        Handles various formats:
        - "£15" -> (15, None, "GBP")
        - "$20-30" -> (20, 30, "USD")
        - "10€" -> (10, None, "EUR")
        - "15-25 EUR" -> (15, 25, "EUR")
        - "Free" -> (None, None, "")
        - "10.50" -> (10.50, None, "")  # No currency detected

        Args:
            price_str: Price string to parse

        Returns:
            Tuple of (min_price, max_price, currency_code)
            - min_price: Minimum price as Decimal, or None if free/unknown
            - max_price: Maximum price as Decimal, or None if single price
            - currency_code: ISO currency code (e.g., "EUR", "GBP"), or "" if not detected
        """
        if not price_str:
            return None, None, ""

        price_str = price_str.strip()

        # Check for free events
        if cls._is_free(price_str):
            return None, None, ""

        # Detect currency
        currency = cls.detect_currency(price_str)

        # Extract numeric values
        numbers = cls._extract_numbers(price_str)

        if not numbers:
            return None, None, currency

        if len(numbers) == 1:
            return numbers[0], None, currency
        else:
            # Range: min-max
            return min(numbers), max(numbers), currency

    @classmethod
    def detect_currency(cls, price_str: str) -> str:
        """
        Detect currency from price string.

        Args:
            price_str: Price string to analyze

        Returns:
            ISO currency code (e.g., "EUR") or empty string if not detected
        """
        if not price_str:
            return ""

        # Check for currency symbols
        for symbol, code in cls.SYMBOL_TO_CODE.items():
            if symbol in price_str:
                return code

        # Check for currency names/codes in text
        price_lower = price_str.lower()
        for code, patterns in cls.CURRENCY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, price_lower):
                    return code

        return ""

    @classmethod
    def _is_free(cls, price_str: str) -> bool:
        """Check if price indicates a free event."""
        free_indicators = [
            "free",
            "gratis",
            "entrada libre",
            "entrada gratuita",
            "kostenlos",
            "gratuit",
            "gratuito",
            "無料",
            "costless",
            "no charge",
            "no cover",
        ]
        price_lower = price_str.lower()
        return any(indicator in price_lower for indicator in free_indicators)

    @classmethod
    def _extract_numbers(cls, price_str: str) -> list[Decimal]:
        """
        Extract numeric values from price string.

        Handles:
        - "15" -> [15]
        - "15.50" -> [15.50]
        - "15,50" -> [15.50] (European format)
        - "15-25" -> [15, 25]
        - "$10-$20" -> [10, 20]
        """
        # Remove currency symbols and common text
        clean = re.sub(r"[€£$¥₹]", "", price_str)
        clean = re.sub(
            r"\b(EUR|GBP|USD|JPY|CHF|AUD|CAD|BRL|PLN|CZK|SEK|NOK|DKK)\b",
            "",
            clean,
            flags=re.IGNORECASE,
        )

        # Find all number patterns (including decimals with . or ,)
        # Pattern matches: 15, 15.50, 15,50
        number_pattern = r"\d+(?:[.,]\d+)?"
        matches = re.findall(number_pattern, clean)

        numbers = []
        for match in matches:
            try:
                # Convert European format (comma decimal) to standard
                normalized = match.replace(",", ".")
                numbers.append(Decimal(normalized))
            except InvalidOperation:
                continue

        return numbers

    @classmethod
    def format_price(
        cls,
        amount: Decimal | None,
        currency: str = "",
        include_symbol: bool = True,
    ) -> str:
        """
        Format a price for display.

        Args:
            amount: Price amount
            currency: Currency code
            include_symbol: Whether to include currency symbol

        Returns:
            Formatted price string
        """
        if amount is None:
            return "Free" if not currency else ""

        # Get currency symbol
        symbol = ""
        if include_symbol:
            # Reverse lookup symbol from code
            for sym, code in cls.SYMBOL_TO_CODE.items():
                if code == currency:
                    symbol = sym
                    break

        # Format amount
        amount_str = f"{amount:.2f}"

        # Remove trailing zeros after decimal
        if "." in amount_str:
            amount_str = amount_str.rstrip("0").rstrip(".")

        if symbol:
            # Symbol position depends on currency
            if currency in ["EUR", "CHF"]:
                return f"{amount_str}{symbol}"
            else:
                return f"{symbol}{amount_str}"
        elif currency:
            return f"{amount_str} {currency}"
        else:
            return amount_str
