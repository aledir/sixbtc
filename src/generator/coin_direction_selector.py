"""
Coin and Direction Selector - Centralized selection logic for all generators.

Provides two modes per generator (configurable):
1. market_regime.enabled=false (DEFAULT): Top N coins by volume + round-robin direction
2. market_regime.enabled=true: Query market_regimes for direction-aware coin selection

Usage:
    from src.generator.coin_direction_selector import CoinDirectionSelector

    selector = CoinDirectionSelector(config, 'unger')
    direction, coins = selector.select()
"""

import itertools
import threading
from typing import Optional

from src.data.coin_registry import get_coins_with_sufficient_data, get_top_coins_by_volume
from src.database import get_session, MarketRegime
from src.utils import get_logger

logger = get_logger(__name__)


class CoinDirectionSelector:
    """
    Selects coins and direction for strategy generation.

    Two modes:
    - Volume-based (default): Top N coins by volume, round-robin direction
    - Regime-based: Query market_regimes for direction-aware selection

    Round-robin cycle uses generator's supported_directions from config.
    """

    # Class-level direction cycles per generator (persist across instances)
    _direction_cycles: dict[str, itertools.cycle] = {}
    _cycle_lock = threading.Lock()

    DEFAULT_DIRECTIONS = ['LONG', 'SHORT']

    def __init__(self, config: dict, generator_name: str):
        """
        Initialize selector for a specific generator.

        Args:
            config: Application config dict
            generator_name: Name of generator (unger, pandas_ta, pattern_gen, etc.)
        """
        self.config = config
        self.generator_name = generator_name

        # Get generator-specific config
        gen_config = config.get('generation', {}).get('strategy_sources', {})
        self.generator_config = gen_config.get(generator_name, {})

        # Check if market_regime is enabled for this generator
        self.use_regime = self.generator_config.get('market_regime', {}).get('enabled', False)

        # Get supported directions from config (default: LONG, SHORT only)
        self.supported_directions = self.generator_config.get(
            'supported_directions',
            self.DEFAULT_DIRECTIONS
        )

        # Get top_coins_limit from config
        self.top_coins_limit = config['trading']['top_coins_limit']

        # Get regime config
        self.regime_config = config.get('regime', {})
        self.min_strength = self.regime_config.get('min_strength', 0.5)

        # Initialize direction cycle for this generator if not exists
        self._ensure_direction_cycle()

    def _ensure_direction_cycle(self) -> None:
        """Ensure direction cycle exists for this generator using supported_directions."""
        with self._cycle_lock:
            if self.generator_name not in self._direction_cycles:
                self._direction_cycles[self.generator_name] = itertools.cycle(self.supported_directions)
                logger.debug(
                    f"Created direction cycle for {self.generator_name}: "
                    f"{self.supported_directions}"
                )

    def _next_direction(self) -> str:
        """Get next direction from round-robin cycle."""
        with self._cycle_lock:
            return next(self._direction_cycles[self.generator_name])

    def select(
        self,
        direction_override: Optional[str] = None,
    ) -> tuple[str, list[str]]:
        """
        Select direction and coins based on config.

        Args:
            direction_override: Force specific direction (bypasses round-robin/regime)

        Returns:
            (direction, coins) tuple
        """
        if self.use_regime:
            return self._select_regime_based(direction_override)
        else:
            return self._select_volume_based(direction_override)

    def _select_volume_based(
        self,
        direction_override: Optional[str] = None,
    ) -> tuple[str, list[str]]:
        """
        Volume-based selection (default mode).

        - Coins: Top N by 24h volume with sufficient data coverage
        - Direction: Round-robin through generator's supported_directions

        NOTE: Uses get_coins_with_sufficient_data() which filters out coins
        without enough OHLCV data for backtesting (is_days + oos_days) * coverage_pct.
        Falls back to get_top_coins_by_volume() if no coins with coverage data.
        """
        # Get coins with sufficient data coverage (preferred)
        coins = get_coins_with_sufficient_data(limit=self.top_coins_limit)

        # Fallback to volume-only if data_coverage_days not populated yet
        # (first run before data_scheduler has updated coverage)
        if not coins:
            coins = get_top_coins_by_volume(self.top_coins_limit)
            if coins:
                logger.debug(
                    f"[{self.generator_name}] No coins with coverage data, "
                    f"falling back to volume-only"
                )

        if not coins:
            logger.warning(f"[{self.generator_name}] No coins from volume query")
            return 'LONG', []

        # Get direction
        if direction_override:
            direction = direction_override.upper()
        else:
            direction = self._next_direction()

        logger.debug(
            f"[{self.generator_name}] Volume-based: {len(coins)} coins "
            f"(with sufficient data), direction={direction}"
        )

        return direction, coins

    def _select_regime_based(
        self,
        direction_override: Optional[str] = None,
    ) -> tuple[str, list[str]]:
        """
        Regime-based selection.

        - Query market_regimes for direction groups
        - Select direction based on dominant regime (or override)
        - Get coins matching that direction
        """
        groups = self._get_direction_groups()

        # Filter empty groups
        non_empty = {d: coins for d, coins in groups.items() if coins}

        if not non_empty:
            # Fallback to volume-based
            logger.info(
                f"[{self.generator_name}] No regime data, falling back to volume-based"
            )
            return self._select_volume_based(direction_override)

        # If direction override, get coins for that direction
        if direction_override:
            direction = direction_override.upper()
            # Map BIDI to BOTH for regime query
            regime_dir = 'BOTH' if direction == 'BIDI' else direction
            coins = groups.get(regime_dir, [])
            if not coins:
                # Fallback: use all regime coins
                coins = list(set(
                    coin for coin_list in groups.values() for coin in coin_list
                ))
            logger.debug(
                f"[{self.generator_name}] Regime-based override: {len(coins)} coins, "
                f"direction={direction}"
            )
            return direction, coins

        # Select based on dominant regime
        direction, coins = self._select_dominant_direction(groups)

        logger.debug(
            f"[{self.generator_name}] Regime-based: {len(coins)} coins, "
            f"direction={direction}, groups: LONG={len(groups['LONG'])}, "
            f"SHORT={len(groups['SHORT'])}, BOTH={len(groups['BOTH'])}"
        )

        return direction, coins

    def _get_direction_groups(self) -> dict[str, list[str]]:
        """
        Query MarketRegime and group symbols by direction.

        Returns:
            {"LONG": [...], "SHORT": [...], "BOTH": [...]}
        """
        groups: dict[str, list[str]] = {"LONG": [], "SHORT": [], "BOTH": []}

        try:
            with get_session() as session:
                regimes = session.query(MarketRegime).filter(
                    MarketRegime.strength >= self.min_strength
                ).all()
                for r in regimes:
                    if r.direction in groups:
                        groups[r.direction].append(r.symbol)
            return groups
        except Exception as e:
            logger.warning(f"[{self.generator_name}] Failed to query direction groups: {e}")
            return groups

    def _select_dominant_direction(
        self,
        groups: dict[str, list[str]],
    ) -> tuple[str, list[str]]:
        """
        Select direction based on dominant regime with 50/50 BIDI diversity.

        Logic (from original Unger implementation):
        - Find dominant directional regime (LONG or SHORT)
        - 50% chance to use dominant, 50% to use BIDI (if available)
        """
        import random

        # Separate directional from neutral
        directional = {d: c for d, c in groups.items() if d in ('LONG', 'SHORT') and c}
        has_bidi = bool(groups.get('BOTH'))

        # If only BOTH available, use BIDI
        if not directional:
            return "BIDI", groups.get('BOTH', [])

        # Find dominant
        max_size = max(len(c) for c in directional.values())
        candidates = [d for d, c in directional.items() if len(c) == max_size]
        dominant = random.choice(candidates)

        # 50/50 split
        if has_bidi and random.random() < 0.50:
            return "BIDI", groups['BOTH']
        else:
            return dominant, groups[dominant]

    @classmethod
    def reset_cycles(cls) -> None:
        """Reset all direction cycles (for testing)."""
        with cls._cycle_lock:
            cls._direction_cycles.clear()
            logger.debug("All direction cycles reset")


def get_selector(config: dict, generator_name: str) -> CoinDirectionSelector:
    """
    Convenience function to create a selector.

    Args:
        config: Application config
        generator_name: Name of generator

    Returns:
        CoinDirectionSelector instance
    """
    return CoinDirectionSelector(config, generator_name)
