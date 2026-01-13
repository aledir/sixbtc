"""
Pattern-Gen Strategy: Low Volume Breakout Setup + MFI Overbought
Type: VPR (template)
Timeframe: 1h
Direction: short
Blocks: LOW_VOL_BREAKOUT_SETUP, MFI_OVERBOUGHT
Generated: 2026-01-13T07:03:50.440958+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_VPR_74a76c2b6817663d(StrategyCore):
    """
    Pattern: Low Volume Breakout Setup + MFI Overbought
    Direction: short
    Lookback: 30 bars
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
    LOOKBACK = 30

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.06
    TP_PCT = 0.1
    LEVERAGE = 1
    exit_after_bars = 0

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Low Volume Breakout Setup + MFI Overbought
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['low_vol'] = df['volume'] < df['vol_ma'] * 0.7
        df['low_vol_days'] = df['low_vol'].rolling(3).sum() >= 2
        df['range_tight'] = (df['high'].rolling(3).max() - df['low'].rolling(3).min()) / df['close'] < 0.02
        df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['low_vol_days'] & df['range_tight']
        df['entry_cond2'] = df['mfi'] > 80
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
            reason='Low Volume Breakout Setup + MFI Overbought',
        )