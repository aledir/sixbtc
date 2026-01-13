"""
Pattern-Gen Strategy: Average Price Cross Down + Volatility Expanding
Type: AVG (template)
Timeframe: 30m
Direction: short
Blocks: AVGPRICE_CROSS_DOWN, VOLATILITY_EXPANDING
Generated: 2026-01-13T01:57:23.776811+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_AVG_f78fbdd7dfdd46cf(StrategyCore):
    """
    Pattern: Average Price Cross Down + Volatility Expanding
    Direction: short
    Lookback: 60 bars
    Execution: close_based
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '30m'

    # Execution type for parametric optimization
    execution_type = 'close_based'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Lookback required
    LOOKBACK = 60

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.6
    TP_PCT = 0.0
    LEVERAGE = 1
    exit_after_bars = 40

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Average Price Cross Down + Volatility Expanding
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['avgprice'] = ta.AVGPRICE(df['open'], df['high'], df['low'], df['close'])
        df['avgprice_ma'] = ta.SMA(df['avgprice'], timeperiod=20)
        df['below'] = df['avgprice'] < df['avgprice_ma']
        df['was_above'] = df['avgprice'].shift(1) >= df['avgprice_ma'].shift(1)
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        df['atr_ma'] = df['atr'].rolling(20).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['below'] & df['was_above']
        df['entry_cond2'] = df['atr'] > df['atr_ma'] * 1.2
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
            reason='Average Price Cross Down + Volatility Expanding',
        )