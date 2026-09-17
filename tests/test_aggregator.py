"""Tests for CryptoPriceAggregator failover, caching, and conversions."""

import pytest
from unittest.mock import AsyncMock
import httpx
from crypto_mcp.aggregator import CryptoPriceAggregator
from crypto_mcp.governance.cache import MemoryCache
from crypto_mcp.models import CryptoPriceData, DataProvenance
from crypto_mcp.providers.base import BasePriceProvider


class MockProvider(BasePriceProvider):
    def __init__(self, name: str, should_fail: bool = False, return_price: float = 100.0):
        self.name = name
        self.should_fail = should_fail
        self.return_price = return_price
        self.call_count = 0

    async def fetch_price(self, symbol: str, vs_currency: str = "USD"):
        self.call_count += 1
        if self.should_fail:
            raise httpx.ConnectError("Connection timed out")
        return CryptoPriceData(
            symbol=symbol,
            vs_currency=vs_currency,
            price=self.return_price,
            price_str=str(self.return_price),
            display_price=f"${self.return_price}",
            metadata=DataProvenance(source=self.name),
        )

    async def fetch_market_data(self, symbol: str, vs_currency: str = "USD"):
        return None

    async def health_check(self) -> bool:
        return not self.should_fail


@pytest.mark.asyncio
async def test_aggregator_primary_provider_success():
    p1 = MockProvider("p1", should_fail=False, return_price=60000.0)
    p2 = MockProvider("p2", should_fail=False, return_price=60050.0)
    agg = CryptoPriceAggregator(providers=[p1, p2])

    res = await agg.get_price("BTC", "USD")
    assert res.price == 60000.0
    assert res.metadata.source == "p1"
    assert p1.call_count == 1
    assert p2.call_count == 0


@pytest.mark.asyncio
async def test_aggregator_failover_to_secondary():
    """Verify that when primary provider fails, aggregator seamlessly falls back to secondary."""
    p1 = MockProvider("p1", should_fail=True)
    p2 = MockProvider("p2", should_fail=False, return_price=61000.0)
    agg = CryptoPriceAggregator(providers=[p1, p2])

    res = await agg.get_price("BTC", "USD")
    assert res.price == 61000.0
    assert res.metadata.source == "p2"
    assert p1.call_count == 1
    assert p2.call_count == 1


@pytest.mark.asyncio
async def test_aggregator_cache_hit():
    p1 = MockProvider("p1", return_price=60000.0)
    agg = CryptoPriceAggregator(providers=[p1], fresh_price_ttl=10.0)

    # First call - fetches from provider
    res1 = await agg.get_price("BTC", "USD")
    assert res1.metadata.cached is False
    assert p1.call_count == 1

    # Second call - should hit cache
    res2 = await agg.get_price("BTC", "USD")
    assert res2.metadata.cached is True
    assert p1.call_count == 1  # Not called again!


@pytest.mark.asyncio
async def test_aggregator_stale_fallback_when_all_fail():
    cache = MemoryCache(default_fresh_ttl=0.01, default_stale_ttl=10.0)
    p1 = MockProvider("p1", should_fail=False, return_price=50000.0)
    agg = CryptoPriceAggregator(providers=[p1], cache=cache, fresh_price_ttl=0.01, stale_ttl=10.0)

    # Prime cache
    await agg.get_price("BTC", "USD")

    # Now simulate provider failing and fresh TTL expiring
    p1.should_fail = True
    import asyncio
    await asyncio.sleep(0.02)  # expire fresh TTL

    # Calling get_price should return stale cache instead of crashing
    res_stale = await agg.get_price("BTC", "USD")
    assert res_stale.metadata.stale is True
    assert res_stale.metadata.cached is True
    assert "temporarily unavailable" in (res_stale.metadata.warning or "")


@pytest.mark.asyncio
async def test_aggregator_batch_prices():
    p1 = MockProvider("p1", return_price=50000.0)
    agg = CryptoPriceAggregator(providers=[p1])

    batch_res = await agg.batch_prices(["BTC", "ETH", "SOL"], "USD")
    assert batch_res.count == 3
    assert "BTC" in batch_res.results
    assert "ETH" in batch_res.results
    assert "SOL" in batch_res.results


@pytest.mark.asyncio
async def test_aggregator_batch_prices_limit():
    agg = CryptoPriceAggregator(providers=[MockProvider("p1")])
    too_many = [f"COIN{i}" for i in range(25)]
    with pytest.raises(ValueError, match="Maximum 20 symbols"):
        await agg.batch_prices(too_many)


@pytest.mark.asyncio
async def test_aggregator_convert():
    class DummyProvider(BasePriceProvider):
        name = "dummy"
        async def fetch_price(self, symbol: str, vs_currency: str = "USD"):
            prices = {"BTC": 50000.0, "ETH": 2500.0}
            p = prices.get(symbol, 1.0)
            return CryptoPriceData(
                symbol=symbol,
                vs_currency="USD",
                price=p,
                price_str=str(p),
                display_price=f"${p}",
                metadata=DataProvenance(source="dummy"),
            )
        async def fetch_market_data(self, symbol: str, vs_currency: str = "USD"):
            return None
        async def health_check(self) -> bool:
            return True

    agg = CryptoPriceAggregator(providers=[DummyProvider()])
    # Convert 2 BTC to ETH: 2 * 50000 / 2500 = 40 ETH
    conv = await agg.convert(amount=2, from_coin="BTC", to_coin="ETH")
    assert conv.converted_amount == 40.0
    assert conv.converted_str == "40.0"
    assert "1 BTC = 20.0 ETH" in conv.rate
