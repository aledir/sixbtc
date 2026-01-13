"""
Pattern-Gen Strategy: Vortex Bearish Cross + Volume Dry Up
Type: VTX (template)
Timeframe: 2h
Direction: short
Blocks: VORTEX_BEAR_CROSS, VOLUME_DRY
Generated: 2026-01-13T09:29:05.266216+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_VTX_845dea647f663734(StrategyCore):
    """
    Pattern: Vortex Bearish Cross + Volume Dry Up
    Direction: short
    Lookback: 30 bars
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
    LOOKBACK = 30

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.05
    TP_PCT = 0.1
    LEVERAGE = 1
    exit_after_bars = 100

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Vortex Bearish Cross + Volume Dry Up
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
        df['vmp'] = abs(df['high'] - df['low'].shift(1))
        df['vmm'] = abs(df['low'] - df['high'].shift(1))
        df['vmp_sum'] = df['vmp'].rolling(21).sum()
        df['vmm_sum'] = df['vmm'].rolling(21).sum()
        df['tr_sum'] = df['tr'].rolling(21).sum()
        df['vip'] = df['vmp_sum'] / df['tr_sum']
        df['vim'] = df['vmm_sum'] / df['tr_sum']
        df['cross_down'] = (df['vip'] < df['vim']) & (df['vip'].shift(1) >= df['vim'].shift(1))
        df['vol_avg'] = df['volume'].rolling(10).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['cross_down']
        df['entry_cond2'] = df['volume'] < df['vol_avg'] * 0.7
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
            reason='Vortex Bearish Cross + Volume Dry Up',
        )