"""
Pattern-Gen Strategy: Evolved: Failed Breakout (Sell the Rip) + Lower Highs and Lower Lows
Type: ADV (genetic)
Timeframe: 1h
Direction: short
Blocks: FAILED_BREAKOUT_SHORT, LH_LL
Generated: 2026-01-13T09:18:38.754302+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGgStrat_ADV_01c85648cbf3e550(StrategyCore):
    """
    Pattern: Evolved: Failed Breakout (Sell the Rip) + Lower Highs and Lower Lows
    Direction: short
    Lookback: 50 bars
    Execution: touch_based
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Execution type for parametric optimization
    execution_type = 'touch_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 50

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.08
    TP_PCT = 0.12
    LEVERAGE = 1
    exit_after_bars = 0

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Evolved: Failed Breakout (Sell the Rip) + Lower Highs and Lower Lows
        Composition: genetic
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['resistance'] = df['high'].rolling(30).max().shift(1)
        df['broke_resistance'] = df['high'].shift(1) > df['resistance'].shift(1)
        df['rejected'] = df['close'] < df['resistance']
        df['lh'] = df['high'] < df['high'].shift(5)
        df['ll'] = df['low'] < df['low'].shift(5)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['broke_resistance'] & df['rejected']
        df['entry_cond2'] = df['lh'] & df['ll']
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
            reason='Evolved: Failed Breakout (Sell the Rip) + Lower Highs and Lower Lows',
        )