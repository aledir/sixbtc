"""
Trade Sync - Synchronizes closed trades from Hyperliquid to database

When positions are closed on Hyperliquid, this module:
1. Detects closed positions (by comparing with previous iteration)
2. Fetches fills from Hyperliquid API
3. Reconstructs complete trade records
4. Updates Trade table with exit data

This enables the Dual-Ranking system to calculate live performance metrics.

Design:
- Hyperliquid is SOURCE OF TRUTH (CLAUDE.MD Rule #18)
- DB is audit trail only
- Uses WebSocket for position tracking, HTTP for fills
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import UUID

from src.config.loader import load_config
from src.database import get_session
from src.database.models import Trade, Strategy
from src.data.hyperliquid_websocket import (
    HyperliquidDataProvider,
    UserPosition,
    AccountState,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TradeSync:
    """
    Synchronizes closed positions from Hyperliquid to Trade table.

    Approach:
    1. Monitor positions via WebSocket (webData2)
    2. When position disappears -> fetch fills from HTTP API
    3. Reconstruct trade (entry fills + exit fill)
    4. Update existing Trade record (or create new one)

    This is called every Monitor cycle (15 seconds).
    """

    def __init__(
        self,
        config: Optional[Dict] = None,
        data_provider: Optional[HyperliquidDataProvider] = None
    ):
        """
        Initialize TradeSync.

        Args:
            config: Configuration dict (loads from file if None)
            data_provider: WebSocket provider for position data
        """
        self.config = config or load_config()._raw_config
        self.data_provider = data_provider

        # Track positions from last sync cycle
        self._last_positions: Dict[str, Dict] = {}

        # Config
        sync_config = self.config.get('hyperliquid', {}).get('trade_sync', {})
        self.fills_lookback_days = sync_config.get('fills_lookback_days', 7)

        logger.info("TradeSync initialized")

    def set_data_provider(self, provider: HyperliquidDataProvider):
        """Set the data provider (for late initialization)."""
        self.data_provider = provider

    async def sync_cycle(self, iteration: int):
        """
        Run one sync cycle.

        Called every Monitor iteration (15 seconds).

        Args:
            iteration: Current monitor iteration number
        """
        if not self.data_provider:
            logger.warning("TradeSync: no data provider set")
            return

        try:
            # Get current positions from WebSocket
            positions = self.data_provider.get_positions_sync()

            # Build current positions map
            current_map = {p.coin: self._position_to_dict(p) for p in positions}

            # Detect closed positions
            closed_symbols = await self._detect_closed_positions(current_map)

            if closed_symbols:
                logger.info(f"Detected {len(closed_symbols)} closed positions: {closed_symbols}")
                await self._process_closed_positions(closed_symbols, iteration)

            # Update cache for next cycle
            self._last_positions = current_map

        except Exception as e:
            logger.error(f"TradeSync cycle failed: {e}", exc_info=True)

    async def _detect_closed_positions(
        self,
        current_map: Dict[str, Dict]
    ) -> Set[str]:
        """
        Detect which positions have been closed since last cycle.

        Returns:
            Set of coin symbols that were closed
        """
        if not self._last_positions:
            # First iteration - no comparison possible
            return set()

        previous_symbols = set(self._last_positions.keys())
        current_symbols = set(current_map.keys())

        closed = previous_symbols - current_symbols
        return closed

    async def _process_closed_positions(
        self,
        symbols: Set[str],
        iteration: int
    ):
        """
        Process closed positions by fetching fills and updating DB.

        Args:
            symbols: Set of closed coin symbols
            iteration: Current monitor iteration
        """
        # Fetch fills from HTTP API
        fills = await self.data_provider.fetch_fills_http(limit=500)

        if not fills:
            logger.warning("No fills returned from HTTP API")
            return

        # Reconstruct trades from fills
        trades = self._reconstruct_trades_from_fills(fills)

        # Filter to only closed positions we detected
        relevant_trades = [t for t in trades if t['symbol'].replace('-USDC', '') in symbols]

        if not relevant_trades:
            logger.debug(f"No matching trades found for {symbols}")
            return

        # Update database
        for trade_data in relevant_trades:
            await self._update_trade_in_db(trade_data, iteration)

    def _reconstruct_trades_from_fills(self, fills: List[Dict]) -> List[Dict]:
        """
        Reconstruct complete trades from Hyperliquid fills.

        Logic (from sevenbtc):
        1. Group fills by coin
        2. For each "Close" fill (closedPnl != 0), find corresponding "Open" fills
        3. Calculate weighted average entry price
        4. Net P&L = closedPnl - total_fees

        Args:
            fills: List of fill dicts from HTTP API

        Returns:
            List of reconstructed trade dicts
        """
        # Group fills by coin
        fills_by_coin = defaultdict(list)
        for fill in fills:
            fills_by_coin[fill['coin']].append(fill)

        # Sort each coin's fills by time (oldest first)
        for coin in fills_by_coin:
            fills_by_coin[coin].sort(key=lambda x: x['time'])

        trades = []

        for coin, coin_fills in fills_by_coin.items():
            for i, fill in enumerate(coin_fills):
                # Look for closing fills (closedPnl != 0)
                closed_pnl_str = fill.get('closedPnl', '0')
                closed_pnl = float(closed_pnl_str) if closed_pnl_str else 0

                if closed_pnl == 0:
                    continue  # Not a closing fill

                # This is a position close
                exit_fill = fill
                exit_time = datetime.fromtimestamp(exit_fill['time'] / 1000)
                exit_price = float(exit_fill['px'])
                exit_size = abs(float(exit_fill['sz']))
                exit_fee = abs(float(exit_fill.get('fee', 0)))

                # Determine position side from direction
                direction = exit_fill.get('dir', '')
                if 'Close Long' in direction:
                    side = 'long'
                elif 'Close Short' in direction:
                    side = 'short'
                else:
                    continue

                # Find corresponding opening fills
                entry_fills = []
                remaining_size = exit_size

                for j in range(i - 1, -1, -1):
                    if remaining_size <= 0.0001:
                        break

                    prev_fill = coin_fills[j]
                    prev_dir = prev_fill.get('dir', '')

                    is_opening = (side == 'long' and 'Open Long' in prev_dir) or \
                                 (side == 'short' and 'Open Short' in prev_dir)

                    if is_opening:
                        fill_size = abs(float(prev_fill['sz']))
                        entry_fills.append(prev_fill)
                        remaining_size -= fill_size

                if not entry_fills:
                    entry_time = exit_time
                    entry_price = exit_price
                    total_entry_fee = 0
                else:
                    # Calculate weighted average entry price
                    total_value = 0
                    total_size = 0
                    total_entry_fee = 0

                    for entry_fill in entry_fills:
                        fill_price = float(entry_fill['px'])
                        fill_size = abs(float(entry_fill['sz']))
                        fill_fee = abs(float(entry_fill.get('fee', 0)))

                        total_value += fill_price * fill_size
                        total_size += fill_size
                        total_entry_fee += fill_fee

                    entry_price = total_value / total_size if total_size > 0 else exit_price
                    entry_time = datetime.fromtimestamp(entry_fills[0]['time'] / 1000)

                # Calculate net P&L (closedPnl - fees)
                total_fee = total_entry_fee + exit_fee
                net_pnl = closed_pnl - total_fee

                # Calculate duration
                duration_seconds = (exit_time - entry_time).total_seconds()
                duration_minutes = int(duration_seconds / 60)

                # Create trade record
                trades.append({
                    'exit_tid': exit_fill.get('tid', ''),
                    'symbol': coin,
                    'side': side,
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'size': exit_size,
                    'exit_time': exit_time,
                    'exit_price': exit_price,
                    'gross_pnl': closed_pnl,
                    'net_pnl': net_pnl,
                    'entry_fee': total_entry_fee,
                    'exit_fee': exit_fee,
                    'total_fee': total_fee,
                    'duration_minutes': duration_minutes,
                })

        return trades

    async def _update_trade_in_db(self, trade_data: Dict, iteration: int):
        """
        Update existing Trade record in database with exit data.

        If no matching open trade found, logs warning (trade opened outside system).

        Args:
            trade_data: Reconstructed trade data
            iteration: Current monitor iteration
        """
        try:
            with get_session() as session:
                # Check for duplicate (already synced)
                existing = session.query(Trade).filter(
                    Trade.position_id == trade_data['exit_tid']
                ).first()

                if existing:
                    logger.debug(f"Trade {trade_data['exit_tid']} already synced")
                    return

                # Find matching open trade (entry_time, symbol, no exit)
                trade = session.query(Trade).filter(
                    Trade.symbol == trade_data['symbol'],
                    Trade.exit_time.is_(None)
                ).first()

                if trade:
                    # Update existing trade
                    trade.exit_time = trade_data['exit_time']
                    trade.exit_price = trade_data['exit_price']
                    trade.exit_size = trade_data['size']
                    trade.pnl_usd = trade_data['net_pnl']
                    trade.fees_usd = trade_data['total_fee']
                    trade.entry_fee_usd = trade_data['entry_fee']
                    trade.exit_fee_usd = trade_data['exit_fee']
                    trade.position_id = trade_data['exit_tid']
                    trade.duration_minutes = trade_data['duration_minutes']
                    trade.iteration = iteration
                    trade.exit_reason = 'synced'

                    # Calculate pnl_pct
                    if trade.entry_price and trade.entry_size:
                        trade.pnl_pct = trade_data['net_pnl'] / (trade.entry_price * trade.entry_size) * 100

                    logger.info(
                        f"Synced trade: {trade_data['symbol']} {trade_data['side']} "
                        f"PnL=${trade_data['net_pnl']:.2f} "
                        f"(duration: {trade_data['duration_minutes']}min)"
                    )
                else:
                    # Trade opened outside of SixBTC system
                    # Could create new Trade record here if needed
                    logger.warning(
                        f"No matching open trade for {trade_data['symbol']} - "
                        f"trade may have been opened outside SixBTC"
                    )

        except Exception as e:
            logger.error(f"Failed to update trade in DB: {e}", exc_info=True)

    def _position_to_dict(self, pos: UserPosition) -> Dict:
        """Convert UserPosition to dict for comparison."""
        return {
            'coin': pos.coin,
            'side': pos.side,
            'size': pos.size,
            'entry_price': pos.entry_price,
            'leverage': pos.leverage,
        }
