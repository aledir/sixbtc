"""
Pattern-Gen Strategy: RSI Bearish Divergence (lookback30_period21_threshold8)
Type: DIV (parametric)
Timeframe: 2h
Direction: short
Blocks: RSI_BEARISH_DIVERGENCE
Generated: 2026-01-13T12:36:34.092152+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_DIV_73cd934d81289399(StrategyCore):
    """
    Pattern: RSI Bearish Divergence (lookback30_period21_threshold8)
    Direction: short
    Lookback: 80 bars
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
    LOOKBACK = 80

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.4
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 15

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: RSI Bearish Divergence (lookback30_period21_threshold8)
        Composition: parametric
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['rsi'] = ta.RSI(df['close'], timeperiod=21)
        df['price_max'] = df['high'].rolling(30).max()
        df['is_price_high'] = df['high'] == df['price_max']
        df['rsi_at_high'] = df['rsi'].where(df['is_price_high']).ffill()
        df['prev_price_max'] = df['price_max'].shift(30)
        df['prev_rsi_at_high'] = df['rsi_at_high'].shift(30)
        df['price_higher'] = df['price_max'] > df['prev_price_max']
        df['rsi_lower'] = df['rsi_at_high'] < df['prev_rsi_at_high'] - 8

        # === ENTRY SIGNAL ===
        df['entry_signal'] = df['is_price_high'] & df['price_higher'] & df['rsi_lower']

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
            reason='RSI Bearish Divergence (lookback30_period21_threshold8)',
        )