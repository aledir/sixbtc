"""
Pattern-Gen Strategy: Typical Price Cross Down + Volume Spike + Volatility Expanding
Type: TYP (template)
Timeframe: 30m
Direction: short
Blocks: TYPPRICE_CROSS_DOWN, VOLUME_SPIKE, VOLATILITY_EXPANDING
Generated: 2026-01-13T01:05:55.738933+00:00
"""

import talib as ta
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class PGnStrat_TYP_aefcfdd78a11cb0f(StrategyCore):
    """
    Pattern: Typical Price Cross Down + Volume Spike + Volatility Expanding
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
    exit_after_bars = 30

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators and entry_signal for vectorized backtesting.

        Pattern: Typical Price Cross Down + Volume Spike + Volatility Expanding
        Composition: template
        """
        df = df.copy()

        # === INDICATOR CALCULATIONS ===
        df['typprice'] = ta.TYPPRICE(df['high'], df['low'], df['close'])
        df['typprice_ma'] = ta.SMA(df['typprice'], timeperiod=10)
        df['below'] = df['typprice'] < df['typprice_ma']
        df['was_above'] = df['typprice'].shift(1) >= df['typprice_ma'].shift(1)
        df['vol_avg'] = df['volume'].rolling(20).mean()
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        df['atr_ma'] = df['atr'].rolling(50).mean()

        # === ENTRY SIGNAL ===
        df['entry_cond1'] = df['below'] & df['was_above']
        df['entry_cond2'] = df['volume'] > df['vol_avg'] * 3.0
        df['entry_cond3'] = df['atr'] > df['atr_ma'] * 1.0
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
            reason='Typical Price Cross Down + Volume Spike + Volatility Expanding',
        )