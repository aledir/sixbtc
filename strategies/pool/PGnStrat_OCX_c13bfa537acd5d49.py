"""
Pattern-Gen Strategy: CCI Zero Cross + Volatility Expanding
Type: OCX (template)
Timeframe: 2h
Direction: long
Blocks: CCI_ZERO_CROSS, VOLATILITY_EXPANDING
Generated: 2026-01-13T04:49:18.034431+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_OCX_c13bfa537acd5d49(StrategyCore):
    """
    Pattern: CCI Zero Cross + Volatility Expanding
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
    SL_PCT = 0.8
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 30

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: CCI Zero Cross + Volatility Expanding
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod=20)
        df['cross_up'] = (df['cci'] > 0) & (df['cci'].shift(1) <= 0)
        df['was_oversold'] = df['cci'].shift(3) < -50
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        df['atr_ma'] = df['atr'].rolling(50).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['cross_up'] & df['was_oversold']
        df['entry_cond2'] = df['atr'] > df['atr_ma'] * 1.2
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
            reason='CCI Zero Cross + Volatility Expanding',
        )