"""
Pipeline Metrics Collector (Event-Based)

Collects pipeline metrics from the strategy_events table.
Events persist even when strategies are deleted, enabling accurate metrics.

Log format (verbose, self-explanatory):
Each section has a header line explaining the category, followed by
individual metrics with clear descriptions. Sections:

- [QUEUE]: Current strategy counts by status (waiting at each stage)
- [FUNNEL 24H]: Conversion rates through pipeline in last 24h
- [TIMING]: Average processing time per strategy at each stage
- [FAILURES 24H]: Rejection counts by stage with reasons
- [BACKPRESSURE]: Queue saturation levels (OK/OVERFLOW)
- [POOL]: ACTIVE pool statistics (strategies ready for live)
- [RETEST 24H]: Pool freshness (re-backtest results)
- [LIVE]: Strategies currently trading real money
"""

import os
import time
import logging
from datetime import datetime, timedelta, UTC, date
from typing import Dict, List, Optional, Any, Tuple

from hyperliquid.info import Info
from hyperliquid.utils import constants
from sqlalchemy import select, func, and_, or_, desc, cast, Integer, text

from src.config import load_config
from src.database import get_session, PipelineMetricsSnapshot, Strategy
from src.database.models import StrategyEvent, BacktestResult, ScheduledTaskExecution, Subaccount

# TYPE_CHECKING imports to avoid circular dependencies
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.executor.statistics_service import StatisticsService

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects pipeline metrics from events at regular intervals.

    Uses strategy_events table for accurate metrics:
    - Success rates calculated from passed/failed events
    - Failure reasons tracked and aggregated
    - Timing information from event durations
    """

    def __init__(
        self,
        config: Optional[Dict] = None,
        statistics_service: Optional['StatisticsService'] = None
    ):
        """
        Initialize metrics collector.

        Args:
            config: Configuration dict (if None, loads from file)
            statistics_service: Optional StatisticsService for true P&L stats from Hyperliquid
        """
        if config is None:
            config = load_config()

        # Statistics service for true P&L calculation (Hyperliquid as source of truth)
        self.statistics_service = statistics_service

        self.config = config._raw_config if hasattr(config, '_raw_config') else config

        # Collection interval (default: 1 minute = 60 seconds)
        metrics_config = self.config.get('metrics', {})
        self.interval_seconds = metrics_config.get('collection_interval', 60)

        # Queue limits from pipeline config
        pipeline_config = self.config.get('pipeline', {})
        queue_limits = pipeline_config.get('queue_limits', {})
        self.limit_generated = queue_limits.get('generated', 500)
        self.limit_validated = queue_limits.get('validated', 500)

        # ACTIVE pool limit from active_pool config
        active_pool_config = self.config.get('active_pool', {})
        self.limit_active = active_pool_config.get('max_size', 300)
        self.pool_min_score = active_pool_config.get('min_score', 40)

        # LIVE limit from rotator config
        rotator_config = self.config.get('rotator', {})
        self.limit_live = rotator_config.get('max_live_strategies', 10)

        # Backtesting config for retest and periods
        backtesting_config = self.config.get('backtesting', {})
        self.retest_interval_days = backtesting_config.get('retest', {}).get('interval_days', 3)
        self.is_days = backtesting_config.get('is_days', 120)
        self.oos_days = backtesting_config.get('oos_days', 30)

        # Parse enabled sources from generation config
        gen_config = self.config.get('generation', {})
        strategy_sources = gen_config.get('strategy_sources', {})
        self.enabled_sources = set()
        for source_name, source_cfg in strategy_sources.items():
            if source_cfg.get('enabled', False):
                self.enabled_sources.add(source_name)
                # Check if genetic sub-source is enabled
                genetic_cfg = source_cfg.get('genetic', {})
                if genetic_cfg.get('enabled', False):
                    self.enabled_sources.add(f'{source_name}_genetic')

        # Hyperliquid Info client for balance queries (read-only)
        hl_config = self.config.get('hyperliquid', {})
        testnet = hl_config.get('testnet', False)
        api_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL
        self._hl_info = Info(api_url, skip_ws=True)
        self._hl_master_address = os.getenv('HL_MASTER_ADDRESS')

        logger.info(f"MetricsCollector initialized (interval: {self.interval_seconds}s)")

    def collect_snapshot(self) -> None:
        """Collect current pipeline metrics and save to database."""
        try:
            with get_session() as session:
                # Time windows
                now = datetime.now(UTC)
                window_1min = now - timedelta(seconds=self.interval_seconds)
                window_24h = now - timedelta(hours=24)

                # Collect all metrics
                queue_depths = self._get_queue_depths(session)
                generation_by_source = self._get_generation_by_source(session, window_24h)
                generator_stats = self._get_generator_stats_24h(session, window_24h)
                ai_calls_today = self._get_ai_calls_today()
                unused_patterns = self._get_unused_patterns(session)
                funnel = self._get_funnel_24h(session, window_24h)
                validation_by_source = self._get_validation_by_source_24h(session, window_24h)
                pool_added_by_source = self._get_pool_added_by_source_24h(session, window_24h)
                timing = self._get_timing_avg_24h(session, window_24h)
                throughput = self._get_throughput_interval(session, window_1min)
                failures = self._get_failures_24h(session, window_24h)
                backpressure = self._get_backpressure_status(session, queue_depths)
                pool_stats = self._get_pool_stats(session)
                pool_quality = self._get_pool_quality(session)
                pool_by_source = self._get_pool_by_source(session)
                pool_avg_score_by_source = self._get_pool_avg_score_by_source(session)
                is_stats = self._get_is_stats_24h(session, window_24h)
                oos_stats = self._get_oos_stats_24h(session, window_24h)
                score_stats = self._get_score_stats_24h(session, window_24h)
                retest_stats = self._get_retest_stats_24h(session, window_24h)
                robustness_stats = self._get_robustness_stats_24h(session, window_24h)
                pool_robustness = self._get_pool_robustness_stats(session)
                live_stats = self._get_live_rotation_stats(session, window_24h)
                combo_stats = self._get_combo_stats_24h(session, window_24h)
                scheduler_stats = self._get_scheduler_stats(session)
                subaccount_stats = self._get_subaccount_stats(session)

                # Determine overall status
                status, issue = self._get_status_and_issue(
                    queue_depths, backpressure, throughput
                )

                # Save snapshot to database
                self._save_snapshot(
                    session, queue_depths, throughput, funnel, pool_quality, status
                )

                # Log metrics in pipeline order (10 steps)
                self._log_metrics(
                    status=status,
                    issue=issue,
                    queue_depths=queue_depths,
                    generator_stats=generator_stats,
                    ai_calls_today=ai_calls_today,
                    unused_patterns=unused_patterns,
                    funnel=funnel,
                    validation_by_source=validation_by_source,
                    timing=timing,
                    failures=failures,
                    backpressure=backpressure,
                    is_stats=is_stats,
                    oos_stats=oos_stats,
                    score_stats=score_stats,
                    pool_stats=pool_stats,
                    pool_quality=pool_quality,
                    pool_by_source=pool_by_source,
                    pool_avg_score_by_source=pool_avg_score_by_source,
                    pool_added_by_source=pool_added_by_source,
                    retest_stats=retest_stats,
                    robustness_stats=robustness_stats,
                    pool_robustness=pool_robustness,
                    live_stats=live_stats,
                    combo_stats=combo_stats,
                    scheduler_stats=scheduler_stats,
                    subaccount_stats=subaccount_stats,
                )

        except Exception as e:
            logger.error(f"Failed to collect metrics snapshot: {e}", exc_info=True)

    def _get_queue_depths(self, session) -> Dict[str, int]:
        """Get count of strategies by status."""
        result = session.execute(
            select(Strategy.status, func.count(Strategy.id))
            .group_by(Strategy.status)
        ).all()

        return {status: count for status, count in result}

    def _get_generation_by_source(self, session, since: datetime) -> Dict[str, int]:
        """
        Get generation counts by source type (pattern, ai_free, ai_assigned).

        Uses the pattern_based and ai_provider fields in event_data.
        - pattern_based=true → 'pattern'
        - pattern_based=false with ai_provider → 'ai' (can't distinguish free vs assigned from events)
        """
        # Query generation events with breakdown by pattern_based
        result = session.execute(
            text("""
                SELECT
                    CASE
                        WHEN (event_data->>'pattern_based')::boolean = true THEN 'pattern'
                        WHEN event_data->>'ai_provider' IS NOT NULL THEN 'ai'
                        ELSE 'unknown'
                    END as source_type,
                    COUNT(*) as count
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'generation'
                  AND event_type = 'created'
                GROUP BY
                    CASE
                        WHEN (event_data->>'pattern_based')::boolean = true THEN 'pattern'
                        WHEN event_data->>'ai_provider' IS NOT NULL THEN 'ai'
                        ELSE 'unknown'
                    END
            """),
            {'since': since}
        ).all()

        # Build dict with defaults
        sources = {'pattern': 0, 'ai': 0, 'unknown': 0}
        for source_type, count in result:
            sources[source_type] = count

        return sources

    def _get_generator_stats_24h(self, session, since: datetime) -> Dict[str, Any]:
        """
        Get detailed generator statistics for last 24h.

        Returns:
            Dict with:
            - total: Total strategies generated
            - by_source: Count by generation_mode (pattern, ai_free, ai_assigned)
            - by_type: Current strategy_type distribution (TRD, MOM, REV, VOL, CDL)
            - by_direction: Count by direction (LONG, SHORT, BIDIR)
            - by_timeframe: Count by timeframe (15m, 30m, 1h, 4h, 1d)
            - timing_by_source: Average generation time (ms) by source
            - leverage: Dict with min, max, avg leverage
        """
        # Single atomic query for all counts using CTE to avoid race conditions
        # All breakdowns are calculated from the same snapshot of data
        stats_result = session.execute(
            text("""
                WITH base AS (
                    SELECT
                        id,
                        event_data,
                        duration_ms
                    FROM strategy_events
                    WHERE timestamp >= :since
                      AND stage = 'generation'
                      AND event_type = 'created'
                ),
                -- Total count
                total_count AS (
                    SELECT COUNT(*) as cnt FROM base
                ),
                -- By source
                by_source AS (
                    SELECT
                        COALESCE(event_data->>'generation_mode',
                            CASE
                                WHEN (event_data->>'pattern_based')::boolean = true THEN 'pattern'
                                ELSE 'ai_free'
                            END
                        ) as source,
                        COUNT(*) as cnt
                    FROM base
                    GROUP BY 1
                ),
                -- By type (from strategies table - current state, not historical events)
                by_type AS (
                    SELECT
                        s.strategy_type as stype,
                        COUNT(*) as cnt
                    FROM strategies s
                    WHERE s.strategy_type IS NOT NULL
                    GROUP BY 1
                ),
                -- By direction
                by_direction AS (
                    SELECT
                        COALESCE(event_data->>'direction', 'UNKNOWN') as direction,
                        COUNT(*) as cnt
                    FROM base
                    GROUP BY 1
                ),
                -- By timeframe
                by_timeframe AS (
                    SELECT
                        event_data->>'timeframe' as tf,
                        COUNT(*) as cnt
                    FROM base
                    WHERE event_data->>'timeframe' IS NOT NULL
                    GROUP BY 1
                )
                SELECT
                    'total' as category, 'total' as key, cnt
                FROM total_count
                UNION ALL
                SELECT 'source' as category, source as key, cnt FROM by_source
                UNION ALL
                SELECT 'type' as category, stype as key, cnt FROM by_type WHERE stype IS NOT NULL
                UNION ALL
                SELECT 'direction' as category, direction as key, cnt FROM by_direction
                UNION ALL
                SELECT 'timeframe' as category, tf as key, cnt FROM by_timeframe WHERE tf IS NOT NULL
            """),
            {'since': since}
        ).all()

        # Parse results
        total = 0
        by_source = {
            'pattern': 0,
            'pattern_gen': 0,
            'pattern_gen_genetic': 0,
            'unger': 0,
            'unger_genetic': 0,
            'pandas_ta': 0,
            'ai_free': 0,
            'ai_assigned': 0,
        }
        by_type = {}
        by_direction = {'LONG': 0, 'SHORT': 0, 'BIDIR': 0}
        by_timeframe = {}

        for category, key, cnt in stats_result:
            if category == 'total':
                total = cnt
            elif category == 'source' and key in by_source:
                by_source[key] = cnt
            elif category == 'type' and key:
                by_type[key] = cnt
            elif category == 'direction' and key in by_direction:
                by_direction[key] = cnt
            elif category == 'timeframe' and key:
                by_timeframe[key] = cnt

        # Average timing by source
        timing_result = session.execute(
            text("""
                SELECT
                    COALESCE(event_data->>'generation_mode',
                        CASE
                            WHEN (event_data->>'pattern_based')::boolean = true THEN 'pattern'
                            ELSE 'ai_free'
                        END
                    ) as source,
                    AVG(duration_ms) as avg_ms
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'generation'
                  AND event_type = 'created'
                  AND duration_ms IS NOT NULL
                GROUP BY 1
            """),
            {'since': since}
        ).all()

        timing_by_source = {
            'pattern': None,
            'pattern_gen': None,
            'pattern_gen_genetic': None,
            'unger': None,
            'unger_genetic': None,
            'pandas_ta': None,
            'ai_free': None,
            'ai_assigned': None,
        }
        for source, avg_ms in timing_result:
            if source in timing_by_source and avg_ms is not None:
                timing_by_source[source] = float(avg_ms)

        # Leverage stats (min, max, avg)
        leverage_result = session.execute(
            text("""
                SELECT
                    MIN((event_data->>'leverage')::int) as min_lev,
                    MAX((event_data->>'leverage')::int) as max_lev,
                    AVG((event_data->>'leverage')::int) as avg_lev
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'generation'
                  AND event_type = 'created'
                  AND event_data->>'leverage' IS NOT NULL
            """),
            {'since': since}
        ).first()

        leverage = {
            'min': int(leverage_result[0]) if leverage_result and leverage_result[0] else None,
            'max': int(leverage_result[1]) if leverage_result and leverage_result[1] else None,
            'avg': float(leverage_result[2]) if leverage_result and leverage_result[2] else None
        }

        # By AI provider (claude, gemini, etc.) - excludes pattern-based (direct)
        by_provider_result = session.execute(
            text("""
                SELECT
                    COALESCE(event_data->>'ai_provider', 'unknown') as provider,
                    COUNT(*) as count
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'generation'
                  AND event_type = 'created'
                  AND COALESCE(event_data->>'ai_provider', 'direct') != 'direct'
                GROUP BY 1
                ORDER BY count DESC
            """),
            {'since': since}
        ).all()

        by_provider = {}
        for provider, count in by_provider_result:
            by_provider[provider] = count

        # Generation failures (validation failed before DB save)
        gen_failures = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'generation',
                StrategyEvent.event_type == 'failed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        return {
            'total': total,
            'by_source': by_source,
            'by_type': by_type,
            'by_direction': by_direction,
            'by_timeframe': by_timeframe,
            'timing_by_source': timing_by_source,
            'leverage': leverage,
            'by_provider': by_provider,
            'gen_failures': gen_failures
        }

    def _get_ai_calls_today(self) -> Dict[str, Any]:
        """
        Get AI call usage for today from ai_calls.json file.

        Returns:
            Dict with count, max_calls, remaining, or None values if file not found
        """
        import json
        from pathlib import Path

        state_file = Path("data/ai_calls.json")
        today = date.today().isoformat()

        if not state_file.exists():
            return {'count': None, 'max_calls': None, 'remaining': None}

        try:
            with open(state_file, 'r') as f:
                state = json.load(f)

            # Check if same day
            if state.get('date') == today:
                count = state.get('count', 0)
                max_calls = state.get('max_calls', 0)
                return {
                    'count': count,
                    'max_calls': max_calls,
                    'remaining': max(0, max_calls - count)
                }
            else:
                # New day, counter would reset
                return {
                    'count': 0,
                    'max_calls': state.get('max_calls', 0),
                    'remaining': state.get('max_calls', 0)
                }
        except Exception:
            return {'count': None, 'max_calls': None, 'remaining': None}

    def _get_unused_patterns(self, session) -> Dict[str, Any]:
        """
        Get pattern statistics (all time, not 24h).

        Returns:
            Dict with unique patterns used, total available, remaining, strategies count
        """
        # Get unique BASE pattern IDs ever used (from events, not strategies table)
        # Events persist when strategies are deleted, so this count is stable
        # Pattern IDs are stored in event_data->>'pattern_ids' as JSON array
        unique_used = session.execute(
            text("""
                SELECT COUNT(DISTINCT split_part(elem, '__', 1))
                FROM strategy_events se,
                     json_array_elements_text((se.event_data->>'pattern_ids')::json) AS elem
                WHERE se.stage = 'generation'
                  AND se.event_type = 'created'
                  AND se.event_data->>'pattern_ids' IS NOT NULL
            """)
        ).scalar() or 0

        # Fallback to strategies table if no events have pattern_ids yet
        # (for backward compatibility with strategies generated before this fix)
        if unique_used == 0:
            unique_used = session.execute(
                text("""
                    SELECT COUNT(DISTINCT split_part(elem, '__', 1))
                    FROM strategies s,
                         json_array_elements_text(s.pattern_ids) AS elem
                    WHERE s.pattern_based = true
                      AND s.pattern_ids IS NOT NULL
                """)
            ).scalar() or 0

        # Get total strategies generated from patterns (from events, stable count)
        strategies_generated = session.execute(
            text("""
                SELECT COUNT(*)
                FROM strategy_events
                WHERE stage = 'generation'
                  AND event_type = 'created'
                  AND event_data->>'generation_mode' = 'pattern'
            """)
        ).scalar() or 0

        # Try to get total patterns from pattern-discovery API (suppress logs)
        total_available = None
        try:
            pattern_api_url = self.config.get('pattern_discovery', {}).get('api_url')
            if pattern_api_url:
                import logging
                from src.generator.pattern_fetcher import PatternFetcher
                # Temporarily suppress pattern_fetcher logs
                pf_logger = logging.getLogger('src.generator.pattern_fetcher')
                old_level = pf_logger.level
                pf_logger.setLevel(logging.WARNING)
                try:
                    fetcher = PatternFetcher(api_url=pattern_api_url)
                    patterns = fetcher.get_tier_1_patterns(limit=500)
                    total_available = len(patterns) if patterns else None
                finally:
                    pf_logger.setLevel(old_level)
        except Exception:
            pass

        remaining = None
        if total_available is not None:
            remaining = max(0, total_available - unique_used)

        return {
            'unique_used': unique_used,
            'total_available': total_available,
            'remaining': remaining,
            'strategies_generated': strategies_generated
        }

    def _get_pool_by_source(self, session) -> Dict[str, int]:
        """
        Get ACTIVE pool composition by generation_mode.
        """
        result = session.execute(
            select(Strategy.generation_mode, func.count(Strategy.id))
            .where(Strategy.status == 'ACTIVE')
            .group_by(Strategy.generation_mode)
        ).all()

        # Build dict with defaults (matches config.yaml strategy_sources)
        sources = {
            'pattern': 0,
            'pattern_gen': 0,
            'pattern_gen_genetic': 0,
            'unger': 0,
            'unger_genetic': 0,
            'pandas_ta': 0,
            'ai_free': 0,
            'ai_assigned': 0,
            'unknown': 0,
        }
        for mode, count in result:
            if mode in sources:
                sources[mode] = count
            elif mode:
                sources['unknown'] += count

        return sources

    def _get_pool_avg_score_by_source(self, session) -> Dict[str, Optional[float]]:
        """
        Get average score of ACTIVE pool strategies by generation_mode.
        """
        result = session.execute(
            select(Strategy.generation_mode, func.avg(Strategy.score_backtest))
            .where(Strategy.status == 'ACTIVE')
            .group_by(Strategy.generation_mode)
        ).all()

        sources: Dict[str, Optional[float]] = {
            'pattern': None,
            'pattern_gen': None,
            'pattern_gen_genetic': None,
            'unger': None,
            'unger_genetic': None,
            'pandas_ta': None,
            'ai_free': None,
            'ai_assigned': None,
        }
        for mode, avg_score in result:
            if mode in sources and avg_score is not None:
                sources[mode] = float(avg_score)

        return sources

    def _get_funnel_24h(self, session, since: datetime) -> Dict[str, Any]:
        """
        Get pipeline funnel metrics for last 24h.

        Returns counts and pass rates for each stage.
        """
        # Generated
        generated = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'generation',
                StrategyEvent.event_type == 'created',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Validated (passed validation)
        validated = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'validation',
                StrategyEvent.event_type == 'completed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Validation failed (for funnel clarity)
        validation_failed = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'validation',
                StrategyEvent.status == 'failed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Parametric output: strategies that exited parametric (passed IS threshold)
        # = scored (passed OOS) + oos_failed (failed OOS but exited parametric)
        parametric_scored = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'backtest',
                StrategyEvent.event_type == 'scored',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        parametric_oos_failed = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'backtest',
                StrategyEvent.event_type == 'oos_failed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Total strategies that exited parametric (before OOS validation)
        parametric_output = parametric_scored + parametric_oos_failed

        # Parametric failed (no valid combinations found - base rejected)
        parametric_failed = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'backtest',
                StrategyEvent.event_type == 'parametric_failed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Score OK (passed score threshold)
        score_ok = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'shuffle_test',
                StrategyEvent.event_type == 'started',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Shuffle OK
        shuffle_ok = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'shuffle_test',
                StrategyEvent.status == 'passed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Multi-window started (for in_progress tracking)
        mw_started = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'multi_window',
                StrategyEvent.event_type == 'started',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Multi-window OK
        mw_ok = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'multi_window',
                StrategyEvent.status == 'passed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Multi-window failed (for in_progress calculation)
        mw_failed = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'multi_window',
                StrategyEvent.status == 'failed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Pool entries
        pool_entered = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'pool',
                StrategyEvent.event_type == 'entered',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Sum combinations_tested per UNIQUE base (not per strategy output)
        # Each base tests ~1015 combos, but multiple strategies may pass from same base
        # We use DISTINCT strategy_name to count each base only once
        # Note: Only parametric_failed events have combinations_tested populated reliably
        combo_result = session.execute(
            text("""
                SELECT COUNT(*), COALESCE(SUM(combos), 0) FROM (
                    SELECT DISTINCT ON (strategy_name)
                        (event_data->>'combinations_tested')::int as combos
                    FROM strategy_events
                    WHERE timestamp >= :since
                      AND stage = 'backtest'
                      AND event_type IN ('scored', 'score_rejected', 'parametric_failed')
                      AND event_data->>'combinations_tested' IS NOT NULL
                    ORDER BY strategy_name, timestamp DESC
                ) sub
            """),
            {'since': since}
        ).first()
        bases_with_combos = combo_result[0] if combo_result else 0
        combinations_tested = combo_result[1] if combo_result else 0

        # Count unique bases that completed parametric backtest (all, for reference)
        bases_completed = session.execute(
            text("""
                SELECT COUNT(DISTINCT strategy_name)
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type IN ('scored', 'score_rejected', 'parametric_failed')
            """),
            {'since': since}
        ).scalar() or 0

        # Count unique bases that produced at least one strategy (using base_code_hash)
        # base_code_hash links parametric output strategies back to their base template
        # Include both scored (passed OOS) and oos_failed (failed OOS but exited parametric)
        bases_with_output = session.execute(
            text("""
                SELECT COUNT(DISTINCT base_code_hash)
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type IN ('scored', 'oos_failed')
                  AND base_code_hash IS NOT NULL
            """),
            {'since': since}
        ).scalar() or 0

        # Calculate pass rates
        def pct(num: int, denom: int) -> Optional[int]:
            if denom == 0:
                return None
            return int(round(100 * num / denom))

        return {
            'generated': generated,
            'validated': validated,
            'validation_failed': validation_failed,
            'validated_pct': pct(validated, generated),
            'bases_completed': bases_completed,
            'bases_with_combos': bases_with_combos,
            'bases_with_output': bases_with_output,
            'combinations_tested': combinations_tested,
            # Parametric output = strategies that exited (passed IS threshold)
            'parametric_output': parametric_output,
            'parametric_scored': parametric_scored,  # Passed OOS too
            'parametric_oos_failed': parametric_oos_failed,  # Failed OOS
            'parametric_failed': parametric_failed,  # Base rejected (no valid combos)
            'parametric_completed': parametric_output + parametric_failed,
            'score_ok': score_ok,
            'score_ok_pct': pct(score_ok, parametric_scored),
            'shuffle_ok': shuffle_ok,
            'shuffle_ok_pct': pct(shuffle_ok, score_ok),
            'mw_started': mw_started,
            'mw_ok': mw_ok,
            'mw_failed': mw_failed,
            'mw_ok_pct': pct(mw_ok, shuffle_ok),
            'pool': pool_entered,
            'pool_pct': pct(pool_entered, mw_ok if mw_ok > 0 else shuffle_ok),
        }

    def _get_validation_by_source_24h(self, session, since: datetime) -> Dict[str, Dict[str, int]]:
        """
        Get validation passed/failed counts by generation_mode (source).

        Joins strategy_events with strategies table to get generation_mode.
        Returns dict with 'passed' and 'failed' sub-dicts by source.
        """
        # Query validation events joined with strategies for generation_mode
        result = session.execute(
            text("""
                WITH validation_events AS (
                    SELECT
                        e.strategy_id,
                        CASE
                            WHEN e.event_type = 'completed' AND e.status = 'completed' THEN 'passed'
                            WHEN e.status = 'failed' THEN 'failed'
                        END as result
                    FROM strategy_events e
                    WHERE e.timestamp >= :since
                      AND e.stage = 'validation'
                      AND (
                          (e.event_type = 'completed' AND e.status = 'completed')
                          OR e.status = 'failed'
                      )
                )
                SELECT
                    COALESCE(s.generation_mode, 'unknown') as source,
                    v.result,
                    COUNT(*) as cnt
                FROM validation_events v
                JOIN strategies s ON s.id = v.strategy_id
                GROUP BY s.generation_mode, v.result
            """),
            {'since': since}
        ).all()

        # Initialize with all known sources
        sources = ['pattern', 'pattern_gen', 'pattern_gen_genetic', 'unger', 'pandas_ta', 'ai_free', 'ai_assigned']
        passed = {s: 0 for s in sources}
        failed = {s: 0 for s in sources}

        for source, result_type, cnt in result:
            if source in passed:
                if result_type == 'passed':
                    passed[source] = cnt
                elif result_type == 'failed':
                    failed[source] = cnt

        return {'passed': passed, 'failed': failed}

    def _get_pool_added_by_source_24h(self, session, since: datetime) -> Dict[str, int]:
        """
        Get pool entries (24h added) by generation_mode (source).

        Joins strategy_events (pool.entered) with strategies table.
        """
        result = session.execute(
            text("""
                SELECT
                    COALESCE(s.generation_mode, 'unknown') as source,
                    COUNT(*) as cnt
                FROM strategy_events e
                JOIN strategies s ON s.id = e.strategy_id
                WHERE e.timestamp >= :since
                  AND e.stage = 'pool'
                  AND e.event_type = 'entered'
                GROUP BY s.generation_mode
            """),
            {'since': since}
        ).all()

        # Initialize with all known sources
        sources = {
            'pattern': 0, 'pattern_gen': 0, 'pattern_gen_genetic': 0,
            'unger': 0, 'unger_genetic': 0, 'pandas_ta': 0, 'ai_free': 0, 'ai_assigned': 0
        }
        for source, cnt in result:
            if source in sources:
                sources[source] = cnt

        return sources

    def _get_combo_stats_24h(self, session, since: datetime) -> Dict:
        """
        Aggregate combo_stats from parametric_stats events.

        Returns dict with aggregated statistics:
        {
            total_combos, passed_combos, failed_combos,
            bases_with_passed, bases_with_failed,
            fail_reasons: {sharpe, trades, wr, exp, dd},
            failed_avg: {sharpe, wr, exp, trades},
            passed_avg: {sharpe, wr, exp, trades}
        }
        """
        result = session.execute(
            text("""
                SELECT
                    COALESCE(SUM((event_data->'combo_stats'->>'total')::int), 0) as total_combos,
                    COALESCE(SUM((event_data->'combo_stats'->>'passed')::int), 0) as passed_combos,
                    COALESCE(SUM((event_data->'combo_stats'->>'failed')::int), 0) as failed_combos,
                    COUNT(DISTINCT CASE WHEN (event_data->'combo_stats'->>'passed')::int > 0
                          THEN base_code_hash END) as bases_with_passed,
                    COUNT(DISTINCT CASE WHEN (event_data->'combo_stats'->>'passed')::int = 0
                          THEN base_code_hash END) as bases_with_failed,
                    COALESCE(SUM((event_data->'combo_stats'->'fail_reasons'->>'sharpe')::int), 0) as fail_sharpe,
                    COALESCE(SUM((event_data->'combo_stats'->'fail_reasons'->>'trades')::int), 0) as fail_trades,
                    COALESCE(SUM((event_data->'combo_stats'->'fail_reasons'->>'wr')::int), 0) as fail_wr,
                    COALESCE(SUM((event_data->'combo_stats'->'fail_reasons'->>'exp')::int), 0) as fail_exp,
                    COALESCE(SUM((event_data->'combo_stats'->'fail_reasons'->>'dd')::int), 0) as fail_dd,
                    -- Weighted averages for failed combos
                    CASE WHEN SUM((event_data->'combo_stats'->>'failed')::int) > 0 THEN
                        SUM((event_data->'combo_stats'->'failed_avg'->>'sharpe')::float *
                            (event_data->'combo_stats'->>'failed')::int) /
                        SUM((event_data->'combo_stats'->>'failed')::int)
                    ELSE 0 END as failed_avg_sharpe,
                    CASE WHEN SUM((event_data->'combo_stats'->>'failed')::int) > 0 THEN
                        SUM((event_data->'combo_stats'->'failed_avg'->>'wr')::float *
                            (event_data->'combo_stats'->>'failed')::int) /
                        SUM((event_data->'combo_stats'->>'failed')::int)
                    ELSE 0 END as failed_avg_wr,
                    CASE WHEN SUM((event_data->'combo_stats'->>'failed')::int) > 0 THEN
                        SUM((event_data->'combo_stats'->'failed_avg'->>'exp')::float *
                            (event_data->'combo_stats'->>'failed')::int) /
                        SUM((event_data->'combo_stats'->>'failed')::int)
                    ELSE 0 END as failed_avg_exp,
                    CASE WHEN SUM((event_data->'combo_stats'->>'failed')::int) > 0 THEN
                        SUM((event_data->'combo_stats'->'failed_avg'->>'trades')::float *
                            (event_data->'combo_stats'->>'failed')::int) /
                        SUM((event_data->'combo_stats'->>'failed')::int)
                    ELSE 0 END as failed_avg_trades,
                    -- Weighted averages for passed combos
                    CASE WHEN SUM((event_data->'combo_stats'->>'passed')::int) > 0 THEN
                        SUM((event_data->'combo_stats'->'passed_avg'->>'sharpe')::float *
                            (event_data->'combo_stats'->>'passed')::int) /
                        SUM((event_data->'combo_stats'->>'passed')::int)
                    ELSE 0 END as passed_avg_sharpe,
                    CASE WHEN SUM((event_data->'combo_stats'->>'passed')::int) > 0 THEN
                        SUM((event_data->'combo_stats'->'passed_avg'->>'wr')::float *
                            (event_data->'combo_stats'->>'passed')::int) /
                        SUM((event_data->'combo_stats'->>'passed')::int)
                    ELSE 0 END as passed_avg_wr,
                    CASE WHEN SUM((event_data->'combo_stats'->>'passed')::int) > 0 THEN
                        SUM((event_data->'combo_stats'->'passed_avg'->>'exp')::float *
                            (event_data->'combo_stats'->>'passed')::int) /
                        SUM((event_data->'combo_stats'->>'passed')::int)
                    ELSE 0 END as passed_avg_exp,
                    CASE WHEN SUM((event_data->'combo_stats'->>'passed')::int) > 0 THEN
                        SUM((event_data->'combo_stats'->'passed_avg'->>'trades')::float *
                            (event_data->'combo_stats'->>'passed')::int) /
                        SUM((event_data->'combo_stats'->>'passed')::int)
                    ELSE 0 END as passed_avg_trades,
                    -- Count only bases that have a matching generation.created event
                    -- (excludes orphan parametric_stats from previous sessions after reset)
                    COUNT(DISTINCT CASE
                        WHEN base_code_hash IN (
                            SELECT DISTINCT base_code_hash
                            FROM strategy_events
                            WHERE stage = 'generation'
                              AND event_type = 'created'
                              AND timestamp >= :since
                        ) THEN base_code_hash
                    END) as total_bases,
                    -- Duration stats per base (parametric backtest time)
                    AVG(duration_ms) as avg_duration_ms,
                    MIN(duration_ms) as min_duration_ms,
                    MAX(duration_ms) as max_duration_ms
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type = 'parametric_stats'
                  AND event_data->'combo_stats' IS NOT NULL
            """),
            {'since': since}
        ).first()

        if not result or result[0] == 0:
            return {}

        return {
            'total_combos': result[0],
            'passed_combos': result[1],
            'failed_combos': result[2],
            'bases_with_passed': result[3],
            'bases_with_failed': result[4],
            'fail_reasons': {
                'sharpe': result[5],
                'trades': result[6],
                'wr': result[7],
                'exp': result[8],
                'dd': result[9],
            },
            'failed_avg': {
                'sharpe': result[10] or 0,
                'wr': result[11] or 0,
                'exp': result[12] or 0,
                'trades': result[13] or 0,
            },
            'passed_avg': {
                'sharpe': result[14] or 0,
                'wr': result[15] or 0,
                'exp': result[16] or 0,
                'trades': result[17] or 0,
            },
            'total_bases': result[18],
            'avg_duration_ms': float(result[19]) if result[19] else None,
            'min_duration_ms': float(result[20]) if result[20] else None,
            'max_duration_ms': float(result[21]) if result[21] else None,
        }

    def _get_timing_avg_24h(self, session, since: datetime) -> Dict[str, Optional[float]]:
        """Get average timing metrics per phase for last 24h."""
        timing = {}

        stages = [
            ('validation', 'validation'),
            ('backtest', 'backtest'),
            ('shuffle_test', 'shuffle'),
            ('multi_window', 'multiwindow'),
        ]

        for db_stage, key in stages:
            avg_ms = session.execute(
                select(func.avg(StrategyEvent.duration_ms))
                .where(and_(
                    StrategyEvent.stage == db_stage,
                    StrategyEvent.duration_ms.isnot(None),
                    StrategyEvent.timestamp >= since
                ))
            ).scalar()

            timing[key] = float(avg_ms) if avg_ms is not None else None

        return timing

    def _get_throughput_interval(
        self, session, since: datetime
    ) -> Dict[str, int]:
        """Get throughput (counts) for each stage in the interval."""
        # Generation
        gen = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'generation',
                StrategyEvent.event_type == 'created',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Validation completed
        val = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'validation',
                StrategyEvent.event_type == 'completed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Backtest completed (scored OR parametric_failed)
        # Counts all backtests that ran, not just those that passed thresholds
        bt = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'backtest',
                StrategyEvent.event_type.in_(['scored', 'parametric_failed']),
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Score passed (shuffle started)
        score = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'shuffle_test',
                StrategyEvent.event_type == 'started',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Shuffle passed
        shuf = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'shuffle_test',
                StrategyEvent.status == 'passed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Multi-window passed
        mw = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'multi_window',
                StrategyEvent.status == 'passed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Pool entered
        pool = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'pool',
                StrategyEvent.event_type == 'entered',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        return {
            'gen': gen,
            'val': val,
            'bt': bt,
            'score': score,
            'shuf': shuf,
            'mw': mw,
            'pool': pool,
        }

    def _get_failures_24h(self, session, since: datetime) -> Dict[str, int]:
        """Get failure counts by type for last 24h."""
        # Validation failures
        validation_fail = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'validation',
                StrategyEvent.status == 'failed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Parametric failed (no valid combinations)
        parametric_fail = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'backtest',
                StrategyEvent.event_type == 'parametric_failed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Score rejected
        score_reject = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'backtest',
                StrategyEvent.event_type == 'score_rejected',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Shuffle failed
        shuffle_fail = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'shuffle_test',
                StrategyEvent.status == 'failed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Shuffle cached count (for info)
        shuffle_cached = session.execute(
            text("""
                SELECT COUNT(*)
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'shuffle_test'
                  AND (event_data->>'cached')::boolean = true
            """),
            {'since': since}
        ).scalar() or 0

        # Multi-window failed
        mw_fail = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'multi_window',
                StrategyEvent.status == 'failed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Pool rejected
        pool_reject = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'pool',
                StrategyEvent.event_type == 'rejected',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        return {
            'validation': validation_fail,
            'parametric_fail': parametric_fail,
            'score_reject': score_reject,
            'shuffle_fail': shuffle_fail,
            'shuffle_cached': shuffle_cached,
            'mw_fail': mw_fail,
            'pool_reject': pool_reject,
        }

    def _get_backpressure_status(
        self, session, queue_depths: Dict[str, int]
    ) -> Dict[str, Any]:
        """Get backpressure status (queue depths and processing counts)."""
        gen_count = queue_depths.get('GENERATED', 0)
        val_count = queue_depths.get('VALIDATED', 0)

        # Count strategies currently being processed
        bt_processing = session.execute(
            select(func.count(Strategy.id))
            .where(and_(
                Strategy.status == 'VALIDATED',
                Strategy.processing_by.isnot(None)
            ))
        ).scalar() or 0

        bt_waiting = val_count - bt_processing

        # Check if queues are full
        gen_full = gen_count >= self.limit_generated
        val_full = val_count >= self.limit_validated

        return {
            'gen_queue': gen_count,
            'gen_limit': self.limit_generated,
            'gen_full': gen_full,
            'val_queue': val_count,
            'val_limit': self.limit_validated,
            'bt_waiting': bt_waiting,
            'bt_processing': bt_processing,
        }

    def _get_pool_stats(self, session) -> Dict[str, Any]:
        """Get ACTIVE pool statistics."""
        # Pool size
        pool_size = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.status == 'ACTIVE')
        ).scalar() or 0

        # Score stats
        score_stats = session.execute(
            select(
                func.min(Strategy.score_backtest),
                func.max(Strategy.score_backtest),
                func.avg(Strategy.score_backtest),
            )
            .where(Strategy.status == 'ACTIVE')
        ).first()

        return {
            'size': pool_size,
            'limit': self.limit_active,
            'score_min': float(score_stats[0]) if score_stats[0] else None,
            'score_max': float(score_stats[1]) if score_stats[1] else None,
            'score_avg': float(score_stats[2]) if score_stats[2] else None,
        }

    def _get_pool_quality(self, session) -> Dict[str, Any]:
        """Get quality metrics for ACTIVE pool strategies."""
        # Note: Use in-sample backtest metrics (more stable than OOS)
        # weighted_sharpe_pure is inflated by short OOS period
        result = session.execute(
            select(
                func.avg(BacktestResult.expectancy),      # IS expectancy
                func.avg(BacktestResult.sharpe_ratio),    # IS sharpe (not inflated)
                func.avg(BacktestResult.win_rate),        # IS win rate
                func.avg(BacktestResult.max_drawdown),    # IS drawdown
            )
            .join(Strategy, BacktestResult.strategy_id == Strategy.id)
            .where(and_(
                Strategy.status == 'ACTIVE',
                BacktestResult.period_type == 'in_sample'
            ))
        ).first()

        if result and result[0] is not None:
            return {
                'expectancy_avg': float(result[0]) if result[0] else None,
                'sharpe_avg': float(result[1]) if result[1] else None,
                'winrate_avg': float(result[2]) if result[2] else None,
                'dd_avg': float(result[3]) if result[3] else None,
            }

        return {
            'expectancy_avg': None,
            'sharpe_avg': None,
            'winrate_avg': None,
            'dd_avg': None,
        }

    def _get_is_stats_24h(self, session, since: datetime) -> Dict[str, Any]:
        """
        Get IN-SAMPLE backtest statistics for last 24h.

        IS passed = strategies that reached OOS (passed IS validation):
        - BacktestResult OOS (strategies that passed both IS and OOS)
        - oos_failed events (strategies that passed IS but failed OOS)

        IS failed = is_failed events (strategies that failed IS validation)

        Returns passed/failed counts, avg metrics for each, and fail reasons.
        """
        # IS passed count from BacktestResult OOS (strategies that passed everything)
        oos_passed_result = session.execute(
            select(func.count(BacktestResult.id))
            .where(and_(
                BacktestResult.period_type == 'out_of_sample',
                BacktestResult.created_at >= since
            ))
        ).scalar() or 0

        # IS passed count from oos_failed events (passed IS, failed OOS)
        oos_failed_count_result = session.execute(
            text("""
                SELECT COUNT(*)
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type = 'oos_failed'
                  AND event_data->>'reason' NOT LIKE 'IS %'
            """),
            {'since': since}
        ).scalar() or 0

        passed_count = oos_passed_result + oos_failed_count_result

        # IS passed avg metrics: combine from BacktestResult IS + oos_failed IS metrics
        # From BacktestResult IS (strategies that passed everything)
        br_is_result = session.execute(
            select(
                func.count(BacktestResult.id),
                func.sum(BacktestResult.sharpe_ratio),
                func.sum(BacktestResult.win_rate),
                func.sum(BacktestResult.expectancy),
                func.sum(BacktestResult.total_trades),
            )
            .where(and_(
                BacktestResult.period_type == 'in_sample',
                BacktestResult.created_at >= since
            ))
        ).first()

        br_count = br_is_result[0] if br_is_result else 0
        br_sums = {
            'sharpe': float(br_is_result[1]) if br_is_result and br_is_result[1] else 0,
            'wr': float(br_is_result[2]) if br_is_result and br_is_result[2] else 0,
            'exp': float(br_is_result[3]) if br_is_result and br_is_result[3] else 0,
            'trades': float(br_is_result[4]) if br_is_result and br_is_result[4] else 0,
        }

        # From oos_failed events (passed IS, failed OOS) - get IS metrics
        oos_failed_is_result = session.execute(
            text("""
                SELECT
                    COUNT(*),
                    SUM((event_data->>'is_sharpe')::float),
                    SUM((event_data->>'is_win_rate')::float),
                    SUM((event_data->>'is_expectancy')::float),
                    SUM((event_data->>'is_trades')::float)
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type = 'oos_failed'
                  AND event_data->>'reason' NOT LIKE 'IS %'
            """),
            {'since': since}
        ).first()

        oos_f_count = oos_failed_is_result[0] if oos_failed_is_result else 0
        oos_f_sums = {
            'sharpe': float(oos_failed_is_result[1]) if oos_failed_is_result and oos_failed_is_result[1] else 0,
            'wr': float(oos_failed_is_result[2]) if oos_failed_is_result and oos_failed_is_result[2] else 0,
            'exp': float(oos_failed_is_result[3]) if oos_failed_is_result and oos_failed_is_result[3] else 0,
            'trades': float(oos_failed_is_result[4]) if oos_failed_is_result and oos_failed_is_result[4] else 0,
        }

        # Weighted average
        total_passed = br_count + oos_f_count
        if total_passed > 0:
            passed_avg = {
                'sharpe': (br_sums['sharpe'] + oos_f_sums['sharpe']) / total_passed,
                'wr': (br_sums['wr'] + oos_f_sums['wr']) / total_passed,
                'exp': (br_sums['exp'] + oos_f_sums['exp']) / total_passed,
                'trades': (br_sums['trades'] + oos_f_sums['trades']) / total_passed,
            }
        else:
            passed_avg = {'sharpe': None, 'wr': None, 'exp': None, 'trades': None}

        # Failed strategies: from is_failed events
        failed_result = session.execute(
            text("""
                SELECT
                    COUNT(*),
                    AVG((event_data->>'is_sharpe')::float),
                    AVG((event_data->>'is_win_rate')::float),
                    AVG((event_data->>'is_expectancy')::float),
                    AVG((event_data->>'is_trades')::float),
                    AVG(duration_ms)
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type = 'is_failed'
            """),
            {'since': since}
        ).first()

        failed_count = failed_result[0] if failed_result else 0
        failed_avg = {
            'sharpe': float(failed_result[1]) if failed_result and failed_result[1] else None,
            'wr': float(failed_result[2]) if failed_result and failed_result[2] else None,
            'exp': float(failed_result[3]) if failed_result and failed_result[3] else None,
            'trades': float(failed_result[4]) if failed_result and failed_result[4] else None,
        }

        # Average timing from ALL IS events (both passed and failed)
        is_timing_result = session.execute(
            text("""
                SELECT AVG(duration_ms)
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type IN ('is_passed', 'is_failed')
                  AND duration_ms IS NOT NULL
            """),
            {'since': since}
        ).scalar()
        is_avg_duration_ms = float(is_timing_result) if is_timing_result else None

        # Fail reasons breakdown (from fail_types dict in is_failed events)
        # CUMULATIVE: each strategy counted for ALL thresholds it violates (like PARAMETRIC)
        fail_reasons_result = session.execute(
            text("""
                SELECT
                    COALESCE(SUM((event_data->'fail_types'->>'sharpe')::int), 0) as fail_sharpe,
                    COALESCE(SUM((event_data->'fail_types'->>'wr')::int), 0) as fail_wr,
                    COALESCE(SUM((event_data->'fail_types'->>'exp')::int), 0) as fail_exp,
                    COALESCE(SUM((event_data->'fail_types'->>'dd')::int), 0) as fail_dd,
                    COALESCE(SUM((event_data->'fail_types'->>'trades')::int), 0) as fail_trades
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type = 'is_failed'
                  AND event_data->'fail_types' IS NOT NULL
            """),
            {'since': since}
        ).first()

        fail_reasons = {
            'sharpe': int(fail_reasons_result[0]) if fail_reasons_result else 0,
            'wr': int(fail_reasons_result[1]) if fail_reasons_result else 0,
            'exp': int(fail_reasons_result[2]) if fail_reasons_result else 0,
            'dd': int(fail_reasons_result[3]) if fail_reasons_result else 0,
            'trades': int(fail_reasons_result[4]) if fail_reasons_result else 0,
        }

        total_count = passed_count + failed_count

        return {
            'count': total_count,
            'passed': passed_count,
            'failed': failed_count,
            'passed_avg': passed_avg,
            'failed_avg': failed_avg,
            'fail_reasons': fail_reasons,
            'avg_duration_ms': is_avg_duration_ms,
        }

    def _get_oos_stats_24h(self, session, since: datetime) -> Dict[str, Any]:
        """
        Get OUT-OF-SAMPLE validation statistics for last 24h.

        Combines:
        - BacktestResult (strategies that passed OOS validation)
        - oos_failed events (strategies that failed OOS validation)

        Returns passed/failed counts, avg metrics for each, and fail reasons.
        """
        # Passed strategies: from BacktestResult (OOS period)
        passed_result = session.execute(
            select(
                func.count(BacktestResult.id),
                func.avg(BacktestResult.sharpe_ratio),
                func.avg(BacktestResult.win_rate),
                func.avg(BacktestResult.expectancy),
                func.avg(BacktestResult.total_trades),
                func.avg(BacktestResult.max_drawdown),
            )
            .where(and_(
                BacktestResult.period_type == 'out_of_sample',
                BacktestResult.created_at >= since
            ))
        ).first()

        passed_count = passed_result[0] if passed_result else 0
        passed_avg = {
            'sharpe': float(passed_result[1]) if passed_result and passed_result[1] else None,
            'wr': float(passed_result[2]) if passed_result and passed_result[2] else None,
            'exp': float(passed_result[3]) if passed_result and passed_result[3] else None,
            'trades': float(passed_result[4]) if passed_result and passed_result[4] else None,
            'dd': float(passed_result[5]) if passed_result and passed_result[5] else None,
        }

        # Failed strategies: from oos_failed events (includes OOS metrics now)
        # Exclude old events where IS failures were incorrectly logged as oos_failed
        # (before is_failed event type was introduced)
        failed_result = session.execute(
            text("""
                SELECT
                    COUNT(*),
                    AVG((event_data->>'oos_sharpe')::float),
                    AVG((event_data->>'oos_win_rate')::float),
                    AVG((event_data->>'oos_expectancy')::float),
                    AVG((event_data->>'oos_trades')::float),
                    AVG((event_data->>'oos_max_drawdown')::float),
                    AVG(duration_ms)
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type = 'oos_failed'
                  AND event_data->>'reason' NOT LIKE 'IS %'
            """),
            {'since': since}
        ).first()

        failed_count = failed_result[0] if failed_result else 0
        failed_avg = {
            'sharpe': float(failed_result[1]) if failed_result and failed_result[1] else None,
            'wr': float(failed_result[2]) if failed_result and failed_result[2] else None,
            'exp': float(failed_result[3]) if failed_result and failed_result[3] else None,
            'trades': float(failed_result[4]) if failed_result and failed_result[4] else None,
            'dd': float(failed_result[5]) if failed_result and failed_result[5] else None,
        }

        # Average timing from ALL OOS events (both passed and failed)
        oos_timing_result = session.execute(
            text("""
                SELECT AVG(duration_ms)
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type IN ('oos_passed', 'oos_failed')
                  AND duration_ms IS NOT NULL
            """),
            {'since': since}
        ).scalar()
        oos_avg_duration_ms = float(oos_timing_result) if oos_timing_result else None

        # Fail reasons breakdown (from fail_types dict in oos_failed events)
        # CUMULATIVE: each strategy counted for ALL thresholds it violates (like PARAMETRIC)
        fail_reasons_result = session.execute(
            text("""
                SELECT
                    COALESCE(SUM((event_data->'fail_types'->>'sharpe')::int), 0) as fail_sharpe,
                    COALESCE(SUM((event_data->'fail_types'->>'wr')::int), 0) as fail_wr,
                    COALESCE(SUM((event_data->'fail_types'->>'exp')::int), 0) as fail_exp,
                    COALESCE(SUM((event_data->'fail_types'->>'dd')::int), 0) as fail_dd,
                    COALESCE(SUM((event_data->'fail_types'->>'trades')::int), 0) as fail_trades,
                    COALESCE(SUM((event_data->'fail_types'->>'degradation')::int), 0) as fail_degradation
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type = 'oos_failed'
                  AND event_data->'fail_types' IS NOT NULL
            """),
            {'since': since}
        ).first()

        fail_reasons = {
            'sharpe': int(fail_reasons_result[0]) if fail_reasons_result else 0,
            'wr': int(fail_reasons_result[1]) if fail_reasons_result else 0,
            'exp': int(fail_reasons_result[2]) if fail_reasons_result else 0,
            'dd': int(fail_reasons_result[3]) if fail_reasons_result else 0,
            'trades': int(fail_reasons_result[4]) if fail_reasons_result else 0,
            'degradation': int(fail_reasons_result[5]) if fail_reasons_result else 0,
        }

        # Get degradation stats for passed strategies (from IS rows)
        # recency_ratio = 1 - degradation, so degradation = 1 - recency_ratio
        passed_degrad_result = session.execute(
            select(
                func.avg(1 - BacktestResult.recency_ratio),
                func.sum(func.cast(BacktestResult.recency_ratio >= 1.0, Integer)),
                func.sum(func.cast(BacktestResult.recency_ratio < 1.0, Integer)),
            )
            .where(and_(
                BacktestResult.period_type == 'in_sample',
                BacktestResult.recency_ratio.isnot(None),
                BacktestResult.created_at >= since
            ))
        ).first()

        p_degrad = float(passed_degrad_result[0]) if passed_degrad_result and passed_degrad_result[0] else 0
        p_better = int(passed_degrad_result[1]) if passed_degrad_result and passed_degrad_result[1] else 0
        p_worse = int(passed_degrad_result[2]) if passed_degrad_result and passed_degrad_result[2] else 0

        total_count = passed_count + failed_count

        # Calculate avg degradation (only for passed, since failed have fail_type=degradation tracked)
        avg_degradation = p_degrad if passed_count > 0 else None

        return {
            'count': total_count,
            'passed': passed_count,
            'failed': failed_count,
            'passed_avg': passed_avg,
            'failed_avg': failed_avg,
            'fail_reasons': fail_reasons,
            'avg_degradation': avg_degradation,
            'oos_better': p_better,
            'oos_worse': p_worse,
            'avg_duration_ms': oos_avg_duration_ms,
        }

    def _get_score_stats_24h(self, session, since: datetime) -> Dict[str, Any]:
        """Get score calculation statistics for last 24h.

        Includes ALL scored strategies (both passed and failed min_score threshold).
        Sources:
        - shuffle_test.started: strategies that passed score threshold
        - backtest.score_rejected: strategies that failed score threshold
        """
        # Query combines both passed (shuffle_test.started) and failed (score_rejected)
        result = session.execute(
            text("""
                WITH all_scores AS (
                    -- Strategies that passed score threshold (went to shuffle test)
                    SELECT (event_data->>'score')::float as score
                    FROM strategy_events
                    WHERE timestamp >= :since
                      AND stage = 'shuffle_test'
                      AND event_type = 'started'
                      AND event_data->>'score' IS NOT NULL

                    UNION ALL

                    -- Strategies that failed score threshold (score_rejected event)
                    SELECT (event_data->>'score')::float as score
                    FROM strategy_events
                    WHERE timestamp >= :since
                      AND stage = 'backtest'
                      AND event_type = 'score_rejected'
                      AND event_data->>'score' IS NOT NULL
                )
                SELECT
                    MIN(score) as min_score,
                    MAX(score) as max_score,
                    AVG(score) as avg_score
                FROM all_scores
                WHERE score IS NOT NULL
            """),
            {'since': since}
        ).first()

        return {
            'min_score': float(result[0]) if result and result[0] else None,
            'max_score': float(result[1]) if result and result[1] else None,
            'avg_score': float(result[2]) if result and result[2] else None,
        }

    def _get_retest_stats_24h(self, session, since: datetime) -> Dict[str, Any]:
        """Get re-backtest statistics for last 24h."""
        # A retest is when a strategy that was already ACTIVE gets backtested again.
        # We detect this by: created_at < since (strategy existed before 24h window)
        # AND last_backtested_at >= since (backtested in last 24h)
        # First backtest: created_at and last_backtested_at are both recent
        # Retest: created_at is old, last_backtested_at is recent

        # Retested = strategies created BEFORE the 24h window
        # but backtested WITHIN the 24h window (true retest)
        retested = session.execute(
            select(func.count(Strategy.id))
            .where(and_(
                Strategy.created_at < since,  # Created before 24h ago
                Strategy.last_backtested_at >= since,  # Backtested in last 24h
                Strategy.status.in_(['ACTIVE', 'RETIRED'])
            ))
        ).scalar() or 0

        # Passed = still ACTIVE after retest
        passed = session.execute(
            select(func.count(Strategy.id))
            .where(and_(
                Strategy.created_at < since,
                Strategy.last_backtested_at >= since,
                Strategy.status == 'ACTIVE'
            ))
        ).scalar() or 0

        # Retired by reason (retired in last 24h, grouped by retired_reason)
        retired_by_reason = session.execute(
            select(Strategy.retired_reason, func.count(Strategy.id))
            .where(and_(
                Strategy.retired_at >= since,
                Strategy.status == 'RETIRED'
            ))
            .group_by(Strategy.retired_reason)
        ).all()

        reason_counts = {r[0]: r[1] for r in retired_by_reason if r[0] is not None}

        # Count robustness failures (all robustness_below_threshold:* reasons)
        robustness_failed = sum(
            count for reason, count in reason_counts.items()
            if reason and reason.startswith('robustness_below_threshold')
        )

        return {
            'tested': retested,
            'passed': passed,
            'failed': reason_counts.get('retest_failed', 0),
            'evicted': reason_counts.get('evicted', 0),
            'score_below_min': reason_counts.get('score_below_min', 0),
            'pool_rejected': reason_counts.get('pool_rejected', 0),
            'robustness_failed': robustness_failed,
            # Legacy: total retired (for backwards compatibility)
            'retired': sum(r[1] for r in retired_by_reason),
        }

    def _get_robustness_stats_24h(self, session, since: datetime) -> Dict[str, Any]:
        """Get robustness check statistics for last 24h."""
        # Query robustness_check events
        events = session.query(StrategyEvent).filter(
            StrategyEvent.timestamp >= since,
            StrategyEvent.stage == 'robustness_check',
        ).all()

        passed = [e for e in events if e.status == 'passed']
        failed = [e for e in events if e.status == 'failed']

        passed_robustness = [
            e.event_data.get('robustness', 0)
            for e in passed
            if e.event_data and 'robustness' in e.event_data
        ]
        failed_robustness = [
            e.event_data.get('robustness', 0)
            for e in failed
            if e.event_data and 'robustness' in e.event_data
        ]

        return {
            'passed': len(passed),
            'failed': len(failed),
            'total': len(events),
            'pass_rate': len(passed) / len(events) if events else 0,
            'passed_avg': sum(passed_robustness) / len(passed_robustness) if passed_robustness else 0,
            'failed_avg': sum(failed_robustness) / len(failed_robustness) if failed_robustness else 0,
        }

    def _get_pool_robustness_stats(self, session) -> Dict[str, Any]:
        """Get robustness stats for current ACTIVE pool."""
        strategies = session.query(Strategy).filter(
            Strategy.status == 'ACTIVE',
            Strategy.robustness_score.isnot(None),
        ).all()

        if not strategies:
            return {'min': 0, 'max': 0, 'avg': 0, 'count': 0}

        scores = [s.robustness_score for s in strategies]
        return {
            'min': min(scores),
            'max': max(scores),
            'avg': sum(scores) / len(scores),
            'count': len(scores),
        }

    def _get_live_rotation_stats(self, session, since: datetime) -> Dict[str, Any]:
        """Get LIVE rotation statistics including diversity."""
        from collections import defaultdict

        # Get rotator config for diversity limits
        rotator_config = self.config.get('rotator', {})
        selection_config = rotator_config.get('selection', {})
        max_per_type = selection_config.get('max_per_type', 3)
        max_per_timeframe = selection_config.get('max_per_timeframe', 3)
        max_per_direction = selection_config.get('max_per_direction', 5)
        min_pool_size = rotator_config.get('min_pool_size', 0)

        # Current LIVE count
        live_count = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.status == 'LIVE')
        ).scalar() or 0

        # ACTIVE count (for pool_ready check)
        active_count = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.status == 'ACTIVE')
        ).scalar() or 0

        # Pool ready check
        pool_ready = active_count >= min_pool_size if min_pool_size > 0 else True

        # Deployed in last 24h
        deployed_24h = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'deployment',
                StrategyEvent.event_type == 'succeeded',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Retired from LIVE in last 24h
        retired_24h = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'live',
                StrategyEvent.event_type == 'retired',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Get LIVE strategies for diversity and avg calculations
        live_strategies = session.execute(
            select(Strategy)
            .where(Strategy.status == 'LIVE')
        ).scalars().all()

        # Average age of LIVE strategies (days)
        avg_age = None
        if live_strategies:
            ages = []
            for s in live_strategies:
                if s.live_since:
                    age_seconds = (datetime.now(UTC) - s.live_since.replace(tzinfo=UTC)).total_seconds()
                    ages.append(age_seconds / 86400)
            if ages:
                avg_age = sum(ages) / len(ages)

        # Average score of LIVE strategies
        avg_score = None
        if live_strategies:
            scores = [s.score_backtest for s in live_strategies if s.score_backtest is not None]
            if scores:
                avg_score = sum(scores) / len(scores)

        # Diversity stats for LIVE strategies
        type_counts = defaultdict(int)
        tf_counts = defaultdict(int)
        dir_counts = defaultdict(int)

        for s in live_strategies:
            if s.strategy_type:
                type_counts[s.strategy_type] += 1
            if s.optimal_timeframe:
                tf_counts[s.optimal_timeframe] += 1
            # Detect direction from code
            direction = self._detect_direction(s.code) if s.code else 'LONG'
            dir_counts[direction] += 1

        return {
            # Rotation stats
            'live': live_count,
            'limit': self.limit_live,
            'slots_free': max(0, self.limit_live - live_count),
            'active_count': active_count,
            'min_pool_size': min_pool_size,
            'pool_ready': pool_ready,
            'deployed_24h': deployed_24h,
            'retired_24h': retired_24h,
            # LIVE stats
            'avg_age_days': avg_age,
            'avg_score': avg_score,
            # Diversity stats
            'diversity': {
                'types': {'unique': len(type_counts), 'max': max_per_type},
                'timeframes': {'unique': len(tf_counts), 'max': max_per_timeframe},
                'directions': {'unique': len(dir_counts), 'max': max_per_direction},
            },
            'type_distribution': dict(type_counts),
            'timeframe_distribution': dict(tf_counts),
            'direction_distribution': dict(dir_counts),
        }

    def _detect_direction(self, code: str) -> str:
        """Detect trading direction from strategy code."""
        if not code:
            return "LONG"

        code_lower = code.lower()

        # Check for explicit BIDI/BIDIR (with and without spaces)
        has_bidi = (
            "direction='bidi'" in code_lower or
            'direction="bidi"' in code_lower or
            "direction = 'bidi'" in code_lower or
            'direction = "bidi"' in code_lower
        )
        if has_bidi:
            return "BIDIR"

        # Check for long/short (with and without spaces around =)
        has_long = (
            "direction='long'" in code_lower or
            'direction="long"' in code_lower or
            "direction = 'long'" in code_lower or
            'direction = "long"' in code_lower
        )
        has_short = (
            "direction='short'" in code_lower or
            'direction="short"' in code_lower or
            "direction = 'short'" in code_lower or
            'direction = "short"' in code_lower
        )

        if has_long and has_short:
            return "BIDIR"
        elif has_short:
            return "SHORT"
        return "LONG"

    def _get_subaccount_stats(self, session) -> List[Dict[str, Any]]:
        """
        Get statistics for each active subaccount.

        Returns list of dicts with subaccount metrics for logging.
        Optionally includes true P&L from Hyperliquid if statistics_service is available.
        """
        # Query subaccounts with their assigned strategies
        subaccounts = (
            session.query(Subaccount, Strategy)
            .outerjoin(Strategy, Subaccount.strategy_id == Strategy.id)
            .filter(Subaccount.status == 'ACTIVE')
            .order_by(Subaccount.id)
            .all()
        )

        # Pre-fetch true P&L stats from Hyperliquid if statistics_service available
        true_pnl_stats = {}
        if self.statistics_service:
            try:
                subaccount_ids = [sub.id for sub, _ in subaccounts]
                true_pnl_stats = self.statistics_service.get_all_subaccounts_stats(subaccount_ids)
            except Exception as e:
                logger.warning(f"Failed to fetch true P&L stats from Hyperliquid: {e}")

        result = []
        now = datetime.now(UTC)
        for sub, strategy in subaccounts:
            # Calculate rpnl percentage (DB-based)
            allocated = sub.allocated_capital or 0
            total_pnl = sub.total_pnl or 0
            rpnl_pct = (total_pnl / allocated * 100) if allocated > 0 else 0

            # Calculate strategy uptime from live_since
            uptime_days = None
            if strategy and strategy.live_since:
                live_since = strategy.live_since
                if live_since.tzinfo is None:
                    live_since = live_since.replace(tzinfo=UTC)
                uptime_days = (now - live_since).total_seconds() / 86400

            # Get strategy details
            timeframe = strategy.timeframe if strategy else None
            direction = self._detect_direction(strategy.code) if strategy and strategy.code else None
            coins = strategy.trading_coins if strategy else None
            coins_count = len(coins) if coins else 0

            stats = {
                'id': sub.id,
                'balance': sub.current_balance or 0,
                'strategy_name': strategy.name if strategy else None,
                'timeframe': timeframe,
                'direction': direction,
                'coins_count': coins_count,
                'uptime_days': uptime_days,
                'rpnl': total_pnl,
                'rpnl_pct': rpnl_pct,
                'upnl': sub.unrealized_pnl or 0,
                'positions': sub.open_positions_count or 0,
                'dd_pct': (sub.current_drawdown or 0) * 100,
                'wr_pct': (sub.win_rate or 0) * 100,
            }

            # Add true P&L from Hyperliquid if available
            # These are immune to manual deposits/withdrawals
            if sub.id in true_pnl_stats:
                hl_stats = true_pnl_stats[sub.id]
                stats['hl_balance'] = hl_stats.get('current_balance', 0)
                stats['hl_net_deposits'] = hl_stats.get('net_deposits', 0)
                stats['hl_true_pnl'] = hl_stats.get('true_pnl', 0)
                stats['hl_true_pnl_pct'] = hl_stats.get('true_pnl_pct', 0)

            result.append(stats)

        return result

    def _get_main_account_balance(self) -> float:
        """
        Get main account balance from Hyperliquid.

        Returns:
            Account equity in USD, or 0.0 if unavailable
        """
        if not self._hl_master_address:
            return 0.0

        try:
            state = self._hl_info.user_state(self._hl_master_address)
            if state and 'marginSummary' in state:
                return float(state['marginSummary'].get('accountValue', 0))
            return 0.0
        except Exception as e:
            logger.warning(f"Failed to get main account balance: {e}")
            return 0.0

    def _get_scheduler_stats(self, session) -> Dict[str, Any]:
        """
        Get scheduler task execution statistics.

        Returns dict with task stats including last run, status, and next scheduled run.
        Tasks are ordered according to PIPELINE_AUX.md schedule.
        """
        # Get configs
        scheduler_config = self.config.get('scheduler', {})
        tasks_config = scheduler_config.get('tasks', {})
        data_scheduler_config = self.config.get('data_scheduler', {})
        regime_config = self.config.get('regime', {})

        # Build ordered list of ALL scheduler tasks (per PIPELINE_AUX.md)
        # Order: fixed-schedule (01:xx), data-scheduler (02:xx), interval-based
        task_list = []

        # 1. Fixed-schedule tasks (01:00-01:50 UTC)
        restart_cfg = tasks_config.get('daily_restart_services', {})
        if restart_cfg.get('enabled', False):
            task_list.append({
                'name': 'daily_restart_services',
                'interval_hours': 24,
                'run_hour': restart_cfg.get('restart_hour', 1),
                'run_minute': restart_cfg.get('restart_minute', 0),
            })

        if regime_config.get('enabled', False):
            task_list.append({
                'name': 'refresh_market_regimes',
                'interval_hours': 24,
                'run_hour': 1,
                'run_minute': 0,
            })

        renew_cfg = tasks_config.get('renew_agent_wallets', {})
        if renew_cfg.get('enabled', False):
            task_list.append({
                'name': 'renew_agent_wallets',
                'interval_hours': 24,
                'run_hour': renew_cfg.get('run_hour', 1),
                'run_minute': renew_cfg.get('run_minute', 10),
            })

        funds_cfg = tasks_config.get('check_subaccount_funds', {})
        if funds_cfg.get('enabled', False):
            task_list.append({
                'name': 'check_subaccount_funds',
                'interval_hours': 24,
                'run_hour': funds_cfg.get('run_hour', 1),
                'run_minute': funds_cfg.get('run_minute', 20),
            })

        tmp_cfg = tasks_config.get('cleanup_tmp_dir', {})
        if tmp_cfg.get('enabled', False):
            task_list.append({
                'name': 'cleanup_tmp_dir',
                'interval_hours': 24,
                'run_hour': tmp_cfg.get('run_hour', 1),
                'run_minute': tmp_cfg.get('run_minute', 30),
            })

        events_cfg = tasks_config.get('cleanup_old_events', {})
        if events_cfg.get('enabled', False):
            task_list.append({
                'name': 'cleanup_old_events',
                'interval_hours': 24,
                'run_hour': events_cfg.get('run_hour', 1),
                'run_minute': events_cfg.get('run_minute', 40),
            })

        stale_cfg = tasks_config.get('cleanup_stale_strategies', {})
        if stale_cfg.get('enabled', False):
            task_list.append({
                'name': 'cleanup_stale_strategies',
                'interval_hours': 24,
                'run_hour': stale_cfg.get('run_hour', 1),
                'run_minute': stale_cfg.get('run_minute', 50),
            })

        failed_cfg = tasks_config.get('cleanup_old_failed', {})
        if failed_cfg.get('enabled', False):
            task_list.append({
                'name': 'cleanup_old_failed',
                'interval_hours': 24,
                'run_hour': failed_cfg.get('run_hour', 2),
                'run_minute': failed_cfg.get('run_minute', 0),
            })

        retired_cfg = tasks_config.get('cleanup_old_retired', {})
        if retired_cfg.get('enabled', False):
            task_list.append({
                'name': 'cleanup_old_retired',
                'interval_hours': 24,
                'run_hour': retired_cfg.get('run_hour', 2),
                'run_minute': retired_cfg.get('run_minute', 10),
            })

        # 2. Data scheduler tasks (separate schedules)
        if data_scheduler_config.get('enabled', False):
            task_list.append({
                'name': 'update_pairs',
                'interval_hours': 12,
                'run_hours': data_scheduler_config.get('update_pairs_hours', [1, 13]),
                'run_minute': data_scheduler_config.get('update_pairs_minute', 45),
            })
            task_list.append({
                'name': 'download_data',
                'interval_hours': 12,
                'run_hours': data_scheduler_config.get('download_data_hours', [2, 14]),
                'run_minute': data_scheduler_config.get('download_data_minute', 0),
            })

        # 3. Interval-based tasks (always enabled - core tasks)
        zombie_cfg = tasks_config.get('cleanup_zombie_processes', {})
        if zombie_cfg.get('enabled', False):
            task_list.append({
                'name': 'cleanup_zombie_processes',
                'interval_hours': zombie_cfg.get('interval_hours', 3),
            })

        # Core tasks (always enabled, not in config)
        task_list.append({
            'name': 'cleanup_stale_processing',
            'interval_hours': 0.5,
        })
        task_list.append({
            'name': 'refresh_data_cache',
            'interval_hours': 4,
        })

        # Query last execution for each task
        task_stats = {}
        total_ok = 0
        total_tasks = len(task_list)
        now = datetime.now(UTC)

        for task_info in task_list:
            task_name = task_info['name']

            # Get most recent execution
            last_exec = session.execute(
                select(ScheduledTaskExecution)
                .where(ScheduledTaskExecution.task_name == task_name)
                .order_by(ScheduledTaskExecution.started_at.desc())
                .limit(1)
            ).scalar()

            if last_exec:
                last_run = last_exec.started_at
                status = last_exec.status
                duration = last_exec.duration_seconds
                metadata = last_exec.task_metadata or {}

                # Calculate next run based on task type
                next_run = self._calculate_next_run(task_info, last_run, now)

                # Count OK statuses
                if status == 'SUCCESS':
                    total_ok += 1

                task_stats[task_name] = {
                    'last_run': last_run,
                    'status': status,
                    'duration_seconds': duration,
                    'metadata': metadata,
                    'next_run': next_run,
                    'interval_hours': task_info.get('interval_hours', 24),
                }
            else:
                # No execution found - calculate first scheduled run
                next_run = self._calculate_next_run(task_info, None, now)
                task_stats[task_name] = {
                    'last_run': None,
                    'status': 'NEVER_RUN',
                    'duration_seconds': None,
                    'metadata': {},
                    'next_run': next_run,
                    'interval_hours': task_info.get('interval_hours', 24),
                }

        return {
            'total_ok': total_ok,
            'total_tasks': total_tasks,
            'tasks': task_stats,
        }

    def _calculate_next_run(
        self,
        task_info: Dict[str, Any],
        last_run: Optional[datetime],
        now: datetime
    ) -> Optional[datetime]:
        """
        Calculate next scheduled run for a task.

        For fixed-schedule tasks: next occurrence of run_hour:run_minute
        For interval tasks: last_run + interval_hours
        For data scheduler tasks: next occurrence in update_hours
        """
        task_name = task_info['name']

        # Check for fixed schedule (run_hour or restart_hour)
        run_hour = task_info.get('run_hour') or task_info.get('restart_hour')
        run_minute = task_info.get('run_minute') or task_info.get('restart_minute', 0)

        if run_hour is not None:
            # Fixed schedule task - find next occurrence
            next_run = now.replace(hour=run_hour, minute=run_minute, second=0, microsecond=0)
            if next_run <= now:
                # Already passed today, schedule for tomorrow
                next_run += timedelta(days=1)
            return next_run

        # Check for multi-hour schedule tasks (data scheduler)
        run_hours = task_info.get('run_hours')
        if run_hours:
            run_minute_multi = task_info.get('run_minute', 0)
            # Find next hour in run_hours
            for hour in sorted(run_hours):
                candidate = now.replace(hour=hour, minute=run_minute_multi, second=0, microsecond=0)
                if candidate > now:
                    return candidate
            # All hours passed today, use first hour tomorrow
            return now.replace(hour=run_hours[0], minute=run_minute_multi, second=0, microsecond=0) + timedelta(days=1)

        # Interval-based task
        interval_hours = task_info.get('interval_hours', 24)
        if last_run:
            return last_run + timedelta(hours=interval_hours)

        return None

    def _get_status_and_issue(
        self,
        queue_depths: Dict[str, int],
        backpressure: Dict[str, Any],
        throughput: Dict[str, int],
    ) -> Tuple[str, Optional[str]]:
        """Determine overall status and issue description."""
        active = queue_depths.get('ACTIVE', 0)
        live = queue_depths.get('LIVE', 0)
        generated = queue_depths.get('GENERATED', 0)
        validated = queue_depths.get('VALIDATED', 0)
        bt_waiting = backpressure.get('bt_waiting', 0)
        bt_processing = backpressure.get('bt_processing', 0)

        # Pipeline activity indicators
        pipeline_has_work = generated > 0 or validated > 0 or bt_processing > 0
        pipeline_throughput = sum(throughput.values())

        # Check for real issues (not just empty pool)
        issues = []

        # Backtest stalled (waiting but not processing)
        if bt_waiting > 0 and bt_processing == 0 and throughput.get('bt', 0) == 0:
            issues.append(f"Backtest stalled ({bt_waiting} waiting)")

        # Generator queue full
        if backpressure.get('gen_full', False):
            issues.append("Generator queue full")

        # Determine status
        if issues:
            # Real problems (backpressure or stall)
            return 'BACKPRESSURE', issues[0]
        elif active == 0 and live == 0:
            # Pool empty but check if pipeline is working
            if pipeline_has_work or pipeline_throughput > 0:
                return 'WARMING_UP', None
            else:
                return 'IDLE', None
        else:
            return 'HEALTHY', None

    def _save_snapshot(
        self,
        session,
        queue_depths: Dict[str, int],
        throughput: Dict[str, int],
        funnel: Dict[str, Any],
        pool_quality: Dict[str, Any],
        status: str,
    ) -> None:
        """Save metrics snapshot to database."""
        # Calculate utilization
        gen_util = queue_depths.get('GENERATED', 0) / self.limit_generated if self.limit_generated > 0 else 0
        val_util = queue_depths.get('VALIDATED', 0) / self.limit_validated if self.limit_validated > 0 else 0
        active_util = queue_depths.get('ACTIVE', 0) / self.limit_active if self.limit_active > 0 else 0

        # Calculate success rates
        val_rate = funnel['validated_pct'] / 100 if funnel['validated_pct'] else None
        bt_rate = funnel['pool_pct'] / 100 if funnel['pool_pct'] else None

        snapshot = PipelineMetricsSnapshot(
            timestamp=datetime.now(UTC),
            queue_generated=queue_depths.get('GENERATED', 0),
            queue_validated=queue_depths.get('VALIDATED', 0),
            queue_active=queue_depths.get('ACTIVE', 0),
            queue_live=queue_depths.get('LIVE', 0),
            queue_retired=queue_depths.get('RETIRED', 0),
            queue_failed=queue_depths.get('FAILED', 0),
            throughput_generation=throughput.get('gen', 0) * 60,  # per hour
            throughput_validation=throughput.get('val', 0) * 60,
            throughput_backtesting=throughput.get('bt', 0) * 60,
            utilization_generated=gen_util,
            utilization_validated=val_util,
            utilization_active=active_util,
            success_rate_validation=val_rate,
            success_rate_backtesting=bt_rate,
            bottleneck_stage=None,
            overall_status=status.lower(),
            avg_sharpe=pool_quality.get('sharpe_avg'),
            avg_win_rate=pool_quality.get('winrate_avg'),
            avg_expectancy=pool_quality.get('expectancy_avg'),
            pattern_count=0,
            ai_count=0,
        )

        session.add(snapshot)
        session.commit()

    def _log_metrics(
        self,
        status: str,
        issue: Optional[str],
        queue_depths: Dict[str, int],
        generator_stats: Dict[str, Any],
        ai_calls_today: Dict[str, Any],
        unused_patterns: Dict[str, Any],
        funnel: Dict[str, Any],
        validation_by_source: Dict[str, Dict[str, int]],
        timing: Dict[str, Optional[float]],
        failures: Dict[str, int],
        backpressure: Dict[str, Any],
        is_stats: Dict[str, Any],
        oos_stats: Dict[str, Any],
        score_stats: Dict[str, Any],
        pool_stats: Dict[str, Any],
        pool_quality: Dict[str, Any],
        pool_by_source: Dict[str, int],
        pool_avg_score_by_source: Dict[str, Optional[float]],
        pool_added_by_source: Dict[str, int],
        retest_stats: Dict[str, Any],
        robustness_stats: Dict[str, Any],
        pool_robustness: Dict[str, Any],
        live_stats: Dict[str, Any],
        combo_stats: Dict[str, Any],
        scheduler_stats: Dict[str, Any],
        subaccount_stats: List[Dict[str, Any]],
    ) -> None:
        """
        Log metrics following the 10-step pipeline structure.

        Each section shows: queue state -> 24h throughput -> timing -> failures
        """

        # Helper functions
        def fmt_pct(val: Optional[int]) -> str:
            return f"{val}%" if val is not None else "--"

        def fmt_time(ms: Optional[float]) -> str:
            if ms is None:
                return "--"
            if ms >= 60000:
                return f"{ms/60000:.1f}min"
            if ms >= 1000:
                return f"{ms/1000:.1f}s"
            return f"{int(ms)}ms"

        def fmt_float(val: Optional[float], decimals: int = 1) -> str:
            if val is None:
                return "--"
            return f"{val:.{decimals}f}"

        def fmt_pct_float(val: Optional[float]) -> str:
            if val is None:
                return "--"
            return f"{val*100:.0f}%"

        def fmt_pct_exp(val: Optional[float]) -> str:
            """Format expectancy as percentage (0.0020 -> 0.20%)"""
            if val is None:
                return "--"

        # Source abbreviation mapping (generation_mode -> abbrev)
        SOURCE_ABBREV = {
            'pattern': 'pat',
            'pattern_gen': 'pgn',
            'pattern_gen_genetic': 'pgg',
            'unger': 'ung',
            'unger_genetic': 'ugg',
            'pandas_ta': 'pta',
            'ai_free': 'aif',
            'ai_assigned': 'aia',
        }

        # Build filtered source list (order matters for display)
        SOURCE_ORDER = ['pattern', 'pattern_gen', 'pattern_gen_genetic', 'unger', 'unger_genetic', 'pandas_ta', 'ai_free', 'ai_assigned']
        enabled_sources = self.enabled_sources

        def fmt_sources(values: Dict[str, Any], formatter=str) -> str:
            """Format source values, filtering out disabled sources."""
            parts = []
            for src in SOURCE_ORDER:
                if src in enabled_sources:
                    abbrev = SOURCE_ABBREV[src]
                    val = values.get(src, 0)
                    parts.append(f"{abbrev}={formatter(val)}")
            return ', '.join(parts) if parts else '--'

        # === STATUS ===
        if issue:
            logger.info(f'=== PIPELINE STATUS: {status} ({issue}) ===')
        else:
            logger.info(f'=== PIPELINE STATUS: {status} ===')

        # =====================================================================
        # [1/10 GENERATOR]
        # =====================================================================
        gen_total = generator_stats['total']
        gen_by_source = generator_stats['by_source']
        gen_by_type = generator_stats['by_type']
        gen_by_dir = generator_stats['by_direction']
        gen_by_tf = generator_stats['by_timeframe']
        gen_timing = generator_stats['timing_by_source']

        logger.info(f'[1/10 GENERATOR] 24h: {gen_total} strategies | {fmt_sources(gen_by_source)}')

        type_parts = [f'{t}={c}' for t, c in sorted(gen_by_type.items()) if c > 0]
        type_str = ', '.join(type_parts) if type_parts else '--'
        logger.info(f'[1/10 GENERATOR] types: {type_str}')

        dir_long = gen_by_dir.get('LONG', 0)
        dir_short = gen_by_dir.get('SHORT', 0)
        dir_bidir = gen_by_dir.get('BIDIR', 0)
        logger.info(f'[1/10 GENERATOR] direction: LONG={dir_long}, SHORT={dir_short}, BIDIR={dir_bidir}')

        tf_order = ['5m', '15m', '30m', '1h', '2h']
        tf_parts = [f'{tf}={gen_by_tf.get(tf, 0)}' for tf in tf_order if gen_by_tf.get(tf, 0) > 0]
        for tf, count in gen_by_tf.items():
            if tf not in tf_order and count > 0:
                tf_parts.append(f'{tf}={count}')
        tf_str = ', '.join(tf_parts) if tf_parts else '--'
        logger.info(f'[1/10 GENERATOR] timeframe: {tf_str}')

        # Only show patterns line if pattern source is enabled
        if 'pattern' in enabled_sources:
            pat_unique = unused_patterns.get('unique_used', 0)
            pat_total = unused_patterns.get('total_available')
            pat_remaining = unused_patterns.get('remaining')
            if pat_total is not None:
                logger.info(f'[1/10 GENERATOR] patterns: {pat_unique} used | {pat_remaining} remaining ({pat_total} tier1 available)')
            else:
                logger.info(f'[1/10 GENERATOR] patterns: {pat_unique} used')

        gen_failures = generator_stats.get('gen_failures', 0)
        timing_str = fmt_sources(gen_timing, formatter=fmt_time)
        logger.info(f'[1/10 GENERATOR] timing: {timing_str} | failures: {gen_failures}')

        # =====================================================================
        # [2/10 VALIDATOR]
        # =====================================================================
        g = queue_depths.get('GENERATED', 0)
        val = funnel["validated"]
        val_failed = funnel["validation_failed"]
        # Use gen_total from generator_stats for consistency (same source as [1/10 GENERATOR])
        gen = gen_total

        logger.info(f'[2/10 VALIDATOR] queue: {g} waiting')
        val_failed_str = f" | failed: {val_failed}" if val_failed > 0 else ""
        # Recalculate validated_pct using consistent denominator
        validated_pct = int(round(100 * val / gen)) if gen > 0 else None
        logger.info(f'[2/10 VALIDATOR] 24h: {val}/{gen} passed ({fmt_pct(validated_pct)}){val_failed_str}')

        # Validation breakdown by source (passed and failed)
        val_passed = validation_by_source.get('passed', {})
        val_failed_src = validation_by_source.get('failed', {})
        logger.info(f'[2/10 VALIDATOR] passed: {fmt_sources(val_passed)}')
        logger.info(f'[2/10 VALIDATOR] failed: {fmt_sources(val_failed_src)}')

        logger.info(f'[2/10 VALIDATOR] timing: {fmt_time(timing.get("validation"))} avg')

        # =====================================================================
        # [3/10 PARAMETRIC]
        # =====================================================================
        bt_waiting = backpressure["bt_waiting"]
        bt_processing = backpressure["bt_processing"]

        logger.info(f'[3/10 PARAMETRIC] queue: {bt_waiting} waiting, {bt_processing} running')

        if combo_stats:
            total_combos = combo_stats.get('total_combos', 0)
            passed_combos = combo_stats.get('passed_combos', 0)
            failed_combos = combo_stats.get('failed_combos', 0)
            total_bases = combo_stats.get('total_bases', 0)
            bases_passed = combo_stats.get('bases_with_passed', 0)
            bases_failed = combo_stats.get('bases_with_failed', 0)

            logger.info(f'[3/10 PARAMETRIC] 24h: {total_bases} bases, {total_combos} combos tested')
            logger.info(f'[3/10 PARAMETRIC] bases with passed combos: {bases_passed}')
            logger.info(f'[3/10 PARAMETRIC] bases with failed combos: {bases_failed}')

            # Failed combos stats
            if total_combos > 0:
                failed_pct = 100 * failed_combos // total_combos
                logger.info(f'[3/10 PARAMETRIC] combos failed: {failed_combos} ({failed_pct}% of {total_combos})')

                fa = combo_stats.get('failed_avg', {})
                if failed_combos > 0:
                    logger.info(
                        f"[3/10 PARAMETRIC] combos failed avg: "
                        f"sharpe={fa.get('sharpe', 0):.2f}, "
                        f"wr={fa.get('wr', 0)*100:.0f}%, "
                        f"exp={fa.get('exp', 0)*100:.2f}%, "
                        f"trades={fa.get('trades', 0):.0f}"
                    )

                # Fail reasons (CUMULATIVE - count and % of failed combos that violated each threshold)
                fr = combo_stats.get('fail_reasons', {})
                if failed_combos > 0:
                    def fr_fmt(n: int) -> str:
                        pct = 100 * n // failed_combos if failed_combos > 0 else 0
                        return f"{n} ({pct}%)"
                    logger.info(
                        f"[3/10 PARAMETRIC] fail reasons: "
                        f"sharpe: {fr_fmt(fr.get('sharpe', 0))}, "
                        f"trades: {fr_fmt(fr.get('trades', 0))}, "
                        f"wr: {fr_fmt(fr.get('wr', 0))}, "
                        f"exp: {fr_fmt(fr.get('exp', 0))}, "
                        f"dd: {fr_fmt(fr.get('dd', 0))}"
                    )

                # Passed combos stats
                passed_pct = 100 * passed_combos // total_combos
                logger.info(f'[3/10 PARAMETRIC] combos passed: {passed_combos} ({passed_pct}% of {total_combos})')

                pa = combo_stats.get('passed_avg', {})
                if passed_combos > 0:
                    logger.info(
                        f"[3/10 PARAMETRIC] combos passed avg: "
                        f"sharpe={pa.get('sharpe', 0):.2f}, "
                        f"wr={pa.get('wr', 0)*100:.0f}%, "
                        f"exp={pa.get('exp', 0)*100:.2f}%, "
                        f"trades={pa.get('trades', 0):.0f}"
                    )

            # Timing per base with range
            total_bases = combo_stats.get('total_bases', 0)
            avg_time = fmt_time(combo_stats.get('avg_duration_ms'))
            min_time = fmt_time(combo_stats.get('min_duration_ms'))
            max_time = fmt_time(combo_stats.get('max_duration_ms'))
            logger.info(
                f'[3/10 PARAMETRIC] timing {avg_time}/base '
                f'(min={min_time}, max={max_time}), {total_bases} bases'
            )
        else:
            # No combo_stats available yet
            combinations = funnel["combinations_tested"]
            logger.info(f'[3/10 PARAMETRIC] 24h: -- bases, {combinations} combos (no stats yet)')

        # =====================================================================
        # [4/10 IS_BACKTEST]
        # =====================================================================
        is_count = is_stats.get('count', 0)
        is_passed = is_stats.get('passed', 0)
        is_failed = is_stats.get('failed', 0)

        is_passed_pct = int(100 * is_passed // is_count) if is_count > 0 else 0
        is_failed_pct = int(100 * is_failed // is_count) if is_count > 0 else 0

        logger.info(f'[4/10 IS_BACKTEST] 24h: {is_count} strategies tested')
        logger.info(f'[4/10 IS_BACKTEST] passed: {is_passed} ({is_passed_pct}%)')

        # Passed avg
        is_pa = is_stats.get('passed_avg', {})
        is_pa_sharpe = fmt_float(is_pa.get('sharpe'))
        is_pa_wr = fmt_pct_float(is_pa.get('wr'))
        is_pa_exp = fmt_pct_exp(is_pa.get('exp'))
        is_pa_trades = fmt_float(is_pa.get('trades'), 0) if is_pa.get('trades') else "--"
        logger.info(f'[4/10 IS_BACKTEST] passed avg: sharpe={is_pa_sharpe}, wr={is_pa_wr}, exp={is_pa_exp}, trades={is_pa_trades}')

        logger.info(f'[4/10 IS_BACKTEST] failed: {is_failed} ({is_failed_pct}%)')

        # Failed avg
        is_fa = is_stats.get('failed_avg', {})
        is_fa_sharpe = fmt_float(is_fa.get('sharpe'))
        is_fa_wr = fmt_pct_float(is_fa.get('wr'))
        is_fa_exp = fmt_pct_exp(is_fa.get('exp'))
        is_fa_trades = fmt_float(is_fa.get('trades'), 0) if is_fa.get('trades') else "--"
        logger.info(f'[4/10 IS_BACKTEST] failed avg: sharpe={is_fa_sharpe}, wr={is_fa_wr}, exp={is_fa_exp}, trades={is_fa_trades}')

        # Fail reasons (count and % of failed strategies that violated each threshold)
        is_fr = is_stats.get('fail_reasons', {})
        if is_failed > 0:
            def is_fr_fmt(n: int) -> str:
                pct = 100 * n // is_failed if is_failed > 0 else 0
                return f"{n} ({pct}%)"
            logger.info(
                f"[4/10 IS_BACKTEST] fail reasons: "
                f"sharpe: {is_fr_fmt(is_fr.get('sharpe', 0))}, "
                f"wr: {is_fr_fmt(is_fr.get('wr', 0))}, "
                f"exp: {is_fr_fmt(is_fr.get('exp', 0))}, "
                f"dd: {is_fr_fmt(is_fr.get('dd', 0))}, "
                f"trades: {is_fr_fmt(is_fr.get('trades', 0))}"
            )

        # Timing (from failed strategies only - passed go to OOS without separate event)
        is_timing = fmt_time(is_stats.get('avg_duration_ms'))
        logger.info(f'[4/10 IS_BACKTEST] timing: {is_timing} avg')

        # =====================================================================
        # [5/10 OOS_BACKTEST]
        # =====================================================================
        oos_count = oos_stats.get('count', 0)
        oos_passed = oos_stats.get('passed', 0)
        oos_failed = oos_stats.get('failed', 0)

        oos_passed_pct = int(100 * oos_passed // oos_count) if oos_count > 0 else 0
        oos_failed_pct = int(100 * oos_failed // oos_count) if oos_count > 0 else 0

        logger.info(f'[5/10 OOS_BACKTEST] 24h: {oos_count} strategies tested')
        logger.info(f'[5/10 OOS_BACKTEST] passed: {oos_passed} ({oos_passed_pct}%)')

        # Passed avg
        oos_pa = oos_stats.get('passed_avg', {})
        oos_pa_sharpe = fmt_float(oos_pa.get('sharpe'))
        oos_pa_wr = fmt_pct_float(oos_pa.get('wr'))
        oos_pa_exp = fmt_pct_exp(oos_pa.get('exp'))
        oos_pa_trades = fmt_float(oos_pa.get('trades'), 0) if oos_pa.get('trades') else "--"
        logger.info(f'[5/10 OOS_BACKTEST] passed avg: sharpe={oos_pa_sharpe}, wr={oos_pa_wr}, exp={oos_pa_exp}, trades={oos_pa_trades}')

        logger.info(f'[5/10 OOS_BACKTEST] failed: {oos_failed} ({oos_failed_pct}%)')

        # Failed avg
        oos_fa = oos_stats.get('failed_avg', {})
        oos_fa_sharpe = fmt_float(oos_fa.get('sharpe'))
        oos_fa_wr = fmt_pct_float(oos_fa.get('wr'))
        oos_fa_exp = fmt_pct_exp(oos_fa.get('exp'))
        oos_fa_trades = fmt_float(oos_fa.get('trades'), 0) if oos_fa.get('trades') else "--"
        logger.info(f'[5/10 OOS_BACKTEST] failed avg: sharpe={oos_fa_sharpe}, wr={oos_fa_wr}, exp={oos_fa_exp}, trades={oos_fa_trades}')

        # Fail reasons (count and % of failed strategies that violated each threshold)
        oos_fr = oos_stats.get('fail_reasons', {})
        if oos_failed > 0:
            def oos_fr_fmt(n: int) -> str:
                pct = 100 * n // oos_failed if oos_failed > 0 else 0
                return f"{n} ({pct}%)"
            logger.info(
                f"[5/10 OOS_BACKTEST] fail reasons: "
                f"sharpe: {oos_fr_fmt(oos_fr.get('sharpe', 0))}, "
                f"wr: {oos_fr_fmt(oos_fr.get('wr', 0))}, "
                f"exp: {oos_fr_fmt(oos_fr.get('exp', 0))}, "
                f"dd: {oos_fr_fmt(oos_fr.get('dd', 0))}, "
                f"trades: {oos_fr_fmt(oos_fr.get('trades', 0))}, "
                f"degradation: {oos_fr_fmt(oos_fr.get('degradation', 0))}"
            )

        # Degradation summary (for passed strategies)
        avg_degrad = oos_stats.get('avg_degradation')
        oos_better = oos_stats.get('oos_better', 0)
        oos_worse = oos_stats.get('oos_worse', 0)
        if oos_passed > 0 and avg_degrad is not None:
            # performance_change = -degradation (positive = OOS better than IS)
            perf_change = -avg_degrad * 100
            perf_str = f"{perf_change:+.0f}%"  # +100% or -50%
            logger.info(f'[5/10 OOS_BACKTEST] passed performance_change: {perf_str} | oos_better={oos_better}, oos_worse={oos_worse}')

        # Timing (from failed strategies only - passed continue to scoring)
        oos_timing = fmt_time(oos_stats.get('avg_duration_ms'))
        logger.info(f'[5/10 OOS_BACKTEST] timing: {oos_timing} avg')

        # =====================================================================
        # [6/10 SCORE]
        # =====================================================================
        param_scored = funnel["parametric_scored"]  # Strategies that passed OOS
        score_ok = funnel["score_ok"]
        score_rejected = failures["score_reject"]
        min_score = fmt_float(score_stats.get('min_score'))
        max_score = fmt_float(score_stats.get('max_score'))
        avg_score = fmt_float(score_stats.get('avg_score'))

        logger.info(f'[6/10 SCORE] 24h: {score_ok}/{param_scored} passed min_score={self.pool_min_score} ({fmt_pct(funnel["score_ok_pct"])})')
        logger.info(f'[6/10 SCORE] range: {min_score} to {max_score} (avg {avg_score}) | rejected: {score_rejected}')

        # =====================================================================
        # [7/10 SHUFFLE]
        # =====================================================================
        shuf = funnel["shuffle_ok"]
        shuffle_fail = failures["shuffle_fail"]
        shuffle_cached = failures.get("shuffle_cached", 0)

        logger.info(f'[7/10 SHUFFLE] 24h: {shuf}/{score_ok} passed ({fmt_pct(funnel["shuffle_ok_pct"])})')
        logger.info(f'[7/10 SHUFFLE] timing: {fmt_time(timing.get("shuffle"))} | bias_failures: {shuffle_fail} | cached: {shuffle_cached}')

        # =====================================================================
        # [8/10 WFA]
        # =====================================================================
        mw = funnel["mw_ok"]
        mw_failed = funnel["mw_failed"]
        mw_started = funnel["mw_started"]
        mw_in_progress = max(0, mw_started - mw - mw_failed)

        mw_in_progress_str = f" | in_progress: {mw_in_progress}" if mw_in_progress > 0 else ""
        logger.info(f'[8/10 WFA] 24h: {mw}/{shuf} passed 4-window ({fmt_pct(funnel["mw_ok_pct"])}){mw_in_progress_str}')
        logger.info(f'[8/10 WFA] timing: {fmt_time(timing.get("multiwindow"))} | failed: {mw_failed} (params not stable across time windows)')

        # =====================================================================
        # [8.5/10 ROBUSTNESS] - Final gate before pool entry
        # =====================================================================
        robustness_config = self.config.get('backtesting', {}).get('robustness', {})
        min_robustness = robustness_config.get('min_threshold', 0.80)

        if robustness_stats['total'] > 0:
            logger.info(
                f"[8.5/10 ROBUSTNESS] 24h: {robustness_stats['passed']}/{robustness_stats['total']} "
                f"passed ({fmt_pct(int(robustness_stats['pass_rate'] * 100))})"
            )
            logger.info(
                f"[8.5/10 ROBUSTNESS] passed_avg: {robustness_stats['passed_avg']:.2f} | "
                f"failed_avg: {robustness_stats['failed_avg']:.2f} | threshold: {min_robustness}"
            )

        if pool_robustness['count'] > 0:
            logger.info(
                f"[8.5/10 ROBUSTNESS] pool: {pool_robustness['min']:.2f} to {pool_robustness['max']:.2f} "
                f"(avg {pool_robustness['avg']:.2f})"
            )

        # =====================================================================
        # [9/10 POOL]
        # =====================================================================
        pool_size = pool_stats["size"]
        pool_limit = pool_stats["limit"]
        pool_entered = funnel["pool"]

        logger.info(f'[9/10 POOL] size: {pool_size}/{pool_limit} | 24h_added: {pool_entered}, 24h_retired: {retest_stats["retired"]}')
        logger.info(
            f'[9/10 POOL] 24h_retired: score<min={retest_stats["score_below_min"]}, '
            f'wfa_failed={retest_stats["pool_rejected"]}, robustness={retest_stats["robustness_failed"]}, '
            f'retest={retest_stats["failed"]}, evicted={retest_stats["evicted"]}'
        )
        logger.info(f'[9/10 POOL] 24h_added: {fmt_sources(pool_added_by_source)}')
        logger.info(f'[9/10 POOL] sources: {fmt_sources(pool_by_source)}')

        # Success rate: pool_added / generated (24h)
        def calc_success_rate(src: str) -> str:
            added = pool_added_by_source.get(src, 0)
            generated = gen_by_source.get(src, 0)
            if generated == 0:
                return "--"
            return f"{(added / generated) * 100:.2f}%"

        success_rates = {src: calc_success_rate(src) for src in SOURCE_ORDER}
        logger.info(f'[9/10 POOL] success_rate: {fmt_sources(success_rates, formatter=str)}')

        # Avg score by source (current pool)
        def fmt_avg_score(val) -> str:
            if val is None:
                return "--"
            return f"{val:.1f}"

        logger.info(f'[9/10 POOL] avg_score: {fmt_sources(pool_avg_score_by_source, formatter=fmt_avg_score)}')

        robustness_avg_str = f'{pool_robustness["avg"]:.2f}' if pool_robustness['count'] > 0 else '--'
        logger.info(f'[9/10 POOL] scores: {fmt_float(pool_stats["score_min"])} to {fmt_float(pool_stats["score_max"])} (avg {fmt_float(pool_stats["score_avg"])}) | robustness: {robustness_avg_str}')

        expectancy_str = f'{pool_quality["expectancy_avg"]*100:.1f}%' if pool_quality["expectancy_avg"] else "--"
        logger.info(f'[9/10 POOL] quality: sharpe={fmt_float(pool_quality["sharpe_avg"])}, wr={fmt_pct_float(pool_quality["winrate_avg"])}, exp={expectancy_str}, dd={fmt_pct_float(pool_quality["dd_avg"])}')

        logger.info(f'[9/10 POOL] retest: tested={retest_stats["tested"]}, passed={retest_stats["passed"]}, failed={retest_stats["failed"]}')
        logger.info(f'[9/10 POOL] rotation: evicted={retest_stats["evicted"]}, score_below_min={retest_stats["score_below_min"]}')

        # =====================================================================
        # [10/10 ROTATION]
        # =====================================================================
        live_count = live_stats["live"]
        live_limit = live_stats["limit"]
        slots_free = live_stats["slots_free"]
        active_count = live_stats["active_count"]
        min_pool_size = live_stats["min_pool_size"]
        pool_ready = live_stats["pool_ready"]
        pool_ready_str = "YES" if pool_ready else "NO"

        logger.info(
            f'[10/10 ROTATION] slots: {slots_free}/{live_limit} free | '
            f'pool_ready: {pool_ready_str} ({active_count} >= {min_pool_size})'
        )
        logger.info(
            f'[10/10 ROTATION] 24h: deployed={live_stats["deployed_24h"]}, '
            f'retired={live_stats["retired_24h"]}'
        )

        # =====================================================================
        # [LIVE]
        # =====================================================================
        # Trading mode from config
        dry_run = self.config.get('hyperliquid', {}).get('dry_run', True)
        mode_str = 'DRY_RUN' if dry_run else 'LIVE'

        avg_age_str = f'{live_stats["avg_age_days"]:.1f}d' if live_stats["avg_age_days"] else "--"
        avg_score_str = f'{live_stats["avg_score"]:.1f}' if live_stats["avg_score"] else "--"

        logger.info(
            f'[LIVE] mode={mode_str} | strategies: {live_count} | '
            f'avg_age={avg_age_str}, avg_score={avg_score_str}'
        )

        # Diversity stats - clearer format
        type_dist = live_stats.get("type_distribution", {})
        tf_dist = live_stats.get("timeframe_distribution", {})
        dir_dist = live_stats.get("direction_distribution", {})

        n_types = len(type_dist)
        n_tfs = len(tf_dist)
        n_dirs = len(dir_dist)

        # Build descriptive strings
        if n_tfs == 1 and tf_dist:
            tf_str = f"1 tf (all {list(tf_dist.keys())[0]})"
        else:
            tf_str = f"{n_tfs} tfs"

        if n_dirs == 1 and dir_dist:
            dir_str = f"1 dir (all {list(dir_dist.keys())[0]})"
        else:
            dir_str = f"{n_dirs} dirs"

        logger.info(
            f'[LIVE] diversity: {n_types} types, {tf_str}, {dir_str}'
        )

        # Capital summary: main + subaccounts
        main_balance = self._get_main_account_balance()
        subs_balance = sum(sub['balance'] for sub in subaccount_stats)
        total_balance = main_balance + subs_balance

        logger.info(
            f'[LIVE] total_capital: ${total_balance:.0f} | '
            f'main_account: ${main_balance:.0f} | sub_accounts: ${subs_balance:.0f}'
        )

        # =====================================================================
        # [SUB x] - Per-subaccount stats
        # =====================================================================
        for sub in subaccount_stats:
            sub_id = sub['id']
            balance = sub['balance']
            strategy = sub['strategy_name'] or '--'
            timeframe = sub.get('timeframe') or '--'
            direction = sub.get('direction') or '--'
            coins_count = sub.get('coins_count') or 0
            uptime_days = sub.get('uptime_days')
            rpnl = sub['rpnl']
            rpnl_pct = sub['rpnl_pct']
            upnl = sub['upnl']
            positions = sub['positions']
            dd_pct = sub['dd_pct']
            wr_pct = sub['wr_pct']

            # Format uptime
            uptime_str = f'{uptime_days:.1f}d' if uptime_days is not None else '--'

            # Format direction short (LONG->L, SHORT->S, BIDIR->B)
            dir_short = direction[0] if direction != '--' else '--'

            # Format coins (show count or -- if not populated)
            coins_str = f'{coins_count}c' if coins_count > 0 else '--'

            # Format strategy info: tf/dir/coins
            strat_info = f'{timeframe}/{dir_short}/{coins_str}'

            # Format with signs
            rpnl_sign = '+' if rpnl >= 0 else ''
            rpnl_pct_sign = '+' if rpnl_pct >= 0 else ''
            upnl_sign = '+' if upnl >= 0 else ''

            logger.info(
                f'[SUB {sub_id}] {strategy} | {strat_info} | '
                f'rpnl={rpnl_sign}${rpnl:.2f} ({rpnl_pct_sign}{rpnl_pct:.0f}%) | '
                f'dd={dd_pct:.0f}% | pos={positions} | upnl={upnl_sign}${upnl:.2f} | '
                f'${balance:.0f} | wr={wr_pct:.0f}% | up={uptime_str}'
            )

        # =====================================================================
        # [SCHEDULER]
        # =====================================================================
        total_ok = scheduler_stats.get("total_ok", 0)
        total_tasks = scheduler_stats.get("total_tasks", 0)
        tasks = scheduler_stats.get("tasks", {})

        logger.info(f'[SCHEDULER] status: {total_ok}/{total_tasks} tasks OK')

        # Format task status lines
        def fmt_task_time(dt: Optional[datetime]) -> str:
            if dt is None:
                return "never"
            return dt.strftime("%H:%M UTC")

        def fmt_task_status(status: str) -> str:
            if status == "SUCCESS":
                return "OK"
            elif status == "FAILED":
                return "FAIL"
            elif status == "NEVER_RUN":
                return "NEVER"
            elif status == "RUNNING":
                return "RUN"
            return status[:4]

        # Log each task on its own line (order preserved from _get_scheduler_stats per PIPELINE_AUX.md)
        for task_name, task_info in tasks.items():
            last_run = fmt_task_time(task_info.get("last_run"))
            next_run = fmt_task_time(task_info.get("next_run"))
            status = fmt_task_status(task_info.get("status", "UNKNOWN"))
            metadata = task_info.get("metadata", {})

            # Build result string from metadata
            result_parts = []
            for key, val in metadata.items():
                if isinstance(val, (int, float)) and key not in ('duration_seconds',):
                    result_parts.append(f"{key}={val}")
            result_str = f" ({', '.join(result_parts)})" if result_parts else ""

            logger.info(
                f'[SCHEDULER] {task_name}: last={last_run}, next={next_run}, status={status}{result_str}'
            )

    # =========================================================================
    # PUBLIC API METHODS (for external use)
    # =========================================================================

    def get_funnel_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get pipeline funnel metrics for the specified time period.

        Returns conversion rates through each stage.
        """
        since = datetime.now(UTC) - timedelta(hours=hours)

        with get_session() as session:
            return self._get_funnel_24h(session, since)

    def get_failure_analysis(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get detailed failure analysis for the specified time period.
        """
        since = datetime.now(UTC) - timedelta(hours=hours)

        with get_session() as session:
            return self._get_failures_24h(session, since)

    def get_full_snapshot(self) -> Dict[str, Any]:
        """
        Get the full pipeline snapshot as a dictionary for API consumption.

        Returns all computed metrics as a structured dict, same data that
        gets logged every collection interval.
        """
        try:
            with get_session() as session:
                # Time windows
                now = datetime.now(UTC)
                window_1min = now - timedelta(seconds=self.interval_seconds)
                window_24h = now - timedelta(hours=24)

                # Collect all metrics
                queue_depths = self._get_queue_depths(session)
                generator_stats = self._get_generator_stats_24h(session, window_24h)
                ai_calls_today = self._get_ai_calls_today()
                unused_patterns = self._get_unused_patterns(session)
                funnel = self._get_funnel_24h(session, window_24h)
                validation_by_source = self._get_validation_by_source_24h(session, window_24h)
                pool_added_by_source = self._get_pool_added_by_source_24h(session, window_24h)
                timing = self._get_timing_avg_24h(session, window_24h)
                throughput = self._get_throughput_interval(session, window_1min)
                failures = self._get_failures_24h(session, window_24h)
                backpressure = self._get_backpressure_status(session, queue_depths)
                pool_stats = self._get_pool_stats(session)
                pool_quality = self._get_pool_quality(session)
                pool_by_source = self._get_pool_by_source(session)
                pool_avg_score_by_source = self._get_pool_avg_score_by_source(session)
                is_stats = self._get_is_stats_24h(session, window_24h)
                oos_stats = self._get_oos_stats_24h(session, window_24h)
                score_stats = self._get_score_stats_24h(session, window_24h)
                retest_stats = self._get_retest_stats_24h(session, window_24h)
                robustness_stats = self._get_robustness_stats_24h(session, window_24h)
                pool_robustness = self._get_pool_robustness_stats(session)
                live_stats = self._get_live_rotation_stats(session, window_24h)
                combo_stats = self._get_combo_stats_24h(session, window_24h)
                scheduler_stats = self._get_scheduler_stats(session)
                subaccount_stats = self._get_subaccount_stats(session)

                # Overall status
                status, issue = self._get_status_and_issue(
                    queue_depths, backpressure, throughput
                )

                # Capital stats
                main_balance = self._get_main_account_balance()
                subs_balance = sum(sub['balance'] for sub in subaccount_stats)
                total_balance = main_balance + subs_balance

                # Trading mode
                dry_run = self.config.get('hyperliquid', {}).get('dry_run', True)

                return {
                    'timestamp': now.isoformat(),
                    'status': status,
                    'issue': issue,
                    'trading_mode': 'DRY_RUN' if dry_run else 'LIVE',

                    # Capital summary
                    'capital': {
                        'total': total_balance,
                        'main_account': main_balance,
                        'subaccounts': subs_balance,
                    },

                    # Queue depths
                    'queue_depths': queue_depths,

                    # Generator (step 1)
                    'generator': {
                        'total_24h': generator_stats['total'],
                        'by_source': generator_stats['by_source'],
                        'by_type': generator_stats['by_type'],
                        'by_direction': generator_stats['by_direction'],
                        'by_timeframe': generator_stats['by_timeframe'],
                        'timing_by_source': generator_stats['timing_by_source'],
                        'leverage': generator_stats['leverage'],
                        'by_provider': generator_stats['by_provider'],
                        'failures': generator_stats['gen_failures'],
                    },

                    # AI calls
                    'ai_calls': ai_calls_today,

                    # Patterns (for pattern source)
                    'patterns': unused_patterns,

                    # Validator (step 2)
                    'validator': {
                        'queue': queue_depths.get('GENERATED', 0),
                        'passed_24h': funnel['validated'],
                        'failed_24h': funnel['validation_failed'],
                        'by_source_passed': validation_by_source.get('passed', {}),
                        'by_source_failed': validation_by_source.get('failed', {}),
                        'timing_avg_ms': timing.get('validation'),
                    },

                    # Parametric (step 3)
                    'parametric': {
                        'waiting': backpressure['bt_waiting'],
                        'processing': backpressure['bt_processing'],
                        **combo_stats,
                    },

                    # IS Backtest (step 4)
                    'is_backtest': is_stats,

                    # OOS Backtest (step 5)
                    'oos_backtest': oos_stats,

                    # Score (step 6)
                    'score': score_stats,

                    # Shuffle test (step 7)
                    'shuffle': {
                        'failed': failures.get('shuffle_fail', 0),
                        'cached': failures.get('shuffle_cached', 0),
                    },

                    # WFA/Multi-window (step 8)
                    'wfa': {
                        'failed': failures.get('mw_fail', 0),
                    },

                    # Robustness (step 9)
                    'robustness': {
                        **robustness_stats,
                        'pool': pool_robustness,
                    },

                    # Pool (step 10)
                    'pool': {
                        **pool_stats,
                        'quality': pool_quality,
                        'by_source': pool_by_source,
                        'avg_score_by_source': pool_avg_score_by_source,
                        'added_24h_by_source': pool_added_by_source,
                    },

                    # Retest stats
                    'retest': retest_stats,

                    # Live trading
                    'live': {
                        **live_stats,
                    },

                    # Subaccounts (detailed per-subaccount stats)
                    'subaccounts': subaccount_stats,

                    # Scheduler
                    'scheduler': scheduler_stats,

                    # Backpressure status
                    'backpressure': backpressure,

                    # Funnel (raw data)
                    'funnel': funnel,

                    # Throughput
                    'throughput': throughput,

                    # Timing
                    'timing': timing,

                    # Failures
                    'failures': failures,
                }

        except Exception as e:
            logger.error(f"Failed to get full snapshot: {e}", exc_info=True)
            return {'error': str(e), 'timestamp': datetime.now(UTC).isoformat()}

    def run(self) -> None:
        """Main collection loop (runs forever)."""
        logger.info(f"Metrics collector started (interval: {self.interval_seconds}s)")

        while True:
            try:
                self.collect_snapshot()
            except Exception as e:
                logger.error(f"Metrics collection failed: {e}", exc_info=True)

            time.sleep(self.interval_seconds)


def main():
    """Entry point for running as a service."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    collector = MetricsCollector()
    collector.run()


if __name__ == '__main__':
    main()
