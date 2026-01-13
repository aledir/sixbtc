"""
Pattern-Gen Strategy: Structure Shift + ADX Trending Market
Type: PST (template)
Timeframe: 2h
Direction: long
Blocks: STRUCTURE_SHIFT, ADX_TRENDING
Generated: 2026-01-13T05:36:32.811671+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_PST_dbbe64f7402daf68(StrategyCore):
    """
    Pattern: Structure Shift + ADX Trending Market
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
    SL_PCT = 0.3
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

        Pattern: Structure Shift + ADX Trending Market
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['swing_high'] = df['high'].rolling(10).max()
        df['swing_low'] = df['low'].rolling(10).min()
        df['break_high'] = df['close'] > df['swing_high'].shift(1)
        df['was_downtrend'] = df['close'].shift(5) < df['close'].shift(10)
        df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
        df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=20)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['break_high'] & df['was_downtrend'] & df['vol_surge']
        df['entry_cond2'] = df['adx'] > 25
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
            reason='Structure Shift + ADX Trending Market',
        )