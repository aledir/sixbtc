"""
Pandas-TA Indicator Registry

Contains 80+ indicators from pandas_ta organized by category.
Each indicator has:
- Standard parameter values (trading-sensible)
- Category for regime mapping
- Direction compatibility
- Output column patterns
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class PtaIndicator:
    """Single pandas_ta indicator definition."""

    id: str                                    # Unique ID: "RSI", "EMA", "SUPERTREND"
    name: str                                  # Human-readable: "Relative Strength Index"
    category: str                              # "momentum", "trend", "volatility", "volume"
    pandas_ta_func: str                        # Function name in pandas_ta: "rsi", "ema"
    params: dict[str, list]                    # {"length": [7, 14, 21, 28]}
    output_columns: list[str]                  # Column name patterns
    regime_type: Literal["TREND", "REVERSAL", "BOTH"]
    direction: Literal["LONG", "SHORT", "BIDI"]
    lookback: int = 50                         # Minimum bars required
    input_type: str = "close"                  # "close", "hlc", "hlcv", "ohlcv"


# =============================================================================
# MOMENTUM INDICATORS (Mean Reversion - REVERSAL regime)
# =============================================================================

MOMENTUM_INDICATORS = [
    PtaIndicator(
        id="RSI",
        name="Relative Strength Index",
        category="momentum",
        pandas_ta_func="rsi",
        params={"length": [7, 14, 21, 28]},
        output_columns=["RSI_{length}"],
        regime_type="REVERSAL",
        direction="BIDI",
        lookback=30,
        input_type="close",
    ),
    PtaIndicator(
        id="STOCH_K",
        name="Stochastic %K",
        category="momentum",
        pandas_ta_func="stoch",
        params={"k": [5, 14], "d": [3, 5], "smooth_k": [3, 5]},
        output_columns=["STOCHk_{k}_{d}_{smooth_k}", "STOCHd_{k}_{d}_{smooth_k}"],
        regime_type="REVERSAL",
        direction="BIDI",
        lookback=30,
        input_type="hlc",
    ),
    PtaIndicator(
        id="CCI",
        name="Commodity Channel Index",
        category="momentum",
        pandas_ta_func="cci",
        params={"length": [14, 20, 28]},
        output_columns=["CCI_{length}_0.015"],
        regime_type="REVERSAL",
        direction="BIDI",
        lookback=30,
        input_type="hlc",
    ),
    PtaIndicator(
        id="WILLR",
        name="Williams %R",
        category="momentum",
        pandas_ta_func="willr",
        params={"length": [14, 21, 28]},
        output_columns=["WILLR_{length}"],
        regime_type="REVERSAL",
        direction="BIDI",
        lookback=30,
        input_type="hlc",
    ),
    PtaIndicator(
        id="CMO",
        name="Chande Momentum Oscillator",
        category="momentum",
        pandas_ta_func="cmo",
        params={"length": [9, 14, 21]},
        output_columns=["CMO_{length}"],
        regime_type="REVERSAL",
        direction="BIDI",
        lookback=30,
        input_type="close",
    ),
    PtaIndicator(
        id="ROC",
        name="Rate of Change",
        category="momentum",
        pandas_ta_func="roc",
        params={"length": [9, 12, 21]},
        output_columns=["ROC_{length}"],
        regime_type="REVERSAL",
        direction="BIDI",
        lookback=30,
        input_type="close",
    ),
    PtaIndicator(
        id="MOM",
        name="Momentum",
        category="momentum",
        pandas_ta_func="mom",
        params={"length": [10, 14, 21]},
        output_columns=["MOM_{length}"],
        regime_type="REVERSAL",
        direction="BIDI",
        lookback=30,
        input_type="close",
    ),
    PtaIndicator(
        id="TSI",
        name="True Strength Index",
        category="momentum",
        pandas_ta_func="tsi",
        params={"fast": [13], "slow": [25]},
        output_columns=["TSI_{fast}_{slow}", "TSIs_{fast}_{slow}"],
        regime_type="REVERSAL",
        direction="BIDI",
        lookback=40,
        input_type="close",
    ),
    PtaIndicator(
        id="UO",
        name="Ultimate Oscillator",
        category="momentum",
        pandas_ta_func="uo",
        params={"fast": [7], "medium": [14], "slow": [28]},
        output_columns=["UO_{fast}_{medium}_{slow}"],
        regime_type="REVERSAL",
        direction="BIDI",
        lookback=40,
        input_type="hlc",
    ),
    PtaIndicator(
        id="AO",
        name="Awesome Oscillator",
        category="momentum",
        pandas_ta_func="ao",
        params={"fast": [5], "slow": [34]},
        output_columns=["AO_{fast}_{slow}"],
        regime_type="REVERSAL",
        direction="BIDI",
        lookback=40,
        input_type="hl",
    ),
    PtaIndicator(
        id="MFI",
        name="Money Flow Index",
        category="momentum",
        pandas_ta_func="mfi",
        params={"length": [14, 21]},
        output_columns=["MFI_{length}"],
        regime_type="REVERSAL",
        direction="BIDI",
        lookback=30,
        input_type="hlcv",
    ),
]


# =============================================================================
# TREND INDICATORS (Trend Following - TREND regime)
# =============================================================================

TREND_INDICATORS = [
    PtaIndicator(
        id="EMA",
        name="Exponential Moving Average",
        category="trend",
        pandas_ta_func="ema",
        params={"length": [8, 12, 20, 26, 50, 100, 200]},
        output_columns=["EMA_{length}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=200,
        input_type="close",
    ),
    PtaIndicator(
        id="SMA",
        name="Simple Moving Average",
        category="trend",
        pandas_ta_func="sma",
        params={"length": [10, 20, 50, 100, 200]},
        output_columns=["SMA_{length}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=200,
        input_type="close",
    ),
    PtaIndicator(
        id="SUPERTREND",
        name="Supertrend",
        category="trend",
        pandas_ta_func="supertrend",
        params={"length": [7, 10, 14], "multiplier": [2.0, 3.0, 4.0]},
        output_columns=["SUPERT_{length}_{multiplier}", "SUPERTd_{length}_{multiplier}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=30,
        input_type="hlc",
    ),
    PtaIndicator(
        id="PSAR",
        name="Parabolic SAR",
        category="trend",
        pandas_ta_func="psar",
        params={"af0": [0.02], "af": [0.02], "max_af": [0.2]},
        output_columns=["PSARl_{af0}_{max_af}", "PSARs_{af0}_{max_af}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=30,
        input_type="hlc",
    ),
    PtaIndicator(
        id="HMA",
        name="Hull Moving Average",
        category="trend",
        pandas_ta_func="hma",
        params={"length": [9, 14, 21, 50]},
        output_columns=["HMA_{length}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=60,
        input_type="close",
    ),
    PtaIndicator(
        id="DEMA",
        name="Double EMA",
        category="trend",
        pandas_ta_func="dema",
        params={"length": [10, 20, 50]},
        output_columns=["DEMA_{length}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=60,
        input_type="close",
    ),
    PtaIndicator(
        id="TEMA",
        name="Triple EMA",
        category="trend",
        pandas_ta_func="tema",
        params={"length": [10, 20, 50]},
        output_columns=["TEMA_{length}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=80,
        input_type="close",
    ),
    PtaIndicator(
        id="T3",
        name="T3 Moving Average",
        category="trend",
        pandas_ta_func="t3",
        params={"length": [5, 10, 20]},
        output_columns=["T3_{length}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=60,
        input_type="close",
    ),
    PtaIndicator(
        id="KAMA",
        name="Kaufman Adaptive MA",
        category="trend",
        pandas_ta_func="kama",
        params={"length": [10, 21], "fast": [2], "slow": [30]},
        output_columns=["KAMA_{length}_{fast}_{slow}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=50,
        input_type="close",
    ),
    PtaIndicator(
        id="ZLMA",
        name="Zero Lag MA",
        category="trend",
        pandas_ta_func="zlma",
        params={"length": [10, 20, 50]},
        output_columns=["ZL_EMA_{length}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=60,
        input_type="close",
    ),
]


# =============================================================================
# CROSSOVER INDICATORS (Trend Following - TREND regime)
# =============================================================================

CROSSOVER_INDICATORS = [
    PtaIndicator(
        id="MACD",
        name="MACD",
        category="crossover",
        pandas_ta_func="macd",
        params={"fast": [8, 12], "slow": [21, 26], "signal": [7, 9]},
        output_columns=["MACD_{fast}_{slow}_{signal}", "MACDh_{fast}_{slow}_{signal}", "MACDs_{fast}_{slow}_{signal}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=40,
        input_type="close",
    ),
    PtaIndicator(
        id="PPO",
        name="Percentage Price Oscillator",
        category="crossover",
        pandas_ta_func="ppo",
        params={"fast": [12], "slow": [26], "signal": [9]},
        output_columns=["PPO_{fast}_{slow}_{signal}", "PPOh_{fast}_{slow}_{signal}", "PPOs_{fast}_{slow}_{signal}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=40,
        input_type="close",
    ),
    PtaIndicator(
        id="TRIX",
        name="TRIX",
        category="crossover",
        pandas_ta_func="trix",
        params={"length": [14, 18, 30]},
        output_columns=["TRIX_{length}", "TRIXs_{length}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=50,
        input_type="close",
    ),
    PtaIndicator(
        id="ADX",
        name="Average Directional Index",
        category="crossover",
        pandas_ta_func="adx",
        params={"length": [14, 20, 25]},
        output_columns=["ADX_{length}", "DMP_{length}", "DMN_{length}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=40,
        input_type="hlc",
    ),
    PtaIndicator(
        id="AROON",
        name="Aroon",
        category="crossover",
        pandas_ta_func="aroon",
        params={"length": [14, 25]},
        output_columns=["AROOND_{length}", "AROONU_{length}", "AROONOSC_{length}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=30,
        input_type="hlc",
    ),
    PtaIndicator(
        id="DPO",
        name="Detrended Price Oscillator",
        category="crossover",
        pandas_ta_func="dpo",
        params={"length": [14, 20]},
        output_columns=["DPO_{length}"],
        regime_type="TREND",
        direction="BIDI",
        lookback=30,
        input_type="close",
    ),
]


# =============================================================================
# VOLATILITY INDICATORS (Both regimes)
# =============================================================================

VOLATILITY_INDICATORS = [
    PtaIndicator(
        id="BBANDS",
        name="Bollinger Bands",
        category="volatility",
        pandas_ta_func="bbands",
        params={"length": [10, 20], "std": [1.5, 2.0, 2.5]},
        output_columns=["BBL_{length}_{std}", "BBM_{length}_{std}", "BBU_{length}_{std}", "BBB_{length}_{std}", "BBP_{length}_{std}"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=30,
        input_type="close",
    ),
    PtaIndicator(
        id="ATR",
        name="Average True Range",
        category="volatility",
        pandas_ta_func="atr",
        params={"length": [7, 14, 21]},
        output_columns=["ATRr_{length}"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=30,
        input_type="hlc",
    ),
    PtaIndicator(
        id="NATR",
        name="Normalized ATR",
        category="volatility",
        pandas_ta_func="natr",
        params={"length": [14, 21]},
        output_columns=["NATR_{length}"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=30,
        input_type="hlc",
    ),
    PtaIndicator(
        id="KC",
        name="Keltner Channels",
        category="volatility",
        pandas_ta_func="kc",
        params={"length": [20], "scalar": [1.5, 2.0]},
        output_columns=["KCLe_{length}_{scalar}", "KCBe_{length}_{scalar}", "KCUe_{length}_{scalar}"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=30,
        input_type="hlc",
    ),
    PtaIndicator(
        id="DONCHIAN",
        name="Donchian Channels",
        category="volatility",
        pandas_ta_func="donchian",
        params={"lower_length": [20], "upper_length": [20]},
        output_columns=["DCL_{lower_length}_{upper_length}", "DCM_{lower_length}_{upper_length}", "DCU_{lower_length}_{upper_length}"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=30,
        input_type="hlc",
    ),
    PtaIndicator(
        id="MASSI",
        name="Mass Index",
        category="volatility",
        pandas_ta_func="massi",
        params={"fast": [9], "slow": [25]},
        output_columns=["MASSI_{fast}_{slow}"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=40,
        input_type="hl",
    ),
    PtaIndicator(
        id="UI",
        name="Ulcer Index",
        category="volatility",
        pandas_ta_func="ui",
        params={"length": [14, 21]},
        output_columns=["UI_{length}"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=30,
        input_type="close",
    ),
]


# =============================================================================
# VOLUME INDICATORS (Both regimes)
# =============================================================================

VOLUME_INDICATORS = [
    PtaIndicator(
        id="OBV",
        name="On Balance Volume",
        category="volume",
        pandas_ta_func="obv",
        params={},
        output_columns=["OBV"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=20,
        input_type="cv",
    ),
    PtaIndicator(
        id="AD",
        name="Accumulation/Distribution",
        category="volume",
        pandas_ta_func="ad",
        params={},
        output_columns=["AD"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=20,
        input_type="hlcv",
    ),
    PtaIndicator(
        id="ADOSC",
        name="AD Oscillator",
        category="volume",
        pandas_ta_func="adosc",
        params={"fast": [3], "slow": [10]},
        output_columns=["ADOSC_{fast}_{slow}"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=20,
        input_type="hlcv",
    ),
    PtaIndicator(
        id="CMF",
        name="Chaikin Money Flow",
        category="volume",
        pandas_ta_func="cmf",
        params={"length": [20, 21]},
        output_columns=["CMF_{length}"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=30,
        input_type="hlcv",
    ),
    PtaIndicator(
        id="EFI",
        name="Elder Force Index",
        category="volume",
        pandas_ta_func="efi",
        params={"length": [13, 21]},
        output_columns=["EFI_{length}"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=30,
        input_type="cv",
    ),
    PtaIndicator(
        id="NVI",
        name="Negative Volume Index",
        category="volume",
        pandas_ta_func="nvi",
        params={"length": [1]},
        output_columns=["NVI_{length}"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=30,
        input_type="cv",
    ),
    PtaIndicator(
        id="PVI",
        name="Positive Volume Index",
        category="volume",
        pandas_ta_func="pvi",
        params={"length": [1]},
        output_columns=["PVI_{length}"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=30,
        input_type="cv",
    ),
    PtaIndicator(
        id="VWAP",
        name="VWAP",
        category="volume",
        pandas_ta_func="vwap",
        params={},
        output_columns=["VWAP_D"],
        regime_type="BOTH",
        direction="BIDI",
        lookback=20,
        input_type="hlcv",
    ),
]


# =============================================================================
# ALL INDICATORS
# =============================================================================

ALL_INDICATORS = (
    MOMENTUM_INDICATORS
    + TREND_INDICATORS
    + CROSSOVER_INDICATORS
    + VOLATILITY_INDICATORS
    + VOLUME_INDICATORS
)

# Index by ID
INDICATORS_BY_ID = {ind.id: ind for ind in ALL_INDICATORS}

# Index by category
INDICATORS_BY_CATEGORY = {}
for ind in ALL_INDICATORS:
    if ind.category not in INDICATORS_BY_CATEGORY:
        INDICATORS_BY_CATEGORY[ind.category] = []
    INDICATORS_BY_CATEGORY[ind.category].append(ind)

# Index by regime
INDICATORS_BY_REGIME = {"TREND": [], "REVERSAL": [], "BOTH": []}
for ind in ALL_INDICATORS:
    INDICATORS_BY_REGIME[ind.regime_type].append(ind)


def get_indicator(indicator_id: str) -> PtaIndicator:
    """Get indicator by ID."""
    if indicator_id not in INDICATORS_BY_ID:
        raise ValueError(f"Unknown indicator ID: {indicator_id}")
    return INDICATORS_BY_ID[indicator_id]


def get_indicators_by_category(category: str) -> list[PtaIndicator]:
    """Get all indicators in a category."""
    return INDICATORS_BY_CATEGORY.get(category, [])


def get_indicators_by_regime(regime_type: str) -> list[PtaIndicator]:
    """Get indicators suitable for a regime type."""
    if regime_type == "MIXED":
        return ALL_INDICATORS
    # TREND includes TREND + BOTH, REVERSAL includes REVERSAL + BOTH
    both = INDICATORS_BY_REGIME.get("BOTH", [])
    specific = INDICATORS_BY_REGIME.get(regime_type, [])
    return specific + both


def get_indicators_by_direction(direction: str) -> list[PtaIndicator]:
    """Get indicators matching a direction."""
    if direction == "BIDI":
        return ALL_INDICATORS
    return [i for i in ALL_INDICATORS if i.direction == direction or i.direction == "BIDI"]


def get_all_indicator_ids() -> list[str]:
    """Get all indicator IDs."""
    return list(INDICATORS_BY_ID.keys())
