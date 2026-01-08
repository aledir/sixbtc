"""
Strategy Selector - Select Top Strategies for Deployment

Single Responsibility: Select best strategies from ACTIVE pool with diversification.

Selection criteria:
- Score >= min_score (from active_pool config - single threshold)
- Diversification: max N per type, max M per timeframe
- Not already in LIVE status
"""

from collections import defaultdict
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func

from src.database import get_session
from src.database.models import Strategy, BacktestResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class StrategySelector:
    """
    Selects top strategies from ACTIVE pool for deployment.

    Single Responsibility: Selection only (no deployment, no scoring).
    """

    def __init__(self, config: dict):
        """
        Initialize selector with config.

        Args:
            config: Configuration dict with 'rotator' and 'active_pool' sections

        Raises:
            KeyError: If required config sections are missing (Fast Fail)
        """
        rotator_config = config['rotator']

        # Single threshold: all ACTIVE strategies are LIVE eligible
        # min_score comes from active_pool (single source of truth)
        self.min_score = config['active_pool']['min_score']
        self.max_live_strategies = rotator_config['max_live_strategies']
        self.min_pool_size = rotator_config.get('min_pool_size', 0)

        # Diversification constraints
        selection_config = rotator_config['selection']
        self.max_per_type = selection_config['max_per_type']
        self.max_per_timeframe = selection_config['max_per_timeframe']

        logger.info(
            f"StrategySelector initialized: min_score={self.min_score}, "
            f"max_live={self.max_live_strategies}, min_pool={self.min_pool_size}, "
            f"max_per_type={self.max_per_type}, max_per_timeframe={self.max_per_timeframe}"
        )

    def get_candidates(self, slots_available: int) -> List[Dict]:
        """
        Get top candidates from ACTIVE pool for deployment.

        Applies:
        1. Score threshold (>= min_score from active_pool)
        2. Diversification constraints (type, timeframe)
        3. Sorts by score descending

        Args:
            slots_available: Number of free LIVE slots

        Returns:
            List of candidate strategy dicts, up to slots_available
        """
        if slots_available <= 0:
            return []

        with get_session() as session:
            # Get ACTIVE strategies with score >= threshold
            eligible = (
                session.query(Strategy)
                .filter(Strategy.status == 'ACTIVE')
                .filter(Strategy.score_backtest >= self.min_score)
                .order_by(Strategy.score_backtest.desc())
                .all()
            )

            if not eligible:
                logger.debug("No ACTIVE strategies meet score threshold")
                return []

            # Get current LIVE strategies for diversification check
            live_strategies = (
                session.query(Strategy)
                .filter(Strategy.status == 'LIVE')
                .all()
            )

            # Count existing LIVE by type and timeframe
            type_counts = defaultdict(int)
            tf_counts = defaultdict(int)
            for s in live_strategies:
                if s.strategy_type:
                    type_counts[s.strategy_type] += 1
                if s.optimal_timeframe:
                    tf_counts[s.optimal_timeframe] += 1

            # Select with diversification
            candidates = []
            for strategy in eligible:
                if len(candidates) >= slots_available:
                    break

                strategy_type = strategy.strategy_type or 'UNKNOWN'
                timeframe = strategy.optimal_timeframe or 'UNKNOWN'

                # Check diversification constraints
                if type_counts[strategy_type] >= self.max_per_type:
                    logger.debug(
                        f"Skipped {strategy.name}: max {self.max_per_type} "
                        f"strategies of type {strategy_type}"
                    )
                    continue

                if tf_counts[timeframe] >= self.max_per_timeframe:
                    logger.debug(
                        f"Skipped {strategy.name}: max {self.max_per_timeframe} "
                        f"strategies on timeframe {timeframe}"
                    )
                    continue

                # Add to candidates
                candidates.append({
                    'id': strategy.id,
                    'name': strategy.name,
                    'strategy_type': strategy_type,
                    'timeframe': timeframe,
                    'score': strategy.score_backtest,
                    'code': strategy.code,
                    'backtest_pairs': strategy.backtest_pairs,
                })

                # Update counts for next iteration
                type_counts[strategy_type] += 1
                tf_counts[timeframe] += 1

                logger.debug(
                    f"Candidate: {strategy.name} (type={strategy_type}, "
                    f"tf={timeframe}, score={strategy.score_backtest:.1f})"
                )

            logger.info(
                f"Selected {len(candidates)} candidates from {len(eligible)} eligible "
                f"(slots={slots_available})"
            )

            return candidates

    def get_live_count(self) -> int:
        """Get current count of LIVE strategies."""
        with get_session() as session:
            return (
                session.query(func.count(Strategy.id))
                .filter(Strategy.status == 'LIVE')
                .scalar()
            ) or 0

    def get_free_slots(self) -> int:
        """Get number of free LIVE slots."""
        live_count = self.get_live_count()
        return max(0, self.max_live_strategies - live_count)

    def get_active_count(self) -> int:
        """Get current count of ACTIVE strategies in pool."""
        with get_session() as session:
            return (
                session.query(func.count(Strategy.id))
                .filter(Strategy.status == 'ACTIVE')
                .scalar()
            ) or 0

    def is_pool_ready(self) -> bool:
        """
        Check if ACTIVE pool has minimum required strategies.

        Returns:
            True if pool has >= min_pool_size strategies
        """
        if self.min_pool_size <= 0:
            return True
        return self.get_active_count() >= self.min_pool_size

    def get_selection_stats(self) -> Dict:
        """
        Get current selection statistics.

        Returns:
            Dict with active_count, live_count, free_slots, type_distribution
        """
        with get_session() as session:
            active_count = (
                session.query(func.count(Strategy.id))
                .filter(Strategy.status == 'ACTIVE')
                .scalar()
            ) or 0

            live_count = (
                session.query(func.count(Strategy.id))
                .filter(Strategy.status == 'LIVE')
                .scalar()
            ) or 0

            # Type distribution for LIVE
            live_strategies = (
                session.query(Strategy)
                .filter(Strategy.status == 'LIVE')
                .all()
            )

            type_dist = defaultdict(int)
            tf_dist = defaultdict(int)
            for s in live_strategies:
                if s.strategy_type:
                    type_dist[s.strategy_type] += 1
                if s.optimal_timeframe:
                    tf_dist[s.optimal_timeframe] += 1

            return {
                'active_count': active_count,
                'live_count': live_count,
                'max_live': self.max_live_strategies,
                'min_pool_size': self.min_pool_size,
                'pool_ready': active_count >= self.min_pool_size if self.min_pool_size > 0 else True,
                'free_slots': max(0, self.max_live_strategies - live_count),
                'type_distribution': dict(type_dist),
                'timeframe_distribution': dict(tf_dist),
            }
