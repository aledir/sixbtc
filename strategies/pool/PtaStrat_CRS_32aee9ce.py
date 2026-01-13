"""
PtaStrat: Detrended Price Oscillator + Keltner Channels
Timeframe: 30m
Direction: SHORT
Regime: TREND
Exit Mechanism: (EC and TS) or TP
Generated: 2026-01-13T01:40:03.614080+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_CRS_32aee9ce(StrategyCore):
    """
    Entry: 2 indicator(s)
    - Detrended Price Oscillator threshold_above 70
    - Keltner Channels threshold_above 70
    Exit: Trailing requires EC true, or TP exits
    SL: Fixed Percentage
TP: Structure High/LowTrailing: Wide Trail    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '30m'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.03
    TP_PCT = 0.1
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 12

    # Stop Loss params
    sl_type = StopLossType.PERCENTAGE

    # Take Profit params

    # Trailing Stop
    trailing_stop_pct = 0.025
    trailing_activation_pct = 0.04

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

        # Indicator 2: Keltner Channels
        kc_result = ta.kc(
            df['high'], df['low'], df['close'],
            length=20,
            scalar=2.0,
        )
        # Multi-column output - take first (main) column
        if isinstance(kc_result, pd.DataFrame):
            df['kc'] = kc_result.iloc[:, 0]
        else:
            df['kc'] = kc_result



        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Detrended Price Oscillator threshold_above 70
        cond_1 = df['dpo'] > 70
        entry_signal = entry_signal & cond_1

        # Condition 2: Keltner Channels threshold_above 70
        cond_2 = df['kc'] > 70
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
            'tp_price': df['low'].iloc[-20:].min(),

            # Trailing Stop
            'trailing_stop_pct': 0.025,
            'trailing_activation_pct': 0.04,

            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'DPO(threshold_above) + KC(threshold_above)',
        }

        return Signal(**signal_kwargs)

