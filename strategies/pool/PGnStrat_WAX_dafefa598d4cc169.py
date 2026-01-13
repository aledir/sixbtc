"""
Pattern-Gen Strategy: Williams AD Rising + Momentum Oversold
Type: WAX (template)
Timeframe: 2h
Direction: long
Blocks: WAD_RISING, MOM_OVERSOLD
Generated: 2026-01-13T08:22:54.304522+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_WAX_dafefa598d4cc169(StrategyCore):
    """
    Pattern: Williams AD Rising + Momentum Oversold
    Direction: long
    Lookback: 30 bars
    Execution: touch_based
    """

    # Direction
    direction = 'long'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Execution type for parametric optimization
    execution_type = 'touch_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 30

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.04
    TP_PCT = 0.06
    LEVERAGE = 1
    exit_after_bars = 0

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Williams AD Rising + Momentum Oversold
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['trh'] = np.maximum(df['high'], df['close'].shift(1))
        df['trl'] = np.minimum(df['low'], df['close'].shift(1))
        df['ad'] = np.where(df['close'] > df['close'].shift(1), df['close'] - df['trl'], np.where(df['close'] < df['close'].shift(1), df['close'] - df['trh'], 0))
        df['wad'] = df['ad'].cumsum()
        df['wad_ma'] = df['wad'].rolling(20).mean()
        df['rising'] = df['wad'] > df['wad_ma']
        df['wad_up'] = df['wad'] > df['wad'].shift(3)
        df['mom'] = ta.MOM(df['close'], timeperiod=20)
        df['mom_pct'] = df['mom'] / df['close'].shift(20) * 100

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['rising'] & df['wad_up']
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
            reason='Williams AD Rising + Momentum Oversold',
        )