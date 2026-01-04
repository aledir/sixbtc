"""
Pattern Discovery API Client

Fetches validated trading patterns from the pattern-discovery service.
Patterns are used as building blocks for AI-generated strategies.
"""

import requests
from typing import Optional, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class CoinPerformance:
    """Coin-specific performance data for a pattern"""
    coin: str
    edge: float
    win_rate: float
    n_signals: int


@dataclass
class TargetResult:
    """Target-specific test results for a pattern"""
    target_name: str
    tier: Optional[int]  # Can be None for non-validated targets
    edge: float  # avg_edge from API
    win_rate: float
    n_signals: int
    direction: str  # 'long' or 'short'
    hold_hours: int  # 1, 4, 24, etc.
    magnitude: Optional[float] = None  # Target price move in % (e.g., 2.0 for 2%)
    is_valid: bool = False
    quality_score: float = 0.0


@dataclass
class Pattern:
    """Trading pattern from pattern-discovery"""
    id: str
    name: str
    formula: str
    tier: int
    target_name: str  # e.g., 'target_up_24h'
    target_direction: str  # 'long' or 'short'
    test_edge: float  # Edge percentage
    test_win_rate: float  # Win rate (0-1)
    test_n_signals: int  # Number of signals
    quality_score: float

    # New fields from pattern-discovery API
    timeframe: str = "15m"  # Pattern timeframe
    holding_period: Optional[str] = None  # Expected hold time (4h, 24h)
    target_magnitude: Optional[float] = None  # Target price move in % (e.g., 2.0 for 2%)
    strategy_type: Optional[str] = None  # MOM, REV, TRN, BRE, VOL
    formula_readable: Optional[str] = None  # Human-readable formula

    # Suggested trading parameters
    suggested_sl_type: Optional[str] = None  # ATR, PERCENTAGE, etc.
    suggested_sl_multiplier: Optional[float] = None
    suggested_tp_type: Optional[str] = None
    suggested_rr_ratio: Optional[float] = None
    avg_signals_per_month: Optional[float] = None

    worst_window: Optional[float] = None  # Minimum edge across windows

    # Executable source code (from new API)
    formula_source: Optional[str] = None  # Complete Python function code
    formula_components: Optional[dict] = None  # {category, docstring, return_expression}

    # Coin-specific performance data
    coin_performance: Optional[List[CoinPerformance]] = None

    # Multi-target support
    target_results: Optional[List[TargetResult]] = None
    original_pattern_id: Optional[str] = None  # For virtual patterns
    is_virtual: bool = False  # True if expanded from multi-target

    def get_high_edge_coins(
        self,
        min_edge: float = 0.10,
        min_signals: int = 50,
        max_coins: int = 30,
        filter_tradable: bool = True
    ) -> List[str]:
        """
        Get coins where this pattern has demonstrated positive edge.

        Args:
            min_edge: Minimum edge threshold (default 10%)
            min_signals: Minimum number of signals for reliability
            max_coins: Maximum coins to return
            filter_tradable: If True, only return coins in CoinRegistry (default True)

        Returns:
            List of coin symbols sorted by edge (descending)
        """
        if not self.coin_performance:
            return []

        # Get tradable coins from registry if filtering enabled
        tradable_coins = None
        if filter_tradable:
            try:
                from src.data.coin_registry import get_active_pairs
                tradable_coins = set(get_active_pairs())
            except Exception as e:
                logger.warning(f"Failed to get tradable coins: {e}")
                tradable_coins = None

        filtered = [
            cp for cp in self.coin_performance
            if cp.edge >= min_edge and cp.n_signals >= min_signals
            and (tradable_coins is None or cp.coin in tradable_coins)
        ]

        # Sort by edge descending
        sorted_coins = sorted(filtered, key=lambda x: x.edge, reverse=True)

        return [cp.coin for cp in sorted_coins[:max_coins]]


class PatternFetcher:
    """
    Client for pattern-discovery API

    Fetches validated Tier 1 patterns to use in strategy generation.

    API Base: http://localhost:8001/api/v1
    """

    def __init__(self, api_url: str = "http://localhost:8001"):
        """
        Initialize pattern fetcher

        Args:
            api_url: Base URL for pattern-discovery API
        """
        self.api_url = api_url.rstrip('/')
        self.api_base = f"{self.api_url}/api/v1"
        self._available = self._check_connection()

    def _check_connection(self, max_retries: int = 3) -> bool:
        """
        Check if pattern-discovery API is accessible with retries.

        Uses exponential backoff to handle race conditions at startup
        (e.g., when pattern-discovery is still starting).

        Args:
            max_retries: Maximum number of connection attempts

        Returns:
            True if connected, False otherwise
        """
        import time

        for attempt in range(max_retries):
            try:
                response = requests.get(f"{self.api_url}/health", timeout=5)
                if response.status_code == 200:
                    logger.info(f"Pattern Discovery API connected: {self.api_url}")
                    return True
                else:
                    logger.warning(
                        f"Pattern Discovery API returned status {response.status_code}"
                    )
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    logger.debug(
                        f"Pattern Discovery API not accessible (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.warning(f"Pattern Discovery API not accessible after {max_retries} attempts: {e}")
                    logger.warning("Strategy generation will use custom AI logic only")

        return False

    def is_available(self) -> bool:
        """Check if API is available"""
        return self._available

    def fetch_production_patterns(
        self,
        tier: int = 1,
        limit: int = 100
    ) -> List[dict]:
        """
        Fetch production-ready patterns

        Args:
            tier: Pattern tier (1 = highest quality)
            limit: Maximum number of patterns to return

        Returns:
            List of pattern dicts
        """
        if not self._available:
            return []

        try:
            params = {
                'status': 'PRODUCTION',
                'tier': tier,
                'limit': limit
            }

            response = requests.get(
                f"{self.api_base}/patterns",
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch patterns: {response.status_code} {response.text}"
                )
                return []

            data = response.json()
            patterns = data.get('patterns', [])

            logger.info(f"Fetched {len(patterns)} Tier {tier} PRODUCTION patterns")
            return patterns

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching patterns: {e}")
            return []

    def get_tier_1_patterns(
        self,
        timeframe: Optional[str] = None,
        limit: int = 10,
        min_quality_score: float = 0.75
    ) -> List[Pattern]:
        """
        Fetch Tier 1 patterns from pattern-discovery

        Args:
            timeframe: Filter by timeframe (e.g., '15m', '1h') - not used by API currently
            limit: Maximum number of patterns to return
            min_quality_score: Minimum quality score (0-1)

        Returns:
            List of Pattern objects
        """
        if not self._available:
            return []

        try:
            params = {
                'status': 'PRODUCTION',
                'tier': 1,
                'limit': limit,
                'include_coin_performance': 'true',  # Get per-coin edge data
            }

            response = requests.get(
                f"{self.api_base}/patterns",
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch patterns: {response.status_code} {response.text}"
                )
                return []

            data = response.json()
            raw_patterns = data.get('patterns', [])

            # Filter by quality score locally
            filtered = [
                p for p in raw_patterns
                if (p.get('quality_score') or 0) >= min_quality_score
            ]

            patterns = [self._parse_pattern(p) for p in filtered]

            logger.info(f"Fetched {len(patterns)} Tier 1 patterns (quality >= {min_quality_score})")
            return patterns

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching patterns: {e}")
            return []

    def get_pattern_by_id(self, pattern_id: str) -> Optional[Pattern]:
        """
        Get specific pattern by ID

        Args:
            pattern_id: Pattern UUID

        Returns:
            Pattern object or None if not found
        """
        if not self._available:
            return None

        try:
            response = requests.get(
                f"{self.api_base}/patterns/{pattern_id}",
                timeout=10
            )

            if response.status_code != 200:
                logger.error(f"Pattern {pattern_id} not found")
                return None

            data = response.json()
            return self._parse_pattern(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching pattern {pattern_id}: {e}")
            return None

    def _parse_pattern(self, data: dict) -> Pattern:
        """Parse pattern data from API response"""
        # target_direction now comes directly from API (long/short)
        target_direction = data.get('target_direction', 'long')

        # Parse coin_performance data
        coin_perf_data = data.get('coin_performance', [])
        coin_performance = None
        if coin_perf_data:
            coin_performance = [
                CoinPerformance(
                    coin=cp.get('coin', ''),
                    edge=cp.get('edge', 0.0),
                    win_rate=cp.get('win_rate', 0.0),
                    n_signals=cp.get('n_signals', 0)
                )
                for cp in coin_perf_data
                if cp.get('coin')  # Skip empty entries
            ]

        # Parse target_results (dict format: {target_name: {tier, avg_edge, ...}})
        target_results_data = data.get('target_results', {})
        target_results = None
        if target_results_data and isinstance(target_results_data, dict):
            target_results = [
                TargetResult(
                    target_name=target_name,
                    tier=tr_data.get('tier'),  # Can be None for non-tier targets
                    edge=tr_data.get('avg_edge', 0.0),
                    win_rate=tr_data.get('win_rate', 0.0),
                    n_signals=tr_data.get('n_signals', 0),
                    direction=tr_data.get('direction', 'long'),
                    hold_hours=tr_data.get('hold_hours', 24),
                    magnitude=tr_data.get('magnitude'),  # Target price move in %
                    is_valid=tr_data.get('is_valid', False),
                    quality_score=tr_data.get('quality_score', 0.0)
                )
                for target_name, tr_data in target_results_data.items()
                if target_name and tr_data  # Skip empty entries
            ]

        return Pattern(
            id=str(data.get('id', '')),
            name=data.get('name', ''),
            formula=data.get('formula', ''),
            tier=data.get('tier', 3),
            target_name=data.get('target_name', ''),
            target_direction=target_direction,
            test_edge=data.get('test_edge') or 0.0,
            test_win_rate=data.get('test_win_rate') or 0.0,
            test_n_signals=data.get('test_n_signals') or 0,
            quality_score=data.get('quality_score') or 0.0,

            # New fields from pattern-discovery API
            timeframe=data.get('timeframe', '15m'),
            holding_period=data.get('holding_period'),
            target_magnitude=data.get('target_magnitude'),  # From API
            strategy_type=data.get('strategy_type'),
            formula_readable=data.get('formula_readable'),

            # Suggested trading parameters
            suggested_sl_type=data.get('suggested_sl_type'),
            suggested_sl_multiplier=data.get('suggested_sl_multiplier'),
            suggested_tp_type=data.get('suggested_tp_type'),
            suggested_rr_ratio=data.get('suggested_rr_ratio'),
            avg_signals_per_month=data.get('avg_signals_per_month'),

            worst_window=data.get('worst_window'),

            # Executable source code (new API fields)
            formula_source=data.get('formula_source'),
            formula_components=data.get('formula_components'),

            # Coin-specific performance data
            coin_performance=coin_performance,

            # Multi-target support
            target_results=target_results,
            original_pattern_id=None,
            is_virtual=False,
        )

    def get_stats(self) -> dict:
        """Get pattern-discovery service statistics"""
        if not self._available:
            return {}

        try:
            response = requests.get(f"{self.api_base}/patterns/stats", timeout=10)
            if response.status_code == 200:
                return response.json()
            return {}
        except requests.exceptions.RequestException:
            return {}

    def get_new_patterns_since(self, since_date: str) -> List[Pattern]:
        """
        Get patterns discovered after a specific date

        Useful for incremental pattern fetching to avoid duplicates.

        Args:
            since_date: ISO date string (e.g., '2025-01-01')

        Returns:
            List of new Pattern objects
        """
        patterns = self.fetch_production_patterns(tier=1, limit=1000)

        # Filter by discovered_date
        new_patterns = []
        for p in patterns:
            discovered = p.get('discovered_date', '')
            if discovered and discovered >= since_date:
                new_patterns.append(self._parse_pattern(p))

        logger.info(f"Found {len(new_patterns)} new patterns since {since_date}")
        return new_patterns

    def expand_pattern_to_targets(
        self,
        pattern: Pattern,
        min_edge: float = 0.05,
        max_targets: int = 5
    ) -> List[Pattern]:
        """
        Expand one pattern into multiple patterns, one per Tier 1 target.

        This allows exploiting a single pattern formula for multiple trading
        directions (long/short) and holding periods (4h/24h).

        Args:
            pattern: Base pattern with target_results
            min_edge: Minimum edge for target inclusion (default 5%)
            max_targets: Maximum number of targets to expand

        Returns:
            List of Pattern objects (virtual patterns)
        """
        if not pattern.target_results:
            return [pattern]  # No expansion possible

        # Filter Tier 1 targets with sufficient edge
        tier1_targets = [
            t for t in pattern.target_results
            if t.tier == 1 and t.edge >= min_edge
        ]

        if len(tier1_targets) <= 1:
            return [pattern]  # Only one target, no expansion needed

        # Sort by edge descending and limit
        tier1_targets = sorted(tier1_targets, key=lambda t: t.edge, reverse=True)
        tier1_targets = tier1_targets[:max_targets]

        # Create virtual pattern for each target
        virtual_patterns = []
        for target in tier1_targets:
            virtual = Pattern(
                id=f"{pattern.id}__{target.target_name}",  # Composite ID
                name=f"{pattern.name}_{target.target_name}",
                formula=pattern.formula,
                tier=pattern.tier,
                target_name=target.target_name,
                target_direction=target.direction,
                test_edge=target.edge,
                test_win_rate=target.win_rate,
                test_n_signals=target.n_signals,
                quality_score=target.quality_score or pattern.quality_score,
                timeframe=pattern.timeframe,
                holding_period=f"{target.hold_hours}h",
                target_magnitude=target.magnitude,  # Target price move in % (e.g., 2.0)
                strategy_type=pattern.strategy_type,
                formula_readable=pattern.formula_readable,
                suggested_sl_type=pattern.suggested_sl_type,
                suggested_sl_multiplier=pattern.suggested_sl_multiplier,
                suggested_tp_type=pattern.suggested_tp_type,
                suggested_rr_ratio=pattern.suggested_rr_ratio,
                avg_signals_per_month=pattern.avg_signals_per_month,
                worst_window=pattern.worst_window,
                formula_source=pattern.formula_source,
                formula_components=pattern.formula_components,
                coin_performance=pattern.coin_performance,
                target_results=pattern.target_results,
                original_pattern_id=pattern.id,
                is_virtual=True,
            )
            virtual_patterns.append(virtual)

        logger.info(
            f"Expanded pattern {pattern.name} into {len(virtual_patterns)} "
            f"virtual patterns for targets: {[t.target_name for t in tier1_targets]}"
        )

        return virtual_patterns

    def get_tier_1_patterns_expanded(
        self,
        limit: int = 10,
        min_quality_score: float = 0.75,
        expand_multi_target: bool = True,
        min_edge_for_expansion: float = 0.05,
        max_targets_per_pattern: int = 5
    ) -> List[Pattern]:
        """
        Fetch Tier 1 patterns with multi-target expansion.

        When a pattern has multiple Tier 1 targets (e.g., both LONG and SHORT),
        this method expands it into separate virtual patterns, each optimized
        for its specific target.

        Args:
            limit: Max base patterns to fetch from API
            min_quality_score: Quality threshold for base patterns
            expand_multi_target: If True, expand patterns with multiple Tier 1 targets
            min_edge_for_expansion: Minimum edge for a target to be expanded (default 5%)
            max_targets_per_pattern: Maximum targets to expand per pattern

        Returns:
            List of Pattern objects (may be more than limit if expanded)
        """
        base_patterns = self.get_tier_1_patterns(
            limit=limit,
            min_quality_score=min_quality_score
        )

        if not expand_multi_target:
            return base_patterns

        # Expand patterns with multiple Tier 1 targets
        expanded = []
        for pattern in base_patterns:
            virtual_patterns = self.expand_pattern_to_targets(
                pattern,
                min_edge=min_edge_for_expansion,
                max_targets=max_targets_per_pattern
            )
            expanded.extend(virtual_patterns)

        logger.info(
            f"Expanded {len(base_patterns)} base patterns to "
            f"{len(expanded)} total patterns (including virtual)"
        )

        return expanded
