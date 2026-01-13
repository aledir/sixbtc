"""
Pattern-Gen Strategy: A/D Bearish Divergence + Volume Above Average
Type: WAD (template)
Timeframe: 2h
Direction: short
Blocks: WAD_BEARISH_DIVERGENCE, VOLUME_ABOVE_AVERAGE
Generated: 2026-01-13T04:03:24.766970+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_WAD_ea0a1bc510854ccc(StrategyCore):
    """
    Pattern: A/D Bearish Divergence + Volume Above Average
    Direction: short
    Lookback: 60 bars
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
    LOOKBACK = 60

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.8
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 15

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: A/D Bearish Divergence + Volume Above Average
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['ad'] = ta.AD(df['high'], df['low'], df['close'], df['volume'])
        df['price_max'] = df['high'].rolling(10).max()
        df['is_price_high'] = df['high'] == df['price_max']
        df['ad_at_high'] = df['ad'].where(df['is_price_high']).ffill()
        df['prev_price_max'] = df['price_max'].shift(10)
        df['prev_ad_at_high'] = df['ad_at_high'].shift(10)
        df['price_higher'] = df['price_max'] > df['prev_price_max']
        df['ad_lower'] = df['ad_at_high'] < df['prev_ad_at_high']
        df['vol_ma'] = df['volume'].rolling(20).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['is_price_high'] & df['price_higher'] & df['ad_lower']
        df['entry_cond2'] = df['volume'] > df['vol_ma'] * 1.0
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
            reason='A/D Bearish Divergence + Volume Above Average',
        )