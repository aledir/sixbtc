"""
Retirement Policy - Decide Which LIVE Strategies to Retire

Single Responsibility: Evaluate LIVE strategies and decide retirement.

Retirement criteria (any triggers retirement):
1. Score live < min_score (default 30)
2. Degradation > max_degradation (default 50% worse than backtest)
3. Drawdown > max_drawdown (default 30%)
"""

from datetime import datetime, UTC
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from src.database import get_session
from src.database.models import Strategy, Subaccount
from src.database.event_tracker import EventTracker
from src.utils.logger import get_logger
from src.utils.strategy_files import remove_from_live

logger = get_logger(__name__)


class RetirementPolicy:
    """
    Evaluates LIVE strategies and decides retirement.

    Single Responsibility: Retirement decisions only (no deployment changes).
    """

    def __init__(self, config: dict):
        """
        Initialize retirement policy.

        Args:
            config: Configuration dict with 'monitor.retirement' section

        Raises:
            KeyError: If required config sections are missing (Fast Fail)
        """
        retirement_config = config['monitor']['retirement']

        self.min_score = retirement_config['min_score']
        self.max_degradation = retirement_config['max_degradation']
        self.max_drawdown = retirement_config['max_drawdown']
        self.min_trades = retirement_config['min_trades']

        logger.info(
            f"RetirementPolicy initialized: min_score={self.min_score}, "
            f"max_degradation={self.max_degradation:.0%}, "
            f"max_drawdown={self.max_drawdown:.0%}"
        )

    def evaluate_strategy(self, strategy_id: UUID) -> Tuple[bool, Optional[str]]:
        """
        Evaluate if a strategy should be retired.

        Args:
            strategy_id: Strategy UUID

        Returns:
            (should_retire: bool, reason: Optional[str])
        """
        with get_session() as session:
            strategy = session.query(Strategy).filter(
                Strategy.id == strategy_id
            ).first()

            if not strategy:
                return (False, None)

            if strategy.status != 'LIVE':
                return (False, None)

            # Check minimum trades before evaluation
            trades_live = strategy.total_trades_live or 0
            if trades_live < self.min_trades:
                logger.debug(
                    f"{strategy.name}: {trades_live} trades < {self.min_trades}, "
                    f"skipping retirement check"
                )
                return (False, None)

            # Check 1: Live score below threshold
            score_live = strategy.score_live
            if score_live is not None and score_live < self.min_score:
                return (True, f"Live score {score_live:.1f} < {self.min_score}")

            # Check 2: Degradation vs backtest
            degradation = strategy.live_degradation_pct
            if degradation is not None and degradation > self.max_degradation:
                return (
                    True,
                    f"Degradation {degradation:.0%} > {self.max_degradation:.0%}"
                )

            # Check 3: Live drawdown
            drawdown = strategy.max_drawdown_live
            if drawdown is not None and drawdown > self.max_drawdown:
                return (True, f"Drawdown {drawdown:.0%} > {self.max_drawdown:.0%}")

            return (False, None)

    def evaluate_all_live(self) -> List[Dict]:
        """
        Evaluate all LIVE strategies for retirement.

        Returns:
            List of strategies that should be retired:
            [{'id': UUID, 'name': str, 'reason': str}, ...]
        """
        to_retire = []

        with get_session() as session:
            live_strategies = (
                session.query(Strategy)
                .filter(Strategy.status == 'LIVE')
                .all()
            )

            for strategy in live_strategies:
                should_retire, reason = self.evaluate_strategy(strategy.id)
                if should_retire:
                    to_retire.append({
                        'id': strategy.id,
                        'name': strategy.name,
                        'reason': reason,
                    })
                    logger.info(f"Strategy {strategy.name} marked for retirement: {reason}")

        return to_retire

    def retire_strategy(self, strategy_id: UUID, reason: str) -> bool:
        """
        Execute retirement for a strategy.

        Updates strategy status and frees subaccount.

        Args:
            strategy_id: Strategy UUID
            reason: Reason for retirement

        Returns:
            True if retirement successful
        """
        try:
            with get_session() as session:
                # Update strategy
                strategy = session.query(Strategy).filter(
                    Strategy.id == strategy_id
                ).first()

                if not strategy:
                    logger.warning(f"Strategy {strategy_id} not found")
                    return False

                # Calculate live duration if available
                live_duration_hours = None
                if strategy.live_since:
                    delta = datetime.now(UTC) - strategy.live_since
                    live_duration_hours = delta.total_seconds() / 3600

                strategy.status = 'RETIRED'
                strategy.retired_at = datetime.now(UTC)

                # Remove .py file from live/
                remove_from_live(strategy.name)

                # Emit retirement event
                EventTracker.strategy_retired(
                    strategy_id=strategy_id,
                    strategy_name=strategy.name,
                    reason=reason,
                    live_duration_hours=live_duration_hours,
                    final_pnl=strategy.total_pnl_live
                )

                # Free subaccount
                subaccount = (
                    session.query(Subaccount)
                    .filter(Subaccount.strategy_id == strategy_id)
                    .first()
                )

                if subaccount:
                    subaccount.strategy_id = None
                    subaccount.status = 'PAUSED'
                    logger.info(f"Freed subaccount {subaccount.id}")

                session.commit()
                logger.info(f"Retired {strategy.name}: {reason}")

            return True

        except Exception as e:
            logger.error(f"Failed to retire {strategy_id}: {e}")
            return False

    def run_retirement_check(self) -> Dict:
        """
        Run full retirement check cycle.

        1. Evaluate all LIVE strategies
        2. Retire those that meet criteria
        3. Return summary

        Returns:
            Dict with check results: {'checked': int, 'retired': int, 'failed': int}
        """
        results = {'checked': 0, 'retired': 0, 'failed': 0}

        # Get strategies to retire
        to_retire = self.evaluate_all_live()
        results['checked'] = len(to_retire)

        # Execute retirements
        for strategy_info in to_retire:
            success = self.retire_strategy(
                strategy_info['id'],
                strategy_info['reason']
            )
            if success:
                results['retired'] += 1
            else:
                results['failed'] += 1

        if results['retired'] > 0:
            logger.info(
                f"Retirement check: {results['retired']} retired, "
                f"{results['failed']} failed"
            )

        return results
