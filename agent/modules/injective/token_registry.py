"""Token registry — maps denoms to symbols, decimals, and names.

Loads the official token list from InjectiveLabs/injective-lists on startup,
and merges any custom overrides from a local JSON file.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal

import httpx
import structlog

logger = structlog.get_logger()

# CDN URL (recommended by injective-lists README)
_CDN_BASE = "https://d36789lqgasyke.cloudfront.net/json/tokens"
# GitHub fallback
_GH_BASE = "https://raw.githubusercontent.com/InjectiveLabs/injective-lists/master/json/tokens"

# Well-known tokens as fallback when the remote list can't be fetched
_WELL_KNOWN: dict[str, dict] = {
    "inj": {"symbol": "INJ", "decimals": 18, "name": "Injective"},
    "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7": {
        "symbol": "USDT", "decimals": 6, "name": "Tether USD",
    },
    "peggy0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": {
        "symbol": "USDC", "decimals": 6, "name": "USD Coin",
    },
    "peggy0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2": {
        "symbol": "WETH", "decimals": 18, "name": "Wrapped Ether",
    },
    "peggy0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599": {
        "symbol": "WBTC", "decimals": 8, "name": "Wrapped Bitcoin",
    },
}


@dataclass
class TokenMeta:
    symbol: str
    decimals: int
    name: str = ""


class TokenRegistry:
    """Maps denoms to their metadata (symbol, decimals)."""

    def __init__(self) -> None:
        self._tokens: dict[str, TokenMeta] = {}

    async def load(self, network: str = "mainnet", custom_file: str | None = None) -> None:
        """Load token metadata from remote list + optional local overrides."""
        # 1. Seed with well-known fallbacks
        for denom, info in _WELL_KNOWN.items():
            self._tokens[denom] = TokenMeta(**info)

        # 2. Fetch official list from CDN (fall back to GitHub raw)
        net = "mainnet" if network == "mainnet" else "testnet"
        for base_url in [_CDN_BASE, _GH_BASE]:
            url = f"{base_url}/{net}.json"
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    count = self._ingest(data)
                    logger.info("token_registry_loaded", source=url, count=count)
                    break  # success — skip fallback
            except Exception as e:
                logger.warning("token_registry_fetch_failed", url=url, error=str(e))
        else:
            logger.warning("token_registry_using_fallbacks_only")

        # 3. Load custom overrides from local file
        if custom_file and os.path.exists(custom_file):
            try:
                with open(custom_file) as f:
                    custom = json.load(f)
                count = self._ingest(custom)
                logger.info("token_registry_custom_loaded", file=custom_file, count=count)
            except Exception as e:
                logger.warning("token_registry_custom_error", file=custom_file, error=str(e))

        logger.info("token_registry_ready", total=len(self._tokens))

    def _ingest(self, data: list[dict]) -> int:
        """Ingest a list of token entries. Returns count of tokens loaded."""
        count = 0
        for entry in data:
            denom = entry.get("denom", "")
            if not denom:
                continue
            self._tokens[denom] = TokenMeta(
                symbol=entry.get("symbol", ""),
                decimals=entry.get("decimals", 18),
                name=entry.get("name", ""),
            )
            count += 1
        return count

    # ── Lookups ──────────────────────────────────────────────────────────

    def get_decimals(self, denom: str) -> int:
        meta = self._tokens.get(denom)
        return meta.decimals if meta else 18  # default 18 for unknown tokens

    def get_symbol(self, denom: str) -> str:
        meta = self._tokens.get(denom)
        if meta and meta.symbol:
            return meta.symbol
        return _shorten_denom(denom)

    def get_meta(self, denom: str) -> TokenMeta | None:
        return self._tokens.get(denom)

    # ── Decimal Conversions ──────────────────────────────────────────────

    def chain_price_to_human_spot(
        self, raw_price: str, base_denom: str, quote_denom: str,
    ) -> str:
        """Convert a raw chain spot price to human-readable.

        Chain stores: chain_price = human_price * 10^(quote_dec - base_dec)
        So: human_price = chain_price * 10^(base_dec - quote_dec)
        """
        if not raw_price:
            return ""
        base_dec = self.get_decimals(base_denom)
        quote_dec = self.get_decimals(quote_denom)
        exp = base_dec - quote_dec
        human = Decimal(raw_price) * Decimal(10) ** exp
        return _fmt(human)

    def chain_price_to_human_deriv(self, raw_price: str, quote_denom: str) -> str:
        """Convert a raw chain derivative price to human-readable.

        For perps: human_price = chain_price / 10^quote_decimals
        """
        if not raw_price:
            return ""
        quote_dec = self.get_decimals(quote_denom)
        human = Decimal(raw_price) / Decimal(10) ** quote_dec
        return _fmt(human)

    def chain_quantity_to_human_spot(self, raw_qty: str, base_denom: str) -> str:
        """Convert a raw chain spot quantity to human-readable.

        Chain stores quantities in base token smallest units.
        human_qty = chain_qty / 10^base_decimals
        """
        if not raw_qty:
            return ""
        base_dec = self.get_decimals(base_denom)
        human = Decimal(raw_qty) / Decimal(10) ** base_dec
        return _fmt(human)

    def format_balance(self, amount: str, denom: str) -> dict:
        """Return a balance dict with symbol added (balances from indexer are already human-readable)."""
        return {
            "denom": denom,
            "symbol": self.get_symbol(denom),
            "amount": amount,
        }

    def human_to_chain_amount(self, human_amount: Decimal, denom: str) -> int:
        """Convert a human-readable amount to chain base units (for deposits/withdrawals)."""
        decimals = self.get_decimals(denom)
        return int(human_amount * Decimal(10) ** decimals)


def _shorten_denom(denom: str) -> str:
    """Shorten long denoms for display."""
    if denom.startswith("factory/"):
        parts = denom.split("/")
        return parts[-1] if len(parts) >= 3 else denom[:30]
    if denom.startswith("ibc/"):
        return f"IBC/{denom[4:10]}..."
    if denom.startswith("peggy0x"):
        return f"peggy..{denom[-6:]}"
    if len(denom) > 20:
        return f"{denom[:17]}..."
    return denom


def _fmt(d: Decimal) -> str:
    """Format a Decimal, stripping trailing zeros."""
    return f"{d:f}".rstrip("0").rstrip(".")
