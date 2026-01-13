"""
Pattern-Gen Strategy: Swing High Retest + Volume Breakout Down
Type: SWG (template)
Timeframe: 2h
Direction: short
Blocks: SWING_HIGH_RETEST, VOLUME_BREAKOUT_DOWN
Generated: 2026-01-13T03:15:58.980607+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_SWG_32d24d821826a451(StrategyCore):
    """
    Pattern: Swing High Retest + Volume Breakout Down
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
    SL_PCT = 0.3
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 20

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Swing High Retest + Volume Breakout Down
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['swing_high'] = df['high'].rolling(20).max()
        df['near_swing'] = abs(df['high'] - df['swing_high'].shift(1)) / df['close'] < 0.01
        df['rejected'] = df['close'] < df['open']
        df['vol_avg'] = df['volume'].rolling(20).mean()
        df['close_chg'] = df['close'].pct_change()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['near_swing'] & df['rejected']
        df['entry_cond2'] = (df['volume'] > df['vol_avg'] * 3.0) & (df['close_chg'] < 0)
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
            reason='Swing High Retest + Volume Breakout Down',
        )