# injective

Blockchain trading on Injective DEX — spot and perpetual markets, orderbooks, balances, positions, and subaccount management.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `injective.search_markets` | Search spot or derivative markets by ticker | guest |
| `injective.get_price` | Best bid, ask, and last traded price | guest |
| `injective.get_orderbook` | Bids and asks with depth limit | guest |
| `injective.get_balances` | Token balances for a subaccount | owner |
| `injective.get_portfolio` | Aggregated portfolio overview | owner |
| `injective.get_subaccounts` | List all subaccounts with balances | owner |
| `injective.subaccount_transfer` | Move funds (deposit/withdraw/transfer) | owner |
| `injective.place_spot_order` | Place spot limit or market order | owner |
| `injective.cancel_spot_order` | Cancel spot order by hash | owner |
| `injective.get_spot_orders` | List open spot orders | owner |
| `injective.place_derivative_order` | Place perp order with auto-calculated margin | owner |
| `injective.cancel_derivative_order` | Cancel perp order by hash | owner |
| `injective.get_derivative_orders` | List open perp orders | owner |
| `injective.get_positions` | Open positions with entry/mark price, PnL | owner |
| `injective.close_position` | Close position via reduce-only market order | owner |

## Tool Details

### Market Data (guest)

**`injective.search_markets`**
- **query** (string, required) — ticker or token name (e.g. "INJ", "BTC", "ETH/USDT")
- **market_type** (string, required) — `spot` or `derivative`
- Returns hex `market_id` needed by all other tools

**`injective.get_price`**
- **market_id** (string, required) — hex ID from `search_markets`

**`injective.get_orderbook`**
- **market_id** (string, required)
- **depth** (integer, optional) — price levels (default 10)

### Account (owner)

**`injective.get_balances`**
- **subaccount_index** (integer, optional) — default 0 (primary)

**`injective.get_portfolio`**
- No parameters — aggregated bank + subaccount + positions overview

**`injective.get_subaccounts`**
- No parameters

**`injective.subaccount_transfer`**
- **amount** (number, required)
- **denom** (string, required) — e.g. "inj", "peggy0x..." for USDT
- **action** (string, required) — `deposit`, `withdraw`, `transfer`
- **source_index** (integer, optional) — default 0
- **dest_index** (integer, optional) — default 1 (only for `transfer`)

### Spot Trading (owner)

**`injective.place_spot_order`**
- **market_id**, **side** (`buy`/`sell`), **price**, **quantity** (required)
- **order_type** (optional) — `limit` (default) or `market`

**`injective.cancel_spot_order`**
- **market_id**, **order_hash** (required)

**`injective.get_spot_orders`**
- **market_id** (optional), **subaccount_index** (optional, default 0)

### Derivative / Perpetual Trading (owner)

**`injective.place_derivative_order`**
- **market_id**, **side**, **price**, **quantity** (required)
- **leverage** (number, optional) — default 1
- **order_type** (optional) — `limit` (default) or `market`
- **reduce_only** (boolean, optional) — only reduce existing position (default false)
- Margin auto-calculated: price * quantity / leverage

**`injective.cancel_derivative_order`**
- **market_id**, **order_hash** (required)
- **is_buy** (boolean, required) — from `get_derivative_orders`
- **is_market_order** (boolean, optional)
- **is_conditional** (boolean, optional)

**`injective.get_derivative_orders`**
- **market_id** (optional), **subaccount_index** (optional, default 0)

**`injective.get_positions`**
- **market_id** (optional), **subaccount_index** (optional, default 0)
- Returns entry price, mark price, quantity, margin, unrealized PnL

**`injective.close_position`**
- **market_id** (string, required)
- **quantity** (number, optional) — default: full position
- **price** (number, optional) — default: best bid/ask with 5% slippage
- Auto-detects position side, places reduce-only market order in opposite direction

## Implementation Notes

- Market IDs are hex identifiers returned by `search_markets` — required by all trading tools
- Subaccount index 0 is the primary trading account
- Margin is auto-calculated from price, quantity, and leverage
- Reduce-only orders prevent accidental position growth when closing
- Owner-only permission for all trading operations; market data is guest-accessible

## Key Files

- `agent/modules/injective/manifest.py`
- `agent/modules/injective/tools.py`
- `agent/modules/injective/main.py`
