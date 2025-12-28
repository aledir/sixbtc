"""
Backtesting Engine

Backtests StrategyCore instances with realistic portfolio simulation.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import math
import time

from src.strategies.base import StrategyCore, Signal, StopLossType, ExitType
from src.backtester.signal_vectorizer import (
    SignalVectorizer,
    CursorDataFrame,
    PrecomputedDataFrame
)
from src.utils.logger import get_logger
from src.config.loader import load_config
from src.executor.risk_manager import RiskManager
from src.database.connection import get_session
from src.database.models import Coin

logger = get_logger(__name__)


def sanitize_float(value: float, default: float = 0.0) -> float:
    """
    Sanitize float values for JSON storage.
    Replaces Infinity and NaN with default value.
    """
    if value is None or math.isnan(value) or math.isinf(value):
        return default
    return float(value)


class BacktestEngine:
    """
    Backtesting engine for StrategyCore strategies

    Executes strategies on historical data with realistic portfolio simulation
    and calculates comprehensive performance metrics.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize backtester

        Args:
            config: Configuration dict (if None, loads from file)
        """
        self.config = config or load_config()

        # Extract config values using dot notation
        self.fee_rate = self.config.get('hyperliquid.fee_rate')
        self.slippage = self.config.get('hyperliquid.slippage')
        self.initial_capital = self.config.get('backtesting.initial_capital')

        # Use the same RiskManager as live executor for consistency
        # This ensures backtest results match live trading behavior
        # RiskManager expects a dict, not a Config object
        risk_config = self.config._raw_config if hasattr(self.config, '_raw_config') else self.config
        self.risk_manager = RiskManager(risk_config)

        # Cache for coin max leverage (avoid repeated DB queries)
        self._coin_max_leverage_cache: Dict[str, int] = {}

    def _get_coin_max_leverage(self, symbol: str) -> int:
        """
        Get max leverage for a coin from database (with caching).

        Args:
            symbol: Coin symbol (e.g., 'BTC', 'ETH')

        Returns:
            Max leverage from DB, defaults to 10 if not found
        """
        if symbol in self._coin_max_leverage_cache:
            return self._coin_max_leverage_cache[symbol]

        with get_session() as session:
            coin = session.query(Coin).filter(Coin.symbol == symbol).first()
            if coin:
                self._coin_max_leverage_cache[symbol] = coin.max_leverage
                return coin.max_leverage

        # Default fallback
        logger.warning(f"Coin {symbol} not found in DB, using default max_leverage=10")
        self._coin_max_leverage_cache[symbol] = 10
        return 10

    def backtest(
        self,
        strategy: StrategyCore,
        data: Dict[str, pd.DataFrame],
        max_positions: Optional[int] = None
    ) -> Dict:
        """
        Portfolio backtest with realistic position limits

        This is the PRIMARY method for multi-symbol backtesting.
        Simulates real trading constraints:
        - Maximum concurrent positions (from config: risk.limits.max_open_positions_per_subaccount)
        - Shared capital pool across all symbols
        - Position priority based on signal order
        - Slippage and fees applied to each trade

        This ensures backtest results match live trading behavior.

        Args:
            strategy: StrategyCore instance
            data: Dict mapping symbol → OHLCV DataFrame
            max_positions: Maximum concurrent open positions (default from config)

        Returns:
            Portfolio-level metrics with position-limited simulation
        """
        # Get max_positions from config if not provided
        if max_positions is None:
            max_positions = self.config.get('risk.limits.max_open_positions_per_subaccount')

        logger.info(
            f"Running realistic portfolio backtest "
            f"({len(data)} symbols, max_positions={max_positions})"
        )

        # Profiling timers
        _t_start = time.perf_counter()
        _t_align = 0.0
        _t_signals = 0.0
        _t_simulation = 0.0

        # Align all dataframes to common timestamp index
        _t0 = time.perf_counter()
        aligned_data = self._align_dataframes(data)
        _t_align = time.perf_counter() - _t0

        if aligned_data is None:
            return self._empty_results()

        common_index = aligned_data['_index']
        symbols = [s for s in aligned_data.keys() if s != '_index']

        # Track state across time
        open_positions = {}  # symbol -> {entry_price, entry_idx, size, sl, tp}
        closed_trades = []
        equity = self.initial_capital
        equity_curve = [equity]

        # Generate signals for all symbols upfront
        _t0 = time.perf_counter()
        all_signals = {}
        for symbol in symbols:
            df = aligned_data[symbol]
            entries, exits, sizes, sl_pcts, tp_pcts, signal_meta = self._generate_signals_with_atr(
                strategy, df, symbol
            )
            all_signals[symbol] = {
                'entries': entries,
                'exits': exits,
                'sizes': sizes,
                'sl_pcts': sl_pcts,
                'tp_pcts': tp_pcts,
                'close': df['close'],
                'high': df['high'],  # For trailing high water mark
                'signal_meta': signal_meta,  # Trailing and TIME_BASED info
            }
        _t_signals = time.perf_counter() - _t0

        # Simulate bar by bar
        _t0 = time.perf_counter()
        for i, timestamp in enumerate(common_index):
            # 1. Update trailing stops for open positions BEFORE checking exits
            for symbol, pos in open_positions.items():
                if not pos.get('trailing_sl'):
                    continue

                sig = all_signals[symbol]
                current_high = sig['high'].iloc[i]
                current_price = sig['close'].iloc[i]
                direction = pos.get('direction', 'long')

                # Check activation (must be in profit by activation_pct)
                if not pos.get('trailing_active', False):
                    activation_pct = pos.get('trailing_activation_pct', 0.01)
                    if direction == 'long':
                        profit_pct = (current_price - pos['entry_price']) / pos['entry_price']
                    else:
                        profit_pct = (pos['entry_price'] - current_price) / pos['entry_price']

                    if profit_pct >= activation_pct:
                        pos['trailing_active'] = True
                        pos['high_water_mark'] = current_high if direction == 'long' else current_price
                    continue  # Don't update SL until activated

                # Update high water mark
                if direction == 'long':
                    if current_high > pos.get('high_water_mark', 0):
                        pos['high_water_mark'] = current_high
                    # Calculate new trailing SL from high water mark
                    trail_pct = pos.get('trailing_stop_pct', 0.02)
                    new_sl = pos['high_water_mark'] * (1 - trail_pct)
                    # Only move SL up, never down
                    if new_sl > pos['sl']:
                        pos['sl'] = new_sl
                else:  # short
                    if current_price < pos.get('high_water_mark', float('inf')):
                        pos['high_water_mark'] = current_price
                    trail_pct = pos.get('trailing_stop_pct', 0.02)
                    new_sl = pos['high_water_mark'] * (1 + trail_pct)
                    if new_sl < pos['sl']:
                        pos['sl'] = new_sl

            # 2. Check exits for open positions (SL/TP/signal/time)
            positions_to_close = []
            for symbol, pos in open_positions.items():
                sig = all_signals[symbol]
                current_price = sig['close'].iloc[i]
                direction = pos.get('direction', 'long')

                # Check TIME_BASED exit first
                if pos.get('exit_after_bars') is not None:
                    bars_held = i - pos['entry_idx']
                    if bars_held >= pos['exit_after_bars']:
                        if direction == 'long':
                            pnl = (current_price - pos['entry_price']) * pos['size']
                        else:
                            pnl = (pos['entry_price'] - current_price) * pos['size']
                        positions_to_close.append((symbol, current_price, 'time_exit', pnl))
                        continue

                # Check stop loss (direction-aware)
                if direction == 'long':
                    if current_price <= pos['sl']:
                        pnl = (pos['sl'] - pos['entry_price']) * pos['size']
                        positions_to_close.append((symbol, pos['sl'], 'sl', pnl))
                        continue
                else:  # short
                    if current_price >= pos['sl']:
                        pnl = (pos['entry_price'] - pos['sl']) * pos['size']
                        positions_to_close.append((symbol, pos['sl'], 'sl', pnl))
                        continue

                # Check take profit (direction-aware)
                if pos['tp'] is not None:
                    if direction == 'long' and current_price >= pos['tp']:
                        pnl = (pos['tp'] - pos['entry_price']) * pos['size']
                        positions_to_close.append((symbol, pos['tp'], 'tp', pnl))
                        continue
                    elif direction == 'short' and current_price <= pos['tp']:
                        pnl = (pos['entry_price'] - pos['tp']) * pos['size']
                        positions_to_close.append((symbol, pos['tp'], 'tp', pnl))
                        continue

                # Check exit signal
                if sig['exits'].iloc[i]:
                    if direction == 'long':
                        pnl = (current_price - pos['entry_price']) * pos['size']
                    else:
                        pnl = (pos['entry_price'] - current_price) * pos['size']
                    positions_to_close.append((symbol, current_price, 'signal', pnl))

            # Close positions (apply slippage + fees)
            for symbol, exit_price, reason, raw_pnl in positions_to_close:
                pos = open_positions.pop(symbol)
                direction = pos.get('direction', 'long')
                leverage = pos.get('leverage', 1)
                margin = pos.get('margin', 0)

                # Apply slippage to exit price (adverse direction)
                if direction == 'long':
                    slipped_exit = exit_price * (1 - self.slippage)
                else:
                    slipped_exit = exit_price * (1 + self.slippage)

                # Recalculate PnL with slippage
                if direction == 'long':
                    pnl = (slipped_exit - pos['entry_price']) * pos['size']
                else:
                    pnl = (pos['entry_price'] - slipped_exit) * pos['size']

                # Apply fees (entry + exit)
                notional = pos['entry_price'] * pos['size']
                fees = notional * self.fee_rate * 2  # Entry + exit
                pnl -= fees

                # Return on margin (leveraged return)
                return_on_margin = pnl / margin if margin > 0 else 0

                equity += pnl
                closed_trades.append({
                    'symbol': symbol,
                    'entry_idx': pos['entry_idx'],
                    'exit_idx': i,
                    'entry_price': pos['entry_price'],
                    'exit_price': slipped_exit,
                    'size': pos['size'],
                    'margin': margin,
                    'leverage': leverage,
                    'notional': notional,
                    'pnl': pnl,
                    'return_on_margin': return_on_margin,
                    'fees': fees,
                    'exit_reason': reason,
                    'direction': direction,
                })

            # 3. Check for new entries (if slots available)
            if len(open_positions) < max_positions:
                available_slots = max_positions - len(open_positions)

                # Collect potential entries
                potential_entries = []
                for symbol in symbols:
                    if symbol in open_positions:
                        continue  # Already have position

                    sig = all_signals[symbol]
                    if sig['entries'].iloc[i]:
                        # Get signal metadata for this bar
                        meta = sig['signal_meta'].get(i, {})
                        potential_entries.append({
                            'symbol': symbol,
                            'price': sig['close'].iloc[i],
                            'size_pct': sig['sizes'].iloc[i],
                            'sl_pct': sig['sl_pcts'].iloc[i],
                            'tp_pct': sig['tp_pcts'].iloc[i] if pd.notna(sig['tp_pcts'].iloc[i]) else None,
                            'meta': meta,
                        })

                # Take first N entries (could add priority logic here)
                for entry in potential_entries[:available_slots]:
                    symbol = entry['symbol']
                    price = entry['price']
                    meta = entry['meta']
                    direction = meta.get('direction', 'long')

                    # Apply slippage to entry price (adverse direction)
                    if direction == 'long':
                        slipped_entry = price * (1 + self.slippage)
                    else:
                        slipped_entry = price * (1 - self.slippage)

                    # Calculate leverage: min(signal leverage, coin max leverage)
                    target_leverage = meta.get('leverage', 1)
                    coin_max_leverage = self._get_coin_max_leverage(symbol)
                    actual_leverage = min(target_leverage, coin_max_leverage)

                    # Calculate position size with leverage
                    # margin = % of equity allocated to this position
                    # notional = margin * leverage (actual exposure)
                    # size = notional / price (in coin units)
                    margin = equity * entry['size_pct']
                    notional = margin * actual_leverage
                    size = notional / slipped_entry

                    # Calculate SL/TP prices (direction-aware, from slipped entry)
                    if direction == 'long':
                        sl_price = slipped_entry * (1 - entry['sl_pct'])
                        tp_price = slipped_entry * (1 + entry['tp_pct']) if entry['tp_pct'] else None
                    else:  # short
                        sl_price = slipped_entry * (1 + entry['sl_pct'])
                        tp_price = slipped_entry * (1 - entry['tp_pct']) if entry['tp_pct'] else None

                    pos_data = {
                        'entry_price': slipped_entry,
                        'entry_idx': i,
                        'size': size,
                        'margin': margin,
                        'leverage': actual_leverage,
                        'sl': sl_price,
                        'tp': tp_price,
                        'direction': direction,
                    }

                    # Add trailing SL metadata if applicable
                    if meta.get('sl_type') == StopLossType.TRAILING:
                        pos_data['trailing_sl'] = True
                        pos_data['trailing_stop_pct'] = meta.get('trailing_stop_pct', 0.02)
                        pos_data['trailing_activation_pct'] = meta.get('trailing_activation_pct', 0.01)
                        pos_data['trailing_active'] = False
                        pos_data['high_water_mark'] = price

                    # Add TIME_BASED exit metadata if applicable
                    if meta.get('exit_type') == ExitType.TIME_BASED:
                        pos_data['exit_after_bars'] = meta.get('exit_after_bars', 20)

                    open_positions[symbol] = pos_data

            equity_curve.append(equity)
        _t_simulation = time.perf_counter() - _t0

        # Close any remaining positions at last price (apply slippage + fees)
        for symbol, pos in list(open_positions.items()):
            sig = all_signals[symbol]
            exit_price = sig['close'].iloc[-1]
            direction = pos.get('direction', 'long')
            leverage = pos.get('leverage', 1)
            margin = pos.get('margin', 0)

            # Apply slippage to exit price
            if direction == 'long':
                slipped_exit = exit_price * (1 - self.slippage)
                pnl = (slipped_exit - pos['entry_price']) * pos['size']
            else:
                slipped_exit = exit_price * (1 + self.slippage)
                pnl = (pos['entry_price'] - slipped_exit) * pos['size']

            # Apply fees
            notional = pos['entry_price'] * pos['size']
            fees = notional * self.fee_rate * 2
            pnl -= fees

            # Return on margin (leveraged return)
            return_on_margin = pnl / margin if margin > 0 else 0

            equity += pnl
            closed_trades.append({
                'symbol': symbol,
                'entry_idx': pos['entry_idx'],
                'exit_idx': len(common_index) - 1,
                'entry_price': pos['entry_price'],
                'exit_price': slipped_exit,
                'size': pos['size'],
                'margin': margin,
                'leverage': leverage,
                'notional': notional,
                'pnl': pnl,
                'return_on_margin': return_on_margin,
                'fees': fees,
                'exit_reason': 'end',
                'direction': direction,
            })

        # Calculate metrics
        metrics = self._calculate_portfolio_metrics(
            closed_trades,
            equity_curve,
            self.initial_capital
        )
        metrics['max_positions_used'] = max_positions
        metrics['symbols_count'] = len(symbols)

        # Log profiling results
        _t_total = time.perf_counter() - _t_start
        logger.info(
            f"Backtest complete: {len(closed_trades)} trades, {len(symbols)} symbols, "
            f"{len(common_index)} bars | "
            f"Time: {_t_total:.2f}s (align={_t_align:.2f}s, signals={_t_signals:.2f}s, sim={_t_simulation:.2f}s)"
        )

        return metrics

    def _align_dataframes(
        self,
        data: Dict[str, pd.DataFrame]
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Align multiple dataframes to common timestamp index

        Returns dict with aligned dataframes plus '_index' key for timestamps
        """
        if not data:
            return None

        # Set timestamp as index for all dataframes
        indexed_data = {}
        for symbol, df in data.items():
            if 'timestamp' in df.columns:
                df_copy = df.set_index('timestamp')
            else:
                df_copy = df.copy()
            indexed_data[symbol] = df_copy

        # Find common index (intersection of all timestamps)
        indices = [set(df.index) for df in indexed_data.values()]
        common_idx = sorted(set.intersection(*indices))

        if len(common_idx) < 100:
            logger.warning(f"Insufficient common data points: {len(common_idx)}")
            return None

        # Create aligned dict
        aligned = {'_index': common_idx}
        for symbol, df in indexed_data.items():
            aligned[symbol] = df.loc[common_idx]

        return aligned

    def _calculate_portfolio_metrics(
        self,
        trades: List[Dict],
        equity_curve: List[float],
        initial_capital: float
    ) -> Dict:
        """Calculate metrics from trade list and equity curve"""
        if not trades:
            return self._empty_results()

        # Basic trade stats
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t['pnl'] > 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # PnL stats
        pnls = [t['pnl'] for t in trades]
        total_pnl = sum(pnls)
        avg_pnl = np.mean(pnls)
        total_return = total_pnl / initial_capital

        # Expectancy
        avg_win = np.mean([p for p in pnls if p > 0]) if winning_trades > 0 else 0
        avg_loss = abs(np.mean([p for p in pnls if p < 0])) if (total_trades - winning_trades) > 0 else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        # Drawdown
        equity_arr = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity_arr)
        drawdowns = (equity_arr - running_max) / running_max
        max_drawdown = abs(drawdowns.min())

        # Sharpe (simplified - daily returns)
        returns = np.diff(equity_arr) / equity_arr[:-1]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0

        # Profit factor
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Average leverage used
        leverages = [t.get('leverage', 1) for t in trades]
        avg_leverage = np.mean(leverages) if leverages else 1.0

        return {
            'total_return': sanitize_float(total_return),
            'sharpe_ratio': sanitize_float(sharpe),
            'max_drawdown': sanitize_float(max_drawdown),
            'total_trades': total_trades,
            'win_rate': sanitize_float(win_rate),
            'expectancy': sanitize_float(expectancy),
            'profit_factor': sanitize_float(profit_factor, default=1.0),
            'avg_leverage': sanitize_float(avg_leverage, default=1.0),
            'final_equity': equity_curve[-1] if equity_curve else initial_capital,
            'trades': trades,
        }

    def _generate_signals_with_atr(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        symbol: str = None,
        use_precomputed: bool = True
    ) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, Dict]:
        """
        Generate entry/exit signals with ATR-based SL/TP percentages

        Uses PrecomputedDataFrame (fastest) or CursorDataFrame for signal generation.

        PrecomputedDataFrame pre-calculates common indicators (RSI, ATR, SMA, EMA,
        MACD, Bollinger Bands, etc.) ONCE for the entire dataset, then uses a cursor
        to simulate truncated data. This gives 10-18x speedup for strategies that
        use standard indicator names (rsi_14, atr_14, sma_20, etc.).

        Supports multiple exit mechanisms:
        1. sl_stop/tp_stop - VectorBT native percentage stops
        2. exits - indicator-based exit signals (direction='close')
        3. time_exit - exit after N bars (via exit_type=TIME_BASED)
        4. trailing - trailing stop with activation threshold

        Args:
            strategy: StrategyCore instance
            data: OHLCV DataFrame with high, low, close columns
            symbol: Symbol name for per-coin leverage
            use_precomputed: If True, use PrecomputedDataFrame with pre-calculated
                           indicators for maximum speed. Set to False if strategy
                           uses custom indicator calculations.

        Returns:
            (entries, exits, sizes, sl_pcts, tp_pcts, signal_meta) where signal_meta
            contains per-bar trailing/time_based info for realistic backtest
        """
        import talib as ta

        n = len(data)
        entries = pd.Series(False, index=data.index)
        exits = pd.Series(False, index=data.index)  # Indicator-based exits
        sizes = pd.Series(0.0, index=data.index)
        sl_pcts = pd.Series(np.nan, index=data.index)  # SL as % of price
        tp_pcts = pd.Series(np.nan, index=data.index)  # TP as % of price

        # Extra metadata for trailing/time_based (indexed by bar number)
        signal_meta = {}

        # Pre-calculate ATR for entire dataset
        if all(col in data.columns for col in ['high', 'low', 'close']):
            atr = ta.ATR(data['high'], data['low'], data['close'], timeperiod=14)
        else:
            # Fallback: estimate ATR from close only
            atr = data['close'].rolling(14).std() * 1.5

        # Choose DataFrame wrapper based on use_precomputed flag
        # PrecomputedDataFrame: fastest (18x) - pre-calculates RSI, ATR, SMA, etc.
        # CursorDataFrame: fast (3.6x) - no indicator pre-computation
        if use_precomputed:
            cursor_df = PrecomputedDataFrame(data, precompute=True)
        else:
            cursor_df = CursorDataFrame(data)

        warmup = 50  # Minimum bars before signal generation
        fallback_mode = False  # Track if we need to use copy fallback

        for i in range(warmup, n):
            # Move cursor to current bar (O(1) operation)
            cursor_df.set_cursor(i)

            # Generate signal using cursor view (strategy sees df.iloc[:i+1])
            try:
                if fallback_mode:
                    # Strategy doesn't support cursor view, use copy
                    df_slice = data.iloc[:i+1].copy()
                    signal = strategy.generate_signal(df_slice, symbol)
                else:
                    signal = strategy.generate_signal(cursor_df, symbol)
            except Exception as e:
                # Some strategies may fail on cursor view, fallback to copy
                if not fallback_mode:
                    logger.debug(f"Strategy needs DataFrame copy, switching to fallback: {e}")
                    fallback_mode = True
                df_slice = data.iloc[:i+1].copy()
                signal = strategy.generate_signal(df_slice, symbol)

            if signal is None:
                continue

            # Process entry signals
            if signal.direction in ['long', 'short']:
                entries.iloc[i] = True

                current_price = data['close'].iloc[i]
                current_atr = atr.iloc[i] if not np.isnan(atr.iloc[i]) else current_price * 0.02

                # Use RiskManager for position sizing - SAME logic as live executor
                # Pass actual df_slice for VOLATILITY type SL calculation
                df_slice = data.iloc[:i+1]
                position_size, stop_loss, take_profit = self.risk_manager.calculate_position_size(
                    signal=signal,
                    account_balance=self.initial_capital,
                    current_price=current_price,
                    atr=current_atr,
                    df=df_slice
                )

                # Convert absolute SL/TP to percentages for VectorBT
                sl_pct = abs(current_price - stop_loss) / current_price
                sl_pcts.iloc[i] = sl_pct

                # Position size from RiskManager is in coin units, convert to % of capital
                position_notional = position_size * current_price
                sizes.iloc[i] = position_notional / self.initial_capital

                # TP as percentage (only if strategy has take_profit enabled)
                if signal.tp_type is not None:
                    tp_pct = abs(take_profit - current_price) / current_price
                    tp_pcts.iloc[i] = tp_pct

                # Store extra metadata for trailing, time-based exits, and leverage
                meta = {
                    'direction': signal.direction,
                    'sl_type': getattr(signal, 'sl_type', StopLossType.ATR),
                    'exit_type': getattr(signal, 'exit_type', None),
                    'leverage': getattr(signal, 'leverage', 1),
                }

                # Trailing SL metadata
                if meta['sl_type'] == StopLossType.TRAILING:
                    meta['trailing_stop_pct'] = getattr(signal, 'trailing_stop_pct', 0.02)
                    meta['trailing_activation_pct'] = getattr(signal, 'trailing_activation_pct', 0.01)

                # Time-based exit metadata
                if meta['exit_type'] == ExitType.TIME_BASED:
                    meta['exit_after_bars'] = getattr(signal, 'exit_after_bars', 20)

                signal_meta[i] = meta

            # Process exit signals (indicator-based close)
            elif signal.direction == 'close':
                exits.iloc[i] = True

        return entries, exits, sizes, sl_pcts, tp_pcts, signal_meta

    def _extract_metrics(self, portfolio, n_signals: int) -> Dict:
        """
        Extract comprehensive metrics from VectorBT portfolio

        Args:
            portfolio: VectorBT Portfolio object
            n_signals: Number of entry signals generated

        Returns:
            Dict with all metrics
        """
        stats = portfolio.stats()

        # Core metrics
        total_return = portfolio.total_return() if hasattr(portfolio, 'total_return') else 0.0
        sharpe = portfolio.sharpe_ratio() if hasattr(portfolio, 'sharpe_ratio') else 0.0
        sortino = portfolio.sortino_ratio() if hasattr(portfolio, 'sortino_ratio') else 0.0
        max_dd = portfolio.max_drawdown() if hasattr(portfolio, 'max_drawdown') else 0.0

        # Trade statistics
        trades = portfolio.trades if hasattr(portfolio, 'trades') else None

        # Handle win_rate (might be property or method)
        if trades is not None:
            try:
                win_rate = trades.win_rate() if callable(trades.win_rate) else trades.win_rate
            except:
                win_rate = 0.0
        else:
            win_rate = 0.0

        total_trades = trades.count() if trades is not None else 0

        # Handle expectancy
        if trades is not None and hasattr(trades, 'expectancy'):
            try:
                expectancy = trades.expectancy() if callable(trades.expectancy) else trades.expectancy
            except:
                expectancy = 0.0
        else:
            expectancy = 0.0

        # Handle profit_factor
        if trades is not None and hasattr(trades, 'profit_factor'):
            try:
                profit_factor = trades.profit_factor() if callable(trades.profit_factor) else trades.profit_factor
            except:
                profit_factor = 0.0
        else:
            profit_factor = 0.0

        # Custom metrics
        ed_ratio = self._calculate_ed_ratio(expectancy, max_dd)
        consistency = self._calculate_consistency(portfolio)

        return {
            # Returns
            'total_return': sanitize_float(total_return),
            'cagr': sanitize_float(self._calculate_cagr(portfolio)),

            # Risk-adjusted
            'sharpe_ratio': sanitize_float(sharpe),
            'sortino_ratio': sanitize_float(sortino),
            'max_drawdown': sanitize_float(max_dd),

            # Trade stats
            'total_trades': int(total_trades),
            'win_rate': sanitize_float(win_rate),
            'expectancy': sanitize_float(expectancy),
            'profit_factor': sanitize_float(profit_factor, default=1.0),

            # Custom
            'ed_ratio': sanitize_float(ed_ratio),
            'consistency': sanitize_float(consistency),

            # Metadata
            'n_signals_generated': int(n_signals),
            'signal_execution_rate': sanitize_float(total_trades / n_signals) if n_signals > 0 else 0.0,
        }

    def _extract_trades(self, portfolio) -> List[Dict]:
        """
        Extract individual trade records

        Returns:
            List of trade dicts
        """
        trades = portfolio.trades if hasattr(portfolio, 'trades') else None

        if trades is None or trades.count() == 0:
            return []

        trade_list = []

        for i in range(trades.count()):
            try:
                trade = {
                    'entry_idx': int(trades.entry_idx[i]) if hasattr(trades, 'entry_idx') else i,
                    'exit_idx': int(trades.exit_idx[i]) if hasattr(trades, 'exit_idx') else i,
                    'entry_price': float(trades.entry_price[i]) if hasattr(trades, 'entry_price') else 0.0,
                    'exit_price': float(trades.exit_price[i]) if hasattr(trades, 'exit_price') else 0.0,
                    'size': float(trades.size[i]) if hasattr(trades, 'size') else 0.0,
                    'pnl': float(trades.pnl[i]) if hasattr(trades, 'pnl') else 0.0,
                    'return': float(trades.returns[i]) if hasattr(trades, 'returns') else 0.0,
                }
                trade_list.append(trade)
            except Exception as e:
                logger.debug(f"Could not extract trade {i}: {e}")
                continue

        return trade_list

    def _calculate_ed_ratio(self, expectancy: float, max_dd: float) -> float:
        """
        Calculate Expectancy/Drawdown ratio (edge efficiency)

        Higher = better edge relative to risk
        """
        if max_dd == 0 or max_dd > 1:
            return 0.0

        return expectancy / max_dd

    def _calculate_consistency(self, portfolio) -> float:
        """
        Calculate consistency (% of time in profit)

        Returns value between 0 and 1
        """
        try:
            equity_curve = portfolio.value()
            initial_value = equity_curve.iloc[0]

            in_profit = (equity_curve > initial_value).sum()
            total_periods = len(equity_curve)

            return in_profit / total_periods if total_periods > 0 else 0.0
        except:
            return 0.0

    def _calculate_cagr(self, portfolio) -> float:
        """
        Calculate Compound Annual Growth Rate

        Returns annualized return
        """
        try:
            total_return = portfolio.total_return()
            equity_curve = portfolio.value()

            # Calculate years
            n_periods = len(equity_curve)
            # Assume daily data if not specified
            years = n_periods / 365

            if years > 0:
                cagr = (1 + total_return) ** (1 / years) - 1
                return float(cagr)
        except:
            pass

        return 0.0

    def _empty_results(self) -> Dict:
        """
        Return empty results structure

        Used when backtest fails or has no trades
        """
        return {
            'total_return': 0.0,
            'cagr': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0,
            'max_drawdown': 0.0,
            'total_trades': 0,
            'win_rate': 0.0,
            'expectancy': 0.0,
            'profit_factor': 0.0,
            'avg_leverage': 1.0,
            'ed_ratio': 0.0,
            'consistency': 0.0,
            'n_signals_generated': 0,
            'signal_execution_rate': 0.0,
            'trades': [],
        }


# Backward compatibility aliases
VectorBTBacktester = BacktestEngine


class VectorBTEngine:
    """
    Deprecated: Use BacktestEngine directly instead.
    Kept for backward compatibility.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.backtester = BacktestEngine(config)

    def backtest(
        self,
        strategy: StrategyCore,
        data: Dict[str, pd.DataFrame],
        max_positions: Optional[int] = None
    ) -> Dict:
        """
        Run portfolio backtest with realistic position limits and leverage

        Args:
            strategy: StrategyCore instance
            data: Dict mapping symbol -> OHLCV DataFrame
            max_positions: Max concurrent positions (default from config)

        Returns:
            Portfolio-level metrics with position-limited simulation
        """
        return self.backtester.backtest(strategy, data, max_positions)

    # Alias for backward compatibility
    backtest_portfolio = backtest

    def calculate_metrics(self, portfolio) -> Dict:
        """
        Calculate metrics from VectorBT portfolio

        Args:
            portfolio: VectorBT portfolio object

        Returns:
            Metrics dictionary
        """
        return self.backtester._extract_metrics(portfolio, 0)
