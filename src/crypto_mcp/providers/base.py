"""Base provider interface for crypto price data sources."""

from abc import ABC, abstractmethod
from typing import Optional
from crypto_mcp.models import CryptoPriceData, CryptoMarketData


class BasePriceProvider(ABC):
    """Abstract interface that all crypto price providers must implement."""

    name: str = "base"
    market_type: str = "cex_orderbook"  # or 'aggregated_dex_cex'

    @abstractmethod
    async def fetch_price(self, symbol: str, vs_currency: str = "USD") -> Optional[CryptoPriceData]:
        """Fetch latest spot price. Returns None if symbol is unsupported."""
        pass

    @abstractmethod
    async def fetch_market_data(self, symbol: str, vs_currency: str = "USD") -> Optional[CryptoMarketData]:
        """Fetch 24-hour ticker statistics. Returns None if unsupported."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider endpoint is reachable."""
        pass
