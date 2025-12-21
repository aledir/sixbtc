"""
Pattern Discovery API Client

Fetches validated trading patterns from the pattern-discovery service.
Patterns are used as building blocks for AI-generated strategies.
"""

import requests
from typing import Optional
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
    target_direction: str  # 'long' or 'short'
    test_edge: float  # Edge percentage
    test_win_rate: float  # Win rate (0-1)
    test_sharpe: float
    test_trades: int
    quality_score: float


class PatternFetcher:
    """
    Client for pattern-discovery API

    Fetches validated Tier 1 patterns to use in strategy generation.
    """

    def __init__(self, api_url: str = "http://localhost:8001"):
        """
        Initialize pattern fetcher

        Args:
            api_url: Base URL for pattern-discovery API
        """
        self.api_url = api_url.rstrip('/')
        self._check_connection()

    def _check_connection(self):
        """Check if pattern-discovery API is accessible"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"Pattern Discovery API connected: {self.api_url}")
            else:
                logger.warning(
                    f"Pattern Discovery API returned status {response.status_code}"
                )
        except Exception as e:
            # Catch all exceptions including mocked ones in tests
            logger.warning(f"Pattern Discovery API not accessible: {e}")
            logger.warning("Strategy generation will use custom AI logic only")

    def fetch_top_patterns(
        self,
        tier: int = 1,
        limit: int = 10,
        min_edge: float = 0.03,
        timeframe: Optional[str] = None
    ) -> list[dict]:
        """
        Fetch top patterns from pattern-discovery

        Args:
            tier: Pattern tier (1 = highest quality)
            limit: Maximum number of patterns to return
            min_edge: Minimum edge threshold
            timeframe: Filter by timeframe (e.g., '15m', '1h')

        Returns:
            List of pattern dicts
        """
        try:
            params = {
                'tier': tier,
                'limit': limit,
                'min_edge': min_edge
            }

            if timeframe:
                params['timeframe'] = timeframe

            response = requests.get(
                f"{self.api_url}/patterns",
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

            # Filter by min_edge
            patterns = [p for p in patterns if p.get('performance', {}).get('edge', 0) >= min_edge]

            logger.info(f"Fetched {len(patterns)} Tier {tier} patterns")
            return patterns

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching patterns: {e}")
            return []

    def fetch_by_type(
        self,
        pattern_type: str,
        tier: int = 1,
        limit: int = 10
    ) -> list[dict]:
        """
        Fetch patterns by type

        Args:
            pattern_type: Pattern type (e.g., 'MOM', 'REV', 'TRN')
            tier: Pattern tier (1 = highest quality)
            limit: Maximum number of patterns to return

        Returns:
            List of pattern dicts
        """
        try:
            params = {
                'tier': tier,
                'type': pattern_type,
                'limit': limit
            }

            response = requests.get(
                f"{self.api_url}/patterns",
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

            logger.info(f"Fetched {len(patterns)} {pattern_type} patterns")
            return patterns

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching patterns: {e}")
            raise

    def get_tier_1_patterns(
        self,
        timeframe: Optional[str] = None,
        limit: int = 10,
        min_quality_score: float = 0.75
    ) -> list[Pattern]:
        """
        Fetch Tier 1 patterns from pattern-discovery

        Args:
            timeframe: Filter by timeframe (e.g., '15m', '1h')
            limit: Maximum number of patterns to return
            min_quality_score: Minimum quality score (0-1)

        Returns:
            List of Pattern objects
        """
        try:
            params = {
                'tier': 1,
                'limit': limit,
                'min_quality_score': min_quality_score
            }

            if timeframe:
                params['timeframe'] = timeframe

            response = requests.get(
                f"{self.api_url}/patterns",
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch patterns: {response.status_code} {response.text}"
                )
                return []

            data = response.json()
            patterns = [self._parse_pattern(p) for p in data.get('patterns', [])]

            logger.info(f"Fetched {len(patterns)} Tier 1 patterns")
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
        try:
            response = requests.get(
                f"{self.api_url}/patterns/{pattern_id}",
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
        return Pattern(
            id=data['id'],
            name=data['name'],
            formula=data['formula'],
            tier=data['tier'],
            target_direction=data['target_direction'],
            test_edge=data['test_edge'],
            test_win_rate=data['test_win_rate'],
            test_sharpe=data['test_sharpe'],
            test_trades=data['test_trades'],
            quality_score=data['quality_score']
        )

    def get_stats(self) -> dict:
        """Get pattern-discovery service statistics"""
        try:
            response = requests.get(f"{self.api_url}/stats", timeout=10)
            if response.status_code == 200:
                return response.json()
            return {}
        except requests.exceptions.RequestException:
            return {}
