"""
Pattern-Gen Strategy: Expansion After Squeeze (contract_mult0.5_expand_mult1.5_period20)
Type: EXC (parametric)
Timeframe: 1h
Direction: long
Blocks: EXPANSION_AFTER_SQUEEZE
Generated: 2026-01-13T01:00:08.904549+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_EXC_25f6b8bbcc28c855(StrategyCore):
    """
    Pattern: Expansion After Squeeze (contract_mult0.5_expand_mult1.5_period20)
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
    SL_PCT = 0.4
    TP_PCT = 0.0
    LEVERAGE = 2
    exit_after_bars = 50

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Expansion After Squeeze (contract_mult0.5_expand_mult1.5_period20)
        Composition: parametric
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['bar_range'] = df['high'] - df['low']
        df['range_avg'] = df['bar_range'].rolling(20).mean()
        df['was_contracted'] = df['bar_range'].shift(1) < df['range_avg'].shift(1) * 0.5
        df['now_expanded'] = df['bar_range'] > df['range_avg'] * 1.5
        df['bullish'] = df['close'] > df['open']

        # === ENTRY SIGNAL ===
        df['entry_signal'] = df['was_contracted'] & df['now_expanded'] & df['bullish']

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
            reason='Expansion After Squeeze (contract_mult0.5_expand_mult1.5_period20)',
        )