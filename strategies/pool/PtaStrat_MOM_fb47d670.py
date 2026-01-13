"""
PtaStrat: Chande Momentum Oscillator + On Balance Volume
Timeframe: 2h
Direction: SHORT
Regime: MIXED
Exit Mechanism: TP and EC
Generated: 2026-01-13T14:48:13.637724+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_MOM_fb47d670(StrategyCore):
    """
    Entry: 2 indicator(s)
    - Chande Momentum Oscillator threshold_above 20
    - On Balance Volume threshold_above 70
    Exit: Exit at target only if condition is true
    SL: Fixed Percentage
TP: Structure High/Low    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Indicator columns for lookahead test
    indicator_columns = ['cmo', 'obv', 'entry_signal']

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.1
    TP_PCT = 0.12
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 0

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
        # Indicator 1: Chande Momentum Oscillator
        cmo_result = ta.cmo(
            df['close'],
            length=21,
        )
        # Handle both Series and DataFrame results (some indicators return DataFrame even with single output)
        if isinstance(cmo_result, pd.DataFrame):
            df['cmo'] = cmo_result.iloc[:, 0]
        else:
            df['cmo'] = cmo_result

        # Indicator 2: On Balance Volume
        obv_result = ta.obv(
            df['close'], df['volume'],
        )
        # Handle both Series and DataFrame results (some indicators return DataFrame even with single output)
        if isinstance(obv_result, pd.DataFrame):
            df['obv'] = obv_result.iloc[:, 0]
        else:
            df['obv'] = obv_result



        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Chande Momentum Oscillator threshold_above 20
        cond_1 = df['cmo'] > 20
        entry_signal = entry_signal & cond_1

        # Condition 2: On Balance Volume threshold_above 70
        cond_2 = df['obv'] > 70
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
        # Direction derived from entry conditions (never BIDI at strategy level)
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

            'reason': 'CMO(threshold_above) + OBV(threshold_above)',
        }

        return Signal(**signal_kwargs)

