"""
Pattern-Gen Strategy: Evolved: CCI Bearish Divergence + Low Volume Breakout Setup
Type: DIV (genetic)
Timeframe: 1h
Direction: short
Blocks: CCI_BEARISH_DIVERGENCE, LOW_VOL_BREAKOUT_SETUP
Generated: 2026-01-13T05:32:35.835736+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGgStrat_DIV_57d3f28a5f655a74(StrategyCore):
    """
    Pattern: Evolved: CCI Bearish Divergence + Low Volume Breakout Setup
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
    SL_PCT = 0.05
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 100

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Evolved: CCI Bearish Divergence + Low Volume Breakout Setup
        Composition: genetic
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod=20)
        df['price_max'] = df['high'].rolling(20).max()
        df['is_price_high'] = df['high'] == df['price_max']
        df['cci_at_high'] = df['cci'].where(df['is_price_high']).ffill()
        df['prev_price_max'] = df['price_max'].shift(20)
        df['prev_cci_at_high'] = df['cci_at_high'].shift(20)
        df['price_higher'] = df['price_max'] > df['prev_price_max']
        df['cci_lower'] = df['cci_at_high'] < df['prev_cci_at_high'] - 30
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['low_vol'] = df['volume'] < df['vol_ma'] * 0.7
        df['low_vol_days'] = df['low_vol'].rolling(3).sum() >= 2
        df['range_tight'] = (df['high'].rolling(3).max() - df['low'].rolling(3).min()) / df['close'] < 0.02

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['is_price_high'] & df['price_higher'] & df['cci_lower']
        df['entry_cond2'] = df['low_vol_days'] & df['range_tight']
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
            reason='Evolved: CCI Bearish Divergence + Low Volume Breakout Setup',
        )