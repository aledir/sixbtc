"""
Unified Strategy Type System.

All generators MUST use these 5 types. No exceptions, no fallbacks.
This module is the single source of truth for strategy categorization.
"""

from enum import Enum


class StrategyType(str, Enum):
    """
    The 5 unified strategy types.

    Every strategy in the system belongs to exactly one of these types.
    """
    TRD = "TRD"  # Trend: Breakout, Crossover, Trend-following indicators
    MOM = "MOM"  # Momentum: RSI, MACD, Stochastic, oscillators
    REV = "REV"  # Reversal: Mean reversion, oversold/overbought
    VOL = "VOL"  # Volume: OBV, CMF, MFI, KVO, volume-based
    CDL = "CDL"  # Candlestick: Engulfing, hammer, doji, patterns


# =============================================================================
# INDICATOR TO TYPE MAPPING
# =============================================================================
# Maps indicator names to their strategy type.
# Used by all generators to determine strategy type from indicators used.

INDICATOR_TO_TYPE: dict[str, StrategyType] = {
    # ----- TRD (Trend) -----
    # Breakout indicators
    "DONCHIAN": StrategyType.TRD,
    "BREAKOUT": StrategyType.TRD,
    "ATR_BREAKOUT": StrategyType.TRD,
    "RANGE": StrategyType.TRD,

    # Crossover indicators
    "MA": StrategyType.TRD,
    "EMA": StrategyType.TRD,
    "SMA": StrategyType.TRD,
    "WMA": StrategyType.TRD,
    "DEMA": StrategyType.TRD,
    "TEMA": StrategyType.TRD,
    "HMA": StrategyType.TRD,
    "ALMA": StrategyType.TRD,
    "KAMA": StrategyType.TRD,
    "FWMA": StrategyType.TRD,
    "T3": StrategyType.TRD,
    "ZLMA": StrategyType.TRD,
    "JMA": StrategyType.TRD,
    "VWAP": StrategyType.TRD,

    # Trend-following indicators
    "SUPERTREND": StrategyType.TRD,
    "PSAR": StrategyType.TRD,
    "PARABOLIC": StrategyType.TRD,
    "ICHIMOKU": StrategyType.TRD,
    "AROON": StrategyType.TRD,
    "VORTEX": StrategyType.TRD,
    "ADX": StrategyType.TRD,
    "DI": StrategyType.TRD,
    "DMI": StrategyType.TRD,
    "CHANDELIER": StrategyType.TRD,
    "CHOP": StrategyType.TRD,
    "CHOPPINESS": StrategyType.TRD,
    "TRIX": StrategyType.TRD,
    "MASS": StrategyType.TRD,
    "DPO": StrategyType.TRD,
    "KST": StrategyType.TRD,
    "PSAR": StrategyType.TRD,

    # Keltner/ATR (trend context)
    "KELT": StrategyType.TRD,
    "KELTNER": StrategyType.TRD,
    "ATR": StrategyType.TRD,

    # ----- MOM (Momentum) -----
    "RSI": StrategyType.MOM,
    "MACD": StrategyType.MOM,
    "STOCH": StrategyType.MOM,
    "STOCHASTIC": StrategyType.MOM,
    "STOCHRSI": StrategyType.MOM,
    "TSI": StrategyType.MOM,
    "FISHER": StrategyType.MOM,
    "CMO": StrategyType.MOM,
    "ROC": StrategyType.MOM,
    "MOM": StrategyType.MOM,
    "MOMENTUM": StrategyType.MOM,
    "CCI": StrategyType.MOM,
    "WILLR": StrategyType.MOM,
    "WILLIAMS": StrategyType.MOM,
    "UO": StrategyType.MOM,
    "ULTIMATE": StrategyType.MOM,
    "AO": StrategyType.MOM,
    "AWESOME": StrategyType.MOM,
    "AC": StrategyType.MOM,
    "ACCELERATOR": StrategyType.MOM,
    "PPO": StrategyType.MOM,
    "PVO": StrategyType.MOM,
    "APO": StrategyType.MOM,
    "BOP": StrategyType.MOM,
    "BALANCE": StrategyType.MOM,
    "COPPOCK": StrategyType.MOM,
    "KDJ": StrategyType.MOM,
    "QQE": StrategyType.MOM,
    "RSX": StrategyType.MOM,
    "RVGI": StrategyType.MOM,
    "SMI": StrategyType.MOM,
    "SQUEEZE": StrategyType.MOM,
    "SQUEEZE_PRO": StrategyType.MOM,
    "TRIX": StrategyType.MOM,
    "ELDER": StrategyType.MOM,
    "IMPULSE": StrategyType.MOM,

    # ----- REV (Reversal / Mean Reversion) -----
    "BB": StrategyType.REV,
    "BBANDS": StrategyType.REV,
    "BOLLINGER": StrategyType.REV,
    "ZSCORE": StrategyType.REV,
    "PERCENTILE": StrategyType.REV,
    "DEVIATION": StrategyType.REV,
    "MEAN_REVERSION": StrategyType.REV,
    "REVERSION": StrategyType.REV,

    # ----- VOL (Volume) -----
    "OBV": StrategyType.VOL,
    "CMF": StrategyType.VOL,
    "MFI": StrategyType.VOL,
    "KVO": StrategyType.VOL,
    "KLINGER": StrategyType.VOL,
    "EFI": StrategyType.VOL,
    "FORCE": StrategyType.VOL,
    "NVI": StrategyType.VOL,
    "PVI": StrategyType.VOL,
    "AOBV": StrategyType.VOL,
    "AD": StrategyType.VOL,
    "ADOSC": StrategyType.VOL,
    "VOL": StrategyType.VOL,
    "VOLUME": StrategyType.VOL,
    "VWMA": StrategyType.VOL,
    "VP": StrategyType.VOL,
    "PVT": StrategyType.VOL,
    "EMV": StrategyType.VOL,
    "EOM": StrategyType.VOL,

    # ----- CDL (Candlestick) -----
    "ENGULFING": StrategyType.CDL,
    "HAMMER": StrategyType.CDL,
    "DOJI": StrategyType.CDL,
    "MORNING_STAR": StrategyType.CDL,
    "EVENING_STAR": StrategyType.CDL,
    "THREE_WHITE": StrategyType.CDL,
    "THREE_BLACK": StrategyType.CDL,
    "SHOOTING_STAR": StrategyType.CDL,
    "HARAMI": StrategyType.CDL,
    "PIERCING": StrategyType.CDL,
    "DARK_CLOUD": StrategyType.CDL,
    "SPINNING_TOP": StrategyType.CDL,
    "MARUBOZU": StrategyType.CDL,
    "CANDLESTICK": StrategyType.CDL,
    "PATTERN": StrategyType.CDL,
    "PIN_BAR": StrategyType.CDL,
    "INSIDE_BAR": StrategyType.CDL,
    "OUTSIDE_BAR": StrategyType.CDL,
}


# =============================================================================
# CATEGORY TO TYPE MAPPING (for Unger generator)
# =============================================================================
# Maps Unger entry categories to strategy types.

CATEGORY_TO_TYPE: dict[str, StrategyType] = {
    # Trend types
    "breakout": StrategyType.TRD,
    "crossover": StrategyType.TRD,
    "trend_advanced": StrategyType.TRD,

    # Momentum types
    "threshold": StrategyType.MOM,  # RSI < 30 is momentum-based
    "momentum_advanced": StrategyType.MOM,

    # Reversal types
    "mean_reversion": StrategyType.REV,
    "volatility": StrategyType.REV,  # BB squeeze/bounce is reversal

    # Volume types
    "volume_flow": StrategyType.VOL,

    # Candlestick types
    "candlestick": StrategyType.CDL,
}


# =============================================================================
# OLD TYPE MIGRATION MAPPING
# =============================================================================
# Maps old arbitrary types to the 5 unified types.
# Used for migrating existing strategies and pattern_gen blocks.

OLD_TYPE_TO_NEW: dict[str, StrategyType] = {
    # Already correct (5 unified types)
    "TRD": StrategyType.TRD,
    "MOM": StrategyType.MOM,
    "REV": StrategyType.REV,
    "VOL": StrategyType.VOL,
    "CDL": StrategyType.CDL,

    # Unger legacy types
    "UNG": StrategyType.TRD,
    "BRK": StrategyType.TRD,

    # ----- Momentum types (oscillators, thresholds, divergences) -----
    "THR": StrategyType.MOM,  # Threshold (RSI, CCI, Stoch)
    "DIV": StrategyType.MOM,  # Divergence
    "APO": StrategyType.MOM,  # Absolute Price Oscillator
    "RSL": StrategyType.MOM,  # RSI-related
    "MEX": StrategyType.MOM,  # MACD extensions
    "PPO": StrategyType.MOM,  # Percentage Price Oscillator
    "CMO": StrategyType.MOM,  # Chande Momentum Oscillator
    "TSI": StrategyType.MOM,  # True Strength Index
    "RVI": StrategyType.MOM,  # Relative Vigor Index
    "SMI": StrategyType.MOM,  # Stochastic Momentum Index
    "ULT": StrategyType.MOM,  # Ultimate Oscillator
    "WLR": StrategyType.MOM,  # Williams %R
    "SRI": StrategyType.MOM,  # StochRSI
    "QQE": StrategyType.MOM,  # QQE
    "TVI": StrategyType.MOM,  # Trade Volume Index
    "BOP": StrategyType.MOM,  # Balance of Power
    "COP": StrategyType.MOM,  # Coppock Curve
    "PST": StrategyType.MOM,  # Price Strength
    "IMC": StrategyType.MOM,  # Impulse
    "IMP": StrategyType.MOM,  # Impulse
    "ELD": StrategyType.MOM,  # Elder
    "AWE": StrategyType.MOM,  # Awesome Oscillator
    "ACC": StrategyType.MOM,  # Accelerator

    # ----- Trend types (crossovers, trend-following, directional) -----
    "CRS": StrategyType.TRD,  # Crossover
    "MAS": StrategyType.TRD,  # MA Slope
    "DMI": StrategyType.TRD,  # DMI/ADX
    "ADX": StrategyType.TRD,  # ADX
    "SAR": StrategyType.TRD,  # Parabolic SAR
    "ICH": StrategyType.TRD,  # Ichimoku
    "ARN": StrategyType.TRD,  # Aroon
    "DON": StrategyType.TRD,  # Donchian
    "KLT": StrategyType.TRD,  # Keltner
    "TRX": StrategyType.TRD,  # TRIX
    "KST": StrategyType.TRD,  # KST
    "DPO": StrategyType.TRD,  # Detrended Price Oscillator
    "CHP": StrategyType.TRD,  # Choppiness
    "ATB": StrategyType.TRD,  # ATR-based breakout
    "CNF": StrategyType.TRD,  # Confirmation
    "CHN": StrategyType.TRD,  # Channel
    "ADV": StrategyType.TRD,  # Advanced trend
    "VTX": StrategyType.TRD,  # Vortex
    "SWG": StrategyType.TRD,  # Swing
    "HLS": StrategyType.TRD,  # Higher Lows/Lower Highs
    "HLB": StrategyType.TRD,  # High/Low breakout
    "DBL": StrategyType.TRD,  # Double patterns
    "SQZ": StrategyType.TRD,  # Squeeze

    # ----- Reversal types (mean reversion, volatility bands, statistical) -----
    "STA": StrategyType.REV,  # Statistical
    "BBW": StrategyType.REV,  # Bollinger Bands width
    "ZLM": StrategyType.REV,  # Z-score/ZLMA
    "STD": StrategyType.REV,  # Standard deviation
    "PCE": StrategyType.REV,  # Percentile
    "PCT": StrategyType.REV,  # Percentile
    "MRV": StrategyType.REV,  # Mean reversion

    # ----- Volume types -----
    "VFL": StrategyType.VOL,  # Volume flow
    "VPR": StrategyType.VOL,  # Volume price relation
    "FRC": StrategyType.VOL,  # Force Index
    "OBV": StrategyType.VOL,  # OBV
    "CMF": StrategyType.VOL,  # CMF
    "MFI": StrategyType.VOL,  # MFI
    "KLG": StrategyType.VOL,  # Klinger
    "NVI": StrategyType.VOL,  # NVI
    "PVI": StrategyType.VOL,  # PVI
    "PVT": StrategyType.VOL,  # PVT
    "ADO": StrategyType.VOL,  # A/D Oscillator
    "EMV": StrategyType.VOL,  # Ease of Movement
    "VWP": StrategyType.VOL,  # VWAP
    "VWM": StrategyType.VOL,  # VWMA
    "WAD": StrategyType.VOL,  # Williams A/D
    "HVO": StrategyType.VOL,  # High Volume

    # ----- Candlestick/Price Action types -----
    "PRC": StrategyType.CDL,  # Price action
    "GAP": StrategyType.CDL,  # Gap
    "INR": StrategyType.CDL,  # Inside bar
    "HAK": StrategyType.CDL,  # Heikin Ashi
    "PIN": StrategyType.CDL,  # Pin bar
    "ENG": StrategyType.CDL,  # Engulfing

    # ----- Pattern gen specific (need case-by-case mapping) -----
    # Filters/Range/Misc
    "FLT": StrategyType.TRD,  # Filter (mostly trend context)
    "RNG": StrategyType.REV,  # Range (mean reversion)
    "RTR": StrategyType.REV,  # Return (statistical)
    "RCM": StrategyType.REV,  # Range compression
    "RCE": StrategyType.REV,  # Range expansion
    "CNS": StrategyType.REV,  # Consolidation
    "CSZ": StrategyType.REV,  # Candle size
    "CSQ": StrategyType.REV,  # Consecutive

    # Momentum/Strength related
    "MDI": StrategyType.MOM,  # Momentum direction
    "MCH": StrategyType.MOM,  # Momentum change
    "MQU": StrategyType.MOM,  # Momentum quality
    "MBR": StrategyType.MOM,  # Momentum break
    "NRX": StrategyType.MOM,  # Narrow range X
    "DUM": StrategyType.MOM,  # Dummy/test
    "PMD": StrategyType.MOM,  # Price momentum direction
    "LNR": StrategyType.TRD,  # Linear regression
    "KAM": StrategyType.TRD,  # KAMA

    # More specialized
    "MLT": StrategyType.TRD,  # Multi-timeframe
    "MED": StrategyType.REV,  # Median
    "PEX": StrategyType.REV,  # Price extreme
    "PVE": StrategyType.VOL,  # Price-Volume extreme
    "PVL": StrategyType.VOL,  # Price-Volume
    "PRB": StrategyType.REV,  # Probability
    "PRJ": StrategyType.TRD,  # Projection
    "PRT": StrategyType.REV,  # Percentile return
    "PRO": StrategyType.TRD,  # Projection
    "SMB": StrategyType.TRD,  # Supertrend / Moving breakout
    "SER": StrategyType.REV,  # Series
    "SNT": StrategyType.TRD,  # Supertrend
    "SNR": StrategyType.TRD,  # Support/Resistance
    "SBN": StrategyType.TRD,  # Support breakout near
    "RBW": StrategyType.TRD,  # Rainbow
    "RBN": StrategyType.TRD,  # Ribbon
    "RPS": StrategyType.MOM,  # RPS
    "RRJ": StrategyType.REV,  # Return rejection
    "RVC": StrategyType.REV,  # Reversal confirmation
    "RCX": StrategyType.REV,  # Range cross
    "TMA": StrategyType.TRD,  # Triangular MA
    "TRP": StrategyType.TRD,  # Triple
    "TWR": StrategyType.TRD,  # Tower
    "TYP": StrategyType.REV,  # Typical price
    "UOE": StrategyType.MOM,  # Ultimate oscillator extreme
    "VAX": StrategyType.REV,  # Volatility extreme
    "VCX": StrategyType.VOL,  # Volume cross
    "VDY": StrategyType.VOL,  # Volume dynamics
    "VDS": StrategyType.VOL,  # Volume dispersion
    "VBK": StrategyType.VOL,  # Volume breakout
    "VLR": StrategyType.VOL,  # Volume ratio
    "VMM": StrategyType.VOL,  # Volume momentum
    "VOO": StrategyType.VOL,  # Volume oscillator
    "VRE": StrategyType.VOL,  # Volume regime
    "VRG": StrategyType.VOL,  # Volume range
    "VSQ": StrategyType.VOL,  # Volume squeeze
    "VSY": StrategyType.VOL,  # Volume sync
    "VTR": StrategyType.VOL,  # Volume trend
    "VPX": StrategyType.VOL,  # Volume price extreme
    "WCL": StrategyType.TRD,  # Weighted close
    "WVT": StrategyType.VOL,  # Weighted volume
    "WAX": StrategyType.VOL,  # Williams A/D extreme
    "ZZG": StrategyType.TRD,  # Zigzag

    # Additional codes found in pattern_gen
    "ACH": StrategyType.MOM,  # Acceleration change
    "ALM": StrategyType.TRD,  # ALMA
    "ARS": StrategyType.TRD,  # Aroon strength
    "ASI": StrategyType.TRD,  # ASI
    "AVG": StrategyType.TRD,  # Average
    "BKC": StrategyType.TRD,  # Breakout confirmation
    "BKF": StrategyType.TRD,  # Breakout filter
    "BKS": StrategyType.TRD,  # Breakout signal
    "BPX": StrategyType.TRD,  # Breakout extreme
    "BSN": StrategyType.TRD,  # Breakout near
    "BWR": StrategyType.REV,  # Bandwidth ratio
    "CDM": StrategyType.CDL,  # Candle momentum
    "CHV": StrategyType.REV,  # Chaikin volatility
    "CLX": StrategyType.TRD,  # Close extreme
    "CLP": StrategyType.TRD,  # Close position
    "CNP": StrategyType.TRD,  # Channel position
    "COG": StrategyType.TRD,  # Center of gravity
    "CRI": StrategyType.REV,  # Compression indicator
    "CYC": StrategyType.REV,  # Cycle
    "DMX": StrategyType.TRD,  # DMI extreme
    "DPT": StrategyType.TRD,  # Departure
    "DTP": StrategyType.REV,  # Deviation from typical price
    "DTV": StrategyType.REV,  # Deviation
    "DVX": StrategyType.MOM,  # Divergence extreme
    "DYM": StrategyType.MOM,  # Dynamic momentum
    "EFR": StrategyType.VOL,  # Elder force ray
    "EHL": StrategyType.TRD,  # Elder high low
    "EIM": StrategyType.MOM,  # Elder impulse
    "EMS": StrategyType.TRD,  # EMA system
    "EMX": StrategyType.TRD,  # EMA extreme
    "ETM": StrategyType.TRD,  # Entry timing
    "EXC": StrategyType.TRD,  # Extreme condition
    "EXS": StrategyType.TRD,  # Expansion
    "FSH": StrategyType.MOM,  # Fisher transform
    "GAX": StrategyType.CDL,  # Gap extreme
    "HLD": StrategyType.TRD,  # Hold
    "HMA": StrategyType.TRD,  # Hull MA
    "HPI": StrategyType.TRD,  # High price indicator
    "HRS": StrategyType.TRD,  # Hours
    "IDM": StrategyType.TRD,  # Internal direction
    "JMA": StrategyType.TRD,  # Jurik MA
    "LAG": StrategyType.TRD,  # Lag
    "LIQ": StrategyType.VOL,  # Liquidity
    "MAC": StrategyType.MOM,  # MACD
    "MCG": StrategyType.TRD,  # Moving channel
    "MDV": StrategyType.REV,  # Mean deviation
    "MFB": StrategyType.VOL,  # MFI breakout
    "MFE": StrategyType.VOL,  # MFI extreme
    "MFX": StrategyType.VOL,  # MFI cross
    "MPT": StrategyType.TRD,  # Multi-period trend
    "MRG": StrategyType.REV,  # Mean range
    "MSH": StrategyType.MOM,  # Momentum shift
    "MTF": StrategyType.TRD,  # Multi-timeframe
    "NTR": StrategyType.REV,  # N-period return
    "OCR": StrategyType.TRD,  # Oscillator
    "OCX": StrategyType.MOM,  # Oscillator cross
    "OEX": StrategyType.MOM,  # Oscillator extreme
    "OFP": StrategyType.TRD,  # Offset position
    "PAZ": StrategyType.CDL,  # Pattern zone
    "PBE": StrategyType.TRD,  # Price breakout
    "PCR": StrategyType.TRD,  # Price channel ratio
    "PDN": StrategyType.TRD,  # Price down
    "PEF": StrategyType.REV,  # Price efficiency
    "PLV": StrategyType.REV,  # Price level
    "PMM": StrategyType.MOM,  # Price momentum
    "PMO": StrategyType.MOM,  # Price momentum oscillator
    "POX": StrategyType.MOM,  # Polarized
    "PPE": StrategyType.MOM,  # PPO extreme
    "PPX": StrategyType.MOM,  # PPO cross
    "PTC": StrategyType.TRD,  # Price trend channel
    "PTR": StrategyType.TRD,  # Price trend
    "PZO": StrategyType.MOM,  # Price zone oscillator
    "RGB": StrategyType.TRD,  # Range breakout
    "RMI": StrategyType.MOM,  # RMI
    "SPK": StrategyType.VOL,  # Spike
    "SPT": StrategyType.TRD,  # Support
    "STC": StrategyType.MOM,  # Schaff trend cycle
    "STB": StrategyType.TRD,  # Stability
    "STE": StrategyType.TRD,  # Strength
    "STW": StrategyType.TRD,  # Stairway
    "SWI": StrategyType.TRD,  # Swing indicator
    "TCF": StrategyType.TRD,  # Trend confirmation filter
    "TCH": StrategyType.TRD,  # Trend channel
    "TDM": StrategyType.TRD,  # Tom DeMark
    "TEX": StrategyType.TRD,  # Trend extreme
    "TFL": StrategyType.TRD,  # Trend filter
    "THT": StrategyType.MOM,  # Threshold test
    "TIN": StrategyType.TRD,  # Trend indicator
    "TQU": StrategyType.TRD,  # Trend quality
    "TSC": StrategyType.MOM,  # TSI cross
    "TSE": StrategyType.MOM,  # TSI extreme
    "TSX": StrategyType.MOM,  # TSI cross extreme
    "VWR": StrategyType.VOL,  # VWAP ratio
}


def get_type_from_indicators(indicators: list[str]) -> StrategyType:
    """
    Determine strategy type from list of indicators used.

    Args:
        indicators: List of indicator names (e.g., ["RSI", "MA"])

    Returns:
        StrategyType based on primary indicator

    Raises:
        ValueError: If no indicators provided or all unknown
    """
    if not indicators:
        raise ValueError("No indicators provided for type determination")

    # Priority order: check each indicator until we find a match
    for indicator in indicators:
        indicator_upper = indicator.upper()
        if indicator_upper in INDICATOR_TO_TYPE:
            return INDICATOR_TO_TYPE[indicator_upper]

    # No match found - this is a bug, not a fallback situation
    raise ValueError(
        f"Cannot determine type from indicators: {indicators}. "
        f"Add mapping to INDICATOR_TO_TYPE in strategy_types.py"
    )


def get_type_from_category(category: str) -> StrategyType:
    """
    Determine strategy type from Unger entry category.

    Args:
        category: Entry category (e.g., "breakout", "crossover")

    Returns:
        StrategyType for this category

    Raises:
        ValueError: If category is unknown
    """
    if category not in CATEGORY_TO_TYPE:
        raise ValueError(
            f"Unknown category: '{category}'. "
            f"Add mapping to CATEGORY_TO_TYPE in strategy_types.py"
        )
    return CATEGORY_TO_TYPE[category]


def migrate_old_type(old_type: str) -> StrategyType:
    """
    Map old arbitrary type to new unified type.

    Args:
        old_type: Old 3-letter type code

    Returns:
        New unified StrategyType
    """
    # If already a valid new type, return it
    if old_type in [t.value for t in StrategyType]:
        return StrategyType(old_type)

    # Check migration mapping
    if old_type in OLD_TYPE_TO_NEW:
        return OLD_TYPE_TO_NEW[old_type]

    # Unknown type - use heuristics based on common patterns
    old_upper = old_type.upper()

    # Volume-related
    if any(x in old_upper for x in ["VOL", "VLM", "OBV", "CMF", "MFI", "KVO", "NVI", "PVI"]):
        return StrategyType.VOL

    # Momentum-related
    if any(x in old_upper for x in ["MOM", "RSI", "MAC", "STO", "TSI", "ROC", "CCI", "PPO", "CMO", "QQE"]):
        return StrategyType.MOM

    # Reversal-related
    if any(x in old_upper for x in ["REV", "BB", "BOL", "ZSC", "DEV"]):
        return StrategyType.REV

    # Candlestick-related
    if any(x in old_upper for x in ["CDL", "ENG", "HAM", "DOJ", "STA", "PIN", "BAR"]):
        return StrategyType.CDL

    # Default to TRD (trend) - most common type
    return StrategyType.TRD
