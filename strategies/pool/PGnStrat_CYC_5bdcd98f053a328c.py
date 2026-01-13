"""
Pattern-Gen Strategy: Cycle High + Not Oversold (RSI > threshold)
Type: CYC (template)
Timeframe: 2h
Direction: short
Blocks: CYCLE_HIGH, NOT_OVERSOLD
Generated: 2026-01-13T00:37:04.175842+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_CYC_5bdcd98f053a328c(StrategyCore):
    """
    Pattern: Cycle High + Not Oversold (RSI > threshold)
    Direction: short
    Lookback: 40 bars
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
    LOOKBACK = 40

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.24
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 60

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Cycle High + Not Oversold (RSI > threshold)
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['rsi'] = ta.RSI(df['close'], timeperiod=14)
        df['rsi_high'] = df['rsi'].rolling(30).max()
        df['at_cycle_high'] = df['rsi'] >= df['rsi_high'] * 0.95
        df['turning'] = df['rsi'] < df['rsi'].shift(1)
        df['price_resist'] = df['close'] < df['high'].rolling(10).max()
        df['rsi_filter'] = ta.RSI(df['close'], timeperiod=14)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['at_cycle_high'] & df['turning'] & df['price_resist']
        df['entry_cond2'] = df['rsi_filter'] > 35
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
            reason='Cycle High + Not Oversold (RSI > threshold)',
        )