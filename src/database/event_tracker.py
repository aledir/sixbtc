"""
Event Tracker for Pipeline Metrics

Provides a simple interface to emit pipeline events that are stored
in the strategy_events table. Events persist even when strategies
are deleted, enabling accurate metrics calculation.

Usage:
    from src.database.event_tracker import EventTracker

    # Emit a simple event
    EventTracker.emit(
        event_type="syntax_passed",
        stage="validation",
        status="passed",
        strategy_id=uuid,
        strategy_name="Strategy_MOM_abc123",
        duration_ms=150
    )

    # Or use convenience methods
    EventTracker.validation_passed(strategy_id, name, "syntax", duration_ms=150)
    EventTracker.validation_failed(strategy_id, name, "lookahead", reason="shift(-1)")
"""

import logging
from datetime import datetime, UTC
from typing import Optional, Any
from uuid import UUID

from src.database import get_session
from src.database.models import StrategyEvent

logger = logging.getLogger(__name__)


class EventTracker:
    """
    Static helper class for emitting pipeline events.

    All methods are static - no instance needed.
    Events are written synchronously to database.
    Failures are logged but don't block pipeline execution.
    """

    @staticmethod
    def emit(
        event_type: str,
        stage: str,
        status: str,
        strategy_id: Optional[UUID],
        strategy_name: str,
        duration_ms: Optional[int] = None,
        base_code_hash: Optional[str] = None,
        **metadata: Any
    ) -> bool:
        """
        Emit a pipeline event to the database.

        Args:
            event_type: Event type (e.g., "syntax_passed", "shuffle_failed")
            stage: Pipeline stage (e.g., "validation", "backtest", "pool")
            status: Event status ("started", "passed", "failed", "completed")
            strategy_id: Strategy UUID (can be None if strategy deleted)
            strategy_name: Strategy name (required, persists after delete)
            duration_ms: Duration in milliseconds (optional)
            base_code_hash: Template hash for parametric strategies (optional)
            **metadata: Additional key-value pairs stored as JSON

        Returns:
            True if event was saved, False if error occurred
        """
        try:
            event = StrategyEvent(
                timestamp=datetime.now(UTC),
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                base_code_hash=base_code_hash,
                event_type=event_type,
                stage=stage,
                status=status,
                duration_ms=duration_ms,
                event_data=metadata if metadata else None
            )

            with get_session() as session:
                session.add(event)
                session.commit()

            return True

        except Exception as e:
            # Log error but don't crash pipeline
            logger.warning(f"Failed to emit event {event_type}: {e}")
            return False

    # =========================================================================
    # GENERATION EVENTS
    # =========================================================================

    @staticmethod
    def generation_created(
        strategy_id: UUID,
        strategy_name: str,
        strategy_type: str,
        timeframe: str,
        ai_provider: Optional[str] = None,
        pattern_based: bool = False,
        base_code_hash: Optional[str] = None
    ) -> bool:
        """Emit event when a new strategy is generated."""
        return EventTracker.emit(
            event_type="created",
            stage="generation",
            status="completed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            base_code_hash=base_code_hash,
            strategy_type=strategy_type,
            timeframe=timeframe,
            ai_provider=ai_provider,
            pattern_based=pattern_based
        )

    # =========================================================================
    # VALIDATION EVENTS
    # =========================================================================

    @staticmethod
    def validation_started(
        strategy_id: UUID,
        strategy_name: str,
        phase: str
    ) -> bool:
        """Emit event when a validation phase starts."""
        return EventTracker.emit(
            event_type=f"{phase}_started",
            stage="validation",
            status="started",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            phase=phase
        )

    @staticmethod
    def validation_passed(
        strategy_id: UUID,
        strategy_name: str,
        phase: str,
        duration_ms: Optional[int] = None,
        **details: Any
    ) -> bool:
        """Emit event when a validation phase passes."""
        return EventTracker.emit(
            event_type=f"{phase}_passed",
            stage="validation",
            status="passed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            duration_ms=duration_ms,
            phase=phase,
            **details
        )

    @staticmethod
    def validation_failed(
        strategy_id: UUID,
        strategy_name: str,
        phase: str,
        reason: str,
        duration_ms: Optional[int] = None,
        **details: Any
    ) -> bool:
        """Emit event when a validation phase fails."""
        return EventTracker.emit(
            event_type=f"{phase}_failed",
            stage="validation",
            status="failed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            duration_ms=duration_ms,
            phase=phase,
            reason=reason,
            **details
        )

    @staticmethod
    def validation_completed(
        strategy_id: UUID,
        strategy_name: str,
        total_duration_ms: int
    ) -> bool:
        """Emit event when all validation phases complete successfully."""
        return EventTracker.emit(
            event_type="completed",
            stage="validation",
            status="completed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            duration_ms=total_duration_ms
        )

    # =========================================================================
    # BACKTEST EVENTS
    # =========================================================================

    @staticmethod
    def backtest_started(
        strategy_id: UUID,
        strategy_name: str,
        timeframe: str,
        base_code_hash: Optional[str] = None
    ) -> bool:
        """Emit event when backtest starts."""
        return EventTracker.emit(
            event_type="started",
            stage="backtest",
            status="started",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            base_code_hash=base_code_hash,
            timeframe=timeframe
        )

    @staticmethod
    def backtest_tf_completed(
        strategy_id: UUID,
        strategy_name: str,
        timeframe: str,
        sharpe: float,
        win_rate: float,
        trades: int,
        passed: bool,
        duration_ms: Optional[int] = None
    ) -> bool:
        """Emit event when a single timeframe backtest completes."""
        return EventTracker.emit(
            event_type="tf_completed",
            stage="backtest",
            status="passed" if passed else "failed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            duration_ms=duration_ms,
            timeframe=timeframe,
            sharpe=sharpe,
            win_rate=win_rate,
            trades=trades,
            passed=passed
        )

    @staticmethod
    def backtest_scored(
        strategy_id: UUID,
        strategy_name: str,
        score: float,
        sharpe: float,
        win_rate: float,
        edge: float,
        consistency: float,
        drawdown: float
    ) -> bool:
        """Emit event when strategy is scored after backtest."""
        return EventTracker.emit(
            event_type="scored",
            stage="backtest",
            status="completed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            score=score,
            sharpe=sharpe,
            win_rate=win_rate,
            edge=edge,
            consistency=consistency,
            drawdown=drawdown
        )

    @staticmethod
    def backtest_score_rejected(
        strategy_id: UUID,
        strategy_name: str,
        score: float,
        threshold: float
    ) -> bool:
        """Emit event when strategy is rejected due to low score."""
        return EventTracker.emit(
            event_type="score_rejected",
            stage="backtest",
            status="failed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            score=score,
            threshold=threshold,
            reason="score_below_threshold"
        )

    # =========================================================================
    # SHUFFLE TEST EVENTS
    # =========================================================================

    @staticmethod
    def shuffle_test_started(
        strategy_id: UUID,
        strategy_name: str,
        cached: bool = False,
        base_code_hash: Optional[str] = None
    ) -> bool:
        """Emit event when shuffle test starts."""
        return EventTracker.emit(
            event_type="started",
            stage="shuffle_test",
            status="started",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            base_code_hash=base_code_hash,
            cached=cached
        )

    @staticmethod
    def shuffle_test_passed(
        strategy_id: UUID,
        strategy_name: str,
        cached: bool = False,
        duration_ms: Optional[int] = None,
        base_code_hash: Optional[str] = None
    ) -> bool:
        """Emit event when shuffle test passes."""
        return EventTracker.emit(
            event_type="passed",
            stage="shuffle_test",
            status="passed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            base_code_hash=base_code_hash,
            duration_ms=duration_ms,
            cached=cached
        )

    @staticmethod
    def shuffle_test_failed(
        strategy_id: UUID,
        strategy_name: str,
        reason: str,
        cached: bool = False,
        duration_ms: Optional[int] = None,
        base_code_hash: Optional[str] = None,
        **details: Any
    ) -> bool:
        """Emit event when shuffle test fails."""
        return EventTracker.emit(
            event_type="failed",
            stage="shuffle_test",
            status="failed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            base_code_hash=base_code_hash,
            duration_ms=duration_ms,
            cached=cached,
            reason=reason,
            **details
        )

    # =========================================================================
    # MULTI-WINDOW VALIDATION EVENTS
    # =========================================================================

    @staticmethod
    def multi_window_started(
        strategy_id: UUID,
        strategy_name: str,
        windows_count: int,
        cached: bool = False,
        base_code_hash: Optional[str] = None
    ) -> bool:
        """Emit event when multi-window validation starts."""
        return EventTracker.emit(
            event_type="started",
            stage="multi_window",
            status="started",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            base_code_hash=base_code_hash,
            windows_count=windows_count,
            cached=cached
        )

    @staticmethod
    def multi_window_passed(
        strategy_id: UUID,
        strategy_name: str,
        avg_sharpe: float,
        cv: float,
        duration_ms: Optional[int] = None,
        cached: bool = False,
        base_code_hash: Optional[str] = None
    ) -> bool:
        """Emit event when multi-window validation passes."""
        return EventTracker.emit(
            event_type="passed",
            stage="multi_window",
            status="passed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            base_code_hash=base_code_hash,
            duration_ms=duration_ms,
            avg_sharpe=avg_sharpe,
            cv=cv,
            cached=cached
        )

    @staticmethod
    def multi_window_failed(
        strategy_id: UUID,
        strategy_name: str,
        reason: str,
        duration_ms: Optional[int] = None,
        cached: bool = False,
        base_code_hash: Optional[str] = None,
        **details: Any
    ) -> bool:
        """Emit event when multi-window validation fails."""
        return EventTracker.emit(
            event_type="failed",
            stage="multi_window",
            status="failed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            base_code_hash=base_code_hash,
            duration_ms=duration_ms,
            cached=cached,
            reason=reason,
            **details
        )

    # =========================================================================
    # POOL EVENTS
    # =========================================================================

    @staticmethod
    def pool_attempted(
        strategy_id: UUID,
        strategy_name: str,
        score: float,
        min_score_in_pool: Optional[float] = None,
        pool_size: Optional[int] = None
    ) -> bool:
        """Emit event when strategy attempts to enter pool."""
        return EventTracker.emit(
            event_type="attempted",
            stage="pool",
            status="started",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            score=score,
            min_score_in_pool=min_score_in_pool,
            pool_size=pool_size
        )

    @staticmethod
    def pool_entered(
        strategy_id: UUID,
        strategy_name: str,
        score: float,
        pool_size: int
    ) -> bool:
        """Emit event when strategy enters the pool."""
        return EventTracker.emit(
            event_type="entered",
            stage="pool",
            status="passed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            score=score,
            pool_size=pool_size
        )

    @staticmethod
    def pool_rejected(
        strategy_id: UUID,
        strategy_name: str,
        score: float,
        reason: str,
        min_score_in_pool: Optional[float] = None
    ) -> bool:
        """Emit event when strategy is rejected from pool."""
        return EventTracker.emit(
            event_type="rejected",
            stage="pool",
            status="failed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            score=score,
            reason=reason,
            min_score_in_pool=min_score_in_pool
        )

    # =========================================================================
    # DEPLOYMENT EVENTS
    # =========================================================================

    @staticmethod
    def deployment_started(
        strategy_id: UUID,
        strategy_name: str,
        subaccount_id: int
    ) -> bool:
        """Emit event when deployment to subaccount starts."""
        return EventTracker.emit(
            event_type="started",
            stage="deployment",
            status="started",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            subaccount_id=subaccount_id
        )

    @staticmethod
    def deployment_succeeded(
        strategy_id: UUID,
        strategy_name: str,
        subaccount_id: int,
        allocated_capital: float
    ) -> bool:
        """Emit event when deployment succeeds."""
        return EventTracker.emit(
            event_type="succeeded",
            stage="deployment",
            status="passed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            subaccount_id=subaccount_id,
            allocated_capital=allocated_capital
        )

    @staticmethod
    def deployment_failed(
        strategy_id: UUID,
        strategy_name: str,
        subaccount_id: int,
        error: str
    ) -> bool:
        """Emit event when deployment fails."""
        return EventTracker.emit(
            event_type="failed",
            stage="deployment",
            status="failed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            subaccount_id=subaccount_id,
            error=error
        )

    # =========================================================================
    # LIVE EVENTS
    # =========================================================================

    @staticmethod
    def strategy_promoted_live(
        strategy_id: UUID,
        strategy_name: str,
        subaccount_id: int
    ) -> bool:
        """Emit event when strategy is promoted to LIVE status."""
        return EventTracker.emit(
            event_type="promoted",
            stage="live",
            status="completed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            subaccount_id=subaccount_id
        )

    @staticmethod
    def strategy_retired(
        strategy_id: UUID,
        strategy_name: str,
        reason: str,
        live_duration_hours: Optional[float] = None,
        final_pnl: Optional[float] = None
    ) -> bool:
        """Emit event when strategy is retired."""
        return EventTracker.emit(
            event_type="retired",
            stage="live",
            status="completed",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            reason=reason,
            live_duration_hours=live_duration_hours,
            final_pnl=final_pnl
        )

    # =========================================================================
    # EMERGENCY EVENTS
    # =========================================================================

    @staticmethod
    def emergency_stop_triggered(
        reason: str,
        affected_strategies: int,
        affected_subaccounts: int
    ) -> bool:
        """Emit event when emergency stop is triggered."""
        return EventTracker.emit(
            event_type="stop_triggered",
            stage="emergency",
            status="completed",
            strategy_id=None,
            strategy_name="SYSTEM",
            reason=reason,
            affected_strategies=affected_strategies,
            affected_subaccounts=affected_subaccounts
        )
