"""
StrategyCore Base Class

Abstract base class for all trading strategies in SixBTC.
All generated strategies MUST inherit from this class to ensure
compatibility with both backtest (VectorBT) and live (Hyperliquid SDK).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import pandas as pd


@dataclass
class Signal:
    """
    Trading signal output from a strategy

    Attributes:
        direction: 'long', 'short', or 'close'
        atr_stop_multiplier: Stop loss distance in ATR multiples (default: 2.0)
        atr_take_multiplier: Take profit distance in ATR multiples (default: 3.0)
        stop_loss: Absolute stop loss price (optional, used if ATR not available)
        take_profit: Absolute take profit price (optional, used if ATR not available)
        size: Position size (will be calculated by executor based on risk)
        reason: Explanation for logging and debugging
        confidence: Signal confidence 0-1 (optional, for future weighting)
    """
    direction: str  # 'long', 'short', 'close'

    # ATR-based risk management (preferred)
    atr_stop_multiplier: float = 2.0  # Stop at 2x ATR
    atr_take_multiplier: float = 3.0  # TP at 3x ATR (1.5:1 R:R)

    # Fixed price fallback (if ATR not available)
    stop_loss: Optional[float] = None  # Absolute price
    take_profit: Optional[float] = None  # Absolute price

    # Position sizing (calculated by executor)
    size: Optional[float] = None  # Will be calculated

    # Metadata
    reason: str = ""  # Explanation for signal
    confidence: float = 1.0  # 0-1 confidence score

    def __post_init__(self):
        """Validate signal parameters"""
        if self.direction not in ['long', 'short', 'close']:
            raise ValueError(f"Invalid direction: {self.direction}")

        if self.confidence < 0 or self.confidence > 1:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")


class StrategyCore(ABC):
    """
    Abstract base class for all trading strategies

    REQUIREMENTS:
    1. Pure function: Same input -> same output
    2. No state mutation
    3. No external dependencies (DB, API, etc.)
    4. No lookahead bias (only use past data)

    USAGE:
        class MyStrategy(StrategyCore):
            def generate_signal(self, df: pd.DataFrame) -> Signal | None:
                # Your logic here
                if entry_condition:
                    return Signal(direction='long', reason="...")
                return None
    """

    def __init__(self, params: Optional[dict] = None):
        """
        Initialize strategy with optional parameters

        Args:
            params: Strategy-specific parameters (e.g., {'rsi_period': 14})
        """
        self.params = params or {}

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> Optional[Signal]:
        """
        Generate trading signal from OHLCV data

        Args:
            df: OHLCV DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
                Rows are ordered chronologically (oldest first)
                You can ONLY use data up to the current row (no future data)

        Returns:
            Signal object if conditions met, None otherwise

        Example:
            def generate_signal(self, df: pd.DataFrame) -> Signal | None:
                # Minimum data check
                if len(df) < 50:
                    return None

                # Calculate indicators (ONLY on past data)
                rsi = ta.RSI(df['close'], timeperiod=14)
                atr = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)

                # Current values
                current_rsi = rsi.iloc[-1]
                current_atr = atr.iloc[-1]

                # Entry condition
                if current_rsi < 30:  # Oversold
                    return Signal(
                        direction='long',
                        atr_stop_multiplier=2.0,
                        atr_take_multiplier=3.0,
                        reason=f"RSI oversold at {current_rsi:.2f}"
                    )

                return None
        """
        pass

    def __str__(self) -> str:
        """String representation"""
        return f"{self.__class__.__name__}(params={self.params})"

    def __repr__(self) -> str:
        """Debug representation"""
        return self.__str__()
