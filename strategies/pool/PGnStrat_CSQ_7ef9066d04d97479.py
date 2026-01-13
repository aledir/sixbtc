"""
Pattern-Gen Strategy: Morning Star + Volatility Expanding
Type: CSQ (template)
Timeframe: 2h
Direction: long
Blocks: MORNING_STAR, VOLATILITY_EXPANDING
Generated: 2026-01-13T08:13:36.005960+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_CSQ_7ef9066d04d97479(StrategyCore):
    """
    Pattern: Morning Star + Volatility Expanding
    Direction: long
    Lookback: 60 bars
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
    LOOKBACK = 60

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.4
    TP_PCT = 0.0
    LEVERAGE = 2
    exit_after_bars = 30

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Morning Star + Volatility Expanding
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['bear1'] = (df['close'].shift(2) < df['open'].shift(2)) & (abs(df['close'].shift(2) - df['open'].shift(2)) > (df['high'].shift(2) - df['low'].shift(2)) * 0.5)
        df['small2'] = abs(df['close'].shift(1) - df['open'].shift(1)) < (df['high'].shift(1) - df['low'].shift(1)) * 0.3
        df['bull3'] = (df['close'] > df['open']) & (abs(df['close'] - df['open']) > (df['high'] - df['low']) * 0.5)
        df['gap_down'] = df['open'].shift(1) < df['close'].shift(2)
        df['recovery'] = df['close'] > (df['open'].shift(2) + df['close'].shift(2)) / 2
        df['morning_star'] = df['bear1'] & df['small2'] & df['bull3'] & df['recovery']
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        df['atr_ma'] = df['atr'].rolling(50).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['morning_star']
        df['entry_cond2'] = df['atr'] > df['atr_ma'] * 1.0
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
            reason='Morning Star + Volatility Expanding',
        )