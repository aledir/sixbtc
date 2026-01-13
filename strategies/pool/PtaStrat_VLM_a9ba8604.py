"""
PtaStrat: Negative Volume Index + Detrended Price Oscillator
Timeframe: 1h
Direction: SHORT
Regime: TREND
Exit Mechanism: (TP and EC) or TS
Generated: 2026-01-13T00:49:12.683150+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_VLM_a9ba8604(StrategyCore):
    """
    Entry: 2 indicator(s)
    - Negative Volume Index slope_down 0
    - Detrended Price Oscillator threshold_above 70
    Exit: TP requires EC true, or trailing exits
    SL: Fixed Percentage
TP: Fixed PercentageTrailing: Chandelier Exit    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.04
    TP_PCT = 0.06
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 6  # No time-based exit

    # Stop Loss params
    sl_type = StopLossType.PERCENTAGE

    # Take Profit params
    tp_type = TakeProfitType.PERCENTAGE

    # Trailing Stop
    trailing_stop_pct = 0.01
    trailing_activation_pct = 0.015

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        Uses pandas_ta library for indicator calculations.
        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()

        # === CALCULATE INDICATORS ===
        # Indicator 1: Negative Volume Index
        nvi_result = ta.nvi(
            df['close'], df['volume'],
            length=1,
        )
        df['nvi'] = nvi_result

        # Indicator 2: Detrended Price Oscillator
        dpo_result = ta.dpo(
            df['close'],
            length=20,
        )
        df['dpo'] = dpo_result



        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Negative Volume Index slope_down 0
        cond_1 = df['nvi'] < df['nvi'].shift(1)
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
            'sl_type': StopLossType.PERCENTAGE,
            'sl_pct': self.SL_PCT,

            # Take Profit
            'tp_type': TakeProfitType.PERCENTAGE,
            'tp_pct': self.TP_PCT,

            # Trailing Stop
            'trailing_stop_pct': 0.01,
            'trailing_activation_pct': 0.015,

            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'NVI(slope_down) + DPO(threshold_above)',
        }

        return Signal(**signal_kwargs)

