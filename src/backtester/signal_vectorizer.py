"""
Signal Vectorizer

Converts candle-by-candle generate_signal() to fast vectorized execution.

The trick: instead of copying df.iloc[:i+1] for each bar (O(n²)),
we pass a lightweight "cursor view" that makes iloc[-1] point to bar i.

This gives 10-100x speedup while using the SAME strategy code.
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass

from src.strategies.base import StrategyCore, Signal
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CursorDataFrame:
    """
    Lightweight view of a DataFrame with a movable cursor.

    Makes the strategy think it's looking at df.iloc[:cursor+1]
    but without actually copying data.

    Supports:
    - df.iloc[-1] -> row at cursor
    - df.iloc[-N:] -> last N rows up to cursor
    - df['column'] -> Series with cursor limit
    - df['column'].iloc[-1] -> value at cursor
    - len(df) -> cursor + 1
    """

    __slots__ = ['_df', '_cursor', '_columns_cache']

    def __init__(self, df: pd.DataFrame, cursor: int = 0):
        self._df = df
        self._cursor = cursor
        self._columns_cache: Dict[str, 'CursorSeries'] = {}

    def set_cursor(self, cursor: int):
        """Move cursor to new position"""
        self._cursor = cursor
        # Clear cache when cursor moves
        self._columns_cache.clear()

    def __len__(self) -> int:
        """Length appears as cursor + 1 (simulates truncated df)"""
        return self._cursor + 1

    def __getitem__(self, key):
        """Access column by name"""
        if isinstance(key, str):
            if key not in self._columns_cache:
                self._columns_cache[key] = CursorSeries(
                    self._df[key].values,
                    self._cursor
                )
            else:
                # Update cursor in cached series
                self._columns_cache[key]._cursor = self._cursor
            return self._columns_cache[key]
        raise KeyError(f"Only string column access supported, got {type(key)}")

    @property
    def iloc(self) -> 'CursorILoc':
        """Support df.iloc[-1] etc."""
        return CursorILoc(self._df, self._cursor)

    @property
    def columns(self):
        """Return column names"""
        return self._df.columns

    @property
    def index(self):
        """Return index up to cursor"""
        return self._df.index[:self._cursor + 1]

    def copy(self) -> pd.DataFrame:
        """
        Return actual truncated DataFrame.
        Used if strategy really needs a copy.
        """
        return self._df.iloc[:self._cursor + 1].copy()


class CursorSeries:
    """
    Lightweight view of a Series with cursor limit.

    Supports:
    - series.iloc[-1] -> value at cursor
    - series.iloc[-N:] -> last N values
    - series.values -> numpy array up to cursor
    """

    __slots__ = ['_values', '_cursor']

    def __init__(self, values: np.ndarray, cursor: int):
        self._values = values
        self._cursor = cursor

    def __len__(self) -> int:
        return self._cursor + 1

    @property
    def iloc(self) -> 'SeriesILoc':
        return SeriesILoc(self._values, self._cursor)

    @property
    def values(self) -> np.ndarray:
        """Return values up to cursor (view, not copy)"""
        return self._values[:self._cursor + 1]

    def __array__(self) -> np.ndarray:
        """Support numpy operations"""
        return self._values[:self._cursor + 1]


class CursorILoc:
    """iloc accessor for CursorDataFrame"""

    __slots__ = ['_df', '_cursor']

    def __init__(self, df: pd.DataFrame, cursor: int):
        self._df = df
        self._cursor = cursor

    def __getitem__(self, key):
        if isinstance(key, int):
            # Handle negative indexing
            if key < 0:
                actual_idx = self._cursor + 1 + key
            else:
                actual_idx = key

            if actual_idx < 0 or actual_idx > self._cursor:
                raise IndexError(f"Index {key} out of bounds for cursor {self._cursor}")

            return self._df.iloc[actual_idx]

        elif isinstance(key, slice):
            # Handle slices like iloc[-10:]
            start, stop = key.start, key.stop

            # Convert negative indices
            if start is not None and start < 0:
                start = max(0, self._cursor + 1 + start)
            if stop is None:
                stop = self._cursor + 1
            elif stop < 0:
                stop = self._cursor + 1 + stop

            return self._df.iloc[start:stop]

        raise TypeError(f"Invalid iloc key type: {type(key)}")


class SeriesILoc:
    """iloc accessor for CursorSeries"""

    __slots__ = ['_values', '_cursor']

    def __init__(self, values: np.ndarray, cursor: int):
        self._values = values
        self._cursor = cursor

    def __getitem__(self, key):
        if isinstance(key, int):
            if key < 0:
                actual_idx = self._cursor + 1 + key
            else:
                actual_idx = key

            if actual_idx < 0 or actual_idx > self._cursor:
                raise IndexError(f"Index {key} out of bounds")

            return self._values[actual_idx]

        elif isinstance(key, slice):
            start, stop = key.start, key.stop

            if start is not None and start < 0:
                start = max(0, self._cursor + 1 + start)
            if stop is None:
                stop = self._cursor + 1
            elif stop < 0:
                stop = self._cursor + 1 + stop

            return self._values[start:stop]

        raise TypeError(f"Invalid iloc key type: {type(key)}")


@dataclass
class VectorizedSignals:
    """Result of vectorized signal generation"""
    signals: np.ndarray  # 1=long, -1=short, 0=none
    sl_multipliers: np.ndarray  # ATR multiplier for SL
    tp_multipliers: np.ndarray  # ATR multiplier for TP
    leverages: np.ndarray  # Leverage per signal

    def to_dataframe(self, index: pd.Index) -> pd.DataFrame:
        return pd.DataFrame({
            'signal': self.signals,
            'sl_multiplier': self.sl_multipliers,
            'tp_multiplier': self.tp_multipliers,
            'leverage': self.leverages
        }, index=index)


class SignalVectorizer:
    """
    Wraps a StrategyCore to generate signals efficiently using two-phase approach.

    TWO-PHASE APPROACH:
    1. calculate_indicators(df) - Called ONCE on full dataframe
    2. generate_signal(df_with_indicators) - Called per bar, reads pre-calculated values

    This gives O(n) indicator calculation instead of O(n^2).

    Usage:
        strategy = Strategy_MOM_abc123()
        vectorizer = SignalVectorizer(strategy, warmup=50)

        # Generate all signals at once
        result = vectorizer.generate_all(df)

        # Or step through bar by bar (for live)
        for i in range(warmup, len(df)):
            vectorizer.step(i)
            signal = vectorizer.get_current_signal()
    """

    def __init__(self, strategy: StrategyCore, warmup: int = 50):
        """
        Initialize vectorizer.

        Args:
            strategy: StrategyCore instance
            warmup: Minimum bars before generating signals
        """
        self.strategy = strategy
        self.warmup = warmup
        self._cursor_df: Optional[CursorDataFrame] = None
        self._df_with_indicators: Optional[pd.DataFrame] = None
        self._current_signal: Optional[Signal] = None

    def generate_all(
        self,
        df: pd.DataFrame,
        symbol: str = 'BTC'
    ) -> VectorizedSignals:
        """
        Generate signals for entire DataFrame using two-phase approach.

        This is the fast path for backtesting.

        Args:
            df: OHLCV DataFrame
            symbol: Trading symbol

        Returns:
            VectorizedSignals with arrays of signals
        """
        n = len(df)

        # Pre-allocate result arrays
        signals = np.zeros(n, dtype=np.int8)
        sl_multipliers = np.full(n, 2.0, dtype=np.float32)
        tp_multipliers = np.full(n, 3.0, dtype=np.float32)
        leverages = np.ones(n, dtype=np.int8)

        # PHASE 1: Calculate indicators ONCE on full dataframe
        try:
            df_with_indicators = self.strategy.calculate_indicators(df)
            logger.debug(f"Calculated indicators: {self.strategy.indicator_columns}")
        except Exception as e:
            logger.warning(f"calculate_indicators() failed, using raw data: {e}")
            df_with_indicators = df.copy()

        # Create cursor view on df_with_indicators
        cursor_df = CursorDataFrame(df_with_indicators)

        # Calculate effective warmup
        effective_warmup = min(self.warmup, n - 1)

        # PHASE 2: Generate signals bar by bar using cursor view
        for i in range(effective_warmup, n):
            cursor_df.set_cursor(i)

            try:
                signal = self.strategy.generate_signal(cursor_df, symbol)

                if signal is not None:
                    if signal.direction == 'long':
                        signals[i] = 1
                    elif signal.direction == 'short':
                        signals[i] = -1

                    sl_multipliers[i] = signal.atr_stop_multiplier
                    tp_multipliers[i] = signal.atr_take_multiplier
                    leverages[i] = signal.leverage

            except Exception as e:
                # Log but continue - don't break the loop
                if i % 1000 == 0:  # Log every 1000 bars to avoid spam
                    logger.debug(f"Signal generation error at bar {i}: {e}")
                continue

        return VectorizedSignals(
            signals=signals,
            sl_multipliers=sl_multipliers,
            tp_multipliers=tp_multipliers,
            leverages=leverages
        )

    def prepare(self, df: pd.DataFrame):
        """
        Prepare for stepping through bars (live mode).

        Calculates indicators ONCE, then creates cursor for iteration.

        Args:
            df: Full OHLCV DataFrame
        """
        # PHASE 1: Calculate indicators once
        try:
            self._df_with_indicators = self.strategy.calculate_indicators(df)
        except Exception as e:
            logger.warning(f"calculate_indicators() failed: {e}")
            self._df_with_indicators = df.copy()

        self._cursor_df = CursorDataFrame(self._df_with_indicators)
        self._current_signal = None

    def step(self, bar: int, symbol: str = 'BTC') -> Optional[Signal]:
        """
        Step to bar and generate signal.

        Args:
            bar: Bar index to process
            symbol: Trading symbol

        Returns:
            Signal if generated, None otherwise
        """
        if self._cursor_df is None:
            raise RuntimeError("Call prepare() first")

        if bar < self.warmup:
            return None

        self._cursor_df.set_cursor(bar)

        try:
            self._current_signal = self.strategy.generate_signal(
                self._cursor_df, symbol
            )
        except Exception as e:
            logger.debug(f"Signal error at bar {bar}: {e}")
            self._current_signal = None

        return self._current_signal

    def get_current_signal(self) -> Optional[Signal]:
        """Get signal from last step()"""
        return self._current_signal


def vectorize_strategy(
    strategy: StrategyCore,
    df: pd.DataFrame,
    symbol: str = 'BTC',
    warmup: int = 50
) -> VectorizedSignals:
    """
    Convenience function to vectorize a strategy.

    Args:
        strategy: StrategyCore instance
        df: OHLCV DataFrame
        symbol: Trading symbol
        warmup: Warmup bars

    Returns:
        VectorizedSignals
    """
    vectorizer = SignalVectorizer(strategy, warmup=warmup)
    return vectorizer.generate_all(df, symbol)


class PrecomputedDataFrame:
    """
    DataFrame with pre-computed indicators.

    For maximum performance, indicators are calculated ONCE for the entire
    DataFrame, then we use a cursor to simulate truncated data.

    Supports common TA-lib indicators:
    - RSI, ATR, SMA, EMA, MACD, Bollinger Bands, etc.
    """

    __slots__ = ['_df', '_cursor', '_indicators', '_columns_cache']

    # Common indicator periods to pre-compute
    DEFAULT_PERIODS = [7, 14, 20, 21, 50, 100, 200]
    ATR_PERIODS = [7, 14, 20]
    RSI_PERIODS = [7, 14, 21]

    def __init__(self, df: pd.DataFrame, precompute: bool = True):
        """
        Initialize with optional indicator pre-computation.

        Args:
            df: OHLCV DataFrame
            precompute: If True, calculate common indicators upfront
        """
        self._df = df.copy()
        self._cursor = len(df) - 1
        self._indicators: Dict[str, np.ndarray] = {}
        self._columns_cache: Dict[str, 'PrecomputedSeries'] = {}

        if precompute:
            self._precompute_indicators()

    def _precompute_indicators(self):
        """Pre-compute common indicators"""
        try:
            import talib as ta
        except ImportError:
            logger.warning("TA-Lib not available, skipping precomputation")
            return

        close = self._df['close'].values
        high = self._df['high'].values
        low = self._df['low'].values
        volume = self._df['volume'].values

        # RSI
        for period in self.RSI_PERIODS:
            key = f'rsi_{period}'
            self._indicators[key] = ta.RSI(close, timeperiod=period)

        # ATR
        for period in self.ATR_PERIODS:
            key = f'atr_{period}'
            self._indicators[key] = ta.ATR(high, low, close, timeperiod=period)

        # SMA
        for period in self.DEFAULT_PERIODS:
            key = f'sma_{period}'
            self._indicators[key] = ta.SMA(close, timeperiod=period)

        # EMA
        for period in self.DEFAULT_PERIODS:
            key = f'ema_{period}'
            self._indicators[key] = ta.EMA(close, timeperiod=period)

        # Bollinger Bands (20, 2)
        self._indicators['bb_upper'], self._indicators['bb_middle'], self._indicators['bb_lower'] = \
            ta.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)

        # MACD
        self._indicators['macd'], self._indicators['macd_signal'], self._indicators['macd_hist'] = \
            ta.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)

        # Stochastic
        self._indicators['stoch_k'], self._indicators['stoch_d'] = \
            ta.STOCH(high, low, close, fastk_period=14, slowk_period=3, slowd_period=3)

        # ADX
        self._indicators['adx_14'] = ta.ADX(high, low, close, timeperiod=14)

        # Volume SMA
        self._indicators['volume_sma_20'] = ta.SMA(volume.astype(float), timeperiod=20)

        logger.debug(f"Pre-computed {len(self._indicators)} indicators")

    def set_cursor(self, cursor: int):
        """Move cursor to new position"""
        self._cursor = cursor
        self._columns_cache.clear()

    def __len__(self) -> int:
        return self._cursor + 1

    def __getitem__(self, key: str):
        """Access column or indicator by name"""
        if key not in self._columns_cache:
            if key in self._df.columns:
                values = self._df[key].values
            elif key in self._indicators:
                values = self._indicators[key]
            else:
                raise KeyError(f"Column or indicator '{key}' not found")

            self._columns_cache[key] = PrecomputedSeries(values, self._cursor)
        else:
            self._columns_cache[key]._cursor = self._cursor

        return self._columns_cache[key]

    def get_indicator(self, name: str, period: int = None) -> 'PrecomputedSeries':
        """
        Get pre-computed indicator.

        Args:
            name: Indicator name (rsi, atr, sma, ema, etc.)
            period: Period (if applicable)

        Returns:
            PrecomputedSeries with indicator values
        """
        if period:
            key = f'{name}_{period}'
        else:
            key = name

        if key in self._indicators:
            return PrecomputedSeries(self._indicators[key], self._cursor)

        raise KeyError(f"Indicator '{key}' not pre-computed")

    @property
    def iloc(self) -> 'CursorILoc':
        return CursorILoc(self._df, self._cursor)

    @property
    def columns(self):
        return self._df.columns

    @property
    def index(self):
        return self._df.index[:self._cursor + 1]

    def copy(self) -> pd.DataFrame:
        """Return actual truncated DataFrame with indicators"""
        result = self._df.iloc[:self._cursor + 1].copy()
        for key, values in self._indicators.items():
            result[key] = values[:self._cursor + 1]
        return result


class PrecomputedSeries:
    """Series view with cursor limit and pre-computed values"""

    __slots__ = ['_values', '_cursor']

    def __init__(self, values: np.ndarray, cursor: int):
        self._values = values
        self._cursor = cursor

    def __len__(self) -> int:
        return self._cursor + 1

    @property
    def iloc(self) -> 'SeriesILoc':
        return SeriesILoc(self._values, self._cursor)

    @property
    def values(self) -> np.ndarray:
        return self._values[:self._cursor + 1]

    def __array__(self) -> np.ndarray:
        return self._values[:self._cursor + 1]

    def max(self) -> float:
        return np.nanmax(self._values[:self._cursor + 1])

    def min(self) -> float:
        return np.nanmin(self._values[:self._cursor + 1])

    def mean(self) -> float:
        return np.nanmean(self._values[:self._cursor + 1])


class FastSignalVectorizer:
    """
    Ultra-fast signal vectorizer using strategy's two-phase approach.

    DEPRECATED: Use SignalVectorizer instead. Both now use the same
    two-phase approach where strategies define their own indicators.

    Usage:
        strategy = MyStrategy()
        vectorizer = FastSignalVectorizer(strategy, warmup=50)
        result = vectorizer.generate_all(df, 'BTC')
    """

    def __init__(self, strategy: StrategyCore, warmup: int = 50):
        self.strategy = strategy
        self.warmup = warmup

    def generate_all(
        self,
        df: pd.DataFrame,
        symbol: str = 'BTC'
    ) -> VectorizedSignals:
        """
        Generate signals using strategy's two-phase approach.

        Args:
            df: OHLCV DataFrame
            symbol: Trading symbol

        Returns:
            VectorizedSignals
        """
        n = len(df)

        # Pre-allocate result arrays
        signals = np.zeros(n, dtype=np.int8)
        sl_multipliers = np.full(n, 2.0, dtype=np.float32)
        tp_multipliers = np.full(n, 3.0, dtype=np.float32)
        leverages = np.ones(n, dtype=np.int8)

        # PHASE 1: Calculate strategy's indicators ONCE on full dataframe
        try:
            df_with_indicators = self.strategy.calculate_indicators(df)
            logger.debug(f"Calculated indicators: {self.strategy.indicator_columns}")
        except Exception as e:
            logger.warning(f"calculate_indicators() failed, using raw data: {e}")
            df_with_indicators = df.copy()

        # Create cursor view on df_with_indicators
        cursor_df = CursorDataFrame(df_with_indicators)

        effective_warmup = min(self.warmup, n - 1)

        # PHASE 2: Generate signals bar by bar
        for i in range(effective_warmup, n):
            cursor_df.set_cursor(i)

            try:
                signal = self.strategy.generate_signal(cursor_df, symbol)

                if signal is not None:
                    if signal.direction == 'long':
                        signals[i] = 1
                    elif signal.direction == 'short':
                        signals[i] = -1

                    sl_multipliers[i] = signal.atr_stop_multiplier
                    tp_multipliers[i] = signal.atr_take_multiplier
                    leverages[i] = signal.leverage

            except Exception as e:
                if i % 1000 == 0:
                    logger.debug(f"Signal error at bar {i}: {e}")
                continue

        return VectorizedSignals(
            signals=signals,
            sl_multipliers=sl_multipliers,
            tp_multipliers=tp_multipliers,
            leverages=leverages
        )
