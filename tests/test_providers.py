"""Unit tests for Binance, OKX, and CoinGecko provider adapters with mock HTTP."""

import pytest
import respx
import httpx
from crypto_mcp.providers.binance import BinanceProvider
from crypto_mcp.providers.okx import OKXProvider
from crypto_mcp.providers.coingecko import CoinGeckoProvider


@pytest.mark.asyncio
async def test_binance_fetch_price_success():
    provider = BinanceProvider()
    with respx.mock(base_url="https://api.binance.com/api/v3") as respx_mock:
        respx_mock.get("/ticker/price?symbol=BTCUSDT").respond(
            200, json={"symbol": "BTCUSDT", "price": "68450.25"}
        )
        res = await provider.fetch_price("BTC", "USD")
        assert res is not None
        assert res.symbol == "BTC"
        assert res.price == 68450.25
        assert res.price_str == "68450.25"
        assert res.metadata.source == "binance"
        assert res.metadata.market_type == "cex_orderbook"


@pytest.mark.asyncio
async def test_binance_fetch_market_data_success():
    provider = BinanceProvider()
    with respx.mock(base_url="https://api.binance.com/api/v3") as respx_mock:
        respx_mock.get("/ticker/24hr?symbol=BTCUSDT").respond(
            200,
            json={
                "symbol": "BTCUSDT",
                "priceChangePercent": "3.50",
                "lastPrice": "68500.00",
                "highPrice": "69000.00",
                "lowPrice": "67000.00",
                "quoteVolume": "1500000000.0",
            },
        )
        res = await provider.fetch_market_data("BTC", "USD")
        assert res is not None
        assert res.price == 68500.0
        assert res.change_24h_percent == 3.5
        assert res.high_24h == 69000.0
        assert res.low_24h == 67000.0


@pytest.mark.asyncio
async def test_okx_fetch_price_success():
    provider = OKXProvider()
    with respx.mock(base_url="https://www.okx.com/api/v5/market") as respx_mock:
        respx_mock.get("/ticker?instId=BTC-USDT").respond(
            200,
            json={
                "code": "0",
                "data": [
                    {
                        "instId": "BTC-USDT",
                        "last": "68450.5",
                        "high24h": "69000.0",
                        "low24h": "67000.0",
                        "open24h": "67000.0",
                        "volCcy24h": "1200000000.0",
                    }
                ],
            },
        )
        res = await provider.fetch_price("BTC", "USD")
        assert res is not None
        assert res.symbol == "BTC"
        assert res.price == 68450.5
        assert res.metadata.source == "okx"


@pytest.mark.asyncio
async def test_coingecko_fetch_price_micro_token():
    provider = CoinGeckoProvider()
    with respx.mock(base_url="https://api.coingecko.com/api/v3") as respx_mock:
        respx_mock.get("/simple/price?ids=pepe&vs_currencies=usd").respond(
            200,
            json={"pepe": {"usd": 0.0000084321}},
        )
        res = await provider.fetch_price("PEPE", "USD")
        assert res is not None
        assert res.symbol == "PEPE"
        assert res.price_str == "0.0000084321"
        assert "e" not in res.price_str.lower()
        assert res.metadata.source == "coingecko"
        assert res.metadata.market_type == "aggregated_dex_cex"


@pytest.mark.asyncio
async def test_coingecko_rate_limiter_throttles():
    provider = CoinGeckoProvider(max_requests_per_minute=1)
    with respx.mock(base_url="https://api.coingecko.com/api/v3") as respx_mock:
        respx_mock.get("/simple/price?ids=bitcoin&vs_currencies=usd").respond(
            200, json={"bitcoin": {"usd": 68000.0}}
        )
        # 1st request succeeds
        r1 = await provider.fetch_price("BTC", "USD")
        assert r1 is not None

        # 2nd request should be throttled by local rate limiter with 429
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await provider.fetch_price("BTC", "USD")
        assert exc_info.value.response.status_code == 429
