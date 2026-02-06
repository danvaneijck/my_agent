"""Injective module manifest — tool definitions (scaffold)."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="injective",
    description="Interact with the Injective blockchain for trading operations. Scaffold — not yet connected to live chain.",
    tools=[
        ToolDefinition(
            name="injective.get_portfolio",
            description="Get the current portfolio holdings.",
            parameters=[],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.get_market_price",
            description="Get the current price for a market pair.",
            parameters=[
                ToolParameter(
                    name="market",
                    type="string",
                    description="Market pair identifier (e.g. 'INJ/USDT')",
                ),
            ],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.place_order",
            description="Place a limit order on the Injective DEX.",
            parameters=[
                ToolParameter(name="market", type="string", description="Market pair (e.g. 'INJ/USDT')"),
                ToolParameter(name="side", type="string", description="Order side", enum=["buy", "sell"]),
                ToolParameter(name="price", type="number", description="Limit price"),
                ToolParameter(name="quantity", type="number", description="Order quantity"),
            ],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.cancel_order",
            description="Cancel an open order.",
            parameters=[
                ToolParameter(name="order_id", type="string", description="The order ID to cancel"),
            ],
            required_permission="owner",
        ),
        ToolDefinition(
            name="injective.get_positions",
            description="Get all open positions.",
            parameters=[],
            required_permission="owner",
        ),
    ],
)
