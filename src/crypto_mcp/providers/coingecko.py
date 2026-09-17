"""CoinGecko API provider adapter with local rate-limiting."""

import time
from typing import Optional
import httpx
from crypto_mcp.models import CryptoPriceData, CryptoMarketData, DataProvenance
from crypto_mcp.providers.base import BasePriceProvider
from crypto_mcp.utils.normalizer import normalize_symbol, get_coingecko_id
from crypto_mcp.utils.precision import format_crypto_price, display_price_with_currency
from crypto_mcp.governance.circuit_breaker import SlidingWindowRateLimiter
from crypto_mcp.utils.logging import logger


class CoinGeckoProvider(BasePriceProvider):
    name = "coingecko"
    market_type = "aggregated_dex_cex"
    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self, timeout: float = 4.0, max_requests_per_minute: int = 30):
        self.timeout = timeout
        # Protect against CoinGecko IP ban
        self.rate_limiter = SlidingWindowRateLimiter(
            max_requests=max_requests_per_minute,
            window_seconds=60.0,
        )

    async def fetch_price(self, symbol: str, vs_currency: str = "USD") -> Optional[CryptoPriceData]:
        if not self.rate_limiter.acquire():
            logger.warning("[CoinGecko] Throttled by local rate limiter.")
            raise httpx.HTTPStatusError(
                "Local rate limiter throttled request",
                request=None,  # type: ignore
                response=httpx.Response(status_code=429),
            )

        norm_symbol = normalize_symbol(symbol)
        coin_id = get_coingecko_id(norm_symbol)
        vs_curr = vs_currency.lower()

        url = f"{self.BASE_URL}/simple/price?ids={coin_id}&vs_currencies={vs_curr}"

        t0 = time.time()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url)
                latency = int((time.time() - t0) * 1000)
                resp.raise_for_status()
                data = resp.json()

                coin_data = data.get(coin_id)
                if not coin_data or vs_curr not in coin_data:
                    logger.debug(f"[CoinGecko] No price data for {coin_id} in {vs_curr}.")
                    return None

                price_raw = coin_data[vs_curr]
                price_str = format_crypto_price(price_raw)

                return CryptoPriceData(
                    symbol=norm_symbol,
                    vs_currency=vs_currency.upper(),
                    price=float(price_str),
                    price_str=price_str,
                    display_price=display_price_with_currency(price_str, vs_currency),
                    metadata=DataProvenance(
                        source=self.name,
                        market_type=self.market_type,
                        cached=False,
                        stale=False,
                        latency_ms=latency,
                    ),
                )
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.warning(f"[CoinGecko] Error fetching price for {coin_id}: {e}")
                raise

    async def fetch_market_data(self, symbol: str, vs_currency: str = "USD") -> Optional[CryptoMarketData]:
        if not self.rate_limiter.acquire():
            logger.warning("[CoinGecko] Throttled by local rate limiter.")
            raise httpx.HTTPStatusError(
                "Local rate limiter throttled request",
                request=None,  # type: ignore
                response=httpx.Response(status_code=429),
            )

        norm_symbol = normalize_symbol(symbol)
        coin_id = get_coingecko_id(norm_symbol)
        vs_curr = vs_currency.lower()

        url = f"{self.BASE_URL}/coins/markets?vs_currency={vs_curr}&ids={coin_id}"

        t0 = time.time()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url)
                latency = int((time.time() - t0) * 1000)
                resp.raise_for_status()
                data = resp.json()

                if not data or not isinstance(data, list):
                    return None

                m = data[0]
                curr_price_str = format_crypto_price(m.get("current_price", 0))
                high_str = format_crypto_price(m.get("high_24h", 0)) if m.get("high_24h") else None
                low_str = format_crypto_price(m.get("low_24h", 0)) if m.get("low_24h") else None
                change_pct = m.get("price_change_percentage_24h")
                vol = m.get("total_volume")

                return CryptoMarketData(
                    symbol=norm_symbol,
                    vs_currency=vs_currency.upper(),
                    price=float(curr_price_str),
                    price_str=curr_price_str,
                    display_price=display_price_with_currency(curr_price_str, vs_currency),
                    change_24h_percent=round(change_pct, 2) if change_pct is not None else None,
                    high_24h=float(high_str) if high_str else None,
                    high_24h_str=high_str,
                    low_24h=float(low_str) if low_str else None,
                    low_24h_str=low_str,
                    volume_24h=vol,
                    metadata=DataProvenance(
                        source=self.name,
                        market_type=self.market_type,
                        cached=False,
                        stale=False,
                        latency_ms=latency,
                    ),
                )
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.warning(f"[CoinGecko] Error fetching market data for {coin_id}: {e}")
                raise

    async def health_check(self) -> bool:
        url = f"{self.BASE_URL}/ping"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url)
                return resp.status_code == 200
            except Exception:
                return False
