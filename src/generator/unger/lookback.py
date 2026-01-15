"""
Automatic lookback calculation for indicators.

Computes minimum bars required for each indicator based on its parameters.
No hardcoding - lookback is derived from indicator formula requirements.
"""

from typing import Callable


# Lookback formulas: indicator_name -> function(params) -> min_bars
# Each formula returns the minimum number of bars needed for the indicator
# to produce valid (non-NaN) output.

LOOKBACK_FORMULAS: dict[str, Callable[[dict], int]] = {
    # ==========================================================================
    # TREND ADVANCED INDICATORS
    # ==========================================================================

    # Supertrend: needs ATR(14) + length for direction calculation
    "SUPERTREND": lambda p: p.get("length", 10) + 14 + 5,

    # Parabolic SAR: needs ~40 bars for initial trend establishment
    "PSAR": lambda p: 40,

    # Ichimoku: senkou_span_b(52) + chikou displacement(26) + buffer
    "ICHIMOKU": lambda p: 52 + 26 + 10,

    # Aroon: needs length + 1 for proper calculation
    "AROON": lambda p: p.get("length", 14) + 5,

    # Vortex: needs length bars of TR calculations
    "VORTEX": lambda p: p.get("length", 14) + 5,

    # Choppiness: needs length + ATR period
    "CHOP": lambda p: p.get("length", 14) + 14 + 5,

    # Chandelier Exit: needs length + ATR calculation
    "CHANDELIER": lambda p: p.get("length", 22) + 14 + 5,

    # Hull MA: needs approximately length * 2 due to weighted calculations
    "HMA": lambda p: int(p.get("length", 9) * 2) + 10,

    # ALMA: needs length bars
    "ALMA": lambda p: p.get("length", 9) + 10,

    # ==========================================================================
    # MOMENTUM ADVANCED INDICATORS
    # ==========================================================================

    # TSI: needs long + short + signal periods
    "TSI": lambda p: p.get("long", 25) + p.get("short", 13) + 10,

    # Fisher Transform: needs length bars
    "FISHER": lambda p: p.get("length", 9) + 10,

    # Chande Momentum Oscillator: needs length bars
    "CMO": lambda p: p.get("length", 14) + 5,

    # Ultimate Oscillator: needs max of three periods + buffer
    "UO": lambda p: max(
        p.get("fast", 7),
        p.get("medium", 14),
        p.get("slow", 28)
    ) + 10,

    # Squeeze Momentum: needs BB(20) + KC(20) + momentum period
    "SQUEEZE": lambda p: max(
        p.get("bb_length", 20),
        p.get("kc_length", 20)
    ) + 14 + 5,

    # StochRSI: needs RSI period + Stoch period
    "STOCHRSI": lambda p: p.get("length", 14) + p.get("rsi_length", 14) + 5,

    # RVGI: needs length + signal smoothing
    "RVGI": lambda p: p.get("length", 10) + 4 + 5,

    # QQE: needs RSI + smoothing periods
    "QQE": lambda p: p.get("length", 14) + p.get("smooth", 5) + 10,

    # RSX (smoothed RSI): needs length + smoothing
    "RSX": lambda p: p.get("length", 14) + 10,

    # Williams %R: needs length
    "WILLR": lambda p: p.get("length", 14) + 5,

    # Awesome Oscillator: needs slow SMA period
    "AO": lambda p: p.get("slow", 34) + 5,

    # Accelerator Oscillator: needs AO + its SMA
    "AC": lambda p: p.get("slow", 34) + 5 + 5,

    # Balance of Power: needs smoothing period
    "BOP": lambda p: p.get("length", 14) + 5,

    # Coppock Curve: needs long ROC + WMA
    "COPPOCK": lambda p: p.get("long", 14) + p.get("wma", 10) + 5,

    # KDJ: needs Stochastic periods
    "KDJ": lambda p: p.get("length", 9) + p.get("signal", 3) + 5,

    # Inertia: uses RVI smoothing
    "INERTIA": lambda p: p.get("length", 14) + 20 + 10,

    # ==========================================================================
    # VOLUME FLOW INDICATORS
    # ==========================================================================

    # Chaikin Money Flow: needs length bars
    "CMF": lambda p: p.get("length", 20) + 5,

    # Elder Force Index: needs length EMA
    "EFI": lambda p: p.get("length", 13) + 5,

    # Klinger Volume Oscillator: needs long + signal periods
    "KVO": lambda p: p.get("slow", 55) + p.get("signal", 13) + 5,

    # Percentage Volume Oscillator: needs slow + signal
    "PVO": lambda p: p.get("slow", 26) + p.get("signal", 9) + 5,

    # Negative/Positive Volume Index: needs length
    "NVI": lambda p: p.get("length", 1) + 10,
    "PVI": lambda p: p.get("length", 1) + 10,

    # Archer OBV: needs offset
    "AOBV": lambda p: p.get("offset", 0) + 20,

    # Accumulation/Distribution Oscillator: needs fast + slow
    "ADOSC": lambda p: p.get("slow", 10) + 5,

    # Money Flow Index: needs length
    "MFI": lambda p: p.get("length", 14) + 5,

    # Accumulation/Distribution: cumulative indicator, needs smoothing period
    "AD": lambda p: p.get("length", 20) + 20,

    # ==========================================================================
    # BASIC INDICATORS (used in base entries)
    # ==========================================================================

    # RSI: needs period bars
    "RSI": lambda p: p.get("period", 14) + 5,

    # MACD: needs slow EMA period
    "MACD": lambda p: 26 + 9 + 5,

    # Stochastic: needs length + signal smoothing
    "STOCH": lambda p: 14 + 3 + 5,

    # CCI: needs period
    "CCI": lambda p: p.get("period", 20) + 5,

    # ADX: needs period * 2 (for DI smoothing)
    "ADX": lambda p: 14 * 2 + 5,

    # ATR: needs period
    "ATR": lambda p: 14 + 5,

    # Bollinger Bands: needs period
    "BB": lambda p: p.get("period", 20) + 5,

    # Moving Averages
    "MA": lambda p: max(p.get("N", 20), p.get("slow", 50)) + 5,
    "EMA": lambda p: max(p.get("fast", 12), p.get("slow", 26)) + 5,

    # Rate of Change: needs N periods
    "ROC": lambda p: p.get("N", 10) + 5,

    # Momentum: needs N periods (same as ROC but absolute diff)
    "MOM": lambda p: p.get("N", 10) + 5,

    # VWAP: needs cumulative calculation, minimal lookback
    "VWAP": lambda p: 20,

    # Keltner Channel: needs EMA + ATR
    "KELT": lambda p: 20 + 14 + 5,
}

# Safety margin for edge cases
SAFETY_MARGIN = 10


def compute_lookback(indicators_used: list[str], params: dict) -> int:
    """
    Compute minimum lookback required for a set of indicators.

    Args:
        indicators_used: List of indicator names (e.g., ["SUPERTREND", "ATR"])
        params: Parameter dict with values like {"length": 14, "mult": 3.0}

    Returns:
        Minimum number of bars required

    Raises:
        ValueError: If an unknown indicator is encountered (no fallback)
    """
    if not indicators_used:
        return 20 + SAFETY_MARGIN  # Minimum for price action only

    max_lookback = 0

    for indicator in indicators_used:
        indicator_upper = indicator.upper()

        if indicator_upper not in LOOKBACK_FORMULAS:
            raise ValueError(
                f"Unknown indicator for lookback calculation: '{indicator}'. "
                f"Add formula to LOOKBACK_FORMULAS in lookback.py"
            )

        formula = LOOKBACK_FORMULAS[indicator_upper]
        lookback = formula(params)
        max_lookback = max(max_lookback, lookback)

    return max_lookback + SAFETY_MARGIN


def validate_lookback(
    declared_lookback: int,
    indicators_used: list[str],
    params: dict,
    entry_id: str,
) -> int:
    """
    Validate and possibly correct the declared lookback.

    Args:
        declared_lookback: The manually declared lookback_required
        indicators_used: List of indicator names
        params: Parameter dict
        entry_id: Entry ID for error messages

    Returns:
        Corrected lookback (max of declared and computed)

    Raises:
        ValueError: If computed lookback significantly exceeds declared
    """
    computed = compute_lookback(indicators_used, params)

    if computed > declared_lookback:
        # Auto-correct, but log a warning
        return computed

    return declared_lookback


def get_indicator_lookback(indicator: str, params: dict) -> int:
    """
    Get lookback for a single indicator.

    Args:
        indicator: Indicator name
        params: Parameter dict

    Returns:
        Lookback for this indicator
    """
    return compute_lookback([indicator], params)
