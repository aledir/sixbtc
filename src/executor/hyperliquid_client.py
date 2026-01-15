"""
Hyperliquid Client - Exchange API Integration

Real Hyperliquid SDK implementation for live trading.
Based on sevenbtc's production-tested implementation.

CRITICAL:
- dry_run=True: Log operations without executing (NO fake state)
- dry_run=False: Real orders (production)

Credentials:
- Agent wallet credentials are loaded from database (Credential table)
- Run scripts/setup_hyperliquid.py to initialize credentials

Rule #4b: WebSocket First - IMPERATIVE
- When data_provider is set, ALL data reads use WebSocket (prices, balance, positions)
- REST API is used ONLY for trading operations (place_order, cancel_order, set_leverage)
- REST API is also used for bootstrap/fallback when WebSocket is not available
"""

import os
import time
from dataclasses import dataclass
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional

import ccxt
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

from src.database.connection import get_session
from src.database.models import Credential
from src.utils.logger import get_logger

# Import type hint only to avoid circular import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.data.hyperliquid_websocket import HyperliquidDataProvider

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
        dry_run: bool = True,
        data_provider: Optional['HyperliquidDataProvider'] = None
    ):
        """
        Initialize Hyperliquid client with multi-subaccount support.

        Architecture:
        - SHARED: Info client, CCXT client, asset cache (one instance)
        - PER-SUBACCOUNT: Exchange clients (lazy loading, one per subaccount)
        - DATA PROVIDER: WebSocket data source (Rule #4b: WebSocket First)

        Args:
            config: Configuration dict
            dry_run: If True, log operations without executing
            data_provider: HyperliquidDataProvider for WebSocket data (Rule #4b)

        Raises:
            ValueError: If live mode without valid credentials
        """
        # WebSocket data provider (Rule #4b: WebSocket First)
        # When set, ALL data reads use WebSocket instead of REST
        self.data_provider = data_provider
        # Determine dry_run mode - single source of truth: hyperliquid.dry_run
        if config is not None:
            self.dry_run = config.get('hyperliquid', {}).get('dry_run', dry_run)
            self.testnet = config.get('hyperliquid', {}).get('testnet', False)
        else:
            self.dry_run = dry_run
            self.testnet = False

        # Master address for read-only queries (REQUIRED)
        self.user_address = os.getenv('HL_MASTER_ADDRESS')

        # API URL
        self.api_url = constants.TESTNET_API_URL if self.testnet else constants.MAINNET_API_URL

        # SHARED: Info client (read-only, always available)
        self.info = Info(self.api_url, skip_ws=True)

        # SHARED: CCXT client for market data
        self.ccxt_client = ccxt.hyperliquid({
            "enableRateLimit": True,
            "timeout": 30000,
            "rateLimit": 200,
        })

        # PER-SUBACCOUNT: Exchange clients (lazy loading)
        self._exchange_clients: Dict[int, Exchange] = {}
        self._subaccount_credentials: Dict[int, Dict[str, str]] = {}
        self._load_credentials_from_db()

        # Cache for asset metadata
        self._asset_meta_cache: Dict[str, Dict] = {}
        self._last_request_time = 0
        self._load_asset_metadata()

        # Validate configuration
        if not self.dry_run:
            if not self.user_address:
                raise ValueError("Live trading requires HL_MASTER_ADDRESS in .env")
            if not self._subaccount_credentials:
                raise ValueError(
                    "Live trading requires at least one subaccount with agent wallet. "
                    "Run 'python scripts/setup_hyperliquid.py' to initialize credentials."
                )
            logger.warning("LIVE TRADING MODE - Real orders will be placed!")
        else:
            logger.info("Dry-run mode enabled - Operations will be logged only")

        logger.info(
            f"HyperliquidClient initialized: {self.subaccount_count} subaccounts configured"
        )

    def _load_credentials_from_db(self) -> None:
        """
        Load agent wallet credentials from database.

        Queries the Credential table for active, non-expired agent wallets.
        Each subaccount has one active agent wallet credential.
        """
        try:
            with get_session() as session:
                credentials = session.query(Credential).filter(
                    Credential.is_active == True,
                    Credential.target_type == 'subaccount',
                    Credential.expires_at > datetime.now(UTC)
                ).all()

                for cred in credentials:
                    if cred.subaccount_id is not None:
                        self._subaccount_credentials[cred.subaccount_id] = {
                            'private_key': cred.private_key,
                            'address': cred.target_address,
                            'agent_address': cred.agent_address,
                        }

            if self._subaccount_credentials:
                logger.info(f"Loaded credentials for {len(self._subaccount_credentials)} subaccounts from DB")
            else:
                logger.warning(
                    "No subaccount credentials found in database. "
                    "Run 'python scripts/setup_hyperliquid.py' to initialize."
                )

        except Exception as e:
            logger.error(f"Failed to load credentials from database: {e}")

    def reload_credentials(self) -> int:
        """
        Reload credentials from database.

        Call this after credentials are renewed by the scheduler
        to pick up new agent wallets without restarting.

        Returns:
            Number of credentials loaded
        """
        # Clear existing Exchange clients (they use old credentials)
        old_count = len(self._exchange_clients)
        self._exchange_clients.clear()
        self._subaccount_credentials.clear()

        # Reload from database
        self._load_credentials_from_db()

        if old_count > 0:
            logger.info(
                f"Credentials reloaded: {old_count} Exchange clients cleared, "
                f"{len(self._subaccount_credentials)} credentials loaded"
            )

        return len(self._subaccount_credentials)

    def _get_exchange(self, subaccount_id: int) -> Exchange:
        """
        Get or create Exchange client for a specific subaccount (lazy loading).

        Each subaccount has its own Exchange client with separate nonce tracking.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)

        Returns:
            Exchange client for the subaccount

        Raises:
            ValueError: If subaccount not configured
        """
        if subaccount_id not in self._subaccount_credentials:
            raise ValueError(
                f"Subaccount {subaccount_id} not configured. "
                f"Available: {list(self._subaccount_credentials.keys())}"
            )

        # Lazy create Exchange client on first use
        if subaccount_id not in self._exchange_clients:
            creds = self._subaccount_credentials[subaccount_id]
            account = Account.from_key(creds['private_key'])
            self._exchange_clients[subaccount_id] = Exchange(
                account,
                self.api_url,
                vault_address=creds['address']
            )
            addr_display = f"{creds['address'][:6]}...{creds['address'][-4:]}"
            logger.info(f"Exchange client created for subaccount {subaccount_id}: {addr_display}")

        return self._exchange_clients[subaccount_id]

    def _get_subaccount_address(self, subaccount_id: int) -> str:
        """
        Get address for a specific subaccount (for queries).

        Args:
            subaccount_id: Subaccount number

        Returns:
            Subaccount wallet address

        Raises:
            ValueError: If subaccount not configured (live mode only)
        """
        if subaccount_id not in self._subaccount_credentials:
            # In dry_run mode, return a fake address for testing
            if self.dry_run:
                return '0x' + '0' * 40
            raise ValueError(f"Subaccount {subaccount_id} not configured")
        return self._subaccount_credentials[subaccount_id]['address']

    @property
    def subaccount_count(self) -> int:
        """Number of configured subaccounts"""
        return len(self._subaccount_credentials) or 1  # Minimum 1 for dry_run

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
        """Round price to appropriate tick size based on price level.

        Hyperliquid tick sizes (as of 2024):
        - >= $20,000: tick = 1.0 (integers only)
        - >= $1,000: tick = 0.1
        - >= $100: tick = 0.01
        - >= $1: tick = 0.0001
        - < $1: tick = 0.00001
        """
        if price >= 20000:
            return round(price, 0)  # Integer prices for BTC, etc.
        elif price >= 1000:
            return round(price, 1)
        elif price >= 100:
            return round(price, 2)
        elif price >= 1:
            return round(price, 4)
        else:
            return round(price, 5)

    def get_current_price(self, symbol: str) -> float:
        """
        Get current market price for symbol.

        Rule #4b: WebSocket First - uses data_provider when available.

        Args:
            symbol: Trading pair (e.g., 'BTC')

        Returns:
            Current mid price
        """
        # Normalize symbol (BTC, BTC-USDC, BTC/USDC:USDC all → BTC)
        base_symbol = symbol.split("/")[0].split("-")[0]

        # Rule #4b: WebSocket First
        if self.data_provider:
            price = self.data_provider.get_price_sync(base_symbol)
            if price is not None:
                return price
            # Fallback to REST only if WebSocket has no data
            logger.debug(f"WebSocket has no price for {base_symbol}, falling back to REST")

        # REST fallback (or when data_provider not set)
        try:
            self._wait_rate_limit()
            all_mids = self.info.all_mids()

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
        Get current prices for all symbols.

        Rule #4b: WebSocket First - uses data_provider when available.

        Returns:
            Dict mapping symbol to price
        """
        # Rule #4b: WebSocket First
        if self.data_provider and self.data_provider.mid_prices:
            return {
                coin: mid.price
                for coin, mid in self.data_provider.mid_prices.items()
            }

        # REST fallback (or when data_provider not set)
        try:
            self._wait_rate_limit()
            all_mids = self.info.all_mids()
            return {symbol: float(price) for symbol, price in all_mids.items()}
        except Exception as e:
            logger.error(f"Failed to get current prices: {e}")
            return {}

    def get_account_balance(self, subaccount_id: int) -> float:
        """
        Get account balance for a specific subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)

        Returns:
            Available balance in USD

        Raises:
            ValueError: If subaccount not configured
            RuntimeError: If API call fails (do NOT mask - critical for position sizing)
        """
        try:
            address = self._get_subaccount_address(subaccount_id)
            self._wait_rate_limit()
            user_state = self.info.user_state(address)
            margin_summary = user_state.get("marginSummary", {})
            account_value = float(margin_summary.get("accountValue", 0))
            return account_value

        except ValueError:
            raise  # Re-raise config errors
        except Exception as e:
            # Critical error - do NOT mask with return 0.0 (would break position sizing)
            logger.error(f"Failed to get account balance for subaccount {subaccount_id}: {e}")
            raise RuntimeError(f"Failed to get account balance: {e}") from e

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

    def get_positions(self, subaccount_id: int) -> List[Position]:
        """
        Get all open positions for a specific subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)

        Returns:
            List of Position objects
        """
        try:
            address = self._get_subaccount_address(subaccount_id)
            self._wait_rate_limit()
            user_state = self.info.user_state(address)

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

            logger.debug(f"Retrieved {len(positions)} positions for subaccount {subaccount_id}")
            return positions

        except ValueError:
            raise  # Re-raise config errors
        except Exception as e:
            logger.error(f"Failed to get positions for subaccount {subaccount_id}: {e}")
            return []

    def get_position(self, subaccount_id: int, symbol: str) -> Optional[Position]:
        """
        Get position for specific symbol on a subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
            symbol: Trading pair

        Returns:
            Position object or None if no position
        """
        base_symbol = symbol.split("/")[0].split("-")[0]
        positions = self.get_positions(subaccount_id)

        for pos in positions:
            if pos.symbol == base_symbol:
                return pos

        return None

    def get_open_positions(self, subaccount_id: int) -> List[Dict]:
        """
        Get open positions as list of dicts for a subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)

        Returns:
            List of position dicts
        """
        positions = self.get_positions(subaccount_id)
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
        subaccount_id: int,
        symbol: str,
        side: str,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Optional[Order]:
        """
        Place market order on a specific subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
            symbol: Trading pair (e.g., 'BTC')
            side: 'long'/'buy' or 'short'/'sell'
            size: Position size
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)

        Returns:
            Order object with execution details, or None if failed

        Raises:
            ValueError: If invalid parameters or subaccount not configured
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

        try:
            exchange = self._get_exchange(subaccount_id)
        except ValueError as e:
            logger.error(str(e))
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
                f"[Subaccount {subaccount_id}] Placing market order: {base_symbol} {side} {rounded_size} "
                f"(current=${current_price:.2f}, aggressive=${aggressive_price:.2f})"
            )

            result = exchange.order(
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
        subaccount_id: int,
        symbol: str,
        side: str,
        size: float,
        order_type: str = 'market',
        dry_run: Optional[bool] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict:
        """
        Place order (generic interface) on a specific subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
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
            order = self.place_market_order(subaccount_id, symbol, side, size, stop_loss, take_profit)

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
        subaccount_id: int,
        symbol: str,
        reason: str = "Manual close"
    ) -> bool:
        """
        Close position for symbol on a specific subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
            symbol: Trading pair to close
            reason: Reason for closing

        Returns:
            True if closed successfully
        """
        base_symbol = symbol.split("/")[0].split("-")[0]
        position = self.get_position(subaccount_id, base_symbol)

        if not position:
            logger.warning(f"No position to close for {base_symbol} on subaccount {subaccount_id}")
            return False

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would close position {base_symbol}: {position.side} {position.size} "
                f"(reason: {reason}, subaccount: {subaccount_id})"
            )
            return True

        try:
            exchange = self._get_exchange(subaccount_id)
        except ValueError as e:
            logger.error(str(e))
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

            logger.info(f"[Subaccount {subaccount_id}] Closing position: {base_symbol} {position.size} (reason: {reason})")

            result = exchange.order(
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

    def close_all_positions(self, subaccount_id: int) -> int:
        """
        Close all positions on a specific subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)

        Returns:
            Number of positions closed
        """
        positions = self.get_positions(subaccount_id)

        if not positions:
            logger.info(f"No positions to close on subaccount {subaccount_id}")
            return 0

        closed = 0
        for pos in positions:
            if self.close_position(subaccount_id, pos.symbol, "Close all"):
                closed += 1

        logger.info(f"[Subaccount {subaccount_id}] Closed {closed}/{len(positions)} positions")
        return closed

    def cancel_all_orders(self, subaccount_id: int) -> int:
        """
        Cancel all pending orders on a specific subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)

        Returns:
            Number of orders cancelled
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would cancel all pending orders on subaccount {subaccount_id}")
            return 0

        try:
            address = self._get_subaccount_address(subaccount_id)
            exchange = self._get_exchange(subaccount_id)
        except ValueError as e:
            logger.error(str(e))
            return 0

        try:
            self._wait_rate_limit()
            open_orders = self.info.open_orders(address)

            cancelled = 0
            for order in open_orders:
                try:
                    coin = order.get("coin")
                    oid = order.get("oid")
                    if coin and oid:
                        result = exchange.cancel(coin, int(oid))
                        if result and result.get("status") == "ok":
                            cancelled += 1
                except Exception as e:
                    logger.error(f"Failed to cancel order {order.get('oid')}: {e}")

            logger.info(f"[Subaccount {subaccount_id}] Cancelled {cancelled}/{len(open_orders)} orders")
            return cancelled

        except Exception as e:
            logger.error(f"Failed to cancel all orders on subaccount {subaccount_id}: {e}")
            return 0

    def get_orders(self, subaccount_id: int, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open orders for a subaccount (optionally filtered by symbol).

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
            symbol: Filter by symbol (optional)

        Returns:
            List of order dicts
        """
        try:
            address = self._get_subaccount_address(subaccount_id)
            self._wait_rate_limit()
            open_orders = self.info.open_orders(address)

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
        subaccount_id: int,
        symbol: str,
        side: str,
        size: float,
        trigger_price: float,
        order_type: str = "sl",
        is_market: bool = True,
        reduce_only: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Place a trigger order (Stop Loss or Take Profit) on a subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
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
                f"@ trigger ${rounded_trigger:.2f} (subaccount: {subaccount_id})"
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

        try:
            exchange = self._get_exchange(subaccount_id)
        except ValueError as e:
            logger.error(str(e))
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
                f"[Subaccount {subaccount_id}] Placing {order_type_str}: {base_symbol} {side} {rounded_size} "
                f"@ trigger ${rounded_trigger:.2f}"
            )

            self._wait_rate_limit()
            result = exchange.order(
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

    def cancel_order(self, subaccount_id: int, symbol: str, order_id: str) -> bool:
        """
        Cancel a specific order on a subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
            symbol: Trading pair
            order_id: Order ID to cancel

        Returns:
            True if cancelled successfully
        """
        base_symbol = symbol.split("/")[0].split("-")[0]

        if self.dry_run:
            logger.info(f"[DRY RUN] Would cancel order {order_id} for {base_symbol} on subaccount {subaccount_id}")
            return True

        try:
            exchange = self._get_exchange(subaccount_id)
        except ValueError as e:
            logger.error(str(e))
            return False

        try:
            self._wait_rate_limit()
            result = exchange.cancel(base_symbol, int(order_id))

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
        subaccount_id: int,
        symbol: str,
        new_stop_loss: float,
        old_order_id: Optional[str] = None,
        size: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update stop loss for existing position (cancel old + place new).

        This is the core method for trailing stop implementation.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
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
                f"[DRY RUN] Would update SL for {base_symbol}: ${new_stop_loss:.2f} (subaccount: {subaccount_id})"
            )
            return {"status": "simulated", "trigger_price": new_stop_loss}

        # Cancel existing SL if provided
        if old_order_id:
            cancelled = self.cancel_order(subaccount_id, base_symbol, old_order_id)
            if not cancelled:
                logger.error(f"Failed to cancel old SL order {old_order_id}")
                return None

        # Get position to determine side and size
        position = self.get_position(subaccount_id, base_symbol)
        if not position:
            logger.error(f"No position found for {base_symbol} on subaccount {subaccount_id}")
            return None

        # Determine SL order side (opposite of position)
        sl_side = "sell" if position.side == "long" else "buy"
        order_size = size or position.size

        # Place new SL
        return self.place_trigger_order(
            subaccount_id=subaccount_id,
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
        subaccount_id: int,
        symbol: str,
        new_take_profit: float,
        old_order_id: Optional[str] = None,
        size: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update take profit for existing position (cancel old + place new).

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
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
                f"[DRY RUN] Would update TP for {base_symbol}: ${new_take_profit:.2f} (subaccount: {subaccount_id})"
            )
            return {"status": "simulated", "trigger_price": new_take_profit}

        # Cancel existing TP if provided
        if old_order_id:
            cancelled = self.cancel_order(subaccount_id, base_symbol, old_order_id)
            if not cancelled:
                logger.error(f"Failed to cancel old TP order {old_order_id}")
                return None

        # Get position
        position = self.get_position(subaccount_id, base_symbol)
        if not position:
            logger.error(f"No position found for {base_symbol} on subaccount {subaccount_id}")
            return None

        # Determine TP order side (opposite of position)
        tp_side = "sell" if position.side == "long" else "buy"
        order_size = size or position.size

        # Place new TP
        return self.place_trigger_order(
            subaccount_id=subaccount_id,
            symbol=base_symbol,
            side=tp_side,
            size=order_size,
            trigger_price=new_take_profit,
            order_type="tp",
            is_market=True,
            reduce_only=True
        )

    def update_sl_atomic(
        self,
        subaccount_id: int,
        symbol: str,
        new_stop_loss: float,
        old_order_id: Optional[str] = None,
        size: Optional[float] = None,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Update stop loss using SAFE ATOMIC pattern: place new FIRST, then cancel old.

        This is safer than update_stop_loss because:
        - If new placement fails: old SL still active (position protected)
        - If cancel fails: 2 SLs temporarily (safe, will be cleaned up)
        - Never leaves position unprotected

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
            symbol: Trading pair
            new_stop_loss: New stop loss price
            old_order_id: Existing SL order to cancel (optional)
            size: Position size (required if no position exists)
            max_retries: Max retry attempts for placement

        Returns:
            New order details or None if failed
        """
        base_symbol = symbol.split("/")[0].split("-")[0]

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would atomic update SL for {base_symbol}: ${new_stop_loss:.2f} (subaccount: {subaccount_id})"
            )
            return {"status": "simulated", "trigger_price": new_stop_loss, "order_id": "dry_run"}

        # Get position to determine side and size
        position = self.get_position(subaccount_id, base_symbol)
        if not position:
            logger.error(f"No position found for {base_symbol} on subaccount {subaccount_id}")
            return None

        sl_side = "sell" if position.side == "long" else "buy"
        order_size = size or position.size

        # PHASE 1: Place new SL order FIRST (with retry)
        new_sl_result = None
        for attempt in range(max_retries):
            logger.info(f"[Subaccount {subaccount_id}] Atomic SL update: placing new SL @ ${new_stop_loss:.2f} (attempt {attempt + 1}/{max_retries})")

            new_sl_result = self.place_trigger_order(
                subaccount_id=subaccount_id,
                symbol=base_symbol,
                side=sl_side,
                size=order_size,
                trigger_price=new_stop_loss,
                order_type="sl",
                is_market=True,
                reduce_only=True
            )

            if new_sl_result and new_sl_result.get("order_id"):
                logger.info(f"Atomic SL update: new SL placed successfully, order_id={new_sl_result.get('order_id')}")
                break

            logger.warning(f"Atomic SL update: placement failed, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(1.0)

        if not new_sl_result or not new_sl_result.get("order_id"):
            logger.error(f"Atomic SL update FAILED: could not place new SL after {max_retries} attempts")
            logger.info(f"Old SL {old_order_id} is still active - position remains protected")
            return None

        # PHASE 2: Cancel old SL order (if provided)
        if old_order_id:
            logger.info(f"Atomic SL update: cancelling old SL order {old_order_id}")
            cancelled = self.cancel_order(subaccount_id, base_symbol, old_order_id)

            if not cancelled:
                # Not critical - old SL will trigger if price goes there
                # New SL is already in place, so position is protected
                logger.warning(
                    f"Atomic SL update: failed to cancel old SL {old_order_id}. "
                    f"Position has 2 SL orders temporarily (safe, new SL is active)"
                )
            else:
                logger.info(f"Atomic SL update: old SL {old_order_id} cancelled")

        return new_sl_result

    def place_order_with_sl_tp(
        self,
        subaccount_id: int,
        symbol: str,
        side: str,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Place market order with optional SL and TP orders on a subaccount.

        This is the main entry point for opening a position with protection.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
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
        entry_order = self.place_market_order(subaccount_id, base_symbol, side, size)
        if not entry_order:
            logger.error(f"Failed to place entry order for {base_symbol} on subaccount {subaccount_id}")
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
                subaccount_id=subaccount_id,
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
                subaccount_id=subaccount_id,
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

    def set_leverage(self, subaccount_id: int, symbol: str, leverage: int) -> bool:
        """
        Set leverage for a symbol on a subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
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
            logger.info(f"[DRY RUN] Would set leverage for {base_symbol}: {leverage}x (subaccount: {subaccount_id})")
            return True

        try:
            exchange = self._get_exchange(subaccount_id)
        except ValueError as e:
            logger.error(str(e))
            return False

        try:
            result = exchange.update_leverage(leverage, base_symbol, is_cross=False)

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
            'subaccount_count': self.subaccount_count,
            'configured_subaccounts': list(self._subaccount_credentials.keys()),
            'has_user_address': self.user_address is not None,
            'timestamp': datetime.now().isoformat()
        }

    def emergency_stop_all(self, reason: str) -> None:
        """
        Emergency stop - close all positions and cancel all orders on ALL subaccounts.

        Args:
            reason: Reason for emergency stop (logged)
        """
        logger.critical(f"EMERGENCY STOP: {reason}")

        for subaccount_id in self._subaccount_credentials.keys():
            try:
                logger.info(f"Emergency stop: processing subaccount {subaccount_id}")
                self.cancel_all_orders(subaccount_id)
                self.close_all_positions(subaccount_id)
            except Exception as e:
                logger.error(f"Emergency stop failed for subaccount {subaccount_id}: {e}")

        logger.critical("Emergency stop completed")

    def get_ledger_updates(
        self,
        subaccount_id: int,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get non-funding ledger updates (deposits, withdrawals, transfers) for a subaccount.

        Essential for accurate P&L calculation when user deposits/withdraws funds.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
            start_time: Start timestamp in milliseconds (default: 90 days ago)
            end_time: End timestamp in milliseconds (default: now)

        Returns:
            List of ledger update records with type, amount, direction
        """
        try:
            address = self._get_subaccount_address(subaccount_id)
        except ValueError as e:
            logger.error(str(e))
            return []

        try:
            # Default time range: last 90 days
            now_ms = int(time.time() * 1000)
            if end_time is None:
                end_time = now_ms
            if start_time is None:
                start_time = now_ms - (90 * 24 * 60 * 60 * 1000)  # 90 days

            # Call userNonFundingLedgerUpdates API
            self._wait_rate_limit()
            response = self.info.post("/info", {
                "type": "userNonFundingLedgerUpdates",
                "user": address,
                "startTime": start_time,
                "endTime": end_time
            })

            records = []
            for update in response:
                # Each update has a 'delta' field with the type-specific data
                delta = update.get("delta", {})
                delta_type = delta.get("type", "unknown")
                time_ms = update.get("time", 0)

                record = {
                    "timestamp": time_ms,
                    "datetime": datetime.fromtimestamp(time_ms / 1000, tz=UTC).isoformat() if time_ms else None,
                    "type": delta_type,
                    "hash": update.get("hash", ""),
                }

                # Extract amount based on type
                if delta_type == "deposit":
                    record["amount"] = float(delta.get("usdc", 0))
                    record["direction"] = "in"
                elif delta_type == "withdraw":
                    record["amount"] = float(delta.get("usdc", 0))
                    record["direction"] = "out"
                elif delta_type == "internalTransfer":
                    record["amount"] = float(delta.get("usdc", 0))
                    record["direction"] = "in" if delta.get("isDeposit", False) else "out"
                    record["destination"] = delta.get("destination", "")
                elif delta_type == "subAccountTransfer":
                    record["amount"] = float(delta.get("usdc", 0))
                    record["direction"] = "in" if delta.get("isDeposit", False) else "out"
                elif delta_type == "spotTransfer":
                    record["amount"] = float(delta.get("usdc", 0))
                    record["token"] = delta.get("token", "USDC")
                    record["direction"] = "in" if delta.get("isDeposit", False) else "out"
                elif delta_type == "accountClassTransfer":
                    record["amount"] = float(delta.get("usdc", 0))
                    record["direction"] = "in" if delta.get("isDeposit", False) else "out"
                elif delta_type == "liquidation":
                    record["amount"] = float(delta.get("usdc", 0))
                    record["direction"] = "out"  # Liquidation is always a loss
                    record["liquidated_positions"] = delta.get("leverageType", "")
                else:
                    # Unknown type, try to extract usdc
                    record["amount"] = float(delta.get("usdc", 0)) if "usdc" in delta else 0
                    record["direction"] = "unknown"

                records.append(record)

            # Sort by timestamp
            records.sort(key=lambda x: x["timestamp"])

            # Log summary
            deposits = sum(r["amount"] for r in records if r.get("direction") == "in")
            withdrawals = sum(r["amount"] for r in records if r.get("direction") == "out")
            logger.debug(
                f"Subaccount {subaccount_id} ledger: {len(records)} records, "
                f"deposits=${deposits:.2f}, withdrawals=${withdrawals:.2f}"
            )

            return records

        except Exception as e:
            logger.error(f"Failed to get ledger updates for subaccount {subaccount_id}: {e}")
            return []

    def get_net_deposits(
        self,
        subaccount_id: int,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Calculate net deposits (deposits - withdrawals) for accurate P&L.

        Formula: True P&L = Current Account Value - Net Deposits

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
            start_time: Start timestamp in milliseconds (default: 90 days ago)
            end_time: End timestamp in milliseconds (default: now)

        Returns:
            Dict with total_deposits, total_withdrawals, net_deposits, transaction_count
        """
        ledger = self.get_ledger_updates(subaccount_id, start_time, end_time)

        total_deposits = sum(r["amount"] for r in ledger if r.get("direction") == "in")
        total_withdrawals = sum(r["amount"] for r in ledger if r.get("direction") == "out")

        return {
            "total_deposits": total_deposits,
            "total_withdrawals": total_withdrawals,
            "net_deposits": total_deposits - total_withdrawals,
            "transaction_count": len(ledger),
        }

    def __str__(self) -> str:
        mode = "DRY RUN" if self.dry_run else "LIVE"
        return f"HyperliquidClient(mode={mode}, subaccounts={self.subaccount_count})"

    def __repr__(self) -> str:
        return self.__str__()
