"""
Pattern-Gen Strategy: Evolved: A/D Bearish Divergence + Price Far Above VWAP
Type: WAD (genetic)
Timeframe: 30m
Direction: short
Blocks: WAD_BEARISH_DIVERGENCE, VWAP_DEVIATION_SHORT
Generated: 2026-01-13T13:59:43.987100+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGgStrat_WAD_1d98497dde949d11(StrategyCore):
    """
    Pattern: Evolved: A/D Bearish Divergence + Price Far Above VWAP
    Direction: short
    Lookback: 60 bars
    Execution: touch_based
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '30m'

    # Execution type for parametric optimization
    execution_type = 'touch_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 60

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.06
    TP_PCT = 0.1
    LEVERAGE = 1
    exit_after_bars = 60

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Evolved: A/D Bearish Divergence + Price Far Above VWAP
        Composition: genetic
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['ad'] = ta.AD(df['high'], df['low'], df['close'], df['volume'])
        df['price_max'] = df['high'].rolling(20).max()
        df['is_price_high'] = df['high'] == df['price_max']
        df['ad_at_high'] = df['ad'].where(df['is_price_high']).ffill()
        df['prev_price_max'] = df['price_max'].shift(20)
        df['prev_ad_at_high'] = df['ad_at_high'].shift(20)
        df['price_higher'] = df['price_max'] > df['prev_price_max']
        df['ad_lower'] = df['ad_at_high'] < df['prev_ad_at_high']
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
        df['vwap_dev'] = (df['close'] - df['vwap']) / df['vwap']

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['is_price_high'] & df['price_higher'] & df['ad_lower']
        df['entry_cond2'] = df['vwap_dev'] > 0.01
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
            reason='Evolved: A/D Bearish Divergence + Price Far Above VWAP',
        )