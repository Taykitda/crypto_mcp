"""Data models and response envelopes for the crypto MCP server.

Optimized for LLM context (concise, clear, and high precision).
"""

from datetime import datetime, timezone
from typing import Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class DataProvenance(BaseModel):
    """Metadata regarding data provenance, timing, and health status."""
    source: str = Field(description="Actual data provider (e.g., binance, okx, coingecko)")
    market_type: str = Field(
        default="cex_orderbook",
        description="Market semantics: 'cex_orderbook' (real-time CEX spot) or 'aggregated_dex_cex' (multi-exchange index)",
    )
    cached: bool = Field(default=False, description="Whether this response was served from memory cache")
    stale: bool = Field(default=False, description="True if external sources failed and stale cache fallback was used")
    cache_age_seconds: Optional[int] = Field(default=None, description="Age of cached data in seconds if cached")
    data_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC ISO8601 timestamp of when the price was generated",
    )
    latency_ms: Optional[int] = Field(default=None, description="Round-trip network latency in milliseconds")
    warning: Optional[str] = Field(default=None, description="Operational warning if fallback or stale data was used")


class CryptoPriceData(BaseModel):
    """Real-time spot price information."""
    symbol: str = Field(description="Normalized crypto asset symbol (e.g. BTC, ETH)")
    vs_currency: str = Field(default="USD", description="Quote currency (e.g. USD, CNY, EUR)")
    price: float = Field(description="Numeric price (IEEE 754 float)")
    price_str: str = Field(description="Exact decimal string representation without scientific notation")
    display_price: str = Field(description="Human-friendly formatted price string")
    metadata: DataProvenance = Field(description="Data provenance and status metadata")


class CryptoMarketData(BaseModel):
    """24-hour market overview and statistics."""
    symbol: str = Field(description="Normalized crypto asset symbol (e.g. BTC, ETH)")
    vs_currency: str = Field(default="USD", description="Quote currency")
    price: float = Field(description="Latest spot price")
    price_str: str = Field(description="Latest spot price string")
    display_price: str = Field(description="Human-friendly formatted price string")
    change_24h_percent: Optional[float] = Field(default=None, description="24-hour percentage price change")
    high_24h: Optional[float] = Field(default=None, description="24-hour highest price")
    high_24h_str: Optional[str] = Field(default=None, description="24-hour highest price as exact string")
    low_24h: Optional[float] = Field(default=None, description="24-hour lowest price")
    low_24h_str: Optional[str] = Field(default=None, description="24-hour lowest price as exact string")
    volume_24h: Optional[float] = Field(default=None, description="24-hour volume in quote currency")
    metadata: DataProvenance = Field(description="Data provenance and status metadata")


class BatchPriceData(BaseModel):
    """Batch prices result for multiple assets."""
    vs_currency: str = Field(default="USD")
    results: dict[str, CryptoPriceData] = Field(default_factory=dict, description="Map of symbol to price data")
    errors: dict[str, str] = Field(default_factory=dict, description="Map of failed symbols to error reasons")
    count: int = Field(description="Total successfully fetched count")


class ConversionData(BaseModel):
    """Calculated asset conversion result."""
    from_coin: str = Field(description="Source token or fiat")
    to_coin: str = Field(description="Target token or fiat")
    amount: float = Field(description="Source amount")
    converted_amount: float = Field(description="Converted target amount as float")
    converted_str: str = Field(description="Exact converted target amount string")
    rate: str = Field(description="Exchange rate ratio string (1 from_coin = rate to_coin)")
    metadata: DataProvenance = Field(description="Provenance of conversion rates")


class BaseResponse(BaseModel, Generic[T]):
    """Standard response envelope for all MCP tools."""
    success: bool = Field(description="True if operation succeeded")
    data: Optional[T] = Field(default=None, description="Payload data when success is True")
    error: Optional[str] = Field(default=None, description="Error message when success is False")
    suggestions: Optional[list[str]] = Field(default=None, description="Disambiguation or retry suggestions for Agent")
