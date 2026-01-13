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
                live_stats = self._get_live_rotation_stats(session, window_24h)
                combo_stats = self._get_combo_stats_24h(session, window_24h)

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
                    live_stats=live_stats,
                    combo_stats=combo_stats,
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

        return {
            'tested': retested,
            'passed': passed,
            'failed': reason_counts.get('retest_failed', 0),
            'evicted': reason_counts.get('evicted', 0),
            'score_below_min': reason_counts.get('score_below_min', 0),
            # Legacy: total retired (for backwards compatibility)
            'retired': sum(r[1] for r in retired_by_reason),
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
        live_stats: Dict[str, Any],
        combo_stats: Dict[str, Any],
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
        # [9/10 POOL]
        # =====================================================================
        pool_size = pool_stats["size"]
        pool_limit = pool_stats["limit"]
        pool_entered = funnel["pool"]

        logger.info(f'[9/10 POOL] size: {pool_size}/{pool_limit} | 24h_added: {pool_entered}, 24h_retired: {retest_stats["retired"]}')
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

        logger.info(f'[9/10 POOL] scores: {fmt_float(pool_stats["score_min"])} to {fmt_float(pool_stats["score_max"])} (avg {fmt_float(pool_stats["score_avg"])})')

        expectancy_str = f'{pool_quality["expectancy_avg"]*100:.1f}%' if pool_quality["expectancy_avg"] else "--"
        logger.info(f'[9/10 POOL] quality: sharpe={fmt_float(pool_quality["sharpe_avg"])}, wr={fmt_pct_float(pool_quality["winrate_avg"])}, exp={expectancy_str}, dd={fmt_pct_float(pool_quality["dd_avg"])}')

        logger.info(f'[9/10 POOL] retest: tested={retest_stats["tested"]}, passed={retest_stats["passed"]}, failed={retest_stats["failed"]}')
        logger.info(f'[9/10 POOL] rotation: evicted={retest_stats["evicted"]}, score_below_min={retest_stats["score_below_min"]}')

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
