"""
Backtest Data Loader

Loads and prepares historical OHLCV data for backtesting.
Uses BacktestCacheReader - NEVER downloads data.

Design Principles:
- Read-only: Uses pre-downloaded cache (run data_scheduler first)
- Fast fail: Crash if data doesn't exist
- No network: Never calls Binance API
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from src.utils.logger import get_logger
from src.backtester.cache_reader import BacktestCacheReader, CacheNotFoundError

logger = get_logger(__name__)


class BacktestDataLoader:
    """
    Loads historical data for backtesting

    IMPORTANT: This class reads ONLY from cache.
    Run data_scheduler to download data before using this.

    Supports:
    - Single symbol backtests
    - Multi-symbol backtests (portfolio)
    - Multiple timeframes
    - Date range filtering
    - Dual-period backtesting (full + recent)
    """

    def __init__(self, cache_dir: str = 'data/binance', config: Optional[dict] = None):
        self.cache_dir = Path(cache_dir)
        self.config = config

        # Use cache reader (never downloads)
        try:
            self.cache_reader = BacktestCacheReader(cache_dir=cache_dir)
        except CacheNotFoundError as e:
            logger.error(f"Cache not available: {e}")
            raise

    def load_single_symbol(
        self,
        symbol: str,
        timeframe: str,
        days: int = 180,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load OHLCV data for single symbol from cache

        Args:
            symbol: Trading pair (e.g., 'BTC', 'ETH')
            timeframe: Candle timeframe ('15m', '1h', '4h', '1d')
            days: Number of days to load
            end_date: End date (default: latest in cache)

        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]

        Raises:
            CacheNotFoundError: If data not in cache
        """
        logger.debug(f"Loading {symbol} {timeframe} data ({days} days) from cache")

        df = self.cache_reader.read(
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            end_date=end_date
        )

        if not df.empty:
            logger.debug(
                f"Loaded {len(df)} candles from "
                f"{df['timestamp'].min()} to {df['timestamp'].max()}"
            )

        return df

    def load_training_holdout(
        self,
        symbol: str,
        timeframe: str,
        training_days: int = 365,
        holdout_days: int = 30,
        end_date: Optional[datetime] = None
    ) -> tuple:
        """
        Load data split into training and holdout periods

        This method loads data for two NON-OVERLAPPING periods:
        1. Training period: older data for backtest metrics (e.g., 365 days)
        2. Holdout period: recent data NEVER seen during selection (e.g., last 30 days)

        The holdout serves TWO purposes:
        - Anti-overfitting: if strategy crashes on holdout, it's overfitted
        - Recency score: good holdout performance = strategy "in form" now

        Data layout:
        |---- Training (365 days) ----|---- Holdout (30 days) ----|
        ^                             ^                           ^
        start                    split point                     end

        Args:
            symbol: Trading pair (e.g., 'BTC', 'ETH')
            timeframe: Candle timeframe ('15m', '1h', '4h', '1d')
            training_days: Days for training period
            holdout_days: Days for holdout period (from end)
            end_date: End date (default: latest in cache)

        Returns:
            Tuple of (training_df, holdout_df) - NON-OVERLAPPING
        """
        total_days = training_days + holdout_days

        # Load all data
        df = self.cache_reader.read(
            symbol=symbol,
            timeframe=timeframe,
            days=total_days,
            end_date=end_date
        )

        if df.empty:
            return pd.DataFrame(), pd.DataFrame()

        # Calculate split point based on holdout_days from end
        if 'timestamp' in df.columns:
            df = df.sort_values('timestamp')
            end_ts = df['timestamp'].max()
            split_ts = end_ts - timedelta(days=holdout_days)

            training_df = df[df['timestamp'] < split_ts].copy()
            holdout_df = df[df['timestamp'] >= split_ts].copy()
        else:
            # Use index if no timestamp column
            df = df.sort_index()
            end_ts = df.index.max()
            split_ts = end_ts - timedelta(days=holdout_days)

            training_df = df[df.index < split_ts].copy()
            holdout_df = df[df.index >= split_ts].copy()

        logger.debug(
            f"Split {symbol} {timeframe}: "
            f"training={len(training_df)} candles, holdout={len(holdout_df)} candles"
        )

        return training_df, holdout_df

    def load_multi_symbol_training_holdout(
        self,
        symbols: List[str],
        timeframe: str,
        training_days: int = 365,
        holdout_days: int = 30,
        end_date: Optional[datetime] = None,
        target_count: Optional[int] = None,
        min_coverage_pct: float = 0.90
    ) -> tuple:
        """
        Load training/holdout data for multiple symbols

        Loads NON-OVERLAPPING training and holdout data for portfolio backtesting.

        Args:
            symbols: List of trading pairs (ordered by priority)
            timeframe: Candle timeframe
            training_days: Days for training period
            holdout_days: Days for holdout period
            end_date: End date
            target_count: Target number of symbols (uses all if None)
            min_coverage_pct: Minimum data coverage required

        Returns:
            Tuple of (training_data_dict, holdout_data_dict) - NON-OVERLAPPING
        """
        total_days = training_days + holdout_days

        # Limit symbols if target_count specified
        if target_count:
            symbols = symbols[:target_count * 2]  # Get extra in case some fail

        training_data = {}
        holdout_data = {}
        loaded = 0

        for symbol in symbols:
            if target_count and loaded >= target_count:
                break

            try:
                training_df, holdout_df = self.load_training_holdout(
                    symbol=symbol,
                    timeframe=timeframe,
                    training_days=training_days,
                    holdout_days=holdout_days,
                    end_date=end_date
                )

                # Check coverage
                if training_df.empty or holdout_df.empty:
                    continue

                # Calculate expected candles
                tf_minutes = self._timeframe_to_minutes(timeframe)
                expected_training = (training_days * 24 * 60) / tf_minutes
                expected_holdout = (holdout_days * 24 * 60) / tf_minutes

                training_coverage = len(training_df) / expected_training
                holdout_coverage = len(holdout_df) / expected_holdout

                if training_coverage < min_coverage_pct or holdout_coverage < min_coverage_pct:
                    logger.debug(
                        f"Skipping {symbol}: coverage too low "
                        f"(training={training_coverage:.1%}, holdout={holdout_coverage:.1%})"
                    )
                    continue

                training_data[symbol] = training_df
                holdout_data[symbol] = holdout_df
                loaded += 1

            except Exception as e:
                logger.debug(f"Failed to load {symbol}: {e}")
                continue

        logger.info(
            f"Loaded training/holdout data for {len(training_data)} symbols "
            f"({timeframe}, {training_days}d/{holdout_days}d)"
        )

        return training_data, holdout_data

    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes"""
        multipliers = {'m': 1, 'h': 60, 'd': 1440}
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        return value * multipliers.get(unit, 1)

    def load_multi_symbol(
        self,
        symbols: List[str],
        timeframe: str,
        days: int = 180,
        end_date: Optional[datetime] = None,
        target_count: Optional[int] = None,
        min_coverage_pct: float = 0.90
    ) -> Dict[str, pd.DataFrame]:
        """
        Load OHLCV data for multiple symbols

        Args:
            symbols: List of trading pairs
            timeframe: Candle timeframe
            days: Number of days to load
            end_date: End date
            target_count: Target number of symbols
            min_coverage_pct: Minimum data coverage required

        Returns:
            Dict mapping symbol -> DataFrame
        """
        # Limit symbols if target_count specified
        if target_count:
            symbols = symbols[:target_count * 2]

        data = self.cache_reader.read_multi_symbol(
            symbols=symbols,
            timeframe=timeframe,
            days=days,
            end_date=end_date,
            min_coverage_pct=min_coverage_pct
        )

        # Trim to target_count if needed
        if target_count and len(data) > target_count:
            symbols_to_keep = list(data.keys())[:target_count]
            data = {s: data[s] for s in symbols_to_keep}

        return data

    def _calculate_data_days(self, df: pd.DataFrame, timeframe: str) -> int:
        """Calculate actual number of days covered by data"""
        if df.empty:
            return 0

        if 'timestamp' in df.columns:
            first_ts = df['timestamp'].min()
            last_ts = df['timestamp'].max()
        else:
            first_ts = df.index.min()
            last_ts = df.index.max()

        return (last_ts - first_ts).days

    def prepare_vectorbt_format(
        self,
        data: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Convert multi-symbol data to VectorBT format

        VectorBT expects:
        - Index: timestamps (common across all symbols)
        - Columns: MultiIndex (symbol, ohlcv_field)

        Args:
            data: Dict mapping symbol -> DataFrame

        Returns:
            Multi-index DataFrame ready for VectorBT
        """
        if not data:
            raise ValueError("No data provided")

        # Get common timestamps (intersection of all symbols)
        timestamps = None
        for symbol, df in data.items():
            symbol_timestamps = set(df['timestamp'])
            if timestamps is None:
                timestamps = symbol_timestamps
            else:
                timestamps = timestamps.intersection(symbol_timestamps)

        if not timestamps:
            raise ValueError("No common timestamps across symbols")

        timestamps = sorted(timestamps)
        logger.debug(f"Common timestamp range: {len(timestamps)} candles")

        # Build multi-index DataFrame
        dfs = {}

        for symbol, df in data.items():
            # Filter to common timestamps
            df_filtered = df[df['timestamp'].isin(timestamps)].copy()
            df_filtered = df_filtered.set_index('timestamp').sort_index()

            # Add to dict with symbol prefix
            for col in ['open', 'high', 'low', 'close', 'volume']:
                dfs[(symbol, col)] = df_filtered[col]

        # Combine into multi-index DataFrame
        result = pd.DataFrame(dfs)
        result.columns = pd.MultiIndex.from_tuples(
            result.columns,
            names=['symbol', 'ohlcv']
        )

        logger.debug(f"Prepared VectorBT data: {len(result)} rows x {len(result.columns)} columns")

        return result

    def walk_forward_split(
        self,
        df: pd.DataFrame,
        n_windows: int = 4,
        train_pct: float = 0.75
    ) -> List[tuple]:
        """
        Create walk-forward validation windows

        Args:
            df: Input DataFrame
            n_windows: Number of expanding windows
            train_pct: Initial train/test split

        Returns:
            List of (train_df, test_df) tuples
        """
        total_len = len(df)
        windows = []

        for i in range(n_windows):
            train_end_pct = train_pct + (i * (1 - train_pct) / n_windows)
            train_end = int(total_len * train_end_pct)

            test_end_pct = train_end_pct + ((1 - train_pct) / n_windows)
            test_end = int(total_len * test_end_pct)

            train_df = df.iloc[:train_end]
            test_df = df.iloc[train_end:test_end]

            logger.debug(
                f"Window {i+1}: Train {len(train_df)} -> Test {len(test_df)} candles"
            )

            windows.append((train_df, test_df))

        return windows

    def get_available_symbols(self) -> List[str]:
        """Get list of symbols available in cache"""
        return self.cache_reader.list_cached_symbols()

    def get_available_timeframes(self, symbol: str) -> List[str]:
        """Get list of timeframes available for a symbol"""
        return self.cache_reader.list_cached_timeframes(symbol)


class BinanceDataLoader:
    """
    Binance data loader (alias for BacktestDataLoader)

    Loads OHLCV data from cache for backtesting.
    """

    def __init__(self):
        self.loader = BacktestDataLoader()

    def load_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load OHLCV data for symbol

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe ('15m', '1h', etc.)
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with OHLCV data
        """
        # Calculate days from date range
        if start_date and end_date:
            days = (end_date - start_date).days
        elif start_date:
            days = (datetime.now() - start_date).days
        else:
            days = 180

        # Convert symbol format: BTC/USDT -> BTC
        symbol_clean = symbol.split('/')[0]

        df = self.loader.load_single_symbol(
            symbol=symbol_clean,
            timeframe=timeframe,
            days=days,
            end_date=end_date
        )

        # Filter by start_date if specified
        if start_date and not df.empty:
            df = df[df['timestamp'] >= start_date]

        return df

    def validate_data(self, df: pd.DataFrame) -> bool:
        """Validate OHLCV data integrity"""
        required_cols = ['open', 'high', 'low', 'close', 'volume']

        if not all(col in df.columns for col in required_cols):
            logger.error("Missing required columns")
            return False

        if df[required_cols].isna().any().any():
            logger.error("Found NaN values in OHLCV data")
            return False

        if (df['high'] < df['low']).any():
            logger.error("Invalid OHLC: high < low detected")
            return False

        return True
