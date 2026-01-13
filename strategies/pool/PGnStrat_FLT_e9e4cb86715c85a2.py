"""
Pattern-Gen Strategy: EMA Cross Down + Trend Aligned (fast12_slow26_trend100)
Type: FLT (parametric)
Timeframe: 2h
Direction: short
Blocks: EMA_CROSS_TREND_SHORT
Generated: 2026-01-13T05:54:06.650177+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_FLT_e9e4cb86715c85a2(StrategyCore):
    """
    Pattern: EMA Cross Down + Trend Aligned (fast12_slow26_trend100)
    Direction: short
    Lookback: 120 bars
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
    LOOKBACK = 120

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.3
    TP_PCT = 0.0
    LEVERAGE = 2
    exit_after_bars = 40

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: EMA Cross Down + Trend Aligned (fast12_slow26_trend100)
        Composition: parametric
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['ema_fast'] = ta.EMA(df['close'], timeperiod=12)
        df['ema_slow'] = ta.EMA(df['close'], timeperiod=26)
        df['ema_trend'] = ta.EMA(df['close'], timeperiod=100)
        df['cross_down'] = (df['ema_fast'] < df['ema_slow']) & (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1))
        df['trend_down'] = df['close'] < df['ema_trend']

        # === ENTRY SIGNAL ===
        df['entry_signal'] = df['cross_down'] & df['trend_down']

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
            reason='EMA Cross Down + Trend Aligned (fast12_slow26_trend100)',
        )