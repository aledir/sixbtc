"""
Position Tracker - Track and Monitor Open Positions

Tracks all open positions across subaccounts and manages position lifecycle.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TrackedPosition:
    """
    Tracked position with lifecycle metadata

    Extends basic Position with tracking data
    """
    # Core position data
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float

    # Risk management
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    atr_stop_multiplier: float = 2.0
    atr_take_multiplier: float = 3.0

    # Tracking metadata
    subaccount_id: int = 1
    strategy_id: str = ""
    entry_time: Optional[datetime] = None
    last_update: Optional[datetime] = None

    # Performance
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    high_water_mark: float = 0.0
    max_adverse_excursion: float = 0.0

    # Signal metadata
    entry_reason: str = ""
    confidence: float = 1.0

    def __post_init__(self):
        """Initialize timestamps and metrics"""
        if self.entry_time is None:
            self.entry_time = datetime.now()
        self.last_update = datetime.now()
        self.high_water_mark = self.entry_price

    def update_price(self, new_price: float):
        """
        Update current price and recalculate PnL

        Args:
            new_price: New market price
        """
        self.current_price = new_price
        self.last_update = datetime.now()

        # Calculate PnL
        if self.side == 'long':
            pnl_pct = (new_price - self.entry_price) / self.entry_price
            self.unrealized_pnl = (new_price - self.entry_price) * self.size
        else:  # short
            pnl_pct = (self.entry_price - new_price) / self.entry_price
            self.unrealized_pnl = (self.entry_price - new_price) * self.size

        self.unrealized_pnl_pct = pnl_pct

        # Track high water mark and max adverse excursion
        if self.unrealized_pnl > self.high_water_mark:
            self.high_water_mark = self.unrealized_pnl

        drawdown = self.high_water_mark - self.unrealized_pnl
        if drawdown > self.max_adverse_excursion:
            self.max_adverse_excursion = drawdown

    def check_stop_loss_hit(self) -> bool:
        """Check if stop loss was hit"""
        if self.stop_loss is None:
            return False

        if self.side == 'long':
            return self.current_price <= self.stop_loss
        else:  # short
            return self.current_price >= self.stop_loss

    def check_take_profit_hit(self) -> bool:
        """Check if take profit was hit"""
        if self.take_profit is None:
            return False

        if self.side == 'long':
            return self.current_price >= self.take_profit
        else:  # short
            return self.current_price <= self.take_profit

    def get_holding_time(self) -> float:
        """Get holding time in seconds"""
        if self.entry_time is None:
            return 0.0
        return (datetime.now() - self.entry_time).total_seconds()


class PositionTracker:
    """
    Track all open positions across subaccounts

    Features:
    - Real-time position tracking
    - PnL calculation
    - Stop loss / take profit monitoring
    - Position lifecycle management
    """

    def __init__(self, client=None, dry_run: bool = True, subaccount_id: int = 1):
        """
        Initialize position tracker

        Args:
            client: HyperliquidClient instance (optional for testing)
            dry_run: Dry-run mode flag
            subaccount_id: Default subaccount ID
        """
        self.client = client
        self.dry_run = dry_run
        self.subaccount_id = subaccount_id
        self.positions: Dict[str, TrackedPosition] = {}
        self.closed_positions: List[Dict] = []
        # Key: position_id (e.g., "1_BTC_Strategy_MOM_001")

        logger.info(f"PositionTracker initialized (dry_run={dry_run}, subaccount={subaccount_id})")

    def add_position(
        self,
        subaccount_id: int,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        strategy_id: str = "",
        entry_reason: str = "",
        atr_stop_multiplier: float = 2.0,
        atr_take_multiplier: float = 3.0
    ) -> TrackedPosition:
        """
        Add new position to tracking

        Args:
            subaccount_id: Subaccount ID (1-10)
            symbol: Trading pair
            side: 'long' or 'short'
            size: Position size
            entry_price: Entry price
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            strategy_id: Strategy identifier
            entry_reason: Entry reason/signal
            atr_stop_multiplier: ATR stop multiplier
            atr_take_multiplier: ATR take profit multiplier

        Returns:
            TrackedPosition object
        """
        # Generate unique position ID
        position_id = f"{subaccount_id}_{symbol}_{strategy_id}" if strategy_id else f"{subaccount_id}_{symbol}"

        position = TrackedPosition(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            subaccount_id=subaccount_id,
            strategy_id=strategy_id,
            entry_reason=entry_reason,
            atr_stop_multiplier=atr_stop_multiplier,
            atr_take_multiplier=atr_take_multiplier
        )

        self.positions[position_id] = position

        logger.info(
            f"Added position: {symbol} {side} {size} @ {entry_price} "
            f"(subaccount {subaccount_id}, strategy {strategy_id}, id {position_id})"
        )

        return position

    def remove_position(
        self,
        subaccount_id: int,
        symbol: str,
        strategy_id: Optional[str] = None
    ) -> Optional[TrackedPosition]:
        """
        Remove position from tracking

        Args:
            subaccount_id: Subaccount ID
            symbol: Trading pair
            strategy_id: Strategy ID (optional, for disambiguation)

        Returns:
            Removed TrackedPosition or None
        """
        # Try with strategy ID first
        if strategy_id:
            position_id = f"{subaccount_id}_{symbol}_{strategy_id}"
            if position_id in self.positions:
                position = self.positions.pop(position_id)
                logger.info(f"Removed position: {position_id}")
                return position

        # Try without strategy ID
        position_id = f"{subaccount_id}_{symbol}"
        if position_id in self.positions:
            position = self.positions.pop(position_id)
            logger.info(f"Removed position: {position_id}")
            return position

        # Search for any position with matching subaccount and symbol
        for pid, position in list(self.positions.items()):
            if position.subaccount_id == subaccount_id and position.symbol == symbol:
                self.positions.pop(pid)
                logger.info(f"Removed position: {pid}")
                return position

        logger.warning(f"Position not found: {symbol} (subaccount {subaccount_id})")
        return None

    def update_position_price(
        self,
        subaccount_id: int,
        symbol: str,
        new_price: float,
        strategy_id: Optional[str] = None
    ) -> bool:
        """
        Update position current price

        Args:
            subaccount_id: Subaccount ID
            symbol: Trading pair
            new_price: New market price
            strategy_id: Strategy ID (optional)

        Returns:
            True if updated successfully
        """
        # Try with strategy ID
        if strategy_id:
            position_id = f"{subaccount_id}_{symbol}_{strategy_id}"
            if position_id in self.positions:
                self.positions[position_id].update_price(new_price)
                return True

        # Try without strategy ID
        position_id = f"{subaccount_id}_{symbol}"
        if position_id in self.positions:
            self.positions[position_id].update_price(new_price)
            return True

        # Search for any matching position
        for pid, position in self.positions.items():
            if position.subaccount_id == subaccount_id and position.symbol == symbol:
                position.update_price(new_price)
                return True

        logger.warning(f"Position not found for update: {symbol} (subaccount {subaccount_id})")
        return False

    def get_position(
        self,
        subaccount_id: int,
        symbol: str,
        strategy_id: Optional[str] = None
    ) -> Optional[TrackedPosition]:
        """Get specific position"""
        # Try with strategy ID first
        if strategy_id:
            position_id = f"{subaccount_id}_{symbol}_{strategy_id}"
            if position_id in self.positions:
                return self.positions[position_id]

        # Try without strategy ID
        position_id = f"{subaccount_id}_{symbol}"
        if position_id in self.positions:
            return self.positions[position_id]

        # Search for any position with matching subaccount and symbol
        for pid, position in self.positions.items():
            if position.subaccount_id == subaccount_id and position.symbol == symbol:
                return position

        return None

    def get_subaccount_positions(
        self,
        subaccount_id: int
    ) -> List[TrackedPosition]:
        """Get all positions for subaccount"""
        return [
            pos for pos in self.positions.values()
            if pos.subaccount_id == subaccount_id
        ]

    def get_all_positions(self) -> List[TrackedPosition]:
        """Get all tracked positions"""
        return list(self.positions.values())

    def get_position_count(self, subaccount_id: Optional[int] = None) -> int:
        """
        Get position count

        Args:
            subaccount_id: Filter by subaccount (optional)

        Returns:
            Number of positions
        """
        if subaccount_id is None:
            return len(self.positions)
        else:
            return len(self.get_subaccount_positions(subaccount_id))

    def check_all_stops(self) -> List[Tuple[int, str, str]]:
        """
        Check all positions for stop loss / take profit hits

        Returns:
            List of (subaccount_id, symbol, reason) tuples for positions to close
        """
        positions_to_close = []

        for position_id, position in self.positions.items():
            if position.check_stop_loss_hit():
                positions_to_close.append((position.subaccount_id, position.symbol, 'stop_loss'))
                logger.info(
                    f"Stop loss hit: {position.symbol} @ {position.current_price} "
                    f"(SL: {position.stop_loss})"
                )

            elif position.check_take_profit_hit():
                positions_to_close.append((position.subaccount_id, position.symbol, 'take_profit'))
                logger.info(
                    f"Take profit hit: {position.symbol} @ {position.current_price} "
                    f"(TP: {position.take_profit})"
                )

        return positions_to_close

    def get_total_unrealized_pnl(
        self,
        subaccount_id: Optional[int] = None
    ) -> float:
        """
        Get total unrealized PnL

        Args:
            subaccount_id: Filter by subaccount (optional)

        Returns:
            Total unrealized PnL
        """
        if subaccount_id is None:
            positions = self.get_all_positions()
        else:
            positions = self.get_subaccount_positions(subaccount_id)

        return sum(p.unrealized_pnl for p in positions)

    def get_strategy_positions(self, strategy_id: str) -> List[TrackedPosition]:
        """Get all positions for specific strategy"""
        return [
            pos for pos in self.positions.values()
            if pos.strategy_id == strategy_id
        ]

    def get_positions_by_strategy(self, strategy_id: str) -> List[Dict]:
        """
        Get all positions for specific strategy (test-compatible interface)

        Args:
            strategy_id: Strategy identifier

        Returns:
            List of position dicts
        """
        positions = self.get_strategy_positions(strategy_id)
        return [
            {
                'id': f"{pos.subaccount_id}_{pos.symbol}",
                'strategy_id': pos.strategy_id,
                'symbol': pos.symbol,
                'side': pos.side,
                'size': pos.size,
                'entry_price': pos.entry_price,
                'current_price': pos.current_price,
                'stop_loss': pos.stop_loss,
                'take_profit': pos.take_profit,
                'unrealized_pnl': pos.unrealized_pnl,
                'status': 'open'
            }
            for pos in positions
        ]

    def sync_with_exchange(self) -> int:
        """
        Sync tracked positions with exchange state

        Queries exchange for actual positions and reconciles with tracked positions.
        Adds missing positions, removes closed positions.

        Returns:
            Number of discrepancies found and corrected
        """
        discrepancies = 0

        # Get positions from exchange for all subaccounts
        for subaccount_id in range(1, 11):
            self.client.switch_subaccount(subaccount_id)
            exchange_positions = self.client.get_positions()

            # Convert to dict for easy lookup
            exchange_symbols = {pos.symbol for pos in exchange_positions}
            tracked_symbols = {
                pos.symbol for pos in self.positions.values()
                if pos.subaccount_id == subaccount_id
            }

            # Find positions on exchange but not tracked
            missing_in_tracker = exchange_symbols - tracked_symbols
            for symbol in missing_in_tracker:
                logger.warning(
                    f"Position {symbol} on exchange but not tracked (subaccount {subaccount_id})"
                )
                discrepancies += 1
                # TODO: Add position to tracker

            # Find positions tracked but not on exchange
            missing_on_exchange = tracked_symbols - exchange_symbols
            for symbol in missing_on_exchange:
                logger.warning(
                    f"Position {symbol} tracked but not on exchange (subaccount {subaccount_id})"
                )
                discrepancies += 1
                self.remove_position(subaccount_id, symbol)

        if discrepancies > 0:
            logger.warning(f"Found {discrepancies} discrepancies during sync")
        else:
            logger.debug("Position tracker in sync with exchange")

        return discrepancies

    def get_summary(self) -> Dict:
        """
        Get summary statistics

        Returns:
            Dict with summary stats
        """
        positions = self.get_all_positions()

        if not positions:
            return {
                'total_positions': 0,
                'total_unrealized_pnl': 0.0,
                'long_positions': 0,
                'short_positions': 0,
                'subaccounts_with_positions': 0
            }

        subaccounts_with_positions = len(set(p.subaccount_id for p in positions))

        return {
            'total_positions': len(positions),
            'total_unrealized_pnl': sum(p.unrealized_pnl for p in positions),
            'long_positions': sum(1 for p in positions if p.side == 'long'),
            'short_positions': sum(1 for p in positions if p.side == 'short'),
            'subaccounts_with_positions': subaccounts_with_positions,
            'avg_pnl_pct': sum(p.unrealized_pnl_pct for p in positions) / len(positions),
            'best_performer': max(positions, key=lambda p: p.unrealized_pnl_pct).symbol,
            'worst_performer': min(positions, key=lambda p: p.unrealized_pnl_pct).symbol
        }

    def open_position(
        self,
        strategy_id: str,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ) -> Dict:
        """
        Open new position (test-compatible interface)

        Args:
            strategy_id: Strategy identifier
            symbol: Trading pair
            side: 'long' or 'short'
            size: Position size
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            Position dict

        Raises:
            ValueError: If invalid parameters
        """
        if size <= 0:
            raise ValueError("size must be positive")

        if entry_price <= 0:
            raise ValueError("price must be positive")

        position = self.add_position(
            subaccount_id=self.subaccount_id,
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_id=strategy_id
        )

        # Generate position ID matching internal format
        position_id = f"{self.subaccount_id}_{symbol}_{strategy_id}" if strategy_id else f"{self.subaccount_id}_{symbol}"

        return {
            'id': position_id,
            'strategy_id': strategy_id,
            'symbol': position.symbol,
            'side': position.side,
            'size': position.size,
            'entry_price': position.entry_price,
            'stop_loss': position.stop_loss,
            'take_profit': position.take_profit,
            'status': 'open',
            'entry_time': position.entry_time
        }

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = 'manual'
    ) -> Dict:
        """
        Close position (test-compatible interface)

        Args:
            position_id: Position identifier (format: subaccount_symbol)
            exit_price: Exit price
            reason: Close reason (optional)

        Returns:
            Closed position dict with PnL
        """
        # Get position directly by ID
        if position_id not in self.positions:
            # Try parsing old format
            parts = position_id.split('_')
            if len(parts) >= 2:
                subaccount_id = int(parts[0])
                symbol = '_'.join(parts[1:])
                position = self.remove_position(subaccount_id, symbol)
            else:
                raise ValueError(f"Position not found: {position_id}")
        else:
            position = self.positions.pop(position_id)

        if position is None:
            raise ValueError(f"Position not found: {position_id}")

        # Calculate final PnL
        position.update_price(exit_price)
        pnl = self.calculate_pnl(
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            size=position.size
        )

        closed = {
            'id': position_id,
            'symbol': position.symbol,
            'side': position.side,
            'size': position.size,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'entry_time': position.entry_time,
            'exit_time': datetime.now(),
            'exit_reason': reason,
            'status': 'closed',
            'pnl': pnl
        }

        self.closed_positions.append(closed)

        return closed

    def calculate_pnl(
        self,
        side: Optional[str] = None,
        entry_price: Optional[float] = None,
        exit_price: Optional[float] = None,
        size: Optional[float] = None,
        position: Optional[Dict] = None,
        current_price: Optional[float] = None
    ) -> float:
        """
        Calculate PnL for position

        Args:
            side: Position side ('long' or 'short')
            entry_price: Entry price
            exit_price: Exit price
            size: Position size
            position: Position dict (alternative parameter form)
            current_price: Current price (alternative to exit_price)

        Returns:
            PnL in USD
        """
        # Handle dict form
        if position is not None:
            side = position.get('side')
            entry_price = position.get('entry_price')
            size = position.get('size')
            exit_price = current_price or exit_price

        # Use current_price if exit_price not provided
        if exit_price is None:
            exit_price = current_price

        # Validate required parameters
        if side is None or entry_price is None or exit_price is None or size is None:
            logger.error(
                f"Missing required parameters for PnL calculation: "
                f"side={side}, entry={entry_price}, exit={exit_price}, size={size}"
            )
            return 0.0

        # Calculate PnL
        if side == 'long':
            return (exit_price - entry_price) * size
        else:  # short
            return (entry_price - exit_price) * size

    def get_open_positions_count(self) -> int:
        """
        Get count of open positions

        Returns:
            Number of open positions
        """
        return len(self.positions)

    def get_statistics(self) -> Dict:
        """
        Get trading statistics

        Returns:
            Dict with statistics
        """
        import numpy as np

        if not self.closed_positions:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0
            }

        winning = [p for p in self.closed_positions if p['pnl'] > 0]
        losing = [p for p in self.closed_positions if p['pnl'] <= 0]

        return {
            'total_trades': len(self.closed_positions),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': len(winning) / len(self.closed_positions) if self.closed_positions else 0,
            'total_pnl': sum(p['pnl'] for p in self.closed_positions),
            'avg_win': float(np.mean([p['pnl'] for p in winning])) if winning else 0.0,
            'avg_loss': float(np.mean([p['pnl'] for p in losing])) if losing else 0.0
        }

    def export_statistics(self) -> Dict:
        """
        Export statistics with dry_run flag

        Returns:
            Statistics dict with dry_run flag
        """
        stats = self.get_statistics()
        stats['dry_run'] = self.dry_run
        return stats
