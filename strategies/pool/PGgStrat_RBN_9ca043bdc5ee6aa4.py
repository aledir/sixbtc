"""
Pattern-Gen Strategy: Evolved: MA Ribbon Bearish Alignment + Lower Highs and Lower Lows
Type: RBN (genetic)
Timeframe: 2h
Direction: short
Blocks: MA_RIBBON_BEARISH, LH_LL
Generated: 2026-01-13T05:36:35.475944+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGgStrat_RBN_9ca043bdc5ee6aa4(StrategyCore):
    """
    Pattern: Evolved: MA Ribbon Bearish Alignment + Lower Highs and Lower Lows
    Direction: short
    Lookback: 200 bars
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
    LOOKBACK = 200

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

        Pattern: Evolved: MA Ribbon Bearish Alignment + Lower Highs and Lower Lows
        Composition: genetic
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['ema_fast'] = ta.EMA(df['close'], timeperiod=10)
        df['ema_med'] = ta.EMA(df['close'], timeperiod=50)
        df['ema_slow'] = ta.EMA(df['close'], timeperiod=100)
        df['aligned'] = (df['ema_fast'] < df['ema_med']) & (df['ema_med'] < df['ema_slow'])
        df['price_below'] = df['close'] < df['ema_fast']
        df['lh'] = df['high'] < df['high'].shift(5)
        df['ll'] = df['low'] < df['low'].shift(5)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['aligned'] & df['price_below']
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
            reason='Evolved: MA Ribbon Bearish Alignment + Lower Highs and Lower Lows',
        )