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

# Thresholds with market sense (not random values)
INDICATOR_THRESHOLDS = {
    # Momentum oscillators (0-100 scale)
    "RSI": {
        "oversold": [20, 25, 30, 35],       # LONG entry
        "overbought": [65, 70, 75, 80],     # SHORT entry
        "neutral_low": [40, 45],
        "neutral_high": [55, 60],
    },
    "STOCH_K": {
        "oversold": [15, 20, 25],
        "overbought": [75, 80, 85],
    },
    "MFI": {
        "oversold": [15, 20, 25],
        "overbought": [75, 80, 85],
    },
    "WILLR": {
        # Williams %R: -100 to 0
        "oversold": [-90, -85, -80],        # Near bottom = oversold
        "overbought": [-20, -15, -10],      # Near top = overbought
    },

    # Unbounded oscillators
    "CCI": {
        "oversold": [-150, -100, -80],
        "overbought": [80, 100, 150],
    },
    "CMO": {
        "oversold": [-50, -40, -30],
        "overbought": [30, 40, 50],
    },
    "ROC": {
        "negative": [-5, -3, -2],           # % change
        "positive": [2, 3, 5],
    },
    "MOM": {
        "negative": [-2, -1, 0],
        "positive": [0, 1, 2],
    },
    "TSI": {
        "oversold": [-25, -20, -15],
        "overbought": [15, 20, 25],
    },
    "UO": {
        "oversold": [25, 30, 35],
        "overbought": [65, 70, 75],
    },
    "AO": {
        "negative": [-100, -50, 0],
        "positive": [0, 50, 100],
    },

    # Trend strength
    "ADX": {
        "weak_trend": [15, 20],
        "strong_trend": [25, 30, 40],
    },
    "AROON": {
        # AROONOSC: -100 to 100
        "bearish": [-50, -25],
        "bullish": [25, 50],
    },

    # Bollinger Bands %B (0-1 typically, can go outside)
    "BBANDS": {
        "below_lower": [-0.1, 0, 0.1],      # Below/at lower band
        "above_upper": [0.9, 1.0, 1.1],     # Above/at upper band
        "middle_low": [0.2, 0.3],
        "middle_high": [0.7, 0.8],
    },

    # MACD (histogram crosses zero)
    "MACD": {
        "histogram_negative": [-0.5, -0.2, 0],
        "histogram_positive": [0, 0.2, 0.5],
    },

    # Supertrend direction (1 = bullish, -1 = bearish)
    "SUPERTREND": {
        "bullish": [1],
        "bearish": [-1],
    },

    # Volume indicators (typically compare to moving average)
    "CMF": {
        "outflow": [-0.2, -0.1, -0.05],
        "inflow": [0.05, 0.1, 0.2],
    },
    "EFI": {
        "negative": [-1000000, -100000, 0],
        "positive": [0, 100000, 1000000],
    },

    # Price vs MA (percentage distance)
    "PRICE_VS_MA": {
        "below": [-5, -3, -2, -1],          # % below MA
        "above": [1, 2, 3, 5],              # % above MA
    },

    # ATR-normalized distance
    "ATR_DISTANCE": {
        "close": [0.5, 1.0, 1.5],
        "far": [2.0, 2.5, 3.0],
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
