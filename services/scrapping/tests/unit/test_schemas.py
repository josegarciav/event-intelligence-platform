import pytest

from scrapping.schemas.items import ProductItem


def test_product_item_valid():
    item = ProductItem(
        source_id="test",
        url="https://example.com/p1",
        title="Test Product",
        price="10.00",
        currency="USD",
    )
    assert item.source_id == "test"
    assert item.url == "https://example.com/p1"
    assert item.title == "Test Product"
    assert item.timestamp > 0


def test_product_item_missing_required():
    with pytest.raises(ValueError):
        # Title is required
        ProductItem(source_id="test", url="https://example.com/p1")


def test_product_item_invalid_url():
    with pytest.raises(ValueError):
        ProductItem(source_id="test", url="", title="Test")
