"""
PtaStrat: Detrended Price Oscillator
Timeframe: 1h
Direction: SHORT
Regime: TREND
Exit Mechanism: (EC and TS) or TP
Generated: 2026-01-13T09:17:51.990481+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_CRS_8cb2bc05(StrategyCore):
    """
    Entry: 1 indicator(s)
    - Detrended Price Oscillator threshold_above 70
    Exit: Trailing requires EC true, or TP exits
    SL: Swing Low/High
TP: Risk MultipleTrailing: Percentage Trail    """

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
    exit_after_bars = 16

    # Stop Loss config
    sl_type = StopLossType.STRUCTURE
    sl_lookback = 10

    # Take Profit config
    tp_type = TakeProfitType.RR_RATIO
    tp_rr_ratio = 1.5

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



        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Detrended Price Oscillator threshold_above 70
        cond_1 = df['dpo'] > 70
        entry_signal = entry_signal & cond_1


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
            'sl_lookback': self.sl_lookback,

            # Take Profit (type-aware, optimized by typed parametric backtest)
            'tp_type': self.tp_type,
            'tp_pct': self.TP_PCT,
            'tp_rr_ratio': self.tp_rr_ratio,

            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'DPO(threshold_above)',
        }

        return Signal(**signal_kwargs)

    def should_exit(self, df: pd.DataFrame, position_bars: int) -> bool:
        """
        Check dynamic exit conditions.
        Exit Mechanism: (EC and TS) or TP ((EC^TS)vTP)
        Exit Condition: Price Cross MA Against Short
        """
        # Exit Condition: Price Cross MA Against Short
        ma = df["close"].rolling(20).mean()
        exit_signal = (df["close"].iloc[-1] > ma.iloc[-1]) and (df["close"].iloc[-2] <= ma.iloc[-2])

        # OR logic: exit if exit_signal
        return exit_signal
