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

import time
import logging
from datetime import datetime, timedelta, UTC, date
from typing import Dict, List, Optional, Any, Tuple

from sqlalchemy import select, func, and_, or_, desc, cast, Integer, text

from src.config import load_config
from src.database import get_session, PipelineMetricsSnapshot, Strategy
from src.database.models import StrategyEvent, BacktestResult

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects pipeline metrics from events at regular intervals.

    Uses strategy_events table for accurate metrics:
    - Success rates calculated from passed/failed events
    - Failure reasons tracked and aggregated
    - Timing information from event durations
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize metrics collector.

        Args:
            config: Configuration dict (if None, loads from file)
        """
        if config is None:
            config = load_config()

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
                timing = self._get_timing_avg_24h(session, window_24h)
                throughput = self._get_throughput_interval(session, window_1min)
                failures = self._get_failures_24h(session, window_24h)
                backpressure = self._get_backpressure_status(session, queue_depths)
                pool_stats = self._get_pool_stats(session)
                pool_quality = self._get_pool_quality(session)
                pool_by_source = self._get_pool_by_source(session)
                is_stats = self._get_is_stats_24h(session, window_24h)
                oos_stats = self._get_oos_stats_24h(session, window_24h)
                score_stats = self._get_score_stats_24h(session, window_24h)
                retest_stats = self._get_retest_stats_24h(session, window_24h)
                live_stats = self._get_live_rotation_stats(session, window_24h)
                threshold_breakdown = self._get_threshold_breakdown_24h(session, window_24h)

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
                    timing=timing,
                    failures=failures,
                    backpressure=backpressure,
                    is_stats=is_stats,
                    oos_stats=oos_stats,
                    score_stats=score_stats,
                    pool_stats=pool_stats,
                    pool_quality=pool_quality,
                    pool_by_source=pool_by_source,
                    retest_stats=retest_stats,
                    live_stats=live_stats,
                    threshold_breakdown=threshold_breakdown,
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
            - by_type: Count by strategy_type (MOM, REV, TRN, etc.)
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
                -- By type
                by_type AS (
                    SELECT
                        event_data->>'strategy_type' as stype,
                        COUNT(*) as cnt
                    FROM base
                    WHERE event_data->>'strategy_type' IS NOT NULL
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
        by_source = {'pattern': 0, 'ai_free': 0, 'ai_assigned': 0}
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

        timing_by_source = {'pattern': None, 'ai_free': None, 'ai_assigned': None}
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
        # Get unique BASE pattern IDs used (extract UUID before '__' suffix)
        # Pattern IDs can be: "uuid" or "uuid__target_name"
        unique_used = session.execute(
            text("""
                SELECT COUNT(DISTINCT split_part(elem, '__', 1))
                FROM strategies s,
                     json_array_elements_text(s.pattern_ids) AS elem
                WHERE s.pattern_based = true
                  AND s.pattern_ids IS NOT NULL
            """)
        ).scalar() or 0

        # Get total strategies generated from patterns (all time, currently in DB)
        strategies_in_db = session.execute(
            text("""
                SELECT COUNT(*)
                FROM strategies
                WHERE pattern_based = true
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
            'strategies_in_db': strategies_in_db
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

        # Build dict with defaults
        sources = {'pattern': 0, 'ai_free': 0, 'ai_assigned': 0, 'optimized': 0, 'unknown': 0}
        for mode, count in result:
            if mode in sources:
                sources[mode] = count
            elif mode:
                sources['unknown'] += count

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

        # Parametric passed (strategies saved with score)
        parametric_passed = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'backtest',
                StrategyEvent.event_type == 'scored',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Parametric failed (no valid combinations found)
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
        bases_with_output = session.execute(
            text("""
                SELECT COUNT(DISTINCT base_code_hash)
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type = 'scored'
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
            'parametric_passed': parametric_passed,
            'parametric_failed': parametric_failed,
            'parametric_completed': parametric_passed + parametric_failed,
            'score_ok': score_ok,
            'score_ok_pct': pct(score_ok, parametric_passed),
            'shuffle_ok': shuffle_ok,
            'shuffle_ok_pct': pct(shuffle_ok, score_ok),
            'mw_started': mw_started,
            'mw_ok': mw_ok,
            'mw_failed': mw_failed,
            'mw_ok_pct': pct(mw_ok, shuffle_ok),
            'pool': pool_entered,
            'pool_pct': pct(pool_entered, mw_ok if mw_ok > 0 else shuffle_ok),
        }

    def _get_threshold_breakdown_24h(self, session, since: datetime) -> Dict[str, int]:
        """
        Aggregate threshold breakdown from parametric_failed events.

        Returns dict with failure counts per threshold type:
        {total, fail_trades, fail_sharpe, fail_wr, fail_exp, fail_dd}
        """
        result = session.execute(
            text("""
                SELECT
                    COALESCE(SUM((event_data->'threshold_breakdown'->>'fail_trades')::int), 0) as fail_trades,
                    COALESCE(SUM((event_data->'threshold_breakdown'->>'fail_sharpe')::int), 0) as fail_sharpe,
                    COALESCE(SUM((event_data->'threshold_breakdown'->>'fail_wr')::int), 0) as fail_wr,
                    COALESCE(SUM((event_data->'threshold_breakdown'->>'fail_exp')::int), 0) as fail_exp,
                    COALESCE(SUM((event_data->'threshold_breakdown'->>'fail_dd')::int), 0) as fail_dd,
                    COALESCE(SUM((event_data->'threshold_breakdown'->>'total_combos')::int), 0) as total_combos
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'backtest'
                  AND event_type = 'parametric_failed'
                  AND event_data->'threshold_breakdown' IS NOT NULL
            """),
            {'since': since}
        ).first()

        if not result or result[5] == 0:
            return {}

        return {
            'total': result[5],
            'fail_trades': result[0],
            'fail_sharpe': result[1],
            'fail_wr': result[2],
            'fail_exp': result[3],
            'fail_dd': result[4],
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

        Queries BacktestResult where period_type='in_sample' created in window.
        """
        result = session.execute(
            select(
                func.count(BacktestResult.id),
                func.avg(BacktestResult.sharpe_ratio),
                func.avg(BacktestResult.win_rate),
                func.avg(BacktestResult.expectancy),
                func.avg(BacktestResult.total_trades),
            )
            .where(and_(
                BacktestResult.period_type == 'in_sample',
                BacktestResult.created_at >= since
            ))
        ).first()

        return {
            'count': result[0] if result else 0,
            'avg_sharpe': float(result[1]) if result and result[1] else None,
            'avg_wr': float(result[2]) if result and result[2] else None,
            'avg_exp': float(result[3]) if result and result[3] else None,
            'avg_trades': float(result[4]) if result and result[4] else None,
        }

    def _get_oos_stats_24h(self, session, since: datetime) -> Dict[str, Any]:
        """
        Get OUT-OF-SAMPLE validation statistics for last 24h.

        Queries BacktestResult for OOS metrics. Degradation is stored on IS row
        as recency_ratio (1 - degradation).
        """
        # Count OOS results
        oos_count = session.execute(
            select(func.count(BacktestResult.id))
            .where(and_(
                BacktestResult.period_type == 'out_of_sample',
                BacktestResult.created_at >= since
            ))
        ).scalar() or 0

        # Get degradation stats from IS rows (recency_ratio stored there)
        # recency_ratio = 1 - degradation, so degradation = 1 - recency_ratio
        degrad_result = session.execute(
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

        return {
            'count': oos_count,
            'avg_degradation': float(degrad_result[0]) if degrad_result and degrad_result[0] else None,
            'oos_better': int(degrad_result[1]) if degrad_result and degrad_result[1] else 0,
            'oos_worse': int(degrad_result[2]) if degrad_result and degrad_result[2] else 0,
        }

    def _get_score_stats_24h(self, session, since: datetime) -> Dict[str, Any]:
        """Get score calculation statistics for last 24h."""
        # Get score distribution from strategies that passed score check
        result = session.execute(
            text("""
                SELECT
                    MIN((event_data->>'score')::float) as min_score,
                    MAX((event_data->>'score')::float) as max_score,
                    AVG((event_data->>'score')::float) as avg_score
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'shuffle_test'
                  AND event_type = 'started'
                  AND event_data->>'score' IS NOT NULL
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

        # Retired from retest (retired in last 24h)
        retired = session.execute(
            select(func.count(Strategy.id))
            .where(and_(
                Strategy.retired_at >= since,
                Strategy.status == 'RETIRED'
            ))
        ).scalar() or 0

        return {
            'tested': retested,
            'passed': passed,
            'retired': retired,
        }

    def _get_live_rotation_stats(self, session, since: datetime) -> Dict[str, Any]:
        """Get LIVE rotation statistics."""
        # Current LIVE count
        live_count = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.status == 'LIVE')
        ).scalar() or 0

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

        # Average age of LIVE strategies (days)
        avg_age_result = session.execute(
            select(func.avg(
                func.extract('epoch', func.now() - Strategy.live_since) / 86400
            ))
            .where(and_(
                Strategy.status == 'LIVE',
                Strategy.live_since.isnot(None)
            ))
        ).scalar()

        avg_age = float(avg_age_result) if avg_age_result else None

        return {
            'live': live_count,
            'limit': self.limit_live,
            'deployed_24h': deployed_24h,
            'retired_24h': retired_24h,
            'avg_age_days': avg_age,
        }

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
        timing: Dict[str, Optional[float]],
        failures: Dict[str, int],
        backpressure: Dict[str, Any],
        is_stats: Dict[str, Any],
        oos_stats: Dict[str, Any],
        score_stats: Dict[str, Any],
        pool_stats: Dict[str, Any],
        pool_quality: Dict[str, Any],
        pool_by_source: Dict[str, int],
        retest_stats: Dict[str, Any],
        live_stats: Dict[str, Any],
        threshold_breakdown: Dict[str, int],
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

        src_pattern = gen_by_source.get('pattern', 0)
        src_ai_free = gen_by_source.get('ai_free', 0)
        src_ai_assigned = gen_by_source.get('ai_assigned', 0)
        logger.info(f'[1/10 GENERATOR] 24h: {gen_total} strategies | pattern={src_pattern}, ai_free={src_ai_free}, ai_assigned={src_ai_assigned}')

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

        pat_unique = unused_patterns.get('unique_used', 0)
        pat_total = unused_patterns.get('total_available')
        pat_remaining = unused_patterns.get('remaining')
        pat_in_db = unused_patterns.get('strategies_in_db', 0)
        if pat_total is not None:
            # Format: "33 base patterns -> 79 strategies | 0 unused"
            unused_str = f" | {pat_remaining} unused" if pat_remaining and pat_remaining > 0 else ""
            logger.info(f'[1/10 GENERATOR] patterns: {pat_unique} base -> {pat_in_db} strategies{unused_str}')
        else:
            logger.info(f'[1/10 GENERATOR] patterns: {pat_unique} base -> {pat_in_db} strategies')

        time_pattern = fmt_time(gen_timing.get('pattern'))
        time_ai_free = fmt_time(gen_timing.get('ai_free'))
        time_ai_assigned = fmt_time(gen_timing.get('ai_assigned'))
        gen_failures = generator_stats.get('gen_failures', 0)
        logger.info(f'[1/10 GENERATOR] timing: pattern={time_pattern}, ai_free={time_ai_free}, ai_assigned={time_ai_assigned} | failures: {gen_failures}')

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
        logger.info(f'[2/10 VALIDATOR] timing: {fmt_time(timing.get("validation"))} avg')

        # =====================================================================
        # [3/10 PARAMETRIC]
        # =====================================================================
        v = queue_depths.get('VALIDATED', 0)
        bt_waiting = backpressure["bt_waiting"]
        bt_processing = backpressure["bt_processing"]
        combinations = funnel["combinations_tested"]
        param_failed = funnel["parametric_failed"]
        bases_with_output = funnel["bases_with_output"]
        param_passed = funnel["parametric_passed"]

        if bases_with_output > 0:
            strategies_per_base = f"{param_passed / bases_with_output:.1f}"
        elif param_passed > 0:
            estimated_bases = max(1, param_passed // 6)
            strategies_per_base = f"~{param_passed / estimated_bases:.1f}"
        else:
            strategies_per_base = "--"

        total_bases = param_failed + (bases_with_output or 0)
        logger.info(f'[3/10 PARAMETRIC] queue: {bt_waiting} waiting, {bt_processing} running')
        logger.info(f'[3/10 PARAMETRIC] 24h: {total_bases} bases tested, {combinations} combos')

        # Show threshold breakdown if available
        if threshold_breakdown:
            tb_total = threshold_breakdown.get('total', 0)
            if tb_total > 0:
                def tb_pct(n: int) -> str:
                    return f"{100*n//tb_total}%" if tb_total > 0 else "--"
                ft = threshold_breakdown.get('fail_trades', 0)
                fs = threshold_breakdown.get('fail_sharpe', 0)
                fw = threshold_breakdown.get('fail_wr', 0)
                fe = threshold_breakdown.get('fail_exp', 0)
                fd = threshold_breakdown.get('fail_dd', 0)
                logger.info(f'[3/10 PARAMETRIC] threshold_filter (combos):')
                logger.info(f'[3/10 PARAMETRIC]   trades<10: {ft} ({tb_pct(ft)}) | sharpe<0.3: {fs} ({tb_pct(fs)})')
                logger.info(f'[3/10 PARAMETRIC]   wr<0.35: {fw} ({tb_pct(fw)}) | exp<0.002: {fe} ({tb_pct(fe)}) | dd>0.5: {fd} ({tb_pct(fd)})')

        logger.info(f'[3/10 PARAMETRIC] passed: {bases_with_output or 0} bases -> {param_passed} strategies ({strategies_per_base}/base)')
        logger.info(f'[3/10 PARAMETRIC] timing: {fmt_time(timing.get("backtest"))}/base | failures: {param_failed}')

        # =====================================================================
        # [4/10 IS_BACKTEST]
        # =====================================================================
        is_count = is_stats.get('count', 0)
        is_sharpe = fmt_float(is_stats.get('avg_sharpe'))
        is_wr = fmt_pct_float(is_stats.get('avg_wr'))
        is_exp = fmt_float(is_stats.get('avg_exp'), 3) if is_stats.get('avg_exp') else "--"
        is_trades = fmt_float(is_stats.get('avg_trades'), 0) if is_stats.get('avg_trades') else "--"

        logger.info(f'[4/10 IS_BACKTEST] 24h: {is_count} strategies tested')
        logger.info(f'[4/10 IS_BACKTEST] metrics: sharpe={is_sharpe}, wr={is_wr}, exp={is_exp}, trades={is_trades}')

        # =====================================================================
        # [5/10 OOS_BACKTEST]
        # =====================================================================
        oos_count = oos_stats.get('count', 0)
        avg_degrad = oos_stats.get('avg_degradation')
        oos_better = oos_stats.get('oos_better', 0)
        oos_worse = oos_stats.get('oos_worse', 0)

        degrad_str = f"{avg_degrad*100:.0f}%" if avg_degrad is not None else "--"
        logger.info(f'[5/10 OOS_BACKTEST] 24h: {oos_count} strategies tested')
        logger.info(f'[5/10 OOS_BACKTEST] degradation: {degrad_str} | oos_better={oos_better}, oos_worse={oos_worse}')

        # =====================================================================
        # [6/10 SCORE]
        # =====================================================================
        score_ok = funnel["score_ok"]
        score_rejected = failures["score_reject"]
        min_score = fmt_float(score_stats.get('min_score'))
        max_score = fmt_float(score_stats.get('max_score'))
        avg_score = fmt_float(score_stats.get('avg_score'))

        logger.info(f'[6/10 SCORE] 24h: {score_ok}/{param_passed} passed min_score={self.pool_min_score} ({fmt_pct(funnel["score_ok_pct"])})')
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
        logger.info(f'[8/10 WFA] timing: {fmt_time(timing.get("multiwindow"))} | cv_failures: {mw_failed}')

        # =====================================================================
        # [9/10 POOL]
        # =====================================================================
        pool_size = pool_stats["size"]
        pool_limit = pool_stats["limit"]
        pool_pattern = pool_by_source.get('pattern', 0)
        pool_ai_free = pool_by_source.get('ai_free', 0)
        pool_ai_assigned = pool_by_source.get('ai_assigned', 0)
        pool_optimized = pool_by_source.get('optimized', 0)
        pool_entered = funnel["pool"]

        logger.info(f'[9/10 POOL] size: {pool_size}/{pool_limit} | 24h_added: {pool_entered}')
        logger.info(f'[9/10 POOL] sources: pattern={pool_pattern}, ai_free={pool_ai_free}, ai_assigned={pool_ai_assigned}, optimized={pool_optimized}')
        logger.info(f'[9/10 POOL] scores: {fmt_float(pool_stats["score_min"])} to {fmt_float(pool_stats["score_max"])} (avg {fmt_float(pool_stats["score_avg"])})')

        expectancy_str = f'{pool_quality["expectancy_avg"]*100:.1f}%' if pool_quality["expectancy_avg"] else "--"
        logger.info(f'[9/10 POOL] quality: sharpe={fmt_float(pool_quality["sharpe_avg"])}, wr={fmt_pct_float(pool_quality["winrate_avg"])}, exp={expectancy_str}, dd={fmt_pct_float(pool_quality["dd_avg"])}')

        logger.info(f'[9/10 POOL] retest: tested={retest_stats["tested"]}, passed={retest_stats["passed"]}, evicted={retest_stats["retired"]}')

        # =====================================================================
        # [10/10 LIVE]
        # =====================================================================
        live_count = live_stats["live"]
        live_limit = live_stats["limit"]
        avg_age_str = f'{live_stats["avg_age_days"]:.1f}d' if live_stats["avg_age_days"] else "--"

        logger.info(f'[10/10 LIVE] active: {live_count}/{live_limit} (avg_age: {avg_age_str})')
        logger.info(f'[10/10 LIVE] 24h: deployed={live_stats["deployed_24h"]}, retired={live_stats["retired_24h"]}')

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
