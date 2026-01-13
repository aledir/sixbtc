"""
Pattern-Gen Strategy: Trailing Stop Trigger + Volume Above Average
Type: EXS (template)
Timeframe: 2h
Direction: short
Blocks: TRAIL_STOP_TRIGGER, VOLUME_ABOVE_AVERAGE
Generated: 2026-01-13T02:14:13.739383+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_EXS_89534cf7cffd722a(StrategyCore):
    """
    Pattern: Trailing Stop Trigger + Volume Above Average
    Direction: short
    Lookback: 50 bars
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
    LOOKBACK = 50

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.6
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

        Pattern: Trailing Stop Trigger + Volume Above Average
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        df['high_since'] = df['high'].rolling(10).max()
        df['trail_stop'] = df['high_since'] - df['atr'] * 3.0
        df['stop_hit'] = df['close'] < df['trail_stop']
        df['was_profit'] = df['high_since'] > df['close'].shift(10) * 1.02
        df['vol_ma'] = df['volume'].rolling(20).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['stop_hit'] & df['was_profit']
        df['entry_cond2'] = df['volume'] > df['vol_ma'] * 1.5
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
            reason='Trailing Stop Trigger + Volume Above Average',
        )