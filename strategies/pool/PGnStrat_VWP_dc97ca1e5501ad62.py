"""
Pattern-Gen Strategy: Price Cross Below VWAP + Trend Down (Price < EMA)
Type: VWP (template)
Timeframe: 2h
Direction: short
Blocks: VWAP_CROSS_DOWN, TREND_DOWN
Generated: 2026-01-13T04:21:27.801941+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_VWP_dc97ca1e5501ad62(StrategyCore):
    """
    Pattern: Price Cross Below VWAP + Trend Down (Price < EMA)
    Direction: short
    Lookback: 100 bars
    Execution: touch_based
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Execution type for parametric optimization
    execution_type = 'touch_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 100

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.08
    TP_PCT = 0.12
    LEVERAGE = 1
    exit_after_bars = 0

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Price Cross Below VWAP + Trend Down (Price < EMA)
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
        df['below_vwap'] = df['close'] < df['vwap']
        df['was_above'] = df['close'].shift(1) >= df['vwap'].shift(1)
        df['ema_trend'] = ta.EMA(df['close'], timeperiod=50)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['below_vwap'] & df['was_above']
        df['entry_cond2'] = df['close'] < df['ema_trend']
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
            reason='Price Cross Below VWAP + Trend Down (Price < EMA)',
        )