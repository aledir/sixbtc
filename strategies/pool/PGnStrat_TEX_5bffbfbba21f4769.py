"""
Pattern-Gen Strategy: Overextended Up with Divergence + Volume Dry Up
Type: TEX (template)
Timeframe: 1h
Direction: short
Blocks: OVEREXT_UP_DIV, VOLUME_DRY
Generated: 2026-01-13T09:21:57.868490+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_TEX_5bffbfbba21f4769(StrategyCore):
    """
    Pattern: Overextended Up with Divergence + Volume Dry Up
    Direction: short
    Lookback: 30 bars
    Execution: close_based
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Execution type for parametric optimization
    execution_type = 'close_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 30

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.06
    TP_PCT = 0.075
    LEVERAGE = 2
    exit_after_bars = 0

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Overextended Up with Divergence + Volume Dry Up
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['ma'] = ta.SMA(df['close'], timeperiod=20)
        df['distance'] = (df['close'] - df['ma']) / df['ma'] * 100
        df['overext'] = df['distance'] > 3
        df['rsi'] = ta.RSI(df['close'], timeperiod=14)
        df['rsi_div'] = df['rsi'] < df['rsi'].shift(5)
        df['vol_avg'] = df['volume'].rolling(10).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['overext'] & df['rsi_div']
        df['entry_cond2'] = df['volume'] < df['vol_avg'] * 0.5
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
            reason='Overextended Up with Divergence + Volume Dry Up',
        )