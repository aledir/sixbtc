"""
PtaStrat: AD Oscillator + Detrended Price Oscillator
Timeframe: 1h
Direction: SHORT
Regime: TREND
Exit Mechanism: (TP and EC) or TS
Generated: 2026-01-13T03:12:05.704730+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_VLM_68d8b2d4(StrategyCore):
    """
    Entry: 2 indicator(s)
    - AD Oscillator threshold_above 70
    - Detrended Price Oscillator threshold_above 70
    Exit: TP requires EC true, or trailing exits
    SL: Swing Low/High
TP: ATR-BasedTrailing: ATR Trail    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.03
    TP_PCT = 0.04
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 16  # No time-based exit

    # Stop Loss params
    sl_type = StopLossType.STRUCTURE

    # Take Profit params
    tp_type = TakeProfitType.ATR
    atr_take_multiplier = 4.0

    # Trailing Stop
    trailing_stop_pct = 0.01
    trailing_activation_pct = 0.02

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        Uses pandas_ta library for indicator calculations.
        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()

        # === CALCULATE INDICATORS ===
        # Indicator 1: AD Oscillator
        adosc_result = ta.adosc(
            df['high'], df['low'], df['close'], df['volume'],
            fast=3,
            slow=10,
        )
        df['adosc'] = adosc_result

        # Indicator 2: Detrended Price Oscillator
        dpo_result = ta.dpo(
            df['close'],
            length=20,
        )
        df['dpo'] = dpo_result


        # ATR for SL/TP calculations
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: AD Oscillator threshold_above 70
        cond_1 = df['adosc'] > 70
        entry_signal = entry_signal & cond_1

        # Condition 2: Detrended Price Oscillator threshold_above 70
        cond_2 = df['dpo'] > 70
        entry_signal = entry_signal & cond_2


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
            'sl_type': StopLossType.STRUCTURE,
            'sl_price': df['high'].iloc[-20:].max(),

            # Take Profit
            'tp_type': TakeProfitType.ATR,
            'atr_take_multiplier': 4.0,

            # Trailing Stop
            'trailing_stop_pct': 0.01,
            'trailing_activation_pct': 0.02,

            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'ADOSC(threshold_above) + DPO(threshold_above)',
        }

        return Signal(**signal_kwargs)

