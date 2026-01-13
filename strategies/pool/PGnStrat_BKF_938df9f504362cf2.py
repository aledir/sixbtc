"""
Pattern-Gen Strategy: Volume Breakout Filter + ROC Cross Zero Up
Type: BKF (template)
Timeframe: 2h
Direction: long
Blocks: VOL_BREAKOUT_FILTER, ROC_CROSS_ZERO_UP
Generated: 2026-01-13T04:53:11.478912+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_BKF_938df9f504362cf2(StrategyCore):
    """
    Pattern: Volume Breakout Filter + ROC Cross Zero Up
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

        Pattern: Volume Breakout Filter + ROC Cross Zero Up
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['high_20'] = df['high'].rolling(20).max()
        df['breakout'] = df['close'] > df['high_20'].shift(1)
        df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
        df['body_strong'] = (df['close'] - df['open']) > (df['high'] - df['low']) * 0.5
        df['roc'] = ta.ROC(df['close'], timeperiod=10)
        df['was_negative'] = df['roc'].shift(1) < 0
        df['now_positive'] = df['roc'] >= 0

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['breakout'] & df['vol_confirm'] & df['body_strong']
        df['entry_cond2'] = df['was_negative'] & df['now_positive']
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
            reason='Volume Breakout Filter + ROC Cross Zero Up',
        )