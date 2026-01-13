"""
Unger Strategy v2: RSI Exit Overbought
Timeframe: 1h
Direction: SHORT
Exit Mechanism: EC and TS
Generated: 2026-01-13T00:19:57.841545+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import numpy as np


class UngStrat_THR_f95ae3b8(StrategyCore):
    """
    Entry: RSI Exit Overbought (threshold)
    Filters: 1
    Exit: Trailing exits only if condition is true
    SL: Fixed Percentage
Trailing: ATR Trail    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.04
    TP_PCT = 0.2
    LEVERAGE = 1
    LOOKBACK = 20
    exit_after_bars = 16

    # Stop Loss params
    sl_type = StopLossType.PERCENTAGE


    # Trailing Stop
    trailing_stop_pct = 0.01
    trailing_activation_pct = 0.015

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()

        # RSI
        delta = df['close'].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-10)))










        # === VECTORIZED ENTRY SIGNAL: RSI Exit Overbought ===
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        entry_signal = (rsi < 70) & (rsi.shift(1) >= 70)

        # Filter 1: Unger: NR7 (vectorized)
        from src.generator.regime.unger_patterns import UngerPatterns
        filter_pass = UngerPatterns.pattern_59_nr7(df)
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

            'reason': 'RSI Exit Overbought + 1 filters',
        }

        return Signal(**signal_kwargs)

