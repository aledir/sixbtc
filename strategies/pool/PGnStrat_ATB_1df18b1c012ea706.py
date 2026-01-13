"""
Pattern-Gen Strategy: ATR Channel Breakout Up + Not Overbought (RSI < threshold)
Type: ATB (template)
Timeframe: 2h
Direction: long
Blocks: ATR_CHANNEL_BREAK_UP, NOT_OVERBOUGHT
Generated: 2026-01-13T04:33:30.993876+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_ATB_1df18b1c012ea706(StrategyCore):
    """
    Pattern: ATR Channel Breakout Up + Not Overbought (RSI < threshold)
    Direction: long
    Lookback: 40 bars
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
    LOOKBACK = 40

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.8
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 40

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: ATR Channel Breakout Up + Not Overbought (RSI < threshold)
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['ma'] = ta.SMA(df['close'], timeperiod=20)
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        df['upper_band'] = df['ma'] + df['atr'] * 2.0
        df['rsi_filter'] = ta.RSI(df['close'], timeperiod=14)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['close'] > df['upper_band']
        df['entry_cond2'] = df['rsi_filter'] < 75
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
            reason='ATR Channel Breakout Up + Not Overbought (RSI < threshold)',
        )