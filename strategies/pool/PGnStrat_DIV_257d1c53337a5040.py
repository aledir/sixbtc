"""
Pattern-Gen Strategy: Stochastic Bearish Divergence + Lower Low
Type: DIV (template)
Timeframe: 1h
Direction: short
Blocks: STOCH_BEARISH_DIVERGENCE, LOWER_LOW
Generated: 2026-01-13T04:42:45.551415+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_DIV_257d1c53337a5040(StrategyCore):
    """
    Pattern: Stochastic Bearish Divergence + Lower Low
    Direction: short
    Lookback: 80 bars
    Execution: close_based
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Execution type for parametric optimization
    execution_type = 'close_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 80

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.3
    TP_PCT = 0.0
    LEVERAGE = 2
    exit_after_bars = 30

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Stochastic Bearish Divergence + Lower Low
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=5, slowk_period=5, slowd_period=3)
        df['price_max'] = df['high'].rolling(10).max()
        df['is_price_high'] = df['high'] == df['price_max']
        df['stoch_at_high'] = df['slowk'].where(df['is_price_high']).ffill()
        df['prev_price_max'] = df['price_max'].shift(10)
        df['prev_stoch_at_high'] = df['stoch_at_high'].shift(10)
        df['price_higher'] = df['price_max'] > df['prev_price_max']
        df['stoch_lower'] = df['stoch_at_high'] < df['prev_stoch_at_high'] - 8
        df['low_prev'] = df['low'].shift(1)
        df['low_prev2'] = df['low'].shift(2)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['is_price_high'] & df['price_higher'] & df['stoch_lower']
        df['entry_cond2'] = (df['low'] < df['low_prev']) & (df['low_prev'] < df['low_prev2'])
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
            reason='Stochastic Bearish Divergence + Lower Low',
        )