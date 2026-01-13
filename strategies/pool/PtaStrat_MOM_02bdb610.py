"""
PtaStrat: Chande Momentum Oscillator + Negative Volume Index + AD Oscillator
Timeframe: 1h
Direction: SHORT
Regime: MIXED
Exit Mechanism: (TP and EC) or TS
Generated: 2026-01-13T02:15:33.436847+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_MOM_02bdb610(StrategyCore):
    """
    Entry: 3 indicator(s)
    - Chande Momentum Oscillator crossed_below 0
    - Negative Volume Index slope_down 0
    - AD Oscillator threshold_above 70
    Exit: TP requires EC true, or trailing exits
    SL: Volatility Std Dev
TP: ATR-BasedTrailing: Wide Trail    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.1
    TP_PCT = 0.0
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 32

    # Stop Loss params
    sl_type = StopLossType.PERCENTAGE

    # Take Profit params
    tp_type = TakeProfitType.ATR
    atr_take_multiplier = 5.0

    # Trailing Stop
    trailing_stop_pct = 0.025
    trailing_activation_pct = 0.03

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        Uses pandas_ta library for indicator calculations.
        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()

        # === CALCULATE INDICATORS ===
        # Indicator 1: Chande Momentum Oscillator
        cmo_result = ta.cmo(
            df['close'],
            length=21,
        )
        df['cmo'] = cmo_result

        # Indicator 2: Negative Volume Index
        nvi_result = ta.nvi(
            df['close'], df['volume'],
            length=1,
        )
        df['nvi'] = nvi_result

        # Indicator 3: AD Oscillator
        adosc_result = ta.adosc(
            df['high'], df['low'], df['close'], df['volume'],
            fast=3,
            slow=10,
        )
        df['adosc'] = adosc_result


        # ATR for SL/TP calculations
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Chande Momentum Oscillator crossed_below 0
        cond_1 = (df['cmo'] < 0) & (df['cmo'].shift(1) >= 0)
        entry_signal = entry_signal & cond_1

        # Condition 2: Negative Volume Index slope_down 0
        cond_2 = df['nvi'] < df['nvi'].shift(1)
        entry_signal = entry_signal & cond_2

        # Condition 3: AD Oscillator threshold_above 70
        cond_3 = df['adosc'] > 70
        entry_signal = entry_signal & cond_3


        # Store as boolean column
        df['entry_signal'] = entry_signal.astype(bool)

        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        """
        Generate signal for LIVE execution (reads pre-calculated entry_signal).

        For backtest, the entry_signal column is read directly by the engine.
        """
        if len(df) < self.LOOKBACK + 10:
            return None

        # Read pre-calculated entry signal
        if not df['entry_signal'].iloc[-1]:
            return None

        # === BUILD SIGNAL ===
        signal_direction = 'short'

        signal_kwargs = {
            'direction': signal_direction,
            'leverage': self.LEVERAGE,

            # Stop Loss
            'sl_type': StopLossType.PERCENTAGE,
            'sl_pct': self.SL_PCT,

            # Take Profit
            'tp_type': TakeProfitType.ATR,
            'atr_take_multiplier': 5.0,

            # Trailing Stop
            'trailing_stop_pct': 0.025,
            'trailing_activation_pct': 0.03,

            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'CMO(crossed_below) + NVI(slope_down) + ADOSC(threshold_above)',
        }

        return Signal(**signal_kwargs)

    def should_exit(self, df: pd.DataFrame, position_bars: int) -> bool:
        """
        Check dynamic exit conditions.
        Exit Mechanism: (TP and EC) or TS ((TP^EC)vTS)
        Exit Condition: Price Cross MA Against Short
        """
        # Exit Condition: Price Cross MA Against Short
        ma = df["close"].rolling(10).mean()
        exit_signal = (df["close"].iloc[-1] > ma.iloc[-1]) and (df["close"].iloc[-2] <= ma.iloc[-2])

        # OR logic: exit if exit_signal
        return exit_signal
