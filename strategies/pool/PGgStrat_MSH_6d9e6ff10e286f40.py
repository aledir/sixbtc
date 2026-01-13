"""
Pattern-Gen Strategy: Evolved: Momentum Flip Down (period10)
Type: MSH (genetic)
Timeframe: 2h
Direction: short
Blocks: MOM_FLIP_DOWN
Generated: 2026-01-13T07:30:53.275342+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGgStrat_MSH_6d9e6ff10e286f40(StrategyCore):
    """
    Pattern: Evolved: Momentum Flip Down (period10)
    Direction: short
    Lookback: 20 bars
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
    LOOKBACK = 20

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.4
    TP_PCT = 0.0
    LEVERAGE = 2
    exit_after_bars = 90

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Evolved: Momentum Flip Down (period10)
        Composition: genetic
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['mom'] = ta.MOM(df['close'], timeperiod=10)
        df['mom_negative'] = df['mom'] < 0
        df['mom_was_positive'] = df['mom'].shift(1) > 0

        # === ENTRY SIGNAL ===
        df['entry_signal'] = df['mom_negative'] & df['mom_was_positive']

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
            reason='Evolved: Momentum Flip Down (period10)',
        )