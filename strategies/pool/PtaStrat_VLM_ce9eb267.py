"""
PtaStrat: Archer OBV + Detrended Price Oscillator + Positive Volume Index
Timeframe: 1h
Direction: SHORT
Regime: TREND
Exit Mechanism: TP or EC
Generated: 2026-01-13T12:42:31.032015+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_VLM_ce9eb267(StrategyCore):
    """
    Entry: 3 indicator(s)
    - Archer OBV slope_down 0
    - Detrended Price Oscillator threshold_above 2
    - Positive Volume Index slope_up 0
    Exit: Exit at target or on condition (first hit)
    SL: Fixed Percentage
TP: Fixed Percentage    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Indicator columns for lookahead test
    indicator_columns = ['aobv', 'dpo', 'pvi', 'entry_signal']

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.03
    TP_PCT = 0.06
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 8  # No time-based exit

    # Stop Loss config
    sl_type = StopLossType.PERCENTAGE

    # Take Profit config
    tp_type = TakeProfitType.PERCENTAGE

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        Uses pandas_ta library for indicator calculations.
        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()

        # === CALCULATE INDICATORS ===
        # Indicator 1: Archer OBV
        aobv_result = ta.aobv(
            df['close'], df['volume'],
            fast=4,
            slow=16,
        )
        # Handle both Series and DataFrame results (some indicators return DataFrame even with single output)
        if isinstance(aobv_result, pd.DataFrame):
            df['aobv'] = aobv_result.iloc[:, 0]
        else:
            df['aobv'] = aobv_result

        # Indicator 2: Detrended Price Oscillator
        dpo_result = ta.dpo(
            df['close'],
            length=20,
        )
        # Handle both Series and DataFrame results (some indicators return DataFrame even with single output)
        if isinstance(dpo_result, pd.DataFrame):
            df['dpo'] = dpo_result.iloc[:, 0]
        else:
            df['dpo'] = dpo_result

        # Indicator 3: Positive Volume Index
        pvi_result = ta.pvi(
            df['close'], df['volume'],
            length=1,
        )
        # Handle both Series and DataFrame results (some indicators return DataFrame even with single output)
        if isinstance(pvi_result, pd.DataFrame):
            df['pvi'] = pvi_result.iloc[:, 0]
        else:
            df['pvi'] = pvi_result



        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Archer OBV slope_down 0
        cond_1 = df['aobv'] < df['aobv'].shift(1)
        entry_signal = entry_signal & cond_1

        # Condition 2: Detrended Price Oscillator threshold_above 2
        cond_2 = df['dpo'] > 2
        entry_signal = entry_signal & cond_2

        # Condition 3: Positive Volume Index slope_up 0
        cond_3 = df['pvi'] > df['pvi'].shift(1)
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

            # Stop Loss (type-aware, optimized by typed parametric backtest)
            'sl_type': self.sl_type,
            'sl_pct': self.SL_PCT,

            # Take Profit (type-aware, optimized by typed parametric backtest)
            'tp_type': self.tp_type,
            'tp_pct': self.TP_PCT,

            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'AOBV(slope_down) + DPO(threshold_above) + PVI(slope_up)',
        }

        return Signal(**signal_kwargs)

