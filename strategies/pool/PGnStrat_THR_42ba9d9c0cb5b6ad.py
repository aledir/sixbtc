"""
Pattern-Gen Strategy: Stochastic Overbought + Bearish Engulfing
Type: THR (template)
Timeframe: 2h
Direction: short
Blocks: STOCH_OVERBOUGHT, BEARISH_ENGULFING
Generated: 2026-01-13T00:21:08.834510+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_THR_42ba9d9c0cb5b6ad(StrategyCore):
    """
    Pattern: Stochastic Overbought + Bearish Engulfing
    Direction: short
    Lookback: 30 bars
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
    LOOKBACK = 30

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.36
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 60

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Stochastic Overbought + Bearish Engulfing
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'],
            fastk_period=14, slowk_period=3, slowd_period=3)
        df['prev_bullish'] = df['close'].shift(1) > df['open'].shift(1)
        df['curr_bearish'] = df['close'] < df['open']
        df['engulf'] = (df['open'] > df['close'].shift(1)) & (df['close'] < df['open'].shift(1))

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['slowk'] > 75
        df['entry_cond2'] = df['prev_bullish'] & df['curr_bearish'] & df['engulf']
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
            reason='Stochastic Overbought + Bearish Engulfing',
        )