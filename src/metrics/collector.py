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
                retest_stats = self._get_retest_stats_24h(session, window_24h)
                live_stats = self._get_live_rotation_stats(session, window_24h)

                # Determine overall status
                status, issue = self._get_status_and_issue(
                    queue_depths, backpressure, throughput
                )

                # Save snapshot to database
                self._save_snapshot(
                    session, queue_depths, throughput, funnel, pool_quality, status
                )

                # Log metrics in new format
                self._log_metrics(
                    status=status,
                    issue=issue,
                    queue_depths=queue_depths,
                    generation_by_source=generation_by_source,
                    generator_stats=generator_stats,
                    ai_calls_today=ai_calls_today,
                    unused_patterns=unused_patterns,
                    funnel=funnel,
                    timing=timing,
                    throughput=throughput,
                    failures=failures,
                    backpressure=backpressure,
                    pool_stats=pool_stats,
                    pool_quality=pool_quality,
                    pool_by_source=pool_by_source,
                    retest_stats=retest_stats,
                    live_stats=live_stats,
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
        # Total generated
        total = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'generation',
                StrategyEvent.event_type == 'created',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # By source (generation_mode) - uses new field in event_data
        by_source_result = session.execute(
            text("""
                SELECT
                    COALESCE(event_data->>'generation_mode',
                        CASE
                            WHEN (event_data->>'pattern_based')::boolean = true THEN 'pattern'
                            ELSE 'ai_free'
                        END
                    ) as source,
                    COUNT(*) as count
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'generation'
                  AND event_type = 'created'
                GROUP BY 1
            """),
            {'since': since}
        ).all()

        by_source = {'pattern': 0, 'ai_free': 0, 'ai_assigned': 0}
        for source, count in by_source_result:
            if source in by_source:
                by_source[source] = count

        # By strategy type (MOM, REV, TRN, etc.)
        by_type_result = session.execute(
            text("""
                SELECT
                    event_data->>'strategy_type' as stype,
                    COUNT(*) as count
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'generation'
                  AND event_type = 'created'
                  AND event_data->>'strategy_type' IS NOT NULL
                GROUP BY 1
                ORDER BY count DESC
            """),
            {'since': since}
        ).all()

        by_type = {}
        for stype, count in by_type_result:
            if stype:
                by_type[stype] = count

        # By direction (LONG, SHORT, BIDIR)
        by_direction_result = session.execute(
            text("""
                SELECT
                    COALESCE(event_data->>'direction', 'UNKNOWN') as direction,
                    COUNT(*) as count
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'generation'
                  AND event_type = 'created'
                GROUP BY 1
            """),
            {'since': since}
        ).all()

        by_direction = {'LONG': 0, 'SHORT': 0, 'BIDIR': 0}
        for direction, count in by_direction_result:
            if direction in by_direction:
                by_direction[direction] = count

        # By timeframe (15m, 30m, 1h, 4h, 1d)
        by_timeframe_result = session.execute(
            text("""
                SELECT
                    event_data->>'timeframe' as tf,
                    COUNT(*) as count
                FROM strategy_events
                WHERE timestamp >= :since
                  AND stage = 'generation'
                  AND event_type = 'created'
                  AND event_data->>'timeframe' IS NOT NULL
                GROUP BY 1
                ORDER BY count DESC
            """),
            {'since': since}
        ).all()

        by_timeframe = {}
        for tf, count in by_timeframe_result:
            if tf:
                by_timeframe[tf] = count

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
        generation_by_source: Dict[str, int],
        generator_stats: Dict[str, Any],
        ai_calls_today: Dict[str, Any],
        unused_patterns: Dict[str, Any],
        funnel: Dict[str, Any],
        timing: Dict[str, Optional[float]],
        throughput: Dict[str, int],
        failures: Dict[str, int],
        backpressure: Dict[str, Any],
        pool_stats: Dict[str, Any],
        pool_quality: Dict[str, Any],
        pool_by_source: Dict[str, int],
        retest_stats: Dict[str, Any],
        live_stats: Dict[str, Any],
    ) -> None:
        """
        Log metrics in verbose, self-explanatory format.

        Key design principles:
        - Strategy types (pattern, ai_free, ai_assigned) are tracked separately
        - TIMING section clearly distinguishes:
          * parametric_full = time for ALL ~1015 combinations per base strategy
          * multiwindow_test = time for ONE strategy on 4 windows
        - Visual separators make backtester phases crystal clear
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

        # === GENERATOR 24H ===
        gen_total = generator_stats['total']
        gen_by_source = generator_stats['by_source']
        gen_by_type = generator_stats['by_type']
        gen_by_dir = generator_stats['by_direction']
        gen_by_tf = generator_stats['by_timeframe']
        gen_timing = generator_stats['timing_by_source']
        gen_leverage = generator_stats['leverage']

        logger.info(f'[GENERATOR 24H] total strategies generated in last 24 hours: {gen_total}')

        # By source
        src_pattern = gen_by_source.get('pattern', 0)
        src_ai_free = gen_by_source.get('ai_free', 0)
        src_ai_assigned = gen_by_source.get('ai_assigned', 0)
        logger.info(f'[GENERATOR 24H] by_source: pattern={src_pattern}, ai_free={src_ai_free}, ai_assigned={src_ai_assigned}')

        # By type (show all types that have count > 0)
        type_parts = [f'{t}={c}' for t, c in sorted(gen_by_type.items()) if c > 0]
        type_str = ', '.join(type_parts) if type_parts else '--'
        logger.info(f'[GENERATOR 24H] by_type: {type_str}')

        # By direction
        dir_long = gen_by_dir.get('LONG', 0)
        dir_short = gen_by_dir.get('SHORT', 0)
        dir_bidir = gen_by_dir.get('BIDIR', 0)
        logger.info(f'[GENERATOR 24H] by_direction: LONG={dir_long}, SHORT={dir_short}, BIDIR={dir_bidir}')

        # By timeframe (ordered by timeframe duration)
        tf_order = ['5m', '15m', '30m', '1h', '2h']
        tf_parts = [f'{tf}={gen_by_tf.get(tf, 0)}' for tf in tf_order if gen_by_tf.get(tf, 0) > 0]
        # Add any other timeframes not in the standard order
        for tf, count in gen_by_tf.items():
            if tf not in tf_order and count > 0:
                tf_parts.append(f'{tf}={count}')
        tf_str = ', '.join(tf_parts) if tf_parts else '--'
        logger.info(f'[GENERATOR 24H] by_timeframe: {tf_str}')

        # Leverage stats
        lev_min = gen_leverage.get('min')
        lev_max = gen_leverage.get('max')
        lev_avg = gen_leverage.get('avg')
        lev_str = f"min={lev_min or '--'}, max={lev_max or '--'}, avg={fmt_float(lev_avg)}"
        logger.info(f'[GENERATOR 24H] leverage: {lev_str}')

        # AI calls today
        ai_count = ai_calls_today.get('count')
        ai_max = ai_calls_today.get('max_calls')
        ai_remaining = ai_calls_today.get('remaining')
        if ai_count is not None and ai_max is not None:
            logger.info(f'[GENERATOR 24H] ai_calls_today: {ai_count}/{ai_max} ({ai_remaining} remaining)')
        else:
            logger.info('[GENERATOR 24H] ai_calls_today: --')

        # Timing by source
        time_pattern = fmt_time(gen_timing.get('pattern'))
        time_ai_free = fmt_time(gen_timing.get('ai_free'))
        time_ai_assigned = fmt_time(gen_timing.get('ai_assigned'))
        logger.info(f'[GENERATOR 24H] avg_time: pattern={time_pattern}, ai_free={time_ai_free}, ai_assigned={time_ai_assigned}')

        # Generation failures (validation failed before DB save)
        gen_failures = generator_stats.get('gen_failures', 0)
        logger.info(f'[GENERATOR 24H] gen_validation_failed: {gen_failures}')

        # Patterns (all time stats, not 24h)
        pat_unique = unused_patterns.get('unique_used', 0)
        pat_total = unused_patterns.get('total_available')
        pat_remaining = unused_patterns.get('remaining')
        pat_in_db = unused_patterns.get('strategies_in_db', 0)
        if pat_total is not None:
            logger.info(f'[GENERATOR] patterns: {pat_unique}/{pat_total} used ({pat_remaining} remaining) -> {pat_in_db} strategies in DB')
        else:
            logger.info(f'[GENERATOR] patterns: {pat_unique} used (total unknown) -> {pat_in_db} strategies in DB')

        # === QUEUE ===
        g = queue_depths.get('GENERATED', 0)
        v = queue_depths.get('VALIDATED', 0)
        a = queue_depths.get('ACTIVE', 0)
        lv = queue_depths.get('LIVE', 0)
        r = queue_depths.get('RETIRED', 0)
        # Calculate failed from events (DB count is always 0 because failed strategies are deleted)
        failed_24h = (
            failures["validation"] +
            failures["parametric_fail"] +
            failures["score_reject"] +
            failures["shuffle_fail"] +
            failures["mw_fail"]
        )
        logger.info('[QUEUE] strategies waiting at each stage')
        logger.info(f'[QUEUE] generated: {g} (waiting for validation)')
        logger.info(f'[QUEUE] validated: {v} (waiting for backtest)')
        logger.info(f'[QUEUE] active: {a} (in pool, ready to deploy)')
        logger.info(f'[QUEUE] live: {lv} (trading now)')
        logger.info(f'[QUEUE] retired: {r} (removed from live)')
        # Total processed = strategies that completed any stage (use generated as proxy)
        total_processed = funnel["generated"]
        failed_pct = f"{100 * failed_24h // total_processed}%" if total_processed > 0 else "--"
        logger.info(f'[QUEUE] failed_24h: {failed_24h} of {total_processed} ({failed_pct}) rejected in last 24h')

        # === FUNNEL 24H ===
        gen = funnel["generated"]
        val = funnel["validated"]
        val_failed = funnel["validation_failed"]
        bases_done = funnel["bases_completed"]
        bases_with_combos = funnel["bases_with_combos"]
        bases_with_output = funnel["bases_with_output"]
        combinations = funnel["combinations_tested"]
        param_passed = funnel["parametric_passed"]
        param_failed = funnel["parametric_failed"]
        score = funnel["score_ok"]
        shuf = funnel["shuffle_ok"]
        mw_started = funnel["mw_started"]
        mw = funnel["mw_ok"]
        mw_failed = funnel["mw_failed"]
        mw_in_progress = max(0, mw_started - mw - mw_failed)
        pool = funnel["pool"]

        # Calculate rates - use bases_with_combos for accurate average
        avg_combos_per_base = f"{combinations // bases_with_combos}" if bases_with_combos > 0 else "1015"

        # bases_with_output uses base_code_hash (0 for legacy events without hash)
        # When base_code_hash not available, estimate from param_passed / avg_per_base
        if bases_with_output > 0:
            bases_producing = bases_with_output
            strategies_per_base = f"{param_passed / bases_with_output:.1f}"
        elif param_passed > 0:
            # Fallback: estimate ~6 strategies per successful base (empirical average)
            estimated_bases = max(1, param_passed // 6)
            bases_producing = estimated_bases
            strategies_per_base = f"~{param_passed / estimated_bases:.1f}"
        else:
            bases_producing = 0
            strategies_per_base = "--"

        # Find bottleneck (lowest non-100% pass rate after validation)
        bottleneck = ""
        if shuf > 0 and mw == 0 and mw_in_progress == 0:
            bottleneck = " <-- BOTTLENECK"
        elif score > 0 and shuf == 0:
            bottleneck = " <-- BOTTLENECK"

        # Show validation with failed count for clarity
        val_total = val + val_failed
        val_failed_str = f", {val_failed} failed" if val_failed > 0 else ""
        logger.info('[FUNNEL 24H] pipeline conversion (base strategies -> output strategies)')
        logger.info(f'[FUNNEL 24H] validated: {val} of {gen} base passed syntax/AST/execution ({fmt_pct(funnel["validated_pct"])}){val_failed_str}')
        logger.info(f'[FUNNEL 24H] parametric: {bases_producing} base -> {param_passed} strategies ({strategies_per_base}/base), {param_failed} base rejected, {combinations} combos')
        logger.info(f'[FUNNEL 24H] score_ok: {score} of {param_passed} strategies passed min_score {self.pool_min_score} ({fmt_pct(funnel["score_ok_pct"])})')
        logger.info(f'[FUNNEL 24H] shuffle_ok: {shuf} of {score} passed lookahead test ({fmt_pct(funnel["shuffle_ok_pct"])})')
        mw_in_progress_str = f", {mw_in_progress} in progress" if mw_in_progress > 0 else ""
        logger.info(f'[FUNNEL 24H] multiwindow_ok: {mw} of {shuf} passed 4-window consistency ({fmt_pct(funnel["mw_ok_pct"])}), {mw_failed} failed{mw_in_progress_str}{bottleneck}')
        logger.info(f'[FUNNEL 24H] pool_added: {pool} entered ACTIVE pool')

        # === TIMING ===
        logger.info('[TIMING 24H] average duration by operation type')
        logger.info(f'[TIMING 24H] validation: {fmt_time(timing.get("validation"))} per base (syntax + AST + execution)')
        logger.info(f'[TIMING 24H] parametric_backtest: {fmt_time(timing.get("backtest"))} per base (1015 combos x {self.is_days}d + {self.oos_days}d)')
        shuffle_cached = failures.get("shuffle_cached", 0)
        shuffle_cached_str = f", {shuffle_cached} cached" if shuffle_cached > 0 else ""
        logger.info(f'[TIMING 24H] shuffle_test: {fmt_time(timing.get("shuffle"))} per strategy (lookahead detection{shuffle_cached_str})')
        logger.info(f'[TIMING 24H] multiwindow_test: {fmt_time(timing.get("multiwindow"))} per strategy (4 window backtests)')

        # === FAILURES 24H ===
        # Note: counts may exceed funnel numbers due to backlog (strategies validated before 24h window)
        logger.info('[FAILURES 24H] rejection counts by stage (may include backlog)')
        logger.info(f'[FAILURES 24H] validation: {failures["validation"]} (code errors)')
        logger.info(f'[FAILURES 24H] parametric_no_valid: {failures["parametric_fail"]} (no combo passed filters)')
        logger.info(f'[FAILURES 24H] score_below_min: {failures["score_reject"]} (score < {self.pool_min_score})')
        logger.info(f'[FAILURES 24H] shuffle_bias: {failures["shuffle_fail"]} (lookahead bias detected)')
        logger.info(f'[FAILURES 24H] multiwindow_inconsistent: {failures["mw_fail"]} (CV > 1.5 across time windows)')
        # pool_rejected: explain based on whether pool is full and whether rejections happened
        pool_size = pool_stats["size"]
        pool_reject_count = failures["pool_reject"]
        if pool_reject_count == 0:
            if pool_size >= self.limit_active:
                pool_reject_msg = f"pool_rejected: 0 (pool full at {self.limit_active}, no new strategies qualified)"
            else:
                pool_reject_msg = f"pool_rejected: 0 (pool not full, all qualifying strategies accepted)"
        else:
            pool_reject_msg = f"pool_rejected: {pool_reject_count} (score < worst in full pool of {self.limit_active})"
        logger.info(f'[FAILURES 24H] {pool_reject_msg}')

        # === BACKPRESSURE ===
        gen_pct = int(100 * backpressure["gen_queue"] / backpressure["gen_limit"]) if backpressure["gen_limit"] > 0 else 0
        val_pct = int(100 * backpressure["val_queue"] / backpressure["val_limit"]) if backpressure["val_limit"] > 0 else 0
        gen_status = "OVERFLOW" if backpressure["gen_full"] else "OK"
        val_status = "OVERFLOW" if val_pct > 100 else "OK"
        logger.info('[BACKPRESSURE] queue saturation')
        logger.info(f'[BACKPRESSURE] validation_pending: {backpressure["gen_queue"]}/{backpressure["gen_limit"]} ({gen_pct}%) {gen_status}')
        logger.info(f'[BACKPRESSURE] backtest_pending: {backpressure["val_queue"]}/{backpressure["val_limit"]} ({val_pct}%) {val_status}')
        logger.info(f'[BACKPRESSURE] backtest_waiting: {backpressure["bt_waiting"]} in queue')
        logger.info(f'[BACKPRESSURE] backtest_active: {backpressure["bt_processing"]} running now')

        # === POOL === (IMPROVED - includes composition by source)
        pool_pattern = pool_by_source.get('pattern', 0)
        pool_ai_free = pool_by_source.get('ai_free', 0)
        pool_ai_assigned = pool_by_source.get('ai_assigned', 0)
        pool_optimized = pool_by_source.get('optimized', 0)
        logger.info('[POOL] strategies ready for live trading')
        logger.info(f'[POOL] size: {pool_stats["size"]} of {pool_stats["limit"]} max')
        logger.info(f'[POOL] by_source: pattern={pool_pattern}, ai_free={pool_ai_free}, ai_assigned={pool_ai_assigned}, optimized={pool_optimized}')
        logger.info(f'[POOL] score_range: {fmt_float(pool_stats["score_min"])} - {fmt_float(pool_stats["score_max"])} (avg {fmt_float(pool_stats["score_avg"])})')
        expectancy_str = f'{pool_quality["expectancy_avg"]*100:.1f}%' if pool_quality["expectancy_avg"] else "--"
        logger.info(f'[POOL] quality: sharpe={fmt_float(pool_quality["sharpe_avg"])}, winrate={fmt_pct_float(pool_quality["winrate_avg"])}, expectancy={expectancy_str}, dd={fmt_pct_float(pool_quality["dd_avg"])}')

        # === RETEST 24H ===
        logger.info(f'[RETEST 24H] pool freshness (re-backtest every {self.retest_interval_days} days)')
        logger.info(f'[RETEST 24H] tested: {retest_stats["tested"]}, passed: {retest_stats["passed"]}, evicted: {retest_stats["retired"]}')

        # === LIVE ===
        avg_age_str = f'{live_stats["avg_age_days"]:.1f}d' if live_stats["avg_age_days"] else "--"
        logger.info('[LIVE] strategies trading real money')
        logger.info(f'[LIVE] active: {live_stats["live"]} of {live_stats["limit"]} max (avg_age: {avg_age_str})')
        logger.info(f'[LIVE] 24h: deployed={live_stats["deployed_24h"]}, retired={live_stats["retired_24h"]}')

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
