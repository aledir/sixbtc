"""
Pattern-Gen Strategy: Evolved: Institutional Volume (threshold2.0)
Type: SMB (genetic)
Timeframe: 2h
Direction: long
Blocks: INSTITUTIONAL_VOL
Generated: 2026-01-13T07:47:34.111196+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGgStrat_SMB_c80f4d5b0f170863(StrategyCore):
    """
    Pattern: Evolved: Institutional Volume (threshold2.0)
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
    SL_PCT = 0.18
    TP_PCT = 0.0
    LEVERAGE = 3
    exit_after_bars = 75

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Evolved: Institutional Volume (threshold2.0)
        Composition: genetic
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['vol_std'] = df['volume'].rolling(20).std()
        df['vol_zscore'] = (df['volume'] - df['vol_ma']) / df['vol_std']
        df['inst_vol'] = df['vol_zscore'] > 2.0
        df['bullish_bar'] = df['close'] > df['open']
        df['body_ratio'] = abs(df['close'] - df['open']) / (df['high'] - df['low'] + 0.0001)
        df['strong_body'] = df['body_ratio'] > 0.6

        # === ENTRY SIGNAL ===
        df['entry_signal'] = df['inst_vol'] & df['bullish_bar'] & df['strong_body']

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
            reason='Evolved: Institutional Volume (threshold2.0)',
        )