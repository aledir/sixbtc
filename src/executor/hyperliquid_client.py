"""
Hyperliquid Client - Exchange API Integration

Real Hyperliquid SDK implementation for live trading.
Based on sevenbtc's production-tested implementation.

CRITICAL:
- dry_run=True: Log operations without executing (NO fake state)
- dry_run=False: Real orders (production)
"""

import os
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import ccxt
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

from src.utils.logger import get_logger

logger = get_logger(__name__)


class OrderStatus(Enum):
    """Order status enum"""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Order data structure"""
    order_id: str
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    timestamp: float = 0.0


@dataclass
class Position:
    """Position data structure"""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    leverage: int = 1
    liquidation_price: Optional[float] = None
    margin_used: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class HyperliquidClient:
    """
    Hyperliquid API client with real SDK integration

    Features:
    - Market data fetching (OHLCV, tickers, prices)
    - Account state queries (balance, positions)
    - Order execution (market orders)
    - Position management

    dry_run mode: Logs operations without executing
    """

    def __init__(
        self,
        config: Optional[Dict] = None,
        private_key: Optional[str] = None,
        vault_address: Optional[str] = None,
        dry_run: bool = True
    ):
        """
        Initialize Hyperliquid client

        Args:
            config: Configuration dict
            private_key: Hyperliquid private key (or from env/config)
            vault_address: Hyperliquid wallet address (or from env/config)
            dry_run: If True, log operations without executing

        Raises:
            ValueError: If live mode without valid credentials
        """
        # Determine dry_run mode
        if dry_run is not None:
            self.dry_run = dry_run
        elif config is not None:
            try:
                self.dry_run = config['development']['testing']['dry_run']
            except KeyError:
                try:
                    self.dry_run = config.get('dry_run', True)
                except (KeyError, TypeError):
                    self.dry_run = True
        else:
            self.dry_run = True

        # Get credentials from config, params, or environment
        if config is not None:
            hl_config = config.get('hyperliquid', {})
            self.private_key = private_key or hl_config.get('private_key') or os.getenv('HYPERLIQUID_PRIVATE_KEY')
            self.wallet_address = vault_address or hl_config.get('vault_address') or hl_config.get('wallet_address') or os.getenv('HYPERLIQUID_WALLET_ADDRESS')
            self.testnet = hl_config.get('testnet', False)
        else:
            self.private_key = private_key or os.getenv('HYPERLIQUID_PRIVATE_KEY')
            self.wallet_address = vault_address or os.getenv('HYPERLIQUID_WALLET_ADDRESS')
            self.testnet = False

        self.current_subaccount = 1

        # Initialize Info client (read-only, always available)
        api_url = constants.TESTNET_API_URL if self.testnet else constants.MAINNET_API_URL
        self.info = Info(api_url, skip_ws=True)

        # Initialize Exchange client for trading (only if credentials provided)
        self.exchange_client = None
        if self.private_key and self.wallet_address:
            try:
                account = Account.from_key(self.private_key)
                self.exchange_client = Exchange(account, api_url)
                wallet_display = f"{self.wallet_address[:6]}...{self.wallet_address[-4:]}"
                logger.info(f"Hyperliquid Exchange client initialized: {wallet_display}")
            except Exception as e:
                logger.error(f"Failed to initialize Exchange client: {e}")
                self.exchange_client = None

        # Initialize CCXT client for market data
        self.ccxt_client = ccxt.hyperliquid({
            "enableRateLimit": True,
            "timeout": 30000,
            "rateLimit": 200,
        })

        # Cache for asset metadata
        self._asset_meta_cache: Dict[str, Dict] = {}
        self._last_request_time = 0
        self._load_asset_metadata()

        # Validate live mode credentials
        if not self.dry_run:
            if not self.private_key or not self.wallet_address:
                raise ValueError("Live trading requires valid private_key and wallet_address")
            if not self.exchange_client:
                raise ValueError("Live trading requires Exchange client initialization")
            logger.warning("LIVE TRADING MODE - Real orders will be placed!")
        else:
            logger.info("Dry-run mode enabled - Operations will be logged only")

    def _load_asset_metadata(self):
        """Load asset metadata (sz_decimals, max leverage) from Hyperliquid"""
        try:
            meta = self.info.meta()
            for asset in meta.get("universe", []):
                symbol = asset.get("name")
                self._asset_meta_cache[symbol] = {
                    "sz_decimals": asset.get("szDecimals", 5),
                    "max_leverage": asset.get("maxLeverage", 20),
                }
            logger.info(f"Loaded metadata for {len(self._asset_meta_cache)} assets")
        except Exception as e:
            logger.error(f"Failed to load asset metadata: {e}")

    def _wait_rate_limit(self, min_interval: float = 0.2):
        """Wait for rate limit compliance"""
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    def get_sz_decimals(self, symbol: str) -> int:
        """Get size decimals for an asset"""
        base_coin = symbol.split("/")[0].split("-")[0]
        if base_coin not in self._asset_meta_cache:
            self._load_asset_metadata()
        return self._asset_meta_cache.get(base_coin, {}).get("sz_decimals", 5)

    def get_max_leverage(self, symbol: str) -> int:
        """Get maximum leverage for an asset"""
        base_coin = symbol.split("/")[0].split("-")[0]
        if base_coin not in self._asset_meta_cache:
            self._load_asset_metadata()
        return self._asset_meta_cache.get(base_coin, {}).get("max_leverage", 20)

    def round_size(self, symbol: str, size: float) -> float:
        """Round order size to asset's sz_decimals precision"""
        sz_decimals = self.get_sz_decimals(symbol)
        return round(size, sz_decimals)

    def round_price(self, price: float) -> float:
        """Round price to appropriate tick size based on price level"""
        if price >= 10000:
            return round(price, 1)
        elif price >= 1000:
            return round(price, 2)
        elif price >= 100:
            return round(price, 3)
        elif price >= 10:
            return round(price, 4)
        elif price >= 1:
            return round(price, 5)
        else:
            return round(price, 6)

    def switch_subaccount(self, subaccount_id: int) -> bool:
        """
        Switch to specified subaccount

        Args:
            subaccount_id: Target subaccount (1-10)

        Returns:
            True if switched successfully
        """
        if not 1 <= subaccount_id <= 10:
            logger.error(f"Invalid subaccount_id: {subaccount_id}")
            return False

        self.current_subaccount = subaccount_id
        logger.info(f"Switched to subaccount {subaccount_id}")
        return True

    def get_current_price(self, symbol: str) -> float:
        """
        Get current market price for symbol

        Args:
            symbol: Trading pair (e.g., 'BTC')

        Returns:
            Current mid price
        """
        try:
            self._wait_rate_limit()
            all_mids = self.info.all_mids()

            # Normalize symbol (BTC, BTC-USDC, BTC/USDC:USDC all → BTC)
            base_symbol = symbol.split("/")[0].split("-")[0]

            if base_symbol in all_mids:
                return float(all_mids[base_symbol])
            else:
                logger.warning(f"Symbol {base_symbol} not found in all_mids")
                return 0.0

        except Exception as e:
            logger.error(f"Failed to get current price for {symbol}: {e}")
            return 0.0

    def get_current_prices(self) -> Dict[str, float]:
        """
        Get current prices for all symbols

        Returns:
            Dict mapping symbol to price
        """
        try:
            self._wait_rate_limit()
            all_mids = self.info.all_mids()
            return {symbol: float(price) for symbol, price in all_mids.items()}
        except Exception as e:
            logger.error(f"Failed to get current prices: {e}")
            return {}

    def get_account_balance(self) -> float:
        """
        Get account balance for current subaccount

        Returns:
            Available balance in USD
        """
        if not self.wallet_address:
            logger.error("No wallet address configured")
            return 0.0

        try:
            self._wait_rate_limit()
            user_state = self.info.user_state(self.wallet_address)
            margin_summary = user_state.get("marginSummary", {})
            account_value = float(margin_summary.get("accountValue", 0))
            return account_value

        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            return 0.0

    def get_account_state(self, address: Optional[str] = None) -> Dict[str, Any]:
        """
        Get full account state from Hyperliquid

        Args:
            address: Account address (uses configured wallet if None)

        Returns:
            Account state dict with marginSummary and assetPositions
        """
        address = address or self.wallet_address
        if not address:
            logger.error("No wallet address configured")
            return {}

        try:
            self._wait_rate_limit()
            return self.info.user_state(address)

        except Exception as e:
            logger.error(f"Failed to get account state: {e}")
            return {}

    def get_positions(self) -> List[Position]:
        """
        Get all open positions on current subaccount

        Returns:
            List of Position objects
        """
        if not self.wallet_address:
            logger.error("No wallet address configured")
            return []

        try:
            self._wait_rate_limit()
            user_state = self.info.user_state(self.wallet_address)

            positions = []
            for asset_pos in user_state.get("assetPositions", []):
                pos_data = asset_pos.get("position", {})

                size_raw = float(pos_data.get("szi", 0))
                if size_raw == 0:
                    continue  # Skip closed positions

                coin = pos_data.get("coin", "")
                entry_price = float(pos_data.get("entryPx", 0))
                unrealized_pnl = float(pos_data.get("unrealizedPnl", 0))

                # Calculate mark price from entry and PnL
                mark_price = entry_price + (unrealized_pnl / abs(size_raw)) if size_raw != 0 else entry_price

                leverage_data = pos_data.get("leverage", {})
                leverage = int(float(leverage_data.get("value", 1))) if isinstance(leverage_data, dict) else 1

                liq_px = pos_data.get("liquidationPx")
                liquidation_price = float(liq_px) if liq_px else None

                margin_used = float(pos_data.get("marginUsed", 0))

                positions.append(Position(
                    symbol=coin,
                    side="long" if size_raw > 0 else "short",
                    size=abs(size_raw),
                    entry_price=entry_price,
                    current_price=mark_price,
                    unrealized_pnl=unrealized_pnl,
                    leverage=leverage,
                    liquidation_price=liquidation_price,
                    margin_used=margin_used
                ))

            logger.debug(f"Retrieved {len(positions)} positions")
            return positions

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for specific symbol

        Args:
            symbol: Trading pair

        Returns:
            Position object or None if no position
        """
        base_symbol = symbol.split("/")[0].split("-")[0]
        positions = self.get_positions()

        for pos in positions:
            if pos.symbol == base_symbol:
                return pos

        return None

    def get_open_positions(self, address: Optional[str] = None) -> List[Dict]:
        """
        Get open positions as list of dicts

        Args:
            address: Account address (uses configured wallet if None)

        Returns:
            List of position dicts
        """
        positions = self.get_positions()
        return [
            {
                'coin': pos.symbol,
                'side': pos.side,
                'szi': pos.size,
                'entryPx': pos.entry_price,
                'unrealizedPnl': pos.unrealized_pnl,
                'positionValue': pos.size * pos.current_price
            }
            for pos in positions
        ]

    def place_market_order(
        self,
        symbol: str,
        side: str,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Optional[Order]:
        """
        Place market order

        Args:
            symbol: Trading pair (e.g., 'BTC')
            side: 'long'/'buy' or 'short'/'sell'
            size: Position size
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)

        Returns:
            Order object with execution details, or None if failed

        Raises:
            ValueError: If invalid parameters
        """
        # Normalize side
        if side == 'buy':
            side = 'long'
        elif side == 'sell':
            side = 'short'

        if side not in ['long', 'short']:
            raise ValueError(f"Invalid side: {side}. Must be 'long' or 'short'")

        if size <= 0:
            raise ValueError(f"Invalid size: {size}. Must be positive")

        # Normalize symbol
        base_symbol = symbol.split("/")[0].split("-")[0]
        rounded_size = self.round_size(base_symbol, size)

        if self.dry_run:
            # Log only, no execution
            current_price = self.get_current_price(base_symbol)
            logger.info(
                f"[DRY RUN] Would place market order: {base_symbol} {side} {rounded_size} "
                f"@ ~${current_price:.2f} (SL={stop_loss}, TP={take_profit})"
            )
            return Order(
                order_id=f"dry_run_{int(time.time())}",
                symbol=base_symbol,
                side=side,
                size=rounded_size,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                status=OrderStatus.FILLED,
                timestamp=time.time()
            )

        if not self.exchange_client:
            logger.error("Exchange client not initialized - cannot place orders")
            return None

        try:
            # Get current market price
            self._wait_rate_limit()
            all_mids = self.info.all_mids()

            if base_symbol not in all_mids:
                logger.error(f"Symbol {base_symbol} not found in market data")
                return None

            current_price = float(all_mids[base_symbol])
            is_buy = (side == 'long')

            # Use aggressive pricing (10% spread) to ensure execution
            if is_buy:
                aggressive_price = current_price * 1.10
            else:
                aggressive_price = current_price * 0.90

            aggressive_price = self.round_price(aggressive_price)

            logger.info(
                f"Placing market order: {base_symbol} {side} {rounded_size} "
                f"(current=${current_price:.2f}, aggressive=${aggressive_price:.2f})"
            )

            result = self.exchange_client.order(
                base_symbol,
                is_buy,
                float(rounded_size),
                aggressive_price,
                {"limit": {"tif": "Ioc"}},
                reduce_only=False,
            )

            if result and result.get("status") == "ok":
                statuses = result.get("response", {}).get("data", {}).get("statuses", [])

                if statuses and len(statuses) > 0:
                    if "error" in statuses[0]:
                        logger.error(f"Order rejected: {statuses[0]['error']}")
                        return None

                    filled_data = statuses[0].get("filled")
                    if filled_data:
                        fill_price = float(filled_data.get("avgPx", aggressive_price))
                        filled_size = float(filled_data.get("totalSz", rounded_size))
                        order_id = str(filled_data.get("oid", -1))

                        logger.info(f"Order #{order_id} filled: {filled_size} @ ${fill_price:.2f}")

                        return Order(
                            order_id=order_id,
                            symbol=base_symbol,
                            side=side,
                            size=filled_size,
                            entry_price=fill_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            status=OrderStatus.FILLED,
                            timestamp=time.time()
                        )

                logger.warning("Order placed but not filled immediately")
                return None

            else:
                logger.error(f"Order placement failed: {result}")
                return None

        except Exception as e:
            logger.error(f"Failed to place market order: {e}", exc_info=True)
            return None

    def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        order_type: str = 'market',
        dry_run: Optional[bool] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict:
        """
        Place order (generic interface)

        Args:
            symbol: Trading pair
            side: 'long'/'short' or 'buy'/'sell'
            size: Position size
            order_type: Order type (currently only 'market' supported)
            dry_run: Override dry-run setting
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            Dict with execution details
        """
        effective_dry_run = dry_run if dry_run is not None else self.dry_run
        original_dry_run = self.dry_run
        self.dry_run = effective_dry_run

        try:
            order = self.place_market_order(symbol, side, size, stop_loss, take_profit)

            if order:
                return {
                    'status': 'ok' if not effective_dry_run else 'simulated',
                    'order_id': order.order_id,
                    'symbol': order.symbol,
                    'fill_price': order.entry_price,
                    'size': order.size,
                    'side': order.side,
                    'simulated': effective_dry_run
                }
            else:
                return {'status': 'error', 'message': 'Order placement failed'}

        finally:
            self.dry_run = original_dry_run

    def close_position(
        self,
        symbol: str,
        reason: str = "Manual close"
    ) -> bool:
        """
        Close position for symbol

        Args:
            symbol: Trading pair to close
            reason: Reason for closing

        Returns:
            True if closed successfully
        """
        base_symbol = symbol.split("/")[0].split("-")[0]
        position = self.get_position(base_symbol)

        if not position:
            logger.warning(f"No position to close for {base_symbol}")
            return False

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would close position {base_symbol}: {position.side} {position.size} "
                f"(reason: {reason})"
            )
            return True

        if not self.exchange_client:
            logger.error("Exchange client not initialized")
            return False

        try:
            # Close by placing opposite order with reduce_only
            is_buy = (position.side == 'short')  # Opposite to close

            # Get current price for aggressive pricing
            self._wait_rate_limit()
            all_mids = self.info.all_mids()
            current_price = float(all_mids.get(base_symbol, 0))

            if is_buy:
                aggressive_price = current_price * 1.10
            else:
                aggressive_price = current_price * 0.90

            aggressive_price = self.round_price(aggressive_price)

            logger.info(f"Closing position: {base_symbol} {position.size} (reason: {reason})")

            result = self.exchange_client.order(
                base_symbol,
                is_buy,
                float(position.size),
                aggressive_price,
                {"limit": {"tif": "Ioc"}},
                reduce_only=True,
            )

            if result and result.get("status") == "ok":
                logger.info(f"Position closed for {base_symbol}")
                return True
            else:
                logger.error(f"Failed to close position: {result}")
                return False

        except Exception as e:
            logger.error(f"Error closing position for {base_symbol}: {e}")
            return False

    def close_all_positions(self) -> int:
        """
        Close all positions on current subaccount

        Returns:
            Number of positions closed
        """
        positions = self.get_positions()

        if not positions:
            logger.info("No positions to close")
            return 0

        closed = 0
        for pos in positions:
            if self.close_position(pos.symbol, "Close all"):
                closed += 1

        logger.info(f"Closed {closed}/{len(positions)} positions")
        return closed

    def cancel_all_orders(self) -> int:
        """
        Cancel all pending orders on current subaccount

        Returns:
            Number of orders cancelled
        """
        if not self.wallet_address:
            logger.error("No wallet address configured")
            return 0

        if self.dry_run:
            logger.info("[DRY RUN] Would cancel all pending orders")
            return 0

        if not self.exchange_client:
            logger.error("Exchange client not initialized")
            return 0

        try:
            self._wait_rate_limit()
            open_orders = self.info.open_orders(self.wallet_address)

            cancelled = 0
            for order in open_orders:
                try:
                    coin = order.get("coin")
                    oid = order.get("oid")
                    if coin and oid:
                        result = self.exchange_client.cancel(coin, int(oid))
                        if result and result.get("status") == "ok":
                            cancelled += 1
                except Exception as e:
                    logger.error(f"Failed to cancel order {order.get('oid')}: {e}")

            logger.info(f"Cancelled {cancelled}/{len(open_orders)} orders")
            return cancelled

        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return 0

    def get_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open orders (optionally filtered by symbol)

        Args:
            symbol: Filter by symbol (optional)

        Returns:
            List of order dicts
        """
        if not self.wallet_address:
            logger.error("No wallet address configured")
            return []

        try:
            self._wait_rate_limit()
            open_orders = self.info.open_orders(self.wallet_address)

            base_symbol = symbol.split("/")[0].split("-")[0] if symbol else None

            orders = []
            for order in open_orders:
                if base_symbol and order.get("coin") != base_symbol:
                    continue

                orders.append({
                    "oid": order.get("oid"),
                    "symbol": order.get("coin"),
                    "side": "buy" if order.get("isBuy") else "sell",
                    "size": float(order.get("sz", 0)),
                    "price": float(order.get("limitPx", 0)),
                })

            logger.debug(f"Retrieved {len(orders)} orders")
            return orders

        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []

    def place_trigger_order(
        self,
        symbol: str,
        side: str,
        size: float,
        trigger_price: float,
        order_type: str = "sl",
        is_market: bool = True,
        reduce_only: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Place a trigger order (Stop Loss or Take Profit)

        Args:
            symbol: Trading pair (e.g., 'BTC')
            side: 'buy' or 'sell' (direction when triggered)
            size: Order size
            trigger_price: Price at which the order triggers
            order_type: 'sl' for Stop Loss or 'tp' for Take Profit
            is_market: If True, execute as market order when triggered
            reduce_only: If True, order can only reduce position (default True for SL/TP)

        Returns:
            Dict with order details or None if failed
        """
        if order_type not in ["sl", "tp"]:
            logger.error(f"Invalid order_type: {order_type}. Must be 'sl' or 'tp'")
            return None

        # Normalize
        base_symbol = symbol.split("/")[0].split("-")[0]
        if side == 'long':
            side = 'buy'
        elif side == 'short':
            side = 'sell'

        rounded_size = self.round_size(base_symbol, size)
        rounded_trigger = self.round_price(trigger_price)
        order_type_str = "Stop Loss" if order_type == "sl" else "Take Profit"

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would place {order_type_str}: {base_symbol} {side} {rounded_size} "
                f"@ trigger ${rounded_trigger:.2f}"
            )
            return {
                "status": "simulated",
                "order_id": f"dry_run_trigger_{int(time.time())}",
                "symbol": base_symbol,
                "trigger_price": rounded_trigger,
                "order_type": order_type,
                "side": side,
                "size": rounded_size,
            }

        if not self.exchange_client:
            logger.error("Exchange client not initialized - cannot place trigger orders")
            return None

        try:
            is_buy = side.lower() in ["buy", "long"]

            # Build trigger order type per Hyperliquid API
            trigger_order_type = {
                "trigger": {
                    "triggerPx": float(rounded_trigger),
                    "isMarket": is_market,
                    "tpsl": order_type,
                }
            }

            # Use trigger price as limit price for market triggers
            limit_price = rounded_trigger

            logger.info(
                f"Placing {order_type_str}: {base_symbol} {side} {rounded_size} "
                f"@ trigger ${rounded_trigger:.2f}"
            )

            self._wait_rate_limit()
            result = self.exchange_client.order(
                base_symbol,
                is_buy,
                float(rounded_size),
                float(limit_price),
                trigger_order_type,
                reduce_only=reduce_only,
            )

            if result and result.get("status") == "ok":
                statuses = result.get("response", {}).get("data", {}).get("statuses", [])

                if statuses and len(statuses) > 0:
                    status_data = statuses[0]

                    # Check for errors
                    if "error" in status_data:
                        logger.error(f"{order_type_str} rejected: {status_data['error']}")
                        return None

                    # Trigger orders are in "resting" state when placed
                    resting_data = status_data.get("resting")
                    if resting_data:
                        order_id = resting_data.get("oid", -1)
                        logger.info(
                            f"{order_type_str} #{order_id} PLACED: {rounded_size} {base_symbol} "
                            f"@ trigger ${rounded_trigger:.2f}"
                        )
                        return {
                            "status": "ok",
                            "order_id": str(order_id),
                            "symbol": base_symbol,
                            "trigger_price": trigger_price,
                            "order_type": order_type,
                            "side": side,
                            "size": rounded_size,
                        }

                    # Rare case: trigger executed immediately
                    filled_data = status_data.get("filled")
                    if filled_data:
                        fill_price = float(filled_data.get("avgPx", trigger_price))
                        order_id = filled_data.get("oid", -1)
                        logger.info(
                            f"{order_type_str} #{order_id} FILLED IMMEDIATELY @ ${fill_price:.2f}"
                        )
                        return {
                            "status": "ok",
                            "order_id": str(order_id),
                            "symbol": base_symbol,
                            "fill_price": fill_price,
                            "filled": True,
                        }

                logger.warning(f"{order_type_str} placed but status unclear")
                return None
            else:
                logger.error(f"{order_type_str} placement failed: {result}")
                return None

        except Exception as e:
            logger.error(f"Failed to place {order_type_str}: {e}", exc_info=True)
            return None

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        Cancel a specific order

        Args:
            symbol: Trading pair
            order_id: Order ID to cancel

        Returns:
            True if cancelled successfully
        """
        base_symbol = symbol.split("/")[0].split("-")[0]

        if self.dry_run:
            logger.info(f"[DRY RUN] Would cancel order {order_id} for {base_symbol}")
            return True

        if not self.exchange_client:
            logger.error("Exchange client not initialized")
            return False

        try:
            self._wait_rate_limit()
            result = self.exchange_client.cancel(base_symbol, int(order_id))

            if result and result.get("status") == "ok":
                # Check for errors inside response
                statuses = result.get("response", {}).get("data", {}).get("statuses", [])
                if statuses and "error" in statuses[0]:
                    logger.error(f"Cancel failed: {statuses[0]['error']}")
                    return False

                logger.info(f"Cancelled order {order_id} for {base_symbol}")
                return True
            else:
                logger.error(f"Cancel failed: {result}")
                return False

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def update_stop_loss(
        self,
        symbol: str,
        new_stop_loss: float,
        old_order_id: Optional[str] = None,
        size: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update stop loss for existing position (cancel old + place new)

        This is the core method for trailing stop implementation.

        Args:
            symbol: Trading pair
            new_stop_loss: New stop loss price
            old_order_id: Existing SL order to cancel (optional)
            size: Position size (required if old_order_id is None)

        Returns:
            New order details or None if failed
        """
        base_symbol = symbol.split("/")[0].split("-")[0]

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would update SL for {base_symbol}: ${new_stop_loss:.2f}"
            )
            return {"status": "simulated", "trigger_price": new_stop_loss}

        # Cancel existing SL if provided
        if old_order_id:
            cancelled = self.cancel_order(base_symbol, old_order_id)
            if not cancelled:
                logger.error(f"Failed to cancel old SL order {old_order_id}")
                return None

        # Get position to determine side and size
        position = self.get_position(base_symbol)
        if not position:
            logger.error(f"No position found for {base_symbol}")
            return None

        # Determine SL order side (opposite of position)
        sl_side = "sell" if position.side == "long" else "buy"
        order_size = size or position.size

        # Place new SL
        return self.place_trigger_order(
            symbol=base_symbol,
            side=sl_side,
            size=order_size,
            trigger_price=new_stop_loss,
            order_type="sl",
            is_market=True,
            reduce_only=True
        )

    def update_take_profit(
        self,
        symbol: str,
        new_take_profit: float,
        old_order_id: Optional[str] = None,
        size: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update take profit for existing position (cancel old + place new)

        Args:
            symbol: Trading pair
            new_take_profit: New take profit price
            old_order_id: Existing TP order to cancel (optional)
            size: Position size (required if old_order_id is None)

        Returns:
            New order details or None if failed
        """
        base_symbol = symbol.split("/")[0].split("-")[0]

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would update TP for {base_symbol}: ${new_take_profit:.2f}"
            )
            return {"status": "simulated", "trigger_price": new_take_profit}

        # Cancel existing TP if provided
        if old_order_id:
            cancelled = self.cancel_order(base_symbol, old_order_id)
            if not cancelled:
                logger.error(f"Failed to cancel old TP order {old_order_id}")
                return None

        # Get position
        position = self.get_position(base_symbol)
        if not position:
            logger.error(f"No position found for {base_symbol}")
            return None

        # Determine TP order side (opposite of position)
        tp_side = "sell" if position.side == "long" else "buy"
        order_size = size or position.size

        # Place new TP
        return self.place_trigger_order(
            symbol=base_symbol,
            side=tp_side,
            size=order_size,
            trigger_price=new_take_profit,
            order_type="tp",
            is_market=True,
            reduce_only=True
        )

    def place_order_with_sl_tp(
        self,
        symbol: str,
        side: str,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Place market order with optional SL and TP orders

        This is the main entry point for opening a position with protection.

        Args:
            symbol: Trading pair
            side: 'long' or 'short'
            size: Position size
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)

        Returns:
            Dict with entry order and SL/TP order details
        """
        base_symbol = symbol.split("/")[0].split("-")[0]
        result = {
            "entry": None,
            "stop_loss": None,
            "take_profit": None,
            "status": "error"
        }

        # 1. Place entry order
        entry_order = self.place_market_order(base_symbol, side, size)
        if not entry_order:
            logger.error(f"Failed to place entry order for {base_symbol}")
            return result

        result["entry"] = {
            "order_id": entry_order.order_id,
            "fill_price": entry_order.entry_price,
            "size": entry_order.size,
            "side": entry_order.side,
        }

        # Determine SL/TP side (opposite of entry)
        sl_tp_side = "sell" if side in ["long", "buy"] else "buy"

        # 2. Place Stop Loss if specified
        if stop_loss:
            sl_order = self.place_trigger_order(
                symbol=base_symbol,
                side=sl_tp_side,
                size=size,
                trigger_price=stop_loss,
                order_type="sl"
            )
            if sl_order:
                result["stop_loss"] = sl_order
            else:
                logger.warning(f"Failed to place SL at ${stop_loss:.2f}")

        # 3. Place Take Profit if specified
        if take_profit:
            tp_order = self.place_trigger_order(
                symbol=base_symbol,
                side=sl_tp_side,
                size=size,
                trigger_price=take_profit,
                order_type="tp"
            )
            if tp_order:
                result["take_profit"] = tp_order
            else:
                logger.warning(f"Failed to place TP at ${take_profit:.2f}")

        result["status"] = "ok"
        return result

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Set leverage for a symbol

        Args:
            symbol: Trading pair
            leverage: Leverage value (1-50x depending on asset)

        Returns:
            True if successful
        """
        base_symbol = symbol.split("/")[0].split("-")[0]
        max_lev = self.get_max_leverage(base_symbol)

        if leverage > max_lev:
            logger.warning(f"Requested leverage {leverage}x exceeds max {max_lev}x for {base_symbol}")
            leverage = max_lev

        if self.dry_run:
            logger.info(f"[DRY RUN] Would set leverage for {base_symbol}: {leverage}x")
            return True

        if not self.exchange_client:
            logger.error("Exchange client not initialized")
            return False

        try:
            result = self.exchange_client.update_leverage(leverage, base_symbol, is_cross=False)

            if result and result.get("status") == "ok":
                logger.info(f"Set leverage for {base_symbol}: {leverage}x")
                return True
            else:
                logger.error(f"Failed to set leverage: {result}")
                return False

        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            return False

    def health_check(self) -> Dict[str, Any]:
        """
        Check client health status

        Returns:
            Health status dict
        """
        try:
            self._wait_rate_limit()
            self.ccxt_client.load_markets()
            status = 'healthy'
        except Exception:
            status = 'unhealthy'

        return {
            'status': status,
            'dry_run': self.dry_run,
            'subaccount': self.current_subaccount,
            'has_exchange_client': self.exchange_client is not None,
            'has_wallet': self.wallet_address is not None,
            'timestamp': datetime.now().isoformat()
        }

    def __str__(self) -> str:
        mode = "DRY RUN" if self.dry_run else "LIVE"
        return f"HyperliquidClient(mode={mode}, subaccount={self.current_subaccount})"

    def __repr__(self) -> str:
        return self.__str__()
