#!/usr/bin/env python3
"""Interactive test script for the Injective module.

Loads env vars from agent/.env, initializes InjectiveTools directly
(no FastAPI / Docker needed), and runs each tool with live data.

Usage:
    # From the agent/ directory (so .env is picked up):
    cd agent
    pip install injective-py pydantic-settings structlog
    python -m modules.injective.test_tools

    # Or with explicit env file:
    ENV_FILE=./agent/.env python agent/modules/injective/test_tools.py

Write operations (place_spot_order, cancel_spot_order, place_derivative_order,
cancel_derivative_order, subaccount_transfer, close_position) are SKIPPED by
default. Set RUN_WRITE_TESTS=1 to include them — they will submit real
transactions on whichever network is configured.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time


def _pp(label: str, data: dict) -> None:
    """Pretty-print a result dict."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(json.dumps(data, indent=2, default=str))


async def main() -> None:
    # ── Setup ────────────────────────────────────────────────────────────
    # Ensure agent/.env is loaded even when running outside Docker
    env_file = os.environ.get("ENV_FILE", ".env")
    if os.path.exists(env_file):
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print(f"Loaded env from {env_file}")
    else:
        print(f"No {env_file} found — using existing environment variables")

    # Now import after env is loaded so pydantic-settings picks up the values
    from modules.injective.tools import InjectiveTools

    write_tests = os.environ.get("RUN_WRITE_TESTS", "").strip() == "1"
    tools = InjectiveTools()

    print("\nInitializing Injective tools...")
    t0 = time.time()
    await tools.init()
    print(f"Initialized in {time.time() - t0:.1f}s")
    print(f"  Network:  {tools.settings.injective_network}")
    print(f"  Address:  {tools.acc_address or '(read-only, no wallet)'}")
    print(f"  Markets cached: {len(tools.market_cache.spot_markets)} spot, "
          f"{len(tools.market_cache.derivative_markets)} derivative")

    # ── 1. search_markets (spot) ─────────────────────────────────────────
    print("\n\n>>> search_markets(query='INJ', market_type='spot')")
    result = await tools.search_markets(query="INJ", market_type="spot")
    _pp("search_markets — spot INJ", result)

    spot_market_id = None
    if result["markets"]:
        spot_market_id = result["markets"][0]["market_id"]
        print(f"\n  Using spot market_id: {spot_market_id}")

    # ── 2. search_markets (derivative) ───────────────────────────────────
    print("\n\n>>> search_markets(query='BTC', market_type='derivative')")
    result = await tools.search_markets(query="BTC", market_type="derivative")
    _pp("search_markets — derivative BTC", result)

    deriv_market_id = None
    if result["markets"]:
        deriv_market_id = result["markets"][0]["market_id"]
        print(f"\n  Using derivative market_id: {deriv_market_id}")

    # ── 3. get_price (spot) ──────────────────────────────────────────────
    if spot_market_id:
        print(f"\n\n>>> get_price(market_id='{spot_market_id[:16]}...')")
        result = await tools.get_price(market_id=spot_market_id)
        _pp("get_price — spot", result)
    else:
        print("\n  SKIP get_price (spot) — no spot market found")

    # ── 4. get_price (derivative) ────────────────────────────────────────
    if deriv_market_id:
        print(f"\n\n>>> get_price(market_id='{deriv_market_id[:16]}...')")
        result = await tools.get_price(market_id=deriv_market_id)
        _pp("get_price — derivative", result)
    else:
        print("\n  SKIP get_price (derivative) — no derivative market found")

    # ── 5. get_orderbook (spot) ──────────────────────────────────────────
    if spot_market_id:
        print(f"\n\n>>> get_orderbook(market_id='{spot_market_id[:16]}...', depth=5)")
        result = await tools.get_orderbook(market_id=spot_market_id, depth=5)
        _pp("get_orderbook — spot", result)
    else:
        print("\n  SKIP get_orderbook (spot)")

    # ── 6. get_orderbook (derivative) ────────────────────────────────────
    if deriv_market_id:
        print(f"\n\n>>> get_orderbook(market_id='{deriv_market_id[:16]}...', depth=5)")
        result = await tools.get_orderbook(market_id=deriv_market_id, depth=5)
        _pp("get_orderbook — derivative", result)
    else:
        print("\n  SKIP get_orderbook (derivative)")

    # ── Account tools (require wallet) ───────────────────────────────────
    if tools.address:
        # ── 7. get_portfolio ─────────────────────────────────────────────
        print("\n\n>>> get_portfolio()")
        result = await tools.get_portfolio()
        _pp("get_portfolio", result)

        # ── 8. get_balances ──────────────────────────────────────────────
        print("\n\n>>> get_balances(subaccount_index=0)")
        result = await tools.get_balances(subaccount_index=0)
        _pp("get_balances", result)

        # ── 9. get_subaccounts ───────────────────────────────────────────
        print("\n\n>>> get_subaccounts()")
        result = await tools.get_subaccounts()
        _pp("get_subaccounts", result)

        # ── 10. get_spot_orders ──────────────────────────────────────────
        print("\n\n>>> get_spot_orders()")
        result = await tools.get_spot_orders()
        _pp("get_spot_orders", result)

        # ── 11. get_derivative_orders ────────────────────────────────────
        print("\n\n>>> get_derivative_orders()")
        result = await tools.get_derivative_orders()
        _pp("get_derivative_orders", result)

        # ── 12. get_positions ────────────────────────────────────────────
        print("\n\n>>> get_positions()")
        result = await tools.get_positions()
        _pp("get_positions", result)
    else:
        print("\n\n  SKIP account tools (no wallet configured)")

    # ── Write operations (off by default) ────────────────────────────────
    if not write_tests:
        print("\n\n" + "="*60)
        print("  Write tests SKIPPED (set RUN_WRITE_TESTS=1 to enable)")
        print("="*60)
        print("\nAll read-only tests complete.")
        return

    if not tools.address:
        print("\n  Cannot run write tests without a wallet")
        return

    print("\n\n" + "="*60)
    print("  WRITE TESTS — real transactions will be submitted!")
    print("="*60)

    # ── 13. subaccount_transfer (deposit) ────────────────────────────────
    print("\n\n>>> subaccount_transfer(amount=0.001, denom='inj', action='deposit')")
    try:
        result = await tools.subaccount_transfer(
            amount=0.001, denom="inj", action="deposit",
        )
        _pp("subaccount_transfer — deposit", result)
    except Exception as e:
        print(f"  ERROR: {e}")

    # ── 14. place_spot_order (limit, far from market) ────────────────────
    if spot_market_id:
        # Place a buy limit well below market so it won't fill
        print(f"\n\n>>> place_spot_order(side='buy', price=0.01, quantity=1, order_type='limit')")
        try:
            result = await tools.place_spot_order(
                market_id=spot_market_id,
                side="buy",
                price=0.01,
                quantity=1,
                order_type="limit",
            )
            _pp("place_spot_order", result)

            # ── 15. cancel_spot_order ────────────────────────────────────
            order_cid = result.get("cid", "")
            if "tx_hash" in result:
                print("\n  Waiting 3s for order to appear on chain...")
                await asyncio.sleep(3)
                orders = await tools.get_spot_orders(market_id=spot_market_id)
                if orders["orders"]:
                    oh = orders["orders"][0]["order_hash"]
                    print(f"\n>>> cancel_spot_order(order_hash='{oh[:16]}...')")
                    cancel_result = await tools.cancel_spot_order(
                        market_id=spot_market_id, order_hash=oh,
                    )
                    _pp("cancel_spot_order", cancel_result)
        except Exception as e:
            print(f"  ERROR: {e}")

    # ── 16. place_derivative_order (limit, far from market) ──────────────
    if deriv_market_id:
        print(f"\n\n>>> place_derivative_order(side='buy', price=1.0, quantity=0.001, leverage=1)")
        try:
            result = await tools.place_derivative_order(
                market_id=deriv_market_id,
                side="buy",
                price=1.0,
                quantity=0.001,
                leverage=1,
                order_type="limit",
            )
            _pp("place_derivative_order", result)

            # ── 17. cancel_derivative_order ──────────────────────────────
            if "tx_hash" in result:
                print("\n  Waiting 3s for order to appear on chain...")
                await asyncio.sleep(3)
                orders = await tools.get_derivative_orders(market_id=deriv_market_id)
                if orders["orders"]:
                    oh = orders["orders"][0]["order_hash"]
                    print(f"\n>>> cancel_derivative_order(order_hash='{oh[:16]}...')")
                    cancel_result = await tools.cancel_derivative_order(
                        market_id=deriv_market_id, order_hash=oh,
                    )
                    _pp("cancel_derivative_order", cancel_result)
        except Exception as e:
            print(f"  ERROR: {e}")

    # ── 18. close_position (only if there's an open position) ────────────
    positions = await tools.get_positions()
    if positions["positions"]:
        pos = positions["positions"][0]
        mid = pos["market_id"]
        print(f"\n\n>>> close_position(market_id='{mid[:16]}...')")
        try:
            result = await tools.close_position(market_id=mid)
            _pp("close_position", result)
        except Exception as e:
            print(f"  ERROR: {e}")
    else:
        print("\n  SKIP close_position — no open positions")

    print("\n\nAll tests complete.")


if __name__ == "__main__":
    asyncio.run(main())
