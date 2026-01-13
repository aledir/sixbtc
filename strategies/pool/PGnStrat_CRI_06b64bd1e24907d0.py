"""
Pattern-Gen Strategy: BB Volume Combo + ADX Trending Market + Volume Above Average
Type: CRI (template)
Timeframe: 2h
Direction: long
Blocks: BB_VOL_COMBO, ADX_TRENDING, VOLUME_ABOVE_AVERAGE
Generated: 2026-01-13T07:08:19.218617+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_CRI_06b64bd1e24907d0(StrategyCore):
    """
    Pattern: BB Volume Combo + ADX Trending Market + Volume Above Average
    Direction: long
    Lookback: 50 bars
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
    LOOKBACK = 50

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.1
    TP_PCT = 0.12
    LEVERAGE = 1
    exit_after_bars = 6

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: BB Volume Combo + ADX Trending Market + Volume Above Average
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
        df['at_lower'] = df['low'] <= df['bb_lower']
        df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
        df['reversal'] = df['close'] > df['open']
        df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
        df['vol_ma'] = df['volume'].rolling(50).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['at_lower'] & df['vol_surge'] & df['reversal']
        df['entry_cond2'] = df['adx'] > 30
        df['entry_cond3'] = df['volume'] > df['vol_ma'] * 1.2
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
            reason='BB Volume Combo + ADX Trending Market + Volume Above Average',
        )