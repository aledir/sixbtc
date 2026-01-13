"""
Unger Strategy v2: Price Above MA
Timeframe: 2h
Direction: SHORT
Exit Mechanism: TP and EC
Generated: 2026-01-13T00:18:49.065811+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import numpy as np


class UngStrat_REV_6457c0d4(StrategyCore):
    """
    Entry: Price Above MA (mean_reversion)
    Filters: 2
    Exit: Exit at target only if condition is true
    SL: ATR-Based
TP: Risk Multiple    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.1
    TP_PCT = 0.25
    LEVERAGE = 1
    LOOKBACK = 55
    exit_after_bars = 12  # No time-based exit

    # Stop Loss params
    sl_type = StopLossType.ATR
    atr_stop_multiplier = 3.0

    # Take Profit params
    tp_type = TakeProfitType.RR_RATIO
    rr_ratio = 3.0


    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()


        # Moving Averages
        df['ma'] = df['close'].rolling(20).mean()




        # ATR
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()



        # ADX
        high_diff = df['high'].diff()
        low_diff = -df['low'].diff()
        plus_dm = ((high_diff > low_diff) & (high_diff > 0)) * high_diff
        minus_dm = ((low_diff > high_diff) & (low_diff > 0)) * low_diff
        tr = (df['high'] - df['low']).rolling(14).mean()
        plus_di = 100 * plus_dm.rolling(14).mean() / (tr + 1e-10)
        minus_di = 100 * minus_dm.rolling(14).mean() / (tr + 1e-10)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        df['adx'] = dx.rolling(14).mean()


        # === VECTORIZED ENTRY SIGNAL: Price Above MA ===
        ma = df["close"].rolling(20).mean()
        entry_signal = df["close"] > ma * (1 + 3/100)

        # Filter 1: Volume Spike (vectorized)
        vol_ma = df["volume"].rolling(20).mean()
        filter_pass = df["volume"] > vol_ma * 1.5
        entry_signal = entry_signal & filter_pass
        # Filter 2: Unger: Small Body (vectorized)
        from src.generator.regime.unger_patterns import UngerPatterns
        filter_pass = UngerPatterns.pattern_02_small_body(df)
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

            'reason': 'Price Above MA + 2 filters',
        }

        return Signal(**signal_kwargs)

