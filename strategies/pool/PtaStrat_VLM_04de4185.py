"""
PtaStrat: Elder Force Index
Timeframe: 2h
Direction: SHORT
Regime: MIXED
Exit Mechanism: TP or TS
Generated: 2026-01-13T05:53:08.996328+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_VLM_04de4185(StrategyCore):
    """
    Entry: 1 indicator(s)
    - Elder Force Index threshold_above 1000000
    Exit: Exit at target or via trailing (first hit)
    SL: Structure Low/High
TP: Fixed PercentageTrailing: Chandelier Exit    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.1
    TP_PCT = 0.12
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 0  # No time-based exit

    # Stop Loss params
    sl_type = StopLossType.STRUCTURE

    # Take Profit params
    tp_type = TakeProfitType.PERCENTAGE

    # Trailing Stop
    trailing_stop_pct = 0.01
    trailing_activation_pct = 0.01

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        Uses pandas_ta library for indicator calculations.
        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()

        # === CALCULATE INDICATORS ===
        # Indicator 1: Elder Force Index
        efi_result = ta.efi(
            df['close'], df['volume'],
            length=21,
        )
        df['efi'] = efi_result



        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Elder Force Index threshold_above 1000000
        cond_1 = df['efi'] > 1000000
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

            # Stop Loss
            'sl_type': StopLossType.STRUCTURE,
            'sl_price': df['high'].iloc[-3:].max(),

            # Take Profit
            'tp_type': TakeProfitType.PERCENTAGE,
            'tp_pct': self.TP_PCT,

            # Trailing Stop
            'trailing_stop_pct': 0.01,
            'trailing_activation_pct': 0.01,

            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'EFI(threshold_above)',
        }

        return Signal(**signal_kwargs)

