"""
PtaStrat: Detrended Price Oscillator + Negative Volume Index + AD Oscillator
Timeframe: 30m
Direction: SHORT
Regime: MIXED
Exit Mechanism: All OR
Generated: 2026-01-13T04:07:45.634644+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_CRS_f35d5662(StrategyCore):
    """
    Entry: 3 indicator(s)
    - Detrended Price Oscillator threshold_above 70
    - Negative Volume Index threshold_above 70
    - AD Oscillator slope_down 0
    Exit: Exit on any of the three (first hit)
    SL: Fixed Percentage
TP: Fixed PercentageTrailing: ATR Trail    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '30m'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.02
    TP_PCT = 0.1
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 12  # No time-based exit

    # Stop Loss params
    sl_type = StopLossType.PERCENTAGE

    # Take Profit params
    tp_type = TakeProfitType.PERCENTAGE

    # Trailing Stop
    trailing_stop_pct = 0.01
    trailing_activation_pct = 0.01

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        Uses pandas_ta library for indicator calculations.
        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()

        # === CALCULATE INDICATORS ===
        # Indicator 1: Detrended Price Oscillator
        dpo_result = ta.dpo(
            df['close'],
            length=20,
        )
        df['dpo'] = dpo_result

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



        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Detrended Price Oscillator threshold_above 70
        cond_1 = df['dpo'] > 70
        entry_signal = entry_signal & cond_1

        # Condition 2: Negative Volume Index threshold_above 70
        cond_2 = df['nvi'] > 70
        entry_signal = entry_signal & cond_2

        # Condition 3: AD Oscillator slope_down 0
        cond_3 = df['adosc'] < df['adosc'].shift(1)
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
            'tp_type': TakeProfitType.PERCENTAGE,
            'tp_pct': self.TP_PCT,

            # Trailing Stop
            'trailing_stop_pct': 0.01,
            'trailing_activation_pct': 0.01,

            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'DPO(threshold_above) + NVI(threshold_above) + ADOSC(slope_down)',
        }

        return Signal(**signal_kwargs)

    def should_exit(self, df: pd.DataFrame, position_bars: int) -> bool:
        """
        Check dynamic exit conditions.
        Exit Mechanism: All OR (OR OR)
        Exit Condition: RSI Extreme Short Exit
        """
        # Exit Condition: RSI Extreme Short Exit
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        exit_signal = rsi.iloc[-1] < 30

        # OR logic: exit if exit_signal
        return exit_signal
