"""
Pattern-Gen Strategy: Bullish Impulse Pullback + ADX Trending Market
Type: IMP (template)
Timeframe: 2h
Direction: long
Blocks: IMPULSE_PULLBACK_BULL, ADX_TRENDING
Generated: 2026-01-13T07:23:05.103509+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_IMP_6f2de8cc16506011(StrategyCore):
    """
    Pattern: Bullish Impulse Pullback + ADX Trending Market
    Direction: long
    Lookback: 40 bars
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
    LOOKBACK = 40

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

        Pattern: Bullish Impulse Pullback + ADX Trending Market
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['impulse_move'] = df['close'].shift(3) - df['close'].shift(10)
        df['impulse_pct'] = df['impulse_move'] / df['close'].shift(10) * 100
        df['had_impulse'] = df['impulse_pct'] > 3
        df['pullback'] = df['close'] < df['close'].shift(3)
        df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['had_impulse'] & df['pullback']
        df['entry_cond2'] = df['adx'] > 30
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
            reason='Bullish Impulse Pullback + ADX Trending Market',
        )