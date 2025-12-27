"""
Pattern Discovery API Client

Fetches validated trading patterns from the pattern-discovery service.
Patterns are used as building blocks for AI-generated strategies.
"""

import requests
from typing import Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


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
    strategy_type: Optional[str] = None  # MOM, REV, TRN, BRE, VOL
    formula_readable: Optional[str] = None  # Human-readable formula

    # Suggested trading parameters
    suggested_sl_type: Optional[str] = None  # ATR, PERCENTAGE, etc.
    suggested_sl_multiplier: Optional[float] = None
    suggested_tp_type: Optional[str] = None
    suggested_rr_ratio: Optional[float] = None
    avg_signals_per_month: Optional[float] = None

    worst_window: Optional[float] = None  # Minimum edge across windows


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

    def _check_connection(self) -> bool:
        """Check if pattern-discovery API is accessible"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"Pattern Discovery API connected: {self.api_url}")
                return True
            else:
                logger.warning(
                    f"Pattern Discovery API returned status {response.status_code}"
                )
                return False
        except Exception as e:
            logger.warning(f"Pattern Discovery API not accessible: {e}")
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
            strategy_type=data.get('strategy_type'),
            formula_readable=data.get('formula_readable'),

            # Suggested trading parameters
            suggested_sl_type=data.get('suggested_sl_type'),
            suggested_sl_multiplier=data.get('suggested_sl_multiplier'),
            suggested_tp_type=data.get('suggested_tp_type'),
            suggested_rr_ratio=data.get('suggested_rr_ratio'),
            avg_signals_per_month=data.get('avg_signals_per_month'),

            worst_window=data.get('worst_window')
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
