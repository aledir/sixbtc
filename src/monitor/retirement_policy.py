"""
Retirement Policy - Decide Which LIVE Strategies to Retire

Single Responsibility: Evaluate LIVE strategies and decide retirement.

Retirement criteria (any triggers retirement):
1. Score live < min_score (default 35)
2. Score degradation > max_score_degradation (default 40% worse than backtest)
3. Drawdown > max_drawdown (default 25%)
4. Consecutive losses >= max_consecutive_losses (default 10)
5. Trade frequency degradation > max_trades_degradation (default 50%)
"""

from datetime import datetime, UTC
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from src.database import get_session
from src.database.models import Strategy, Subaccount, Trade, BacktestResult
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
        self.max_score_degradation = retirement_config['max_score_degradation']
        self.max_drawdown = retirement_config['max_drawdown']
        self.min_trades = retirement_config['min_trades']
        self.max_consecutive_losses = retirement_config['max_consecutive_losses']
        self.max_trades_degradation = retirement_config['max_trades_degradation']

        logger.info(
            f"RetirementPolicy initialized: min_score={self.min_score}, "
            f"max_score_degradation={self.max_score_degradation:.0%}, "
            f"max_drawdown={self.max_drawdown:.0%}, "
            f"max_consecutive_losses={self.max_consecutive_losses}, "
            f"max_trades_degradation={self.max_trades_degradation:.0%}"
        )

    def _count_consecutive_losses(self, strategy_id: UUID, session) -> int:
        """
        Count current streak of consecutive losing trades (from most recent).

        Args:
            strategy_id: Strategy UUID
            session: Database session

        Returns:
            Current consecutive losses streak (0 if last trade was winning)
        """
        # Limit query to max needed + buffer for efficiency
        limit = self.max_consecutive_losses + 10

        trades = (
            session.query(Trade)
            .filter(
                Trade.strategy_id == strategy_id,
                Trade.exit_time.isnot(None)
            )
            .order_by(Trade.exit_time.desc())  # Most recent first
            .limit(limit)
            .all()
        )

        if not trades:
            return 0

        consecutive = 0
        for trade in trades:
            if trade.pnl_usd is not None and trade.pnl_usd < 0:
                consecutive += 1
            else:
                break  # Stop at first winning trade

        return consecutive

    def _calculate_trades_degradation(
        self, strategy_id: UUID, session
    ) -> Optional[float]:
        """
        Calculate trade frequency degradation (live vs backtest).

        Formula: (expected - actual) / expected

        Args:
            strategy_id: Strategy UUID
            session: Database session

        Returns:
            Degradation as fraction (0.50 = 50% fewer trades)
            None if insufficient data
        """
        strategy = session.query(Strategy).filter(
            Strategy.id == strategy_id
        ).first()

        if not strategy or not strategy.live_since:
            return None

        # Get backtest result (most recent full period)
        backtest = (
            session.query(BacktestResult)
            .filter(
                BacktestResult.strategy_id == strategy_id,
                BacktestResult.period_type == 'full'
            )
            .order_by(BacktestResult.created_at.desc())
            .first()
        )

        if not backtest or not backtest.period_days or backtest.period_days == 0:
            return None

        if not backtest.total_trades or backtest.total_trades == 0:
            return None

        # Expected trades per day from backtest
        expected_per_day = backtest.total_trades / backtest.period_days

        # Days live (strip timezone for naive datetime comparison with DB)
        now_naive = datetime.now(UTC).replace(tzinfo=None)
        days_live = (now_naive - strategy.live_since).total_seconds() / 86400

        if days_live < 7:  # Need at least 7 days for meaningful comparison
            return None

        # Expected trades in live period
        expected_trades = expected_per_day * days_live
        actual_trades = strategy.total_trades_live or 0

        if expected_trades <= 0:
            return None

        # Degradation (positive = fewer trades than expected)
        degradation = (expected_trades - actual_trades) / expected_trades

        return max(0.0, degradation)  # Non-negative only

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

            # Check 2: Score degradation vs backtest
            score_deg = strategy.live_degradation_pct
            if score_deg is not None and score_deg > self.max_score_degradation:
                return (
                    True,
                    f"Score degradation {score_deg:.0%} > {self.max_score_degradation:.0%}"
                )

            # Check 3: Live drawdown
            drawdown = strategy.max_drawdown_live
            if drawdown is not None and drawdown > self.max_drawdown:
                return (True, f"Drawdown {drawdown:.0%} > {self.max_drawdown:.0%}")

            # Check 4: Consecutive losses (regime change indicator)
            consecutive_losses = self._count_consecutive_losses(strategy_id, session)
            if consecutive_losses >= self.max_consecutive_losses:
                return (
                    True,
                    f"Consecutive losses {consecutive_losses} >= {self.max_consecutive_losses}"
                )

            # Check 5: Trade frequency degradation
            trades_deg = self._calculate_trades_degradation(strategy_id, session)
            if trades_deg is not None and trades_deg > self.max_trades_degradation:
                return (
                    True,
                    f"Trade frequency -{trades_deg:.0%} vs backtest (max -{self.max_trades_degradation:.0%})"
                )

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
