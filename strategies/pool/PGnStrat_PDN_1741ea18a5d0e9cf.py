"""
Pattern-Gen Strategy: Price Clustering + Rate of Change Oversold
Type: PDN (template)
Timeframe: 2h
Direction: long
Blocks: PRICE_CLUSTERING, ROC_OVERSOLD
Generated: 2026-01-13T06:29:35.779091+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_PDN_1741ea18a5d0e9cf(StrategyCore):
    """
    Pattern: Price Clustering + Rate of Change Oversold
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
    SL_PCT = 0.24
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

        Pattern: Price Clustering + Rate of Change Oversold
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['range'] = df['high'].rolling(10).max() - df['low'].rolling(10).min()
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        df['density'] = df['range'] / (df['atr'] * 10)
        df['tight'] = df['density'] < 2.0
        df['break_up'] = df['close'] > df['high'].shift(1).rolling(5).max()
        df['roc'] = ta.ROC(df['close'], timeperiod=20)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['tight'].shift(1) & df['break_up']
        df['entry_cond2'] = df['roc'] < -5
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
            reason='Price Clustering + Rate of Change Oversold',
        )