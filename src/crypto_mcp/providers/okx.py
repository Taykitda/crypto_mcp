"""OKX Public API provider adapter."""

import time
from typing import Optional
import httpx
from crypto_mcp.models import CryptoPriceData, CryptoMarketData, DataProvenance
from crypto_mcp.providers.base import BasePriceProvider
from crypto_mcp.utils.normalizer import normalize_symbol, get_okx_inst_id
from crypto_mcp.utils.precision import format_crypto_price, display_price_with_currency
from crypto_mcp.utils.logging import logger


class OKXProvider(BasePriceProvider):
    name = "okx"
    market_type = "cex_orderbook"
    BASE_URL = "https://www.okx.com/api/v5/market"

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout

    async def fetch_price(self, symbol: str, vs_currency: str = "USD") -> Optional[CryptoPriceData]:
        norm_symbol = normalize_symbol(symbol)
        inst_id = get_okx_inst_id(norm_symbol, vs_currency)
        url = f"{self.BASE_URL}/ticker?instId={inst_id}"

        t0 = time.time()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url)
                latency = int((time.time() - t0) * 1000)
                resp.raise_for_status()
                data = resp.json()

                tickers = data.get("data", [])
                if not tickers:
                    logger.debug(f"[OKX] No ticker data returned for {inst_id}.")
                    return None

                ticker = tickers[0]
                last_price_raw = ticker.get("last")
                if not last_price_raw:
                    return None

                price_str = format_crypto_price(last_price_raw)
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
                logger.warning(f"[OKX] Error fetching price for {inst_id}: {e}")
                raise

    async def fetch_market_data(self, symbol: str, vs_currency: str = "USD") -> Optional[CryptoMarketData]:
        norm_symbol = normalize_symbol(symbol)
        inst_id = get_okx_inst_id(norm_symbol, vs_currency)
        url = f"{self.BASE_URL}/ticker?instId={inst_id}"

        t0 = time.time()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url)
                latency = int((time.time() - t0) * 1000)
                resp.raise_for_status()
                data = resp.json()

                tickers = data.get("data", [])
                if not tickers:
                    return None

                t = tickers[0]
                last_str = format_crypto_price(t.get("last", "0"))
                high_str = format_crypto_price(t.get("high24h", "0"))
                low_str = format_crypto_price(t.get("low24h", "0"))
                open_str = format_crypto_price(t.get("open24h", "0"))
                vol_ccy = float(t.get("volCcy24h", 0.0))

                last_f = float(last_str)
                open_f = float(open_str)
                change_pct = ((last_f - open_f) / open_f * 100) if open_f > 0 else 0.0

                return CryptoMarketData(
                    symbol=norm_symbol,
                    vs_currency=vs_currency.upper(),
                    price=last_f,
                    price_str=last_str,
                    display_price=display_price_with_currency(last_str, vs_currency),
                    change_24h_percent=round(change_pct, 2),
                    high_24h=float(high_str),
                    high_24h_str=high_str,
                    low_24h=float(low_str),
                    low_24h_str=low_str,
                    volume_24h=vol_ccy,
                    metadata=DataProvenance(
                        source=self.name,
                        market_type=self.market_type,
                        cached=False,
                        stale=False,
                        latency_ms=latency,
                    ),
                )
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.warning(f"[OKX] Error fetching market data for {inst_id}: {e}")
                raise

    async def health_check(self) -> bool:
        url = "https://www.okx.com/api/v5/public/time"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url)
                return resp.status_code == 200
            except Exception:
                return False
