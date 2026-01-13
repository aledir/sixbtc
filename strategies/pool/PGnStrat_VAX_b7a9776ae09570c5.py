"""
Pattern-Gen Strategy: Volume Reversal (mult2.5)
Type: VAX (parametric)
Timeframe: 2h
Direction: long
Blocks: VOL_REVERSAL
Generated: 2026-01-13T04:30:25.800309+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_VAX_b7a9776ae09570c5(StrategyCore):
    """
    Pattern: Volume Reversal (mult2.5)
    Direction: long
    Lookback: 30 bars
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
    LOOKBACK = 30

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.4
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

        Pattern: Volume Reversal (mult2.5)
        Composition: parametric
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['vol_spike'] = df['volume'] > df['volume'].rolling(20).mean() * 2.5
        df['price_down'] = df['close'].shift(1) < df['close'].shift(5)
        df['reversal'] = df['close'] > df['open']
        df['reclaim'] = df['close'] > df['close'].shift(1)

        # === ENTRY SIGNAL ===
        df['entry_signal'] = df['vol_spike'] & df['price_down'] & df['reversal'] & df['reclaim']

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
            reason='Volume Reversal (mult2.5)',
        )