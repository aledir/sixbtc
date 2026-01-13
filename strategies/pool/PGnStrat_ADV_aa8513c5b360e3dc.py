"""
Pattern-Gen Strategy: Failed Breakout (Sell the Rip) + Volume Spike + Volume Breakout Down
Type: ADV (template)
Timeframe: 1h
Direction: short
Blocks: FAILED_BREAKOUT_SHORT, VOLUME_SPIKE, VOLUME_BREAKOUT_DOWN
Generated: 2026-01-13T07:44:20.166009+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_ADV_aa8513c5b360e3dc(StrategyCore):
    """
    Pattern: Failed Breakout (Sell the Rip) + Volume Spike + Volume Breakout Down
    Direction: short
    Lookback: 50 bars
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
    LOOKBACK = 50

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

        Pattern: Failed Breakout (Sell the Rip) + Volume Spike + Volume Breakout Down
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['resistance'] = df['high'].rolling(20).max().shift(1)
        df['broke_resistance'] = df['high'].shift(1) > df['resistance'].shift(1)
        df['rejected'] = df['close'] < df['resistance']
        df['vol_avg'] = df['volume'].rolling(50).mean()
        df['vol_avg'] = df['volume'].rolling(20).mean()
        df['close_chg'] = df['close'].pct_change()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['broke_resistance'] & df['rejected']
        df['entry_cond2'] = df['volume'] > df['vol_avg'] * 3.0
        df['entry_cond3'] = (df['volume'] > df['vol_avg'] * 2.0) & (df['close_chg'] < 0)
        df['entry_signal'] = df['entry_cond1'] & df['entry_cond2'] & df['entry_cond3']

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
            reason='Failed Breakout (Sell the Rip) + Volume Spike + Volume Breakout Down',
        )