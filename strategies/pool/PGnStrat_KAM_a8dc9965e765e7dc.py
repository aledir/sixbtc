"""
Pattern-Gen Strategy: KAMA Slope Negative + Volume Dry Up + Williams %R Overbought
Type: KAM (template)
Timeframe: 1h
Direction: short
Blocks: KAMA_SLOPE_DOWN, VOLUME_DRY, WILLR_OVERBOUGHT
Generated: 2026-01-13T00:30:27.289261+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_KAM_a8dc9965e765e7dc(StrategyCore):
    """
    Pattern: KAMA Slope Negative + Volume Dry Up + Williams %R Overbought
    Direction: short
    Lookback: 40 bars
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
    LOOKBACK = 40

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.24
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

        Pattern: KAMA Slope Negative + Volume Dry Up + Williams %R Overbought
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['kama'] = ta.KAMA(df['close'], timeperiod=20)
        df['kama_slope'] = df['kama'] - df['kama'].shift(5)
        df['vol_avg'] = df['volume'].rolling(10).mean()
        df['willr'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod=14)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['kama_slope'] < 0
        df['entry_cond2'] = df['volume'] < df['vol_avg'] * 0.7
        df['entry_cond3'] = df['willr'] > -10
        df['entry_signal'] = df['entry_cond1'] & df['entry_cond2'] & df['entry_cond3']

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
            reason='KAMA Slope Negative + Volume Dry Up + Williams %R Overbought',
        )