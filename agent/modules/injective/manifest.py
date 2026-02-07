"""Injective module manifest — tool definitions for spot and derivative trading."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="injective",
    description="Trade on Injective DEX — spot and perpetual markets, orderbooks, balances, positions, and subaccount management.",
    tools=[
        # ── Market Data (read-only) ──────────────────────────────────────
        ToolDefinition(
            name="injective.search_markets",
            description=(
                "Search for spot or derivative markets by ticker or name. "
                "Returns market IDs needed by all other trading tools. "
                "Example: query='INJ' market_type='spot' → INJ/USDT market with its hex ID."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Ticker or token name to search for (e.g. 'INJ', 'BTC', 'ETH/USDT')",
                ),
                ToolParameter(
                    name="market_type",
                    type="string",
                    description="Type of market to search",
                    enum=["spot", "derivative"],
                ),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="injective.get_price",
            description=(
                "Get the current best bid, best ask, and last traded price "
                "for a spot or derivative market."
            ),
            parameters=[
                ToolParameter(
                    name="market_id",
                    type="string",
                    description="Hex market ID (from search_markets)",
                ),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="injective.get_orderbook",
            description="Get the orderbook (bids and asks) for a spot or derivative market.",
            parameters=[
                ToolParameter(
                    name="market_id",
                    type="string",
                    description="Hex market ID (from search_markets)",
                ),
                ToolParameter(
                    name="depth",
                    type="integer",
                    description="Number of price levels to return (default 10)",
                    required=False,
                ),
            ],
            required_permission="guest",
        ),
        # ── Account & Subaccount ─────────────────────────────────────────
        ToolDefinition(
            name="injective.get_balances",
            description="Get all token balances for a subaccount (available and total deposits).",
            parameters=[
                ToolParameter(
                    name="subaccount_index",
                    type="integer",
                    description="Subaccount index (default 0, the primary trading account)",
                    required=False,
                ),
            ],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.get_portfolio",
            description="Get an aggregated portfolio overview: bank balances, subaccount balances, and positions summary.",
            parameters=[],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.get_subaccounts",
            description="List all subaccounts and their balances.",
            parameters=[],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.subaccount_transfer",
            description=(
                "Move funds between bank and subaccounts. "
                "Use 'deposit' to move from bank to subaccount, "
                "'withdraw' to move from subaccount to bank, "
                "or 'transfer' to move between two subaccounts."
            ),
            parameters=[
                ToolParameter(
                    name="amount",
                    type="number",
                    description="Amount to transfer",
                ),
                ToolParameter(
                    name="denom",
                    type="string",
                    description="Token denomination (e.g. 'inj', 'peggy0x...' for USDT)",
                ),
                ToolParameter(
                    name="action",
                    type="string",
                    description="Transfer direction",
                    enum=["deposit", "withdraw", "transfer"],
                ),
                ToolParameter(
                    name="source_index",
                    type="integer",
                    description="Source subaccount index (default 0)",
                    required=False,
                ),
                ToolParameter(
                    name="dest_index",
                    type="integer",
                    description="Destination subaccount index (default 1, only for 'transfer' action)",
                    required=False,
                ),
            ],
            required_permission="owner",
        ),
        # ── Spot Trading ─────────────────────────────────────────────────
        ToolDefinition(
            name="injective.place_spot_order",
            description=(
                "Place a spot order (limit or market). "
                "For market orders, price acts as the worst acceptable price."
            ),
            parameters=[
                ToolParameter(
                    name="market_id",
                    type="string",
                    description="Hex market ID (from search_markets)",
                ),
                ToolParameter(
                    name="side",
                    type="string",
                    description="Order side",
                    enum=["buy", "sell"],
                ),
                ToolParameter(
                    name="price",
                    type="number",
                    description="Limit price, or worst price for market orders",
                ),
                ToolParameter(
                    name="quantity",
                    type="number",
                    description="Order quantity in base asset",
                ),
                ToolParameter(
                    name="order_type",
                    type="string",
                    description="Order type (default 'limit')",
                    required=False,
                    enum=["limit", "market"],
                ),
            ],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.cancel_spot_order",
            description="Cancel an open spot order by its order hash.",
            parameters=[
                ToolParameter(
                    name="market_id",
                    type="string",
                    description="Hex market ID the order belongs to",
                ),
                ToolParameter(
                    name="order_hash",
                    type="string",
                    description="The order hash to cancel",
                ),
            ],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.get_spot_orders",
            description="List open spot orders, optionally filtered by market.",
            parameters=[
                ToolParameter(
                    name="market_id",
                    type="string",
                    description="Filter by market ID (optional — omit to show all)",
                    required=False,
                ),
                ToolParameter(
                    name="subaccount_index",
                    type="integer",
                    description="Subaccount index (default 0)",
                    required=False,
                ),
            ],
            required_permission="owner",
        ),
        # ── Derivative / Perp Trading ────────────────────────────────────
        ToolDefinition(
            name="injective.place_derivative_order",
            description=(
                "Place a derivative (perpetual) order. Margin is auto-calculated "
                "from price * quantity / leverage. Set reduce_only=true to close a position."
            ),
            parameters=[
                ToolParameter(
                    name="market_id",
                    type="string",
                    description="Hex market ID (from search_markets)",
                ),
                ToolParameter(
                    name="side",
                    type="string",
                    description="Order side",
                    enum=["buy", "sell"],
                ),
                ToolParameter(
                    name="price",
                    type="number",
                    description="Limit price, or worst price for market orders",
                ),
                ToolParameter(
                    name="quantity",
                    type="number",
                    description="Order quantity",
                ),
                ToolParameter(
                    name="leverage",
                    type="number",
                    description="Leverage multiplier (default 1)",
                    required=False,
                ),
                ToolParameter(
                    name="order_type",
                    type="string",
                    description="Order type (default 'limit')",
                    required=False,
                    enum=["limit", "market"],
                ),
                ToolParameter(
                    name="reduce_only",
                    type="boolean",
                    description="If true, this order can only reduce an existing position (default false)",
                    required=False,
                ),
            ],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.cancel_derivative_order",
            description="Cancel an open derivative order by its order hash. Use the order_side and is_conditional fields from get_derivative_orders to fill is_buy and is_conditional.",
            parameters=[
                ToolParameter(
                    name="market_id",
                    type="string",
                    description="Hex market ID the order belongs to",
                ),
                ToolParameter(
                    name="order_hash",
                    type="string",
                    description="The order hash to cancel",
                ),
                ToolParameter(
                    name="is_buy",
                    type="boolean",
                    description="True if the order is a buy order (order_side == 'buy')",
                ),
                ToolParameter(
                    name="is_market_order",
                    type="boolean",
                    description="True if the order is a market order (default false for limit orders)",
                    required=False,
                ),
                ToolParameter(
                    name="is_conditional",
                    type="boolean",
                    description="True if the order is a conditional/trigger order",
                    required=False,
                ),
            ],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.get_derivative_orders",
            description="List open derivative orders, optionally filtered by market.",
            parameters=[
                ToolParameter(
                    name="market_id",
                    type="string",
                    description="Filter by market ID (optional — omit to show all)",
                    required=False,
                ),
                ToolParameter(
                    name="subaccount_index",
                    type="integer",
                    description="Subaccount index (default 0)",
                    required=False,
                ),
            ],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.get_positions",
            description=(
                "Get open perpetual positions with entry price, mark price, "
                "quantity, margin, and unrealized PnL."
            ),
            parameters=[
                ToolParameter(
                    name="market_id",
                    type="string",
                    description="Filter by market ID (optional — omit to show all)",
                    required=False,
                ),
                ToolParameter(
                    name="subaccount_index",
                    type="integer",
                    description="Subaccount index (default 0)",
                    required=False,
                ),
            ],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.close_position",
            description=(
                "Close an open perpetual position by placing a reduce-only market order "
                "in the opposite direction. Automatically detects position side. "
                "Omit quantity to close the full position."
            ),
            parameters=[
                ToolParameter(
                    name="market_id",
                    type="string",
                    description="Hex market ID of the position to close",
                ),
                ToolParameter(
                    name="quantity",
                    type="number",
                    description="Quantity to close (default: full position size)",
                    required=False,
                ),
                ToolParameter(
                    name="price",
                    type="number",
                    description="Worst acceptable price (default: best bid/ask with 5% slippage)",
                    required=False,
                ),
            ],
            required_permission="owner",
        ),
    ],
)
