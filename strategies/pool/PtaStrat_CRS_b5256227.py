"""
PtaStrat: Detrended Price Oscillator + Negative Volume Index
Timeframe: 2h
Direction: SHORT
Regime: TREND
Exit Mechanism: EC Only
Generated: 2026-01-13T03:19:51.577301+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_CRS_b5256227(StrategyCore):
    """
    Entry: 2 indicator(s)
    - Detrended Price Oscillator threshold_above 70
    - Negative Volume Index slope_down 0
    Exit: Exit only on dynamic conditions
    SL: Swing Low/High
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.03
    TP_PCT = 0.12
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 12  # No time-based exit

    # Stop Loss params
    sl_type = StopLossType.STRUCTURE



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



        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Detrended Price Oscillator threshold_above 70
        cond_1 = df['dpo'] > 70
        entry_signal = entry_signal & cond_1

        # Condition 2: Negative Volume Index slope_down 0
        cond_2 = df['nvi'] < df['nvi'].shift(1)
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



            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'DPO(threshold_above) + NVI(slope_down)',
        }

        return Signal(**signal_kwargs)

