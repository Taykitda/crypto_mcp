"""Symbol normalization, alias mapping, and security validation.

Protects against SSRF / injection by strictly validating user inputs,
and normalizes fuzzy token names (e.g. 'bitcoin' -> 'BTC').
"""

import re
from typing import Optional

# Strict alphanumeric + hyphen/underscore validation (max 20 chars)
SYMBOL_REGEX = re.compile(r"^[a-zA-Z0-9\-_]{1,20}$")

# Common alias to standard ticker symbol mapping
ALIAS_MAP: dict[str, str] = {
    "bitcoin": "BTC",
    "btc": "BTC",
    "xbt": "BTC",
    "ethereum": "ETH",
    "eth": "ETH",
    "ether": "ETH",
    "solana": "SOL",
    "sol": "SOL",
    "binancecoin": "BNB",
    "bnb": "BNB",
    "ripple": "XRP",
    "xrp": "XRP",
    "dogecoin": "DOGE",
    "doge": "DOGE",
    "cardano": "ADA",
    "ada": "ADA",
    "tether": "USDT",
    "usdt": "USDT",
    "usd-coin": "USDC",
    "usdc": "USDC",
    "pepe": "PEPE",
    "shiba": "SHIB",
    "shib": "SHIB",
    "shiba-inu": "SHIB",
    "avalanche": "AVAX",
    "avax": "AVAX",
    "polkadot": "DOT",
    "dot": "DOT",
    "chainlink": "LINK",
    "link": "LINK",
    "sui": "SUI",
    "toncoin": "TON",
    "ton": "TON",
    "near": "NEAR",
    "polygon": "POL",
    "matic": "POL",
    "pol": "POL",
    "uniswap": "UNI",
    "uni": "UNI",
    "monero": "XMR",
    "xmr": "XMR",
}

# Standard ticker to CoinGecko coin_id mapping
COINGECKO_ID_MAP: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "USDT": "tether",
    "USDC": "usd-coin",
    "PEPE": "pepe",
    "SHIB": "shiba-inu",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "LINK": "chainlink",
    "SUI": "sui",
    "TON": "the-open-network",
    "NEAR": "near",
    "POL": "polygon-ecosystem-token",
    "UNI": "uniswap",
    "XMR": "monero",
}

# Standard supported fiat & stable quote currencies
SUPPORTED_VS_CURRENCIES = {
    "USD", "USDT", "USDC", "EUR", "CNY", "JPY", "GBP", "AUD", "CAD", "HKD", "KRW"
}


def sanitize_and_validate_symbol(symbol: str) -> str:
    """Validate and clean input symbol.
    
    Raises:
        ValueError: If symbol contains illegal characters or is too long.
    """
    if not symbol:
        raise ValueError("Symbol cannot be empty.")
    
    cleaned = symbol.strip().lower()
    if not SYMBOL_REGEX.match(cleaned):
        raise ValueError(
            f"Invalid symbol '{symbol}'. Symbols must be alphanumeric (1-20 characters)."
        )
    return cleaned


def normalize_symbol(symbol: str) -> str:
    """Normalize input symbol to uppercase standard ticker.
    
    Examples:
        'bitcoin' -> 'BTC'
        'btc' -> 'BTC'
        'ETH' -> 'ETH'
    """
    cleaned = sanitize_and_validate_symbol(symbol)
    return ALIAS_MAP.get(cleaned, cleaned.upper())


def normalize_vs_currency(vs_currency: str = "usd") -> str:
    """Validate and normalize quote currency."""
    if not vs_currency:
        return "USD"
    cleaned = sanitize_and_validate_symbol(vs_currency).upper()
    return cleaned


def get_coingecko_id(symbol: str) -> str:
    """Get CoinGecko coin_id from symbol or alias."""
    norm = normalize_symbol(symbol)
    if norm in COINGECKO_ID_MAP:
        return COINGECKO_ID_MAP[norm]
    # Fallback: if user passed a coingecko id directly (e.g. 'pepe-fork')
    return symbol.strip().lower()


def get_binance_pair(symbol: str, vs_currency: str = "USD") -> str:
    """Convert symbol and vs_currency to Binance market pair.
    
    Binance pairs use USDT for USD pricing (e.g. BTCUSDT).
    """
    norm_symbol = normalize_symbol(symbol)
    norm_vs = normalize_vs_currency(vs_currency)
    
    # Binance quote currency substitution
    if norm_vs == "USD":
        norm_vs = "USDT"
    
    return f"{norm_symbol}{norm_vs}"


def get_okx_inst_id(symbol: str, vs_currency: str = "USD") -> str:
    """Convert symbol and vs_currency to OKX instrument ID.
    
    OKX uses format: BTC-USDT.
    """
    norm_symbol = normalize_symbol(symbol)
    norm_vs = normalize_vs_currency(vs_currency)
    
    if norm_vs == "USD":
        norm_vs = "USDT"
    
    return f"{norm_symbol}-{norm_vs}"
