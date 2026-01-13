"""
Pattern-Gen Strategy: Klinger Oscillator Negative + RSI Overbought
Type: KLG (template)
Timeframe: 2h
Direction: short
Blocks: KLINGER_NEGATIVE, RSI_OVERBOUGHT
Generated: 2026-01-13T04:47:23.351463+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_KLG_074ef9b0a87adef2(StrategyCore):
    """
    Pattern: Klinger Oscillator Negative + RSI Overbought
    Direction: short
    Lookback: 70 bars
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
    LOOKBACK = 70

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.24
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 40

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Klinger Oscillator Negative + RSI Overbought
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['hlc'] = df['high'] + df['low'] + df['close']
        df['trend'] = (df['hlc'] > df['hlc'].shift(1)).astype(int) * 2 - 1
        df['dm'] = df['high'] - df['low']
        df['cm'] = df['dm'].where(df['trend'] == df['trend'].shift(1), df['dm'] + df['dm'].shift(1))
        df['vf'] = df['volume'] * df['trend'] * (2 * df['dm'] / df['cm'] - 1).abs() * 100
        df['kvo'] = ta.EMA(df['vf'], timeperiod=34) - ta.EMA(df['vf'], timeperiod=55)
        df['rsi'] = ta.RSI(df['close'], timeperiod=7)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['kvo'] < -0
        df['entry_cond2'] = df['rsi'] > 70
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
            reason='Klinger Oscillator Negative + RSI Overbought',
        )