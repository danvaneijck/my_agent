"""Injective module tool implementations — scaffold with mock data."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class InjectiveTools:
    """Scaffold tool implementations for Injective blockchain operations.

    All methods return mock data. Replace with real Injective SDK integration later.
    """

    async def get_portfolio(self) -> dict:
        """Return mock portfolio holdings."""
        return {
            "holdings": [
                {"asset": "INJ", "balance": "125.50", "value_usd": "2510.00"},
                {"asset": "USDT", "balance": "5000.00", "value_usd": "5000.00"},
                {"asset": "ETH", "balance": "1.25", "value_usd": "4375.00"},
            ],
            "total_value_usd": "11885.00",
            "_mock": True,
        }

    async def get_market_price(self, market: str) -> dict:
        """Return mock market price."""
        mock_prices = {
            "INJ/USDT": {"bid": "20.00", "ask": "20.05", "last": "20.02"},
            "ETH/USDT": {"bid": "3500.00", "ask": "3501.50", "last": "3500.75"},
            "BTC/USDT": {"bid": "65000.00", "ask": "65010.00", "last": "65005.00"},
        }
        price = mock_prices.get(market.upper(), {"bid": "0", "ask": "0", "last": "0"})
        return {
            "market": market,
            **price,
            "_mock": True,
        }

    async def place_order(
        self,
        market: str,
        side: str,
        price: float,
        quantity: float,
    ) -> dict:
        """Return mock order placement result."""
        return {
            "order_id": "mock_order_12345",
            "market": market,
            "side": side,
            "price": str(price),
            "quantity": str(quantity),
            "status": "placed",
            "_mock": True,
            "_warning": "This is a scaffold. No real order was placed.",
        }

    async def cancel_order(self, order_id: str) -> dict:
        """Return mock order cancellation result."""
        return {
            "order_id": order_id,
            "status": "cancelled",
            "_mock": True,
            "_warning": "This is a scaffold. No real order was cancelled.",
        }

    async def get_positions(self) -> dict:
        """Return mock open positions."""
        return {
            "positions": [
                {
                    "market": "INJ/USDT",
                    "side": "long",
                    "size": "50.00",
                    "entry_price": "18.50",
                    "mark_price": "20.02",
                    "pnl": "76.00",
                },
            ],
            "_mock": True,
        }
