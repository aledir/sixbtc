"""
Pattern-Gen Strategy: Efficiency Ratio Rising + Rate of Change Oversold
Type: EFR (template)
Timeframe: 2h
Direction: long
Blocks: ER_RISING, ROC_OVERSOLD
Generated: 2026-01-13T12:29:32.147167+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_EFR_6e4c5a7d024193f9(StrategyCore):
    """
    Pattern: Efficiency Ratio Rising + Rate of Change Oversold
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
    SL_PCT = 0.1
    TP_PCT = 0.0
    LEVERAGE = 5
    exit_after_bars = 24

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Efficiency Ratio Rising + Rate of Change Oversold
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['change'] = abs(df['close'] - df['close'].shift(14))
        df['volatility'] = abs(df['close'] - df['close'].shift(1)).rolling(14).sum()
        df['er'] = df['change'] / (df['volatility'] + 1e-10)
        df['er_rising'] = df['er'] > df['er'].shift(3)
        df['er_above_mid'] = df['er'] > 0.3
        df['roc'] = ta.ROC(df['close'], timeperiod=20)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['er_rising'] & df['er_above_mid']
        df['entry_cond2'] = df['roc'] < -15
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
            reason='Efficiency Ratio Rising + Rate of Change Oversold',
        )