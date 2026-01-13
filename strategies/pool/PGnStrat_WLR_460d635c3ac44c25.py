"""
Pattern-Gen Strategy: Williams %R Exit Overbought + Volume Spike
Type: WLR (template)
Timeframe: 1h
Direction: short
Blocks: WILLR_EXIT_OVERBOUGHT, VOLUME_SPIKE
Generated: 2026-01-13T07:32:17.651768+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_WLR_460d635c3ac44c25(StrategyCore):
    """
    Pattern: Williams %R Exit Overbought + Volume Spike
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
    SL_PCT = 0.6
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 25

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Williams %R Exit Overbought + Volume Spike
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['willr'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod=14)
        df['was_overbought'] = df['willr'].shift(1) > -20
        df['now_below'] = df['willr'] <= -20
        df['vol_avg'] = df['volume'].rolling(50).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['was_overbought'] & df['now_below']
        df['entry_cond2'] = df['volume'] > df['vol_avg'] * 2.5
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
            reason='Williams %R Exit Overbought + Volume Spike',
        )