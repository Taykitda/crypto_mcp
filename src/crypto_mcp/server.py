"""MCP Server definition and tool registrations for Crypto price queries."""

import json
from typing import Optional
from mcp.server.mcpserver import MCPServer
from crypto_mcp.aggregator import CryptoPriceAggregator
from crypto_mcp.models import (
    BaseResponse,
    CryptoPriceData,
    CryptoMarketData,
    BatchPriceData,
    ConversionData,
)
from crypto_mcp.utils.normalizer import (
    sanitize_and_validate_symbol,
    normalize_symbol,
    ALIAS_MAP,
)
from crypto_mcp.utils.logging import logger, setup_logging


def create_server(aggregator: Optional[CryptoPriceAggregator] = None) -> MCPServer:
    """Create and configure the Crypto MCP Server."""
    agg = aggregator or CryptoPriceAggregator()
    server = MCPServer(
        name="crypto-mcp",
        instructions=(
            "Crypto Market Data MCP Server. Provides real-time spot prices, 24h market statistics, "
            "batch price queries, and asset conversions with multi-provider failover (Binance, OKX, CoinGecko)."
        ),
    )

    @server.tool()
    async def get_crypto_price(
        symbol: str,
        vs_currency: str = "USD",
        force_refresh: bool = False,
    ) -> str:
        """Get the real-time spot price of a cryptocurrency.

        Args:
            symbol: Crypto asset ticker or name (e.g. 'BTC', 'bitcoin', 'ETH', 'SOL', 'PEPE').
            vs_currency: Quote currency for price quotation (default: 'USD', supports 'CNY', 'EUR', 'USDT', etc.).
            force_refresh: If True, bypasses local TTL cache to pull fresh upstream data.

        Returns:
            JSON string containing BaseResponse with price, exact decimal string, and metadata.
        """
        try:
            sanitize_and_validate_symbol(symbol)
            data = await agg.get_price(symbol, vs_currency=vs_currency, force_refresh=force_refresh)
            resp = BaseResponse[CryptoPriceData](success=True, data=data)
        except ValueError as ve:
            resp = BaseResponse[CryptoPriceData](
                success=False,
                error=str(ve),
                suggestions=["Check symbol spelling. Supported examples: BTC, ETH, SOL, BNB, DOGE, PEPE."],
            )
        except Exception as e:
            logger.error(f"Error in get_crypto_price({symbol}): {e}")
            resp = BaseResponse[CryptoPriceData](
                success=False,
                error=f"Failed to fetch price for {symbol}: {str(e)}",
                suggestions=["Retry in a few moments or verify if the coin is listed on major exchanges."],
            )
        return resp.model_dump_json()

    @server.tool()
    async def get_crypto_market_data(
        symbol: str,
        vs_currency: str = "USD",
        force_refresh: bool = False,
    ) -> str:
        """Get 24-hour market statistics for a cryptocurrency (price, 24h change %, high, low, volume).

        Args:
            symbol: Crypto asset ticker (e.g. 'BTC', 'ETH', 'SOL').
            vs_currency: Quote currency (default: 'USD').
            force_refresh: If True, bypasses cache.

        Returns:
            JSON string containing BaseResponse with 24h high/low, volume, and percentage change.
        """
        try:
            sanitize_and_validate_symbol(symbol)
            data = await agg.get_market_data(symbol, vs_currency=vs_currency, force_refresh=force_refresh)
            resp = BaseResponse[CryptoMarketData](success=True, data=data)
        except ValueError as ve:
            resp = BaseResponse[CryptoMarketData](success=False, error=str(ve))
        except Exception as e:
            logger.error(f"Error in get_crypto_market_data({symbol}): {e}")
            resp = BaseResponse[CryptoMarketData](
                success=False,
                error=f"Failed to fetch market data for {symbol}: {str(e)}",
            )
        return resp.model_dump_json()

    @server.tool()
    async def batch_crypto_prices(
        symbols: list[str],
        vs_currency: str = "USD",
    ) -> str:
        """Fetch prices for multiple cryptocurrencies concurrently in a single request.

        Saves LLM context and round-trips compared to calling get_crypto_price individually.

        Args:
            symbols: List of crypto tickers (e.g. ['BTC', 'ETH', 'SOL', 'BNB'], max 20).
            vs_currency: Quote currency for quotation (default: 'USD').

        Returns:
            JSON string containing BaseResponse with map of symbol -> price details and failed symbols.
        """
        try:
            data = await agg.batch_prices(symbols, vs_currency=vs_currency)
            resp = BaseResponse[BatchPriceData](success=True, data=data)
        except ValueError as ve:
            resp = BaseResponse[BatchPriceData](success=False, error=str(ve))
        except Exception as e:
            logger.error(f"Error in batch_crypto_prices: {e}")
            resp = BaseResponse[BatchPriceData](success=False, error=str(e))
        return resp.model_dump_json()

    @server.tool()
    async def convert_crypto(
        amount: float,
        from_coin: str,
        to_coin: str,
    ) -> str:
        """Accurately convert an amount of one crypto/fiat asset into another using exact Decimal math.

        Eliminates LLM floating-point calculation errors.

        Args:
            amount: Quantity of the source coin to convert (e.g. 1.5).
            from_coin: Source asset symbol (e.g. 'BTC', 'ETH', 'USD').
            to_coin: Target asset symbol (e.g. 'ETH', 'SOL', 'USD').

        Returns:
            JSON string containing converted amount, exact decimal string, and exchange rate ratio.
        """
        try:
            sanitize_and_validate_symbol(from_coin)
            sanitize_and_validate_symbol(to_coin)
            data = await agg.convert(amount=amount, from_coin=from_coin, to_coin=to_coin)
            resp = BaseResponse[ConversionData](success=True, data=data)
        except ValueError as ve:
            resp = BaseResponse[ConversionData](success=False, error=str(ve))
        except Exception as e:
            logger.error(f"Error in convert_crypto({amount} {from_coin} -> {to_coin}): {e}")
            resp = BaseResponse[ConversionData](success=False, error=str(e))
        return resp.model_dump_json()

    return server


def main() -> None:
    """Entry point to run the server over stdio transport."""
    setup_logging()
    logger.info("Starting Crypto MCP Server on stdio transport...")
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
