"""
Helper Functions Fetcher

Fetches timeframe-specific helper functions from pattern-discovery API.
These are needed to execute pattern formula_source code.
"""

import requests
from typing import Optional, Dict
from dataclasses import dataclass
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class HelperContext:
    """Context for executing pattern formulas"""
    base_timeframe: str
    timeframe_bars: Dict[str, int]  # {"1h": 4, "4h": 16, "24h": 96}
    helper_functions: Dict[str, str]  # {"_get_rsi": "def _get_rsi(df, period=14): ..."}
    precomputed_bars: Dict[str, Dict[str, int]]  # Per-timeframe mappings
    fetched_at: datetime = None

    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.now()


class HelperFetcher:
    """
    Fetches helper functions and timeframe bar mappings from pattern-discovery API

    These are needed to execute pattern formula_source code which uses:
    - bars_24h() -> returns number of bars in 24 hours
    - bars_1h() -> returns number of bars in 1 hour
    - _get_rsi(df, period) -> RSI calculation
    - etc.

    Implements caching to avoid repeated API calls (1 hour TTL).
    """

    def __init__(self, api_url: str, cache_ttl_seconds: int = 3600):
        """
        Initialize helper fetcher

        Args:
            api_url: Base URL for pattern-discovery API
            cache_ttl_seconds: Cache TTL in seconds (default 1 hour)
        """
        self.api_url = api_url.rstrip('/')
        self.api_base = f"{self.api_url}/api/v1"
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache: Dict[str, HelperContext] = {}

    def get_helpers(self, base_timeframe: str = "15m") -> Optional[HelperContext]:
        """
        Fetch helpers for a specific base timeframe

        Uses caching to avoid hitting API repeatedly.

        Args:
            base_timeframe: The timeframe to get helpers for (e.g., "15m", "1h")

        Returns:
            HelperContext with timeframe bars and helper functions
        """
        # Check cache first
        if base_timeframe in self._cache:
            cached = self._cache[base_timeframe]
            age = datetime.now() - cached.fetched_at
            if age < self.cache_ttl:
                logger.debug(f"Using cached helpers for {base_timeframe}")
                return cached

        # Fetch from API
        try:
            response = requests.get(
                f"{self.api_base}/helpers",
                params={"base_timeframe": base_timeframe},
                timeout=10
            )

            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch helpers: {response.status_code} {response.text}"
                )
                return self._get_fallback_context(base_timeframe)

            data = response.json()

            context = HelperContext(
                base_timeframe=data.get('base_timeframe', base_timeframe),
                timeframe_bars=data.get('timeframe_bars', {}),
                helper_functions=data.get('helper_functions', {}),
                precomputed_bars=data.get('precomputed_bars', {}),
            )

            # Cache the result
            self._cache[base_timeframe] = context

            logger.info(
                f"Fetched helpers for {base_timeframe}: "
                f"{len(context.timeframe_bars)} bar mappings, "
                f"{len(context.helper_functions)} helper functions"
            )

            return context

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching helpers: {e}")
            return self._get_fallback_context(base_timeframe)

    def _get_fallback_context(self, base_timeframe: str) -> HelperContext:
        """
        Return fallback context when API is unavailable

        Provides default bar mappings for common timeframes.
        """
        # Calculate bars based on timeframe
        tf_minutes = self._parse_timeframe_minutes(base_timeframe)

        # Common period mappings (in minutes)
        periods = {
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "8h": 480,
            "12h": 720,
            "24h": 1440,
            "48h": 2880,
            "7d": 10080,
        }

        timeframe_bars = {}
        for period, minutes in periods.items():
            if tf_minutes > 0:
                timeframe_bars[period] = minutes // tf_minutes

        logger.warning(
            f"Using fallback helpers for {base_timeframe} "
            f"(API unavailable)"
        )

        return HelperContext(
            base_timeframe=base_timeframe,
            timeframe_bars=timeframe_bars,
            helper_functions={},
            precomputed_bars={base_timeframe: timeframe_bars},
        )

    def _parse_timeframe_minutes(self, timeframe: str) -> int:
        """Parse timeframe string to minutes"""
        tf = timeframe.lower().strip()

        if tf.endswith('m'):
            return int(tf[:-1])
        elif tf.endswith('h'):
            return int(tf[:-1]) * 60
        elif tf.endswith('d'):
            return int(tf[:-1]) * 1440
        else:
            return 15  # Default to 15m

    def get_bars_for_period(
        self,
        period: str,
        base_timeframe: str = "15m"
    ) -> Optional[int]:
        """
        Get number of bars for a period in a specific timeframe

        Args:
            period: Period string (e.g., "24h", "4h", "1h")
            base_timeframe: The timeframe context

        Returns:
            Number of bars, or None if not found
        """
        context = self.get_helpers(base_timeframe)
        if context is None:
            return None
        return context.timeframe_bars.get(period)

    def generate_bars_functions_code(self, base_timeframe: str = "15m") -> str:
        """
        Generate Python code for bars_* helper functions

        Returns code like:
        ```
        def bars_1h(): return 4
        def bars_4h(): return 16
        def bars_24h(): return 96
        ```
        """
        context = self.get_helpers(base_timeframe)
        if context is None:
            return "# No bar mappings available\ndef bars_24h(): return 96"

        lines = []
        for period, bars in sorted(context.timeframe_bars.items()):
            func_name = f"bars_{period}"
            lines.append(f"def {func_name}(): return {bars}")

        return "\n".join(lines) if lines else "def bars_24h(): return 96"

    def generate_helper_functions_code(self, base_timeframe: str = "15m") -> str:
        """
        Generate Python code for helper functions

        Returns the helper function definitions as a single string.
        """
        context = self.get_helpers(base_timeframe)
        if context is None or not context.helper_functions:
            return "# No helper functions available"

        lines = []
        for func_name, func_code in context.helper_functions.items():
            lines.append(func_code)
            lines.append("")  # Blank line between functions

        return "\n".join(lines).strip()

    def clear_cache(self):
        """Clear the helper cache"""
        self._cache.clear()
        logger.info("Helper cache cleared")

    def is_available(self) -> bool:
        """Check if helper API is available"""
        try:
            response = requests.get(
                f"{self.api_base}/helpers",
                params={"base_timeframe": "15m"},
                timeout=5
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
