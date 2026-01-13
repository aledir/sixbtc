"""
Pattern-Gen Strategy: Trending Regime + Volume Breakout Up
Type: MRG (template)
Timeframe: 1h
Direction: long
Blocks: TRENDING_REGIME, VOLUME_BREAKOUT_UP
Generated: 2026-01-13T04:53:04.265317+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_MRG_72d105dcebe96eed(StrategyCore):
    """
    Pattern: Trending Regime + Volume Breakout Up
    Direction: long
    Lookback: 30 bars
    Execution: close_based
    """

    # Direction
    direction = 'long'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Execution type for parametric optimization
    execution_type = 'close_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 30

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.1
    TP_PCT = 0.2
    LEVERAGE = 1
    exit_after_bars = 16

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Trending Regime + Volume Breakout Up
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
        df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
        df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
        df['trending'] = df['adx'] > 30
        df['bullish_trend'] = df['plus_di'] > df['minus_di']
        df['adx_rising'] = df['adx'] > df['adx'].shift(3)
        df['vol_avg'] = df['volume'].rolling(20).mean()
        df['close_chg'] = df['close'].pct_change()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['trending'] & df['bullish_trend'] & df['adx_rising']
        df['entry_cond2'] = (df['volume'] > df['vol_avg'] * 2.5) & (df['close_chg'] > 0)
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
            reason='Trending Regime + Volume Breakout Up',
        )