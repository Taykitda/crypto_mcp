"""Crypto price aggregator and orchestrator with tiered routing and automatic failover."""

import asyncio
from typing import Optional
from crypto_mcp.governance.cache import MemoryCache
from crypto_mcp.governance.circuit_breaker import CircuitBreaker
from crypto_mcp.models import (
    CryptoPriceData,
    CryptoMarketData,
    BatchPriceData,
    ConversionData,
    DataProvenance,
)
from crypto_mcp.providers.base import BasePriceProvider
from crypto_mcp.providers.binance import BinanceProvider
from crypto_mcp.providers.okx import OKXProvider
from crypto_mcp.providers.coingecko import CoinGeckoProvider
from crypto_mcp.utils.normalizer import (
    normalize_symbol,
    normalize_vs_currency,
    sanitize_and_validate_symbol,
)
from crypto_mcp.utils.precision import (
    calculate_conversion,
    format_crypto_price,
    to_decimal,
)
from crypto_mcp.utils.logging import logger


class CryptoPriceAggregator:
    """Orchestrates multi-provider fetching, automated failover, caching, and conversions."""

    def __init__(
        self,
        providers: Optional[list[BasePriceProvider]] = None,
        cache: Optional[MemoryCache] = None,
        fresh_price_ttl: float = 10.0,
        fresh_market_ttl: float = 60.0,
        stale_ttl: float = 300.0,
    ):
        self.cache = cache or MemoryCache(default_fresh_ttl=fresh_price_ttl, default_stale_ttl=stale_ttl)
        self.fresh_price_ttl = fresh_price_ttl
        self.fresh_market_ttl = fresh_market_ttl

        # Default provider chain: Binance -> OKX -> CoinGecko
        self.providers = providers or [
            BinanceProvider(),
            OKXProvider(),
            CoinGeckoProvider(),
        ]
        self.circuit_breakers = {p.name: CircuitBreaker(p.name) for p in self.providers}

    async def get_price(
        self,
        symbol: str,
        vs_currency: str = "USD",
        force_refresh: bool = False,
    ) -> CryptoPriceData:
        """Fetch spot price with caching and multi-provider failover."""
        norm_sym = normalize_symbol(symbol)
        norm_vs = normalize_vs_currency(vs_currency)
        cache_key = f"price:{norm_sym}:{norm_vs}"

        # 1. Check L1 fresh cache
        if not force_refresh:
            cached_data, is_stale, age = self.cache.get(cache_key, allow_stale=False)
            if cached_data is not None:
                logger.debug(f"Cache hit (fresh) for {cache_key}")
                cached_copy = cached_data.model_copy(deep=True)
                cached_copy.metadata.cached = True
                cached_copy.metadata.cache_age_seconds = age
                return cached_copy

        # 2. Iterate providers with failover
        errors = []
        for provider in self.providers:
            cb = self.circuit_breakers.get(provider.name)
            if cb and not cb.is_available():
                logger.warning(f"Skipping [{provider.name}] as circuit is open.")
                continue

            try:
                res = await provider.fetch_price(norm_sym, norm_vs)
                if res is not None:
                    if cb:
                        cb.record_success()
                    # Store in cache
                    self.cache.set(
                        cache_key,
                        res,
                        fresh_ttl=self.fresh_price_ttl,
                    )
                    return res
                else:
                    logger.debug(f"[{provider.name}] could not resolve symbol {norm_sym}.")
            except Exception as e:
                logger.warning(f"Provider [{provider.name}] failed for {norm_sym}: {e}")
                if cb:
                    cb.record_failure()
                errors.append(f"{provider.name}: {str(e)}")

        # 3. L2 Stale Cache fallback
        stale_data, is_stale, age = self.cache.get(cache_key, allow_stale=True)
        if stale_data is not None:
            logger.warning(f"All providers failed for {norm_sym}. Using stale fallback (age {age}s).")
            stale_copy = stale_data.model_copy(deep=True)
            stale_copy.metadata.cached = True
            stale_copy.metadata.stale = True
            stale_copy.metadata.cache_age_seconds = age
            stale_copy.metadata.warning = (
                f"External providers temporarily unavailable. Serving stale price from {age}s ago."
            )
            return stale_copy

        raise RuntimeError(
            f"Unable to retrieve price for {norm_sym}/{norm_vs} across all providers. Errors: {'; '.join(errors)}"
        )

    async def get_market_data(
        self,
        symbol: str,
        vs_currency: str = "USD",
        force_refresh: bool = False,
    ) -> CryptoMarketData:
        """Fetch 24h market stats with caching and failover."""
        norm_sym = normalize_symbol(symbol)
        norm_vs = normalize_vs_currency(vs_currency)
        cache_key = f"market:{norm_sym}:{norm_vs}"

        if not force_refresh:
            cached_data, is_stale, age = self.cache.get(cache_key, allow_stale=False)
            if cached_data is not None:
                cached_copy = cached_data.model_copy(deep=True)
                cached_copy.metadata.cached = True
                cached_copy.metadata.cache_age_seconds = age
                return cached_copy

        errors = []
        for provider in self.providers:
            cb = self.circuit_breakers.get(provider.name)
            if cb and not cb.is_available():
                continue

            try:
                res = await provider.fetch_market_data(norm_sym, norm_vs)
                if res is not None:
                    if cb:
                        cb.record_success()
                    self.cache.set(
                        cache_key,
                        res,
                        fresh_ttl=self.fresh_market_ttl,
                    )
                    return res
            except Exception as e:
                logger.warning(f"Provider [{provider.name}] failed market data for {norm_sym}: {e}")
                if cb:
                    cb.record_failure()
                errors.append(f"{provider.name}: {str(e)}")

        stale_data, is_stale, age = self.cache.get(cache_key, allow_stale=True)
        if stale_data is not None:
            stale_copy = stale_data.model_copy(deep=True)
            stale_copy.metadata.cached = True
            stale_copy.metadata.stale = True
            stale_copy.metadata.cache_age_seconds = age
            stale_copy.metadata.warning = (
                f"External providers unavailable. Serving stale market data from {age}s ago."
            )
            return stale_copy

        raise RuntimeError(
            f"Unable to retrieve market data for {norm_sym}/{norm_vs}. Errors: {'; '.join(errors)}"
        )

    async def batch_prices(
        self,
        symbols: list[str],
        vs_currency: str = "USD",
    ) -> BatchPriceData:
        """Fetch multiple crypto prices concurrently with a cap of 20 symbols."""
        if not symbols:
            raise ValueError("Symbols list cannot be empty.")
        if len(symbols) > 20:
            raise ValueError("Maximum 20 symbols allowed per batch query to prevent context overflow.")

        tasks = [self.get_price(sym, vs_currency=vs_currency) for sym in symbols]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

        success_map: dict[str, CryptoPriceData] = {}
        error_map: dict[str, str] = {}

        for sym, res in zip(symbols, results_raw):
            clean_sym = normalize_symbol(sym)
            if isinstance(res, Exception):
                error_map[clean_sym] = str(res)
            elif isinstance(res, CryptoPriceData):
                success_map[clean_sym] = res

        return BatchPriceData(
            vs_currency=normalize_vs_currency(vs_currency),
            results=success_map,
            errors=error_map,
            count=len(success_map),
        )

    async def convert(
        self,
        amount: float,
        from_coin: str,
        to_coin: str,
    ) -> ConversionData:
        """Convert asset amount from from_coin to to_coin using high-precision Decimal."""
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")

        from_sym = normalize_symbol(from_coin)
        to_sym = normalize_symbol(to_coin)

        # Get USD price for from_coin
        if from_sym in {"USD", "USDT", "USDC"}:
            from_usd = 1.0
            from_src = "fiat_anchor"
        else:
            p1 = await self.get_price(from_sym, "USD")
            from_usd = p1.price
            from_src = p1.metadata.source

        # Get USD price for to_coin
        if to_sym in {"USD", "USDT", "USDC"}:
            to_usd = 1.0
            to_src = "fiat_anchor"
        else:
            p2 = await self.get_price(to_sym, "USD")
            to_usd = p2.price
            to_src = p2.metadata.source

        converted_dec, converted_str = calculate_conversion(
            amount=amount,
            from_price_usd=from_usd,
            to_price_usd=to_usd,
        )

        rate_dec, rate_str = calculate_conversion(
            amount=1,
            from_price_usd=from_usd,
            to_price_usd=to_usd,
        )

        return ConversionData(
            from_coin=from_sym,
            to_coin=to_sym,
            amount=float(amount),
            converted_amount=float(converted_dec),
            converted_str=converted_str,
            rate=f"1 {from_sym} = {rate_str} {to_sym}",
            metadata=DataProvenance(
                source=f"{from_src}->{to_src}",
                market_type="derived_conversion",
                cached=False,
                stale=False,
            ),
        )
