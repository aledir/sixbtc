"""
Example Strategies

Hand-crafted strategies for testing and demonstration.
These serve as templates for AI-generated strategies.
"""

import pandas as pd
import numpy as np
from ta import trend, momentum, volatility, volume as vol_indicators
from src.strategies.base import StrategyCore, Signal


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

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        """Generate momentum signal based on RSI and volume"""
        # Minimum data requirement
        min_bars = max(self.rsi_period, self.volume_ma_period, self.atr_period) + 10
        if len(df) < min_bars:
            return None

        # Calculate indicators
        rsi = momentum.RSIIndicator(df['close'], window=self.rsi_period).rsi()
        atr = volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=self.atr_period
        ).average_true_range()
        volume_ma = df['volume'].rolling(window=self.volume_ma_period).mean()

        # Current values
        current_rsi = rsi.iloc[-1]
        current_atr = atr.iloc[-1]
        current_volume = df['volume'].iloc[-1]
        avg_volume = volume_ma.iloc[-1]

        # Check for volume spike
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        volume_spike = volume_ratio > self.volume_spike_threshold

        # LONG entry: Oversold + volume spike
        if current_rsi < self.rsi_oversold and volume_spike:
            return Signal(
                direction='long',
                atr_stop_multiplier=2.0,
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
                atr_stop_multiplier=2.0,
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
        - TP: Middle band (mean)
        - SL: 2x ATR
    """

    def __init__(self, params: dict = None):
        """Initialize with default parameters"""
        super().__init__(params)

        self.bb_period = self.params.get('bb_period', 20)
        self.bb_std = self.params.get('bb_std', 2.0)
        self.rsi_period = self.params.get('rsi_period', 14)
        self.atr_period = self.params.get('atr_period', 14)

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        """Generate mean reversion signal"""
        min_bars = max(self.bb_period, self.rsi_period, self.atr_period) + 10
        if len(df) < min_bars:
            return None

        # Calculate Bollinger Bands
        bb_indicator = volatility.BollingerBands(
            df['close'], window=self.bb_period, window_dev=self.bb_std
        )
        bb_upper = bb_indicator.bollinger_hband()
        bb_middle = bb_indicator.bollinger_mavg()
        bb_lower = bb_indicator.bollinger_lband()

        # Calculate RSI and ATR
        rsi = momentum.RSIIndicator(df['close'], window=self.rsi_period).rsi()
        atr = volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=self.atr_period
        ).average_true_range()

        # Current values
        current_price = df['close'].iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_upper = bb_upper.iloc[-1]
        current_middle = bb_middle.iloc[-1]
        current_lower = bb_lower.iloc[-1]

        # Calculate distance from bands
        lower_distance = abs(current_price - current_lower) / current_lower
        upper_distance = abs(current_price - current_upper) / current_upper

        # LONG: Price near lower band + oversold RSI
        if lower_distance < 0.01 and current_rsi < 40:
            return Signal(
                direction='long',
                atr_stop_multiplier=2.0,
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
                atr_stop_multiplier=2.0,
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

    def __init__(self, params: dict = None):
        """Initialize with default parameters"""
        super().__init__(params)

        self.fast_period = self.params.get('fast_period', 12)
        self.slow_period = self.params.get('slow_period', 26)
        self.adx_period = self.params.get('adx_period', 14)
        self.adx_threshold = self.params.get('adx_threshold', 25)
        self.atr_period = self.params.get('atr_period', 14)

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        """Generate trend following signal"""
        min_bars = max(self.slow_period, self.adx_period, self.atr_period) + 10
        if len(df) < min_bars:
            return None

        # Calculate EMAs
        ema_fast = trend.EMAIndicator(df['close'], window=self.fast_period).ema_indicator()
        ema_slow = trend.EMAIndicator(df['close'], window=self.slow_period).ema_indicator()

        # Calculate ADX
        adx = trend.ADXIndicator(
            df['high'], df['low'], df['close'], window=self.adx_period
        ).adx()

        # Calculate ATR
        atr = volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=self.atr_period
        ).average_true_range()

        # Current values
        current_fast = ema_fast.iloc[-1]
        current_slow = ema_slow.iloc[-1]
        prev_fast = ema_fast.iloc[-2]
        prev_slow = ema_slow.iloc[-2]
        current_adx = adx.iloc[-1]

        # Check for crossover
        bullish_cross = (prev_fast <= prev_slow) and (current_fast > current_slow)
        bearish_cross = (prev_fast >= prev_slow) and (current_fast < current_slow)

        # Strong trend requirement
        strong_trend = current_adx > self.adx_threshold

        # LONG: Bullish crossover + strong trend
        if bullish_cross and strong_trend:
            return Signal(
                direction='long',
                atr_stop_multiplier=2.5,
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
                atr_stop_multiplier=2.5,
                atr_take_multiplier=4.0,
                reason=(
                    f"Bearish EMA crossover (EMA{self.fast_period}={current_fast:.2f} < "
                    f"EMA{self.slow_period}={current_slow:.2f}), ADX={current_adx:.1f}"
                )
            )

        return None
