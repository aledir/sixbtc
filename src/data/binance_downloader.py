"""
Binance Data Downloader

Downloads historical OHLCV data from Binance for backtesting.
Uses CCXT for standardized exchange interface.

Design Principles:
- KISS: Simple incremental download with caching
- Fast Fail: Crash if exchange unavailable (no silent failures)
- No Defaults: All parameters from config
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

import ccxt
import pandas as pd
import requests
from tqdm import tqdm

from src.config.loader import load_config

logger = logging.getLogger(__name__)


class BinanceDataDownloader:
    """
    Downloads historical OHLCV data from Binance

    Features:
    - Fetches HL-Binance symbol intersection
    - Volume filtering (min 24h volume)
    - Incremental updates (only missing candles)
    - Parquet storage (fast, compressed)
    - Multi-symbol parallel download
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize Binance downloader

        Args:
            config: Configuration dict (loads from file if None)
        """
        self.config = config or load_config()

        # Initialize CCXT Binance
        self.exchange = ccxt.binance({
            'enableRateLimit': True,  # Respect rate limits
            'options': {
                'defaultType': 'future',  # Use USDT-M futures
            }
        })

        # Data directory from config or default
        cache_dir = self.config.get('data.cache_dir', 'data/binance')
        self.data_dir = Path(cache_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Volume threshold (0 = no filter, pairs_updater already handles selection)
        self.min_volume_24h = self.config.get('data_scheduler.min_volume_usd', 0)

        logger.info(f"BinanceDataDownloader initialized - data_dir: {self.data_dir}")

    def get_hyperliquid_symbols(self) -> List[str]:
        """
        Fetch available symbols from Hyperliquid API

        Returns:
            List of symbol names (e.g., ['BTC', 'ETH', 'SOL'])
        """
        try:
            url = "https://api.hyperliquid.xyz/info"
            response = requests.post(
                url,
                json={"type": "meta"},
                timeout=10
            )
            response.raise_for_status()

            meta = response.json()
            symbols = [asset['name'] for asset in meta['universe']]

            logger.info(f"Fetched {len(symbols)} Hyperliquid symbols")
            return symbols

        except Exception as e:
            logger.error(f"Failed to fetch Hyperliquid symbols: {e}")
            raise

    def get_binance_perps(self) -> List[str]:
        """
        Get all Binance USDT perpetual futures symbols

        Returns:
            List of base symbols (e.g., ['BTC', 'ETH', 'SOL'])
        """
        try:
            markets = self.exchange.load_markets()

            # Filter USDT perpetuals
            perps = [
                m['base'] for m in markets.values()
                if m['type'] == 'swap' and m['quote'] == 'USDT' and m['active']
            ]

            logger.info(f"Fetched {len(perps)} Binance perpetual symbols")
            return perps

        except Exception as e:
            logger.error(f"Failed to fetch Binance symbols: {e}")
            raise

    def get_24h_volume(self, symbol: str) -> float:
        """
        Get 24h volume for a symbol

        Args:
            symbol: Symbol base (e.g., 'BTC')

        Returns:
            24h volume in USDT
        """
        try:
            ticker_symbol = f"{symbol}/USDT:USDT"
            ticker = self.exchange.fetch_ticker(ticker_symbol)
            volume_usdt = ticker['quoteVolume']  # Volume in USDT

            return volume_usdt

        except Exception as e:
            logger.warning(f"Failed to get volume for {symbol}: {e}")
            return 0.0

    def _get_24h_volume(self, symbol: str) -> float:
        """
        Private method for getting 24h volume (for mocking in tests)

        Args:
            symbol: Symbol base (e.g., 'BTC')

        Returns:
            24h volume in USDT
        """
        return self.get_24h_volume(symbol)

    def filter_by_volume(self, symbols: List[str]) -> List[str]:
        """
        Filter symbols by 24h volume

        Args:
            symbols: List of symbols to filter

        Returns:
            Filtered symbols with volume >= min_volume_24h
        """
        filtered = []

        for symbol in symbols:
            volume = self._get_24h_volume(symbol)

            if volume >= self.min_volume_24h:
                filtered.append(symbol)

        logger.info(
            f"Filtered {len(symbols)} symbols to {len(filtered)} "
            f"with volume >= ${self.min_volume_24h:,.0f}"
        )

        return filtered

    def get_common_symbols(self) -> List[str]:
        """
        Get intersection of Binance and Hyperliquid symbols with volume filter

        Returns:
            List of common symbols sorted by volume (descending)
        """
        logger.info("Calculating Binance-Hyperliquid intersection...")

        # Get symbol lists
        hl_symbols = set(self.get_hyperliquid_symbols())
        binance_symbols = set(self.get_binance_perps())

        # Intersection
        common = list(hl_symbols & binance_symbols)
        logger.info(f"Found {len(common)} common symbols")

        # Filter by volume
        symbols_with_volume = []

        for symbol in tqdm(common, desc="Checking volumes"):
            volume = self._get_24h_volume(symbol)

            if volume >= self.min_volume_24h:
                symbols_with_volume.append((symbol, volume))

        # Sort by volume (descending)
        symbols_with_volume.sort(key=lambda x: x[1], reverse=True)
        filtered_symbols = [s[0] for s in symbols_with_volume]

        logger.info(
            f"Filtered to {len(filtered_symbols)} symbols "
            f"with volume >= ${self.min_volume_24h:,.0f}"
        )

        return filtered_symbols

    def download_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        days: Optional[int] = None,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Download OHLCV data for a symbol

        Args:
            symbol: Symbol base (e.g., 'BTC')
            timeframe: CCXT timeframe (e.g., '5m', '15m', '1h', '1d')
            days: Number of days to download (None = all available history)
            force_refresh: Force re-download even if cached

        Returns:
            DataFrame with columns [timestamp, open, high, low, close, volume]
        """
        # File path for cached data
        file_path = self.data_dir / f"{symbol}_{timeframe}.parquet"

        # Calculate required start date
        now = pd.Timestamp.now(tz='UTC')
        if days is None:
            required_start = pd.Timestamp('2017-01-01', tz='UTC')
        else:
            required_start = now - pd.Timedelta(days=days)

        # Load existing data if available
        if file_path.exists() and not force_refresh:
            logger.debug(f"Loading cached data: {file_path}")
            df = pd.read_parquet(file_path)

            first_timestamp = df['timestamp'].min()
            last_timestamp = df['timestamp'].max()
            tf_seconds = self._timeframe_to_seconds(timeframe)

            # Check if cache covers required period (backfill check)
            needs_backfill = first_timestamp > required_start + pd.Timedelta(days=1)

            # Check if cache is up to date (forward check)
            needs_update = (now - last_timestamp).total_seconds() >= tf_seconds

            if not needs_backfill and not needs_update:
                logger.info(f"{symbol} {timeframe}: Using cached data (complete)")
                # Filter to requested period
                if days is not None:
                    df = df[df['timestamp'] >= required_start].reset_index(drop=True)
                return df

            if needs_backfill:
                # Cache doesn't cover required period - download from required_start
                logger.info(
                    f"{symbol} {timeframe}: Backfilling - cache starts at "
                    f"{first_timestamp.date()}, need {required_start.date()}"
                )
                start_date = required_start
            else:
                # Just append new candles
                logger.info(f"{symbol} {timeframe}: Updating cached data")
                start_date = last_timestamp + pd.Timedelta(seconds=tf_seconds)
        else:
            # No cache - download from scratch
            if days is None:
                logger.info(f"{symbol} {timeframe}: Downloading ALL available history")
            else:
                logger.info(f"{symbol} {timeframe}: Downloading {days} days from scratch")
            start_date = required_start
            df = pd.DataFrame()

        # Download data
        ccxt_symbol = f"{symbol}/USDT:USDT"

        try:
            # CCXT fetch_ohlcv returns [[timestamp, o, h, l, c, v], ...]
            since = int(start_date.timestamp() * 1000)  # CCXT uses milliseconds

            all_candles = []

            while True:
                candles = self.exchange.fetch_ohlcv(
                    ccxt_symbol,
                    timeframe=timeframe,
                    since=since,
                    limit=1000  # Max per request
                )

                if not candles:
                    break

                all_candles.extend(candles)

                # Update since to last candle timestamp
                since = candles[-1][0] + 1

                # Break if we've reached present
                if candles[-1][0] >= pd.Timestamp.now(tz='UTC').timestamp() * 1000:
                    break

            if all_candles:
                # Convert to DataFrame
                new_df = pd.DataFrame(
                    all_candles,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )

                # Convert timestamp to datetime
                new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms', utc=True)

                # Merge with existing data
                if not df.empty:
                    df = pd.concat([df, new_df], ignore_index=True)
                    df = df.drop_duplicates(subset=['timestamp'], keep='last')
                    df = df.sort_values('timestamp').reset_index(drop=True)
                else:
                    df = new_df

                # Save to cache
                df.to_parquet(file_path, index=False)
                logger.info(
                    f"{symbol} {timeframe}: Downloaded {len(new_df)} candles, "
                    f"total {len(df)} candles cached"
                )
            else:
                logger.warning(f"{symbol} {timeframe}: No new data available")

            # Filter to requested period before returning
            if days is not None:
                df = df[df['timestamp'] >= required_start].reset_index(drop=True)

            return df

        except Exception as e:
            logger.error(f"Failed to download {symbol} {timeframe}: {e}")

            # Return cached data if available
            if not df.empty:
                logger.warning(f"Returning stale cached data for {symbol} {timeframe}")
                return df

            raise

    def download_multiple(
        self,
        symbols: List[str],
        timeframe: str,
        days: Optional[int] = None,
        force_refresh: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        Download OHLCV for multiple symbols

        Args:
            symbols: List of symbols
            timeframe: CCXT timeframe
            days: Number of days (None = all available)
            force_refresh: Force re-download

        Returns:
            Dict mapping symbol to DataFrame
        """
        results = {}

        for symbol in tqdm(symbols, desc=f"Downloading {timeframe}"):
            try:
                df = self.download_ohlcv(symbol, timeframe, days, force_refresh)
                results[symbol] = df

            except Exception as e:
                logger.error(f"Skipping {symbol} due to error: {e}")
                continue

        logger.info(
            f"Downloaded {len(results)}/{len(symbols)} symbols "
            f"for timeframe {timeframe}"
        )

        return results

    def download_all_timeframes(
        self,
        symbols: Optional[List[str]] = None,
        days: Optional[int] = None,
        force_refresh: bool = False
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Download all timeframes for all symbols

        Args:
            symbols: List of symbols (uses common symbols if None)
            days: Number of days to download
            force_refresh: Force re-download

        Returns:
            Dict mapping {symbol: {timeframe: DataFrame}}
        """
        # Get symbols
        if symbols is None:
            symbols = self.get_common_symbols()

        # Get timeframes from config
        timeframes = self.config.get_required('trading.timeframes.available')

        # Download all combinations
        results = {}

        for timeframe in timeframes:
            logger.info(f"Downloading timeframe: {timeframe}")

            tf_data = self.download_multiple(symbols, timeframe, days, force_refresh)

            # Organize by symbol
            for symbol, df in tf_data.items():
                if symbol not in results:
                    results[symbol] = {}
                results[symbol][timeframe] = df

        logger.info(
            f"Download complete: {len(results)} symbols × "
            f"{len(timeframes)} timeframes"
        )

        return results

    @staticmethod
    def _timeframe_to_seconds(timeframe: str) -> int:
        """
        Convert CCXT timeframe to seconds

        Args:
            timeframe: CCXT timeframe (e.g., '5m', '1h', '1d')

        Returns:
            Seconds in timeframe
        """
        unit = timeframe[-1]
        value = int(timeframe[:-1])

        multipliers = {
            'm': 60,
            'h': 3600,
            'd': 86400,
            'w': 604800,
        }

        return value * multipliers[unit]

    def get_cached_symbols(self) -> List[str]:
        """
        Get list of symbols with cached data

        Returns:
            List of cached symbol names
        """
        if not self.data_dir.exists():
            return []

        # Extract unique symbols from cached files
        symbols = set()

        for file in self.data_dir.glob("*.parquet"):
            # File format: {symbol}_{timeframe}.parquet
            symbol = file.stem.split('_')[0]
            symbols.add(symbol)

        return sorted(symbols)

    def get_cached_data(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[pd.DataFrame]:
        """
        Load cached data for a symbol

        Args:
            symbol: Symbol base
            timeframe: Timeframe

        Returns:
            DataFrame if cached, None otherwise
        """
        file_path = self.data_dir / f"{symbol}_{timeframe}.parquet"

        if file_path.exists():
            return pd.read_parquet(file_path)

        return None

    def clear_cache(self, symbol: Optional[str] = None):
        """
        Clear cached data

        Args:
            symbol: Symbol to clear (all if None)
        """
        if symbol:
            # Clear specific symbol
            for file in self.data_dir.glob(f"{symbol}_*.parquet"):
                file.unlink()
                logger.info(f"Deleted cache: {file}")
        else:
            # Clear all
            for file in self.data_dir.glob("*.parquet"):
                file.unlink()
            logger.info("Cleared all cached data")

    def save_data(self, symbol: str, timeframe: str, df: pd.DataFrame) -> Path:
        """
        Save OHLCV data to Parquet file

        Args:
            symbol: Symbol base
            timeframe: Timeframe
            df: DataFrame to save

        Returns:
            Path to saved file
        """
        file_path = self.data_dir / f"{symbol}_{timeframe}.parquet"
        df.to_parquet(file_path, index=False)
        logger.debug(f"Saved {len(df)} candles to {file_path}")
        return file_path

    def load_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Load cached OHLCV data

        Args:
            symbol: Symbol base
            timeframe: Timeframe

        Returns:
            DataFrame if exists, None otherwise
        """
        file_path = self.data_dir / f"{symbol}_{timeframe}.parquet"

        if file_path.exists():
            return pd.read_parquet(file_path)

        return None

    def update_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        Update cached data with latest candles

        Args:
            symbol: Symbol base
            timeframe: Timeframe

        Returns:
            Updated DataFrame
        """
        # Load existing data
        existing_df = self.load_data(symbol, timeframe)

        if existing_df is not None and not existing_df.empty:
            # Download from last timestamp
            last_timestamp_val = existing_df['timestamp'].max()

            # Convert to pd.Timestamp if needed
            if not isinstance(last_timestamp_val, pd.Timestamp):
                # Assume it's milliseconds
                last_timestamp = pd.Timestamp(int(last_timestamp_val), unit='ms', tz='UTC')
            else:
                last_timestamp = last_timestamp_val
                # Ensure timezone aware
                if last_timestamp.tz is None:
                    last_timestamp = last_timestamp.tz_localize('UTC')

            days_since = (pd.Timestamp.now(tz='UTC') - last_timestamp).days + 1

            # Download new data
            new_df = self.download_ohlcv(symbol, timeframe, days=days_since, force_refresh=True)

            return new_df
        else:
            # No existing data - download from scratch
            return self.download_ohlcv(symbol, timeframe, days=180)

    def validate_ohlcv(self, df: pd.DataFrame) -> bool:
        """
        Validate OHLCV data structure and values

        Args:
            df: DataFrame to validate

        Returns:
            True if valid, False otherwise
        """
        # Check required columns
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

        if not all(col in df.columns for col in required_columns):
            return False

        # Check for empty data
        if df.empty:
            return True  # Empty is valid

        # Check for negative prices
        if (df[['open', 'high', 'low', 'close']] < 0).any().any():
            return False

        # Check high >= low
        if (df['high'] < df['low']).any():
            return False

        return True

    def timeframe_to_seconds(self, timeframe: str) -> int:
        """
        Convert timeframe string to seconds (public method)

        Args:
            timeframe: CCXT timeframe (e.g., '5m', '1h', '1d')

        Returns:
            Seconds in timeframe
        """
        return self._timeframe_to_seconds(timeframe)

    def calculate_candles_needed(self, timeframe: str, days: int) -> int:
        """
        Calculate number of candles for given timeframe and days

        Args:
            timeframe: CCXT timeframe
            days: Number of days

        Returns:
            Number of candles
        """
        seconds_per_candle = self.timeframe_to_seconds(timeframe)
        total_seconds = days * 86400  # 86400 seconds per day
        return total_seconds // seconds_per_candle

    def get_start_timestamp(self, days: int) -> int:
        """
        Calculate start timestamp for download

        Args:
            days: Number of days back

        Returns:
            Timestamp in milliseconds
        """
        start_date = datetime.now() - timedelta(days=days)
        return int(start_date.timestamp() * 1000)

    def cleanup_obsolete_pairs(self, pairs_file: Optional[Path] = None) -> int:
        """
        DISABLED: No longer deletes cached data.

        Keeping historical data for coins that drop out of top 50 is valuable:
        - They may return to top 50 later
        - Re-downloading is expensive (time, bandwidth, rate limits)
        - Storage is cheap

        Returns:
            Always 0 (no files deleted)
        """
        logger.debug("cleanup_obsolete_pairs() is disabled - keeping all historical data")
        return 0
