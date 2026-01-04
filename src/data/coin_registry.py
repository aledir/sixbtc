"""
CoinRegistry - Centralized coin management.

Single source of truth for tradable coins across all components.
Thread-safe with automatic cache invalidation.

Usage:
    from src.data.coin_registry import get_registry, get_active_pairs

    # Get active pairs
    pairs = get_active_pairs(limit=30)

    # Get coin info
    coin = get_registry().get_coin('BTC')

    # Check if tradable
    if get_registry().is_tradable('ETH'):
        ...

    # Get leverage
    max_lev = get_registry().get_max_leverage('SOL')
"""

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from src.database.connection import get_session
from src.database.models import Coin
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CoinInfo:
    """Immutable coin information."""
    symbol: str
    max_leverage: int
    volume_24h: float
    price: float
    is_active: bool
    updated_at: datetime


class CoinNotFoundError(Exception):
    """Raised when coin is not found or not tradable."""
    pass


class CoinRegistry:
    """
    Centralized coin registry with caching and validation.

    Thread-safe singleton that provides:
    - Cached coin data with automatic invalidation
    - Uniform error handling (CoinNotFoundError)
    - Volume and leverage validation
    - Pattern-aware coin filtering for strategies

    Cache invalidation happens when:
    - TTL expires (default 5 minutes)
    - Database coins.updated_at changes (PairsUpdater sync)
    """

    _instance: Optional['CoinRegistry'] = None
    _lock = threading.Lock()

    # Configuration
    CACHE_TTL_SECONDS = 300  # 5 minutes
    MIN_VOLUME_DEFAULT = 1_000_000  # $1M

    def __init__(self):
        self._cache: Dict[str, CoinInfo] = {}
        self._cache_updated_at: Optional[datetime] = None
        self._cache_lock = threading.RLock()
        self._db_updated_at: Optional[datetime] = None

    @classmethod
    def instance(cls) -> 'CoinRegistry':
        """Get singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    logger.debug("CoinRegistry singleton created")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._lock:
            cls._instance = None
            logger.debug("CoinRegistry singleton reset")

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self._cache or self._cache_updated_at is None:
            return False

        # Check TTL
        age = (datetime.now() - self._cache_updated_at).total_seconds()
        if age > self.CACHE_TTL_SECONDS:
            logger.debug(f"Cache expired (age={age:.0f}s > TTL={self.CACHE_TTL_SECONDS}s)")
            return False

        # Check DB staleness
        try:
            with get_session() as session:
                db_updated = session.query(Coin.updated_at).order_by(
                    Coin.updated_at.desc()
                ).first()
                if db_updated and db_updated[0]:
                    if self._db_updated_at is None or db_updated[0] > self._db_updated_at:
                        logger.debug(
                            f"Cache stale (DB updated: {db_updated[0]} > {self._db_updated_at})"
                        )
                        return False
        except Exception as e:
            logger.warning(f"Failed to check DB staleness: {e}")
            # If we can't check, assume cache is valid to avoid hammering DB
            return True

        return True

    def _refresh_cache(self) -> None:
        """Refresh cache from database."""
        try:
            with get_session() as session:
                coins = session.query(Coin).all()

                new_cache = {}
                for coin in coins:
                    new_cache[coin.symbol] = CoinInfo(
                        symbol=coin.symbol,
                        max_leverage=coin.max_leverage,
                        volume_24h=coin.volume_24h or 0,
                        price=coin.price or 0,
                        is_active=coin.is_active,
                        updated_at=coin.updated_at
                    )

                self._cache = new_cache
                self._cache_updated_at = datetime.now()

                # Track DB timestamp for staleness detection
                if coins:
                    timestamps = [c.updated_at for c in coins if c.updated_at]
                    if timestamps:
                        self._db_updated_at = max(timestamps)

                logger.debug(f"CoinRegistry cache refreshed: {len(new_cache)} coins")

        except Exception as e:
            logger.error(f"Failed to refresh coin cache: {e}")
            raise

    def _ensure_cache(self) -> None:
        """Ensure cache is valid, refresh if needed."""
        with self._cache_lock:
            if not self._is_cache_valid():
                self._refresh_cache()

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def get_coin(self, symbol: str, required: bool = True) -> Optional[CoinInfo]:
        """
        Get coin info by symbol.

        Args:
            symbol: Coin symbol (e.g., 'BTC')
            required: If True, raises CoinNotFoundError when not found/inactive

        Returns:
            CoinInfo or None

        Raises:
            CoinNotFoundError: If required=True and coin not found or inactive
        """
        self._ensure_cache()

        coin = self._cache.get(symbol)

        if coin is None or not coin.is_active:
            if required:
                raise CoinNotFoundError(f"Coin '{symbol}' not found or inactive")
            return None

        return coin

    def get_active_pairs(
        self,
        min_volume: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[str]:
        """
        Get active trading pairs sorted by volume descending.

        Args:
            min_volume: Minimum 24h volume in USD (default: $1M)
            limit: Maximum number of pairs to return

        Returns:
            List of symbol strings ordered by volume desc
        """
        self._ensure_cache()

        min_vol = min_volume if min_volume is not None else self.MIN_VOLUME_DEFAULT

        pairs = [
            coin for coin in self._cache.values()
            if coin.is_active and coin.volume_24h >= min_vol
        ]

        # Sort by volume descending
        pairs.sort(key=lambda c: c.volume_24h, reverse=True)

        symbols = [c.symbol for c in pairs]

        if limit:
            symbols = symbols[:limit]

        return symbols

    def get_max_leverage(self, symbol: str) -> int:
        """
        Get maximum leverage for a coin.

        Args:
            symbol: Coin symbol

        Returns:
            Max leverage

        Raises:
            CoinNotFoundError: If coin not found or inactive
        """
        coin = self.get_coin(symbol, required=True)
        return coin.max_leverage

    def get_leverage_range(self) -> tuple:
        """
        Get min/max leverage across all active coins.

        Returns:
            (min_leverage, max_leverage) tuple
        """
        self._ensure_cache()

        leverages = [
            coin.max_leverage for coin in self._cache.values()
            if coin.is_active
        ]

        if not leverages:
            logger.warning("No active coins found, using default leverage range (1, 10)")
            return (1, 10)

        return (min(leverages), max(leverages))

    def is_tradable(self, symbol: str, min_volume: Optional[float] = None) -> bool:
        """
        Check if coin is tradable (active + sufficient volume).

        Args:
            symbol: Coin symbol
            min_volume: Minimum volume (default: $1M)

        Returns:
            True if tradable, False otherwise
        """
        self._ensure_cache()

        coin = self._cache.get(symbol)
        if coin is None or not coin.is_active:
            return False

        min_vol = min_volume if min_volume is not None else self.MIN_VOLUME_DEFAULT
        return coin.volume_24h >= min_vol

    def validate_coins(
        self,
        coins: List[str],
        min_volume: Optional[float] = None
    ) -> tuple:
        """
        Validate a list of coins for trading.

        Args:
            coins: List of coin symbols to validate
            min_volume: Minimum volume threshold

        Returns:
            (valid_coins, invalid_coins) tuple
        """
        valid = []
        invalid = []

        for symbol in coins:
            if self.is_tradable(symbol, min_volume):
                valid.append(symbol)
            else:
                invalid.append(symbol)

        return valid, invalid

    def get_tradable_for_strategy(
        self,
        pattern_coins: Optional[List[str]] = None,
        backtest_pairs: Optional[List[str]] = None,
        min_volume: Optional[float] = None
    ) -> List[str]:
        """
        Get tradable pairs for a strategy with priority:
        1. pattern_coins (if provided and valid) - these have proven edge
        2. backtest_pairs (fallback) - coins used during backtest
        3. Filter to currently active/liquid coins

        Args:
            pattern_coins: Coins from pattern (high edge, ordered by edge)
            backtest_pairs: Coins used in backtest
            min_volume: Minimum volume

        Returns:
            List of tradable symbols (preserves input order)
        """
        self._ensure_cache()

        # Priority: pattern_coins > backtest_pairs
        candidates = pattern_coins if pattern_coins else backtest_pairs
        if not candidates:
            return []

        # Filter to tradable only, preserving order
        valid, invalid = self.validate_coins(candidates, min_volume)

        if invalid:
            logger.debug(
                f"Filtered out {len(invalid)} non-tradable coins: {invalid[:5]}"
                f"{'...' if len(invalid) > 5 else ''}"
            )

        return valid

    def get_delisted_coins(self, known_coins: List[str]) -> List[str]:
        """
        Find coins that were known but are no longer active.

        Useful for detecting when pattern_coins or backtest_pairs
        contain coins that have been delisted.

        Args:
            known_coins: List of previously known coin symbols

        Returns:
            List of symbols that are no longer tradable
        """
        self._ensure_cache()

        delisted = []
        for symbol in known_coins:
            if not self.is_tradable(symbol):
                delisted.append(symbol)

        return delisted

    def invalidate_cache(self) -> None:
        """Force cache invalidation (for testing or manual refresh)."""
        with self._cache_lock:
            self._cache_updated_at = None
            logger.debug("CoinRegistry cache invalidated")

    def get_all_active_coins(self) -> List[CoinInfo]:
        """
        Get all active coins as CoinInfo objects.

        Returns:
            List of CoinInfo for all active coins
        """
        self._ensure_cache()
        return [
            coin for coin in self._cache.values()
            if coin.is_active
        ]

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics for monitoring.

        Returns:
            Dict with cache stats
        """
        return {
            'total_coins': len(self._cache),
            'active_coins': len([c for c in self._cache.values() if c.is_active]),
            'cache_age_seconds': (
                (datetime.now() - self._cache_updated_at).total_seconds()
                if self._cache_updated_at else None
            ),
            'db_updated_at': self._db_updated_at,
        }


# =============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# =============================================================================
# These provide a simpler API for common operations without needing to
# call CoinRegistry.instance() explicitly.

def get_registry() -> CoinRegistry:
    """Get the singleton CoinRegistry instance."""
    return CoinRegistry.instance()


def get_active_pairs(min_volume: float = None, limit: int = None) -> List[str]:
    """
    Get active trading pairs sorted by volume.

    Convenience function - equivalent to:
        CoinRegistry.instance().get_active_pairs(...)
    """
    return get_registry().get_active_pairs(min_volume, limit)


def get_coin(symbol: str, required: bool = True) -> Optional[CoinInfo]:
    """
    Get coin info by symbol.

    Convenience function - equivalent to:
        CoinRegistry.instance().get_coin(...)
    """
    return get_registry().get_coin(symbol, required)


def get_max_leverage(symbol: str) -> int:
    """
    Get max leverage for a coin.

    Convenience function - equivalent to:
        CoinRegistry.instance().get_max_leverage(...)
    """
    return get_registry().get_max_leverage(symbol)


def is_tradable(symbol: str) -> bool:
    """
    Check if coin is tradable.

    Convenience function - equivalent to:
        CoinRegistry.instance().is_tradable(...)
    """
    return get_registry().is_tradable(symbol)
