"""
Performance Tracker - Track Live Strategy Performance

Single Responsibility: Calculate and update live performance metrics for LIVE strategies.

Uses LiveScorer from scorer module for metric calculation.
"""

from datetime import datetime, UTC
from typing import Dict, List, Optional
from uuid import UUID

from src.database import get_session
from src.database.models import Strategy, Trade
from src.scorer import LiveScorer
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PerformanceTracker:
    """
    Tracks live performance for LIVE strategies.

    Single Responsibility: Update live metrics only (no retirement decisions).
    """

    def __init__(self, config: dict):
        """
        Initialize performance tracker.

        Args:
            config: Configuration dict
        """
        self.config = config
        self.live_scorer = LiveScorer(config)

        logger.info("PerformanceTracker initialized")

    def update_all_live_strategies(self) -> Dict:
        """
        Update live metrics for all LIVE strategies.

        Returns:
            Dict with update results: {'updated': int, 'skipped': int, 'failed': int}
        """
        results = {'updated': 0, 'skipped': 0, 'failed': 0}

        # Get all LIVE strategies
        with get_session() as session:
            live_strategies = (
                session.query(Strategy)
                .filter(Strategy.status == 'LIVE')
                .all()
            )
            strategy_ids = [(s.id, s.name) for s in live_strategies]

        if not strategy_ids:
            logger.debug("No LIVE strategies to update")
            return results

        for strategy_id, strategy_name in strategy_ids:
            try:
                updated = self.live_scorer.update_strategy_live_metrics(strategy_id)
                if updated:
                    results['updated'] += 1
                    logger.debug(f"Updated live metrics for {strategy_name}")
                else:
                    results['skipped'] += 1
                    logger.debug(f"Skipped {strategy_name} (insufficient trades)")
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Failed to update {strategy_name}: {e}")

        if results['updated'] > 0:
            logger.info(
                f"Live metrics update: {results['updated']} updated, "
                f"{results['skipped']} skipped, {results['failed']} failed"
            )

        return results

    def get_strategy_performance(self, strategy_id: UUID) -> Optional[Dict]:
        """
        Get current performance metrics for a strategy.

        Args:
            strategy_id: Strategy UUID

        Returns:
            Dict with live metrics or None if not available
        """
        return self.live_scorer.calculate_live_metrics(strategy_id)

    def get_all_live_performance(self) -> List[Dict]:
        """
        Get performance for all LIVE strategies.

        Returns:
            List of dicts with strategy_id, name, and live metrics
        """
        results = []

        with get_session() as session:
            live_strategies = (
                session.query(Strategy)
                .filter(Strategy.status == 'LIVE')
                .all()
            )

            for strategy in live_strategies:
                metrics = self.live_scorer.calculate_live_metrics(strategy.id)
                results.append({
                    'id': strategy.id,
                    'name': strategy.name,
                    'score_backtest': strategy.score_backtest,
                    'score_live': strategy.score_live,
                    'live_since': strategy.live_since,
                    'metrics': metrics,
                })

        return results
