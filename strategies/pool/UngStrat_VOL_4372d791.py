"""
Unger Strategy v2: Keltner Lower Break
Timeframe: 2h
Direction: SHORT
Exit Mechanism: EC Only
Generated: 2026-01-13T00:18:38.317052+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import numpy as np


class UngStrat_VOL_4372d791(StrategyCore):
    """
    Entry: Keltner Lower Break (volatility)
    Filters: 2
    Exit: Exit only on dynamic conditions
    SL: Fixed Percentage
    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.07
    TP_PCT = 0.25
    LEVERAGE = 1
    LOOKBACK = 25
    exit_after_bars = 12

    # Stop Loss params
    sl_type = StopLossType.PERCENTAGE



    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()






        # ATR
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()





        # === VECTORIZED ENTRY SIGNAL: Keltner Lower Break ===
        ema = df["close"].ewm(span=20, adjust=False).mean()
        atr = (df["high"] - df["low"]).rolling(14).mean()
        keltner_lower = ema - atr * 1.5
        entry_signal = df["close"] < keltner_lower

        # Filter 1: RSI Not Overbought (vectorized)
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        filter_pass = rsi < 70
        entry_signal = entry_signal & filter_pass
        # Filter 2: Unger: Bearish Engulfing (vectorized)
        from src.generator.regime.unger_patterns import UngerPatterns
        filter_pass = UngerPatterns.pattern_54_bearish_engulfing(df)
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

            'reason': 'Keltner Lower Break + 2 filters',
        }

        return Signal(**signal_kwargs)

