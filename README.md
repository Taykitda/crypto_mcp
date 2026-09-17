# crypto-mcp

High-reliability, multi-provider Crypto price & market data MCP server for AI Agents.

## Overview
- Multi-provider architecture (Binance, OKX, CoinGecko)
- Automated failover & fallback
- Multi-tier caching (Fresh TTL + Stale Buffer)
- Financial-grade decimal precision (no scientific notation truncation)
- Read-only security sandbox
- Agent-optimized tokens & batch querying
