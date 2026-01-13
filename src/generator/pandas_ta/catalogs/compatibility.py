"""
Indicator Compatibility Rules

Defines which indicators can be combined together:
- INCOMPATIBLE_PAIRS: Pairs that should NOT be combined (redundant)
- RECOMMENDED_COMBOS: Pairs that work well together (market logic)
- COMPATIBLE_CATEGORIES: Category-level compatibility rules
"""

from typing import Optional

from .indicators import PtaIndicator, get_indicator, INDICATORS_BY_ID


# =============================================================================
# INCOMPATIBLE PAIRS
# =============================================================================

# These indicator pairs should NOT be combined (redundant or conflicting)
INCOMPATIBLE_PAIRS = frozenset([
    # Same concept oscillators (measuring same thing)
    frozenset(["RSI", "STOCH_K"]),       # Both momentum oscillators
    frozenset(["RSI", "CCI"]),           # Both measure deviation
    frozenset(["RSI", "WILLR"]),         # Williams %R = 100 - RSI essentially
    frozenset(["RSI", "CMO"]),           # CMO is similar to RSI
    frozenset(["STOCH_K", "WILLR"]),     # Both bounded oscillators
    frozenset(["CCI", "CMO"]),           # Both deviation-based

    # Same moving average family
    frozenset(["EMA", "SMA"]),           # Same concept, different smoothing
    frozenset(["EMA", "DEMA"]),          # DEMA is double EMA
    frozenset(["EMA", "TEMA"]),          # TEMA is triple EMA
    frozenset(["DEMA", "TEMA"]),         # Same family
    frozenset(["SMA", "HMA"]),           # Both MAs
    frozenset(["EMA", "ZLMA"]),          # ZLMA is zero-lag EMA

    # Same oscillator family
    frozenset(["MACD", "PPO"]),          # PPO is MACD normalized
    frozenset(["MACD", "TRIX"]),         # Similar oscillators
    frozenset(["ROC", "MOM"]),           # MOM = ROC unnormalized

    # Same volatility concept
    frozenset(["ATR", "NATR"]),          # NATR = ATR normalized
    frozenset(["BBANDS", "KC"]),         # Both band-based

    # Same volume concept
    frozenset(["OBV", "AD"]),            # Both cumulative volume
    frozenset(["NVI", "PVI"]),           # Complementary (not redundant but correlated)
])


# =============================================================================
# RECOMMENDED COMBINATIONS
# =============================================================================

# These combinations have proven market logic
RECOMMENDED_COMBOS = {
    # Mean reversion + trend confirmation
    frozenset(["RSI", "ADX"]): {
        "regime": "REVERSAL",
        "logic": "RSI oversold + ADX confirms strong trend (not choppy)",
    },
    frozenset(["RSI", "SUPERTREND"]): {
        "regime": "REVERSAL",
        "logic": "RSI oversold + Supertrend confirms direction",
    },
    frozenset(["STOCH_K", "ADX"]): {
        "regime": "REVERSAL",
        "logic": "Stochastic oversold + trend strength",
    },
    frozenset(["CCI", "EMA"]): {
        "regime": "REVERSAL",
        "logic": "CCI extreme + price above/below EMA confirms bias",
    },

    # Trend following + momentum confirmation
    frozenset(["EMA", "ADX"]): {
        "regime": "TREND",
        "logic": "EMA cross + ADX confirms trend strength",
    },
    frozenset(["SUPERTREND", "RSI"]): {
        "regime": "TREND",
        "logic": "Supertrend bullish + RSI not overbought",
    },
    frozenset(["MACD", "ADX"]): {
        "regime": "TREND",
        "logic": "MACD cross + ADX > 25",
    },
    frozenset(["PSAR", "RSI"]): {
        "regime": "TREND",
        "logic": "PSAR direction + momentum confirmation",
    },

    # Volatility + direction
    frozenset(["BBANDS", "RSI"]): {
        "regime": "REVERSAL",
        "logic": "BB squeeze/breakout + RSI confirms extreme",
    },
    frozenset(["ATR", "EMA"]): {
        "regime": "TREND",
        "logic": "Volatility expansion + trend direction",
    },
    frozenset(["KC", "STOCH_K"]): {
        "regime": "REVERSAL",
        "logic": "Keltner bands + momentum extreme",
    },

    # Volume + price
    frozenset(["OBV", "EMA"]): {
        "regime": "TREND",
        "logic": "Volume trend + price trend alignment",
    },
    frozenset(["CMF", "RSI"]): {
        "regime": "REVERSAL",
        "logic": "Money flow + momentum extreme",
    },
    frozenset(["MFI", "BBANDS"]): {
        "regime": "REVERSAL",
        "logic": "Money flow index + Bollinger extreme",
    },

    # Triple combinations (uncommon but powerful)
    frozenset(["RSI", "ADX", "SUPERTREND"]): {
        "regime": "REVERSAL",
        "logic": "Momentum + trend strength + direction",
    },
    frozenset(["MACD", "RSI", "ADX"]): {
        "regime": "TREND",
        "logic": "Trend + momentum + strength",
    },
}


# =============================================================================
# CATEGORY COMPATIBILITY
# =============================================================================

# Which categories can be combined (for diversification)
COMPATIBLE_CATEGORIES = {
    "momentum": ["trend", "volatility", "volume", "crossover"],
    "trend": ["momentum", "volatility", "volume"],
    "crossover": ["momentum", "volatility", "volume"],
    "volatility": ["momentum", "trend", "crossover"],
    "volume": ["momentum", "trend", "crossover"],
}

# Categories that should NOT be combined (too similar)
INCOMPATIBLE_CATEGORIES = {
    frozenset(["momentum", "momentum"]),     # Two momentum = redundant
    frozenset(["trend", "crossover"]),       # Often overlapping (EMA + MACD)
}


# =============================================================================
# COMPATIBILITY FUNCTIONS
# =============================================================================

def are_compatible(ind1_id: str, ind2_id: str) -> bool:
    """
    Check if two indicators are compatible for combining.

    Returns True if they can be combined, False if they should not.
    """
    pair = frozenset([ind1_id, ind2_id])

    # Check explicit incompatibility
    if pair in INCOMPATIBLE_PAIRS:
        return False

    # Get indicators
    ind1 = INDICATORS_BY_ID.get(ind1_id)
    ind2 = INDICATORS_BY_ID.get(ind2_id)

    if not ind1 or not ind2:
        return False

    # Check category compatibility
    if ind1.category == ind2.category:
        # Same category - usually not good (redundant)
        # Exception: some categories are diverse enough
        if ind1.category in ["volatility", "volume"]:
            return True
        return False

    # Check if categories are compatible
    if ind2.category in COMPATIBLE_CATEGORIES.get(ind1.category, []):
        return True

    return False


def are_all_compatible(indicator_ids: list[str]) -> bool:
    """Check if all indicators in a list are mutually compatible."""
    for i, id1 in enumerate(indicator_ids):
        for id2 in indicator_ids[i + 1:]:
            if not are_compatible(id1, id2):
                return False
    return True


def get_compatible_indicators(indicator_id: str, available: list[PtaIndicator]) -> list[PtaIndicator]:
    """
    Get indicators that are compatible with the given indicator.

    Args:
        indicator_id: ID of the indicator to find companions for
        available: List of indicators to filter

    Returns:
        List of compatible indicators
    """
    return [ind for ind in available if are_compatible(indicator_id, ind.id)]


def is_recommended_combo(indicator_ids: list[str]) -> tuple[bool, Optional[str]]:
    """
    Check if a combination is in the recommended list.

    Returns:
        (is_recommended, regime_type or None)
    """
    combo_set = frozenset(indicator_ids)

    if combo_set in RECOMMENDED_COMBOS:
        info = RECOMMENDED_COMBOS[combo_set]
        return (True, info.get("regime"))

    return (False, None)


def get_recommended_partner(indicator_id: str) -> list[str]:
    """
    Get recommended partner indicators for a given indicator.

    Returns list of indicator IDs that form recommended combos.
    """
    partners = []

    for combo in RECOMMENDED_COMBOS.keys():
        if indicator_id in combo:
            # Get the other indicators in the combo
            others = [ind for ind in combo if ind != indicator_id]
            partners.extend(others)

    return list(set(partners))


def filter_by_category_compatibility(
    first_indicator: PtaIndicator,
    candidates: list[PtaIndicator]
) -> list[PtaIndicator]:
    """
    Filter candidates to only those with compatible categories.

    Ensures diversity by avoiding same-category indicators.
    """
    compatible_cats = COMPATIBLE_CATEGORIES.get(first_indicator.category, [])

    return [
        ind for ind in candidates
        if ind.category in compatible_cats
        and ind.id != first_indicator.id
    ]


def filter_by_direction_compatibility(
    direction: str,
    indicators: list[PtaIndicator]
) -> list[PtaIndicator]:
    """
    Filter indicators by direction compatibility.

    Args:
        direction: "LONG", "SHORT", or "BIDI"
        indicators: List to filter

    Returns:
        Indicators compatible with the direction
    """
    if direction == "BIDI":
        return indicators

    return [
        ind for ind in indicators
        if ind.direction == direction or ind.direction == "BIDI"
    ]
