"""
Pattern-Gen Strategy: Evolved: Swing High Retest + Price Cross Below VWAP
Type: SWG (genetic)
Timeframe: 2h
Direction: short
Blocks: SWING_HIGH_RETEST, VWAP_CROSS_DOWN
Generated: 2026-01-13T05:17:29.110542+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGgStrat_SWG_b9c440c8af538357(StrategyCore):
    """
    Pattern: Evolved: Swing High Retest + Price Cross Below VWAP
    Direction: short
    Lookback: 30 bars
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
    LOOKBACK = 30

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.8
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 45

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Evolved: Swing High Retest + Price Cross Below VWAP
        Composition: genetic
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['swing_high'] = df['high'].rolling(20).max()
        df['near_swing'] = abs(df['high'] - df['swing_high'].shift(1)) / df['close'] < 0.01
        df['rejected'] = df['close'] < df['open']
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
        df['below_vwap'] = df['close'] < df['vwap']
        df['was_above'] = df['close'].shift(1) >= df['vwap'].shift(1)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['near_swing'] & df['rejected']
        df['entry_cond2'] = df['below_vwap'] & df['was_above']
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
            reason='Evolved: Swing High Retest + Price Cross Below VWAP',
        )