"""
Pattern-Gen Strategy: Evolved: Volume Spike + Trend + Momentum + Volume Short
Type: VOL (genetic)
Timeframe: 30m
Direction: short
Blocks: VOLUME_SPIKE, TREND_MOM_VOL_SHORT
Generated: 2026-01-13T06:04:59.020158+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGgStrat_VOL_4db0a82d40d00ca9(StrategyCore):
    """
    Pattern: Evolved: Volume Spike + Trend + Momentum + Volume Short
    Direction: short
    Lookback: 120 bars
    Execution: close_based
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '30m'

    # Execution type for parametric optimization
    execution_type = 'close_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 120

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.3
    TP_PCT = 0.0
    LEVERAGE = 2
    exit_after_bars = 90

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Evolved: Volume Spike + Trend + Momentum + Volume Short
        Composition: genetic
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['vol_avg'] = df['volume'].rolling(50).mean()
        df['ema'] = ta.EMA(df['close'], timeperiod=50)
        df['rsi'] = ta.RSI(df['close'], timeperiod=14)
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['trend_down'] = df['close'] < df['ema']
        df['momentum_ok'] = (df['rsi'] < 60) & (df['rsi'] > 35)
        df['volume_ok'] = df['volume'] > df['vol_ma'] * 1.0

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['volume'] > df['vol_avg'] * 3.0
        df['entry_cond2'] = df['trend_down'] & df['momentum_ok'] & df['volume_ok']
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
            reason='Evolved: Volume Spike + Trend + Momentum + Volume Short',
        )