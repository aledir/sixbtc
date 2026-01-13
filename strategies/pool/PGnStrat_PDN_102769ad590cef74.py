"""
Pattern-Gen Strategy: Consolidation Density (mult0.7_period10)
Type: PDN (parametric)
Timeframe: 2h
Direction: long
Blocks: CONSOLIDATION_DENSITY
Generated: 2026-01-13T01:42:12.219822+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_PDN_102769ad590cef74(StrategyCore):
    """
    Pattern: Consolidation Density (mult0.7_period10)
    Direction: long
    Lookback: 35 bars
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
    LOOKBACK = 35

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.05
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

        Pattern: Consolidation Density (mult0.7_period10)
        Composition: parametric
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['hl_range'] = df['high'] - df['low']
        df['avg_range'] = df['hl_range'].rolling(20).mean()
        df['small_range'] = df['hl_range'] < df['avg_range'] * 0.7
        df['consol_days'] = df['small_range'].rolling(10).sum()
        df['tight_consol'] = df['consol_days'] >= 10 * 0.7
        df['breakout'] = df['close'] > df['close'].shift(1).rolling(5).max()

        # === ENTRY SIGNAL ===
        df['entry_signal'] = df['tight_consol'].shift(1) & df['breakout']

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
            reason='Consolidation Density (mult0.7_period10)',
        )