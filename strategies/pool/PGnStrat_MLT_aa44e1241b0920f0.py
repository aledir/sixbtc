"""
Pattern-Gen Strategy: Trend + Momentum + Volume Short + Price Cross EMA Down
Type: MLT (template)
Timeframe: 2h
Direction: short
Blocks: TREND_MOM_VOL_SHORT, PRICE_CROSS_EMA_DOWN
Generated: 2026-01-13T05:58:28.613628+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_MLT_aa44e1241b0920f0(StrategyCore):
    """
    Pattern: Trend + Momentum + Volume Short + Price Cross EMA Down
    Direction: short
    Lookback: 200 bars
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
    LOOKBACK = 200

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.6
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 90

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Trend + Momentum + Volume Short + Price Cross EMA Down
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['ema'] = ta.EMA(df['close'], timeperiod=100)
        df['rsi'] = ta.RSI(df['close'], timeperiod=14)
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['trend_down'] = df['close'] < df['ema']
        df['momentum_ok'] = (df['rsi'] < 60) & (df['rsi'] > 35)
        df['volume_ok'] = df['volume'] > df['vol_ma'] * 1.2
        df['ema'] = ta.EMA(df['close'], timeperiod=20)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['trend_down'] & df['momentum_ok'] & df['volume_ok']
        df['entry_cond2'] = (df['close'] < df['ema']) & (df['close'].shift(1) >= df['ema'].shift(1))
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
            reason='Trend + Momentum + Volume Short + Price Cross EMA Down',
        )