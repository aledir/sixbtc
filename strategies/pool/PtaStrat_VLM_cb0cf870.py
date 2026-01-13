"""
PtaStrat: On Balance Volume + Detrended Price Oscillator
Timeframe: 15m
Direction: SHORT
Regime: TREND
Exit Mechanism: TP Only
Generated: 2026-01-13T02:35:03.602165+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_VLM_cb0cf870(StrategyCore):
    """
    Entry: 2 indicator(s)
    - On Balance Volume slope_down 0
    - Detrended Price Oscillator threshold_above 70
    Exit: Exit only at fixed target
    SL: Swing Low/High
TP: Fixed Percentage    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '15m'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.015
    TP_PCT = 0.02
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 10  # No time-based exit

    # Stop Loss params
    sl_type = StopLossType.STRUCTURE

    # Take Profit params
    tp_type = TakeProfitType.PERCENTAGE


    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        Uses pandas_ta library for indicator calculations.
        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()

        # === CALCULATE INDICATORS ===
        # Indicator 1: On Balance Volume
        obv_result = ta.obv(
            df['close'], df['volume'],
        )
        df['obv'] = obv_result

        # Indicator 2: Detrended Price Oscillator
        dpo_result = ta.dpo(
            df['close'],
            length=20,
        )
        df['dpo'] = dpo_result



        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: On Balance Volume slope_down 0
        cond_1 = df['obv'] < df['obv'].shift(1)
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

            # Take Profit
            'tp_type': TakeProfitType.PERCENTAGE,
            'tp_pct': self.TP_PCT,


            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'OBV(slope_down) + DPO(threshold_above)',
        }

        return Signal(**signal_kwargs)

