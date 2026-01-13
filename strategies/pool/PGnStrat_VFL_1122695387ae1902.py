"""
Pattern-Gen Strategy: High Vol Filter + Trend Up (Price > EMA) + ADX Trending Market
Type: VFL (template)
Timeframe: 2h
Direction: long
Blocks: HIGH_VOL_FILTER, TREND_UP, ADX_TRENDING
Generated: 2026-01-13T03:03:07.845338+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_VFL_1122695387ae1902(StrategyCore):
    """
    Pattern: High Vol Filter + Trend Up (Price > EMA) + ADX Trending Market
    Direction: long
    Lookback: 100 bars
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
    LOOKBACK = 100

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.6
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

        Pattern: High Vol Filter + Trend Up (Price > EMA) + ADX Trending Market
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        df['atr_ma'] = df['atr'].rolling(20).mean()
        df['high_vol'] = df['atr'] > df['atr_ma'] * 1.2
        df['trend_up'] = df['close'] > ta.EMA(df['close'], timeperiod=20)
        df['momentum'] = df['close'] > df['close'].shift(3)
        df['ema_trend'] = ta.EMA(df['close'], timeperiod=100)
        df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=20)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['high_vol'] & df['trend_up'] & df['momentum']
        df['entry_cond2'] = df['close'] > df['ema_trend']
        df['entry_cond3'] = df['adx'] > 30
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
            reason='High Vol Filter + Trend Up (Price > EMA) + ADX Trending Market',
        )