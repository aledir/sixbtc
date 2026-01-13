"""
Unger Strategy v2: MFI Overbought
Timeframe: 1h
Direction: SHORT
Exit Mechanism: TP or TS
Generated: 2026-01-13T00:14:36.665927+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import numpy as np


class UngStrat_THR_35e79b7b(StrategyCore):
    """
    Entry: MFI Overbought (threshold)
    Filters: 1
    Exit: Exit at target or via trailing (first hit)
    SL: Swing Low/High
TP: Structure High/LowTrailing: Chandelier Exit    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.1
    TP_PCT = 0.15
    LEVERAGE = 1
    LOOKBACK = 20
    exit_after_bars = 0  # No time-based exit

    # Stop Loss params
    sl_type = StopLossType.STRUCTURE

    # Take Profit params

    # Trailing Stop
    trailing_stop_pct = 0.01
    trailing_activation_pct = 0.015

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()











        # === VECTORIZED ENTRY SIGNAL: MFI Overbought ===
        tp = (df["high"] + df["low"] + df["close"]) / 3
        mf = tp * df["volume"]
        pos_mf = ((tp > tp.shift(1)) * mf).rolling(14).sum()
        neg_mf = ((tp < tp.shift(1)) * mf).rolling(14).sum()
        mfi = 100 * pos_mf / (pos_mf + neg_mf + 1e-10)
        entry_signal = mfi > 75

        # Filter 1: Consolidation (vectorized)
        recent_range = df["high"].iloc[-10:].max() - df["low"].iloc[-10:].min()
        atr = (df["high"] - df["low"]).rolling(14).mean()
        filter_pass = recent_range < atr * 3.0
        entry_signal = entry_signal & filter_pass

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

            # Stop Loss (always percentage-based, optimized by backtester)
            'sl_type': StopLossType.PERCENTAGE,
            'sl_pct': self.SL_PCT,

            # Take Profit (always percentage-based, optimized by backtester)
            'tp_type': TakeProfitType.PERCENTAGE,
            'tp_pct': self.TP_PCT,

            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'MFI Overbought + 1 filters',
        }

        return Signal(**signal_kwargs)

