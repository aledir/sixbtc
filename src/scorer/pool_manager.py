"""
ACTIVE Pool Manager - Leaderboard Logic

Manages the ACTIVE strategy pool with leaderboard logic:
- Pool has max_size limit (default 300)
- New strategies enter if score >= min_score_entry AND (pool not full OR score > min(pool))
- Lowest scoring strategy is evicted when pool is full and better strategy arrives

Single Responsibility: Manage pool membership (no scoring, no deployment)
"""

from datetime import datetime, UTC
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import func

from src.database import get_session
from src.database.models import Strategy, BacktestResult
from src.scorer.backtest_scorer import BacktestScorer
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PoolManager:
    """
    Manages ACTIVE pool membership using leaderboard logic.

    Rules:
    1. Score < min_score_entry -> RETIRED (never enters pool)
    2. Pool not full AND score >= min_score_entry -> enters pool
    3. Pool full AND score > min(pool) -> evict worst, enter pool
    4. Pool full AND score <= min(pool) -> RETIRED (doesn't enter)
    """

    def __init__(self, config: dict):
        """
        Initialize pool manager.

        Args:
            config: Configuration dict with 'active_pool' section
        """
        pool_config = config['active_pool']
        self.max_size = pool_config['max_size']
        self.min_score_entry = pool_config['min_score_entry']

        self.scorer = BacktestScorer(config)

        logger.info(
            f"PoolManager initialized: max_size={self.max_size}, "
            f"min_score_entry={self.min_score_entry}"
        )

    def get_pool_stats(self) -> dict:
        """
        Get current pool statistics.

        Returns:
            Dict with pool stats: count, min_score, max_score, avg_score
        """
        with get_session() as session:
            stats = (
                session.query(
                    func.count(Strategy.id).label('count'),
                    func.min(Strategy.score_backtest).label('min_score'),
                    func.max(Strategy.score_backtest).label('max_score'),
                    func.avg(Strategy.score_backtest).label('avg_score')
                )
                .filter(Strategy.status == 'ACTIVE')
                .first()
            )

            return {
                'count': stats.count or 0,
                'min_score': stats.min_score,
                'max_score': stats.max_score,
                'avg_score': float(stats.avg_score) if stats.avg_score else None,
                'available_slots': self.max_size - (stats.count or 0)
            }

    def get_min_score_in_pool(self) -> Optional[float]:
        """
        Get the minimum score currently in the ACTIVE pool.

        Returns:
            Minimum score or None if pool is empty
        """
        with get_session() as session:
            result = (
                session.query(func.min(Strategy.score_backtest))
                .filter(Strategy.status == 'ACTIVE')
                .scalar()
            )
            return result

    def get_worst_strategy_in_pool(self) -> Optional[Tuple[UUID, str, float]]:
        """
        Get the worst-performing strategy in the ACTIVE pool.

        Returns:
            Tuple of (id, name, score) or None if pool is empty
        """
        with get_session() as session:
            strategy = (
                session.query(Strategy)
                .filter(Strategy.status == 'ACTIVE')
                .order_by(Strategy.score_backtest.asc())
                .first()
            )

            if strategy:
                return (strategy.id, strategy.name, strategy.score_backtest)
            return None

    def try_enter_pool(self, strategy_id: UUID, score: float) -> Tuple[bool, str]:
        """
        Attempt to enter a strategy into the ACTIVE pool.

        Args:
            strategy_id: Strategy UUID
            score: Pre-calculated backtest score

        Returns:
            Tuple of (success: bool, reason: str)
        """
        # Rule 1: Score below minimum threshold
        if score < self.min_score_entry:
            self._retire_strategy(strategy_id, f"score {score:.1f} < threshold {self.min_score_entry}")
            return False, f"Score {score:.1f} below minimum {self.min_score_entry}"

        with get_session() as session:
            # Get current pool count
            pool_count = (
                session.query(func.count(Strategy.id))
                .filter(Strategy.status == 'ACTIVE')
                .scalar()
            ) or 0

            # Rule 2: Pool not full
            if pool_count < self.max_size:
                self._activate_strategy(strategy_id, score)
                return True, f"Pool not full ({pool_count}/{self.max_size})"

            # Rule 3 & 4: Pool full - check if better than worst
            worst = self.get_worst_strategy_in_pool()
            if worst is None:
                # Edge case: pool count says full but no strategies found
                self._activate_strategy(strategy_id, score)
                return True, "Pool was empty"

            worst_id, worst_name, worst_score = worst

            if score > worst_score:
                # Evict worst and enter
                self._retire_strategy(worst_id, f"evicted by {strategy_id} (score {worst_score:.1f} < {score:.1f})")
                self._activate_strategy(strategy_id, score)
                logger.info(
                    f"Leaderboard: evicted {worst_name} (score={worst_score:.1f}), "
                    f"admitted strategy {strategy_id} (score={score:.1f})"
                )
                return True, f"Evicted {worst_name} (score {worst_score:.1f})"

            # Rule 4: Not good enough
            self._retire_strategy(strategy_id, f"score {score:.1f} <= pool minimum {worst_score:.1f}")
            return False, f"Score {score:.1f} <= pool minimum {worst_score:.1f}"

    def _activate_strategy(self, strategy_id: UUID, score: float):
        """Set strategy to ACTIVE status with score."""
        with get_session() as session:
            strategy = session.query(Strategy).filter(Strategy.id == strategy_id).first()
            if strategy:
                strategy.status = 'ACTIVE'
                strategy.score_backtest = score
                strategy.last_backtested_at = datetime.now(UTC)
                session.commit()
                logger.info(f"Strategy {strategy.name} entered ACTIVE pool (score={score:.1f})")

    def _retire_strategy(self, strategy_id: UUID, reason: str):
        """Set strategy to RETIRED status."""
        with get_session() as session:
            strategy = session.query(Strategy).filter(Strategy.id == strategy_id).first()
            if strategy:
                strategy.status = 'RETIRED'
                strategy.retired_at = datetime.now(UTC)
                session.commit()
                logger.info(f"Strategy {strategy.name} RETIRED: {reason}")

    def revalidate_after_retest(self, strategy_id: UUID, new_score: float) -> Tuple[bool, str]:
        """
        Revalidate a strategy after re-backtest.

        Called when an ACTIVE strategy is re-tested and gets a new score.
        If new score drops below threshold or pool minimum, strategy is retired.

        Args:
            strategy_id: Strategy UUID
            new_score: New backtest score after re-test

        Returns:
            Tuple of (still_active: bool, reason: str)
        """
        # Check threshold
        if new_score < self.min_score_entry:
            self._retire_strategy(strategy_id, f"re-test score {new_score:.1f} < threshold {self.min_score_entry}")
            return False, f"Score dropped below threshold ({new_score:.1f} < {self.min_score_entry})"

        with get_session() as session:
            strategy = session.query(Strategy).filter(Strategy.id == strategy_id).first()
            if not strategy:
                return False, "Strategy not found"

            # Get pool stats (excluding this strategy)
            pool_count = (
                session.query(func.count(Strategy.id))
                .filter(Strategy.status == 'ACTIVE')
                .filter(Strategy.id != strategy_id)
                .scalar()
            ) or 0

            # If pool would still be full without this strategy, check if it's still competitive
            if pool_count >= self.max_size:
                min_other_score = (
                    session.query(func.min(Strategy.score_backtest))
                    .filter(Strategy.status == 'ACTIVE')
                    .filter(Strategy.id != strategy_id)
                    .scalar()
                )

                if min_other_score and new_score < min_other_score:
                    self._retire_strategy(
                        strategy_id,
                        f"re-test score {new_score:.1f} < pool minimum {min_other_score:.1f}"
                    )
                    return False, f"Score dropped below pool minimum ({new_score:.1f} < {min_other_score:.1f})"

            # Update score and last_backtested_at
            strategy.score_backtest = new_score
            strategy.last_backtested_at = datetime.now(UTC)
            session.commit()

            logger.info(f"Strategy {strategy.name} re-validated in ACTIVE pool (new score={new_score:.1f})")
            return True, f"Re-validated with score {new_score:.1f}"
