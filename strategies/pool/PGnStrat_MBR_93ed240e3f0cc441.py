"""
Pattern-Gen Strategy: Two Bar Reversal Bullish + RSI Oversold
Type: MBR (template)
Timeframe: 2h
Direction: long
Blocks: TWO_BAR_REVERSAL_BULL, RSI_OVERSOLD
Generated: 2026-01-13T06:07:25.190633+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_MBR_93ed240e3f0cc441(StrategyCore):
    """
    Pattern: Two Bar Reversal Bullish + RSI Oversold
    Direction: long
    Lookback: 30 bars
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
    LOOKBACK = 30

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.24
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 30

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Two Bar Reversal Bullish + RSI Oversold
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['prev_down'] = df['close'].shift(1) < df['open'].shift(1)
        df['curr_up'] = df['close'] > df['open']
        df['higher_close'] = df['close'] > df['close'].shift(1)
        df['rsi'] = ta.RSI(df['close'], timeperiod=7)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['prev_down'] & df['curr_up'] & df['higher_close']
        df['entry_cond2'] = df['rsi'] < 25
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
            reason='Two Bar Reversal Bullish + RSI Oversold',
        )