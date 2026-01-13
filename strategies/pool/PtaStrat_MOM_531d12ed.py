"""
PtaStrat: Commodity Channel Index + Elder Force Index
Timeframe: 2h
Direction: BIDI
Regime: MIXED
Exit Mechanism: TP and EC
Generated: 2026-01-13T05:52:17.744940+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_MOM_531d12ed(StrategyCore):
    """
    Entry: 2 indicator(s)
    - Commodity Channel Index crossed_below 0
    - Elder Force Index slope_up 0
    Exit: Exit at target only if condition is true
    SL: ATR-Based
TP: Risk Multiple    """

    # Direction
    direction = 'bidi'

    # Timeframe (for Sharpe annualization)
    timeframe = '2h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.03
    TP_PCT = 0.12
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 12  # No time-based exit

    # Stop Loss params
    sl_type = StopLossType.ATR
    atr_stop_multiplier = 3.0

    # Take Profit params
    tp_type = TakeProfitType.RR_RATIO
    rr_ratio = 2.5


    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry_signal for vectorized backtesting.

        Uses pandas_ta library for indicator calculations.
        The backtester reads entry_signal directly (no per-bar loop).
        """
        df = df.copy()

        # === CALCULATE INDICATORS ===
        # Indicator 1: Commodity Channel Index
        cci_result = ta.cci(
            df['high'], df['low'], df['close'],
            length=20,
        )
        df['cci'] = cci_result

        # Indicator 2: Elder Force Index
        efi_result = ta.efi(
            df['close'], df['volume'],
            length=21,
        )
        df['efi'] = efi_result


        # ATR for SL/TP calculations
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Commodity Channel Index crossed_below 0
        cond_1 = (df['cci'] < 0) & (df['cci'].shift(1) >= 0)
        entry_signal = entry_signal & cond_1

        # Condition 2: Elder Force Index slope_up 0
        cond_2 = df['efi'] > df['efi'].shift(1)
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
        signal_direction = 'long'  # Default for BIDI entries

        signal_kwargs = {
            'direction': signal_direction,
            'leverage': self.LEVERAGE,

            # Stop Loss
            'sl_type': StopLossType.ATR,
            'atr_stop_multiplier': 3.0,

            # Take Profit
            'tp_type': TakeProfitType.RR_RATIO,
            'rr_ratio': 2.5,


            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'CCI(crossed_below) + EFI(slope_up)',
        }

        return Signal(**signal_kwargs)

