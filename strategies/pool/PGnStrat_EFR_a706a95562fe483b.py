"""
Pattern-Gen Strategy: Efficiency Low to High + Momentum Oversold
Type: EFR (template)
Timeframe: 2h
Direction: long
Blocks: ER_LOW_TO_HIGH, MOM_OVERSOLD
Generated: 2026-01-13T04:18:56.688108+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_EFR_a706a95562fe483b(StrategyCore):
    """
    Pattern: Efficiency Low to High + Momentum Oversold
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
    SL_PCT = 0.6
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

        Pattern: Efficiency Low to High + Momentum Oversold
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['change'] = abs(df['close'] - df['close'].shift(10))
        df['volatility'] = abs(df['close'] - df['close'].shift(1)).rolling(10).sum()
        df['er'] = df['change'] / (df['volatility'] + 1e-10)
        df['was_low'] = df['er'].shift(3) < 0.2
        df['now_high'] = df['er'] > 0.5
        df['mom'] = ta.MOM(df['close'], timeperiod=14)
        df['mom_pct'] = df['mom'] / df['close'].shift(14) * 100

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['was_low'] & df['now_high']
        df['entry_cond2'] = df['mom_pct'] < -7
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
            reason='Efficiency Low to High + Momentum Oversold',
        )