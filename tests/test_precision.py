"""Tests for precision and formatting utilities."""

import pytest
from decimal import Decimal
from crypto_mcp.utils.precision import (
    format_crypto_price,
    display_price_with_currency,
    calculate_conversion,
    to_decimal,
)


def test_format_crypto_price_normal():
    assert format_crypto_price(68450.25) == "68450.25"
    assert format_crypto_price("100.5") == "100.5"
    assert format_crypto_price(0) == "0.0"


def test_format_crypto_price_micro_token():
    """Verify micro-token price (e.g. PEPE, SHIB) avoids scientific notation."""
    val = 0.0000084321
    res = format_crypto_price(val)
    assert res == "0.0000084321"
    assert "e" not in res.lower()

    super_micro = "0.000000001234"
    res2 = format_crypto_price(super_micro)
    assert res2 == "0.000000001234"
    assert "e" not in res2.lower()


def test_display_price_with_currency():
    assert display_price_with_currency(68450.25, "USD") == "$68,450.25"
    assert display_price_with_currency(12.5, "EUR") == "€12.5"
    assert display_price_with_currency(100, "CNY") == "¥100"

    # Micro price should include compact notation for Agent reference
    micro = display_price_with_currency(0.0000084321, "USD")
    assert "$0.0000084321" in micro
    assert "8.432e-06" in micro


def test_calculate_conversion():
    # 2 BTC (each $50,000) to ETH (each $2,500) -> 40 ETH
    amt, amt_str = calculate_conversion(
        amount=2,
        from_price_usd=50000,
        to_price_usd=2500,
    )
    assert amt == Decimal("40")
    assert amt_str == "40.0"

    # 100 USD to BTC (price $50,000) -> 0.002 BTC
    amt2, amt_str2 = calculate_conversion(
        amount=100,
        from_price_usd=1,
        to_price_usd=50000,
    )
    assert amt2 == Decimal("0.002")
    assert amt_str2 == "0.002"


def test_calculate_conversion_zero_target():
    with pytest.raises(ValueError, match="cannot be zero"):
        calculate_conversion(10, 100, 0)
