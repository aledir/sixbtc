"""
Pattern-Gen Strategy: Upper Wick Rejection (period20_threshold0.6)
Type: PRJ (parametric)
Timeframe: 2h
Direction: short
Blocks: UPPER_WICK_REJECT
Generated: 2026-01-13T07:29:10.678520+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_PRJ_ad32caff7748b141(StrategyCore):
    """
    Pattern: Upper Wick Rejection (period20_threshold0.6)
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
    SL_PCT = 0.18
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 50

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Upper Wick Rejection (period20_threshold0.6)
        Composition: parametric
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['upper_wick'] = df['high'] - df[['close', 'open']].max(axis=1)
        df['bar_range'] = df['high'] - df['low']
        df['wick_ratio'] = df['upper_wick'] / df['bar_range']
        df['at_resistance'] = df['high'] >= df['high'].rolling(20).max().shift(1) * 0.99

        # === ENTRY SIGNAL ===
        df['entry_signal'] = (df['wick_ratio'] > 0.6) & df['at_resistance']

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
            reason='Upper Wick Rejection (period20_threshold0.6)',
        )