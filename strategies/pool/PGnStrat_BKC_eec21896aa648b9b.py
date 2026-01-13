"""
Pattern-Gen Strategy: Breakout with Volume (period20_vol_mult2.0)
Type: BKC (parametric)
Timeframe: 2h
Direction: long
Blocks: BREAKOUT_VOL_CONFIRM
Generated: 2026-01-13T09:02:32.503637+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_BKC_eec21896aa648b9b(StrategyCore):
    """
    Pattern: Breakout with Volume (period20_vol_mult2.0)
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
    SL_PCT = 0.8
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

        Pattern: Breakout with Volume (period20_vol_mult2.0)
        Composition: parametric
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['resistance'] = df['high'].rolling(20).max().shift(1)
        df['breakout'] = df['close'] > df['resistance']
        df['vol_avg'] = df['volume'].rolling(20).mean()
        df['vol_confirm'] = df['volume'] > df['vol_avg'] * 2.0

        # === ENTRY SIGNAL ===
        df['entry_signal'] = df['breakout'] & df['vol_confirm']

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
            reason='Breakout with Volume (period20_vol_mult2.0)',
        )