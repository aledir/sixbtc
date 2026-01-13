"""
Unger Strategy v2: Donchian Lower Breakout
Timeframe: 30m
Direction: BIDI
Exit Mechanism: TP or EC
Generated: 2026-01-12T23:56:49.713975+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import numpy as np


class UngStrat_BRK_38982aaa(StrategyCore):
    """
    Entry: Donchian Lower Breakout (breakout)
    Filters: 0
    Exit: Exit at target or on condition (first hit)
    SL: Structure Low/High
TP: Risk Multiple    """

    # Direction
    direction = 'bidi'

    # Timeframe (for Sharpe annualization)
    timeframe = '30m'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.32
    TP_PCT = 0.0
    LEVERAGE = 2
    LOOKBACK = 60
    exit_after_bars = 60

    # Stop Loss params
    sl_type = StopLossType.STRUCTURE

    # Take Profit params
    tp_type = TakeProfitType.RR_RATIO
    rr_ratio = 1.5


    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()











        # === VECTORIZED ENTRY SIGNAL: Donchian Lower Breakout ===
        entry_signal = df["close"] < df["low"].rolling(55).min().iloc[-2]


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

            'reason': 'Donchian Lower Breakout',
        }

        return Signal(**signal_kwargs)

