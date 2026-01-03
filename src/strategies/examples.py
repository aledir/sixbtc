"""
Example Strategies

Hand-crafted strategies demonstrating the vectorized approach:
1. calculate_indicators() - Pre-calculate indicators + populate entry_signal
2. generate_signal() - For LIVE execution only (reads entry_signal[-1])

Backtester reads entry_signal array directly (no per-bar loop).

All strategies MUST have:
- Class attributes: direction, sl_pct, tp_pct, leverage, exit_after_bars, signal_column
- calculate_indicators() must populate the signal_column (default: 'entry_signal')
"""

import pandas as pd
import numpy as np
import talib as ta
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType


class Strategy_MOM_Example(StrategyCore):
    """
    Simple RSI Momentum Strategy (Long only)

    Entry:
        - LONG: RSI < 30 (oversold) + volume spike

    Exit:
        - Stop Loss: 3% (percentage-based)
        - Take Profit: 2% (percentage-based)
        - Time Exit: 20 bars
    """

    # =========================================================================
    # STRATEGY PARAMETERS (read by backtester for vectorized execution)
    # =========================================================================
    direction = 'long'
    sl_pct = 0.03       # 3% stop loss
    tp_pct = 0.02       # 2% take profit
    leverage = 1
    exit_after_bars = 20
    signal_column = 'entry_signal'

    # Indicator columns added by calculate_indicators()
    indicator_columns = ['rsi', 'atr', 'volume_ma', 'volume_ratio', 'entry_signal']

    def __init__(self, params: dict = None):
        """Initialize with default parameters"""
        super().__init__(params)

        # Strategy parameters
        self.rsi_period = self.params.get('rsi_period', 14)
        self.rsi_oversold = self.params.get('rsi_oversold', 30)
        self.volume_ma_period = self.params.get('volume_ma_period', 20)
        self.volume_spike_threshold = self.params.get('volume_spike_threshold', 1.5)
        self.atr_period = self.params.get('atr_period', 14)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pre-calculate all indicators and entry_signal"""
        df = df.copy()

        # RSI
        df['rsi'] = ta.RSI(df['close'], timeperiod=self.rsi_period)

        # ATR
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=self.atr_period)

        # Volume analysis
        df['volume_ma'] = df['volume'].rolling(window=self.volume_ma_period).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        # Entry signal: RSI oversold + volume spike (vectorized)
        rsi_condition = df['rsi'] < self.rsi_oversold
        volume_condition = df['volume_ratio'] > self.volume_spike_threshold

        df['entry_signal'] = (rsi_condition & volume_condition).astype(bool)

        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        """Generate signal for LIVE execution (reads pre-calculated entry_signal)"""
        min_bars = 100
        if len(df) < min_bars:
            return None

        # Read pre-calculated entry signal
        if not df['entry_signal'].iloc[-1]:
            return None

        return Signal(
            direction=self.direction,
            leverage=self.leverage,
            sl_type=StopLossType.PERCENTAGE,
            sl_pct=self.sl_pct,
            tp_type=TakeProfitType.PERCENTAGE,
            tp_pct=self.tp_pct,
            exit_type=ExitType.TIME_BASED,
            exit_after_bars=self.exit_after_bars,
            reason=f"RSI oversold at {df['rsi'].iloc[-1]:.1f} with volume spike"
        )


class Strategy_REV_Example(StrategyCore):
    """
    Bollinger Bands Mean Reversion Strategy (Long only)

    Entry:
        - LONG: Price touches lower band + RSI < 40

    Exit:
        - Stop Loss: 4%
        - Take Profit: 3%
        - Time Exit: 30 bars
    """

    # =========================================================================
    # STRATEGY PARAMETERS (read by backtester for vectorized execution)
    # =========================================================================
    direction = 'long'
    sl_pct = 0.04       # 4% stop loss
    tp_pct = 0.03       # 3% take profit
    leverage = 1
    exit_after_bars = 30
    signal_column = 'entry_signal'

    indicator_columns = ['bb_upper', 'bb_middle', 'bb_lower', 'rsi', 'atr', 'entry_signal']

    def __init__(self, params: dict = None):
        """Initialize with default parameters"""
        super().__init__(params)

        self.bb_period = self.params.get('bb_period', 20)
        self.bb_std = self.params.get('bb_std', 2.0)
        self.rsi_period = self.params.get('rsi_period', 14)
        self.atr_period = self.params.get('atr_period', 14)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pre-calculate all indicators and entry_signal"""
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

        # Entry signal: Price near lower band + oversold RSI (vectorized)
        lower_distance = (df['close'] - df['bb_lower']).abs() / df['bb_lower']
        price_at_lower = lower_distance < 0.01
        rsi_oversold = df['rsi'] < 40

        df['entry_signal'] = (price_at_lower & rsi_oversold).astype(bool)

        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        """Generate signal for LIVE execution (reads pre-calculated entry_signal)"""
        min_bars = 100
        if len(df) < min_bars:
            return None

        if not df['entry_signal'].iloc[-1]:
            return None

        return Signal(
            direction=self.direction,
            leverage=self.leverage,
            sl_type=StopLossType.PERCENTAGE,
            sl_pct=self.sl_pct,
            tp_type=TakeProfitType.PERCENTAGE,
            tp_pct=self.tp_pct,
            exit_type=ExitType.TIME_BASED,
            exit_after_bars=self.exit_after_bars,
            reason=f"Price at lower BB, RSI {df['rsi'].iloc[-1]:.1f}"
        )


class Strategy_TRN_Example(StrategyCore):
    """
    EMA Crossover Trend Following Strategy (Long only)

    Entry:
        - LONG: Fast EMA crosses above Slow EMA + ADX > 25

    Exit:
        - Stop Loss: 5%
        - Take Profit: 4%
        - Time Exit: 40 bars
    """

    # =========================================================================
    # STRATEGY PARAMETERS (read by backtester for vectorized execution)
    # =========================================================================
    direction = 'long'
    sl_pct = 0.05       # 5% stop loss
    tp_pct = 0.04       # 4% take profit
    leverage = 1
    exit_after_bars = 40
    signal_column = 'entry_signal'

    indicator_columns = ['ema_fast', 'ema_slow', 'adx', 'atr', 'entry_signal']

    def __init__(self, params: dict = None):
        """Initialize with default parameters"""
        super().__init__(params)

        self.fast_period = self.params.get('fast_period', 12)
        self.slow_period = self.params.get('slow_period', 26)
        self.adx_period = self.params.get('adx_period', 14)
        self.adx_threshold = self.params.get('adx_threshold', 25)
        self.atr_period = self.params.get('atr_period', 14)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pre-calculate all indicators and entry_signal"""
        df = df.copy()

        # EMAs
        df['ema_fast'] = ta.EMA(df['close'], timeperiod=self.fast_period)
        df['ema_slow'] = ta.EMA(df['close'], timeperiod=self.slow_period)

        # ADX
        df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=self.adx_period)

        # ATR
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=self.atr_period)

        # Entry signal: Bullish crossover + strong trend (vectorized)
        ema_fast_prev = df['ema_fast'].shift(1)
        ema_slow_prev = df['ema_slow'].shift(1)

        bullish_cross = (ema_fast_prev <= ema_slow_prev) & (df['ema_fast'] > df['ema_slow'])
        strong_trend = df['adx'] > self.adx_threshold

        df['entry_signal'] = (bullish_cross & strong_trend).astype(bool)

        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        """Generate signal for LIVE execution (reads pre-calculated entry_signal)"""
        min_bars = 100
        if len(df) < min_bars:
            return None

        if not df['entry_signal'].iloc[-1]:
            return None

        return Signal(
            direction=self.direction,
            leverage=self.leverage,
            sl_type=StopLossType.PERCENTAGE,
            sl_pct=self.sl_pct,
            tp_type=TakeProfitType.PERCENTAGE,
            tp_pct=self.tp_pct,
            exit_type=ExitType.TIME_BASED,
            exit_after_bars=self.exit_after_bars,
            reason=f"Bullish EMA crossover, ADX={df['adx'].iloc[-1]:.1f}"
        )
