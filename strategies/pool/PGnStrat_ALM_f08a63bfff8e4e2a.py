"""
Pattern-Gen Strategy: ALMA Trend Up + CCI Oversold
Type: ALM (template)
Timeframe: 2h
Direction: long
Blocks: ALMA_TREND, CCI_OVERSOLD
Generated: 2026-01-12T23:55:20.967449+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_ALM_f08a63bfff8e4e2a(StrategyCore):
    """
    Pattern: ALMA Trend Up + CCI Oversold
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
    SL_PCT = 0.06
    TP_PCT = 0.1
    LEVERAGE = 1
    exit_after_bars = 6

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: ALMA Trend Up + CCI Oversold
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        m = 0.85 * (9 - 1)
        s = 9 / 6
        weights = np.exp(-((np.arange(9) - m) ** 2) / (2 * s * s))
        weights = weights / weights.sum()
        df['alma'] = df['close'].rolling(9).apply(lambda x: np.sum(weights * x), raw=True)
        df['above'] = df['close'] > df['alma']
        df['alma_rising'] = df['alma'] > df['alma'].shift(3)
        df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod=20)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['above'] & df['alma_rising']
        df['entry_cond2'] = df['cci'] < -80
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
            reason='ALMA Trend Up + CCI Oversold',
        )