"""
Leveraged Backtesting Engine

Wrapper around VectorBT that properly handles:
- Variable leverage per strategy and per coin
- Accurate margin calculations
- Correct equity curve with leverage
- Accurate metrics (Sharpe, MaxDD, etc.)

The key insight: VectorBT calculates trade PnL correctly (price diff * size - fees).
We just need to track MARGIN requirements and calculate returns relative to margin.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

from src.backtester.vectorbt_engine import VectorBTBacktester
from src.strategies.base import StrategyCore, Signal
from src.database import get_session, Coin
from src.utils.logger import get_logger
from src.config.loader import load_config

logger = get_logger(__name__)


@dataclass
class LeveragedTrade:
    """
    Trade record with leverage information
    """
    symbol: str
    entry_idx: int
    exit_idx: int
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    size: float  # Position size in asset units
    direction: str  # 'long' or 'short'
    leverage: int

    # Calculated fields
    notional: float = 0.0  # size * entry_price
    margin: float = 0.0  # notional / leverage
    pnl_dollars: float = 0.0  # Absolute PnL in dollars
    return_on_margin: float = 0.0  # pnl / margin (leveraged return)
    fees: float = 0.0

    def __post_init__(self):
        """Calculate derived fields"""
        self.notional = abs(self.size * self.entry_price)
        self.margin = self.notional / self.leverage if self.leverage > 0 else self.notional

        # PnL calculation
        if self.direction == 'long':
            self.pnl_dollars = (self.exit_price - self.entry_price) * abs(self.size) - self.fees
        else:  # short
            self.pnl_dollars = (self.entry_price - self.exit_price) * abs(self.size) - self.fees

        # Return on margin (leveraged return)
        if self.margin > 0:
            self.return_on_margin = self.pnl_dollars / self.margin
        else:
            self.return_on_margin = 0.0


class LeveragedBacktester:
    """
    Backtester with proper leverage handling

    Wraps VectorBT and recalculates metrics based on actual margin requirements.

    Key differences from VectorBT alone:
    1. Tracks margin per position, not just notional
    2. Calculates returns relative to margin used
    3. MaxDD calculated on margin-based equity curve
    4. Sharpe calculated on margin-based returns
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize leveraged backtester

        Args:
            config: Configuration dict (if None, loads from file)
        """
        self.config = config or load_config()

        # Base VectorBT backtester
        self.base_backtester = VectorBTBacktester(config)

        # Config values
        self.initial_capital = self.config.get('backtesting.initial_capital', 10000)
        self.fee_rate = self.config.get('hyperliquid.fee_rate', 0.00045)
        self.slippage = self.config.get('hyperliquid.slippage', 0.0005)

        # Default leverage if not specified in signal
        self.default_leverage = 1

        # Cache for coin max leverage (avoid repeated DB queries)
        self._coin_max_leverage_cache: Dict[str, int] = {}

        logger.info("LeveragedBacktester initialized")

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
        data: pd.DataFrame,
        symbol: str = 'UNKNOWN',
        leverage_override: Optional[int] = None
    ) -> Dict:
        """
        Run leveraged backtest on single symbol

        Args:
            strategy: StrategyCore instance
            data: OHLCV DataFrame
            symbol: Symbol name
            leverage_override: Override leverage for all trades (optional)

        Returns:
            Dict with leveraged metrics
        """
        logger.info(f"Running leveraged backtest for {symbol} ({len(data)} candles)")

        # Step 1: Generate signals and extract trades with leverage
        trades = self._generate_trades_with_leverage(
            strategy, data, symbol, leverage_override
        )

        if not trades:
            logger.warning(f"No trades generated for {symbol}")
            return self._empty_results()

        # Step 2: Build leveraged equity curve
        equity_curve, margin_curve = self._build_equity_curves(
            trades, data, self.initial_capital
        )

        # Step 3: Calculate metrics from leveraged equity curve
        metrics = self._calculate_metrics(trades, equity_curve, margin_curve)

        # Add trade list
        metrics['trades'] = [self._trade_to_dict(t) for t in trades]
        metrics['symbol'] = symbol

        logger.info(
            f"Leveraged backtest complete: {len(trades)} trades, "
            f"Sharpe {metrics['sharpe_ratio']:.2f}, "
            f"MaxDD {metrics['max_drawdown']:.1%}, "
            f"Win Rate {metrics['win_rate']:.1%}"
        )

        return metrics

    def backtest_multi_symbol(
        self,
        strategy: StrategyCore,
        data: Dict[str, pd.DataFrame],
        leverage_per_symbol: Optional[Dict[str, int]] = None
    ) -> Dict:
        """
        Run leveraged backtest across multiple symbols

        This simulates a portfolio with shared capital across all symbols.

        Args:
            strategy: StrategyCore instance
            data: Dict mapping symbol -> OHLCV DataFrame
            leverage_per_symbol: Dict mapping symbol -> leverage (optional)

        Returns:
            Portfolio-level metrics with proper leverage handling
        """
        logger.info(f"Running multi-symbol leveraged backtest ({len(data)} symbols)")

        # Collect all trades across all symbols
        all_trades: List[LeveragedTrade] = []

        for symbol, df in data.items():
            leverage = None
            if leverage_per_symbol and symbol in leverage_per_symbol:
                leverage = leverage_per_symbol[symbol]

            trades = self._generate_trades_with_leverage(
                strategy, df, symbol, leverage
            )
            all_trades.extend(trades)

        if not all_trades:
            logger.warning("No trades generated across all symbols")
            return self._empty_results()

        # Sort trades by entry time for proper equity curve
        all_trades.sort(key=lambda t: t.entry_idx)

        # Build unified data index for equity curve
        unified_index = self._build_unified_index(data)

        # Build portfolio equity curve with all trades
        equity_curve, margin_curve = self._build_portfolio_equity_curve(
            all_trades, unified_index, self.initial_capital
        )

        # Calculate portfolio metrics
        metrics = self._calculate_metrics(all_trades, equity_curve, margin_curve)

        # Add symbol breakdown
        symbol_breakdown = self._calculate_symbol_breakdown(all_trades)
        metrics['symbol_breakdown'] = symbol_breakdown
        metrics['symbols_traded'] = len(symbol_breakdown)

        logger.info(
            f"Portfolio backtest complete: {len(all_trades)} trades, "
            f"Sharpe {metrics['sharpe_ratio']:.2f}, "
            f"MaxDD {metrics['max_drawdown']:.1%}"
        )

        return metrics

    def _generate_trades_with_leverage(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        symbol: str,
        leverage_override: Optional[int] = None
    ) -> List[LeveragedTrade]:
        """
        Generate trades by running strategy and capturing leverage per signal

        Args:
            strategy: StrategyCore instance
            data: OHLCV DataFrame
            symbol: Symbol name
            leverage_override: Override leverage for all trades

        Returns:
            List of LeveragedTrade objects
        """
        trades = []
        in_position = False
        current_entry = None

        for i in range(len(data)):
            # Get data up to current bar (no lookahead)
            df_slice = data.iloc[:i+1].copy()

            # Generate signal (pass symbol for per-coin leverage)
            signal = strategy.generate_signal(df_slice, symbol)

            if signal is None:
                continue

            current_price = data['close'].iloc[i]
            current_time = data.index[i] if isinstance(data.index, pd.DatetimeIndex) else i

            # Entry signal
            if signal.direction in ['long', 'short'] and not in_position:
                # Determine target leverage (priority: override > signal > strategy.leverage)
                if leverage_override is not None:
                    target_leverage = leverage_override
                elif hasattr(signal, 'leverage') and signal.leverage > 0:
                    target_leverage = signal.leverage
                elif hasattr(strategy, 'leverage'):
                    target_leverage = strategy.leverage
                else:
                    target_leverage = self.default_leverage

                # Cap at coin's max leverage
                coin_max = self._get_coin_max_leverage(symbol)
                leverage = min(target_leverage, coin_max)

                # Calculate position size (simplified: use fixed fraction of capital)
                # In real backtest, this would come from risk manager
                position_size = self._calculate_position_size(
                    self.initial_capital,
                    current_price,
                    leverage
                )

                current_entry = {
                    'entry_idx': i,
                    'entry_time': current_time,
                    'entry_price': current_price * (1 + self.slippage),  # Slippage on entry
                    'size': position_size,
                    'direction': signal.direction,
                    'leverage': leverage,
                }
                in_position = True

            # Exit signal
            elif signal.direction == 'close' and in_position:
                exit_price = current_price * (1 - self.slippage)  # Slippage on exit

                # Calculate fees
                entry_notional = current_entry['size'] * current_entry['entry_price']
                exit_notional = current_entry['size'] * exit_price
                fees = (entry_notional + exit_notional) * self.fee_rate

                trade = LeveragedTrade(
                    symbol=symbol,
                    entry_idx=current_entry['entry_idx'],
                    exit_idx=i,
                    entry_time=current_entry['entry_time'],
                    exit_time=current_time,
                    entry_price=current_entry['entry_price'],
                    exit_price=exit_price,
                    size=current_entry['size'],
                    direction=current_entry['direction'],
                    leverage=current_entry['leverage'],
                    fees=fees,
                )

                trades.append(trade)
                in_position = False
                current_entry = None

        # Close any open position at end
        if in_position and current_entry is not None:
            exit_price = data['close'].iloc[-1] * (1 - self.slippage)
            exit_time = data.index[-1] if isinstance(data.index, pd.DatetimeIndex) else len(data) - 1

            entry_notional = current_entry['size'] * current_entry['entry_price']
            exit_notional = current_entry['size'] * exit_price
            fees = (entry_notional + exit_notional) * self.fee_rate

            trade = LeveragedTrade(
                symbol=symbol,
                entry_idx=current_entry['entry_idx'],
                exit_idx=len(data) - 1,
                entry_time=current_entry['entry_time'],
                exit_time=exit_time,
                entry_price=current_entry['entry_price'],
                exit_price=exit_price,
                size=current_entry['size'],
                direction=current_entry['direction'],
                leverage=current_entry['leverage'],
                fees=fees,
            )
            trades.append(trade)

        return trades

    def _calculate_position_size(
        self,
        capital: float,
        price: float,
        leverage: int
    ) -> float:
        """
        Calculate position size based on capital and leverage

        Uses 20% of capital as max margin per position.

        Args:
            capital: Available capital
            price: Current price
            leverage: Leverage multiplier

        Returns:
            Position size in asset units
        """
        max_margin = capital * 0.20  # 20% max position size
        notional = max_margin * leverage
        size = notional / price
        return size

    def _build_equity_curves(
        self,
        trades: List[LeveragedTrade],
        data: pd.DataFrame,
        initial_capital: float
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Build equity curve tracking margin-based returns

        Args:
            trades: List of trades
            data: OHLCV data for timestamps
            initial_capital: Starting capital

        Returns:
            (equity_curve, margin_curve) as Series
        """
        n = len(data)
        equity = np.full(n, initial_capital, dtype=float)
        margin_used = np.zeros(n, dtype=float)

        cumulative_pnl = 0.0

        for trade in trades:
            entry_idx = trade.entry_idx
            exit_idx = trade.exit_idx

            # During trade: track margin in use
            for i in range(entry_idx, min(exit_idx + 1, n)):
                margin_used[i] += trade.margin

                # Calculate unrealized PnL at each bar
                if i < len(data):
                    current_price = data['close'].iloc[i]
                    if trade.direction == 'long':
                        unrealized = (current_price - trade.entry_price) * trade.size
                    else:
                        unrealized = (trade.entry_price - current_price) * trade.size

                    # Update equity with unrealized PnL
                    equity[i] = initial_capital + cumulative_pnl + unrealized

            # After trade closes: add realized PnL
            cumulative_pnl += trade.pnl_dollars

            # Update equity after trade closes
            for i in range(exit_idx, n):
                equity[i] = initial_capital + cumulative_pnl

        return (
            pd.Series(equity, index=data.index),
            pd.Series(margin_used, index=data.index)
        )

    def _build_portfolio_equity_curve(
        self,
        trades: List[LeveragedTrade],
        index: pd.Index,
        initial_capital: float
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Build portfolio equity curve with multiple concurrent positions

        Args:
            trades: All trades sorted by entry time
            index: Unified time index
            initial_capital: Starting capital

        Returns:
            (equity_curve, margin_curve)
        """
        n = len(index)
        equity = np.full(n, initial_capital, dtype=float)
        margin_used = np.zeros(n, dtype=float)

        # Track realized PnL
        realized_pnl = 0.0

        # Process each time point
        for i in range(n):
            unrealized_pnl = 0.0
            margin_at_i = 0.0

            for trade in trades:
                # Check if trade is active at this index
                if trade.entry_idx <= i < trade.exit_idx:
                    margin_at_i += trade.margin
                    # Would need price data to calculate unrealized PnL
                    # For simplicity, assume flat during trade

                # Check if trade just closed
                if trade.exit_idx == i:
                    realized_pnl += trade.pnl_dollars

            margin_used[i] = margin_at_i
            equity[i] = initial_capital + realized_pnl + unrealized_pnl

        return (
            pd.Series(equity, index=index),
            pd.Series(margin_used, index=index)
        )

    def _build_unified_index(self, data: Dict[str, pd.DataFrame]) -> pd.Index:
        """
        Build unified time index from multiple symbol data

        Args:
            data: Dict mapping symbol -> DataFrame

        Returns:
            Unified index covering all timestamps
        """
        all_indices = []
        for df in data.values():
            all_indices.extend(df.index.tolist())

        return pd.Index(sorted(set(all_indices)))

    def _calculate_metrics(
        self,
        trades: List[LeveragedTrade],
        equity_curve: pd.Series,
        margin_curve: pd.Series
    ) -> Dict:
        """
        Calculate comprehensive metrics from leveraged data

        Args:
            trades: List of trades
            equity_curve: Equity values over time
            margin_curve: Margin used over time

        Returns:
            Metrics dictionary
        """
        if not trades:
            return self._empty_results()

        # Basic trade stats
        n_trades = len(trades)
        winning_trades = [t for t in trades if t.pnl_dollars > 0]
        losing_trades = [t for t in trades if t.pnl_dollars <= 0]

        win_rate = len(winning_trades) / n_trades if n_trades > 0 else 0.0

        # PnL stats
        total_pnl = sum(t.pnl_dollars for t in trades)
        avg_pnl = total_pnl / n_trades if n_trades > 0 else 0.0

        # Profit factor
        gross_profit = sum(t.pnl_dollars for t in winning_trades)
        gross_loss = abs(sum(t.pnl_dollars for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Returns on margin (leveraged returns)
        returns_on_margin = [t.return_on_margin for t in trades]
        avg_return = np.mean(returns_on_margin) if returns_on_margin else 0.0

        # Total return
        initial_capital = equity_curve.iloc[0]
        final_capital = equity_curve.iloc[-1]
        total_return = (final_capital - initial_capital) / initial_capital

        # Sharpe ratio (on equity curve daily returns)
        equity_returns = equity_curve.pct_change().dropna()
        if len(equity_returns) > 1 and equity_returns.std() > 0:
            sharpe = equity_returns.mean() / equity_returns.std() * np.sqrt(252)
        else:
            sharpe = 0.0

        # Sortino ratio
        downside_returns = equity_returns[equity_returns < 0]
        if len(downside_returns) > 1 and downside_returns.std() > 0:
            sortino = equity_returns.mean() / downside_returns.std() * np.sqrt(252)
        else:
            sortino = 0.0

        # Maximum drawdown
        max_dd = self._calculate_max_drawdown(equity_curve)

        # Expectancy
        expectancy = avg_pnl

        # ED ratio
        ed_ratio = expectancy / abs(max_dd) if max_dd != 0 else 0.0

        # Consistency (% time in profit)
        in_profit = (equity_curve > initial_capital).sum()
        consistency = in_profit / len(equity_curve) if len(equity_curve) > 0 else 0.0

        # Average leverage used
        avg_leverage = np.mean([t.leverage for t in trades]) if trades else 1.0

        # Max margin used
        max_margin_used = margin_curve.max()
        max_margin_pct = max_margin_used / initial_capital if initial_capital > 0 else 0.0

        return {
            # Returns
            'total_return': float(total_return),
            'total_pnl': float(total_pnl),

            # Risk-adjusted
            'sharpe_ratio': float(sharpe),
            'sortino_ratio': float(sortino),
            'max_drawdown': float(max_dd),

            # Trade stats
            'total_trades': n_trades,
            'win_rate': float(win_rate),
            'expectancy': float(expectancy),
            'profit_factor': float(profit_factor) if profit_factor != float('inf') else 999.0,

            # Custom
            'ed_ratio': float(ed_ratio),
            'consistency': float(consistency),

            # Leverage info
            'avg_leverage': float(avg_leverage),
            'max_margin_used': float(max_margin_used),
            'max_margin_pct': float(max_margin_pct),

            # Per-trade return stats
            'avg_return_on_margin': float(avg_return),
            'avg_pnl_per_trade': float(avg_pnl),
        }

    def _calculate_max_drawdown(self, equity_curve: pd.Series) -> float:
        """
        Calculate maximum drawdown from equity curve

        Args:
            equity_curve: Equity values over time

        Returns:
            Maximum drawdown as decimal (e.g., 0.15 for 15%)
        """
        if len(equity_curve) == 0:
            return 0.0

        # Calculate running maximum
        running_max = equity_curve.expanding().max()

        # Calculate drawdown at each point
        drawdown = (equity_curve - running_max) / running_max

        # Return maximum drawdown (most negative value)
        return float(drawdown.min())

    def _calculate_symbol_breakdown(
        self,
        trades: List[LeveragedTrade]
    ) -> Dict[str, Dict]:
        """
        Calculate per-symbol statistics

        Args:
            trades: All trades

        Returns:
            Dict mapping symbol -> metrics
        """
        breakdown = {}

        # Group trades by symbol
        symbols = set(t.symbol for t in trades)

        for symbol in symbols:
            symbol_trades = [t for t in trades if t.symbol == symbol]

            n_trades = len(symbol_trades)
            winning = len([t for t in symbol_trades if t.pnl_dollars > 0])
            total_pnl = sum(t.pnl_dollars for t in symbol_trades)
            avg_leverage = np.mean([t.leverage for t in symbol_trades])

            breakdown[symbol] = {
                'total_trades': n_trades,
                'win_rate': winning / n_trades if n_trades > 0 else 0.0,
                'total_pnl': total_pnl,
                'avg_leverage': avg_leverage,
            }

        return breakdown

    def _trade_to_dict(self, trade: LeveragedTrade) -> Dict:
        """Convert trade to dictionary"""
        return {
            'symbol': trade.symbol,
            'entry_idx': trade.entry_idx,
            'exit_idx': trade.exit_idx,
            'entry_price': trade.entry_price,
            'exit_price': trade.exit_price,
            'size': trade.size,
            'direction': trade.direction,
            'leverage': trade.leverage,
            'notional': trade.notional,
            'margin': trade.margin,
            'pnl': trade.pnl_dollars,
            'return_on_margin': trade.return_on_margin,
        }

    def _empty_results(self) -> Dict:
        """Return empty results structure"""
        return {
            'total_return': 0.0,
            'total_pnl': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0,
            'max_drawdown': 0.0,
            'total_trades': 0,
            'win_rate': 0.0,
            'expectancy': 0.0,
            'profit_factor': 0.0,
            'ed_ratio': 0.0,
            'consistency': 0.0,
            'avg_leverage': 1.0,
            'max_margin_used': 0.0,
            'max_margin_pct': 0.0,
            'avg_return_on_margin': 0.0,
            'avg_pnl_per_trade': 0.0,
            'trades': [],
        }


# Convenience function for quick testing
def run_leveraged_backtest(
    strategy: StrategyCore,
    data: pd.DataFrame,
    symbol: str = 'BTC',
    leverage: int = 1,
    initial_capital: float = 10000
) -> Dict:
    """
    Quick function to run a leveraged backtest

    Args:
        strategy: StrategyCore instance
        data: OHLCV DataFrame
        symbol: Symbol name
        leverage: Leverage to use
        initial_capital: Starting capital

    Returns:
        Metrics dictionary
    """
    config = load_config()
    config._raw_config['backtesting']['initial_capital'] = initial_capital

    backtester = LeveragedBacktester(config)
    return backtester.backtest(strategy, data, symbol, leverage_override=leverage)
