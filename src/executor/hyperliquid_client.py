"""
Hyperliquid Client - Exchange API Integration

Handles all Hyperliquid API interactions with dry-run support.

CRITICAL:
- dry_run=True: NO real orders placed (for testing)
- dry_run=False: Real orders (production only)
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import time

logger = logging.getLogger(__name__)


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
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class HyperliquidClient:
    """
    Hyperliquid API client with dry-run support

    Handles:
    - Order placement (market orders)
    - Position management
    - Subaccount switching
    - Account state queries

    CRITICAL: In dry_run mode, NO real API calls are made
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
            config: Configuration dict (from executor config)
            private_key: Hyperliquid private key (required for live)
            vault_address: Hyperliquid vault address (required for live)
            dry_run: If True, simulate all operations (SAFE)

        Raises:
            ValueError: If live mode without credentials or in test environment
        """
        # Handle both config dict and direct parameters
        if config is not None:
            # CRITICAL: No fallback defaults - config must be complete
            # If dry_run is not in config, crash immediately
            try:
                self.dry_run = config['development']['testing']['dry_run']
            except KeyError:
                # Fallback for test configs that may not have nested structure
                self.dry_run = config['dry_run']

            # Get hyperliquid config (will crash if missing)
            hl_config = config['hyperliquid']
            self.testnet = hl_config.get('testnet', True)  # Testnet OK to default True for safety
            self.private_key = hl_config.get('private_key') or private_key
            self.vault_address = hl_config.get('vault_address') or vault_address
        else:
            self.dry_run = dry_run
            self.testnet = True
            self.private_key = private_key
            self.vault_address = vault_address

        self.current_subaccount = 1

        # Dry-run state (simulated)
        self._mock_orders: List[Order] = []
        self._mock_positions: Dict[str, Position] = {}
        self._mock_balance: float = 10000.0  # $10k starting balance
        self._order_counter = 0

        # CRITICAL: Block live trading in test environment
        if not self.dry_run:
            raise ValueError("Live trading not allowed in tests")

        logger.info("Dry-run mode enabled - No real orders will be placed")

    def __str__(self) -> str:
        """String representation for debugging"""
        mode = "DRY RUN" if self.dry_run else "LIVE"
        return f"HyperliquidClient(mode={mode}, subaccount={self.current_subaccount})"

    def __repr__(self) -> str:
        """String representation for debugging"""
        return self.__str__()

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

        if self.dry_run:
            logger.debug(f"[DRY RUN] Switched to subaccount {subaccount_id}")
            self.current_subaccount = subaccount_id
            return True
        else:
            # TODO: Real subaccount switch via Hyperliquid SDK
            logger.info(f"Switched to subaccount {subaccount_id}")
            self.current_subaccount = subaccount_id
            return True

    def _simulate_order(
        self,
        symbol: str,
        side: str,
        size: float,
        order_type: str = 'market',
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict:
        """
        Simulate order execution (dry-run only)

        Args:
            symbol: Trading pair
            side: 'long' or 'short'
            size: Position size
            order_type: Order type (market/limit)
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            Dict with execution details
        """
        # Get mock price (in production, would use real market data)
        fill_price = self.get_current_price(symbol)

        # Simulate slippage (0.02%)
        slippage = 0.0002
        if side == 'long':
            fill_price *= (1 + slippage)
        else:
            fill_price *= (1 - slippage)

        # Calculate fee (0.045% taker fee)
        fee = size * fill_price * 0.00045

        self._order_counter += 1
        order_id = f"mock_order_{self._order_counter}"

        return {
            'order_id': order_id,
            'fill_price': fill_price,
            'size': size,
            'fee': fee,
            'simulated': True
        }

    def place_market_order(
        self,
        symbol: str,
        side: str,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Order:
        """
        Place market order

        Args:
            symbol: Trading pair (e.g., 'BTC')
            side: 'long' or 'short'
            size: Position size
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)

        Returns:
            Order object with execution details

        Raises:
            ValueError: If invalid parameters
        """
        if side not in ['long', 'short']:
            raise ValueError(f"Invalid side: {side}. Must be 'long' or 'short'")

        if size <= 0:
            raise ValueError(f"Invalid size: {size}. Must be positive")

        if self.dry_run:
            # Simulate order execution
            execution = self._simulate_order(symbol, side, size, 'market', stop_loss, take_profit)

            order = Order(
                order_id=execution['order_id'],
                symbol=symbol,
                side=side,
                size=size,
                entry_price=execution['fill_price'],
                stop_loss=stop_loss,
                take_profit=take_profit,
                status=OrderStatus.FILLED,
                timestamp=time.time()
            )

            self._mock_orders.append(order)

            # Create mock position
            self._mock_positions[symbol] = Position(
                symbol=symbol,
                side=side,
                size=size,
                entry_price=order.entry_price,
                current_price=order.entry_price,
                unrealized_pnl=0.0,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            logger.info(
                f"[DRY RUN] Placed market order: {symbol} {side} {size} @ {order.entry_price}"
            )

            return order
        else:
            # TODO: Real order placement via Hyperliquid SDK
            logger.warning(
                f"[LIVE] Placing real order: {symbol} {side} {size}"
            )
            # Placeholder - integrate real Hyperliquid SDK here
            raise NotImplementedError("Live trading not yet implemented")

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
        Place order (generic interface for tests)

        Args:
            symbol: Trading pair
            side: 'long' or 'short' (or 'buy'/'sell')
            size: Position size
            order_type: Order type
            dry_run: Override dry-run setting (must be True in test mode)
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            Dict with execution details

        Raises:
            ValueError: If attempting live trading when dry_run is enforced
        """
        # Normalize side
        if side == 'buy':
            side = 'long'
        elif side == 'sell':
            side = 'short'

        # Check dry_run override
        effective_dry_run = dry_run if dry_run is not None else self.dry_run

        # CRITICAL: Block live trading
        if not effective_dry_run:
            raise ValueError("Live trading disabled")

        order = self.place_market_order(symbol, side, size, stop_loss, take_profit)

        return {
            'status': 'simulated',
            'order_id': order.order_id,
            'symbol': symbol,
            'fill_price': order.entry_price,
            'size': order.size,
            'side': order.side,
            'fee': size * order.entry_price * 0.00045,
            'simulated': True
        }

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
        if self.dry_run:
            if symbol in self._mock_positions:
                position = self._mock_positions[symbol]
                logger.info(
                    f"[DRY RUN] Closed position {symbol}: {position.side} {position.size} "
                    f"(reason: {reason})"
                )
                del self._mock_positions[symbol]
                return True
            else:
                logger.warning(f"[DRY RUN] No position to close for {symbol}")
                return False
        else:
            # TODO: Real position close via Hyperliquid SDK
            logger.warning(f"[LIVE] Closing position: {symbol}")
            raise NotImplementedError("Live trading not yet implemented")

    def close_all_positions(self) -> int:
        """
        Close all positions on current subaccount

        Returns:
            Number of positions closed
        """
        if self.dry_run:
            count = len(self._mock_positions)
            logger.info(
                f"[DRY RUN] Closing all {count} positions on subaccount {self.current_subaccount}"
            )
            self._mock_positions.clear()
            return count
        else:
            # TODO: Real close all via Hyperliquid SDK
            logger.warning(f"[LIVE] Closing all positions on subaccount {self.current_subaccount}")
            raise NotImplementedError("Live trading not yet implemented")

    def cancel_all_orders(self) -> int:
        """
        Cancel all pending orders on current subaccount

        Returns:
            Number of orders cancelled
        """
        if self.dry_run:
            pending_orders = [
                o for o in self._mock_orders
                if o.status == OrderStatus.PENDING
            ]
            count = len(pending_orders)

            for order in pending_orders:
                order.status = OrderStatus.CANCELLED

            logger.info(
                f"[DRY RUN] Cancelled {count} pending orders on subaccount {self.current_subaccount}"
            )
            return count
        else:
            # TODO: Real cancel all via Hyperliquid SDK
            logger.warning(
                f"[LIVE] Cancelling all orders on subaccount {self.current_subaccount}"
            )
            raise NotImplementedError("Live trading not yet implemented")

    def get_positions(self) -> List[Position]:
        """
        Get all open positions on current subaccount

        Returns:
            List of Position objects
        """
        if self.dry_run:
            positions = list(self._mock_positions.values())
            logger.debug(f"[DRY RUN] Retrieved {len(positions)} positions")
            return positions
        else:
            # TODO: Real positions query via Hyperliquid SDK
            raise NotImplementedError("Live trading not yet implemented")

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for specific symbol

        Args:
            symbol: Trading pair

        Returns:
            Position object or None if no position
        """
        if self.dry_run:
            return self._mock_positions.get(symbol)
        else:
            # TODO: Real position query via Hyperliquid SDK
            raise NotImplementedError("Live trading not yet implemented")

    def get_account_balance(self) -> float:
        """
        Get account balance for current subaccount

        Returns:
            Balance in USD
        """
        if self.dry_run:
            logger.debug(f"[DRY RUN] Account balance: ${self._mock_balance:.2f}")
            return self._mock_balance
        else:
            # TODO: Real balance query via Hyperliquid SDK
            raise NotImplementedError("Live trading not yet implemented")

    def get_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get orders (optionally filtered by symbol)

        Args:
            symbol: Filter by symbol (optional)

        Returns:
            List of Order objects
        """
        if self.dry_run:
            if symbol:
                orders = [o for o in self._mock_orders if o.symbol == symbol]
            else:
                orders = self._mock_orders

            logger.debug(f"[DRY RUN] Retrieved {len(orders)} orders")
            return orders
        else:
            # TODO: Real orders query via Hyperliquid SDK
            raise NotImplementedError("Live trading not yet implemented")

    def update_stop_loss(
        self,
        symbol: str,
        new_stop_loss: float
    ) -> bool:
        """
        Update stop loss for existing position

        Args:
            symbol: Trading pair
            new_stop_loss: New stop loss price

        Returns:
            True if updated successfully
        """
        if self.dry_run:
            if symbol in self._mock_positions:
                self._mock_positions[symbol].stop_loss = new_stop_loss
                logger.info(
                    f"[DRY RUN] Updated stop loss for {symbol}: {new_stop_loss}"
                )
                return True
            else:
                logger.warning(f"[DRY RUN] No position found for {symbol}")
                return False
        else:
            # TODO: Real SL update via Hyperliquid SDK
            raise NotImplementedError("Live trading not yet implemented")

    def update_take_profit(
        self,
        symbol: str,
        new_take_profit: float
    ) -> bool:
        """
        Update take profit for existing position

        Args:
            symbol: Trading pair
            new_take_profit: New take profit price

        Returns:
            True if updated successfully
        """
        if self.dry_run:
            if symbol in self._mock_positions:
                self._mock_positions[symbol].take_profit = new_take_profit
                logger.info(
                    f"[DRY RUN] Updated take profit for {symbol}: {new_take_profit}"
                )
                return True
            else:
                logger.warning(f"[DRY RUN] No position found for {symbol}")
                return False
        else:
            # TODO: Real TP update via Hyperliquid SDK
            raise NotImplementedError("Live trading not yet implemented")

    def get_current_price(self, symbol: str) -> float:
        """
        Get current market price for symbol

        Args:
            symbol: Trading pair

        Returns:
            Current price
        """
        if self.dry_run:
            # Mock price (in real implementation, would fetch from WebSocket cache)
            return 42000.0
        else:
            # TODO: Real price fetch via Hyperliquid SDK or WebSocket
            raise NotImplementedError("Live trading not yet implemented")

    def get_account_state(self, address: str) -> Dict[str, Any]:
        """
        Get account state from Hyperliquid

        Args:
            address: Account address

        Returns:
            Account state dict with marginSummary and assetPositions
        """
        if self.dry_run:
            # Return mock account state
            positions = []
            for symbol, pos in self._mock_positions.items():
                positions.append({
                    'position': {
                        'coin': pos.symbol,
                        'entryPx': str(pos.entry_price),
                        'leverage': {
                            'value': 5,
                            'type': 'cross'
                        },
                        'liquidationPx': '0.0',
                        'marginUsed': str(pos.size * pos.entry_price / 5),
                        'positionValue': str(pos.size * pos.entry_price),
                        'returnOnEquity': '0.0',
                        'szi': str(pos.size),
                        'unrealizedPnl': str(pos.unrealized_pnl)
                    },
                    'type': 'oneWay'
                })

            return {
                'marginSummary': {
                    'accountValue': str(self._mock_balance),
                    'totalNtlPos': str(sum(p.size * p.entry_price for p in self._mock_positions.values())),
                    'totalRawUsd': str(self._mock_balance),
                    'withdrawable': str(self._mock_balance * 0.5)
                },
                'assetPositions': positions
            }
        else:
            # TODO: Real account state query
            raise NotImplementedError("Live trading not yet implemented")

    def get_open_positions(self, address: str) -> List[Dict]:
        """
        Get open positions from account state

        Args:
            address: Account address

        Returns:
            List of position dicts
        """
        state = self.get_account_state(address)
        positions = []

        for asset_pos in state.get('assetPositions', []):
            pos = asset_pos.get('position', {})
            positions.append({
                'coin': pos.get('coin'),
                'entryPx': pos.get('entryPx'),
                'szi': pos.get('szi'),
                'unrealizedPnl': pos.get('unrealizedPnl'),
                'positionValue': pos.get('positionValue')
            })

        return positions

    def get_current_prices(self) -> Dict[str, float]:
        """
        Get current prices for all symbols

        Returns:
            Dict mapping symbol to price
        """
        if self.dry_run:
            # Return mock prices
            return {
                'BTC': 50000.0,
                'ETH': 3000.0,
                'SOL': 100.0
            }
        else:
            # TODO: Real price fetch
            raise NotImplementedError("Live trading not yet implemented")

    def health_check(self) -> Dict[str, Any]:
        """
        Check client health status

        Returns:
            Health status dict
        """
        if self.dry_run:
            return {
                'status': 'healthy',
                'dry_run': True,
                'subaccount': self.current_subaccount,
                'positions': len(self._mock_positions),
                'orders': len(self._mock_orders),
                'balance': self._mock_balance
            }
        else:
            # TODO: Real health check
            return {
                'status': 'healthy',
                'dry_run': False,
                'subaccount': self.current_subaccount
            }
