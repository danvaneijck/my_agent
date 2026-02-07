"""Injective module tool implementations — spot and derivative trading via injective-py SDK."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import structlog

from modules.injective.helpers import MarketCache, format_orderbook_side, require_wallet
from modules.injective.token_registry import TokenRegistry
from shared.config import get_settings

logger = structlog.get_logger()


class InjectiveTools:
    """Live Injective DEX trading tools.

    Uses IndexerClient for read-only queries and AsyncClient + MsgBroadcasterWithPk
    for transaction signing/broadcasting. All prices and quantities are converted
    to human-readable form using token decimals from the official injective-lists.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.market_cache = MarketCache()
        self.token_registry = TokenRegistry()

        # These are set during async init
        self.network = None
        self.indexer_client = None
        self.client = None
        self.composer = None
        self.broadcaster = None
        self.address = None
        self.acc_address: str = ""
        self._initialized = False

    async def init(self) -> None:
        """Async initialization — called once from FastAPI startup."""
        from pyinjective.core.network import Network
        from pyinjective.indexer_client import IndexerClient

        net_name = self.settings.injective_network.lower()

        # Use custom endpoints if provided, otherwise SDK defaults
        exchange_grpc = self.settings.injective_exchange_grpc.strip()
        chain_grpc = self.settings.injective_chain_grpc.strip()
        lcd = self.settings.injective_lcd.strip()

        if exchange_grpc or chain_grpc or lcd:
            # At least one custom endpoint — build a custom network
            if net_name == "mainnet":
                defaults = Network.mainnet()
                chain_id = "injective-1"
            else:
                defaults = Network.testnet()
                chain_id = "injective-888"

            self.network = Network.custom(
                lcd_endpoint=lcd or defaults.lcd_endpoint,
                grpc_endpoint=chain_grpc or defaults.grpc_endpoint,
                grpc_exchange_endpoint=exchange_grpc or defaults.grpc_exchange_endpoint,
                grpc_explorer_endpoint=defaults.grpc_explorer_endpoint,
                chain_stream_endpoint=defaults.chain_stream_endpoint,
                chain_id=chain_id,
                env=defaults.env,
                official_tokens_list_url=defaults.official_tokens_list_url,
                tm_websocket_endpoint=defaults.tm_websocket_endpoint,
            )
            logger.info(
                "injective_custom_network",
                network=net_name,
                exchange_grpc=exchange_grpc or "(default)",
                chain_grpc=chain_grpc or "(default)",
                lcd=lcd or "(default)",
            )
        elif net_name == "mainnet":
            self.network = Network.mainnet()
        else:
            self.network = Network.testnet()

        logger.info("injective_network", network=net_name)

        # IndexerClient is always available (read-only, no wallet needed)
        self.indexer_client = IndexerClient(self.network)

        # Load token registry (decimals, symbols)
        custom_tokens = self.settings.injective_custom_tokens.strip() or None
        await self.token_registry.load(network=net_name, custom_file=custom_tokens)

        # Wallet + broadcaster: accept either hex private key or mnemonic
        pk_hex = self.settings.injective_private_key.strip()
        mnemonic = self.settings.injective_mnemonic.strip()

        if pk_hex:
            await self._init_wallet(pk_hex)
        elif mnemonic:
            pk_hex = self._mnemonic_to_hex(mnemonic)
            await self._init_wallet(pk_hex)
        else:
            logger.warning(
                "injective_no_credentials",
                msg="Read-only mode — set INJECTIVE_PRIVATE_KEY or INJECTIVE_MNEMONIC",
            )

        # Pre-load market cache
        await self.market_cache.refresh(self.indexer_client)
        self._initialized = True

    @staticmethod
    def _mnemonic_to_hex(mnemonic: str) -> str:
        """Derive a hex private key from a BIP-39 mnemonic phrase."""
        from pyinjective.wallet import PrivateKey

        priv_key = PrivateKey.from_mnemonic(mnemonic)
        return priv_key.to_hex()

    async def _init_wallet(self, pk_hex: str) -> None:
        """Set up wallet, async client, composer, and broadcaster."""
        from pyinjective.async_client_v2 import AsyncClient
        from pyinjective.core.broadcaster import MsgBroadcasterWithPk
        from pyinjective.wallet import PrivateKey

        priv_key = PrivateKey.from_hex(pk_hex)
        pub_key = priv_key.to_public_key()
        self.address = pub_key.to_address()
        self.acc_address = self.address.to_acc_bech32()

        logger.info("injective_wallet_loaded", address=self.acc_address)

        self.client = AsyncClient(self.network)
        self.composer = await self.client.composer()

        gas_price = await self.client.current_chain_gas_price()
        gas_price = int(gas_price * 1.1)  # 10% buffer

        self.broadcaster = MsgBroadcasterWithPk.new_using_gas_heuristics(
            network=self.network,
            private_key=pk_hex,
            gas_price=gas_price,
            client=self.client,
            composer=self.composer,
        )

    def _subaccount_id(self, index: int = 1) -> str:
        require_wallet(self.address)
        return self.address.get_subaccount_id(index=index)

    def _market_denoms(self, market_id: str) -> tuple[str, str, bool]:
        """Look up base_denom, quote_denom, and is_spot for a market."""
        for m in self.market_cache.spot_markets:
            if m["market_id"] == market_id:
                return m.get("base_denom", ""), m.get("quote_denom", ""), True
        for m in self.market_cache.derivative_markets:
            if m["market_id"] == market_id:
                return "", m.get("quote_denom", ""), False
        return "", "", True

    def _convert_spot_price(self, raw_price: str, market_id: str) -> str:
        base_denom, quote_denom, _ = self._market_denoms(market_id)
        return self.token_registry.chain_price_to_human_spot(
            raw_price, base_denom, quote_denom
        )

    def _convert_deriv_price(self, raw_price: str, market_id: str) -> str:
        _, quote_denom, _ = self._market_denoms(market_id)
        return self.token_registry.chain_price_to_human_deriv(raw_price, quote_denom)

    def _convert_spot_quantity(self, raw_qty: str, market_id: str) -> str:
        base_denom, _, _ = self._market_denoms(market_id)
        return self.token_registry.chain_quantity_to_human_spot(raw_qty, base_denom)

    # ── Market Data ──────────────────────────────────────────────────────

    async def search_markets(self, query: str, market_type: str) -> dict:
        """Search for markets by ticker."""
        if not self.market_cache.is_loaded:
            await self.market_cache.refresh(self.indexer_client)

        results = self.market_cache.search(query, market_type)
        return {
            "market_type": market_type,
            "query": query,
            "count": len(results),
            "markets": results,
        }

    async def get_price(self, market_id: str) -> dict:
        """Get current price for a market."""
        is_spot = self.market_cache.is_spot_market(market_id)

        if is_spot is True or is_spot is None:
            try:
                return await self._get_spot_price(market_id)
            except Exception:
                if is_spot is True:
                    raise
        return await self._get_derivative_price(market_id)

    async def _get_spot_price(self, market_id: str) -> dict:
        from pyinjective.client.model.pagination import PaginationOption

        ob = await self.indexer_client.fetch_spot_orderbook_v2(
            market_id=market_id, depth=1
        )
        raw_bid = (
            ob["orderbook"].get("buys", [{}])[0].get("price", "")
            if ob.get("orderbook", {}).get("buys")
            else ""
        )
        raw_ask = (
            ob["orderbook"].get("sells", [{}])[0].get("price", "")
            if ob.get("orderbook", {}).get("sells")
            else ""
        )

        pagination = PaginationOption(skip=0, limit=1)
        trades = await self.indexer_client.fetch_spot_trades(
            market_ids=[market_id],
            pagination=pagination,
        )
        raw_last = ""
        trade_list = trades.get("trades", [])
        if trade_list:
            t = trade_list[0].get("price", {})
            raw_last = t if isinstance(t, str) else t.get("price", "")

        return {
            "market_id": market_id,
            "market_type": "spot",
            "best_bid": self._convert_spot_price(raw_bid, market_id),
            "best_ask": self._convert_spot_price(raw_ask, market_id),
            "last_price": self._convert_spot_price(raw_last, market_id),
        }

    async def _get_derivative_price(self, market_id: str) -> dict:
        from pyinjective.client.model.pagination import PaginationOption

        ob = await self.indexer_client.fetch_derivative_orderbook_v2(
            market_id=market_id, depth=1
        )
        raw_bid = (
            ob["orderbook"].get("buys", [{}])[0].get("price", "")
            if ob.get("orderbook", {}).get("buys")
            else ""
        )
        raw_ask = (
            ob["orderbook"].get("sells", [{}])[0].get("price", "")
            if ob.get("orderbook", {}).get("sells")
            else ""
        )

        pagination = PaginationOption(skip=0, limit=1)
        trades = await self.indexer_client.fetch_derivative_trades(
            market_ids=[market_id],
            pagination=pagination,
        )
        raw_last = ""
        trade_list = trades.get("trades", [])
        if trade_list:
            raw_last = trade_list[0].get("positionDelta", {}).get("executionPrice", "")

        return {
            "market_id": market_id,
            "market_type": "derivative",
            "best_bid": self._convert_deriv_price(raw_bid, market_id),
            "best_ask": self._convert_deriv_price(raw_ask, market_id),
            "last_price": self._convert_deriv_price(raw_last, market_id),
        }

    async def get_orderbook(self, market_id: str, depth: int = 10) -> dict:
        """Get orderbook for a market."""
        is_spot = self.market_cache.is_spot_market(market_id)
        base_denom, quote_denom, _ = self._market_denoms(market_id)

        if is_spot is True or is_spot is None:
            try:
                ob = await self.indexer_client.fetch_spot_orderbook_v2(
                    market_id=market_id,
                    depth=depth,
                )
                return {
                    "market_id": market_id,
                    "market_type": "spot",
                    "bids": format_orderbook_side(
                        ob["orderbook"].get("buys", [])[:depth],
                        self.token_registry,
                        base_denom,
                        quote_denom,
                        is_spot=True,
                    ),
                    "asks": format_orderbook_side(
                        ob["orderbook"].get("sells", [])[:depth],
                        self.token_registry,
                        base_denom,
                        quote_denom,
                        is_spot=True,
                    ),
                }
            except Exception:
                if is_spot is True:
                    raise

        ob = await self.indexer_client.fetch_derivative_orderbook_v2(
            market_id=market_id,
            depth=depth,
        )
        return {
            "market_id": market_id,
            "market_type": "derivative",
            "bids": format_orderbook_side(
                ob["orderbook"].get("buys", [])[:depth],
                self.token_registry,
                "",
                quote_denom,
                is_spot=False,
            ),
            "asks": format_orderbook_side(
                ob["orderbook"].get("sells", [])[:depth],
                self.token_registry,
                "",
                quote_denom,
                is_spot=False,
            ),
        }

    # ── Account & Subaccount ─────────────────────────────────────────────

    async def get_balances(self, subaccount_index: int = 1) -> dict:
        """Get balances for a subaccount."""
        require_wallet(self.address)
        subaccount_id = self._subaccount_id(subaccount_index)

        raw = await self.indexer_client.fetch_subaccount_balances_list(
            subaccount_id=subaccount_id,
        )
        balances = []
        for b in raw.get("balances", []):
            deposit = b.get("deposit", {})
            denom = b.get("denom", "")
            balances.append(
                {
                    "denom": denom,
                    "symbol": self.token_registry.get_symbol(denom),
                    "available": deposit.get("availableBalance", "0"),
                    "total": deposit.get("totalBalance", "0"),
                }
            )

        return {
            "subaccount_index": subaccount_index,
            "subaccount_id": subaccount_id,
            "balances": balances,
        }

    async def get_portfolio(self) -> dict:
        """Get aggregated portfolio overview."""
        require_wallet(self.address)

        raw = await self.indexer_client.fetch_portfolio(
            account_address=self.acc_address,
        )
        print(raw)
        portfolio = raw.get("portfolio", {})

        bank_balances = []
        for b in portfolio.get("bankBalances", []):
            denom = b.get("denom", "")
            bank_balances.append(
                {
                    "denom": denom,
                    "symbol": self.token_registry.get_symbol(denom),
                    "amount": b.get("amount", "0"),
                }
            )

        subaccounts = []
        for sa in portfolio.get("subaccounts", []):
            deposit = sa.get("deposit", {})
            denom = sa.get("denom", "")
            subaccounts.append(
                {
                    "subaccount_id": sa.get("subaccountId", ""),
                    "denom": denom,
                    "symbol": self.token_registry.get_symbol(denom),
                    "available": deposit.get("availableBalance", "0"),
                    "total": deposit.get("totalBalance", "0"),
                }
            )

        return {
            "address": self.acc_address,
            "bank_balances": bank_balances,
            "subaccount_balances": subaccounts,
        }

    async def get_subaccounts(self) -> dict:
        """List all subaccounts."""
        require_wallet(self.address)

        raw = await self.indexer_client.fetch_subaccounts_list(self.acc_address)
        subaccount_ids = raw.get("subaccounts", [])

        return {
            "address": self.acc_address,
            "subaccounts": subaccount_ids,
        }

    async def subaccount_transfer(
        self,
        amount: float,
        denom: str,
        action: str,
        source_index: int = 0,
        dest_index: int = 1,
    ) -> dict:
        """Deposit, withdraw, or transfer between subaccounts."""
        require_wallet(self.address)

        dec_amount = Decimal(str(amount))
        # Convert human amount to chain base units for deposits/withdrawals
        chain_amount = self.token_registry.human_to_chain_amount(dec_amount, denom)

        if action == "deposit":
            msg = self.composer.msg_deposit(
                sender=self.acc_address,
                subaccount_id=self._subaccount_id(dest_index),
                amount=Decimal(chain_amount),
                denom=denom,
            )
        elif action == "withdraw":
            msg = self.composer.msg_withdraw(
                sender=self.acc_address,
                subaccount_id=self._subaccount_id(dest_index),
                amount=Decimal(chain_amount),
                denom=denom,
            )
        elif action == "transfer":
            print(
                f"Transferring {amount} {denom} from subaccount {source_index} to {dest_index}"
            )
            msg = self.composer.msg_subaccount_transfer(
                sender=self.acc_address,
                source_subaccount_id=self._subaccount_id(source_index),
                destination_subaccount_id=self._subaccount_id(dest_index),
                amount=chain_amount,
                denom=denom,
            )
        else:
            raise ValueError(f"Unknown action: {action}")

        result = await self.broadcaster.broadcast([msg])
        return {
            "action": action,
            "amount": str(amount),
            "denom": denom,
            "symbol": self.token_registry.get_symbol(denom),
            "tx_hash": getattr(result, "txhash", str(result)),
        }

    # ── Spot Trading ─────────────────────────────────────────────────────

    async def place_spot_order(
        self,
        market_id: str,
        side: str,
        price: float,
        quantity: float,
        order_type: str = "limit",
    ) -> dict:
        """Place a spot limit or market order."""
        require_wallet(self.address)

        order_side = "BUY" if side.lower() == "buy" else "SELL"
        dec_price = Decimal(str(price))
        dec_quantity = Decimal(str(quantity))
        cid = str(uuid4())

        if order_type == "market":
            msg = self.composer.msg_create_spot_market_order(
                market_id=market_id,
                sender=self.acc_address,
                subaccount_id=self._subaccount_id(1),
                fee_recipient=self.acc_address,
                price=dec_price,
                quantity=dec_quantity,
                order_type=order_side,
                cid=cid,
            )
        else:
            msg = self.composer.msg_create_spot_limit_order(
                market_id=market_id,
                sender=self.acc_address,
                subaccount_id=self._subaccount_id(1),
                fee_recipient=self.acc_address,
                price=dec_price,
                quantity=dec_quantity,
                order_type=order_side,
                cid=cid,
            )

        result = await self.broadcaster.broadcast([msg])
        return {
            "order_type": order_type,
            "side": side,
            "price": str(price),
            "quantity": str(quantity),
            "market_id": market_id,
            "cid": cid,
            "tx_hash": getattr(result, "txhash", str(result)),
        }

    async def cancel_spot_order(self, market_id: str, order_hash: str) -> dict:
        """Cancel an open spot order."""
        require_wallet(self.address)

        msg = self.composer.msg_cancel_spot_order(
            market_id=market_id,
            sender=self.acc_address,
            subaccount_id=self._subaccount_id(1),
            order_hash=order_hash,
        )
        result = await self.broadcaster.broadcast([msg])
        return {
            "cancelled": True,
            "order_hash": order_hash,
            "market_id": market_id,
            "tx_hash": getattr(result, "txhash", str(result)),
        }

    async def get_spot_orders(
        self,
        market_id: str | None = None,
        subaccount_index: int = 1,
    ) -> dict:
        """List open spot orders."""
        require_wallet(self.address)
        subaccount_id = self._subaccount_id(subaccount_index)

        kwargs: dict = {"subaccount_id": subaccount_id}
        if market_id:
            kwargs["market_ids"] = [market_id]

        raw = await self.indexer_client.fetch_spot_orders(**kwargs)
        orders = []
        for o in raw.get("orders", []):
            mid = o.get("marketId", "")
            orders.append(
                {
                    "order_hash": o.get("orderHash", ""),
                    "market_id": mid,
                    "order_type": o.get("orderType", ""),
                    "order_side": o.get("orderSide", ""),
                    "price": self._convert_spot_price(o.get("price", ""), mid),
                    "quantity": self._convert_spot_quantity(o.get("quantity", ""), mid),
                    "unfilled_quantity": self._convert_spot_quantity(
                        o.get("unfilledQuantity", ""), mid
                    ),
                    "state": o.get("state", ""),
                    "created_at": o.get("createdAt", ""),
                }
            )
        return {"count": len(orders), "orders": orders}

    # ── Derivative / Perp Trading ────────────────────────────────────────

    async def place_derivative_order(
        self,
        market_id: str,
        side: str,
        price: float,
        quantity: float,
        leverage: float = 1,
        order_type: str = "limit",
        reduce_only: bool = False,
    ) -> dict:
        """Place a derivative limit or market order."""
        require_wallet(self.address)

        order_side = "BUY" if side.lower() == "buy" else "SELL"
        dec_price = Decimal(str(price))
        dec_quantity = Decimal(str(quantity))
        dec_leverage = Decimal(str(leverage))
        cid = str(uuid4())

        margin = self.composer.calculate_margin(
            quantity=dec_quantity,
            price=dec_price,
            leverage=dec_leverage,
            is_reduce_only=reduce_only,
        )

        if order_type == "market":
            msg = self.composer.msg_create_derivative_market_order(
                market_id=market_id,
                sender=self.acc_address,
                subaccount_id=self._subaccount_id(1),
                fee_recipient=self.acc_address,
                price=dec_price,
                quantity=dec_quantity,
                margin=margin,
                order_type=order_side,
                cid=cid,
            )
        else:
            msg = self.composer.msg_create_derivative_limit_order(
                market_id=market_id,
                sender=self.acc_address,
                subaccount_id=self._subaccount_id(1),
                fee_recipient=self.acc_address,
                price=dec_price,
                quantity=dec_quantity,
                margin=margin,
                order_type=order_side,
                cid=cid,
            )

        result = await self.broadcaster.broadcast([msg])
        return {
            "order_type": order_type,
            "side": side,
            "price": str(price),
            "quantity": str(quantity),
            "leverage": str(leverage),
            "reduce_only": reduce_only,
            "margin": str(margin),
            "market_id": market_id,
            "cid": cid,
            "tx_hash": getattr(result, "txhash", str(result)),
        }

    async def cancel_derivative_order(
        self,
        market_id: str,
        order_hash: str,
        is_buy: bool = False,
        is_market_order: bool = False,
        is_conditional: bool = False,
    ) -> dict:
        """Cancel an open derivative order."""
        require_wallet(self.address)

        msg = self.composer.msg_cancel_derivative_order(
            market_id=market_id,
            sender=self.acc_address,
            subaccount_id=self._subaccount_id(1),
            order_hash=order_hash,
            is_buy=is_buy,
            is_market_order=is_market_order,
            is_conditional=is_conditional,
        )
        result = await self.broadcaster.broadcast([msg])
        return {
            "cancelled": True,
            "order_hash": order_hash,
            "market_id": market_id,
            "tx_hash": getattr(result, "txhash", str(result)),
        }

    async def get_derivative_orders(
        self,
        market_id: str | None = None,
        subaccount_index: int = 1,
    ) -> dict:
        """List open derivative orders."""
        require_wallet(self.address)
        subaccount_id = self._subaccount_id(subaccount_index)

        kwargs: dict = {"subaccount_id": subaccount_id}
        if market_id:
            kwargs["market_ids"] = [market_id]

        raw = await self.indexer_client.fetch_derivative_orders(**kwargs)
        print(raw)
        orders = []
        for o in raw.get("orders", []):
            mid = o.get("marketId", "")
            orders.append(
                {
                    "order_hash": o.get("orderHash", ""),
                    "market_id": mid,
                    "order_type": o.get("orderType", ""),
                    "order_side": o.get("orderSide", ""),
                    "price": self._convert_deriv_price(o.get("price", ""), mid),
                    "quantity": o.get("quantity", ""),
                    "margin": self._convert_deriv_price(o.get("margin", ""), mid),
                    "unfilled_quantity": o.get("unfilledQuantity", ""),
                    "state": o.get("state", ""),
                    "is_conditional": o.get("isConditional", False),
                    "created_at": o.get("createdAt", ""),
                }
            )
        return {"count": len(orders), "orders": orders}

    async def get_positions(
        self,
        market_id: str | None = None,
        subaccount_index: int = 1,
    ) -> dict:
        """Get open perpetual positions."""
        require_wallet(self.address)
        subaccount_id = self._subaccount_id(subaccount_index)

        kwargs: dict = {"subaccount_id": subaccount_id}
        if market_id:
            kwargs["market_ids"] = [market_id]

        raw = await self.indexer_client.fetch_derivative_positions_v2(**kwargs)
        print(raw)
        positions = []
        for p in raw.get("positions", []):
            mid = p.get("marketId", "")
            positions.append(
                {
                    "market_id": mid,
                    "ticker": p.get("ticker", ""),
                    "direction": p.get("direction", ""),
                    "quantity": p.get("quantity", ""),
                    "entry_price": self._convert_deriv_price(
                        p.get("entryPrice", ""), mid
                    ),
                    "mark_price": self._convert_deriv_price(
                        p.get("markPrice", ""), mid
                    ),
                    "margin": self._convert_deriv_price(p.get("margin", ""), mid),
                    "aggregate_reduce_only_quantity": p.get(
                        "aggregateReduceOnlyQuantity", ""
                    ),
                    "updated_at": p.get("updatedAt", ""),
                }
            )
        return {"count": len(positions), "positions": positions}

    async def close_position(
        self,
        market_id: str,
        quantity: float | None = None,
        price: float | None = None,
    ) -> dict:
        """Close an open position with a reduce-only market order."""
        require_wallet(self.address)
        subaccount_id = self._subaccount_id(1)

        # Find the current position
        raw = await self.indexer_client.fetch_derivative_positions_v2(
            subaccount_id=subaccount_id,
            market_ids=[market_id],
        )
        positions = raw.get("positions", [])
        if not positions:
            raise ValueError(f"No open position found for market {market_id}")

        pos = positions[0]
        pos_direction = pos.get("direction", "").lower()
        pos_quantity = pos.get("quantity", "0")

        # Determine close side (opposite of position direction)
        if pos_direction == "long":
            close_side = "SELL"
        elif pos_direction == "short":
            close_side = "BUY"
        else:
            raise ValueError(f"Unknown position direction: {pos_direction}")

        dec_quantity = Decimal(str(quantity)) if quantity else Decimal(pos_quantity)

        # If no price given, use orderbook with 5% slippage
        if price is None:
            ob = await self.indexer_client.fetch_derivative_orderbook_v2(
                market_id=market_id,
                depth=1,
            )
            if close_side == "SELL":
                bids = ob.get("buys", [])
                if not bids:
                    raise ValueError(
                        "No bids in orderbook — cannot determine close price"
                    )
                best_bid = Decimal(bids[0].get("price", "0"))
                dec_price = best_bid * Decimal("0.95")
            else:
                asks = ob.get("sells", [])
                if not asks:
                    raise ValueError(
                        "No asks in orderbook — cannot determine close price"
                    )
                best_ask = Decimal(asks[0].get("price", "0"))
                dec_price = best_ask * Decimal("1.05")
        else:
            dec_price = Decimal(str(price))

        margin = self.composer.calculate_margin(
            quantity=dec_quantity,
            price=dec_price,
            leverage=Decimal("1"),
            is_reduce_only=True,
        )

        cid = str(uuid4())
        msg = self.composer.msg_create_derivative_market_order(
            market_id=market_id,
            sender=self.acc_address,
            subaccount_id=subaccount_id,
            fee_recipient=self.acc_address,
            price=dec_price,
            quantity=dec_quantity,
            margin=margin,
            order_type=close_side,
            cid=cid,
        )

        result = await self.broadcaster.broadcast([msg])
        return {
            "closed": True,
            "position_direction": pos_direction,
            "close_side": close_side.lower(),
            "quantity": str(dec_quantity),
            "price": self._convert_deriv_price(str(dec_price), market_id),
            "market_id": market_id,
            "cid": cid,
            "tx_hash": getattr(result, "txhash", str(result)),
        }
