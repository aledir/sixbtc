"""
Pandas-TA Catalogs

Exports:
- Indicator registry (149 pandas_ta indicators across 8 categories)
- Condition types and templates
- Compatibility matrices
"""

from .indicators import (
    PtaIndicator,
    ALL_INDICATORS as INDICATORS,
    INDICATORS_BY_ID,
    INDICATORS_BY_CATEGORY,
    get_indicator,
    get_indicators_by_category,
    get_indicators_by_regime,
    get_indicators_by_direction,
)

from .conditions import (
    ConditionType,
    ConditionTemplate,
    INDICATOR_THRESHOLDS,
    CONDITION_TEMPLATES,
    CATEGORY_CONDITIONS,
    CONDITION_DIRECTION,
    get_condition_template,
    get_conditions_for_category,
    get_thresholds_for_indicator,
    get_direction_for_condition,
    get_opposite_threshold,
)

from .compatibility import (
    INCOMPATIBLE_PAIRS,
    RECOMMENDED_COMBOS,
    COMPATIBLE_CATEGORIES,
    INCOMPATIBLE_CATEGORIES,
    are_compatible,
    are_all_compatible,
    get_compatible_indicators,
    is_recommended_combo,
    get_recommended_partner,
    filter_by_category_compatibility,
    filter_by_direction_compatibility,
)


__all__ = [
    # Indicators
    "PtaIndicator",
    "INDICATORS",
    "INDICATORS_BY_ID",
    "INDICATORS_BY_CATEGORY",
    "get_indicator",
    "get_indicators_by_category",
    "get_indicators_by_regime",
    "get_indicators_by_direction",
    # Conditions
    "ConditionType",
    "ConditionTemplate",
    "INDICATOR_THRESHOLDS",
    "CONDITION_TEMPLATES",
    "CATEGORY_CONDITIONS",
    "CONDITION_DIRECTION",
    "get_condition_template",
    "get_conditions_for_category",
    "get_thresholds_for_indicator",
    "get_direction_for_condition",
    "get_opposite_threshold",
    # Compatibility
    "INCOMPATIBLE_PAIRS",
    "RECOMMENDED_COMBOS",
    "COMPATIBLE_CATEGORIES",
    "INCOMPATIBLE_CATEGORIES",
    "are_compatible",
    "are_all_compatible",
    "get_compatible_indicators",
    "is_recommended_combo",
    "get_recommended_partner",
    "filter_by_category_compatibility",
    "filter_by_direction_compatibility",
]
