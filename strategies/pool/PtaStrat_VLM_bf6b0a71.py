"""
PtaStrat: Chaikin Money Flow + Detrended Price Oscillator
Timeframe: 2h
Direction: SHORT
Regime: TREND
Exit Mechanism: TS Only
Generated: 2026-01-13T08:30:40.939503+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_VLM_bf6b0a71(StrategyCore):
    """
    Entry: 2 indicator(s)
    - Chaikin Money Flow slope_down 0
    - Detrended Price Oscillator threshold_above 70
    Exit: Exit only via trailing stop
    SL: Structure Low/High
Trailing: Percentage Trail    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.03
    TP_PCT = 0.06
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 12  # No time-based exit

    # Stop Loss params
    sl_type = StopLossType.STRUCTURE


    # Trailing Stop
    trailing_stop_pct = 0.015
    trailing_activation_pct = 0.03

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        Uses pandas_ta library for indicator calculations.
        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()

        # === CALCULATE INDICATORS ===
        # Indicator 1: Chaikin Money Flow
        cmf_result = ta.cmf(
            df['high'], df['low'], df['close'], df['volume'],
            length=20,
        )
        df['cmf'] = cmf_result

        # Indicator 2: Detrended Price Oscillator
        dpo_result = ta.dpo(
            df['close'],
            length=20,
        )
        df['dpo'] = dpo_result



        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Chaikin Money Flow slope_down 0
        cond_1 = df['cmf'] < df['cmf'].shift(1)
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
            'sl_price': df['high'].iloc[-10:].max(),


            # Trailing Stop
            'trailing_stop_pct': 0.015,
            'trailing_activation_pct': 0.03,

            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'CMF(slope_down) + DPO(threshold_above)',
        }

        return Signal(**signal_kwargs)

