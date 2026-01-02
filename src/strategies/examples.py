"""
Example Strategies

Hand-crafted strategies demonstrating the two-phase approach:
1. calculate_indicators() - Pre-calculate all indicators ONCE
2. generate_signal() - Read pre-calculated values and generate signal

These serve as templates for AI-generated strategies.
"""

import pandas as pd
import numpy as np
import talib as ta
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class Strategy_MOM_Example(StrategyCore):
    """
    Simple RSI Momentum Strategy

    Entry:
        - LONG: RSI < 30 (oversold) + volume spike
        - SHORT: RSI > 70 (overbought) + volume spike

    Exit:
        - ATR-based stop loss (2x ATR)
        - ATR-based take profit (3x ATR, 1.5:1 R:R)
    """

    # Indicator columns added by calculate_indicators()
    indicator_columns = ['rsi', 'atr', 'volume_ma', 'volume_ratio']

    def __init__(self, params: dict = None):
        """Initialize with default parameters"""
        super().__init__(params)

        # Strategy parameters
        self.rsi_period = self.params.get('rsi_period', 14)
        self.rsi_oversold = self.params.get('rsi_oversold', 30)
        self.rsi_overbought = self.params.get('rsi_overbought', 70)
        self.volume_ma_period = self.params.get('volume_ma_period', 20)
        self.volume_spike_threshold = self.params.get('volume_spike_threshold', 1.5)
        self.atr_period = self.params.get('atr_period', 14)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pre-calculate all indicators"""
        df = df.copy()

        # RSI
        df['rsi'] = ta.RSI(df['close'], timeperiod=self.rsi_period)

        # ATR
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=self.atr_period)

        # Volume analysis
        df['volume_ma'] = df['volume'].rolling(window=self.volume_ma_period).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        """Generate momentum signal based on pre-calculated indicators"""
        # Minimum data requirement
        min_bars = max(self.rsi_period, self.volume_ma_period, self.atr_period) + 10
        if len(df) < min_bars:
            return None

        # Read pre-calculated indicator values
        current_rsi = df['rsi'].iloc[-1]
        current_atr = df['atr'].iloc[-1]
        volume_ratio = df['volume_ratio'].iloc[-1]

        # Check for NaN values
        if pd.isna(current_rsi) or pd.isna(current_atr) or pd.isna(volume_ratio):
            return None

        # Check for volume spike
        volume_spike = volume_ratio > self.volume_spike_threshold

        # LONG entry: Oversold + volume spike
        if current_rsi < self.rsi_oversold and volume_spike:
            return Signal(
                direction='long',
                sl_type=StopLossType.ATR,
                atr_stop_multiplier=2.0,
                tp_type=TakeProfitType.ATR,
                atr_take_multiplier=3.0,
                reason=(
                    f"RSI oversold at {current_rsi:.1f} "
                    f"with volume spike {volume_ratio:.2f}x"
                )
            )

        # SHORT entry: Overbought + volume spike
        if current_rsi > self.rsi_overbought and volume_spike:
            return Signal(
                direction='short',
                sl_type=StopLossType.ATR,
                atr_stop_multiplier=2.0,
                tp_type=TakeProfitType.ATR,
                atr_take_multiplier=3.0,
                reason=(
                    f"RSI overbought at {current_rsi:.1f} "
                    f"with volume spike {volume_ratio:.2f}x"
                )
            )

        return None


class Strategy_REV_Example(StrategyCore):
    """
    Bollinger Bands Mean Reversion Strategy

    Entry:
        - LONG: Price touches lower band + RSI < 40
        - SHORT: Price touches upper band + RSI > 60

    Exit:
        - TP: ATR-based
        - SL: 2x ATR
    """

    indicator_columns = ['bb_upper', 'bb_middle', 'bb_lower', 'rsi', 'atr']

    def __init__(self, params: dict = None):
        """Initialize with default parameters"""
        super().__init__(params)

        self.bb_period = self.params.get('bb_period', 20)
        self.bb_std = self.params.get('bb_std', 2.0)
        self.rsi_period = self.params.get('rsi_period', 14)
        self.atr_period = self.params.get('atr_period', 14)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pre-calculate all indicators"""
        df = df.copy()

        # Bollinger Bands
        df['bb_middle'] = ta.SMA(df['close'], timeperiod=self.bb_period)
        df['bb_std'] = df['close'].rolling(window=self.bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (self.bb_std * df['bb_std'])
        df['bb_lower'] = df['bb_middle'] - (self.bb_std * df['bb_std'])

        # RSI
        df['rsi'] = ta.RSI(df['close'], timeperiod=self.rsi_period)

        # ATR
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=self.atr_period)

        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        """Generate mean reversion signal from pre-calculated indicators"""
        min_bars = max(self.bb_period, self.rsi_period, self.atr_period) + 10
        if len(df) < min_bars:
            return None

        # Read pre-calculated values
        current_price = df['close'].iloc[-1]
        current_rsi = df['rsi'].iloc[-1]
        current_upper = df['bb_upper'].iloc[-1]
        current_lower = df['bb_lower'].iloc[-1]

        # Check for NaN
        if pd.isna(current_rsi) or pd.isna(current_upper) or pd.isna(current_lower):
            return None

        # Calculate distance from bands
        lower_distance = abs(current_price - current_lower) / current_lower
        upper_distance = abs(current_price - current_upper) / current_upper

        # LONG: Price near lower band + oversold RSI
        if lower_distance < 0.01 and current_rsi < 40:
            return Signal(
                direction='long',
                sl_type=StopLossType.ATR,
                atr_stop_multiplier=2.0,
                tp_type=TakeProfitType.ATR,
                atr_take_multiplier=3.0,
                reason=(
                    f"Price at lower BB ({current_price:.2f} vs {current_lower:.2f}), "
                    f"RSI {current_rsi:.1f}"
                )
            )

        # SHORT: Price near upper band + overbought RSI
        if upper_distance < 0.01 and current_rsi > 60:
            return Signal(
                direction='short',
                sl_type=StopLossType.ATR,
                atr_stop_multiplier=2.0,
                tp_type=TakeProfitType.ATR,
                atr_take_multiplier=3.0,
                reason=(
                    f"Price at upper BB ({current_price:.2f} vs {current_upper:.2f}), "
                    f"RSI {current_rsi:.1f}"
                )
            )

        return None


class Strategy_TRN_Example(StrategyCore):
    """
    EMA Crossover Trend Following Strategy

    Entry:
        - LONG: Fast EMA crosses above Slow EMA + ADX > 25
        - SHORT: Fast EMA crosses below Slow EMA + ADX > 25

    Exit:
        - ATR-based stops
    """

    indicator_columns = ['ema_fast', 'ema_slow', 'adx', 'atr']

    def __init__(self, params: dict = None):
        """Initialize with default parameters"""
        super().__init__(params)

        self.fast_period = self.params.get('fast_period', 12)
        self.slow_period = self.params.get('slow_period', 26)
        self.adx_period = self.params.get('adx_period', 14)
        self.adx_threshold = self.params.get('adx_threshold', 25)
        self.atr_period = self.params.get('atr_period', 14)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pre-calculate all indicators"""
        df = df.copy()

        # EMAs
        df['ema_fast'] = ta.EMA(df['close'], timeperiod=self.fast_period)
        df['ema_slow'] = ta.EMA(df['close'], timeperiod=self.slow_period)

        # ADX
        df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=self.adx_period)

        # ATR
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=self.atr_period)

        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        """Generate trend following signal from pre-calculated indicators"""
        min_bars = max(self.slow_period, self.adx_period, self.atr_period) + 10
        if len(df) < min_bars:
            return None

        # Read pre-calculated values
        current_fast = df['ema_fast'].iloc[-1]
        current_slow = df['ema_slow'].iloc[-1]
        prev_fast = df['ema_fast'].iloc[-2]
        prev_slow = df['ema_slow'].iloc[-2]
        current_adx = df['adx'].iloc[-1]

        # Check for NaN
        if pd.isna(current_fast) or pd.isna(current_slow) or pd.isna(current_adx):
            return None
        if pd.isna(prev_fast) or pd.isna(prev_slow):
            return None

        # Check for crossover
        bullish_cross = (prev_fast <= prev_slow) and (current_fast > current_slow)
        bearish_cross = (prev_fast >= prev_slow) and (current_fast < current_slow)

        # Strong trend requirement
        strong_trend = current_adx > self.adx_threshold

        # LONG: Bullish crossover + strong trend
        if bullish_cross and strong_trend:
            return Signal(
                direction='long',
                sl_type=StopLossType.ATR,
                atr_stop_multiplier=2.5,
                tp_type=TakeProfitType.ATR,
                atr_take_multiplier=4.0,
                reason=(
                    f"Bullish EMA crossover (EMA{self.fast_period}={current_fast:.2f} > "
                    f"EMA{self.slow_period}={current_slow:.2f}), ADX={current_adx:.1f}"
                )
            )

        # SHORT: Bearish crossover + strong trend
        if bearish_cross and strong_trend:
            return Signal(
                direction='short',
                sl_type=StopLossType.ATR,
                atr_stop_multiplier=2.5,
                tp_type=TakeProfitType.ATR,
                atr_take_multiplier=4.0,
                reason=(
                    f"Bearish EMA crossover (EMA{self.fast_period}={current_fast:.2f} < "
                    f"EMA{self.slow_period}={current_slow:.2f}), ADX={current_adx:.1f}"
                )
            )

        return None
