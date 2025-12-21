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
    """

    def __init__(self, cache_dir: str = 'data/binance'):
        self.cache_dir = Path(cache_dir)
        self.downloader = BinanceDataDownloader()

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

    def load_multi_symbol(
        self,
        symbols: List[str],
        timeframe: str,
        days: int = 180,
        end_date: Optional[datetime] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load OHLCV data for multiple symbols

        Args:
            symbols: List of trading pairs
            timeframe: Candle timeframe
            days: Number of days to load
            end_date: End date (default: now)

        Returns:
            Dict mapping symbol → DataFrame
        """
        logger.info(f"Loading multi-symbol data: {len(symbols)} symbols, {timeframe}, {days} days")

        data = {}

        for symbol in symbols:
            try:
                df = self.load_single_symbol(symbol, timeframe, days, end_date)
                data[symbol] = df
            except Exception as e:
                logger.error(f"Failed to load {symbol}: {e}")
                continue

        logger.info(f"Successfully loaded {len(data)}/{len(symbols)} symbols")

        return data

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
