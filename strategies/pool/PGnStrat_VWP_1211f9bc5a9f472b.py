"""
Pattern-Gen Strategy: Price Cross Below VWAP + Volatility Expanding
Type: VWP (template)
Timeframe: 1h
Direction: short
Blocks: VWAP_CROSS_DOWN, VOLATILITY_EXPANDING
Generated: 2026-01-13T09:17:50.660700+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_VWP_1211f9bc5a9f472b(StrategyCore):
    """
    Pattern: Price Cross Below VWAP + Volatility Expanding
    Direction: short
    Lookback: 60 bars
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
    LOOKBACK = 60

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.06
    TP_PCT = 0.1
    LEVERAGE = 1
    exit_after_bars = 0

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Price Cross Below VWAP + Volatility Expanding
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
        df['below_vwap'] = df['close'] < df['vwap']
        df['was_above'] = df['close'].shift(1) >= df['vwap'].shift(1)
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        df['atr_ma'] = df['atr'].rolling(20).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['below_vwap'] & df['was_above']
        df['entry_cond2'] = df['atr'] > df['atr_ma'] * 1.0
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
            reason='Price Cross Below VWAP + Volatility Expanding',
        )