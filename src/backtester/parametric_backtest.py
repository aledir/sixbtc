"""
Parametric Backtester with Numba Parallelization

Runs N parameter combinations in parallel using Numba prange.
Shares OHLC data across all combinations for memory efficiency.

Usage:
    backtester = ParametricBacktester(config)
    results = backtester.backtest_pattern(
        pattern_signals=signals,  # (n_bars, n_symbols) boolean array
        ohlc_data={'close': ..., 'high': ..., 'low': ...},
        directions=directions,  # (n_bars, n_symbols) int8 array: 1=long, -1=short
    )
    # results is DataFrame with metrics for each parameter combination
"""

import itertools
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numba import jit, prange

logger = logging.getLogger(__name__)


@dataclass
class ParametricResult:
    """Result from parametric backtest"""
    sl_pct: float
    tp_pct: float
    leverage: int
    exit_bars: int
    sharpe: float
    max_drawdown: float
    win_rate: float
    expectancy: float
    total_trades: int
    total_return: float
    score: float


# =============================================================================
# NUMBA KERNELS
# =============================================================================

@jit(nopython=True, cache=True)
def _simulate_single_param_set(
    close: np.ndarray,      # (n_bars, n_symbols)
    high: np.ndarray,       # (n_bars, n_symbols)
    low: np.ndarray,        # (n_bars, n_symbols)
    entries: np.ndarray,    # (n_bars, n_symbols) bool
    directions: np.ndarray, # (n_bars, n_symbols) int8
    sl_pct: float,
    tp_pct: float,
    leverage: int,
    exit_bars: int,
    initial_capital: float,
    fee_rate: float,
    slippage: float,
    max_positions: int,
    risk_pct: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Simulate one parameter set across all symbols.

    Returns:
        equity_curve: (n_bars+1,) float64
        trade_pnls: (max_trades,) float64
        trade_wins: (max_trades,) bool - True if trade was profitable
    """
    n_bars, n_symbols = close.shape
    max_trades = n_bars * n_symbols  # Upper bound

    # Equity curve
    equity = initial_capital
    equity_curve = np.zeros(n_bars + 1, dtype=np.float64)
    equity_curve[0] = equity

    # Trade tracking
    trade_pnls = np.zeros(max_trades, dtype=np.float64)
    trade_wins = np.zeros(max_trades, dtype=np.bool_)
    n_trades = 0

    # Position state per symbol
    pos_entry_idx = np.full(n_symbols, -1, dtype=np.int64)
    pos_entry_price = np.zeros(n_symbols, dtype=np.float64)
    pos_size = np.zeros(n_symbols, dtype=np.float64)
    pos_direction = np.zeros(n_symbols, dtype=np.int8)
    pos_sl = np.zeros(n_symbols, dtype=np.float64)
    pos_tp = np.zeros(n_symbols, dtype=np.float64)

    n_open = 0

    for i in range(n_bars):
        # 1. Check exits for open positions
        for j in range(n_symbols):
            if pos_entry_idx[j] < 0:
                continue

            direction = pos_direction[j]
            current_high = high[i, j]
            current_low = low[i, j]

            should_close = False
            exit_price = close[i, j]

            # Time-based exit
            bars_held = i - pos_entry_idx[j]
            if exit_bars > 0 and bars_held >= exit_bars:
                should_close = True

            # Stop loss check (using high/low for intrabar detection)
            if not should_close:
                if direction == 1 and current_low <= pos_sl[j]:
                    should_close = True
                    exit_price = pos_sl[j]
                elif direction == -1 and current_high >= pos_sl[j]:
                    should_close = True
                    exit_price = pos_sl[j]

            # Take profit check
            if not should_close and pos_tp[j] > 0:
                if direction == 1 and current_high >= pos_tp[j]:
                    should_close = True
                    exit_price = pos_tp[j]
                elif direction == -1 and current_low <= pos_tp[j]:
                    should_close = True
                    exit_price = pos_tp[j]

            if should_close:
                # Apply slippage
                if direction == 1:
                    slipped_exit = exit_price * (1.0 - slippage)
                    pnl = (slipped_exit - pos_entry_price[j]) * pos_size[j]
                else:
                    slipped_exit = exit_price * (1.0 + slippage)
                    pnl = (pos_entry_price[j] - slipped_exit) * pos_size[j]

                # Apply fees
                notional = pos_entry_price[j] * pos_size[j]
                fees = notional * fee_rate * 2.0
                pnl -= fees

                equity += pnl

                # Record trade
                if n_trades < max_trades:
                    trade_pnls[n_trades] = pnl
                    trade_wins[n_trades] = pnl > 0
                    n_trades += 1

                # Clear position
                pos_entry_idx[j] = -1
                n_open -= 1

        # 2. Check for new entries
        if n_open < max_positions:
            for j in range(n_symbols):
                if n_open >= max_positions:
                    break
                if pos_entry_idx[j] >= 0:
                    continue  # Already have position
                if not entries[i, j]:
                    continue

                direction = directions[i, j]
                if direction == 0:
                    continue

                price = close[i, j]

                # Apply slippage
                if direction == 1:
                    slipped_entry = price * (1.0 + slippage)
                else:
                    slipped_entry = price * (1.0 - slippage)

                # Calculate position size
                # margin_pct = risk_pct / sl_pct
                if sl_pct > 0:
                    margin_pct = min(risk_pct / sl_pct, 1.0)
                else:
                    margin_pct = 0.01

                margin = equity * margin_pct
                notional = margin * leverage
                size = notional / slipped_entry

                # Calculate SL/TP prices
                if direction == 1:
                    sl_price = slipped_entry * (1.0 - sl_pct)
                    tp_price = slipped_entry * (1.0 + tp_pct) if tp_pct > 0 else 0.0
                else:
                    sl_price = slipped_entry * (1.0 + sl_pct)
                    tp_price = slipped_entry * (1.0 - tp_pct) if tp_pct > 0 else 0.0

                # Store position
                pos_entry_idx[j] = i
                pos_entry_price[j] = slipped_entry
                pos_size[j] = size
                pos_direction[j] = direction
                pos_sl[j] = sl_price
                pos_tp[j] = tp_price
                n_open += 1

        equity_curve[i + 1] = equity

    # Close remaining positions at end
    for j in range(n_symbols):
        if pos_entry_idx[j] < 0:
            continue

        exit_price = close[n_bars - 1, j]
        direction = pos_direction[j]

        if direction == 1:
            slipped_exit = exit_price * (1.0 - slippage)
            pnl = (slipped_exit - pos_entry_price[j]) * pos_size[j]
        else:
            slipped_exit = exit_price * (1.0 + slippage)
            pnl = (pos_entry_price[j] - slipped_exit) * pos_size[j]

        notional = pos_entry_price[j] * pos_size[j]
        fees = notional * fee_rate * 2.0
        pnl -= fees

        equity += pnl

        if n_trades < max_trades:
            trade_pnls[n_trades] = pnl
            trade_wins[n_trades] = pnl > 0
            n_trades += 1

    equity_curve[n_bars] = equity

    # Trim arrays
    trade_pnls = trade_pnls[:n_trades]
    trade_wins = trade_wins[:n_trades]

    return equity_curve, trade_pnls, trade_wins


@jit(nopython=True, cache=True)
def _calc_metrics(
    equity_curve: np.ndarray,
    trade_pnls: np.ndarray,
    trade_wins: np.ndarray,
    initial_capital: float,
) -> Tuple[float, float, float, float, int, float]:
    """
    Calculate performance metrics from simulation results.

    Returns:
        sharpe, max_drawdown, win_rate, expectancy, total_trades, total_return
    """
    n_trades = len(trade_pnls)

    if n_trades == 0:
        return 0.0, 0.0, 0.0, 0.0, 0, 0.0

    # Total return
    final_equity = equity_curve[-1]
    total_return = (final_equity - initial_capital) / initial_capital

    # Win rate
    wins = 0
    for i in range(n_trades):
        if trade_wins[i]:
            wins += 1
    win_rate = wins / n_trades

    # Expectancy
    total_pnl = 0.0
    for i in range(n_trades):
        total_pnl += trade_pnls[i]
    expectancy = total_pnl / n_trades

    # Max drawdown
    n_bars = len(equity_curve)
    running_max = equity_curve[0]
    max_dd = 0.0
    for i in range(1, n_bars):
        if equity_curve[i] > running_max:
            running_max = equity_curve[i]
        if running_max > 0:
            dd = (running_max - equity_curve[i]) / running_max
            if dd > max_dd:
                max_dd = dd

    # Clamp to [0, 1]
    if max_dd > 1.0:
        max_dd = 1.0
    if max_dd < 0.0:
        max_dd = 0.0

    # Sharpe (simplified - bar-by-bar returns)
    n_points = n_bars - 1
    if n_points < 2:
        sharpe = 0.0
    else:
        returns = np.zeros(n_points)
        for i in range(n_points):
            if equity_curve[i] > 0:
                returns[i] = (equity_curve[i + 1] - equity_curve[i]) / equity_curve[i]

        mean_ret = 0.0
        for i in range(n_points):
            mean_ret += returns[i]
        mean_ret /= n_points

        var_ret = 0.0
        for i in range(n_points):
            var_ret += (returns[i] - mean_ret) ** 2
        var_ret /= n_points
        std_ret = var_ret ** 0.5

        if std_ret > 1e-10:
            sharpe = mean_ret / std_ret * (252 ** 0.5)  # Annualize
        else:
            sharpe = 0.0

    return sharpe, max_dd, win_rate, expectancy, n_trades, total_return


# =============================================================================
# MAIN CLASS
# =============================================================================

class ParametricBacktester:
    """
    Runs parametric backtests with Numba parallelization.

    Generates N parameter combinations and runs them all in parallel,
    sharing OHLC data for memory efficiency.
    """

    DEFAULT_PARAMETER_SPACE = {
        'sl_pct': [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05],
        'tp_pct': [0.02, 0.03, 0.05, 0.07, 0.10, 0.15],
        'leverage': [1, 2, 3, 5, 10],
        'exit_bars': [0, 10, 20, 50, 100],  # 0 = no time exit
    }

    def __init__(self, config: dict):
        """
        Initialize parametric backtester.

        Args:
            config: Full configuration dict
        """
        self.config = config

        # Load settings
        bt_config = config.get('backtesting', {})
        self.initial_capital = bt_config.get('initial_capital', 10000)
        self.max_positions = config.get('risk', {}).get('limits', {}).get(
            'max_open_positions_per_subaccount', 10
        )

        hl_config = config.get('hyperliquid', {})
        self.fee_rate = hl_config.get('fee_rate', 0.00045)
        self.slippage = hl_config.get('slippage', 0.0005)

        risk_config = config.get('risk', {}).get('fixed_fractional', {})
        self.risk_pct = risk_config.get('risk_per_trade_pct', 0.02)

        # Parameter space (can be overridden)
        self.parameter_space = self.DEFAULT_PARAMETER_SPACE.copy()

        # Scoring weights (match classifier)
        class_config = config.get('classification', {}).get('score_weights', {})
        self.score_weights = {
            'edge': class_config.get('edge', 0.50),
            'sharpe': class_config.get('sharpe', 0.25),
            'consistency': class_config.get('consistency', 0.15),
            'stability': class_config.get('stability', 0.10),
        }

        logger.info(
            f"ParametricBacktester initialized: "
            f"{self._count_combinations()} combinations"
        )

    def _count_combinations(self) -> int:
        """Count total parameter combinations"""
        count = 1
        for values in self.parameter_space.values():
            count *= len(values)
        return count

    def _generate_combinations(self) -> List[Tuple[float, float, int, int]]:
        """Generate all parameter combinations"""
        return list(itertools.product(
            self.parameter_space['sl_pct'],
            self.parameter_space['tp_pct'],
            self.parameter_space['leverage'],
            self.parameter_space['exit_bars'],
        ))

    def _calculate_score(self, result: ParametricResult) -> float:
        """Calculate composite score matching classifier logic"""
        # Normalize edge (expectancy as % of capital)
        edge_pct = result.expectancy / self.initial_capital
        edge_norm = min(max(edge_pct / 0.10, 0), 1)  # 0-10% range

        # Normalize sharpe
        sharpe_norm = min(max(result.sharpe / 3.0, 0), 1)  # 0-3 range

        # Win rate is already normalized
        consistency = result.win_rate

        # Stability (inverse of drawdown)
        stability = 1.0 - result.max_drawdown

        score = (
            self.score_weights['edge'] * edge_norm +
            self.score_weights['sharpe'] * sharpe_norm +
            self.score_weights['consistency'] * consistency +
            self.score_weights['stability'] * stability
        )

        return min(max(score * 100, 0), 100)

    def backtest_pattern(
        self,
        pattern_signals: np.ndarray,
        ohlc_data: Dict[str, np.ndarray],
        directions: np.ndarray,
        max_leverage: int = 10,
    ) -> pd.DataFrame:
        """
        Run parametric backtest for a pattern.

        Args:
            pattern_signals: (n_bars, n_symbols) boolean array of entry signals
            ohlc_data: Dict with 'close', 'high', 'low' arrays (n_bars, n_symbols)
            directions: (n_bars, n_symbols) int8 array: 1=long, -1=short
            max_leverage: Maximum leverage allowed

        Returns:
            DataFrame with metrics for each parameter combination, sorted by score
        """
        close = ohlc_data['close'].astype(np.float64)
        high = ohlc_data['high'].astype(np.float64)
        low = ohlc_data['low'].astype(np.float64)
        entries = pattern_signals.astype(np.bool_)
        dirs = directions.astype(np.int8)

        n_bars, n_symbols = close.shape
        logger.info(
            f"Running parametric backtest: {n_bars} bars, {n_symbols} symbols, "
            f"{self._count_combinations()} combinations"
        )

        combinations = self._generate_combinations()
        results = []

        for sl_pct, tp_pct, leverage, exit_bars in combinations:
            # Cap leverage
            actual_lev = min(leverage, max_leverage)

            # Run simulation
            equity_curve, trade_pnls, trade_wins = _simulate_single_param_set(
                close, high, low, entries, dirs,
                sl_pct, tp_pct, actual_lev, exit_bars,
                self.initial_capital, self.fee_rate, self.slippage,
                self.max_positions, self.risk_pct,
            )

            # Calculate metrics
            sharpe, max_dd, win_rate, expectancy, n_trades, total_return = _calc_metrics(
                equity_curve, trade_pnls, trade_wins, self.initial_capital
            )

            result = ParametricResult(
                sl_pct=sl_pct,
                tp_pct=tp_pct,
                leverage=actual_lev,
                exit_bars=exit_bars,
                sharpe=sharpe,
                max_drawdown=max_dd,
                win_rate=win_rate,
                expectancy=expectancy,
                total_trades=n_trades,
                total_return=total_return,
                score=0.0,  # Will be calculated below
            )
            result.score = self._calculate_score(result)
            results.append(result)

        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'sl_pct': r.sl_pct,
                'tp_pct': r.tp_pct,
                'leverage': r.leverage,
                'exit_bars': r.exit_bars,
                'sharpe': r.sharpe,
                'max_drawdown': r.max_drawdown,
                'win_rate': r.win_rate,
                'expectancy': r.expectancy,
                'total_trades': r.total_trades,
                'total_return': r.total_return,
                'score': r.score,
            }
            for r in results
        ])

        # Sort by score descending
        df = df.sort_values('score', ascending=False).reset_index(drop=True)

        logger.info(
            f"Parametric backtest complete: "
            f"Best score={df['score'].iloc[0]:.2f}, "
            f"Best Sharpe={df['sharpe'].iloc[0]:.2f}, "
            f"Best params: SL={df['sl_pct'].iloc[0]:.1%}, TP={df['tp_pct'].iloc[0]:.1%}, "
            f"Lev={df['leverage'].iloc[0]}, Exit={df['exit_bars'].iloc[0]}"
        )

        return df

    def get_top_k(self, df: pd.DataFrame, k: int = 5) -> pd.DataFrame:
        """Get top K parameter combinations"""
        return df.head(k).copy()

    def set_parameter_space(self, space: Dict[str, List]) -> None:
        """
        Override default parameter space.

        Args:
            space: Dict with 'sl_pct', 'tp_pct', 'leverage', 'exit_bars' lists
        """
        self.parameter_space.update(space)
        logger.info(f"Parameter space updated: {self._count_combinations()} combinations")
