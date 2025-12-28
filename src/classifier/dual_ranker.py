"""
Dual Ranker - Manages separate Backtest and Live rankings

Provides two independent rankings:
1. BACKTEST ranking - for selecting strategies to deploy
2. LIVE ranking - for monitoring and retirement decisions
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from src.database import get_session
from src.database.models import Strategy, BacktestResult
from src.classifier.live_scorer import LiveScorer
from src.classifier.scorer import StrategyScorer
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DualRanker:
    """
    Manages dual ranking system for backtest and live performance.

    Backtest ranking: Used for selecting strategies to deploy
    Live ranking: Used for monitoring and retirement decisions
    """

    def __init__(self, config: dict):
        """
        Initialize dual ranker

        Args:
            config: Configuration dict with 'classification' section
        """
        self.config = config
        self.live_scorer = LiveScorer(config)
        self.backtest_scorer = StrategyScorer(config)

        # Live ranking config
        live_config = config.get('classification', {}).get('live_ranking', {})
        self.retire_threshold = live_config.get('retire_score_threshold', 30)
        self.max_degradation = live_config.get('max_degradation_pct', 0.50)
        self.max_drawdown_live = live_config.get('max_drawdown_live', 0.30)
        self.min_trades_live = live_config.get('min_trades_live', 10)

        logger.info(
            f"DualRanker initialized: retire_threshold={self.retire_threshold}, "
            f"max_degradation={self.max_degradation:.0%}, "
            f"max_drawdown={self.max_drawdown_live:.0%}"
        )

    def get_backtest_ranking(self, limit: int = 50) -> List[Dict]:
        """
        Get backtest ranking for TESTED and SELECTED strategies.

        Ordered by score_backtest (or calculated on the fly if not cached).

        Args:
            limit: Maximum number of strategies to return

        Returns:
            List of strategy dicts with ranking info
        """
        with get_session() as session:
            # Get strategies with their backtest results
            results = (
                session.query(Strategy, BacktestResult)
                .join(BacktestResult, Strategy.id == BacktestResult.strategy_id)
                .filter(Strategy.status.in_(['TESTED', 'SELECTED']))
                .order_by(BacktestResult.sharpe_ratio.desc())
                .limit(limit * 2)  # Get more to filter
                .all()
            )

            ranking = []
            for strategy, backtest in results:
                # Calculate score if not cached
                if strategy.score_backtest is None:
                    metrics = {
                        'expectancy': backtest.expectancy or 0,
                        'sharpe_ratio': backtest.sharpe_ratio or 0,
                        'consistency': backtest.win_rate or 0,
                        'wf_stability': backtest.walk_forward_stability or 0
                    }
                    score = self.backtest_scorer.score(metrics)

                    # Cache it
                    strategy.score_backtest = score
                else:
                    score = strategy.score_backtest

                ranking.append({
                    'id': strategy.id,
                    'name': strategy.name,
                    'strategy_type': strategy.strategy_type,
                    'timeframe': strategy.timeframe,
                    'status': strategy.status,
                    'score': score,
                    'sharpe': backtest.sharpe_ratio,
                    'expectancy': backtest.expectancy,
                    'win_rate': backtest.win_rate,
                    'total_trades': backtest.total_trades,
                    'max_drawdown': backtest.max_drawdown,
                    'ranking_type': 'backtest'
                })

        # Sort by score and limit
        ranking.sort(key=lambda x: x['score'] or 0, reverse=True)
        return ranking[:limit]

    def get_live_ranking(self, limit: int = 20) -> List[Dict]:
        """
        Get live ranking for LIVE strategies.

        Ordered by score_live (calculated from actual trades).

        Args:
            limit: Maximum number of strategies to return

        Returns:
            List of strategy dicts with live ranking info
        """
        with get_session() as session:
            strategies = (
                session.query(Strategy)
                .filter(
                    Strategy.status == 'LIVE',
                    Strategy.total_trades_live >= self.min_trades_live
                )
                .order_by(Strategy.score_live.desc().nullslast())
                .limit(limit)
                .all()
            )

            ranking = []
            for strategy in strategies:
                ranking.append({
                    'id': strategy.id,
                    'name': strategy.name,
                    'strategy_type': strategy.strategy_type,
                    'timeframe': strategy.timeframe,
                    'status': strategy.status,
                    'score': strategy.score_live,
                    'score_backtest': strategy.score_backtest,
                    'sharpe': strategy.sharpe_live,
                    'expectancy': strategy.expectancy_live,
                    'win_rate': strategy.win_rate_live,
                    'total_trades': strategy.total_trades_live,
                    'max_drawdown': strategy.max_drawdown_live,
                    'total_pnl': strategy.total_pnl_live,
                    'degradation_pct': strategy.live_degradation_pct,
                    'last_update': strategy.last_live_update,
                    'ranking_type': 'live'
                })

        return ranking

    def check_retirement_candidates(self) -> List[Dict]:
        """
        Find LIVE strategies that should be retired.

        Retirement criteria:
        1. score_live < retire_threshold (default 30)
        2. live_degradation_pct > max_degradation (default 50%)
        3. max_drawdown_live > max_drawdown_live (default 30%)

        Returns:
            List of dicts with strategy and reason
        """
        candidates = []

        with get_session() as session:
            live_strategies = (
                session.query(Strategy)
                .filter(
                    Strategy.status == 'LIVE',
                    Strategy.total_trades_live >= self.min_trades_live
                )
                .all()
            )

            for strategy in live_strategies:
                should_retire, reason = self._check_retire(strategy)
                if should_retire:
                    candidates.append({
                        'id': strategy.id,
                        'name': strategy.name,
                        'reason': reason,
                        'score_live': strategy.score_live,
                        'score_backtest': strategy.score_backtest,
                        'degradation_pct': strategy.live_degradation_pct,
                        'max_drawdown': strategy.max_drawdown_live,
                        'total_pnl': strategy.total_pnl_live
                    })

        if candidates:
            logger.warning(
                f"Found {len(candidates)} retirement candidates: "
                f"{[c['name'] for c in candidates]}"
            )

        return candidates

    def _check_retire(self, strategy: Strategy) -> Tuple[bool, Optional[str]]:
        """
        Check if a strategy should be retired.

        Args:
            strategy: Strategy model instance

        Returns:
            Tuple of (should_retire: bool, reason: str or None)
        """
        # 1. Score too low
        if strategy.score_live is not None and strategy.score_live < self.retire_threshold:
            return True, f"score_live {strategy.score_live:.1f} < {self.retire_threshold}"

        # 2. Degradation too high
        if strategy.live_degradation_pct is not None and strategy.live_degradation_pct > self.max_degradation:
            return True, f"degradation {strategy.live_degradation_pct:.0%} > {self.max_degradation:.0%}"

        # 3. Drawdown too high
        if strategy.max_drawdown_live is not None and strategy.max_drawdown_live > self.max_drawdown_live:
            return True, f"drawdown {strategy.max_drawdown_live:.0%} > {self.max_drawdown_live:.0%}"

        return False, None

    def retire_strategy(self, strategy_id: UUID, reason: str) -> bool:
        """
        Retire a strategy (set status to RETIRED).

        Args:
            strategy_id: Strategy UUID
            reason: Reason for retirement

        Returns:
            True if retired, False if not found
        """
        with get_session() as session:
            strategy = session.query(Strategy).filter(
                Strategy.id == strategy_id
            ).first()

            if not strategy:
                logger.warning(f"Strategy {strategy_id} not found for retirement")
                return False

            old_status = strategy.status
            strategy.status = 'RETIRED'
            strategy.retired_at = datetime.utcnow()

            logger.warning(
                f"RETIRED {strategy.name}: {reason} "
                f"(was {old_status}, score_live={strategy.score_live:.1f})"
            )

        return True

    def get_combined_summary(self) -> Dict:
        """
        Get summary of both rankings.

        Returns:
            Dict with counts and top performers from each ranking
        """
        backtest_ranking = self.get_backtest_ranking(limit=10)
        live_ranking = self.get_live_ranking(limit=10)

        return {
            'backtest': {
                'count': len(backtest_ranking),
                'top_3': backtest_ranking[:3],
                'avg_score': sum(s['score'] or 0 for s in backtest_ranking) / max(len(backtest_ranking), 1)
            },
            'live': {
                'count': len(live_ranking),
                'top_3': live_ranking[:3],
                'avg_score': sum(s['score'] or 0 for s in live_ranking) / max(len(live_ranking), 1),
                'avg_pnl': sum(s.get('total_pnl') or 0 for s in live_ranking) / max(len(live_ranking), 1)
            },
            'retirement_candidates': len(self.check_retirement_candidates())
        }

    def log_rankings(self):
        """Log current rankings to logger"""
        backtest = self.get_backtest_ranking(limit=5)
        live = self.get_live_ranking(limit=5)

        logger.info("=== BACKTEST RANKING (Top 5) ===")
        for i, s in enumerate(backtest, 1):
            logger.info(
                f"  {i}. {s['name']}: score={s['score']:.1f}, "
                f"sharpe={s['sharpe']:.2f}, expect={s['expectancy']:.1%}"
            )

        logger.info("=== LIVE RANKING (Top 5) ===")
        for i, s in enumerate(live, 1):
            degrad = s.get('degradation_pct')
            degrad_str = f", degrad={degrad:.0%}" if degrad else ""
            logger.info(
                f"  {i}. {s['name']}: score={s['score']:.1f}, "
                f"pnl=${s['total_pnl']:.2f}{degrad_str}"
            )
