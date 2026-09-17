"""Tests for symbol normalization and input validation."""

import pytest
from crypto_mcp.utils.normalizer import (
    sanitize_and_validate_symbol,
    normalize_symbol,
    normalize_vs_currency,
    get_coingecko_id,
    get_binance_pair,
    get_okx_inst_id,
)


def test_sanitize_and_validate_valid():
    assert sanitize_and_validate_symbol("btc") == "btc"
    assert sanitize_and_validate_symbol("  ETH  ") == "eth"
    assert sanitize_and_validate_symbol("pepe-coin") == "pepe-coin"
    assert sanitize_and_validate_symbol("token_123") == "token_123"


def test_sanitize_and_validate_invalid_injections():
    """Verify malicious or special character inputs are blocked."""
    with pytest.raises(ValueError, match="Invalid symbol"):
        sanitize_and_validate_symbol("btc; DROP TABLE")
    with pytest.raises(ValueError, match="Invalid symbol"):
        sanitize_and_validate_symbol("../../etc/passwd")
    with pytest.raises(ValueError, match="Invalid symbol"):
        sanitize_and_validate_symbol("btc<script>")
    with pytest.raises(ValueError, match="cannot be empty"):
        sanitize_and_validate_symbol("")
    with pytest.raises(ValueError, match="Invalid symbol"):
        sanitize_and_validate_symbol("a" * 25)  # Too long


def test_normalize_symbol_aliases():
    assert normalize_symbol("bitcoin") == "BTC"
    assert normalize_symbol("btc") == "BTC"
    assert normalize_symbol("xbt") == "BTC"
    assert normalize_symbol("ethereum") == "ETH"
    assert normalize_symbol("ether") == "ETH"
    assert normalize_symbol("solana") == "SOL"
    assert normalize_symbol("shiba-inu") == "SHIB"
    assert normalize_symbol("unknowncoin") == "UNKNOWNCOIN"


def test_normalize_vs_currency():
    assert normalize_vs_currency() == "USD"
    assert normalize_vs_currency("usd") == "USD"
    assert normalize_vs_currency("cny") == "CNY"
    assert normalize_vs_currency("eur") == "EUR"


def test_get_coingecko_id():
    assert get_coingecko_id("BTC") == "bitcoin"
    assert get_coingecko_id("bitcoin") == "bitcoin"
    assert get_coingecko_id("ETH") == "ethereum"
    assert get_coingecko_id("pepe-fork") == "pepe-fork"


def test_get_binance_and_okx_identifiers():
    assert get_binance_pair("BTC", "USD") == "BTCUSDT"
    assert get_binance_pair("ETH", "EUR") == "ETHEUR"
    assert get_okx_inst_id("BTC", "USD") == "BTC-USDT"
    assert get_okx_inst_id("SOL", "USDC") == "SOL-USDC"
