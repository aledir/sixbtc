"""
92 Entry Filters organized by category with compatibility rules.

A filter should NOT use the same indicator as the entry condition.
Filters are applied as AND conditions after the entry condition.

Categories:
- trend (8): Trend direction filters
- momentum (8): Momentum/oscillator filters
- volatility (6): Volatility-based filters
- volume (4): Volume-based filters
- structure (6): Price structure filters
- unger (60): Unger price action patterns (pure price patterns, no indicator overlap)
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .entries import EntryCondition


@dataclass
class EntryFilter:
    """Definition of an entry filter."""

    id: str                                    # e.g., "FLT_T01"
    name: str                                  # e.g., "Price Above MA"
    category: str                              # e.g., "trend", "momentum", "volatility"
    logic_template: str                        # Python code with {params}
    params: dict = field(default_factory=dict)  # e.g., {"N": [20, 50, 100]}
    indicators_used: list = field(default_factory=list)  # e.g., ["MA"]
    compatible_directions: list = field(default_factory=lambda: ["LONG", "SHORT"])


# =============================================================================
# TREND FILTERS (8)
# =============================================================================

TREND_FILTERS = [
    # FLT_T01: Price Above MA (LONG only)
    EntryFilter(
        id="FLT_T01",
        name="Price Above MA",
        category="trend",
        logic_template='filter_pass = df["close"].iloc[-1] > df["close"].rolling({N}).mean().iloc[-1]',
        params={"N": [20, 50, 100]},
        indicators_used=["MA"],
        compatible_directions=["LONG"],
    ),
    # FLT_T02: Price Below MA (SHORT only)
    EntryFilter(
        id="FLT_T02",
        name="Price Below MA",
        category="trend",
        logic_template='filter_pass = df["close"].iloc[-1] < df["close"].rolling({N}).mean().iloc[-1]',
        params={"N": [20, 50, 100]},
        indicators_used=["MA"],
        compatible_directions=["SHORT"],
    ),
    # FLT_T03: MA Slope Positive (LONG only)
    EntryFilter(
        id="FLT_T03",
        name="MA Slope Positive",
        category="trend",
        logic_template='''ma = df["close"].rolling({N}).mean()
filter_pass = ma.iloc[-1] > ma.iloc[-{slope_period}]''',
        params={"N": [20, 50], "slope_period": [3, 5]},
        indicators_used=["MA"],
        compatible_directions=["LONG"],
    ),
    # FLT_T04: MA Slope Negative (SHORT only)
    EntryFilter(
        id="FLT_T04",
        name="MA Slope Negative",
        category="trend",
        logic_template='''ma = df["close"].rolling({N}).mean()
filter_pass = ma.iloc[-1] < ma.iloc[-{slope_period}]''',
        params={"N": [20, 50], "slope_period": [3, 5]},
        indicators_used=["MA"],
        compatible_directions=["SHORT"],
    ),
    # FLT_T05: MA Stack Bullish (LONG only)
    EntryFilter(
        id="FLT_T05",
        name="MA Stack Bullish",
        category="trend",
        logic_template='''ma20 = df["close"].rolling(20).mean().iloc[-1]
ma50 = df["close"].rolling(50).mean().iloc[-1]
ma100 = df["close"].rolling(100).mean().iloc[-1]
filter_pass = (ma20 > ma50) and (ma50 > ma100)''',
        params={},
        indicators_used=["MA"],
        compatible_directions=["LONG"],
    ),
    # FLT_T06: MA Stack Bearish (SHORT only)
    EntryFilter(
        id="FLT_T06",
        name="MA Stack Bearish",
        category="trend",
        logic_template='''ma20 = df["close"].rolling(20).mean().iloc[-1]
ma50 = df["close"].rolling(50).mean().iloc[-1]
ma100 = df["close"].rolling(100).mean().iloc[-1]
filter_pass = (ma20 < ma50) and (ma50 < ma100)''',
        params={},
        indicators_used=["MA"],
        compatible_directions=["SHORT"],
    ),
    # FLT_T07: ADX Trending
    EntryFilter(
        id="FLT_T07",
        name="ADX Trending",
        category="trend",
        logic_template='''high_diff = df["high"].diff()
low_diff = -df["low"].diff()
plus_dm = ((high_diff > low_diff) & (high_diff > 0)) * high_diff
minus_dm = ((low_diff > high_diff) & (low_diff > 0)) * low_diff
tr = (df["high"] - df["low"]).rolling(14).mean()
plus_di = 100 * plus_dm.rolling(14).mean() / (tr + 1e-10)
minus_di = 100 * minus_dm.rolling(14).mean() / (tr + 1e-10)
dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
adx = dx.rolling(14).mean()
filter_pass = adx.iloc[-1] > {threshold}''',
        params={"threshold": [20, 25]},
        indicators_used=["ADX"],
        compatible_directions=["LONG", "SHORT"],
    ),
    # FLT_T08: Higher Highs Confirmed (LONG only)
    EntryFilter(
        id="FLT_T08",
        name="Higher Highs",
        category="trend",
        logic_template='''hh1 = df["high"].iloc[-1] > df["high"].iloc[-{N}:-1].max()
hh2 = df["high"].iloc[-{N}:-1].max() > df["high"].iloc[-{N}*2:-{N}].max()
filter_pass = hh1 or hh2''',
        params={"N": [5, 10]},
        indicators_used=[],
        compatible_directions=["LONG"],
    ),
]


# =============================================================================
# MOMENTUM FILTERS (8)
# =============================================================================

MOMENTUM_FILTERS = [
    # FLT_M01: RSI Neutral Zone
    EntryFilter(
        id="FLT_M01",
        name="RSI Neutral Zone",
        category="momentum",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
filter_pass = (rsi.iloc[-1] > 40) and (rsi.iloc[-1] < 60)''',
        params={},
        indicators_used=["RSI"],
        compatible_directions=["LONG", "SHORT"],
    ),
    # FLT_M02: RSI Not Oversold (LONG only)
    EntryFilter(
        id="FLT_M02",
        name="RSI Not Oversold",
        category="momentum",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
filter_pass = rsi.iloc[-1] > {threshold}''',
        params={"threshold": [30, 35]},
        indicators_used=["RSI"],
        compatible_directions=["LONG"],
    ),
    # FLT_M03: RSI Not Overbought (SHORT only)
    EntryFilter(
        id="FLT_M03",
        name="RSI Not Overbought",
        category="momentum",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
filter_pass = rsi.iloc[-1] < {threshold}''',
        params={"threshold": [65, 70]},
        indicators_used=["RSI"],
        compatible_directions=["SHORT"],
    ),
    # FLT_M04: MACD Above Zero (LONG only)
    EntryFilter(
        id="FLT_M04",
        name="MACD Above Zero",
        category="momentum",
        logic_template='''ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
macd = ema12 - ema26
filter_pass = macd.iloc[-1] > 0''',
        params={},
        indicators_used=["MACD"],
        compatible_directions=["LONG"],
    ),
    # FLT_M05: MACD Below Zero (SHORT only)
    EntryFilter(
        id="FLT_M05",
        name="MACD Below Zero",
        category="momentum",
        logic_template='''ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
macd = ema12 - ema26
filter_pass = macd.iloc[-1] < 0''',
        params={},
        indicators_used=["MACD"],
        compatible_directions=["SHORT"],
    ),
    # FLT_M06: MACD Histogram Rising (LONG only)
    EntryFilter(
        id="FLT_M06",
        name="MACD Histogram Rising",
        category="momentum",
        logic_template='''ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
macd = ema12 - ema26
signal = macd.ewm(span=9, adjust=False).mean()
hist = macd - signal
filter_pass = hist.iloc[-1] > hist.iloc[-2]''',
        params={},
        indicators_used=["MACD"],
        compatible_directions=["LONG"],
    ),
    # FLT_M07: ROC Positive (LONG only)
    EntryFilter(
        id="FLT_M07",
        name="ROC Positive",
        category="momentum",
        logic_template='''roc = (df["close"] - df["close"].shift({N})) / df["close"].shift({N}) * 100
filter_pass = roc.iloc[-1] > 0''',
        params={"N": [10, 14]},
        indicators_used=["ROC"],
        compatible_directions=["LONG"],
    ),
    # FLT_M08: ROC Negative (SHORT only)
    EntryFilter(
        id="FLT_M08",
        name="ROC Negative",
        category="momentum",
        logic_template='''roc = (df["close"] - df["close"].shift({N})) / df["close"].shift({N}) * 100
filter_pass = roc.iloc[-1] < 0''',
        params={"N": [10, 14]},
        indicators_used=["ROC"],
        compatible_directions=["SHORT"],
    ),
]


# =============================================================================
# VOLATILITY FILTERS (6)
# =============================================================================

VOLATILITY_FILTERS = [
    # FLT_V01: ATR Above Average
    EntryFilter(
        id="FLT_V01",
        name="ATR Above Average",
        category="volatility",
        logic_template='''atr = (df["high"] - df["low"]).rolling(14).mean()
atr_ma = atr.rolling(20).mean()
filter_pass = atr.iloc[-1] > atr_ma.iloc[-1]''',
        params={},
        indicators_used=["ATR"],
        compatible_directions=["LONG", "SHORT"],
    ),
    # FLT_V02: ATR Below Average
    EntryFilter(
        id="FLT_V02",
        name="ATR Below Average",
        category="volatility",
        logic_template='''atr = (df["high"] - df["low"]).rolling(14).mean()
atr_ma = atr.rolling(20).mean()
filter_pass = atr.iloc[-1] < atr_ma.iloc[-1]''',
        params={},
        indicators_used=["ATR"],
        compatible_directions=["LONG", "SHORT"],
    ),
    # FLT_V03: BB Width Expanding
    EntryFilter(
        id="FLT_V03",
        name="BB Width Expanding",
        category="volatility",
        logic_template='''std = df["close"].rolling(20).std()
ma = df["close"].rolling(20).mean()
bb_width = (4 * std) / ma
filter_pass = bb_width.iloc[-1] > bb_width.iloc[-5]''',
        params={},
        indicators_used=["BB"],
        compatible_directions=["LONG", "SHORT"],
    ),
    # FLT_V04: BB Width Narrow (Squeeze)
    EntryFilter(
        id="FLT_V04",
        name="BB Width Narrow",
        category="volatility",
        logic_template='''std = df["close"].rolling(20).std()
ma = df["close"].rolling(20).mean()
bb_width = (4 * std) / ma
percentile = bb_width.rolling(50).quantile({pct})
filter_pass = bb_width.iloc[-1] < percentile.iloc[-1]''',
        params={"pct": [0.2, 0.3]},
        indicators_used=["BB"],
        compatible_directions=["LONG", "SHORT"],
    ),
    # FLT_V05: Not Extreme Range
    EntryFilter(
        id="FLT_V05",
        name="Not Extreme Range",
        category="volatility",
        logic_template='''curr_range = df["high"].iloc[-1] - df["low"].iloc[-1]
atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
filter_pass = curr_range < atr * {mult}''',
        params={"mult": [2.0, 2.5]},
        indicators_used=["ATR"],
        compatible_directions=["LONG", "SHORT"],
    ),
    # FLT_V06: Sufficient Range
    EntryFilter(
        id="FLT_V06",
        name="Sufficient Range",
        category="volatility",
        logic_template='''curr_range = df["high"].iloc[-1] - df["low"].iloc[-1]
atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
filter_pass = curr_range > atr * {mult}''',
        params={"mult": [0.5, 0.7]},
        indicators_used=["ATR"],
        compatible_directions=["LONG", "SHORT"],
    ),
]


# =============================================================================
# VOLUME FILTERS (4)
# =============================================================================

VOLUME_FILTERS = [
    # FLT_I01: Volume Above Average
    EntryFilter(
        id="FLT_I01",
        name="Volume Above Average",
        category="volume",
        logic_template='''vol_ma = df["volume"].rolling({N}).mean()
filter_pass = df["volume"].iloc[-1] > vol_ma.iloc[-1]''',
        params={"N": [20, 50]},
        indicators_used=["VOL"],
        compatible_directions=["LONG", "SHORT"],
    ),
    # FLT_I02: Volume Spike
    EntryFilter(
        id="FLT_I02",
        name="Volume Spike",
        category="volume",
        logic_template='''vol_ma = df["volume"].rolling({N}).mean()
filter_pass = df["volume"].iloc[-1] > vol_ma.iloc[-1] * {mult}''',
        params={"N": [20], "mult": [1.5, 2.0]},
        indicators_used=["VOL"],
        compatible_directions=["LONG", "SHORT"],
    ),
    # FLT_I03: OBV Rising (LONG only)
    EntryFilter(
        id="FLT_I03",
        name="OBV Rising",
        category="volume",
        logic_template='''direction = (df["close"] > df["close"].shift(1)).astype(int) - (df["close"] < df["close"].shift(1)).astype(int)
obv = (direction * df["volume"]).cumsum()
filter_pass = obv.iloc[-1] > obv.iloc[-{N}]''',
        params={"N": [5, 10]},
        indicators_used=["OBV"],
        compatible_directions=["LONG"],
    ),
    # FLT_I04: OBV Falling (SHORT only)
    EntryFilter(
        id="FLT_I04",
        name="OBV Falling",
        category="volume",
        logic_template='''direction = (df["close"] > df["close"].shift(1)).astype(int) - (df["close"] < df["close"].shift(1)).astype(int)
obv = (direction * df["volume"]).cumsum()
filter_pass = obv.iloc[-1] < obv.iloc[-{N}]''',
        params={"N": [5, 10]},
        indicators_used=["OBV"],
        compatible_directions=["SHORT"],
    ),
]


# =============================================================================
# STRUCTURE FILTERS (6)
# =============================================================================

STRUCTURE_FILTERS = [
    # FLT_S01: Not At Resistance (LONG only)
    EntryFilter(
        id="FLT_S01",
        name="Not At Resistance",
        category="structure",
        logic_template='''recent_high = df["high"].iloc[-{N}-1:-1].max()
filter_pass = df["close"].iloc[-1] < recent_high * 0.98''',
        params={"N": [10, 20]},
        indicators_used=[],
        compatible_directions=["LONG"],
    ),
    # FLT_S02: Not At Support (SHORT only)
    EntryFilter(
        id="FLT_S02",
        name="Not At Support",
        category="structure",
        logic_template='''recent_low = df["low"].iloc[-{N}-1:-1].min()
filter_pass = df["close"].iloc[-1] > recent_low * 1.02''',
        params={"N": [10, 20]},
        indicators_used=[],
        compatible_directions=["SHORT"],
    ),
    # FLT_S03: Inside Range
    EntryFilter(
        id="FLT_S03",
        name="Inside Range",
        category="structure",
        logic_template='''recent_high = df["high"].iloc[-{N}-1:-1].max()
recent_low = df["low"].iloc[-{N}-1:-1].min()
filter_pass = (df["close"].iloc[-1] < recent_high) and (df["close"].iloc[-1] > recent_low)''',
        params={"N": [10, 20]},
        indicators_used=[],
        compatible_directions=["LONG", "SHORT"],
    ),
    # FLT_S04: Consolidation
    EntryFilter(
        id="FLT_S04",
        name="Consolidation",
        category="structure",
        logic_template='''recent_range = df["high"].iloc[-{N}:].max() - df["low"].iloc[-{N}:].min()
atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
filter_pass = recent_range < atr * {mult}''',
        params={"N": [5, 10], "mult": [2.0, 3.0]},
        indicators_used=["ATR"],
        compatible_directions=["LONG", "SHORT"],
    ),
    # FLT_S05: Pullback in Uptrend (LONG only)
    EntryFilter(
        id="FLT_S05",
        name="Pullback in Uptrend",
        category="structure",
        logic_template='''ma = df["close"].rolling({ma_period}).mean()
recent_high = df["high"].iloc[-{N}-1:-1].max()
filter_pass = (df["close"].iloc[-1] < recent_high) and (df["close"].iloc[-1] > ma.iloc[-1])''',
        params={"N": [5, 10], "ma_period": [20, 50]},
        indicators_used=["MA"],
        compatible_directions=["LONG"],
    ),
    # FLT_S06: Pullback in Downtrend (SHORT only)
    EntryFilter(
        id="FLT_S06",
        name="Pullback in Downtrend",
        category="structure",
        logic_template='''ma = df["close"].rolling({ma_period}).mean()
recent_low = df["low"].iloc[-{N}-1:-1].min()
filter_pass = (df["close"].iloc[-1] > recent_low) and (df["close"].iloc[-1] < ma.iloc[-1])''',
        params={"N": [5, 10], "ma_period": [20, 50]},
        indicators_used=["MA"],
        compatible_directions=["SHORT"],
    ),
]


# =============================================================================
# UNGER PATTERN FILTERS (60)
# Pure price action patterns from Andrea Unger's methodology.
# These have NO indicator overlap - can be combined with any entry condition.
# =============================================================================

# Pattern metadata: (pattern_num, method_name, name, direction)
_UNGER_PATTERN_DEFS = [
    # Volatility/Indecision patterns (1-3)
    (1, "pattern_01_small_bar", "Small Bar", ["LONG", "SHORT"]),
    (2, "pattern_02_small_body", "Small Body", ["LONG", "SHORT"]),
    (3, "pattern_03_narrow_range", "Narrow Range", ["LONG", "SHORT"]),
    # Directional/Range expansion patterns (4-7)
    (4, "pattern_04_range_expansion_up", "Range Expansion Up", ["LONG"]),
    (5, "pattern_05_range_expansion_down", "Range Expansion Down", ["SHORT"]),
    (6, "pattern_06_wide_range_bar", "Wide Range Bar", ["LONG", "SHORT"]),
    (7, "pattern_07_breakout_bar", "Breakout Bar", ["LONG", "SHORT"]),
    # Consecutive closes (8-9)
    (8, "pattern_08_three_up_closes", "Three Up Closes", ["LONG"]),
    (9, "pattern_09_three_down_closes", "Three Down Closes", ["SHORT"]),
    # Higher/Lower structure (10-11)
    (10, "pattern_10_higher_high_higher_low", "Higher High Higher Low", ["LONG"]),
    (11, "pattern_11_lower_high_lower_low", "Lower High Lower Low", ["SHORT"]),
    # Range dynamics (12-13)
    (12, "pattern_12_range_contraction_2bars", "Range Contraction 2 Bars", ["LONG", "SHORT"]),
    (13, "pattern_13_range_expansion_2bars", "Range Expansion 2 Bars", ["LONG", "SHORT"]),
    # Close position (14-17)
    (14, "pattern_14_close_above_open", "Close Above Open", ["LONG"]),
    (15, "pattern_15_close_below_open", "Close Below Open", ["SHORT"]),
    (16, "pattern_16_close_upper_quartile", "Close Upper Quartile", ["LONG"]),
    (17, "pattern_17_close_lower_quartile", "Close Lower Quartile", ["SHORT"]),
    # Gap patterns (18-21)
    (18, "pattern_18_gap_up", "Gap Up", ["LONG"]),
    (19, "pattern_19_gap_down", "Gap Down", ["SHORT"]),
    (20, "pattern_20_gap_filled_up", "Gap Filled Up", ["LONG", "SHORT"]),
    (21, "pattern_21_gap_filled_down", "Gap Filled Down", ["LONG", "SHORT"]),
    # Breakout (22-25)
    (22, "pattern_22_close_above_prev_high", "Close Above Prev High", ["LONG"]),
    (23, "pattern_23_close_below_prev_low", "Close Below Prev Low", ["SHORT"]),
    (24, "pattern_24_close_in_prev_range", "Close In Prev Range", ["LONG", "SHORT"]),
    (25, "pattern_25_open_in_prev_range", "Open In Prev Range", ["LONG", "SHORT"]),
    # Body analysis (26-27)
    (26, "pattern_26_body_gt_avg", "Body Greater Than Avg", ["LONG", "SHORT"]),
    (27, "pattern_27_body_lt_avg", "Body Less Than Avg", ["LONG", "SHORT"]),
    # Multi-bar breakout (28-29)
    (28, "pattern_28_high_above_prev_2", "High Above Prev 2", ["LONG"]),
    (29, "pattern_29_low_below_prev_2", "Low Below Prev 2", ["SHORT"]),
    # Close near extreme (30-31)
    (30, "pattern_30_close_near_high", "Close Near High", ["LONG"]),
    (31, "pattern_31_close_near_low", "Close Near Low", ["SHORT"]),
    # Inside/Outside (32-34)
    (32, "pattern_32_inside_bar", "Inside Bar", ["LONG", "SHORT"]),
    (33, "pattern_33_outside_bar", "Outside Bar", ["LONG", "SHORT"]),
    (34, "pattern_34_two_inside_bars", "Two Inside Bars", ["LONG", "SHORT"]),
    # Gap and go (35-36)
    (35, "pattern_35_gap_and_go_up", "Gap And Go Up", ["LONG"]),
    (36, "pattern_36_gap_and_go_down", "Gap And Go Down", ["SHORT"]),
    # Reversal bars (37-40)
    (37, "pattern_37_reversal_bar_up", "Reversal Bar Up", ["LONG"]),
    (38, "pattern_38_reversal_bar_down", "Reversal Bar Down", ["SHORT"]),
    (39, "pattern_39_thrust_up", "Thrust Up", ["LONG"]),
    (40, "pattern_40_thrust_down", "Thrust Down", ["SHORT"]),
    # Crypto 7-day (41-43)
    (41, "pattern_41_seven_day_high", "Seven Day High", ["LONG"]),
    (42, "pattern_42_seven_day_low", "Seven Day Low", ["SHORT"]),
    (43, "pattern_43_seven_day_range_breakout", "Seven Day Range Breakout", ["LONG", "SHORT"]),
    # Candlestick reversal (50-54)
    (50, "pattern_50_doji", "Doji", ["LONG", "SHORT"]),
    (51, "pattern_51_hammer", "Hammer", ["LONG"]),
    (52, "pattern_52_shooting_star", "Shooting Star", ["SHORT"]),
    (53, "pattern_53_bullish_engulfing", "Bullish Engulfing", ["LONG"]),
    (54, "pattern_54_bearish_engulfing", "Bearish Engulfing", ["SHORT"]),
    # Volume patterns (55-57)
    (55, "pattern_55_volume_spike", "Volume Spike", ["LONG", "SHORT"]),
    (56, "pattern_56_low_volume", "Low Volume", ["LONG", "SHORT"]),
    (57, "pattern_57_volume_climax", "Volume Climax", ["LONG", "SHORT"]),
    # Range patterns (58-60)
    (58, "pattern_58_nr4", "NR4", ["LONG", "SHORT"]),
    (59, "pattern_59_nr7", "NR7", ["LONG", "SHORT"]),
    (60, "pattern_60_wide_range_7", "Wide Range 7", ["LONG", "SHORT"]),
    # Advanced structure (61-66)
    (61, "pattern_61_double_inside", "Double Inside", ["LONG", "SHORT"]),
    (62, "pattern_62_pin_bar_up", "Pin Bar Up", ["LONG"]),
    (63, "pattern_63_pin_bar_down", "Pin Bar Down", ["SHORT"]),
    (64, "pattern_64_failed_breakout_up", "Failed Breakout Up", ["SHORT"]),  # Bearish signal
    (65, "pattern_65_failed_breakout_down", "Failed Breakout Down", ["LONG"]),  # Bullish signal
    (66, "pattern_66_momentum_shift", "Momentum Shift", ["LONG", "SHORT"]),
]

# Generate UNGER_PATTERN_FILTERS from definitions
UNGER_PATTERN_FILTERS = [
    EntryFilter(
        id=f"FLT_U{num:02d}",
        name=f"Unger: {name}",
        category="unger",
        logic_template=f'''from src.generator.regime.unger_patterns import UngerPatterns
filter_pass = UngerPatterns.{method}(df).iloc[-1]''',
        params={},
        indicators_used=[],  # Pure price action - no indicator overlap
        compatible_directions=directions,
    )
    for num, method, name, directions in _UNGER_PATTERN_DEFS
]


# =============================================================================
# MASTER LIST
# =============================================================================

ALL_FILTERS: list[EntryFilter] = (
    TREND_FILTERS +
    MOMENTUM_FILTERS +
    VOLATILITY_FILTERS +
    VOLUME_FILTERS +
    STRUCTURE_FILTERS +
    UNGER_PATTERN_FILTERS
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_filters_by_category(category: str) -> list[EntryFilter]:
    """Get all filters for a specific category."""
    return [f for f in ALL_FILTERS if f.category == category]


def get_compatible_filters(entry: "EntryCondition", direction: str) -> list[EntryFilter]:
    """
    Get all filters compatible with an entry condition.

    Compatibility rules:
    1. Filter cannot use the same indicator as entry
    2. Filter must be compatible with entry direction
    """
    compatible = []
    for f in ALL_FILTERS:
        # Rule 1: No same indicator
        if any(ind in entry.indicators_used for ind in f.indicators_used):
            continue
        # Rule 2: Direction compatibility
        if direction not in f.compatible_directions:
            continue
        compatible.append(f)
    return compatible


def get_filter_by_id(filter_id: str) -> EntryFilter | None:
    """Get a specific filter by ID."""
    for f in ALL_FILTERS:
        if f.id == filter_id:
            return f
    return None


def get_category_counts() -> dict[str, int]:
    """Get count of filters per category."""
    from collections import Counter
    return dict(Counter(f.category for f in ALL_FILTERS))
