"""End-to-end tests for the MCP Server tools."""

import json
import pytest
from crypto_mcp.aggregator import CryptoPriceAggregator
from crypto_mcp.models import CryptoPriceData, CryptoMarketData, DataProvenance
from crypto_mcp.providers.base import BasePriceProvider
from crypto_mcp.server import create_server


class MockServerProvider(BasePriceProvider):
    name = "mock"

    async def fetch_price(self, symbol: str, vs_currency: str = "USD"):
        prices = {"BTC": 65000.0, "ETH": 3500.0, "PEPE": 0.0000084321}
        if symbol in prices:
            p = prices[symbol]
            return CryptoPriceData(
                symbol=symbol,
                vs_currency=vs_currency,
                price=p,
                price_str=str(p),
                display_price=f"${p}",
                metadata=DataProvenance(source="mock"),
            )
        return None

    async def fetch_market_data(self, symbol: str, vs_currency: str = "USD"):
        if symbol == "BTC":
            return CryptoMarketData(
                symbol=symbol,
                vs_currency=vs_currency,
                price=65000.0,
                price_str="65000.0",
                display_price="$65,000.00",
                change_24h_percent=2.5,
                high_24h=66000.0,
                high_24h_str="66000.0",
                low_24h=64000.0,
                low_24h_str="64000.0",
                volume_24h=1000000.0,
                metadata=DataProvenance(source="mock"),
            )
        return None

    async def health_check(self) -> bool:
        return True


@pytest.fixture
def test_server():
    agg = CryptoPriceAggregator(providers=[MockServerProvider()])
    return create_server(aggregator=agg)


@pytest.mark.asyncio
async def test_server_list_tools(test_server):
    tools = await test_server.list_tools()
    tool_names = [t.name for t in tools]
    assert "get_crypto_price" in tool_names
    assert "get_crypto_market_data" in tool_names
    assert "batch_crypto_prices" in tool_names
    assert "convert_crypto" in tool_names


@pytest.mark.asyncio
async def test_call_get_crypto_price_success(test_server):
    res = await test_server.call_tool("get_crypto_price", {"symbol": "bitcoin"})
    # Result content in FastMCP 2.x
    text = res.content[0].text
    payload = json.loads(text)

    assert payload["success"] is True
    assert payload["data"]["symbol"] == "BTC"
    assert payload["data"]["price"] == 65000.0
    assert payload["data"]["metadata"]["source"] == "mock"


@pytest.mark.asyncio
async def test_call_get_crypto_price_invalid_symbol(test_server):
    """Verify malicious input receives structured Agent-friendly failure instead of crash."""
    res = await test_server.call_tool("get_crypto_price", {"symbol": "btc; DROP TABLE"})
    text = res.content[0].text
    payload = json.loads(text)

    assert payload["success"] is False
    assert "Invalid symbol" in payload["error"]
    assert len(payload["suggestions"]) > 0


@pytest.mark.asyncio
async def test_call_get_crypto_market_data(test_server):
    res = await test_server.call_tool("get_crypto_market_data", {"symbol": "BTC"})
    text = res.content[0].text
    payload = json.loads(text)

    assert payload["success"] is True
    assert payload["data"]["symbol"] == "BTC"
    assert payload["data"]["change_24h_percent"] == 2.5
    assert payload["data"]["high_24h"] == 66000.0


@pytest.mark.asyncio
async def test_call_batch_crypto_prices(test_server):
    res = await test_server.call_tool(
        "batch_crypto_prices",
        {"symbols": ["BTC", "ETH", "UNKNOWN"]},
    )
    text = res.content[0].text
    payload = json.loads(text)

    assert payload["success"] is True
    data = payload["data"]
    assert data["count"] == 2
    assert "BTC" in data["results"]
    assert "ETH" in data["results"]
    assert "UNKNOWN" in data["errors"]


@pytest.mark.asyncio
async def test_call_convert_crypto(test_server):
    # Convert 1 BTC ($65000) to ETH ($3500): 65000 / 3500 = 18.5714...
    res = await test_server.call_tool(
        "convert_crypto",
        {"amount": 1.0, "from_coin": "BTC", "to_coin": "ETH"},
    )
    text = res.content[0].text
    payload = json.loads(text)

    assert payload["success"] is True
    data = payload["data"]
    assert data["from_coin"] == "BTC"
    assert data["to_coin"] == "ETH"
    assert data["amount"] == 1.0
    assert "ETH" in data["rate"]
