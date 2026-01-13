"""
Pattern-Gen Strategy: Evolved: Trending Regime + Contraction Alert
Type: MRG (genetic)
Timeframe: 2h
Direction: long
Blocks: TRENDING_REGIME, CONTRACTION_ALERT
Generated: 2026-01-13T12:32:57.947462+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGgStrat_MRG_5774ae360c466b04(StrategyCore):
    """
    Pattern: Evolved: Trending Regime + Contraction Alert
    Direction: long
    Lookback: 60 bars
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
    LOOKBACK = 60

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.1
    TP_PCT = 0.12
    LEVERAGE = 1
    exit_after_bars = 12

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Evolved: Trending Regime + Contraction Alert
        Composition: genetic
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
        df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
        df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
        df['trending'] = df['adx'] > 30
        df['bullish_trend'] = df['plus_di'] > df['minus_di']
        df['adx_rising'] = df['adx'] > df['adx'].shift(3)
        df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
        df['width_pct'] = df['bb_width'].rolling(50).apply(lambda x: (x.iloc[-1] < x).sum() / len(x) * 100, raw=False)
        df['extreme_contraction'] = df['width_pct'] < 20

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['trending'] & df['bullish_trend'] & df['adx_rising']
        df['entry_cond2'] = df['extreme_contraction']
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
            reason='Evolved: Trending Regime + Contraction Alert',
        )