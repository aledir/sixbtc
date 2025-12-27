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

        # Selection limits
        selection_config = self.config.get('classification', {}).get('selection', {})
        self.top_n = selection_config.get('top_n', 10)
        self.max_per_type = selection_config.get('max_per_type', 3)
        self.max_per_timeframe = selection_config.get('max_per_timeframe', 3)

        logger.info(
            f"ContinuousClassifierProcess initialized: "
            f"interval={self.interval_hours}h, top_n={self.top_n}"
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
        """Run a single classification cycle"""
        logger.info("Starting classification cycle")

        # Get all TESTED strategies
        tested_strategies = self._get_tested_strategies()

        if not tested_strategies:
            logger.info("No TESTED strategies to classify")
            return

        logger.info(f"Found {len(tested_strategies)} TESTED strategies")

        # Score all strategies
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

        if not scored_strategies:
            logger.warning("No strategies could be scored")
            return

        # Rank by score
        ranked = sorted(scored_strategies, key=lambda x: x['score'], reverse=True)

        logger.info(f"Top 5 strategies by score:")
        for i, s in enumerate(ranked[:5]):
            logger.info(f"  {i+1}. {s['name']}: {s['score']:.4f}")

        # Select top strategies with diversification
        selected = self._select_with_diversification(ranked)

        logger.info(f"Selected {len(selected)} strategies for deployment")

        # Update database: mark old SELECTED as TESTED, mark new as SELECTED
        self._update_selection(selected)

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

    def _select_with_diversification(self, ranked: List[Dict]) -> List[Dict]:
        """
        Select top strategies with type/timeframe diversification.

        Ensures no more than max_per_type strategies of same type,
        and no more than max_per_timeframe strategies on same timeframe.
        """
        selected = []
        type_counts = {}
        tf_counts = {}

        for strategy in ranked:
            if len(selected) >= self.top_n:
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
