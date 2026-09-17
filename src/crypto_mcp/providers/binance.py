"""Binance Public API provider adapter."""

import time
from typing import Optional
import httpx
from crypto_mcp.models import CryptoPriceData, CryptoMarketData, DataProvenance
from crypto_mcp.providers.base import BasePriceProvider
from crypto_mcp.utils.normalizer import normalize_symbol, get_binance_pair
from crypto_mcp.utils.precision import format_crypto_price, display_price_with_currency
from crypto_mcp.utils.logging import logger


class BinanceProvider(BasePriceProvider):
    name = "binance"
    market_type = "cex_orderbook"
    BASE_URL = "https://api.binance.com/api/v3"

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout

    async def fetch_price(self, symbol: str, vs_currency: str = "USD") -> Optional[CryptoPriceData]:
        norm_symbol = normalize_symbol(symbol)
        pair = get_binance_pair(norm_symbol, vs_currency)
        url = f"{self.BASE_URL}/ticker/price?symbol={pair}"

        t0 = time.time()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url)
                latency = int((time.time() - t0) * 1000)
                if resp.status_code == 400:
                    # Symbol not found / invalid pair
                    logger.debug(f"[Binance] Pair {pair} not found (400).")
                    return None
                resp.raise_for_status()
                data = resp.json()

                price_raw = data.get("price")
                if price_raw is None:
                    return None

                price_str = format_crypto_price(price_raw)
                price_float = float(price_str)

                return CryptoPriceData(
                    symbol=norm_symbol,
                    vs_currency=vs_currency.upper(),
                    price=price_float,
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
                logger.warning(f"[Binance] Error fetching price for {pair}: {e}")
                raise

    async def fetch_market_data(self, symbol: str, vs_currency: str = "USD") -> Optional[CryptoMarketData]:
        norm_symbol = normalize_symbol(symbol)
        pair = get_binance_pair(norm_symbol, vs_currency)
        url = f"{self.BASE_URL}/ticker/24hr?symbol={pair}"

        t0 = time.time()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url)
                latency = int((time.time() - t0) * 1000)
                if resp.status_code == 400:
                    return None
                resp.raise_for_status()
                data = resp.json()

                last_price_str = format_crypto_price(data["lastPrice"])
                high_str = format_crypto_price(data["highPrice"])
                low_str = format_crypto_price(data["lowPrice"])

                change_pct = float(data.get("priceChangePercent", 0.0))
                quote_vol = float(data.get("quoteVolume", 0.0))

                return CryptoMarketData(
                    symbol=norm_symbol,
                    vs_currency=vs_currency.upper(),
                    price=float(last_price_str),
                    price_str=last_price_str,
                    display_price=display_price_with_currency(last_price_str, vs_currency),
                    change_24h_percent=change_pct,
                    high_24h=float(high_str),
                    high_24h_str=high_str,
                    low_24h=float(low_str),
                    low_24h_str=low_str,
                    volume_24h=quote_vol,
                    metadata=DataProvenance(
                        source=self.name,
                        market_type=self.market_type,
                        cached=False,
                        stale=False,
                        latency_ms=latency,
                    ),
                )
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.warning(f"[Binance] Error fetching market data for {pair}: {e}")
                raise

    async def health_check(self) -> bool:
        url = f"{self.BASE_URL}/ping"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url)
                return resp.status_code == 200
            except Exception:
                return False
