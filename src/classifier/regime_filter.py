"""
Market Regime Filter

Filters strategies based on current market conditions.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from src.utils.logger import get_logger
from src.config.loader import load_config

logger = get_logger(__name__)


class MarketRegimeFilter:
    """
    Filters strategies based on market regime detection

    Market regimes:
    - TRENDING: Strong directional movement
    - RANGING: Sideways consolidation
    - VOLATILE: High volatility breakout
    - CALM: Low volatility compression
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize regime filter

        Args:
            config: Configuration dict
        """
        self.config = config or load_config()

        # Regime detection parameters
        self.trend_lookback = 20  # ADX period
        self.volatility_lookback = 14  # ATR period
        self.trend_threshold = 25  # ADX > 25 = trending
        self.volatility_threshold = 1.5  # ATR ratio threshold

    def detect_regime(self, price_data) -> str:
        """
        Detect current market regime

        Args:
            price_data: OHLCV DataFrame or dict with market metrics

        Returns:
            Regime string: 'trending', 'ranging', 'volatile', 'calm'
        """
        # Handle dict input (for testing/simple metrics)
        if isinstance(price_data, dict):
            trend = price_data.get('trend', 0)
            volatility = price_data.get('volatility', 0)

            # Simple classification based on dict values
            if abs(trend) > 0.05:  # Strong trend
                if volatility > 0.04:
                    regime = 'volatile'
                else:
                    regime = 'trending'
            else:
                if volatility > 0.04:
                    regime = 'volatile'
                else:
                    regime = 'ranging'

            logger.info(f"Market regime (from dict): {regime.upper()}")
            return regime

        # Handle DataFrame input (for production)
        if len(price_data) < max(self.trend_lookback, self.volatility_lookback):
            logger.warning("Insufficient data for regime detection, defaulting to ranging")
            return 'ranging'

        # Calculate trend strength (simplified ADX)
        trend_strength = self._calculate_trend_strength(price_data)

        # Calculate volatility
        volatility = self._calculate_volatility(price_data)

        # Classify regime
        if trend_strength > self.trend_threshold:
            if volatility > self.volatility_threshold:
                regime = 'volatile'
            else:
                regime = 'trending'
        else:
            if volatility > self.volatility_threshold:
                regime = 'volatile'
            else:
                regime = 'ranging'

        logger.info(
            f"Market regime: {regime.upper()} "
            f"(trend={trend_strength:.1f}, vol={volatility:.2f})"
        )

        return regime

    def filter_strategies(
        self,
        strategies: List[Dict],
        current_regime: str
    ) -> List[Dict]:
        """
        Filter strategies suitable for current market regime

        Args:
            strategies: List of strategy dicts with metadata
            current_regime: Current market regime

        Returns:
            Filtered list of strategies
        """
        filtered = []

        regime_strategy_map = {
            'trending': ['MOM', 'TRN', 'BRE'],  # Momentum, Trend, Breakout
            'ranging': ['REV', 'MR'],  # Mean Reversion, Range
            'volatile': ['BRE', 'VOL'],  # Breakout, Volatility
            'calm': ['REV', 'MR'],  # Mean Reversion
        }

        suitable_types = regime_strategy_map.get(current_regime, [])

        for strategy in strategies:
            strategy_type = strategy.get('type', 'UNKNOWN')

            # Include if strategy type matches regime
            if strategy_type in suitable_types:
                filtered.append(strategy)
                logger.debug(f"Included {strategy.get('name')} for {current_regime} regime")

        logger.info(
            f"Filtered {len(filtered)}/{len(strategies)} strategies "
            f"for {current_regime} regime"
        )

        return filtered

    def filter_for_regime(self, strategies: List[Dict], regime: str) -> List[Dict]:
        """
        Alias for filter_strategies for backwards compatibility

        Args:
            strategies: List of strategy dicts with metadata
            regime: Current market regime

        Returns:
            Filtered list of strategies
        """
        return self.filter_strategies(strategies, regime)

    def _calculate_trend_strength(self, df: pd.DataFrame) -> float:
        """
        Calculate trend strength (simplified ADX)

        Args:
            df: OHLCV DataFrame

        Returns:
            Trend strength value (0-100)
        """
        # Simplified directional movement
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values

        # Calculate price changes
        delta_close = np.diff(close)

        # Use absolute value of changes as trend proxy
        trend_strength = np.mean(np.abs(delta_close[-self.trend_lookback:])) / np.mean(close[-self.trend_lookback:]) * 100

        return float(trend_strength * 100)  # Scale to 0-100

    def _calculate_volatility(self, df: pd.DataFrame) -> float:
        """
        Calculate relative volatility

        Args:
            df: OHLCV DataFrame

        Returns:
            Volatility ratio (current / historical)
        """
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values

        # True Range
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - np.roll(close, 1)),
                np.abs(low - np.roll(close, 1))
            )
        )

        # ATR
        recent_atr = np.mean(tr[-self.volatility_lookback:])
        historical_atr = np.mean(tr[-self.volatility_lookback*3:-self.volatility_lookback])

        if historical_atr == 0:
            return 1.0

        volatility_ratio = recent_atr / historical_atr

        return float(volatility_ratio)

    def get_regime_metrics(self, price_data: pd.DataFrame) -> Dict:
        """
        Get detailed regime metrics

        Args:
            price_data: OHLCV DataFrame

        Returns:
            Dict with regime metrics
        """
        regime = self.detect_regime(price_data)
        trend = self._calculate_trend_strength(price_data)
        volatility = self._calculate_volatility(price_data)

        return {
            'regime': regime,
            'trend_strength': trend,
            'volatility_ratio': volatility,
            'timestamp': datetime.now().isoformat(),
        }
