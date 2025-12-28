"""
Continuous Classifier Process

Scores and selects top strategies for live trading.
Runs at regular intervals to re-evaluate and select top performers.
"""

import asyncio
import os
import signal
import threading
from datetime import datetime
from typing import List, Dict

from src.config import load_config
from src.database import get_session, Strategy, BacktestResult
from src.classifier.scorer import StrategyScorer
from src.classifier.portfolio_builder import PortfolioBuilder
from src.classifier.dual_ranker import DualRanker
from src.classifier.live_scorer import LiveScorer
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()._raw_config
setup_logging(
    log_file=_config.get('logging', {}).get('file', 'logs/sixbtc.log'),
    log_level=_config.get('logging', {}).get('level', 'INFO'),
)

logger = get_logger(__name__)


class ContinuousClassifierProcess:
    """
    Continuous strategy classification process.

    Periodically scores all TESTED strategies and selects top 10 for deployment.
    """

    def __init__(self):
        """Initialize the classifier process"""
        self.config = load_config()._raw_config
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Process configuration (from classification section)
        classification_config = self.config.get('classification', {})
        self.interval_hours = classification_config.get('frequency_hours', 1)

        # Components
        self.scorer = StrategyScorer(self.config)
        self.portfolio_builder = PortfolioBuilder(self.config)
        self.dual_ranker = DualRanker(self.config)
        self.live_scorer = LiveScorer(self.config)

        # Selection limits
        selection_config = self.config.get('classification', {}).get('selection', {})
        self.top_n = selection_config.get('top_n', 10)
        self.max_per_type = selection_config.get('max_per_type', 3)
        self.max_per_timeframe = selection_config.get('max_per_timeframe', 3)

        # Live ranking config
        live_config = self.config.get('classification', {}).get('live_ranking', {})
        self.live_ranking_enabled = live_config.get('enabled', True)

        logger.info(
            f"ContinuousClassifierProcess initialized: "
            f"interval={self.interval_hours}h, top_n={self.top_n}, "
            f"live_ranking={self.live_ranking_enabled}"
        )

    async def run_continuous(self):
        """Main continuous classification loop"""
        logger.info("Starting continuous classification loop")

        while not self.shutdown_event.is_set() and not self.force_exit:
            try:
                # Run classification cycle
                await self._run_classification_cycle()

            except Exception as e:
                logger.error(f"Classification cycle error: {e}", exc_info=True)

            # Wait for next cycle
            await self._wait_interval()

        logger.info("Classification loop ended")

    async def _run_classification_cycle(self):
        """Run a single classification cycle with dual-ranking support"""
        logger.info("Starting classification cycle")

        # Step 1: Update live metrics for LIVE strategies
        if self.live_ranking_enabled:
            self._update_live_metrics()

        # Step 2: Check and process retirement candidates
        if self.live_ranking_enabled:
            self._check_retirements()

        # Step 3: Get dual rankings
        backtest_ranking = self.dual_ranker.get_backtest_ranking(limit=50)
        live_ranking = self.dual_ranker.get_live_ranking(limit=20)

        logger.info(
            f"Rankings: {len(backtest_ranking)} backtest, "
            f"{len(live_ranking)} live strategies"
        )

        # Log top performers from each ranking
        self.dual_ranker.log_rankings()

        # Step 4: Calculate available slots for new deployments
        current_live_count = self._count_live_strategies()
        available_slots = self.top_n - current_live_count

        if available_slots > 0:
            logger.info(f"{available_slots} slots available for new deployments")

            # Get TESTED strategies for selection (exclude already SELECTED/LIVE)
            tested_strategies = self._get_tested_strategies()

            if tested_strategies:
                # Score and rank
                scored_strategies = []
                for strategy in tested_strategies:
                    try:
                        score = self.scorer.score_strategy(strategy)
                        scored_strategies.append({
                            'id': strategy['id'],
                            'name': strategy['name'],
                            'type': strategy['type'],
                            'timeframe': strategy['timeframe'],
                            'score': score,
                            'metrics': strategy['metrics']
                        })
                    except Exception as e:
                        logger.warning(f"Failed to score {strategy['name']}: {e}")

                if scored_strategies:
                    ranked = sorted(
                        scored_strategies,
                        key=lambda x: x['score'],
                        reverse=True
                    )

                    logger.info(f"Top 5 TESTED strategies by score:")
                    for i, s in enumerate(ranked[:5]):
                        logger.info(f"  {i+1}. {s['name']}: {s['score']:.4f}")

                    # Select with diversification (limited to available slots)
                    selected = self._select_with_diversification(
                        ranked,
                        limit=available_slots
                    )

                    logger.info(
                        f"Selected {len(selected)} strategies for deployment"
                    )

                    # Update database
                    self._update_selection(selected)
        else:
            logger.info("No slots available - all positions filled")

    def _update_live_metrics(self):
        """Update live performance metrics for all LIVE strategies"""
        logger.info("Updating live metrics for LIVE strategies")

        try:
            results = self.live_scorer.update_all_live_strategies()
            logger.info(
                f"Live metrics update: {results['updated']} updated, "
                f"{results['skipped']} skipped, {results['failed']} failed"
            )
        except Exception as e:
            logger.error(f"Failed to update live metrics: {e}", exc_info=True)

    def _check_retirements(self):
        """Check and process retirement candidates"""
        candidates = self.dual_ranker.check_retirement_candidates()

        if not candidates:
            logger.debug("No retirement candidates found")
            return

        logger.warning(f"Found {len(candidates)} retirement candidates")

        for candidate in candidates:
            try:
                success = self.dual_ranker.retire_strategy(
                    candidate['id'],
                    candidate['reason']
                )
                if success:
                    logger.warning(
                        f"RETIRED {candidate['name']}: {candidate['reason']} "
                        f"(score_live={candidate.get('score_live', 'N/A')}, "
                        f"pnl=${candidate.get('total_pnl', 0):.2f})"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to retire {candidate['name']}: {e}",
                    exc_info=True
                )

    def _count_live_strategies(self) -> int:
        """Count currently LIVE strategies"""
        with get_session() as session:
            count = session.query(Strategy).filter(
                Strategy.status == 'LIVE'
            ).count()
        return count

    def _get_tested_strategies(self) -> List[Dict]:
        """Get all TESTED strategies with their backtest results"""
        strategies = []

        with get_session() as session:
            # Get TESTED strategies
            results = (
                session.query(Strategy, BacktestResult)
                .join(BacktestResult, Strategy.id == BacktestResult.strategy_id)
                .filter(Strategy.status.in_(["TESTED", "SELECTED"]))
                .all()
            )

            for strategy, backtest in results:
                strategies.append({
                    'id': strategy.id,
                    'name': strategy.name,
                    'type': strategy.strategy_type,
                    'timeframe': strategy.timeframe,
                    'status': strategy.status,
                    'metrics': {
                        'sharpe_ratio': backtest.sharpe_ratio,
                        'win_rate': backtest.win_rate,
                        'expectancy': backtest.expectancy,
                        'max_drawdown': backtest.max_drawdown,
                        'total_trades': backtest.total_trades,
                        'total_return_pct': backtest.total_return_pct,
                        'walk_forward_stability': backtest.walk_forward_stability,
                    }
                })

        return strategies

    def _select_with_diversification(
        self,
        ranked: List[Dict],
        limit: int = None
    ) -> List[Dict]:
        """
        Select top strategies with type/timeframe diversification.

        Ensures no more than max_per_type strategies of same type,
        and no more than max_per_timeframe strategies on same timeframe.

        Args:
            ranked: List of strategies sorted by score descending
            limit: Maximum number to select (defaults to self.top_n)

        Returns:
            List of selected strategies
        """
        max_select = limit if limit is not None else self.top_n
        selected = []
        type_counts = {}
        tf_counts = {}

        for strategy in ranked:
            if len(selected) >= max_select:
                break

            strategy_type = strategy['type']
            timeframe = strategy['timeframe']

            # Check type limit
            if type_counts.get(strategy_type, 0) >= self.max_per_type:
                continue

            # Check timeframe limit
            if tf_counts.get(timeframe, 0) >= self.max_per_timeframe:
                continue

            # Select this strategy
            selected.append(strategy)
            type_counts[strategy_type] = type_counts.get(strategy_type, 0) + 1
            tf_counts[timeframe] = tf_counts.get(timeframe, 0) + 1

        return selected

    def _update_selection(self, selected: List[Dict]):
        """Update database with new selection"""
        selected_ids = {str(s['id']) for s in selected}

        with get_session() as session:
            # Demote old SELECTED strategies (not in new selection) back to TESTED
            old_selected = (
                session.query(Strategy)
                .filter(Strategy.status == "SELECTED")
                .all()
            )

            for strategy in old_selected:
                if str(strategy.id) not in selected_ids:
                    strategy.status = "TESTED"
                    logger.info(f"Demoted {strategy.name} from SELECTED to TESTED")

            # Promote new selections to SELECTED
            for s in selected:
                strategy = session.query(Strategy).filter(Strategy.id == s['id']).first()
                if strategy and strategy.status != "SELECTED":
                    strategy.status = "SELECTED"
                    logger.info(f"Promoted {strategy.name} to SELECTED (score: {s['score']:.4f})")

    async def _wait_interval(self):
        """Wait for next classification cycle"""
        wait_seconds = self.interval_hours * 3600

        logger.debug(f"Waiting {self.interval_hours}h until next classification")

        # Wait in chunks to allow shutdown
        while wait_seconds > 0 and not self.shutdown_event.is_set():
            sleep_time = min(60, wait_seconds)
            await asyncio.sleep(sleep_time)
            wait_seconds -= sleep_time

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Shutdown requested (signal {signum})")
        self.shutdown_event.set()
        self.force_exit = True
        os._exit(0)

    def run(self):
        """Main entry point"""
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        try:
            asyncio.run(self.run_continuous())
        except KeyboardInterrupt:
            pass
        finally:
            logger.info("Classifier process terminated")
