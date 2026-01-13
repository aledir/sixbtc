"""
PtaStrat: Detrended Price Oscillator + On Balance Volume + Elder Force Index
Timeframe: 1h
Direction: SHORT
Regime: TREND
Exit Mechanism: All OR
Generated: 2026-01-13T04:31:24.545668+00:00
"""

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
import pandas as pd
import pandas_ta as ta
import numpy as np


class PtaStrat_CRS_ed36e61d(StrategyCore):
    """
    Entry: 3 indicator(s)
    - Detrended Price Oscillator threshold_above 70
    - On Balance Volume slope_down 0
    - Elder Force Index slope_down 0
    Exit: Exit on any of the three (first hit)
    SL: Volatility Std Dev
TP: Fibonacci ExtensionTrailing: Percentage Trail    """

    # Direction
    direction = 'short'

    # Timeframe (for Sharpe annualization)
    timeframe = '1h'

    # Signal column for vectorized backtest
    signal_column = 'entry_signal'

    # Parametric placeholders (expanded by backtester)
    SL_PCT = 0.03
    TP_PCT = 0.1
    LEVERAGE = 1
    LOOKBACK = 30
    exit_after_bars = 8

    # Stop Loss params
    sl_type = StopLossType.PERCENTAGE

    # Take Profit params
    tp_type = TakeProfitType.PERCENTAGE

    # Trailing Stop
    trailing_stop_pct = 0.005
    trailing_activation_pct = 0.03

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

        # Indicator 2: On Balance Volume
        obv_result = ta.obv(
            df['close'], df['volume'],
        )
        df['obv'] = obv_result

        # Indicator 3: Elder Force Index
        efi_result = ta.efi(
            df['close'], df['volume'],
            length=21,
        )
        df['efi'] = efi_result



        # === VECTORIZED ENTRY SIGNAL ===
        entry_signal = pd.Series(True, index=df.index)

        # Condition 1: Detrended Price Oscillator threshold_above 70
        cond_1 = df['dpo'] > 70
        entry_signal = entry_signal & cond_1

        # Condition 2: On Balance Volume slope_down 0
        cond_2 = df['obv'] < df['obv'].shift(1)
        entry_signal = entry_signal & cond_2

        # Condition 3: Elder Force Index slope_down 0
        cond_3 = df['efi'] < df['efi'].shift(1)
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
            'sl_type': StopLossType.PERCENTAGE,
            'sl_pct': self.SL_PCT,

            # Take Profit
            'tp_type': TakeProfitType.PERCENTAGE,
            'tp_pct': self.TP_PCT,

            # Trailing Stop
            'trailing_stop_pct': 0.005,
            'trailing_activation_pct': 0.03,

            # Time-based Exit (read from class attribute, may be 0 for no time exit)
            'exit_after_bars': self.exit_after_bars,

            'reason': 'DPO(threshold_above) + OBV(slope_down) + EFI(slope_down)',
        }

        return Signal(**signal_kwargs)

