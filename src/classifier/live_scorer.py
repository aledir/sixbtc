"""
Live Performance Scorer

Calculates performance metrics from live Trade records.
Used for dual-ranking system (backtest vs live).
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
import numpy as np

from src.database import get_session
from src.database.models import Strategy, Trade, BacktestResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LiveScorer:
    """
    Calculates live performance metrics from Trade records.

    Mirrors the scoring formula from StrategyScorer but uses
    actual trading data instead of backtest results.
    """

    def __init__(self, config: dict):
        """
        Initialize live scorer

        Args:
            config: Configuration dict with 'classification.live_ranking' section
        """
        live_config = config.get('classification', {}).get('live_ranking', {})
        self.min_trades = live_config.get('min_trades_live', 10)

        # Scoring weights (same as backtest scorer)
        weights_config = config.get('classification', {}).get('score_weights', {})
        self.weights = {
            'edge': weights_config.get('edge', 0.50),
            'sharpe': weights_config.get('sharpe', 0.25),
            'consistency': weights_config.get('consistency', 0.15),
            'stability': weights_config.get('stability', 0.10)
        }

        logger.info(
            f"LiveScorer initialized: min_trades={self.min_trades}, "
            f"weights={self.weights}"
        )

    def calculate_live_metrics(self, strategy_id: UUID) -> Optional[Dict]:
        """
        Calculate live performance metrics from Trade records.

        Args:
            strategy_id: Strategy UUID

        Returns:
            Dict with metrics or None if insufficient data:
            {
                'total_trades': int,
                'win_rate': float,
                'expectancy': float,
                'sharpe': float,
                'max_drawdown': float,
                'total_pnl': float,
                'score': float (0-100)
            }
        """
        with get_session() as session:
            trades = (
                session.query(Trade)
                .filter(
                    Trade.strategy_id == strategy_id,
                    Trade.exit_time.isnot(None)  # Only closed trades
                )
                .order_by(Trade.exit_time.asc())
                .all()
            )

            if len(trades) < self.min_trades:
                logger.debug(
                    f"Strategy {strategy_id}: {len(trades)} trades < "
                    f"min {self.min_trades}"
                )
                return None

            # Extract PnL values
            pnls = [t.pnl_usd for t in trades if t.pnl_usd is not None]
            pnl_pcts = [t.pnl_pct for t in trades if t.pnl_pct is not None]

            if not pnls:
                return None

            # Calculate metrics
            total_trades = len(trades)
            wins = [p for p in pnls if p > 0]
            win_rate = len(wins) / total_trades if total_trades > 0 else 0

            # Expectancy = average profit per trade (as percentage)
            expectancy = np.mean(pnl_pcts) if pnl_pcts else 0

            # Total PnL
            total_pnl = sum(pnls)

            # Sharpe ratio from returns
            sharpe = self._calculate_sharpe(pnl_pcts)

            # Max drawdown from equity curve
            max_drawdown = self._calculate_max_drawdown(pnls)

            # Composite score (same formula as backtest)
            score = self._calculate_score(
                expectancy=expectancy,
                sharpe=sharpe,
                win_rate=win_rate,
                max_drawdown=max_drawdown
            )

            return {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'expectancy': expectancy,
                'sharpe': sharpe,
                'max_drawdown': max_drawdown,
                'total_pnl': total_pnl,
                'score': score
            }

    def _calculate_sharpe(self, returns: List[float]) -> float:
        """
        Calculate Sharpe ratio from trade returns.

        Uses trade-by-trade returns, annualized assuming 252 trading days.
        """
        if len(returns) < 2:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        if std_return == 0:
            return 0.0

        # Annualize: assume ~1 trade per day on average
        sharpe = (mean_return / std_return) * np.sqrt(252)
        return float(sharpe)

    def _calculate_max_drawdown(self, pnls: List[float]) -> float:
        """
        Calculate maximum drawdown from PnL series.

        Returns:
            Max drawdown as positive float (e.g., 0.15 = 15% drawdown)
        """
        if not pnls:
            return 0.0

        # Build equity curve
        equity = np.cumsum(pnls)

        # Calculate running maximum
        running_max = np.maximum.accumulate(equity)

        # Drawdown at each point
        drawdowns = running_max - equity

        # Max drawdown as percentage of peak
        max_dd = 0.0
        for i, dd in enumerate(drawdowns):
            if running_max[i] > 0:
                dd_pct = dd / running_max[i]
                max_dd = max(max_dd, dd_pct)

        return float(max_dd)

    def _calculate_score(
        self,
        expectancy: float,
        sharpe: float,
        win_rate: float,
        max_drawdown: float
    ) -> float:
        """
        Calculate composite score using same formula as backtest scorer.

        Score = (0.50 x Edge) + (0.25 x Sharpe) + (0.15 x Consistency) + (0.10 x Stability)

        Args:
            expectancy: Average return per trade (%)
            sharpe: Sharpe ratio
            win_rate: Win rate (0-1)
            max_drawdown: Max drawdown (0-1)

        Returns:
            Score 0-100
        """
        # Normalize edge (expectancy): typical range 0-10%
        edge_score = self._normalize(expectancy, 0, 0.10)

        # Normalize Sharpe: typical range 0-3
        sharpe_score = self._normalize(sharpe, 0, 3.0)

        # Consistency: use win_rate directly (already 0-1)
        consistency_score = win_rate

        # Stability: inverse of drawdown (lower DD = higher stability)
        stability_score = 1 - min(max_drawdown, 1.0)

        # Weighted sum
        score = (
            self.weights['edge'] * edge_score +
            self.weights['sharpe'] * sharpe_score +
            self.weights['consistency'] * consistency_score +
            self.weights['stability'] * stability_score
        )

        # Scale to 0-100
        return min(max(score * 100, 0), 100)

    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize value to 0-1 range"""
        if max_val == min_val:
            return 0
        normalized = (value - min_val) / (max_val - min_val)
        return min(max(normalized, 0), 1)

    def update_strategy_live_metrics(self, strategy_id: UUID) -> bool:
        """
        Calculate and update live metrics for a strategy.

        Args:
            strategy_id: Strategy UUID

        Returns:
            True if updated, False if insufficient data
        """
        metrics = self.calculate_live_metrics(strategy_id)

        if metrics is None:
            return False

        with get_session() as session:
            strategy = session.query(Strategy).filter(
                Strategy.id == strategy_id
            ).first()

            if not strategy:
                logger.warning(f"Strategy {strategy_id} not found")
                return False

            # Update live metrics
            strategy.score_live = metrics['score']
            strategy.win_rate_live = metrics['win_rate']
            strategy.expectancy_live = metrics['expectancy']
            strategy.sharpe_live = metrics['sharpe']
            strategy.max_drawdown_live = metrics['max_drawdown']
            strategy.total_trades_live = metrics['total_trades']
            strategy.total_pnl_live = metrics['total_pnl']
            strategy.last_live_update = datetime.utcnow()

            # Calculate degradation vs backtest
            if strategy.score_backtest and strategy.score_backtest > 0:
                strategy.live_degradation_pct = (
                    (strategy.score_backtest - metrics['score'])
                    / strategy.score_backtest
                )
            else:
                strategy.live_degradation_pct = None

            logger.info(
                f"Updated live metrics for {strategy.name}: "
                f"score={metrics['score']:.1f}, trades={metrics['total_trades']}, "
                f"win_rate={metrics['win_rate']:.1%}, pnl=${metrics['total_pnl']:.2f}"
            )

        return True

    def update_all_live_strategies(self) -> Dict:
        """
        Update live metrics for all LIVE strategies.

        Returns:
            Dict with update results:
            {
                'updated': int,
                'skipped': int (insufficient data),
                'failed': int
            }
        """
        results = {'updated': 0, 'skipped': 0, 'failed': 0}

        with get_session() as session:
            live_strategies = (
                session.query(Strategy)
                .filter(Strategy.status == 'LIVE')
                .all()
            )
            strategy_ids = [s.id for s in live_strategies]

        for strategy_id in strategy_ids:
            try:
                if self.update_strategy_live_metrics(strategy_id):
                    results['updated'] += 1
                else:
                    results['skipped'] += 1
            except Exception as e:
                logger.error(f"Failed to update {strategy_id}: {e}")
                results['failed'] += 1

        logger.info(
            f"Live metrics update complete: "
            f"{results['updated']} updated, {results['skipped']} skipped, "
            f"{results['failed']} failed"
        )

        return results
