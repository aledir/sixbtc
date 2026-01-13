"""
Pattern-Gen Strategy: Consecutive Down Closes (bars3)
Type: TRP (parametric)
Timeframe: 2h
Direction: short
Blocks: CONSEC_DOWN_CLOSES
Generated: 2026-01-13T07:50:53.314386+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_TRP_80182aa18d551739(StrategyCore):
    """
    Pattern: Consecutive Down Closes (bars3)
    Direction: short
    Lookback: 15 bars
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
    LOOKBACK = 15

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.48
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 90

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Consecutive Down Closes (bars3)
        Composition: parametric
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['down_close'] = df['close'] < df['close'].shift(1)
        df['consec_down'] = df['down_close'].rolling(3).sum() >= 3

        # === ENTRY SIGNAL ===
        df['entry_signal'] = df['consec_down']

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
            reason='Consecutive Down Closes (bars3)',
        )