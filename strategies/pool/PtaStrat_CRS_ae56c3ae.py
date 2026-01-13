"""
PtaStrat: Detrended Price Oscillator + AD Oscillator
Timeframe: 2h
Direction: SHORT
Regime: TREND
Exit Mechanism: TP or EC
Generated: 2026-01-13T09:06:34.226933+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_CRS_ae56c3ae(StrategyCore):
    """
    Entry: 2 indicator(s)
    - Detrended Price Oscillator threshold_above 70
    - AD Oscillator threshold_above 70
    Exit: Exit at target or on condition (first hit)
    SL: Fixed Percentage
TP: ATR-Based    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.05
    TP_PCT = 0.06
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 24

    # Stop Loss params (always percentage-based for Numba kernel compatibility)
    sl_type = StopLossType.PERCENTAGE

    # Take Profit params (always percentage-based for Numba kernel compatibility)
    tp_type = TakeProfitType.PERCENTAGE

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

        # Indicator 2: AD Oscillator
        adosc_result = ta.adosc(
            df['high'], df['low'], df['close'], df['volume'],
            fast=3,
            slow=10,
        )
        df['adosc'] = adosc_result


        # ATR for SL/TP calculations
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Detrended Price Oscillator threshold_above 70
        cond_1 = df['dpo'] > 70
        entry_signal = entry_signal & cond_1

        # Condition 2: AD Oscillator threshold_above 70
        cond_2 = df['adosc'] > 70
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

            # Stop Loss (always percentage-based, optimized by backtester)
            'sl_type': StopLossType.PERCENTAGE,
            'sl_pct': self.SL_PCT,

            # Take Profit (always percentage-based, optimized by backtester)
            'tp_type': TakeProfitType.PERCENTAGE,
            'tp_pct': self.TP_PCT,

            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'DPO(threshold_above) + ADOSC(threshold_above)',
        }

        return Signal(**signal_kwargs)

    def should_exit(self, df: pd.DataFrame, position_bars: int) -> bool:
        """
        Check dynamic exit conditions.
        Exit Mechanism: TP or EC (OR)
        Exit Condition: Price Cross MA Against Short
        """
        # Exit Condition: Price Cross MA Against Short
        ma = df["close"].rolling(50).mean()
        exit_signal = (df["close"].iloc[-1] > ma.iloc[-1]) and (df["close"].iloc[-2] <= ma.iloc[-2])

        # OR logic: exit if exit_signal
        return exit_signal
