"""
Backtest Data Loader

Loads and prepares historical OHLCV data for backtesting.
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from src.utils.logger import get_logger
from src.data.binance_downloader import BinanceDataDownloader

logger = get_logger(__name__)


class BacktestDataLoader:
    """
    Loads historical data for backtesting

    Supports:
    - Single symbol backtests
    - Multi-symbol backtests (portfolio)
    - Multiple timeframes
    - Date range filtering
    - Dual-period backtesting (full + recent)
    """

    def __init__(self, cache_dir: str = 'data/binance', config: Optional[dict] = None):
        self.cache_dir = Path(cache_dir)
        self.downloader = BinanceDataDownloader()
        self.config = config

    def load_single_symbol(
        self,
        symbol: str,
        timeframe: str,
        days: int = 180,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load OHLCV data for single symbol

        Args:
            symbol: Trading pair (e.g., 'BTC', 'ETH')
            timeframe: Candle timeframe ('15m', '1h', '4h', '1d')
            days: Number of days to load
            end_date: End date (default: now)

        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]
        """
        logger.info(f"Loading {symbol} {timeframe} data ({days} days)")

        # Download from Binance (uses cache if available)
        df = self.downloader.download_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            days=days
        )

        # Filter by end_date if specified
        if end_date:
            df = df[df['timestamp'] <= end_date]

        logger.info(f"Loaded {len(df)} candles from {df['timestamp'].min()} to {df['timestamp'].max()}")

        return df

    def load_dual_periods(
        self,
        symbol: str,
        timeframe: str,
        full_period_days: int = 180,
        recent_period_days: int = 60,
        end_date: Optional[datetime] = None
    ) -> tuple:
        """
        Load data for dual-period backtesting

        This method loads data for two periods:
        1. Full period: entire lookback window (e.g., 180 days)
        2. Recent period: only recent data (e.g., last 60 days)

        The recent period is used to validate that a strategy is "in form"
        and hasn't degraded in recent market conditions.

        Args:
            symbol: Trading pair (e.g., 'BTC', 'ETH')
            timeframe: Candle timeframe ('15m', '1h', '4h', '1d')
            full_period_days: Total lookback days for full period
            recent_period_days: Days for recent period (from end)
            end_date: End date (default: now)

        Returns:
            Tuple of (full_period_df, recent_period_df)
        """
        logger.info(
            f"Loading dual periods for {symbol} {timeframe}: "
            f"full={full_period_days}d, recent={recent_period_days}d"
        )

        # Load full period data
        full_df = self.load_single_symbol(
            symbol=symbol,
            timeframe=timeframe,
            days=full_period_days,
            end_date=end_date
        )

        if full_df.empty:
            logger.warning(f"No data loaded for {symbol}")
            return full_df, full_df

        # Calculate recent period start
        # Get end_date from actual data if not specified
        if 'timestamp' in full_df.columns:
            data_end = full_df['timestamp'].max()
        else:
            data_end = full_df.index.max()

        # Handle timezone-aware vs naive datetime
        if hasattr(data_end, 'tzinfo') and data_end.tzinfo is not None:
            # Data is timezone-aware, make recent_start timezone-aware too
            import pytz
            recent_start = (data_end - timedelta(days=recent_period_days))
        else:
            recent_start = data_end - timedelta(days=recent_period_days)

        # Filter for recent period
        if 'timestamp' in full_df.columns:
            recent_df = full_df[full_df['timestamp'] >= recent_start].copy()
        else:
            # If timestamp is index
            recent_df = full_df[full_df.index >= recent_start].copy()

        logger.info(
            f"Dual periods loaded: full={len(full_df)} candles, "
            f"recent={len(recent_df)} candles"
        )

        return full_df, recent_df

    def load_multi_symbol_dual_periods(
        self,
        symbols: List[str],
        timeframe: str,
        full_period_days: int = 180,
        recent_period_days: int = 60,
        end_date: Optional[datetime] = None,
        target_count: Optional[int] = None,
        min_coverage_pct: float = 0.90
    ) -> tuple:
        """
        Load dual-period data for multiple symbols with history validation

        Filters out symbols with insufficient history and can fetch additional
        symbols to reach a target count.

        Args:
            symbols: List of trading pairs (ordered by priority, e.g., volume)
            timeframe: Candle timeframe
            full_period_days: Total lookback days (minimum required history)
            recent_period_days: Recent period days
            end_date: End date (default: now)
            target_count: Target number of symbols to return
            min_coverage_pct: Minimum data coverage required (0.90 = 90%)

        Returns:
            Tuple of (full_data_dict, recent_data_dict)
            Each dict maps symbol -> DataFrame (only symbols with sufficient history)
        """
        target = target_count or len(symbols)
        logger.info(
            f"Loading multi-symbol dual periods: {len(symbols)} candidates, "
            f"target={target}, {timeframe}, full={full_period_days}d, recent={recent_period_days}d"
        )

        full_data = {}
        recent_data = {}
        skipped = []

        for symbol in symbols:
            if len(full_data) >= target:
                break

            try:
                full_df, recent_df = self.load_dual_periods(
                    symbol=symbol,
                    timeframe=timeframe,
                    full_period_days=full_period_days,
                    recent_period_days=recent_period_days,
                    end_date=end_date
                )

                if full_df.empty:
                    skipped.append((symbol, "empty"))
                    continue

                # Validate history coverage
                actual_days = self._calculate_data_days(full_df, timeframe)
                coverage = actual_days / full_period_days if full_period_days > 0 else 0

                if coverage < min_coverage_pct:
                    skipped.append((symbol, f"{actual_days}d < {full_period_days}d ({coverage:.0%})"))
                    logger.debug(
                        f"Skipping {symbol}: insufficient history "
                        f"({actual_days} days, need {full_period_days})"
                    )
                    continue

                full_data[symbol] = full_df
                recent_data[symbol] = recent_df

            except Exception as e:
                skipped.append((symbol, str(e)))
                logger.error(f"Failed to load dual periods for {symbol}: {e}")
                continue

        if skipped:
            logger.info(f"Skipped {len(skipped)} symbols with insufficient history")

        logger.info(
            f"Loaded {len(full_data)}/{target} symbols "
            f"(from {len(symbols)} candidates)"
        )

        return full_data, recent_data

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
        Load OHLCV data for multiple symbols with history validation

        Filters out symbols with insufficient history and can fetch additional
        symbols to reach a target count.

        Args:
            symbols: List of trading pairs (ordered by priority, e.g., volume)
            timeframe: Candle timeframe
            days: Number of days to load (minimum required history)
            end_date: End date (default: now)
            target_count: Target number of symbols to return (fetches more if needed)
            min_coverage_pct: Minimum data coverage required (0.90 = 90% of days)

        Returns:
            Dict mapping symbol → DataFrame (only symbols with sufficient history)
        """
        target = target_count or len(symbols)
        logger.info(
            f"Loading multi-symbol data: {len(symbols)} candidates, "
            f"target={target}, {timeframe}, {days} days"
        )

        data = {}
        skipped = []

        for symbol in symbols:
            if len(data) >= target:
                break

            try:
                df = self.load_single_symbol(symbol, timeframe, days, end_date)

                # Validate history coverage
                if df.empty:
                    skipped.append((symbol, "empty"))
                    continue

                actual_days = self._calculate_data_days(df, timeframe)
                coverage = actual_days / days if days > 0 else 0

                if coverage < min_coverage_pct:
                    skipped.append((symbol, f"{actual_days}d < {days}d ({coverage:.0%})"))
                    logger.debug(
                        f"Skipping {symbol}: insufficient history "
                        f"({actual_days} days, need {days})"
                    )
                    continue

                data[symbol] = df

            except Exception as e:
                skipped.append((symbol, str(e)))
                logger.error(f"Failed to load {symbol}: {e}")
                continue

        if skipped:
            logger.info(f"Skipped {len(skipped)} symbols with insufficient history")

        logger.info(
            f"Loaded {len(data)}/{target} symbols "
            f"(from {len(symbols)} candidates)"
        )

        return data

    def _calculate_data_days(self, df: pd.DataFrame, timeframe: str) -> int:
        """
        Calculate actual number of days covered by data

        Args:
            df: DataFrame with timestamp column
            timeframe: Timeframe string (e.g., '15m', '1h', '1d')

        Returns:
            Number of days covered
        """
        if df.empty:
            return 0

        if 'timestamp' in df.columns:
            first_ts = df['timestamp'].min()
            last_ts = df['timestamp'].max()
        else:
            first_ts = df.index.min()
            last_ts = df.index.max()

        # Handle timezone
        if hasattr(first_ts, 'tzinfo') and first_ts.tzinfo is not None:
            delta = last_ts - first_ts
        else:
            delta = last_ts - first_ts

        return delta.days

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
            data: Dict mapping symbol → DataFrame

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
        logger.info(f"Common timestamp range: {len(timestamps)} candles")

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

        logger.info(f"Prepared VectorBT data: {len(result)} rows × {len(result.columns)} columns")

        return result

    def walk_forward_split(
        self,
        df: pd.DataFrame,
        n_windows: int = 4,
        train_pct: float = 0.75
    ) -> List[tuple]:
        """
        Create walk-forward validation windows

        Example with 4 windows (75/25 split):

        Window 1: Train [0:75%]  → Test [75%:100%]
        Window 2: Train [0:80%]  → Test [80%:100%]
        Window 3: Train [0:85%]  → Test [85%:100%]
        Window 4: Train [0:90%]  → Test [90%:100%]

        Args:
            df: Input DataFrame
            n_windows: Number of expanding windows
            train_pct: Initial train/test split (0.75 = 75% train)

        Returns:
            List of (train_df, test_df) tuples
        """
        total_len = len(df)
        windows = []

        for i in range(n_windows):
            # Expanding train set
            train_end_pct = train_pct + (i * (1 - train_pct) / n_windows)
            train_end = int(total_len * train_end_pct)

            # Test set follows train
            test_end_pct = train_end_pct + ((1 - train_pct) / n_windows)
            test_end = int(total_len * test_end_pct)

            train_df = df.iloc[:train_end]
            test_df = df.iloc[train_end:test_end]

            logger.debug(
                f"Window {i+1}: Train {len(train_df)} candles → Test {len(test_df)} candles"
            )

            windows.append((train_df, test_df))

        return windows

    def get_available_symbols(self) -> List[str]:
        """
        Get list of symbols available in cache

        Returns:
            List of symbol names
        """
        if not self.cache_dir.exists():
            return []

        symbols = set()
        for file in self.cache_dir.glob('*.parquet'):
            # Parse filename: BTC_15m.parquet → BTC
            symbol = file.stem.split('_')[0]
            symbols.add(symbol)

        return sorted(symbols)


class BinanceDataLoader:
    """
    Binance data loader (alias for BacktestDataLoader for compatibility)

    Loads OHLCV data from Binance for backtesting strategies.
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
            days = 180  # Default 6 months

        # Convert symbol format: BTC/USDT → BTC
        symbol_clean = symbol.split('/')[0]

        df = self.loader.load_single_symbol(
            symbol=symbol_clean,
            timeframe=timeframe,
            days=days,
            end_date=end_date
        )

        # Filter by start_date if specified
        if start_date:
            df = df[df['timestamp'] >= start_date]

        return df

    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Validate OHLCV data integrity

        Args:
            df: DataFrame to validate

        Returns:
            True if data is valid, False otherwise
        """
        # Check required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            logger.error("Missing required columns")
            return False

        # Check for NaN values
        if df[required_cols].isna().any().any():
            logger.error("Found NaN values in OHLCV data")
            return False

        # Check OHLC relationships (high >= low is the main constraint)
        # In real trading, open/close can be outside high/low in rare cases due to gaps
        # but high must always be >= low
        invalid_ohlc = (df['high'] < df['low'])

        if invalid_ohlc.any():
            logger.error(f"Invalid OHLC relationships detected: {invalid_ohlc.sum()} bars with high < low")
            return False

        return True
