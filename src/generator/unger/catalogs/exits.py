"""
15 Exit Conditions for dynamic position closing.

Categories:
- reversal (8): Indicator reversal signals
- time (4): Time-based exits
- profit_protection (3): Profit protection exits
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ExitCondition:
    """Definition of an exit condition."""

    id: str                                    # e.g., "EXT_01"
    name: str                                  # e.g., "RSI Extreme Exit"
    category: str                              # e.g., "reversal", "time", "profit_protection"
    logic_template: str                        # Python code
    params: dict = field(default_factory=dict)  # e.g., {"threshold": [70, 75, 80]}
    for_direction: Literal['LONG', 'SHORT', 'BOTH'] = 'BOTH'
    indicators_used: list = field(default_factory=list)


# =============================================================================
# REVERSAL EXITS (8)
# =============================================================================

REVERSAL_EXITS = [
    # EXT_01: RSI Extreme Exit (LONG)
    ExitCondition(
        id="EXT_01",
        name="RSI Extreme Long Exit",
        category="reversal",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
exit_signal = rsi.iloc[-1] > {threshold}''',
        params={"threshold": [70, 75, 80]},
        for_direction="LONG",
        indicators_used=["RSI"],
    ),
    # EXT_02: RSI Extreme Exit (SHORT)
    ExitCondition(
        id="EXT_02",
        name="RSI Extreme Short Exit",
        category="reversal",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
exit_signal = rsi.iloc[-1] < {threshold}''',
        params={"threshold": [20, 25, 30]},
        for_direction="SHORT",
        indicators_used=["RSI"],
    ),
    # EXT_03: MACD Cross Against (LONG)
    ExitCondition(
        id="EXT_03",
        name="MACD Cross Against Long",
        category="reversal",
        logic_template='''ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
macd = ema12 - ema26
signal = macd.ewm(span=9, adjust=False).mean()
exit_signal = (macd.iloc[-1] < signal.iloc[-1]) and (macd.iloc[-2] >= signal.iloc[-2])''',
        params={},
        for_direction="LONG",
        indicators_used=["MACD"],
    ),
    # EXT_04: MACD Cross Against (SHORT)
    ExitCondition(
        id="EXT_04",
        name="MACD Cross Against Short",
        category="reversal",
        logic_template='''ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
macd = ema12 - ema26
signal = macd.ewm(span=9, adjust=False).mean()
exit_signal = (macd.iloc[-1] > signal.iloc[-1]) and (macd.iloc[-2] <= signal.iloc[-2])''',
        params={},
        for_direction="SHORT",
        indicators_used=["MACD"],
    ),
    # EXT_05: Price Cross MA Against (LONG)
    ExitCondition(
        id="EXT_05",
        name="Price Cross MA Against Long",
        category="reversal",
        logic_template='''ma = df["close"].rolling({N}).mean()
exit_signal = (df["close"].iloc[-1] < ma.iloc[-1]) and (df["close"].iloc[-2] >= ma.iloc[-2])''',
        params={"N": [10, 20, 50]},
        for_direction="LONG",
        indicators_used=["MA"],
    ),
    # EXT_06: Price Cross MA Against (SHORT)
    ExitCondition(
        id="EXT_06",
        name="Price Cross MA Against Short",
        category="reversal",
        logic_template='''ma = df["close"].rolling({N}).mean()
exit_signal = (df["close"].iloc[-1] > ma.iloc[-1]) and (df["close"].iloc[-2] <= ma.iloc[-2])''',
        params={"N": [10, 20, 50]},
        for_direction="SHORT",
        indicators_used=["MA"],
    ),
    # EXT_07: Momentum Reversal (LONG)
    ExitCondition(
        id="EXT_07",
        name="Momentum Reversal Long",
        category="reversal",
        logic_template='''roc = (df["close"] - df["close"].shift(10)) / df["close"].shift(10) * 100
exit_signal = roc.iloc[-1] < 0''',
        params={},
        for_direction="LONG",
        indicators_used=["ROC"],
    ),
    # EXT_08: Momentum Reversal (SHORT)
    ExitCondition(
        id="EXT_08",
        name="Momentum Reversal Short",
        category="reversal",
        logic_template='''roc = (df["close"] - df["close"].shift(10)) / df["close"].shift(10) * 100
exit_signal = roc.iloc[-1] > 0''',
        params={},
        for_direction="SHORT",
        indicators_used=["ROC"],
    ),
]


# =============================================================================
# TIME-BASED EXITS (4)
# =============================================================================

TIME_EXITS = [
    # EXT_09: N Bars Exit
    ExitCondition(
        id="EXT_09",
        name="N Bars Exit",
        category="time",
        logic_template='exit_signal = position_bars >= {N}',
        params={"N": [5, 10, 20, 50]},
        for_direction="BOTH",
        indicators_used=[],
    ),
    # EXT_10: End of Day Exit (approximation)
    ExitCondition(
        id="EXT_10",
        name="End of Day Exit",
        category="time",
        logic_template='exit_signal = position_bars >= {N}',  # Placeholder - actual EOD logic in executor
        params={"N": [24, 48, 96]},  # bars per day depends on timeframe
        for_direction="BOTH",
        indicators_used=[],
    ),
    # EXT_11: Max Holding Period
    ExitCondition(
        id="EXT_11",
        name="Max Holding Period",
        category="time",
        logic_template='exit_signal = position_bars >= {N}',
        params={"N": [100, 200, 500]},
        for_direction="BOTH",
        indicators_used=[],
    ),
    # EXT_12: Short Holding
    ExitCondition(
        id="EXT_12",
        name="Short Holding",
        category="time",
        logic_template='exit_signal = position_bars >= {N}',
        params={"N": [3, 5, 8]},
        for_direction="BOTH",
        indicators_used=[],
    ),
]


# =============================================================================
# PROFIT PROTECTION EXITS (3)
# =============================================================================

PROFIT_PROTECTION_EXITS = [
    # EXT_13: Profit + RSI Extreme (LONG)
    ExitCondition(
        id="EXT_13",
        name="Profit RSI Extreme Long",
        category="profit_protection",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
exit_signal = rsi.iloc[-1] > 70''',
        params={},
        for_direction="LONG",
        indicators_used=["RSI"],
    ),
    # EXT_14: Profit + RSI Extreme (SHORT)
    ExitCondition(
        id="EXT_14",
        name="Profit RSI Extreme Short",
        category="profit_protection",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
exit_signal = rsi.iloc[-1] < 30''',
        params={},
        for_direction="SHORT",
        indicators_used=["RSI"],
    ),
    # EXT_15: ADX Weakening
    ExitCondition(
        id="EXT_15",
        name="ADX Weakening",
        category="profit_protection",
        logic_template='''high_diff = df["high"].diff()
low_diff = -df["low"].diff()
plus_dm = ((high_diff > low_diff) & (high_diff > 0)) * high_diff
minus_dm = ((low_diff > high_diff) & (low_diff > 0)) * low_diff
tr = (df["high"] - df["low"]).rolling(14).mean()
plus_di = 100 * plus_dm.rolling(14).mean() / (tr + 1e-10)
minus_di = 100 * minus_dm.rolling(14).mean() / (tr + 1e-10)
dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
adx = dx.rolling(14).mean()
exit_signal = (adx.iloc[-1] < adx.iloc[-5]) and (adx.iloc[-1] < 25)''',
        params={},
        for_direction="BOTH",
        indicators_used=["ADX"],
    ),
]


# =============================================================================
# MASTER LIST
# =============================================================================

EXIT_CONDITIONS: list[ExitCondition] = (
    REVERSAL_EXITS +
    TIME_EXITS +
    PROFIT_PROTECTION_EXITS
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_exits_by_category(category: str) -> list[ExitCondition]:
    """Get all exit conditions for a specific category."""
    return [e for e in EXIT_CONDITIONS if e.category == category]


def get_exits_by_direction(direction: str) -> list[ExitCondition]:
    """Get all exit conditions compatible with a direction."""
    if direction == 'BIDI':
        return EXIT_CONDITIONS
    return [e for e in EXIT_CONDITIONS if e.for_direction == direction or e.for_direction == 'BOTH']


def get_exit_by_id(exit_id: str) -> ExitCondition | None:
    """Get a specific exit condition by ID."""
    for e in EXIT_CONDITIONS:
        if e.id == exit_id:
            return e
    return None


def get_category_counts() -> dict[str, int]:
    """Get count of exit conditions per category."""
    from collections import Counter
    return dict(Counter(e.category for e in EXIT_CONDITIONS))
