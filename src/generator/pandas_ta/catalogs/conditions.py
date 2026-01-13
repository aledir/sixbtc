"""
Entry Condition Types

Defines how indicators can be used as entry conditions:
- Threshold: indicator < value, indicator > value
- Crossover: indicator crosses above/below value or another indicator
- Between: value1 < indicator < value2
- Slope: indicator rising/falling
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class ConditionType(Enum):
    """Types of conditions that can be applied to indicators."""

    THRESHOLD_BELOW = "threshold_below"      # indicator < value (e.g., RSI < 30)
    THRESHOLD_ABOVE = "threshold_above"      # indicator > value (e.g., RSI > 70)
    CROSSED_ABOVE = "crossed_above"          # indicator crossed above value
    CROSSED_BELOW = "crossed_below"          # indicator crossed below value
    BETWEEN = "between"                      # low < indicator < high
    SLOPE_UP = "slope_up"                    # indicator is rising
    SLOPE_DOWN = "slope_down"                # indicator is falling


@dataclass
class ConditionTemplate:
    """
    Template for generating condition code.

    Contains:
    - The condition type
    - Thresholds applicable to specific indicators
    - Code template for vectorized and point-in-time logic
    """

    condition_type: ConditionType
    direction: Literal["LONG", "SHORT", "BIDI"]
    strategy_type: str                       # "THR", "CRS", "MOM", "VOL", etc.

    # Template for vectorized logic (calculate_indicators)
    vectorized_template: str

    # Template for point-in-time logic (generate_signal)
    point_template: str


# =============================================================================
# STANDARD THRESHOLDS FOR INDICATORS
# =============================================================================

# Thresholds with market sense - EXPANDED with extreme values
# Philosophy: let backtest decide what works, explore all possibilities
INDICATOR_THRESHOLDS = {
    # ==========================================================================
    # MOMENTUM OSCILLATORS (0-100 scale)
    # ==========================================================================
    "RSI": {
        "oversold": [5, 10, 15, 20, 25, 30, 35, 40],      # Extreme to mild
        "overbought": [60, 65, 70, 75, 80, 85, 90, 95],   # Mild to extreme
        "neutral_low": [40, 45, 48],
        "neutral_high": [52, 55, 60],
    },
    "STOCH_K": {
        "oversold": [5, 10, 15, 20, 25, 30],
        "overbought": [70, 75, 80, 85, 90, 95],
    },
    "MFI": {
        "oversold": [5, 10, 15, 20, 25, 30],
        "overbought": [70, 75, 80, 85, 90, 95],
    },
    "WILLR": {
        # Williams %R: -100 to 0
        "oversold": [-99, -95, -90, -85, -80, -75],       # Near bottom = oversold
        "overbought": [-25, -20, -15, -10, -5, -1],       # Near top = overbought
    },
    "UO": {
        # Ultimate Oscillator: 0-100
        "oversold": [15, 20, 25, 30, 35],
        "overbought": [65, 70, 75, 80, 85],
    },

    # ==========================================================================
    # UNBOUNDED OSCILLATORS
    # ==========================================================================
    "CCI": {
        "oversold": [-250, -200, -150, -100, -80, -50],
        "overbought": [50, 80, 100, 150, 200, 250],
    },
    "CMO": {
        # Chande Momentum: -100 to 100
        "oversold": [-70, -60, -50, -40, -30, -20],
        "overbought": [20, 30, 40, 50, 60, 70],
    },
    "ROC": {
        # Rate of Change: % change
        "negative": [-10, -7, -5, -3, -2, -1],
        "positive": [1, 2, 3, 5, 7, 10],
    },
    "MOM": {
        # Momentum: unbounded
        "negative": [-5, -3, -2, -1, 0],
        "positive": [0, 1, 2, 3, 5],
    },
    "TSI": {
        # True Strength Index: -100 to 100
        "oversold": [-40, -35, -30, -25, -20, -15, -10],
        "overbought": [10, 15, 20, 25, 30, 35, 40],
    },
    "AO": {
        # Awesome Oscillator: unbounded
        "negative": [-200, -150, -100, -50, 0],
        "positive": [0, 50, 100, 150, 200],
    },
    "PPO": {
        # Percentage Price Oscillator: unbounded %
        "negative": [-3, -2, -1.5, -1, -0.5, 0],
        "positive": [0, 0.5, 1, 1.5, 2, 3],
    },
    "TRIX": {
        # TRIX: unbounded small values
        "negative": [-0.3, -0.2, -0.1, -0.05, 0],
        "positive": [0, 0.05, 0.1, 0.2, 0.3],
    },
    "DPO": {
        # Detrended Price Oscillator: unbounded
        "negative": [-5, -3, -2, -1, 0],
        "positive": [0, 1, 2, 3, 5],
    },

    # ==========================================================================
    # TREND STRENGTH
    # ==========================================================================
    "ADX": {
        "weak_trend": [10, 15, 20],
        "strong_trend": [25, 30, 35, 40, 50],
    },
    "AROON": {
        # AROONOSC: -100 to 100
        "bearish": [-80, -60, -50, -40, -25],
        "bullish": [25, 40, 50, 60, 80],
    },

    # ==========================================================================
    # BOLLINGER BANDS
    # ==========================================================================
    "BBANDS": {
        "below_lower": [-0.2, -0.1, 0, 0.05, 0.1],        # Below/at lower band
        "above_upper": [0.9, 0.95, 1.0, 1.1, 1.2],        # Above/at upper band
        "middle_low": [0.15, 0.2, 0.25, 0.3, 0.35],
        "middle_high": [0.65, 0.7, 0.75, 0.8, 0.85],
    },

    # ==========================================================================
    # MACD
    # ==========================================================================
    "MACD": {
        "histogram_negative": [-1, -0.5, -0.3, -0.2, -0.1, 0],
        "histogram_positive": [0, 0.1, 0.2, 0.3, 0.5, 1],
    },

    # ==========================================================================
    # TREND FOLLOWING
    # ==========================================================================
    "SUPERTREND": {
        "bullish": [1],
        "bearish": [-1],
    },
    "PSAR": {
        # PSAR: slope indicates direction change
        "bullish": [1],
        "bearish": [-1],
    },

    # ==========================================================================
    # VOLATILITY
    # ==========================================================================
    "ATR": {
        # ATR as % of price (normalized)
        "low_vol": [0.5, 1.0, 1.5, 2.0],
        "high_vol": [3.0, 4.0, 5.0, 6.0],
    },
    "NATR": {
        # Normalized ATR: % of price
        "low_vol": [0.5, 1.0, 1.5, 2.0],
        "high_vol": [3.0, 4.0, 5.0, 6.0],
    },
    "KC": {
        # Keltner %B similar to BB %B
        "below_lower": [-0.1, 0, 0.1],
        "above_upper": [0.9, 1.0, 1.1],
    },
    "DONCHIAN": {
        # Donchian %B
        "below_lower": [0, 0.1, 0.2],
        "above_upper": [0.8, 0.9, 1.0],
    },
    "MASSI": {
        # Mass Index
        "squeeze": [21, 25, 26],
        "expansion": [27, 28, 30],
    },
    "UI": {
        # Ulcer Index: lower is better
        "low": [1, 2, 3, 4],
        "high": [6, 8, 10, 15],
    },

    # ==========================================================================
    # VOLUME INDICATORS
    # ==========================================================================
    "CMF": {
        "outflow": [-0.3, -0.25, -0.2, -0.15, -0.1, -0.05],
        "inflow": [0.05, 0.1, 0.15, 0.2, 0.25, 0.3],
    },
    "EFI": {
        # Elder Force Index: volume-weighted price change
        "negative": [-2000000, -1000000, -500000, -100000, 0],
        "positive": [0, 100000, 500000, 1000000, 2000000],
    },
    "OBV": {
        # OBV: slope matters more than absolute value
        "slope": [0],  # Cross zero
    },
    "AD": {
        # A/D Line: slope matters
        "slope": [0],
    },
    "ADOSC": {
        # A/D Oscillator
        "negative": [-1000000, -500000, -100000, 0],
        "positive": [0, 100000, 500000, 1000000],
    },
    "NVI": {
        # Negative Volume Index: slope
        "slope": [0],
    },
    "PVI": {
        # Positive Volume Index: slope
        "slope": [0],
    },
    "VWAP": {
        # VWAP: price vs VWAP
        "below": [-3, -2, -1, -0.5],  # % below
        "above": [0.5, 1, 2, 3],      # % above
    },

    # ==========================================================================
    # MOVING AVERAGES (price distance)
    # ==========================================================================
    "EMA": {
        "below": [-5, -3, -2, -1, -0.5],    # % below MA
        "above": [0.5, 1, 2, 3, 5],         # % above MA
    },
    "SMA": {
        "below": [-5, -3, -2, -1, -0.5],
        "above": [0.5, 1, 2, 3, 5],
    },
    "HMA": {
        "below": [-5, -3, -2, -1, -0.5],
        "above": [0.5, 1, 2, 3, 5],
    },
    "DEMA": {
        "below": [-5, -3, -2, -1, -0.5],
        "above": [0.5, 1, 2, 3, 5],
    },
    "TEMA": {
        "below": [-5, -3, -2, -1, -0.5],
        "above": [0.5, 1, 2, 3, 5],
    },
    "T3": {
        "below": [-5, -3, -2, -1, -0.5],
        "above": [0.5, 1, 2, 3, 5],
    },
    "KAMA": {
        "below": [-5, -3, -2, -1, -0.5],
        "above": [0.5, 1, 2, 3, 5],
    },
    "ZLMA": {
        "below": [-5, -3, -2, -1, -0.5],
        "above": [0.5, 1, 2, 3, 5],
    },

    # ==========================================================================
    # PRICE VS MA (generic)
    # ==========================================================================
    "PRICE_VS_MA": {
        "below": [-7, -5, -3, -2, -1, -0.5],
        "above": [0.5, 1, 2, 3, 5, 7],
    },

    # ==========================================================================
    # ATR-NORMALIZED DISTANCE
    # ==========================================================================
    "ATR_DISTANCE": {
        "close": [0.3, 0.5, 0.75, 1.0, 1.5],
        "far": [2.0, 2.5, 3.0, 4.0, 5.0],
    },

    # ==========================================================================
    # NEW MOMENTUM INDICATORS
    # ==========================================================================
    "APO": {
        "negative": [-3, -2, -1.5, -1, -0.5, 0],
        "positive": [0, 0.5, 1, 1.5, 2, 3],
    },
    "BIAS": {
        "negative": [-5, -3, -2, -1],
        "positive": [1, 2, 3, 5],
    },
    "BOP": {
        # Balance of Power: -1 to 1
        "negative": [-0.8, -0.6, -0.4, -0.2],
        "positive": [0.2, 0.4, 0.6, 0.8],
    },
    "CFO": {
        "negative": [-20, -15, -10, -5, 0],
        "positive": [0, 5, 10, 15, 20],
    },
    "CG": {
        "negative": [-2, -1.5, -1, -0.5, 0],
        "positive": [0, 0.5, 1, 1.5, 2],
    },
    "COPPOCK": {
        "negative": [-100, -50, -25, 0],
        "positive": [0, 25, 50, 100],
    },
    "CTI": {
        # Correlation Trend Indicator: -1 to 1
        "negative": [-0.8, -0.6, -0.4, -0.2],
        "positive": [0.2, 0.4, 0.6, 0.8],
    },
    "ER": {
        # Efficiency Ratio: 0 to 1
        "low": [0.1, 0.2, 0.3],
        "high": [0.5, 0.6, 0.7, 0.8],
    },
    "FISHER": {
        "negative": [-2, -1.5, -1, -0.5],
        "positive": [0.5, 1, 1.5, 2],
    },
    "INERTIA": {
        "oversold": [20, 30, 40],
        "overbought": [60, 70, 80],
    },
    "KDJ": {
        "oversold": [10, 20, 30],
        "overbought": [70, 80, 90],
    },
    "KST": {
        "negative": [-20, -10, -5, 0],
        "positive": [0, 5, 10, 20],
    },
    "PGO": {
        "negative": [-3, -2, -1, 0],
        "positive": [0, 1, 2, 3],
    },
    "PSL": {
        # Psychological Line: 0-100
        "oversold": [20, 30, 40],
        "overbought": [60, 70, 80],
    },
    "QQE": {
        "oversold": [20, 30],
        "overbought": [70, 80],
    },
    "RSX": {
        # Similar to RSI: 0-100
        "oversold": [10, 20, 30],
        "overbought": [70, 80, 90],
    },
    "RVGI": {
        "negative": [-0.5, -0.3, -0.1, 0],
        "positive": [0, 0.1, 0.3, 0.5],
    },
    "SLOPE": {
        "negative": [-1, -0.5, -0.2, 0],
        "positive": [0, 0.2, 0.5, 1],
    },
    "SMI": {
        # Stochastic Momentum Index: -100 to 100
        "oversold": [-60, -50, -40, -30],
        "overbought": [30, 40, 50, 60],
    },
    "SQUEEZE": {
        # Squeeze values around zero
        "negative": [-1, -0.5, -0.2, 0],
        "positive": [0, 0.2, 0.5, 1],
    },
    "SQUEEZE_PRO": {
        "negative": [-1, -0.5, -0.2, 0],
        "positive": [0, 0.2, 0.5, 1],
    },
    "STC": {
        # Schaff Trend Cycle: 0-100
        "oversold": [10, 20, 25],
        "overbought": [75, 80, 90],
    },
    "STOCHRSI": {
        # Stochastic RSI: 0-100
        "oversold": [5, 10, 15, 20],
        "overbought": [80, 85, 90, 95],
    },
    "TMO": {
        "negative": [-10, -5, 0],
        "positive": [0, 5, 10],
    },

    # ==========================================================================
    # NEW TREND INDICATORS
    # ==========================================================================
    "CHOP": {
        # Choppiness Index: 0-100, high = choppy, low = trending
        "trending": [30, 38, 40],
        "choppy": [55, 60, 62],
    },
    "VORTEX": {
        # Vortex: crossover around 1.0
        "negative": [0.8, 0.9, 1.0],
        "positive": [1.0, 1.1, 1.2],
    },
    "VHF": {
        # Vertical Horizontal Filter
        "low": [0.2, 0.3, 0.35],
        "high": [0.4, 0.5, 0.6],
    },

    # ==========================================================================
    # NEW VOLATILITY INDICATORS
    # ==========================================================================
    "RVI": {
        # Relative Volatility Index: 0-100
        "low_vol": [30, 40, 50],
        "high_vol": [60, 70, 80],
    },
    "ABERRATION": {
        "negative": [-2, -1, 0],
        "positive": [0, 1, 2],
    },
    "THERMO": {
        "low": [0.5, 1, 1.5],
        "high": [2, 2.5, 3],
    },

    # ==========================================================================
    # NEW VOLUME INDICATORS
    # ==========================================================================
    "EOM": {
        "negative": [-100, -50, 0],
        "positive": [0, 50, 100],
    },
    "KVO": {
        "negative": [-1000000, -500000, 0],
        "positive": [0, 500000, 1000000],
    },
    "PVO": {
        "negative": [-10, -5, -2, 0],
        "positive": [0, 2, 5, 10],
    },

    # ==========================================================================
    # STATISTICS INDICATORS
    # ==========================================================================
    "ZSCORE": {
        "oversold": [-3, -2.5, -2, -1.5],
        "overbought": [1.5, 2, 2.5, 3],
    },
    "ENTROPY": {
        "low": [0.3, 0.4, 0.5],
        "high": [0.7, 0.8, 0.9],
    },
    "SKEW": {
        "negative": [-2, -1.5, -1, -0.5],
        "positive": [0.5, 1, 1.5, 2],
    },
    "KURTOSIS": {
        "low": [0, 1, 2],
        "high": [4, 5, 6],
    },

    # ==========================================================================
    # CYCLE INDICATORS
    # ==========================================================================
    "EBSW": {
        "negative": [-0.8, -0.5, -0.3],
        "positive": [0.3, 0.5, 0.8],
    },

    # ==========================================================================
    # CANDLE PATTERNS
    # Candle patterns return 100 (bullish), -100 (bearish), or 0 (no pattern)
    # ==========================================================================
    "CANDLE": {
        "bullish": [100],    # Pattern detected = 100
        "bearish": [-100],   # Pattern detected = -100
    },
}


# =============================================================================
# CONDITION TEMPLATES
# =============================================================================

CONDITION_TEMPLATES = {
    ConditionType.THRESHOLD_BELOW: ConditionTemplate(
        condition_type=ConditionType.THRESHOLD_BELOW,
        direction="LONG",  # Below threshold often signals LONG (oversold)
        strategy_type="THR",
        vectorized_template="df['{col}'] < {threshold}",
        point_template="df['{col}'].iloc[-1] < {threshold}",
    ),
    ConditionType.THRESHOLD_ABOVE: ConditionTemplate(
        condition_type=ConditionType.THRESHOLD_ABOVE,
        direction="SHORT",  # Above threshold often signals SHORT (overbought)
        strategy_type="THR",
        vectorized_template="df['{col}'] > {threshold}",
        point_template="df['{col}'].iloc[-1] > {threshold}",
    ),
    ConditionType.CROSSED_ABOVE: ConditionTemplate(
        condition_type=ConditionType.CROSSED_ABOVE,
        direction="LONG",
        strategy_type="CRS",
        vectorized_template="(df['{col}'] > {threshold}) & (df['{col}'].shift(1) <= {threshold})",
        point_template="(df['{col}'].iloc[-1] > {threshold}) and (df['{col}'].iloc[-2] <= {threshold})",
    ),
    ConditionType.CROSSED_BELOW: ConditionTemplate(
        condition_type=ConditionType.CROSSED_BELOW,
        direction="SHORT",
        strategy_type="CRS",
        vectorized_template="(df['{col}'] < {threshold}) & (df['{col}'].shift(1) >= {threshold})",
        point_template="(df['{col}'].iloc[-1] < {threshold}) and (df['{col}'].iloc[-2] >= {threshold})",
    ),
    ConditionType.BETWEEN: ConditionTemplate(
        condition_type=ConditionType.BETWEEN,
        direction="BIDI",
        strategy_type="THR",
        vectorized_template="(df['{col}'] > {low}) & (df['{col}'] < {high})",
        point_template="({low} < df['{col}'].iloc[-1] < {high})",
    ),
    ConditionType.SLOPE_UP: ConditionTemplate(
        condition_type=ConditionType.SLOPE_UP,
        direction="LONG",
        strategy_type="MOM",
        vectorized_template="df['{col}'] > df['{col}'].shift(1)",
        point_template="df['{col}'].iloc[-1] > df['{col}'].iloc[-2]",
    ),
    ConditionType.SLOPE_DOWN: ConditionTemplate(
        condition_type=ConditionType.SLOPE_DOWN,
        direction="SHORT",
        strategy_type="MOM",
        vectorized_template="df['{col}'] < df['{col}'].shift(1)",
        point_template="df['{col}'].iloc[-1] < df['{col}'].iloc[-2]",
    ),
}


# =============================================================================
# CONDITION MAPPING PER INDICATOR CATEGORY
# =============================================================================

# Which condition types make sense for each indicator category
CATEGORY_CONDITIONS = {
    "momentum": [
        ConditionType.THRESHOLD_BELOW,
        ConditionType.THRESHOLD_ABOVE,
        ConditionType.CROSSED_ABOVE,
        ConditionType.CROSSED_BELOW,
    ],
    "trend": [
        ConditionType.CROSSED_ABOVE,
        ConditionType.CROSSED_BELOW,
        ConditionType.SLOPE_UP,
        ConditionType.SLOPE_DOWN,
    ],
    "crossover": [
        ConditionType.THRESHOLD_ABOVE,    # e.g., ADX > 25
        ConditionType.CROSSED_ABOVE,
        ConditionType.CROSSED_BELOW,
    ],
    "volatility": [
        ConditionType.THRESHOLD_BELOW,    # ATR squeeze
        ConditionType.THRESHOLD_ABOVE,    # ATR expansion
        ConditionType.BETWEEN,            # BB %B between values
    ],
    "volume": [
        ConditionType.THRESHOLD_ABOVE,
        ConditionType.THRESHOLD_BELOW,
        ConditionType.SLOPE_UP,
        ConditionType.SLOPE_DOWN,
    ],
    "statistics": [
        ConditionType.THRESHOLD_BELOW,    # Z-score < -2 = oversold
        ConditionType.THRESHOLD_ABOVE,    # Z-score > 2 = overbought
        ConditionType.CROSSED_ABOVE,
        ConditionType.CROSSED_BELOW,
    ],
    "cycle": [
        ConditionType.THRESHOLD_BELOW,
        ConditionType.THRESHOLD_ABOVE,
        ConditionType.CROSSED_ABOVE,
        ConditionType.CROSSED_BELOW,
    ],
    "candle": [
        ConditionType.THRESHOLD_ABOVE,    # Pattern detected = 100
        ConditionType.THRESHOLD_BELOW,    # Pattern detected = -100
    ],
}


# =============================================================================
# DIRECTION MAPPING
# =============================================================================

# Map condition type + indicator behavior to trade direction
CONDITION_DIRECTION = {
    # Momentum - threshold below = oversold = LONG
    ("momentum", ConditionType.THRESHOLD_BELOW): "LONG",
    ("momentum", ConditionType.THRESHOLD_ABOVE): "SHORT",
    ("momentum", ConditionType.CROSSED_ABOVE): "LONG",
    ("momentum", ConditionType.CROSSED_BELOW): "SHORT",

    # Trend - cross up = bullish = LONG
    ("trend", ConditionType.CROSSED_ABOVE): "LONG",
    ("trend", ConditionType.CROSSED_BELOW): "SHORT",
    ("trend", ConditionType.SLOPE_UP): "LONG",
    ("trend", ConditionType.SLOPE_DOWN): "SHORT",

    # Crossover - same as trend
    ("crossover", ConditionType.THRESHOLD_ABOVE): "LONG",  # ADX > 25 confirms trend
    ("crossover", ConditionType.CROSSED_ABOVE): "LONG",
    ("crossover", ConditionType.CROSSED_BELOW): "SHORT",

    # Volatility - can go either way
    ("volatility", ConditionType.THRESHOLD_BELOW): "BIDI",
    ("volatility", ConditionType.THRESHOLD_ABOVE): "BIDI",
    ("volatility", ConditionType.BETWEEN): "BIDI",

    # Volume - positive flow = LONG
    ("volume", ConditionType.THRESHOLD_ABOVE): "LONG",
    ("volume", ConditionType.THRESHOLD_BELOW): "SHORT",
    ("volume", ConditionType.SLOPE_UP): "LONG",
    ("volume", ConditionType.SLOPE_DOWN): "SHORT",

    # Statistics - similar to momentum (mean reversion)
    ("statistics", ConditionType.THRESHOLD_BELOW): "LONG",  # Z-score < -2 = oversold
    ("statistics", ConditionType.THRESHOLD_ABOVE): "SHORT",  # Z-score > 2 = overbought
    ("statistics", ConditionType.CROSSED_ABOVE): "LONG",
    ("statistics", ConditionType.CROSSED_BELOW): "SHORT",

    # Cycle - similar to momentum
    ("cycle", ConditionType.THRESHOLD_BELOW): "LONG",
    ("cycle", ConditionType.THRESHOLD_ABOVE): "SHORT",
    ("cycle", ConditionType.CROSSED_ABOVE): "LONG",
    ("cycle", ConditionType.CROSSED_BELOW): "SHORT",

    # Candle - pattern detection
    ("candle", ConditionType.THRESHOLD_ABOVE): "LONG",   # Bullish pattern = 100
    ("candle", ConditionType.THRESHOLD_BELOW): "SHORT",  # Bearish pattern = -100
}


def get_condition_template(condition_type: ConditionType) -> ConditionTemplate:
    """Get the template for a condition type."""
    return CONDITION_TEMPLATES[condition_type]


def get_conditions_for_category(category: str) -> list[ConditionType]:
    """Get valid condition types for an indicator category."""
    return CATEGORY_CONDITIONS.get(category, [ConditionType.THRESHOLD_ABOVE])


def get_thresholds_for_indicator(indicator_id: str, condition_type: ConditionType) -> list:
    """
    Get threshold values for an indicator and condition type.

    Returns list of valid threshold values based on indicator and condition.
    """
    thresholds = INDICATOR_THRESHOLDS.get(indicator_id, {})

    if condition_type == ConditionType.THRESHOLD_BELOW:
        # Use oversold/negative thresholds
        return thresholds.get("oversold", thresholds.get("negative", [30]))
    elif condition_type == ConditionType.THRESHOLD_ABOVE:
        # Use overbought/positive thresholds
        return thresholds.get("overbought", thresholds.get("positive", [70]))
    elif condition_type in (ConditionType.CROSSED_ABOVE, ConditionType.CROSSED_BELOW):
        # Use neutral values or zero
        neutral = thresholds.get("neutral_low", []) + thresholds.get("neutral_high", [])
        if neutral:
            return neutral
        # Default to 0 for crossover (common for MACD, etc.)
        return [0]
    else:
        # Default
        return [0]


def get_direction_for_condition(category: str, condition_type: ConditionType) -> str:
    """Get trade direction for a category + condition combination."""
    return CONDITION_DIRECTION.get((category, condition_type), "BIDI")
