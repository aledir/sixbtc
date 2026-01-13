"""
Pattern-Gen Strategy: Evolved: Price Cross Below VWAP ()
Type: VWP (genetic)
Timeframe: 2h
Direction: short
Blocks: VWAP_CROSS_DOWN
Generated: 2026-01-13T06:33:04.403027+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGgStrat_VWP_d4b296df661b6d86(StrategyCore):
    """
    Pattern: Evolved: Price Cross Below VWAP ()
    Direction: short
    Lookback: 20 bars
    Execution: touch_based
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Execution type for parametric optimization
    execution_type = 'touch_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 20

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.08
    TP_PCT = 0.12
    LEVERAGE = 3
    exit_after_bars = 0

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Evolved: Price Cross Below VWAP ()
        Composition: genetic
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
        df['below_vwap'] = df['close'] < df['vwap']
        df['was_above'] = df['close'].shift(1) >= df['vwap'].shift(1)

        # === ENTRY SIGNAL ===
        df['entry_signal'] = df['below_vwap'] & df['was_above']

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
            reason='Evolved: Price Cross Below VWAP ()',
        )