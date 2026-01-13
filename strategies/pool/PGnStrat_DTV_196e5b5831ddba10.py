"""
Pattern-Gen Strategy: Volume Detrended Breakout + ROC Cross Zero Down
Type: DTV (template)
Timeframe: 2h
Direction: short
Blocks: VOL_BREAKOUT_DT, ROC_CROSS_ZERO_DOWN
Generated: 2026-01-13T02:31:48.453331+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_DTV_196e5b5831ddba10(StrategyCore):
    """
    Pattern: Volume Detrended Breakout + ROC Cross Zero Down
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
    SL_PCT = 0.12
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

        Pattern: Volume Detrended Breakout + ROC Cross Zero Down
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['vol_ma'] = ta.SMA(df['volume'], timeperiod=20)
        df['vol_detrend'] = df['volume'] - df['vol_ma']
        df['vol_std'] = df['vol_detrend'].rolling(20).std()
        df['breakout'] = df['vol_detrend'] > df['vol_std'] * 2.5
        df['roc'] = ta.ROC(df['close'], timeperiod=10)
        df['was_positive'] = df['roc'].shift(1) > 0
        df['now_negative'] = df['roc'] <= 0

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['breakout']
        df['entry_cond2'] = df['was_positive'] & df['now_negative']
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
            reason='Volume Detrended Breakout + ROC Cross Zero Down',
        )