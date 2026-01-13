"""
Pattern-Gen Strategy: Historical Volatility Breakout + ADX Trending Market
Type: HVO (template)
Timeframe: 30m
Direction: long
Blocks: HV_BREAKOUT, ADX_TRENDING
Generated: 2026-01-13T00:59:05.808846+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_HVO_9b4d08c6d3d12afe(StrategyCore):
    """
    Pattern: Historical Volatility Breakout + ADX Trending Market
    Direction: long
    Lookback: 40 bars
    Execution: touch_based
    """

    # Direction
    direction = 'long'

    # Timeframe (for Sharpe annualization)
    timeframe = '30m'

    # Execution type for parametric optimization
    execution_type = 'touch_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 40

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.12
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 45

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Historical Volatility Breakout + ADX Trending Market
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['returns'] = np.log(df['close'] / df['close'].shift(1))
        df['hv'] = df['returns'].rolling(20).std() * np.sqrt(252) * 100
        df['hv_ma'] = df['hv'].rolling(20).mean()
        df['was_low'] = df['hv'].shift(3) < df['hv_ma'].shift(3)
        df['now_high'] = df['hv'] > df['hv_ma']
        df['breakout'] = df['was_low'] & df['now_high']
        df['price_up'] = df['close'] > df['close'].shift(3)
        df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=20)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['breakout'] & df['price_up']
        df['entry_cond2'] = df['adx'] > 30
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
            reason='Historical Volatility Breakout + ADX Trending Market',
        )