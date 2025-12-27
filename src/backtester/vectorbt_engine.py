"""
VectorBT Backtesting Engine

Wraps VectorBT for backtesting StrategyCore instances.
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
from typing import Dict, Optional, List, Tuple
from datetime import datetime

from src.strategies.base import StrategyCore, Signal
from src.utils.logger import get_logger
from src.config.loader import load_config
import math

logger = get_logger(__name__)


def sanitize_float(value: float, default: float = 0.0) -> float:
    """
    Sanitize float values for JSON storage.
    Replaces Infinity and NaN with default value.
    """
    if value is None or math.isnan(value) or math.isinf(value):
        return default
    return float(value)


class VectorBTBacktester:
    """
    VectorBT-based backtesting engine

    Executes StrategyCore strategies on historical data and
    calculates comprehensive performance metrics.
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

    def backtest(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        symbol: Optional[str] = None
    ) -> Dict:
        """
        Run backtest on single symbol

        Args:
            strategy: StrategyCore instance
            data: OHLCV DataFrame with columns [open, high, low, close, volume]
            symbol: Symbol name (for logging)

        Returns:
            Dict with metrics and trade history
        """
        symbol_name = symbol or 'UNKNOWN'
        logger.info(f"Running backtest for {symbol_name} ({len(data)} candles)")

        # Generate signals with ATR-based SL/TP and indicator exits
        entries, exits, sizes, sl_pcts, tp_pcts = self._generate_signals_with_atr(
            strategy,
            data,
            symbol
        )

        if entries.sum() == 0:
            logger.warning(f"No entry signals generated for {symbol_name}")
            return self._empty_results()

        # Build portfolio kwargs
        portfolio_kwargs = {
            'close': data['close'],
            'entries': entries,
            'size': sizes,
            'size_type': 'percent',
            'fees': self.fee_rate,
            'slippage': self.slippage,
            'init_cash': self.initial_capital,
            'freq': '15min',
            'sl_stop': sl_pcts,
        }

        # Add indicator-based exits if any exist
        if exits.sum() > 0:
            portfolio_kwargs['exits'] = exits

        # Add take profit only if any are set
        if tp_pcts.notna().sum() > 0:
            portfolio_kwargs['tp_stop'] = tp_pcts

        # Run VectorBT backtest
        portfolio = vbt.Portfolio.from_signals(**portfolio_kwargs)

        # Extract metrics
        metrics = self._extract_metrics(portfolio, entries.sum())

        # Add trade list
        metrics['trades'] = self._extract_trades(portfolio)

        logger.info(
            f"Backtest complete: {metrics['total_trades']} trades, "
            f"Sharpe {metrics['sharpe_ratio']:.2f}, "
            f"Win Rate {metrics['win_rate']:.1%}"
        )

        return metrics

    def backtest_multi_symbol(
        self,
        strategy: StrategyCore,
        data: Dict[str, pd.DataFrame]
    ) -> Dict:
        """
        Run backtest across multiple symbols (portfolio)

        Args:
            strategy: StrategyCore instance
            data: Dict mapping symbol → OHLCV DataFrame

        Returns:
            Portfolio-level metrics
        """
        logger.info(f"Running multi-symbol backtest ({len(data)} symbols)")

        # Run backtest for each symbol
        symbol_results = {}

        for symbol, df in data.items():
            try:
                result = self.backtest(strategy, df, symbol)
                symbol_results[symbol] = result
            except Exception as e:
                logger.error(f"Failed to backtest {symbol}: {e}")
                continue

        # Aggregate portfolio metrics
        portfolio_metrics = self._aggregate_portfolio_metrics(symbol_results)

        logger.info(
            f"Portfolio backtest complete: "
            f"{portfolio_metrics['total_trades']} trades across {len(symbol_results)} symbols"
        )

        return portfolio_metrics

    def _generate_signals_with_atr(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        symbol: str = None
    ) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
        """
        Generate entry/exit signals with ATR-based SL/TP percentages

        Supports three exit mechanisms:
        1. sl_stop/tp_stop - VectorBT native percentage stops
        2. exits - indicator-based exit signals (direction='close')
        3. time_exit - handled by strategy returning 'close' after N bars

        Args:
            strategy: StrategyCore instance
            data: OHLCV DataFrame with high, low, close columns
            symbol: Symbol name for per-coin leverage

        Returns:
            (entries, exits, sizes, sl_pcts, tp_pcts) - entries/exits as bool, others as float Series
        """
        import talib as ta

        entries = pd.Series(False, index=data.index)
        exits = pd.Series(False, index=data.index)  # Indicator-based exits
        sizes = pd.Series(0.0, index=data.index)
        sl_pcts = pd.Series(np.nan, index=data.index)  # SL as % of price
        tp_pcts = pd.Series(np.nan, index=data.index)  # TP as % of price

        # Pre-calculate ATR for entire dataset
        if all(col in data.columns for col in ['high', 'low', 'close']):
            atr = ta.ATR(data['high'], data['low'], data['close'], timeperiod=14)
        else:
            # Fallback: estimate ATR from close only
            atr = data['close'].rolling(14).std() * 1.5

        for i in range(len(data)):
            # Get data up to current bar (no lookahead!)
            df_slice = data.iloc[:i+1].copy()

            # Generate signal (pass symbol for per-coin leverage)
            signal = strategy.generate_signal(df_slice, symbol)

            if signal is None:
                continue

            # Process entry signals
            if signal.direction in ['long', 'short']:
                entries.iloc[i] = True
                sizes.iloc[i] = signal.size if signal.size is not None else 1.0

                # Calculate SL/TP as percentages using ATR
                current_price = data['close'].iloc[i]
                current_atr = atr.iloc[i] if not np.isnan(atr.iloc[i]) else current_price * 0.02

                # SL = ATR * multiplier / price (as decimal percentage)
                sl_distance = current_atr * signal.atr_stop_multiplier
                sl_pcts.iloc[i] = sl_distance / current_price

                # TP = ATR * multiplier / price (as decimal percentage)
                # Only set if strategy has take_profit enabled
                if signal.tp_type is not None:
                    tp_distance = current_atr * signal.atr_take_multiplier
                    tp_pcts.iloc[i] = tp_distance / current_price

            # Process exit signals (indicator-based close)
            elif signal.direction == 'close':
                exits.iloc[i] = True

        return entries, exits, sizes, sl_pcts, tp_pcts

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

    def _aggregate_portfolio_metrics(self, symbol_results: Dict[str, Dict]) -> Dict:
        """
        Aggregate metrics across multiple symbols

        Args:
            symbol_results: Dict mapping symbol → metrics

        Returns:
            Portfolio-level aggregated metrics
        """
        if not symbol_results:
            return self._empty_results()

        # Aggregate total trades
        total_trades = sum(r['total_trades'] for r in symbol_results.values())

        # Weighted averages (by number of trades)
        total_weight = max(total_trades, 1)

        avg_sharpe = sum(
            r['sharpe_ratio'] * r['total_trades']
            for r in symbol_results.values()
        ) / total_weight

        avg_win_rate = sum(
            r['win_rate'] * r['total_trades']
            for r in symbol_results.values()
        ) / total_weight

        avg_expectancy = sum(
            r['expectancy'] * r['total_trades']
            for r in symbol_results.values()
        ) / total_weight

        # Max drawdown (worst across all symbols)
        max_dd = max(r['max_drawdown'] for r in symbol_results.values())

        # Recalculate ED ratio with aggregated values
        ed_ratio = self._calculate_ed_ratio(avg_expectancy, max_dd)

        return {
            'total_trades': total_trades,
            'sharpe_ratio': avg_sharpe,
            'win_rate': avg_win_rate,
            'expectancy': avg_expectancy,
            'max_drawdown': max_dd,
            'ed_ratio': ed_ratio,
            'symbols_traded': len(symbol_results),
            'symbol_breakdown': symbol_results,
        }

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
            'ed_ratio': 0.0,
            'consistency': 0.0,
            'n_signals_generated': 0,
            'signal_execution_rate': 0.0,
            'trades': [],
        }


class VectorBTEngine:
    """
    Alias for VectorBTBacktester for test compatibility
    """

    def __init__(self, config: Optional[Dict] = None):
        self.backtester = VectorBTBacktester(config)

    def run_backtest(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        initial_capital: float = 10000,
        fees: float = 0.0004,
        slippage: float = 0.0002
    ) -> Dict:
        """
        Run backtest with custom parameters

        Args:
            strategy: StrategyCore instance
            data: OHLCV DataFrame
            initial_capital: Starting capital
            fees: Fee rate
            slippage: Slippage rate

        Returns:
            Metrics dictionary
        """
        # Override config temporarily
        self.backtester.initial_capital = initial_capital
        self.backtester.fee_rate = fees
        self.backtester.slippage = slippage

        return self.backtester.backtest(strategy, data)

    def backtest_multi_symbol(
        self,
        strategy: StrategyCore,
        data: Dict[str, pd.DataFrame]
    ) -> Dict:
        """
        Run backtest across multiple symbols (portfolio)

        Args:
            strategy: StrategyCore instance
            data: Dict mapping symbol → OHLCV DataFrame

        Returns:
            Portfolio-level metrics with symbol_breakdown
        """
        return self.backtester.backtest_multi_symbol(strategy, data)

    def calculate_metrics(self, portfolio) -> Dict:
        """
        Calculate metrics from VectorBT portfolio

        Args:
            portfolio: VectorBT portfolio object

        Returns:
            Metrics dictionary
        """
        return self.backtester._extract_metrics(portfolio, 0)
