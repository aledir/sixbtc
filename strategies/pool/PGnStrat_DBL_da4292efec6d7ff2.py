"""
Pattern-Gen Strategy: Failed Double Top + Volume Spike
Type: DBL (template)
Timeframe: 1h
Direction: long
Blocks: FAILED_DOUBLE_TOP, VOLUME_SPIKE
Generated: 2026-01-13T05:48:54.913387+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_DBL_da4292efec6d7ff2(StrategyCore):
    """
    Pattern: Failed Double Top + Volume Spike
    Direction: long
    Lookback: 50 bars
    Execution: touch_based
    """

    # Direction
    direction = 'long'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Execution type for parametric optimization
    execution_type = 'touch_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 50

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.06
    TP_PCT = 0.1
    LEVERAGE = 1
    exit_after_bars = 60

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Failed Double Top + Volume Spike
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['high_max'] = df['high'].rolling(30).max()
        df['break_above'] = df['close'] > df['high_max'].shift(1)
        df['vol_avg'] = df['volume'].rolling(50).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['break_above']
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
            reason='Failed Double Top + Volume Spike',
        )