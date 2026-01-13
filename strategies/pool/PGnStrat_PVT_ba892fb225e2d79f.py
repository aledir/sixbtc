"""
Pattern-Gen Strategy: Price Break Above Pivot + Volume Spike
Type: PVT (template)
Timeframe: 2h
Direction: long
Blocks: PIVOT_BREAK_UP, VOLUME_SPIKE
Generated: 2026-01-13T08:26:02.497081+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_PVT_ba892fb225e2d79f(StrategyCore):
    """
    Pattern: Price Break Above Pivot + Volume Spike
    Direction: long
    Lookback: 50 bars
    Execution: touch_based
    """

    # Direction
    direction = 'long'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Execution type for parametric optimization
    execution_type = 'touch_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 50

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.06
    TP_PCT = 0.075
    LEVERAGE = 1
    exit_after_bars = 0

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Price Break Above Pivot + Volume Spike
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
        df['above_pivot'] = df['close'] > df['pivot']
        df['was_below'] = df['close'].shift(1) <= df['pivot'].shift(1)
        df['vol_avg'] = df['volume'].rolling(20).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['above_pivot'] & df['was_below']
        df['entry_cond2'] = df['volume'] > df['vol_avg'] * 3.0
        df['entry_signal'] = df['entry_cond1'] & df['entry_cond2']

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
            reason='Price Break Above Pivot + Volume Spike',
        )