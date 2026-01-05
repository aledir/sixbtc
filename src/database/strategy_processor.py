"""
Strategy Processor - Multi-Process Coordination Layer

Provides atomic claim/release pattern for strategy processing across multiple
processes (generator, validator, backtester, etc.) using PostgreSQL row-level locking.

Pattern:
    processor = StrategyProcessor(process_id="validator-001")

    # Claim a strategy for processing
    strategy = processor.claim_strategy("GENERATED")
    if strategy:
        try:
            # Do work...
            processor.release_strategy(strategy.id, "VALIDATED")
        except Exception as e:
            processor.mark_failed(strategy.id, str(e))
"""

import os
import socket
from datetime import datetime, timedelta, UTC
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.connection import get_session, get_session_factory
from src.database.models import Strategy
from src.utils import get_logger

logger = get_logger(__name__)

# Default timeout for stale processing claims (15 minutes)
# Must be longer than max expected processing time (6 TFs x ~60s each + overhead)
DEFAULT_PROCESSING_TIMEOUT_SECONDS = 900


class StrategyProcessor:
    """
    Thread-safe strategy processor for multi-process coordination.

    Uses PostgreSQL FOR UPDATE SKIP LOCKED for atomic claiming.
    Each process instance should create its own StrategyProcessor with a unique process_id.
    """

    def __init__(self, process_id: Optional[str] = None, timeout_seconds: int = DEFAULT_PROCESSING_TIMEOUT_SECONDS):
        """
        Initialize StrategyProcessor.

        Args:
            process_id: Unique identifier for this process (auto-generated if None)
            timeout_seconds: Seconds before a processing claim is considered stale
        """
        self.process_id = process_id or self._generate_process_id()
        self.timeout_seconds = timeout_seconds
        self._session_factory = get_session_factory()

        logger.info(f"StrategyProcessor initialized: {self.process_id}")

    def _generate_process_id(self) -> str:
        """Generate unique process ID from hostname and PID"""
        hostname = socket.gethostname()[:20]
        pid = os.getpid()
        return f"{hostname}-{pid}"

    def _get_session(self) -> Session:
        """Create a new session for this operation (thread-safe)"""
        return self._session_factory()

    def claim_strategy(self, status: str) -> Optional[Strategy]:
        """
        Atomically claim a strategy with the given status for processing.

        Uses FOR UPDATE SKIP LOCKED to prevent race conditions:
        - Only one process can claim a specific strategy
        - Other processes skip locked rows and get different strategies

        Args:
            status: Strategy status to claim (e.g., "GENERATED", "VALIDATED")

        Returns:
            Strategy object if one was claimed, None if no strategies available
        """
        session = self._get_session()

        try:
            # First, release any stale claims (timed out)
            self._release_stale_claims(session)

            # Atomic claim using FOR UPDATE SKIP LOCKED
            # This query:
            # 1. Finds strategies with matching status AND no current processor
            # 2. Locks the first available row (skipping already-locked rows)
            # 3. Returns the locked row for update
            strategy = (
                session.query(Strategy)
                .filter(
                    Strategy.status == status,
                    Strategy.processing_by.is_(None)
                )
                .with_for_update(skip_locked=True)
                .first()
            )

            if strategy is None:
                session.rollback()
                return None

            # Update the strategy to mark it as being processed
            strategy.processing_by = self.process_id
            strategy.processing_started_at = datetime.now(UTC)

            session.commit()

            logger.debug(f"Claimed strategy {strategy.name} (status={status})")
            return strategy

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to claim strategy: {e}")
            raise
        finally:
            session.close()

    def release_strategy(self, strategy_id, new_status: str) -> bool:
        """
        Release a strategy after successful processing.

        Args:
            strategy_id: Strategy ID (UUID)
            new_status: New status to set (e.g., "VALIDATED", "ACTIVE")

        Returns:
            True if released successfully, False otherwise
        """
        session = self._get_session()

        try:
            strategy = session.query(Strategy).filter(Strategy.id == strategy_id).first()

            if strategy is None:
                logger.warning(f"Strategy {strategy_id} not found for release")
                return False

            if strategy.processing_by != self.process_id:
                logger.warning(
                    f"Strategy {strategy_id} not owned by this process "
                    f"(owned by {strategy.processing_by}, we are {self.process_id})"
                )
                return False

            # Update status and clear processing lock
            old_status = strategy.status
            strategy.status = new_status
            strategy.processing_by = None
            strategy.processing_started_at = None

            # Update relevant timestamps based on new status
            if new_status == "ACTIVE":
                strategy.last_backtested_at = datetime.now(UTC)
            elif new_status == "LIVE":
                strategy.live_since = datetime.now(UTC)
            elif new_status == "RETIRED":
                strategy.retired_at = datetime.now(UTC)

            session.commit()

            logger.info(f"Released strategy {strategy.name}: {old_status} -> {new_status}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to release strategy {strategy_id}: {e}")
            raise
        finally:
            session.close()

    def mark_failed(self, strategy_id, error: str, delete: bool = False) -> bool:
        """
        Mark a strategy as failed after processing error.

        Args:
            strategy_id: Strategy ID (UUID)
            error: Error message to log
            delete: If True, delete the strategy instead of marking as FAILED

        Returns:
            True if operation successful, False otherwise
        """
        session = self._get_session()

        try:
            strategy = session.query(Strategy).filter(Strategy.id == strategy_id).first()

            if strategy is None:
                logger.warning(f"Strategy {strategy_id} not found for marking failed")
                return False

            if delete:
                # Delete the strategy entirely (e.g., for validation failures)
                session.delete(strategy)
                session.commit()
                logger.info(f"Deleted failed strategy {strategy.name}: {error}")
            else:
                # Mark as FAILED but keep the record
                strategy.status = "FAILED"
                strategy.processing_by = None
                strategy.processing_started_at = None
                session.commit()
                logger.warning(f"Marked strategy {strategy.name} as FAILED: {error}")

            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to mark strategy {strategy_id} as failed: {e}")
            raise
        finally:
            session.close()

    def release_all_by_process(self) -> int:
        """
        Release all strategies claimed by this process.

        Useful for graceful shutdown.

        Returns:
            Number of strategies released
        """
        session = self._get_session()

        try:
            result = (
                session.query(Strategy)
                .filter(Strategy.processing_by == self.process_id)
                .update({
                    Strategy.processing_by: None,
                    Strategy.processing_started_at: None
                })
            )

            session.commit()

            if result > 0:
                logger.info(f"Released {result} strategies on shutdown")

            return result

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to release strategies on shutdown: {e}")
            raise
        finally:
            session.close()

    def _release_stale_claims(self, session: Session) -> int:
        """
        Release strategies that have been processing for too long (timeout).

        This handles cases where a process crashes without releasing its claims.

        Args:
            session: Active database session

        Returns:
            Number of stale claims released
        """
        cutoff_time = datetime.now(UTC) - timedelta(seconds=self.timeout_seconds)

        result = (
            session.query(Strategy)
            .filter(
                Strategy.processing_by.isnot(None),
                Strategy.processing_started_at < cutoff_time
            )
            .update({
                Strategy.processing_by: None,
                Strategy.processing_started_at: None
            })
        )

        if result > 0:
            logger.info(f"Released {result} stale processing claims (timeout: {self.timeout_seconds}s)")

        return result

    def get_processing_stats(self) -> dict:
        """
        Get statistics about strategy processing.

        Returns:
            Dict with counts by status and processing state
        """
        session = self._get_session()

        try:
            stats = {
                'by_status': {},
                'processing': 0,
                'processing_by_process': {}
            }

            # Count by status
            status_counts = (
                session.query(Strategy.status, text('COUNT(*)'))
                .group_by(Strategy.status)
                .all()
            )

            for status, count in status_counts:
                stats['by_status'][status] = count

            # Count currently processing
            processing_count = (
                session.query(Strategy)
                .filter(Strategy.processing_by.isnot(None))
                .count()
            )
            stats['processing'] = processing_count

            # Count by process
            process_counts = (
                session.query(Strategy.processing_by, text('COUNT(*)'))
                .filter(Strategy.processing_by.isnot(None))
                .group_by(Strategy.processing_by)
                .all()
            )

            for process_id, count in process_counts:
                stats['processing_by_process'][process_id] = count

            return stats

        finally:
            session.close()

    def count_available(self, status: str) -> int:
        """
        Count strategies available for processing with given status.

        Args:
            status: Strategy status to count

        Returns:
            Number of available strategies (not being processed)
        """
        session = self._get_session()

        try:
            return (
                session.query(Strategy)
                .filter(
                    Strategy.status == status,
                    Strategy.processing_by.is_(None)
                )
                .count()
            )
        finally:
            session.close()

    def get_used_pattern_ids(self) -> set:
        """
        Get pattern IDs that have been used (all time).

        Returns all pattern IDs ever used in strategies to prevent duplicates.
        Pattern exhaustion triggers AI-only generation (not recycling).

        Returns:
            Set of pattern IDs that have been used
        """
        session = self._get_session()

        try:
            # Get all pattern IDs from all strategies (no time filter)
            strategies = (
                session.query(Strategy.pattern_ids)
                .filter(
                    Strategy.pattern_based == True,
                    Strategy.pattern_ids.isnot(None)
                )
                .all()
            )

            # Collect all pattern IDs into a set
            used_ids = set()
            for (pattern_ids,) in strategies:
                if pattern_ids and isinstance(pattern_ids, list):
                    for pid in pattern_ids:
                        if pid:
                            used_ids.add(str(pid))

            logger.debug(f"Found {len(used_ids)} patterns used (all time)")
            return used_ids

        except Exception as e:
            logger.error(f"Failed to get used pattern IDs: {e}")
            return set()
        finally:
            session.close()

    def count_strategies_using_pattern(self, pattern_id: str) -> int:
        """
        Count how many strategies use a specific pattern.

        Args:
            pattern_id: Pattern ID to check

        Returns:
            Number of strategies using this pattern
        """
        session = self._get_session()

        try:
            # Use JSON contains query for PostgreSQL
            from sqlalchemy import func

            count = (
                session.query(Strategy)
                .filter(
                    Strategy.pattern_ids.isnot(None),
                    func.jsonb_exists(Strategy.pattern_ids.cast(text('jsonb')), pattern_id)
                )
                .count()
            )

            return count

        except Exception as e:
            # Fallback: load all and check in Python
            logger.debug(f"JSON query failed, using fallback: {e}")
            strategies = (
                session.query(Strategy.pattern_ids)
                .filter(Strategy.pattern_ids.isnot(None))
                .all()
            )

            count = 0
            for (pattern_ids,) in strategies:
                if pattern_ids and pattern_id in pattern_ids:
                    count += 1

            return count
        finally:
            session.close()

    def get_queue_depths(self) -> dict:
        """
        Get count of strategies by status (excluding currently processing).

        Returns dict with counts for each status that can be used for
        pipeline monitoring and backpressure decisions.

        Returns:
            Dict mapping status -> count of available (non-processing) strategies
        """
        session = self._get_session()

        try:
            results = {}
            for status in ['GENERATED', 'VALIDATED', 'ACTIVE', 'LIVE', 'RETIRED', 'FAILED']:
                count = (
                    session.query(Strategy)
                    .filter(
                        Strategy.status == status,
                        Strategy.processing_by.is_(None)
                    )
                    .count()
                )
                results[status] = count

            return results

        except Exception as e:
            logger.error(f"Failed to get queue depths: {e}")
            return {}
        finally:
            session.close()

    def calculate_backpressure_cooldown(
        self,
        queue_depth: int,
        limit: int,
        base: int = 30,
        increment: int = 2,
        max_cooldown: int = 120
    ) -> int:
        """
        Calculate cooldown based on how much over limit we are.

        Progressive cooldown formula:
        - If under limit: 0 (no cooldown)
        - If at/over limit: base + (overflow * increment), capped at max_cooldown

        Args:
            queue_depth: Current queue depth
            limit: Queue limit threshold
            base: Base cooldown in seconds when limit reached
            increment: Extra seconds per strategy over limit
            max_cooldown: Maximum cooldown in seconds

        Returns:
            Cooldown in seconds (0 if under limit)
        """
        if queue_depth < limit:
            return 0

        overflow = queue_depth - limit
        cooldown = base + (overflow * increment)
        return min(cooldown, max_cooldown)
