"""
Pattern-Gen Strategy: MA Ribbon Bearish Alignment + Stochastic Overbought
Type: RBN (template)
Timeframe: 2h
Direction: short
Blocks: MA_RIBBON_BEARISH, STOCH_OVERBOUGHT
Generated: 2026-01-13T00:32:10.334656+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_RBN_7d4ca71c47550976(StrategyCore):
    """
    Pattern: MA Ribbon Bearish Alignment + Stochastic Overbought
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
    SL_PCT = 0.32
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

        Pattern: MA Ribbon Bearish Alignment + Stochastic Overbought
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['ema_fast'] = ta.EMA(df['close'], timeperiod=20)
        df['ema_med'] = ta.EMA(df['close'], timeperiod=50)
        df['ema_slow'] = ta.EMA(df['close'], timeperiod=200)
        df['aligned'] = (df['ema_fast'] < df['ema_med']) & (df['ema_med'] < df['ema_slow'])
        df['price_below'] = df['close'] < df['ema_fast']
        df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'],
            fastk_period=14, slowk_period=5, slowd_period=5)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['aligned'] & df['price_below']
        df['entry_cond2'] = df['slowk'] > 75
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
            reason='MA Ribbon Bearish Alignment + Stochastic Overbought',
        )