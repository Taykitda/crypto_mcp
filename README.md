# crypto-mcp

An industrial-grade, high-reliability **Crypto Price & Market Data MCP (Model Context Protocol) Server** tailored for AI Agents.

---

## 🌟 Key Features

1. **Multi-Provider Architecture with Automated Failover**:
   - Primary: **Binance** (Zero-auth, millisecond-level spot orderbook ticker).
   - Hot Standby: **OKX** (Zero-auth CEX public ticker backup).
   - Long-Tail & Fiat Anchor: **CoinGecko** (15,000+ tokens, Memes, and multi-fiat quotes).
   - Seamless failover: if primary times out or hits 429 rate limits, it transparently falls back to secondary sources.

2. **Dual-Tier Cache & Stale Recovery Buffer**:
   - **L1 Fresh Cache** (10s for spot prices, 60s for market stats): Eliminates redundant upstream queries during Agent multi-step reasoning.
   - **L2 Stale Buffer** (up to 5 minutes): When all external networks are partitioned or down, gracefully returns recent valid snapshot with `stale: true` and warning metadata, preventing Agent crash.

3. **Financial Precision & Decimal Math**:
   - **Zero Scientific Notation Leakage**: Formats micro-priced tokens (e.g. PEPE `$0.0000084321`) into exact decimal strings to prevent LLM order-of-magnitude hallucinations (`8.43e-6`).
   - Exact conversion using Python `Decimal` arithmetic.

4. **Security Sandbox & Input Sanitization**:
   - Strict alphanumeric whitelist filtering on token symbols and quotes (prevents SSRF and injection).
   - Strict read-only contract: No trading or wallet operations.

5. **Token Economics & Minimal Context**:
   - Strips massive upstream orderbook dumps down to concise, structured JSON envelopes.
   - Includes `batch_crypto_prices` to query up to 20 tokens in a single round-trip, saving 60%+ LLM context and latency.

6. **Observability & Protocol Purity**:
   - Strict stderr logging: Zero `stdout` pollution, guaranteeing flawless JSON-RPC communication across all MCP clients.

---

## 🛠️ MCP Tools

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `get_crypto_price` | `symbol: str`, `vs_currency: str = "USD"`, `force_refresh: bool = False` | Real-time spot price with exact string and provenance metadata. |
| `get_crypto_market_data` | `symbol: str`, `vs_currency: str = "USD"`, `force_refresh: bool = False` | 24-hour ticker statistics (price, 24h change %, high, low, volume). |
| `batch_crypto_prices` | `symbols: list[str]`, `vs_currency: str = "USD"` | Concurrently fetch prices for up to 20 tokens in a single tool call. |
| `convert_crypto` | `amount: float`, `from_coin: str`, `to_coin: str` | Accurate cross-crypto or crypto-fiat conversions via Decimal math. |

---

## 🚀 Quickstart & Client Configuration

### Running via `uvx` (No installation needed)
```bash
uvx --from /Users/alvin/Documents/Code/crypto_mcp crypto-mcp
```

### Claude Desktop Configuration
Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "crypto-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/alvin/Documents/Code/crypto_mcp",
        "run",
        "crypto-mcp"
      ]
    }
  }
}
```

### Cursor / Antigravity IDE Configuration
Add an MCP server with `stdio` command:
```bash
uv --directory /Users/alvin/Documents/Code/crypto_mcp run crypto-mcp
```

---

## 🧪 Running Tests

```bash
uv run pytest
```
All tests verify precision, symbol normalization, provider adapters, failover orchestration, and MCP tool invocations.
