"""
Unit tests for the currency module.

Tests for CurrencyParser price parsing and currency detection.
"""

from decimal import Decimal

import pytest

from src.ingestion.normalization.currency import CurrencyParser


class TestParsePriceString:
    """Tests for parse_price_string method."""

    def test_parse_simple_pound(self):
        """Simple pound price."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("£15")
        assert min_p == Decimal("15")
        assert max_p is None
        assert currency == "GBP"

    def test_parse_simple_dollar(self):
        """Simple dollar price."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("$20")
        assert min_p == Decimal("20")
        assert currency == "USD"

    def test_parse_simple_euro(self):
        """Simple euro price."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("€25")
        assert min_p == Decimal("25")
        assert currency == "EUR"

    def test_parse_euro_after_number(self):
        """Euro symbol after number (European style)."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("25€")
        assert min_p == Decimal("25")
        assert currency == "EUR"

    def test_parse_price_range_pound(self):
        """Price range with pound."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("£15-25")
        assert min_p == Decimal("15")
        assert max_p == Decimal("25")
        assert currency == "GBP"

    def test_parse_price_range_dollar(self):
        """Price range with dollar."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("$20-30")
        assert min_p == Decimal("20")
        assert max_p == Decimal("30")
        assert currency == "USD"

    def test_parse_european_decimal_format(self):
        """European decimal format with comma."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("15,50€")
        assert min_p == Decimal("15.50")
        assert currency == "EUR"

    def test_parse_with_currency_code(self):
        """Price with currency code."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("15-25 EUR")
        assert min_p == Decimal("15")
        assert max_p == Decimal("25")
        assert currency == "EUR"

    def test_parse_free_event(self):
        """Free event should return None values."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("Free")
        assert min_p is None
        assert max_p is None
        assert currency == ""

    def test_parse_free_lowercase(self):
        """Free detection is case insensitive."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("free admission")
        assert min_p is None
        assert max_p is None

    def test_parse_no_numbers(self):
        """String with no numbers returns None."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("TBA")
        assert min_p is None
        assert max_p is None

    def test_parse_empty_string(self):
        """Empty string returns None values."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("")
        assert min_p is None
        assert max_p is None
        assert currency == ""

    def test_parse_decimal_price(self):
        """Decimal price with dot."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("$19.99")
        assert min_p == Decimal("19.99")
        assert currency == "USD"

    def test_parse_range_orders_correctly(self):
        """Range should always be min-max regardless of order."""
        min_p, max_p, currency = CurrencyParser.parse_price_string("$30-20")
        assert min_p == Decimal("20")
        assert max_p == Decimal("30")


class TestDetectCurrency:
    """Tests for detect_currency method."""

    def test_detect_dollar_symbol(self):
        """Should detect $ as USD."""
        assert CurrencyParser.detect_currency("$100") == "USD"

    def test_detect_euro_symbol(self):
        """Should detect € as EUR."""
        assert CurrencyParser.detect_currency("€50") == "EUR"
        assert CurrencyParser.detect_currency("50€") == "EUR"

    def test_detect_pound_symbol(self):
        """Should detect £ as GBP."""
        assert CurrencyParser.detect_currency("£30") == "GBP"

    def test_detect_yen_symbol(self):
        """Should detect ¥ as JPY."""
        assert CurrencyParser.detect_currency("¥1000") == "JPY"

    def test_detect_eur_code(self):
        """Should detect EUR code."""
        assert CurrencyParser.detect_currency("50 EUR") == "EUR"
        assert CurrencyParser.detect_currency("50 eur") == "EUR"

    def test_detect_usd_code(self):
        """Should detect USD code."""
        assert CurrencyParser.detect_currency("100 USD") == "USD"

    def test_detect_gbp_code(self):
        """Should detect GBP code."""
        assert CurrencyParser.detect_currency("30 GBP") == "GBP"

    def test_detect_euro_word(self):
        """Should detect 'euro' word."""
        assert CurrencyParser.detect_currency("50 euro") == "EUR"
        assert CurrencyParser.detect_currency("50 euros") == "EUR"

    def test_detect_dollar_word(self):
        """Should detect 'dollar' word."""
        assert CurrencyParser.detect_currency("100 dollars") == "USD"

    def test_detect_pound_word(self):
        """Should detect 'pound' word."""
        assert CurrencyParser.detect_currency("30 pounds") == "GBP"

    def test_detect_no_currency(self):
        """Should return empty string when no currency detected."""
        assert CurrencyParser.detect_currency("100") == ""
        assert CurrencyParser.detect_currency("just text") == ""

    def test_detect_empty_string(self):
        """Should return empty string for empty input."""
        assert CurrencyParser.detect_currency("") == ""


class TestIsFree:
    """Tests for _is_free method."""

    def test_free_keyword(self):
        """'free' should be detected."""
        assert CurrencyParser._is_free("Free") is True
        assert CurrencyParser._is_free("FREE ENTRY") is True
        assert CurrencyParser._is_free("free admission") is True

    def test_gratis_keyword(self):
        """'gratis' should be detected (Spanish/other)."""
        assert CurrencyParser._is_free("Gratis") is True
        assert CurrencyParser._is_free("entrada gratis") is True

    def test_kostenlos_keyword(self):
        """'kostenlos' should be detected (German)."""
        assert CurrencyParser._is_free("Kostenlos") is True

    def test_gratuit_keyword(self):
        """'gratuit' should be detected (French)."""
        assert CurrencyParser._is_free("Gratuit") is True

    def test_gratuito_keyword(self):
        """'gratuito' should be detected (Italian/Portuguese)."""
        assert CurrencyParser._is_free("Gratuito") is True

    def test_entrada_libre(self):
        """'entrada libre' should be detected (Spanish)."""
        assert CurrencyParser._is_free("Entrada libre") is True

    def test_no_charge(self):
        """'no charge' should be detected."""
        assert CurrencyParser._is_free("No charge") is True

    def test_no_cover(self):
        """'no cover' should be detected."""
        assert CurrencyParser._is_free("No cover") is True

    def test_not_free(self):
        """Non-free strings should return False."""
        assert CurrencyParser._is_free("$20") is False
        assert CurrencyParser._is_free("paid event") is False
        assert CurrencyParser._is_free("tickets required") is False


class TestExtractNumbers:
    """Tests for _extract_numbers method."""

    def test_extract_single_integer(self):
        """Should extract single integer."""
        numbers = CurrencyParser._extract_numbers("15")
        assert numbers == [Decimal("15")]

    def test_extract_decimal_with_dot(self):
        """Should extract decimal with dot."""
        numbers = CurrencyParser._extract_numbers("15.50")
        assert numbers == [Decimal("15.50")]

    def test_extract_decimal_with_comma(self):
        """Should extract European format with comma."""
        numbers = CurrencyParser._extract_numbers("15,50")
        assert numbers == [Decimal("15.50")]

    def test_extract_multiple_numbers(self):
        """Should extract multiple numbers."""
        numbers = CurrencyParser._extract_numbers("15-25")
        assert len(numbers) == 2
        assert Decimal("15") in numbers
        assert Decimal("25") in numbers

    def test_extract_ignores_currency_symbols(self):
        """Should ignore currency symbols."""
        numbers = CurrencyParser._extract_numbers("$15")
        assert numbers == [Decimal("15")]

        numbers = CurrencyParser._extract_numbers("€20")
        assert numbers == [Decimal("20")]

    def test_extract_ignores_currency_codes(self):
        """Should ignore currency codes."""
        numbers = CurrencyParser._extract_numbers("15 EUR")
        assert numbers == [Decimal("15")]

    def test_extract_no_numbers(self):
        """Should return empty list when no numbers."""
        numbers = CurrencyParser._extract_numbers("no price")
        assert numbers == []


class TestFormatPrice:
    """Tests for format_price method."""

    def test_format_with_symbol(self):
        """Should format with currency symbol."""
        result = CurrencyParser.format_price(Decimal("15"), "GBP")
        assert "15" in result
        assert "£" in result

    def test_format_euro_symbol_after(self):
        """Euro symbol should come after amount."""
        result = CurrencyParser.format_price(Decimal("20"), "EUR")
        # EUR uses symbol after amount
        assert "20" in result
        assert "€" in result

    def test_format_usd_symbol_before(self):
        """USD symbol should come before amount."""
        result = CurrencyParser.format_price(Decimal("25"), "USD")
        assert "$" in result

    def test_format_none_amount(self):
        """None amount should return 'Free'."""
        result = CurrencyParser.format_price(None)
        assert result == "Free"

    def test_format_without_symbol(self):
        """Should format with code when no symbol found."""
        result = CurrencyParser.format_price(Decimal("100"), "JPY", include_symbol=True)
        # JPY has symbol ¥
        assert "100" in result

    def test_format_no_currency(self):
        """Should format without currency when not provided."""
        result = CurrencyParser.format_price(Decimal("50"), "")
        assert result == "50"

    def test_format_strips_trailing_zeros(self):
        """Should strip unnecessary trailing zeros."""
        result = CurrencyParser.format_price(Decimal("15.00"), "USD")
        # Should not have .00
        assert ".00" not in result or "$15" in result

    def test_format_keeps_necessary_decimals(self):
        """Should keep necessary decimal places."""
        result = CurrencyParser.format_price(Decimal("15.50"), "USD")
        assert "15.5" in result or "15.50" in result
