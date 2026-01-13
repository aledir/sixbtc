"""
Pattern-Gen Strategy: Median Price Cross Down + Volume Breakout Down + Not Oversold (RSI > threshold)
Type: MED (template)
Timeframe: 1h
Direction: short
Blocks: MEDPRICE_CROSS_DOWN, VOLUME_BREAKOUT_DOWN, NOT_OVERSOLD
Generated: 2026-01-13T03:21:39.782343+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_MED_f413d050f4f64559(StrategyCore):
    """
    Pattern: Median Price Cross Down + Volume Breakout Down + Not Oversold (RSI > threshold)
    Direction: short
    Lookback: 30 bars
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
    LOOKBACK = 30

    # Risk management parameters (to be optimized by parametric backtest)
    SL_PCT = 0.06
    TP_PCT = 0.1
    LEVERAGE = 1
    exit_after_bars = 30

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Median Price Cross Down + Volume Breakout Down + Not Oversold (RSI > threshold)
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['medprice'] = ta.MEDPRICE(df['high'], df['low'])
        df['medprice_ma'] = ta.SMA(df['medprice'], timeperiod=10)
        df['below'] = df['close'] < df['medprice_ma']
        df['was_above'] = df['close'].shift(1) >= df['medprice_ma'].shift(1)
        df['vol_avg'] = df['volume'].rolling(20).mean()
        df['close_chg'] = df['close'].pct_change()
        df['rsi_filter'] = ta.RSI(df['close'], timeperiod=14)

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['below'] & df['was_above']
        df['entry_cond2'] = (df['volume'] > df['vol_avg'] * 3.0) & (df['close_chg'] < 0)
        df['entry_cond3'] = df['rsi_filter'] > 35
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
            reason='Median Price Cross Down + Volume Breakout Down + Not Oversold (RSI > threshold)',
        )