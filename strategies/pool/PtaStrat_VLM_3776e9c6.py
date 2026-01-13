"""
PtaStrat: On Balance Volume + TRIX
Timeframe: 1h
Direction: SHORT
Regime: MIXED
Exit Mechanism: EC Only
Generated: 2026-01-13T05:05:12.962517+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_VLM_3776e9c6(StrategyCore):
    """
    Entry: 2 indicator(s)
    - On Balance Volume slope_down 0
    - TRIX crossed_below 0
    Exit: Exit only on dynamic conditions
    SL: Swing Low/High
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.06
    TP_PCT = 0.15
    LEVERAGE = 1
    LOOKBACK = 50
    exit_after_bars = 0  # No time-based exit

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
        # Indicator 1: On Balance Volume
        obv_result = ta.obv(
            df['close'], df['volume'],
        )
        df['obv'] = obv_result

        # Indicator 2: TRIX
        trix_result = ta.trix(
            df['close'],
            length=18,
        )
        # Multi-column output - take first (main) column
        if isinstance(trix_result, pd.DataFrame):
            df['trix'] = trix_result.iloc[:, 0]
        else:
            df['trix'] = trix_result



        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: On Balance Volume slope_down 0
        cond_1 = df['obv'] < df['obv'].shift(1)
        entry_signal = entry_signal & cond_1

        # Condition 2: TRIX crossed_below 0
        cond_2 = (df['trix'] < 0) & (df['trix'].shift(1) >= 0)
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

            'reason': 'OBV(slope_down) + TRIX(crossed_below)',
        }

        return Signal(**signal_kwargs)

