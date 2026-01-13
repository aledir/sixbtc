"""
Unger Strategy v2: Return to VWAP Short
Timeframe: 2h
Direction: SHORT
Exit Mechanism: EC Only
Generated: 2026-01-12T23:50:29.173390+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import numpy as np


class UngStrat_REV_b85dfe50(StrategyCore):
    """
    Entry: Return to VWAP Short (mean_reversion)
    Filters: 1
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
    SL_PCT = 0.07
    TP_PCT = 0.18
    LEVERAGE = 1
    LOOKBACK = 20
    exit_after_bars = 0

    # Stop Loss params
    sl_type = StopLossType.STRUCTURE



    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()











        # === VECTORIZED ENTRY SIGNAL: Return to VWAP Short ===
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        cum_vol = df["volume"].cumsum()
        cum_tp_vol = (typical_price * df["volume"]).cumsum()
        vwap = cum_tp_vol / cum_vol
        entry_signal = df["close"] > vwap * 1.02

        # Filter 1: Unger: Momentum Shift (vectorized)
        from src.generator.regime.unger_patterns import UngerPatterns
        filter_pass = UngerPatterns.pattern_66_momentum_shift(df)
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

            'reason': 'Return to VWAP Short + 1 filters',
        }

        return Signal(**signal_kwargs)

    def should_exit(self, df: pd.DataFrame, position_bars: int) -> bool:
        """
        Check dynamic exit conditions.
        Exit Mechanism: EC Only (-)
        Exit Condition: Price Cross MA Against Short
        """
        # Exit Condition: Price Cross MA Against Short
        ma = df["close"].rolling(20).mean()
        exit_signal = (df["close"].iloc[-1] > ma.iloc[-1]) and (df["close"].iloc[-2] <= ma.iloc[-2])

        # OR logic: exit if exit_signal
        return exit_signal
