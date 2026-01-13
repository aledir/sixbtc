"""
Pattern-Gen Strategy: Contraction Alert + Volume Breakout Up
Type: VRE (template)
Timeframe: 2h
Direction: long
Blocks: CONTRACTION_ALERT, VOLUME_BREAKOUT_UP
Generated: 2026-01-13T06:24:50.411734+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_VRE_6b1011ab37b83642(StrategyCore):
    """
    Pattern: Contraction Alert + Volume Breakout Up
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
    SL_PCT = 0.1
    TP_PCT = 0.15
    LEVERAGE = 1
    exit_after_bars = 32

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Contraction Alert + Volume Breakout Up
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
        df['width_pct'] = df['bb_width'].rolling(50).apply(lambda x: (x.iloc[-1] < x).sum() / len(x) * 100, raw=False)
        df['extreme_contraction'] = df['width_pct'] < 10
        df['vol_avg'] = df['volume'].rolling(20).mean()
        df['close_chg'] = df['close'].pct_change()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['extreme_contraction']
        df['entry_cond2'] = (df['volume'] > df['vol_avg'] * 3.0) & (df['close_chg'] > 0)
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
            reason='Contraction Alert + Volume Breakout Up',
        )