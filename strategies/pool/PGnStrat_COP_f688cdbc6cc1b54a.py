"""
Pattern-Gen Strategy: Coppock Curve Cross Zero Down + Volume Breakout Down
Type: COP (template)
Timeframe: 1h
Direction: short
Blocks: COPPOCK_CROSS_DOWN, VOLUME_BREAKOUT_DOWN
Generated: 2026-01-13T02:42:56.811425+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_COP_f688cdbc6cc1b54a(StrategyCore):
    """
    Pattern: Coppock Curve Cross Zero Down + Volume Breakout Down
    Direction: short
    Lookback: 50 bars
    Execution: close_based
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Execution type for parametric optimization
    execution_type = 'close_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 50

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.05
    TP_PCT = 0.1
    LEVERAGE = 1
    exit_after_bars = 20

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Coppock Curve Cross Zero Down + Volume Breakout Down
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['roc_long'] = ta.ROC(df['close'], timeperiod=14)
        df['roc_short'] = ta.ROC(df['close'], timeperiod=11)
        df['coppock'] = ta.WMA(df['roc_long'] + df['roc_short'], timeperiod=10)
        df['coppock_negative'] = df['coppock'] < 0
        df['was_positive'] = df['coppock'].shift(1) >= 0
        df['vol_avg'] = df['volume'].rolling(20).mean()
        df['close_chg'] = df['close'].pct_change()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['coppock_negative'] & df['was_positive']
        df['entry_cond2'] = (df['volume'] > df['vol_avg'] * 2.5) & (df['close_chg'] < 0)
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
            reason='Coppock Curve Cross Zero Down + Volume Breakout Down',
        )