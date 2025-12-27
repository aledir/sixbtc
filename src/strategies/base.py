"""
StrategyCore Base Class

Abstract base class for all trading strategies in SixBTC.
All generated strategies MUST inherit from this class to ensure
compatibility with both backtest (VectorBT) and live (Hyperliquid SDK).
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

            def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
                if entry_condition:
                    return Signal(
                        direction='long',
                        leverage=self.leverage,
                        sl_type=StopLossType.ATR,
                        atr_stop_multiplier=2.0,
                        tp_type=TakeProfitType.RR_RATIO,
                        rr_ratio=2.0,
                        reason="Entry reason"
                    )
                return None
    """

    # Target leverage - override in subclass
    # Actual leverage = min(this value, coin's max_leverage from DB)
    leverage: int = 1

    def __init__(self, params: Optional[dict] = None):
        """
        Initialize strategy with optional parameters

        Args:
            params: Strategy-specific parameters (e.g., {'rsi_period': 14})
        """
        self.params = params or {}

    @abstractmethod
    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: Optional[str] = None
    ) -> Optional[Signal]:
        """
        Generate trading signal from OHLCV data.

        Args:
            df: OHLCV DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
                Rows are ordered chronologically (oldest first)
                You can ONLY use data up to the current row (no future data)
            symbol: Coin symbol (e.g., 'BTC', 'ETH') - passed for context

        Returns:
            Signal object if conditions met, None otherwise

        Example (ATR-based):
            def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
                if len(df) < 50:
                    return None

                rsi = ta.RSI(df['close'], timeperiod=14)
                if rsi.iloc[-1] < 30:
                    return Signal(
                        direction='long',
                        leverage=self.leverage,
                        sl_type=StopLossType.ATR,
                        atr_stop_multiplier=2.0,
                        tp_type=TakeProfitType.ATR,
                        atr_take_multiplier=3.0,
                        reason=f"RSI oversold at {rsi.iloc[-1]:.1f}"
                    )
                return None

        Example (Structure-based SL):
            def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
                swing_low = df['low'].rolling(20).min().iloc[-1]
                current_price = df['close'].iloc[-1]

                if entry_condition:
                    return Signal(
                        direction='long',
                        leverage=self.leverage,
                        sl_type=StopLossType.STRUCTURE,
                        sl_price=swing_low,
                        tp_type=TakeProfitType.RR_RATIO,
                        rr_ratio=2.5,
                        reason=f"Entry at {current_price}, SL at swing low {swing_low}"
                    )
                return None
        """
        pass

    def generate_signals_vectorized(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate signals for ALL bars in the dataframe (vectorized).

        This method is used for lookahead bias detection.
        It must produce the SAME signals as calling generate_signal()
        iteratively for each bar with truncated data.

        Args:
            df: OHLCV DataFrame with full data

        Returns:
            DataFrame with columns:
                - 'signal': 1 (long), -1 (short), 0 (no signal/close)
                - 'sl_type': StopLossType value
                - 'tp_type': TakeProfitType value
                - 'reason': Signal reason (optional)

        Default implementation calls generate_signal() in a loop.
        Override for better performance with true vectorized logic.
        """
        n = len(df)

        # Initialize result arrays
        signals = np.zeros(n, dtype=np.int8)
        sl_types = [''] * n
        tp_types = [''] * n

        # Minimum warmup period (most strategies need ~50 bars)
        warmup = min(50, n // 2)

        for i in range(warmup, n):
            # Pass truncated data (no lookahead)
            df_slice = df.iloc[:i + 1]

            try:
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

            except Exception:
                continue

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
