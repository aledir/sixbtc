"""
Pattern-Gen Strategy: Evolved: Coppock Curve Cross Zero Down + Contraction Alert
Type: COP (genetic)
Timeframe: 15m
Direction: short
Blocks: COPPOCK_CROSS_DOWN, CONTRACTION_ALERT
Generated: 2026-01-13T13:51:58.677773+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGgStrat_COP_a1f9a1078c9c317c(StrategyCore):
    """
    Pattern: Evolved: Coppock Curve Cross Zero Down + Contraction Alert
    Direction: short
    Lookback: 60 bars
    Execution: close_based
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '15m'

    # Execution type for parametric optimization
    execution_type = 'close_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 60

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.32
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

        Pattern: Evolved: Coppock Curve Cross Zero Down + Contraction Alert
        Composition: genetic
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['roc_long'] = ta.ROC(df['close'], timeperiod=14)
        df['roc_short'] = ta.ROC(df['close'], timeperiod=11)
        df['coppock'] = ta.WMA(df['roc_long'] + df['roc_short'], timeperiod=10)
        df['coppock_negative'] = df['coppock'] < 0
        df['was_positive'] = df['coppock'].shift(1) >= 0
        df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
        df['width_pct'] = df['bb_width'].rolling(50).apply(lambda x: (x.iloc[-1] < x).sum() / len(x) * 100, raw=False)
        df['extreme_contraction'] = df['width_pct'] < 20

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['coppock_negative'] & df['was_positive']
        df['entry_cond2'] = df['extreme_contraction']
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
            reason='Evolved: Coppock Curve Cross Zero Down + Contraction Alert',
        )