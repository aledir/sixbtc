"""
Pattern-Gen Strategy: Donchian Mid Cross Up + Volume Spike
Type: DON (template)
Timeframe: 2h
Direction: long
Blocks: DONCHIAN_MID_CROSS_UP, VOLUME_SPIKE
Generated: 2026-01-13T03:04:37.574917+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_DON_9f2a5af9dae340b0(StrategyCore):
    """
    Pattern: Donchian Mid Cross Up + Volume Spike
    Direction: long
    Lookback: 60 bars
    Execution: touch_based
    """

    # Direction
    direction = 'long'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Execution type for parametric optimization
    execution_type = 'touch_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 60

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

        Pattern: Donchian Mid Cross Up + Volume Spike
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['donch_high'] = df['high'].rolling(55).max()
        df['donch_low'] = df['low'].rolling(55).min()
        df['donch_mid'] = (df['donch_high'] + df['donch_low']) / 2
        df['above_mid'] = df['close'] > df['donch_mid']
        df['was_below'] = df['close'].shift(1) <= df['donch_mid'].shift(1)
        df['vol_avg'] = df['volume'].rolling(10).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['above_mid'] & df['was_below']
        df['entry_cond2'] = df['volume'] > df['vol_avg'] * 2.0
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
            reason='Donchian Mid Cross Up + Volume Spike',
        )