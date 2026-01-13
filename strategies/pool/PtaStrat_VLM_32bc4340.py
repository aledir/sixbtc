"""
PtaStrat: Elder Force Index + On Balance Volume + Detrended Price Oscillator
Timeframe: 1h
Direction: SHORT
Regime: TREND
Exit Mechanism: TP and EC
Generated: 2026-01-13T03:46:08.578497+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_VLM_32bc4340(StrategyCore):
    """
    Entry: 3 indicator(s)
    - Elder Force Index slope_down 0
    - On Balance Volume slope_down 0
    - Detrended Price Oscillator threshold_above 70
    Exit: Exit at target only if condition is true
    SL: Swing Low/High
TP: ATR-Based    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.04
    TP_PCT = 0.15
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 8

    # Stop Loss params
    sl_type = StopLossType.STRUCTURE

    # Take Profit params
    tp_type = TakeProfitType.ATR
    atr_take_multiplier = 5.0


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
            length=13,
        )
        df['efi'] = efi_result

        # Indicator 2: On Balance Volume
        obv_result = ta.obv(
            df['close'], df['volume'],
        )
        df['obv'] = obv_result

        # Indicator 3: Detrended Price Oscillator
        dpo_result = ta.dpo(
            df['close'],
            length=20,
        )
        df['dpo'] = dpo_result


        # ATR for SL/TP calculations
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Elder Force Index slope_down 0
        cond_1 = df['efi'] < df['efi'].shift(1)
        entry_signal = entry_signal & cond_1

        # Condition 2: On Balance Volume slope_down 0
        cond_2 = df['obv'] < df['obv'].shift(1)
        entry_signal = entry_signal & cond_2

        # Condition 3: Detrended Price Oscillator threshold_above 70
        cond_3 = df['dpo'] > 70
        entry_signal = entry_signal & cond_3


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
            'sl_price': df['high'].iloc[-20:].max(),

            # Take Profit
            'tp_type': TakeProfitType.ATR,
            'atr_take_multiplier': 5.0,


            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'EFI(slope_down) + OBV(slope_down) + DPO(threshold_above)',
        }

        return Signal(**signal_kwargs)

