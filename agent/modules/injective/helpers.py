"""Helpers — market cache, formatting, and error utilities."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class MarketCache:
    """In-memory cache for market metadata (ticker → market_id mapping)."""

    def __init__(self) -> None:
        self.spot_markets: list[dict] = []
        self.derivative_markets: list[dict] = []
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    async def refresh(self, indexer_client) -> None:
        """Fetch all active markets from the indexer and cache them."""
        try:
            raw_spot = await indexer_client.fetch_spot_markets(market_statuses=["active"])
            self.spot_markets = _parse_spot_markets(raw_spot)
        except Exception as e:
            logger.warning("market_cache_spot_error", error=str(e))
            self.spot_markets = []

        try:
            raw_deriv = await indexer_client.fetch_derivative_markets(market_statuses=["active"])
            self.derivative_markets = _parse_derivative_markets(raw_deriv)
        except Exception as e:
            logger.warning("market_cache_derivative_error", error=str(e))
            self.derivative_markets = []

        self._loaded = True
        logger.info(
            "market_cache_refreshed",
            spot_count=len(self.spot_markets),
            derivative_count=len(self.derivative_markets),
        )

    def search(self, query: str, market_type: str) -> list[dict]:
        """Search cached markets by query string."""
        query_upper = query.upper().strip()
        source = self.spot_markets if market_type == "spot" else self.derivative_markets
        results = []
        for m in source:
            ticker = m.get("ticker", "").upper()
            if query_upper in ticker:
                results.append(m)
        # Sort exact ticker matches first, then partial matches
        results.sort(key=lambda m: (0 if m.get("ticker", "").upper() == query_upper else 1))
        return results[:20]

    def is_spot_market(self, market_id: str) -> bool | None:
        """Return True if spot, False if derivative, None if unknown."""
        for m in self.spot_markets:
            if m["market_id"] == market_id:
                return True
        for m in self.derivative_markets:
            if m["market_id"] == market_id:
                return False
        return None


def _parse_spot_markets(raw: dict) -> list[dict]:
    """Extract useful fields from the raw spot markets response."""
    markets = []
    for m in raw.get("markets", []):
        markets.append({
            "market_id": m.get("marketId", ""),
            "ticker": m.get("ticker", ""),
            "base_denom": m.get("baseDenom", ""),
            "quote_denom": m.get("quoteDenom", ""),
            "status": m.get("marketStatus", ""),
            "min_quantity_tick": m.get("minQuantityTickSize", ""),
            "min_price_tick": m.get("minPriceTickSize", ""),
        })
    return markets


def _parse_derivative_markets(raw: dict) -> list[dict]:
    """Extract useful fields from the raw derivative markets response."""
    markets = []
    for m in raw.get("markets", []):
        markets.append({
            "market_id": m.get("marketId", ""),
            "ticker": m.get("ticker", ""),
            "quote_denom": m.get("quoteDenom", ""),
            "oracle_type": m.get("oracleType", ""),
            "status": m.get("marketStatus", ""),
            "initial_margin_ratio": m.get("initialMarginRatio", ""),
            "maintenance_margin_ratio": m.get("maintenanceMarginRatio", ""),
            "min_quantity_tick": m.get("minQuantityTickSize", ""),
            "min_price_tick": m.get("minPriceTickSize", ""),
            "is_perpetual": m.get("isPerpetual", False),
        })
    return markets


def format_orderbook_side(levels: list) -> list[dict]:
    """Format orderbook price levels into a clean list."""
    result = []
    for level in levels:
        result.append({
            "price": level.get("price", ""),
            "quantity": level.get("quantity", ""),
            "timestamp": level.get("timestamp", ""),
        })
    return result


def require_wallet(address: object) -> None:
    """Raise if the wallet is not configured."""
    if address is None:
        raise RuntimeError(
            "Wallet not configured — set INJECTIVE_PRIVATE_KEY in your .env to use trading tools"
        )
