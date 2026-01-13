"""
Pattern-Gen Strategy: Contraction Setup + Williams %R Overbought
Type: EXC (template)
Timeframe: 30m
Direction: short
Blocks: CONTRACTION_SETUP, WILLR_OVERBOUGHT
Generated: 2026-01-13T08:48:25.060924+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_EXC_ddc972f02ebe7079(StrategyCore):
    """
    Pattern: Contraction Setup + Williams %R Overbought
    Direction: short
    Lookback: 30 bars
    Execution: close_based
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '30m'

    # Execution type for parametric optimization
    execution_type = 'close_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 30

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.3
    TP_PCT = 0.0
    LEVERAGE = 2
    exit_after_bars = 60

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Contraction Setup + Williams %R Overbought
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['bar_range'] = df['high'] - df['low']
        df['range_avg'] = df['bar_range'].rolling(20).mean()
        df['contracted'] = df['bar_range'] < df['range_avg'] * 0.6
        df['consec_contract'] = df['contracted'].rolling(3).sum() >= 3
        df['willr'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod=21)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['consec_contract']
        df['entry_cond2'] = df['willr'] > -15
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
            reason='Contraction Setup + Williams %R Overbought',
        )