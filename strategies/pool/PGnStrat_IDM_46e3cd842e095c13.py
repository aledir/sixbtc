"""
Pattern-Gen Strategy: Intraday Reversal Up + Volume Spike
Type: IDM (template)
Timeframe: 2h
Direction: long
Blocks: INTRADAY_REVERSAL_UP, VOLUME_SPIKE
Generated: 2026-01-13T06:19:43.590715+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_IDM_46e3cd842e095c13(StrategyCore):
    """
    Pattern: Intraday Reversal Up + Volume Spike
    Direction: long
    Lookback: 50 bars
    Execution: close_based
    """

    # Direction
    direction = 'long'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Execution type for parametric optimization
    execution_type = 'close_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 50

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.8
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 45

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Intraday Reversal Up + Volume Spike
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['bar_range'] = df['high'] - df['low']
        df['open_pos'] = (df['open'] - df['low']) / df['bar_range']
        df['close_pos'] = (df['close'] - df['low']) / df['bar_range']
        df['reversal'] = (df['open_pos'] < 0.3) & (df['close_pos'] > 0.7)
        df['vol_avg'] = df['volume'].rolling(10).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['reversal']
        df['entry_cond2'] = df['volume'] > df['vol_avg'] * 2.0
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
            reason='Intraday Reversal Up + Volume Spike',
        )