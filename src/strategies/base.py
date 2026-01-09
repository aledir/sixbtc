"""
StrategyCore Base Class

Abstract base class for all trading strategies in SixBTC.
All generated strategies MUST inherit from this class to ensure
compatibility with both backtest and live (Hyperliquid SDK) execution.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import pandas as pd
import numpy as np


# =============================================================================
# STOP LOSS TYPES
# =============================================================================
class StopLossType(str, Enum):
    """
    Available stop loss calculation methods.

    ATR: Dynamic SL based on Average True Range (adapts to volatility)
    PERCENTAGE: Fixed percentage from entry price
    STRUCTURE: Based on price structure (swing low/high, support/resistance)
    VOLATILITY: Based on standard deviation (Bollinger-style)
    TRAILING: Trailing stop that follows price
    """
    ATR = "atr"
    PERCENTAGE = "pct"
    STRUCTURE = "structure"
    VOLATILITY = "volatility"
    TRAILING = "trailing"


# =============================================================================
# TAKE PROFIT TYPES
# =============================================================================
class TakeProfitType(str, Enum):
    """
    Available take profit calculation methods.

    ATR: Dynamic TP based on Average True Range
    RR_RATIO: Based on Risk/Reward ratio (e.g., 2:1 means TP = 2x risk distance)
    PERCENTAGE: Fixed percentage from entry price
    TRAILING: Trailing take profit that locks in gains
    """
    ATR = "atr"
    RR_RATIO = "rr_ratio"
    PERCENTAGE = "pct"
    TRAILING = "trailing"


# =============================================================================
# EXIT CONDITION TYPES
# =============================================================================
class ExitType(str, Enum):
    """
    Available exit condition types (alternative to or in addition to TP).

    INDICATOR: Exit when indicator condition is met (e.g., RSI > 70)
    PATTERN: Exit on reversal pattern detection
    TIME_BASED: Exit after N bars/candles
    TRAILING_BREAKEVEN: Trailing stop with breakeven trigger
    """
    INDICATOR = "indicator"
    PATTERN = "pattern"
    TIME_BASED = "time"
    TRAILING_BREAKEVEN = "trailing_be"


# =============================================================================
# SIGNAL DATACLASS
# =============================================================================
@dataclass
class Signal:
    """
    Trading signal output from a strategy.

    REQUIRED:
        - direction: 'long', 'short', or 'close'
        - Stop Loss: ALWAYS required (via sl_type + params)

    OPTIONAL (but at least one required for exits):
        - Take Profit: via tp_type + params
        - Exit Conditions: via exit_type + params

    Example (ATR-based SL/TP):
        Signal(
            direction='long',
            leverage=5,
            sl_type=StopLossType.ATR,
            atr_stop_multiplier=2.0,
            tp_type=TakeProfitType.ATR,
            atr_take_multiplier=3.0,
            reason="RSI oversold bounce"
        )

    Example (Percentage SL + RR ratio TP):
        Signal(
            direction='long',
            leverage=3,
            sl_type=StopLossType.PERCENTAGE,
            sl_pct=0.02,  # 2% stop loss
            tp_type=TakeProfitType.RR_RATIO,
            rr_ratio=2.5,  # 2.5:1 reward to risk
            reason="Support bounce with 2.5:1 RR"
        )

    Example (Structure SL + Time-based exit):
        Signal(
            direction='long',
            leverage=5,
            sl_type=StopLossType.STRUCTURE,
            sl_price=48500.0,  # Swing low
            exit_type=ExitType.TIME_BASED,
            exit_after_bars=20,
            reason="Swing low entry, exit after 20 bars"
        )
    """
    direction: str  # 'long', 'short', 'close'

    # =========================================================================
    # LEVERAGE
    # =========================================================================
    leverage: int = 1  # Capped at coin's max_leverage on Hyperliquid

    # =========================================================================
    # STOP LOSS (REQUIRED - at least one method must be configured)
    # =========================================================================
    sl_type: StopLossType = StopLossType.ATR

    # ATR-based SL params
    atr_stop_multiplier: float = 2.0  # SL at N * ATR from entry

    # Percentage-based SL params
    sl_pct: Optional[float] = None  # e.g., 0.02 = 2% below entry (long)

    # Structure-based SL params
    sl_price: Optional[float] = None  # Absolute price (swing low, support)

    # Volatility-based SL params (std deviation)
    sl_std_multiplier: Optional[float] = None  # SL at N * std from entry

    # Trailing SL params
    trailing_stop_pct: Optional[float] = None  # Trail by this % from peak
    trailing_activation_pct: Optional[float] = None  # Activate after N% profit

    # =========================================================================
    # TAKE PROFIT (OPTIONAL if exit_type is set)
    # =========================================================================
    tp_type: Optional[TakeProfitType] = None

    # ATR-based TP params
    atr_take_multiplier: float = 3.0  # TP at N * ATR from entry

    # RR Ratio TP params
    rr_ratio: Optional[float] = None  # e.g., 2.0 = TP at 2x risk distance

    # Percentage-based TP params
    tp_pct: Optional[float] = None  # e.g., 0.05 = 5% above entry (long)

    # Fixed price TP
    tp_price: Optional[float] = None  # Absolute take profit price

    # Trailing TP params
    trailing_tp_pct: Optional[float] = None  # Lock in gains, trail by this %

    # =========================================================================
    # EXIT CONDITIONS (OPTIONAL if tp_type is set)
    # =========================================================================
    exit_type: Optional[ExitType] = None

    # Indicator-based exit params
    exit_indicator: Optional[str] = None  # e.g., "RSI", "MACD"
    exit_condition: Optional[str] = None  # e.g., "> 70", "< -50"

    # Time-based exit params
    exit_after_bars: Optional[int] = None  # Exit after N bars

    # Trailing with breakeven params
    breakeven_trigger_pct: Optional[float] = None  # Move SL to entry after N%

    # =========================================================================
    # METADATA
    # =========================================================================
    size: Optional[float] = None  # Position size (calculated by executor)
    reason: str = ""  # Explanation for signal
    confidence: float = 1.0  # 0-1 confidence score

    def __post_init__(self):
        """Validate signal parameters"""
        # Validate direction
        if self.direction not in ['long', 'short', 'close']:
            raise ValueError(f"Invalid direction: {self.direction}")

        # Validate confidence
        if self.confidence < 0 or self.confidence > 1:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")

        # Validate SL configuration for entry signals
        if self.direction in ['long', 'short']:
            self._validate_stop_loss()

            # Ensure at least TP or exit condition exists
            has_tp = self.tp_type is not None or self.tp_price is not None
            has_exit = self.exit_type is not None
            if not has_tp and not has_exit:
                # Default to ATR-based TP if nothing specified
                self.tp_type = TakeProfitType.ATR

    def _validate_stop_loss(self):
        """Validate stop loss configuration based on sl_type"""
        if self.sl_type == StopLossType.ATR:
            if self.atr_stop_multiplier <= 0:
                raise ValueError("atr_stop_multiplier must be > 0")

        elif self.sl_type == StopLossType.PERCENTAGE:
            if self.sl_pct is None or self.sl_pct <= 0:
                raise ValueError("sl_pct required for PERCENTAGE SL type (must be > 0)")

        elif self.sl_type == StopLossType.STRUCTURE:
            if self.sl_price is None:
                raise ValueError("sl_price required for STRUCTURE SL type")

        elif self.sl_type == StopLossType.VOLATILITY:
            if self.sl_std_multiplier is None or self.sl_std_multiplier <= 0:
                raise ValueError("sl_std_multiplier required for VOLATILITY SL type")

        elif self.sl_type == StopLossType.TRAILING:
            if self.trailing_stop_pct is None or self.trailing_stop_pct <= 0:
                raise ValueError("trailing_stop_pct required for TRAILING SL type")

    def get_sl_description(self) -> str:
        """Human-readable SL description"""
        if self.sl_type == StopLossType.ATR:
            return f"ATR x{self.atr_stop_multiplier}"
        elif self.sl_type == StopLossType.PERCENTAGE:
            return f"{self.sl_pct * 100:.1f}%"
        elif self.sl_type == StopLossType.STRUCTURE:
            return f"Price: {self.sl_price}"
        elif self.sl_type == StopLossType.VOLATILITY:
            return f"Std x{self.sl_std_multiplier}"
        elif self.sl_type == StopLossType.TRAILING:
            return f"Trail {self.trailing_stop_pct * 100:.1f}%"
        return "Unknown"

    def get_tp_description(self) -> str:
        """Human-readable TP description"""
        if self.tp_price is not None:
            return f"Price: {self.tp_price}"
        if self.tp_type == TakeProfitType.ATR:
            return f"ATR x{self.atr_take_multiplier}"
        elif self.tp_type == TakeProfitType.RR_RATIO:
            return f"RR {self.rr_ratio}:1"
        elif self.tp_type == TakeProfitType.PERCENTAGE:
            return f"{self.tp_pct * 100:.1f}%"
        elif self.tp_type == TakeProfitType.TRAILING:
            return f"Trail {self.trailing_tp_pct * 100:.1f}%"
        return "Exit condition"


# =============================================================================
# STRATEGY CORE BASE CLASS
# =============================================================================
class StrategyCore(ABC):
    """
    Abstract base class for all trading strategies.

    TWO-PHASE SIGNAL GENERATION:
        Strategies use a two-phase approach for performance and testability:

        1. calculate_indicators(df) -> df_with_indicators
           Pre-calculates ALL indicators on the full dataframe.
           Called ONCE per backtest/signal generation cycle.

        2. generate_signal(df_with_indicators) -> Signal
           Reads pre-calculated indicator values and generates signal.
           Only uses iloc[-1] to read current bar values.

        This separation enables:
        - Freqtrade-style lookahead bias detection (compare indicator values)
        - Numba/Cython optimization of signal generation loop
        - O(n) indicator calculation instead of O(n²)

    REQUIREMENTS:
    1. Pure function: Same input -> same output
    2. No state mutation
    3. No external dependencies (DB, API, etc.)
    4. No lookahead bias (only use past data)

    STOP LOSS is REQUIRED for all entry signals.

    LEVERAGE:
        Each strategy defines a single `leverage` attribute.
        This is the TARGET leverage - actual leverage will be capped at
        the coin's max_leverage from the database.

        actual_leverage = min(strategy.leverage, coin.max_leverage)

    USAGE:
        class MyStrategy(StrategyCore):
            leverage = 10  # Target 10x leverage

            def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
                df = df.copy()
                df['rsi'] = ta.RSI(df['close'], timeperiod=14)
                df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
                return df

            def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
                if df['rsi'].iloc[-1] < 30:
                    return Signal(
                        direction='long',
                        leverage=self.leverage,
                        sl_type=StopLossType.ATR,
                        atr_stop_multiplier=2.0,
                        reason=f"RSI oversold at {df['rsi'].iloc[-1]:.1f}"
                    )
                return None
    """

    # =========================================================================
    # STRATEGY PARAMETERS (read by backtester for vectorized execution)
    # =========================================================================
    # These are class attributes that define the strategy's behavior.
    # The backtester reads these directly instead of calling generate_signal().
    # Override in subclass.

    # Direction: 'long' or 'short'
    direction: str = 'long'

    # Stop loss percentage (e.g., 0.02 = 2%)
    sl_pct: float = 0.02

    # Stop loss type (PERCENTAGE or TRAILING)
    sl_type: StopLossType = StopLossType.PERCENTAGE

    # Trailing stop parameters (only used when sl_type = TRAILING)
    trailing_stop_pct: Optional[float] = None      # Distance from high water mark
    trailing_activation_pct: Optional[float] = None  # Activate after N% profit

    # ATR-based stop parameters (only used when sl_type = ATR)
    atr_stop_multiplier: float = 2.0    # SL at N × ATR from entry
    atr_take_multiplier: float = 3.0    # TP at N × ATR from entry
    atr_period: int = 14                # ATR calculation period

    # Take profit percentage (e.g., 0.03 = 3%)
    tp_pct: float = 0.03

    # Target leverage (capped at coin's max_leverage from DB)
    leverage: int = 1

    # Exit after N bars (time-based exit)
    exit_after_bars: int = 20

    # Column name for entry signals in calculate_indicators()
    # Must be a boolean Series
    signal_column: str = 'entry_signal'

    # Indicator column names added by calculate_indicators()
    # Used for lookahead bias detection
    indicator_columns: List[str] = []

    def __init__(self, params: Optional[dict] = None):
        """
        Initialize strategy with optional parameters

        Args:
            params: Strategy-specific parameters (e.g., {'rsi_period': 14})
        """
        self.params = params or {}

    @abstractmethod
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate ALL indicators on the dataframe.

        This method is called ONCE before signal generation. All indicator
        calculations should happen here, not in generate_signal().

        Args:
            df: OHLCV DataFrame with columns ['open', 'high', 'low', 'close', 'volume']

        Returns:
            DataFrame with original columns PLUS indicator columns.
            Must NOT modify the original df - return a copy.

        Example:
            def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
                df = df.copy()
                df['rsi'] = ta.RSI(df['close'], timeperiod=14)
                df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
                df['ema_fast'] = ta.EMA(df['close'], timeperiod=12)
                df['ema_slow'] = ta.EMA(df['close'], timeperiod=26)
                df['macd'], df['macd_signal'], df['macd_hist'] = ta.MACD(df['close'])
                return df

        IMPORTANT:
        - Always return df.copy() to avoid modifying the original
        - Use only lookback operations (no center=True, no shift(-N))
        - Set self.indicator_columns to list column names for lookahead testing
        """
        pass

    @abstractmethod
    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: Optional[str] = None
    ) -> Optional[Signal]:
        """
        Generate trading signal from DataFrame with pre-calculated indicators.

        This method receives a DataFrame that has ALREADY been processed by
        calculate_indicators(). It should ONLY read indicator values using
        iloc[-1] and apply entry/exit logic.

        Args:
            df: DataFrame with OHLCV + indicator columns (from calculate_indicators)
                Rows are ordered chronologically (oldest first)
                Use df['indicator_name'].iloc[-1] to read current bar values
            symbol: Coin symbol (e.g., 'BTC', 'ETH') - passed for context

        Returns:
            Signal object if conditions met, None otherwise

        Example:
            def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
                if len(df) < 50:
                    return None

                # Read pre-calculated indicators (DO NOT recalculate here!)
                rsi = df['rsi'].iloc[-1]
                atr = df['atr'].iloc[-1]

                if pd.isna(rsi) or pd.isna(atr):
                    return None

                if rsi < 30:
                    return Signal(
                        direction='long',
                        leverage=self.leverage,
                        sl_type=StopLossType.ATR,
                        atr_stop_multiplier=2.0,
                        reason=f"RSI oversold at {rsi:.1f}"
                    )
                return None

        IMPORTANT:
        - DO NOT calculate indicators here - they should be pre-calculated
        - ONLY read values using iloc[-1]
        - Keep logic simple for potential Numba optimization
        """
        pass

    def generate_signals_vectorized(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate signals for ALL bars in the dataframe.

        Uses two-phase approach:
        1. Calculate indicators ONCE on full dataframe
        2. Iterate through bars, reading pre-calculated indicator values

        This is much faster than recalculating indicators for each bar.

        Args:
            df: OHLCV DataFrame with full data

        Returns:
            DataFrame with columns:
                - 'signal': 1 (long), -1 (short), 0 (no signal/close)
                - 'sl_type': StopLossType value
                - 'tp_type': TakeProfitType value

        Note: Override for even better performance with true vectorized logic
        that doesn't require iteration.
        """
        n = len(df)

        # Initialize result arrays
        signals = np.zeros(n, dtype=np.int8)
        sl_types = [''] * n
        tp_types = [''] * n

        # Phase 1: Calculate indicators ONCE on full dataframe
        df_with_indicators = self.calculate_indicators(df)

        # Minimum warmup period (most strategies need ~50 bars)
        warmup = min(50, n // 2)

        # Phase 2: Iterate through bars, reading pre-calculated values
        for i in range(warmup, n):
            # Pass truncated view (indicators already calculated)
            df_slice = df_with_indicators.iloc[:i + 1]

            signal = self.generate_signal(df_slice)

            if signal is not None:
                if signal.direction == 'long':
                    signals[i] = 1
                elif signal.direction == 'short':
                    signals[i] = -1
                else:
                    signals[i] = 0

                sl_types[i] = signal.sl_type.value if signal.sl_type else ''
                tp_types[i] = signal.tp_type.value if signal.tp_type else ''

        return pd.DataFrame({
            'signal': signals,
            'sl_type': sl_types,
            'tp_type': tp_types
        }, index=df.index)

    def __str__(self) -> str:
        """String representation"""
        return f"{self.__class__.__name__}(params={self.params})"

    def __repr__(self) -> str:
        """Debug representation"""
        return self.__str__()
