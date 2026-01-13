"""
Pattern-Gen Strategy: Bearish Engulfing Pattern ()
Type: CDL (parametric)
Timeframe: 2h
Direction: short
Blocks: CDL_ENGULFING_BEAR
Generated: 2026-01-13T03:53:13.601495+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_CDL_5a22e8e25499a22f(StrategyCore):
    """
    Pattern: Bearish Engulfing Pattern ()
    Direction: short
    Lookback: 10 bars
    Execution: close_based
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Execution type for parametric optimization
    execution_type = 'close_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 10

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.8
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 75

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Bearish Engulfing Pattern ()
        Composition: parametric
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['cdl_engulfing'] = ta.CDLENGULFING(df['open'], df['high'], df['low'], df['close'])

        # === ENTRY SIGNAL ===
        df['entry_signal'] = df['cdl_engulfing'] < 0

        # Ensure entry_signal is boolean
        df['entry_signal'] = df['entry_signal'].fillna(False).astype(bool)

        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        """
        Generate signal for LIVE execution.

        For backtest, the entry_signal column is read directly by the engine.
        """
        if len(df) < self.LOOKBACK + 10:
            return None

        # Read pre-calculated entry signal
        if not df['entry_signal'].iloc[-1]:
            return None

        # Build signal
        return Signal(
            direction=self.direction,
            leverage=self.LEVERAGE,
            sl_type=StopLossType.PERCENTAGE,
            sl_pct=self.SL_PCT,
            tp_type=TakeProfitType.PERCENTAGE,
            tp_pct=self.TP_PCT,
            exit_after_bars=self.exit_after_bars,
            reason='Bearish Engulfing Pattern ()',
        )