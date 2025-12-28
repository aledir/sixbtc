"""
Backtest Cache Reader

Reads ONLY from parquet cache files. Never downloads.
This ensures backtests are fast and don't depend on network.

Design Principles:
- Read-only: NEVER downloads data
- Fast fail: Crash if data doesn't exist
- Simple: Just read parquet files
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from src.utils.logger import get_logger

logger = get_logger(__name__)


class CacheNotFoundError(Exception):
    """Raised when required cache data is not found"""
    pass


class BacktestCacheReader:
    """
    Read-only cache reader for backtesting

    NEVER downloads data - use data_scheduler for that.
    If data doesn't exist, raises CacheNotFoundError.
    """

    def __init__(self, cache_dir: str = 'data/binance'):
        """
        Initialize cache reader

        Args:
            cache_dir: Directory containing parquet cache files
        """
        self.cache_dir = Path(cache_dir)

        if not self.cache_dir.exists():
            raise CacheNotFoundError(
                f"Cache directory does not exist: {self.cache_dir}\n"
                "Run data_scheduler first to download data."
            )

        logger.debug(f"BacktestCacheReader initialized - cache_dir: {self.cache_dir}")

    def read(
        self,
        symbol: str,
        timeframe: str,
        days: Optional[int] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Read OHLCV data from cache

        Args:
            symbol: Trading pair (e.g., 'BTC', 'ETH')
            timeframe: Candle timeframe ('15m', '1h', '4h', '1d')
            days: Number of days to load (None = all available)
            end_date: End date (default: latest in cache)

        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]

        Raises:
            CacheNotFoundError: If cache file doesn't exist
        """
        file_path = self.cache_dir / f"{symbol}_{timeframe}.parquet"

        if not file_path.exists():
            raise CacheNotFoundError(
                f"Cache not found: {file_path}\n"
                f"Run data_scheduler to download {symbol} {timeframe} data first."
            )

        # Read parquet
        df = pd.read_parquet(file_path)

        if df.empty:
            logger.warning(f"Cache file is empty: {file_path}")
            return df

        # Ensure timestamp column is datetime
        if 'timestamp' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

        # Filter by end_date
        if end_date is not None:
            if 'timestamp' in df.columns:
                df = df[df['timestamp'] <= end_date]

        # Filter by days
        if days is not None and not df.empty:
            if 'timestamp' in df.columns:
                data_end = df['timestamp'].max()
            else:
                data_end = df.index.max()

            start_date = data_end - timedelta(days=days)

            if 'timestamp' in df.columns:
                df = df[df['timestamp'] >= start_date]
            else:
                df = df[df.index >= start_date]

        logger.debug(
            f"Read {len(df)} candles for {symbol} {timeframe} "
            f"({df['timestamp'].min()} to {df['timestamp'].max()})"
        )

        return df.reset_index(drop=True)

    def read_dual_periods(
        self,
        symbol: str,
        timeframe: str,
        full_period_days: int = 180,
        recent_period_days: int = 60,
        end_date: Optional[datetime] = None
    ) -> tuple:
        """
        Read data for dual-period backtesting

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            full_period_days: Total lookback days
            recent_period_days: Days for recent period
            end_date: End date

        Returns:
            Tuple of (full_period_df, recent_period_df)
        """
        # Read full period
        full_df = self.read(
            symbol=symbol,
            timeframe=timeframe,
            days=full_period_days,
            end_date=end_date
        )

        if full_df.empty:
            return full_df, full_df

        # Calculate recent period
        if 'timestamp' in full_df.columns:
            data_end = full_df['timestamp'].max()
        else:
            data_end = full_df.index.max()

        recent_start = data_end - timedelta(days=recent_period_days)

        if 'timestamp' in full_df.columns:
            recent_df = full_df[full_df['timestamp'] >= recent_start].copy()
        else:
            recent_df = full_df[full_df.index >= recent_start].copy()

        logger.debug(
            f"Dual periods for {symbol}: full={len(full_df)}, recent={len(recent_df)}"
        )

        return full_df, recent_df

    def read_multi_symbol(
        self,
        symbols: List[str],
        timeframe: str,
        days: int = 180,
        end_date: Optional[datetime] = None,
        min_coverage_pct: float = 0.90
    ) -> Dict[str, pd.DataFrame]:
        """
        Read data for multiple symbols

        Args:
            symbols: List of trading pairs
            timeframe: Candle timeframe
            days: Number of days to load
            end_date: End date
            min_coverage_pct: Minimum data coverage required

        Returns:
            Dict mapping symbol -> DataFrame (only symbols with data)
        """
        data = {}
        skipped = []

        for symbol in symbols:
            try:
                df = self.read(symbol, timeframe, days, end_date)

                if df.empty:
                    skipped.append((symbol, "empty"))
                    continue

                # Validate coverage
                actual_days = self._calculate_data_days(df)
                coverage = actual_days / days if days > 0 else 0

                if coverage < min_coverage_pct:
                    skipped.append((symbol, f"{actual_days}d < {days}d ({coverage:.0%})"))
                    continue

                data[symbol] = df

            except CacheNotFoundError:
                skipped.append((symbol, "not cached"))
                continue

        if skipped:
            logger.info(f"Skipped {len(skipped)} symbols: {skipped[:5]}...")

        logger.info(f"Read {len(data)}/{len(symbols)} symbols from cache")

        return data

    def read_multi_symbol_dual_periods(
        self,
        symbols: List[str],
        timeframe: str,
        full_period_days: int = 180,
        recent_period_days: int = 60,
        end_date: Optional[datetime] = None,
        min_coverage_pct: float = 0.90
    ) -> tuple:
        """
        Read dual-period data for multiple symbols

        Args:
            symbols: List of trading pairs
            timeframe: Candle timeframe
            full_period_days: Total lookback days
            recent_period_days: Recent period days
            end_date: End date
            min_coverage_pct: Minimum data coverage required

        Returns:
            Tuple of (full_data_dict, recent_data_dict)
        """
        full_data = {}
        recent_data = {}
        skipped = []

        for symbol in symbols:
            try:
                full_df, recent_df = self.read_dual_periods(
                    symbol=symbol,
                    timeframe=timeframe,
                    full_period_days=full_period_days,
                    recent_period_days=recent_period_days,
                    end_date=end_date
                )

                if full_df.empty:
                    skipped.append((symbol, "empty"))
                    continue

                # Validate coverage
                actual_days = self._calculate_data_days(full_df)
                coverage = actual_days / full_period_days if full_period_days > 0 else 0

                if coverage < min_coverage_pct:
                    skipped.append((symbol, f"{actual_days}d < {full_period_days}d"))
                    continue

                full_data[symbol] = full_df
                recent_data[symbol] = recent_df

            except CacheNotFoundError:
                skipped.append((symbol, "not cached"))
                continue

        if skipped:
            logger.info(f"Skipped {len(skipped)} symbols for dual periods")

        logger.info(
            f"Read {len(full_data)}/{len(symbols)} symbols "
            f"for dual-period backtest"
        )

        return full_data, recent_data

    def list_cached_symbols(self, timeframe: Optional[str] = None) -> List[str]:
        """
        List all symbols available in cache

        Args:
            timeframe: Filter by timeframe (optional)

        Returns:
            List of symbol names
        """
        symbols = set()

        pattern = f"*_{timeframe}.parquet" if timeframe else "*.parquet"

        for file in self.cache_dir.glob(pattern):
            # File format: {symbol}_{timeframe}.parquet
            symbol = file.stem.split('_')[0]
            symbols.add(symbol)

        return sorted(symbols)

    def list_cached_timeframes(self, symbol: str) -> List[str]:
        """
        List all timeframes available for a symbol

        Args:
            symbol: Symbol to check

        Returns:
            List of timeframes
        """
        timeframes = []

        for file in self.cache_dir.glob(f"{symbol}_*.parquet"):
            # File format: {symbol}_{timeframe}.parquet
            tf = file.stem.split('_')[1]
            timeframes.append(tf)

        return sorted(timeframes)

    def get_cache_info(self, symbol: str, timeframe: str) -> Optional[dict]:
        """
        Get information about cached data

        Args:
            symbol: Symbol
            timeframe: Timeframe

        Returns:
            Dict with cache info or None if not found
        """
        file_path = self.cache_dir / f"{symbol}_{timeframe}.parquet"

        if not file_path.exists():
            return None

        df = pd.read_parquet(file_path)

        if df.empty:
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'file': str(file_path),
                'candles': 0,
                'start': None,
                'end': None,
                'days': 0
            }

        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'file': str(file_path),
            'candles': len(df),
            'start': df['timestamp'].min(),
            'end': df['timestamp'].max(),
            'days': self._calculate_data_days(df)
        }

    def _calculate_data_days(self, df: pd.DataFrame) -> int:
        """Calculate number of days covered by data"""
        if df.empty:
            return 0

        if 'timestamp' in df.columns:
            first_ts = df['timestamp'].min()
            last_ts = df['timestamp'].max()
        else:
            first_ts = df.index.min()
            last_ts = df.index.max()

        return (last_ts - first_ts).days
