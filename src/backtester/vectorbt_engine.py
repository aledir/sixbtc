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

logger = get_logger(__name__)


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

        # Generate signals
        entries, exits, sizes, stop_losses, take_profits = self._generate_signals(
            strategy,
            data
        )

        if entries.sum() == 0:
            logger.warning(f"No entry signals generated for {symbol_name}")
            return self._empty_results()

        # Run VectorBT backtest
        portfolio = vbt.Portfolio.from_signals(
            close=data['close'],
            entries=entries,
            exits=exits,
            size=sizes,
            size_type='percent',
            fees=self.fee_rate,
            slippage=self.slippage,
            init_cash=self.initial_capital,
            freq='1min'  # Will be adjusted based on data frequency
        )

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

    def _generate_signals(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame
    ) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
        """
        Generate entry/exit signals for entire dataset

        Args:
            strategy: StrategyCore instance
            data: OHLCV DataFrame

        Returns:
            (entries, exits, sizes, stop_losses, take_profits) as boolean/float Series
        """
        entries = pd.Series(False, index=data.index)
        exits = pd.Series(False, index=data.index)
        sizes = pd.Series(0.0, index=data.index)
        stop_losses = pd.Series(np.nan, index=data.index)
        take_profits = pd.Series(np.nan, index=data.index)

        in_position = False

        for i in range(len(data)):
            # Get data up to current bar (no lookahead!)
            df_slice = data.iloc[:i+1].copy()

            # Generate signal
            signal = strategy.generate_signal(df_slice)

            if signal is None:
                continue

            # Handle signal
            if signal.direction in ['long', 'short'] and not in_position:
                # Entry signal
                entries.iloc[i] = True
                sizes.iloc[i] = signal.size
                stop_losses.iloc[i] = signal.stop_loss
                take_profits.iloc[i] = signal.take_profit
                in_position = True

            elif signal.direction == 'close' and in_position:
                # Exit signal
                exits.iloc[i] = True
                in_position = False

        return entries, exits, sizes, stop_losses, take_profits

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
            'total_return': float(total_return),
            'cagr': self._calculate_cagr(portfolio),

            # Risk-adjusted
            'sharpe_ratio': float(sharpe),
            'sortino_ratio': float(sortino),
            'max_drawdown': float(max_dd),

            # Trade stats
            'total_trades': int(total_trades),
            'win_rate': float(win_rate),
            'expectancy': float(expectancy),
            'profit_factor': float(profit_factor),

            # Custom
            'ed_ratio': float(ed_ratio),
            'consistency': float(consistency),

            # Metadata
            'n_signals_generated': int(n_signals),
            'signal_execution_rate': float(total_trades / n_signals) if n_signals > 0 else 0.0,
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

    def calculate_metrics(self, portfolio) -> Dict:
        """
        Calculate metrics from VectorBT portfolio

        Args:
            portfolio: VectorBT portfolio object

        Returns:
            Metrics dictionary
        """
        return self.backtester._extract_metrics(portfolio, 0)
