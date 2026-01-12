"""
Binance Data Downloader

Downloads historical OHLCV data from Binance for backtesting.
Uses CCXT for standardized exchange interface.

Design Principles:
- KISS: Simple incremental download with caching
- Fast Fail: Crash if exchange unavailable (no silent failures)
- No Defaults: All parameters from config
- Auto-Healing: Corrupted/incomplete caches are detected and repaired
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
import logging

import ccxt
import pandas as pd
import requests
from tqdm import tqdm

from src.config.loader import load_config

logger = logging.getLogger(__name__)

# Minimum valid parquet file size (parquet header is 8 bytes minimum)
MIN_PARQUET_SIZE = 12


@dataclass
class CacheMetadata:
    """
    Metadata for cached OHLCV files.

    Enables auto-healing by tracking whether cache is complete.
    Stored as {symbol}_{timeframe}.meta.json alongside parquet files.
    """
    is_full_history: bool  # True if cache contains all data from listing date
    first_candle_ts: int   # First candle timestamp (ms)
    last_candle_ts: int    # Last candle timestamp (ms)
    candle_count: int      # Total number of candles
    listing_date_ts: Optional[int] = None  # Symbol listing date on Binance (ms)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_json(self) -> str:
        """Serialize to JSON string"""
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'CacheMetadata':
        """Deserialize from JSON string"""
        data = json.loads(json_str)
        return cls(**data)

    @classmethod
    def from_file(cls, path: Path) -> Optional['CacheMetadata']:
        """Load metadata from file, returns None if not exists or corrupted"""
        try:
            if not path.exists():
                return None
            return cls.from_json(path.read_text())
        except Exception:
            return None


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

        # Verify directory is writable (fail fast)
        self._verify_data_dir_writable()

        # Cleanup orphan temp files from previous crashes
        self._cleanup_temp_files()

        # Cache for symbol listing dates (avoid repeated API calls)
        self._listing_date_cache: Dict[str, int] = {}

        logger.info(f"BinanceDataDownloader initialized - data_dir: {self.data_dir}")

    def _verify_data_dir_writable(self) -> None:
        """
        Verify data directory is writable. Fail fast if not.

        Raises:
            PermissionError: If directory is not writable
        """
        test_file = self.data_dir / '.write_test'
        try:
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            raise PermissionError(
                f"Data directory not writable: {self.data_dir} - {e}"
            )

    def _cleanup_temp_files(self) -> int:
        """
        Remove orphan .tmp files from previous crashes.

        Returns:
            Number of temp files removed
        """
        count = 0
        for tmp_file in self.data_dir.glob("*.tmp"):
            try:
                tmp_file.unlink()
                count += 1
                logger.warning(f"Removed orphan temp file: {tmp_file.name}")
            except Exception:
                pass
        return count

    def get_symbol_listing_date(self, symbol: str, timeframe: str = '1d') -> int:
        """
        Get the listing date for a symbol on Binance Futures.

        Queries Binance for the earliest available candle.
        Results are cached to avoid repeated API calls.

        Args:
            symbol: Symbol base (e.g., 'BTC')
            timeframe: Timeframe to check (default '1d' for efficiency)

        Returns:
            Timestamp in milliseconds of first available candle
        """
        cache_key = symbol

        # Check memory cache
        if cache_key in self._listing_date_cache:
            return self._listing_date_cache[cache_key]

        ccxt_symbol = f"{symbol}/USDT:USDT"

        try:
            # Query with very early start date - Binance returns from listing
            since = int(datetime(2017, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)

            candles = self.exchange.fetch_ohlcv(
                ccxt_symbol,
                timeframe='1d',  # Always use 1d for efficiency
                since=since,
                limit=1  # Only need first candle
            )

            if candles:
                listing_ts = candles[0][0]
                self._listing_date_cache[cache_key] = listing_ts
                logger.debug(
                    f"{symbol}: Listing date = "
                    f"{datetime.fromtimestamp(listing_ts/1000, tz=timezone.utc).date()}"
                )
                return listing_ts

            # Fallback: assume recent listing (2020)
            fallback = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
            self._listing_date_cache[cache_key] = fallback
            return fallback

        except Exception as e:
            logger.warning(f"Failed to get listing date for {symbol}: {e}")
            # Conservative fallback
            fallback = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
            self._listing_date_cache[cache_key] = fallback
            return fallback

    def _get_meta_path(self, symbol: str, timeframe: str) -> Path:
        """Get path to metadata file for a symbol/timeframe"""
        return self.data_dir / f"{symbol}_{timeframe}.meta.json"

    def _load_metadata(self, symbol: str, timeframe: str) -> Optional[CacheMetadata]:
        """Load metadata for a cached file"""
        return CacheMetadata.from_file(self._get_meta_path(symbol, timeframe))

    def _save_metadata(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        is_full_history: bool,
        listing_date_ts: Optional[int] = None
    ) -> bool:
        """
        Save metadata for a cached file.

        Args:
            symbol: Symbol base
            timeframe: Timeframe
            df: DataFrame being saved
            is_full_history: Whether this represents complete history
            listing_date_ts: Symbol listing date (ms)

        Returns:
            True if saved successfully
        """
        if df.empty:
            return False

        now = datetime.now(timezone.utc).isoformat()

        # Convert timestamps to ms
        first_ts = df['timestamp'].min()
        last_ts = df['timestamp'].max()

        if isinstance(first_ts, pd.Timestamp):
            first_ts_ms = int(first_ts.timestamp() * 1000)
            last_ts_ms = int(last_ts.timestamp() * 1000)
        else:
            first_ts_ms = int(first_ts)
            last_ts_ms = int(last_ts)

        meta = CacheMetadata(
            is_full_history=is_full_history,
            first_candle_ts=first_ts_ms,
            last_candle_ts=last_ts_ms,
            candle_count=len(df),
            listing_date_ts=listing_date_ts,
            created_at=now,
            updated_at=now
        )

        meta_path = self._get_meta_path(symbol, timeframe)

        try:
            meta_path.write_text(meta.to_json())
            return True
        except Exception as e:
            logger.warning(f"Failed to save metadata for {symbol}_{timeframe}: {e}")
            return False

    def _delete_metadata(self, symbol: str, timeframe: str) -> None:
        """Delete metadata file if exists"""
        meta_path = self._get_meta_path(symbol, timeframe)
        try:
            if meta_path.exists():
                meta_path.unlink()
        except Exception:
            pass

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
        Download OHLCV data for a symbol with TRUE auto-healing.

        Auto-healing logic:
        1. If metadata exists and is_full_history=True: only forward update
        2. If metadata exists and is_full_history=False: partial cache, only forward update
        3. If NO metadata (legacy cache): check against Binance listing date
           - If cache is incomplete -> backfill from listing date (AUTO-REPAIR)
           - If cache is complete -> create metadata, forward update only

        Args:
            symbol: Symbol base (e.g., 'BTC')
            timeframe: CCXT timeframe (e.g., '5m', '15m', '1h', '1d')
            days: Number of days to download (None = all available history)
            force_refresh: Force re-download even if cached

        Returns:
            DataFrame with columns [timestamp, open, high, low, close, volume]
        """
        now = pd.Timestamp.now(tz='UTC')
        tf_seconds = self._timeframe_to_seconds(timeframe)

        # Determine if this is a "full history" request or partial
        is_full_history_request = (days is None)

        # Load existing cache (with auto-repair of corrupted files)
        df = pd.DataFrame()
        metadata = None
        listing_date_ts: Optional[int] = None
        needs_backfill = False
        start_date: Optional[pd.Timestamp] = None

        if not force_refresh:
            cached_df = self.load_data(symbol, timeframe)
            metadata = self._load_metadata(symbol, timeframe)

            if cached_df is not None and not cached_df.empty:
                df = cached_df
                first_timestamp = df['timestamp'].min()
                last_timestamp = df['timestamp'].max()

                # Forward check: need new candles?
                needs_update = (now - last_timestamp).total_seconds() >= tf_seconds

                # Backfill check - depends on whether we have metadata
                if metadata is not None:
                    # CASE 1: Metadata exists - trust it
                    listing_date_ts = metadata.listing_date_ts

                    if is_full_history_request and metadata.is_full_history:
                        # Full history cache, just update forward
                        needs_backfill = False
                    elif is_full_history_request and not metadata.is_full_history:
                        # Was a partial download (days=N), user now wants full
                        # Need to backfill from listing date
                        listing_date_ts = listing_date_ts or self.get_symbol_listing_date(symbol)
                        listing_date = pd.Timestamp(listing_date_ts, unit='ms', tz='UTC')
                        needs_backfill = first_timestamp > listing_date + pd.Timedelta(hours=1)
                    elif not is_full_history_request:
                        # Partial request (days=N)
                        required_start = now - pd.Timedelta(days=days)
                        needs_backfill = first_timestamp > required_start + pd.Timedelta(hours=1)
                else:
                    # CASE 2: No metadata (legacy cache) - AUTO-HEALING
                    # Must check if cache is complete vs Binance listing date
                    listing_date_ts = self.get_symbol_listing_date(symbol)
                    listing_date = pd.Timestamp(listing_date_ts, unit='ms', tz='UTC')

                    if is_full_history_request:
                        # Check if cache starts near listing date
                        # Allow 1 day tolerance for listing date precision
                        cache_start_vs_listing = (first_timestamp - listing_date).total_seconds()

                        if cache_start_vs_listing > 86400:  # >1 day gap
                            # Cache is INCOMPLETE - trigger backfill
                            needs_backfill = True
                            logger.warning(
                                f"{symbol} {timeframe}: Legacy cache incomplete - "
                                f"starts {first_timestamp.date()}, listing {listing_date.date()}. "
                                f"Auto-healing: backfilling..."
                            )
                        else:
                            # Cache starts at/near listing - it's complete
                            needs_backfill = False
                            logger.info(
                                f"{symbol} {timeframe}: Legacy cache is complete, creating metadata"
                            )
                    else:
                        # Partial request with legacy cache
                        required_start = now - pd.Timedelta(days=days)
                        needs_backfill = first_timestamp > required_start + pd.Timedelta(hours=1)

                # Determine action
                if not needs_backfill and not needs_update:
                    logger.info(f"{symbol} {timeframe}: Cache complete")

                    # Save metadata if missing (for legacy caches)
                    if metadata is None:
                        self._save_metadata(
                            symbol, timeframe, df,
                            is_full_history=True,
                            listing_date_ts=listing_date_ts
                        )

                    if days is not None:
                        required_start = now - pd.Timedelta(days=days)
                        df = df[df['timestamp'] >= required_start].reset_index(drop=True)
                    return df

                if needs_backfill:
                    # Backfill from listing date (for full history) or required_start (for partial)
                    if is_full_history_request:
                        listing_date_ts = listing_date_ts or self.get_symbol_listing_date(symbol)
                        start_date = pd.Timestamp(listing_date_ts, unit='ms', tz='UTC')
                    else:
                        start_date = now - pd.Timedelta(days=days)
                    logger.info(
                        f"{symbol} {timeframe}: Backfilling from {start_date.date()}"
                    )
                else:
                    # Just forward update
                    start_date = last_timestamp + pd.Timedelta(seconds=tf_seconds)
                    logger.info(f"{symbol} {timeframe}: Updating forward")
            else:
                # No cache - download from scratch
                if is_full_history_request:
                    listing_date_ts = self.get_symbol_listing_date(symbol)
                    start_date = pd.Timestamp(listing_date_ts, unit='ms', tz='UTC')
                    logger.info(
                        f"{symbol} {timeframe}: No cache, downloading from listing "
                        f"({start_date.date()})"
                    )
                else:
                    start_date = now - pd.Timedelta(days=days)
                    logger.info(
                        f"{symbol} {timeframe}: No cache, downloading {days} days"
                    )
        else:
            # Force refresh
            if is_full_history_request:
                listing_date_ts = self.get_symbol_listing_date(symbol)
                start_date = pd.Timestamp(listing_date_ts, unit='ms', tz='UTC')
                logger.info(f"{symbol} {timeframe}: Force refresh from listing date")
            else:
                start_date = now - pd.Timedelta(days=days)
                logger.info(f"{symbol} {timeframe}: Force refresh, {days} days")

            # Clear old metadata
            self._delete_metadata(symbol, timeframe)

        # Download data
        ccxt_symbol = f"{symbol}/USDT:USDT"

        try:
            since = int(start_date.timestamp() * 1000)
            all_candles = []

            while True:
                candles = self.exchange.fetch_ohlcv(
                    ccxt_symbol,
                    timeframe=timeframe,
                    since=since,
                    limit=1000
                )

                if not candles:
                    break

                all_candles.extend(candles)
                since = candles[-1][0] + 1

                if candles[-1][0] >= now.timestamp() * 1000:
                    break

            if all_candles:
                new_df = pd.DataFrame(
                    all_candles,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms', utc=True)

                if not self.validate_ohlcv(new_df):
                    logger.error(f"{symbol} {timeframe}: Downloaded data failed validation")
                    if not df.empty:
                        return df
                    raise ValueError("Downloaded data is invalid")

                # Merge with existing
                if not df.empty:
                    df = pd.concat([df, new_df], ignore_index=True)
                else:
                    df = new_df

                df = self._sanitize_dataframe(df)

                # Save cache
                saved_path = self.save_data(symbol, timeframe, df)

                # Save metadata
                if saved_path:
                    # Determine is_full_history based on what we downloaded
                    if is_full_history_request:
                        # Check if we have data from listing date
                        first_ts = df['timestamp'].min()
                        listing_ts = listing_date_ts or self.get_symbol_listing_date(symbol)
                        listing_date = pd.Timestamp(listing_ts, unit='ms', tz='UTC')
                        is_full = (first_ts - listing_date).total_seconds() < 86400
                    else:
                        is_full = False

                    self._save_metadata(
                        symbol, timeframe, df,
                        is_full_history=is_full,
                        listing_date_ts=listing_date_ts
                    )

                    logger.info(
                        f"{symbol} {timeframe}: Saved {len(df)} candles "
                        f"(full_history={is_full})"
                    )
                else:
                    logger.warning(f"{symbol} {timeframe}: Download OK but save failed")
            else:
                logger.warning(f"{symbol} {timeframe}: No new data available")

            # Filter for return
            if days is not None and not df.empty:
                required_start = now - pd.Timedelta(days=days)
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

        # Get timeframes from config (root level 'timeframes' key)
        timeframes = list(self.config.get_required('timeframes'))

        # Add regime timeframe if regime detection is enabled
        regime_config = self.config._raw_config.get('regime', {})
        if regime_config.get('enabled', False):
            regime_tf = regime_config.get('timeframe', '1d')
            if regime_tf not in timeframes:
                timeframes.append(regime_tf)
                logger.info(f"Adding {regime_tf} timeframe for regime detection")

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

    def download_for_pairs(
        self,
        days: Optional[int] = None,
        force_refresh: bool = False
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Download OHLCV data for all active pairs from database.

        This is the main entry point for the DataScheduler.
        Reads active coins from the Coin table and downloads all timeframes.

        Args:
            days: Number of days to download (None = all available history)
            force_refresh: Force re-download even if cached

        Returns:
            Dict mapping {symbol: {timeframe: DataFrame}}
        """
        from src.data.coin_registry import get_active_pairs

        # Get active coins from CoinRegistry
        symbols = get_active_pairs()

        if not symbols:
            logger.warning("No active coins in CoinRegistry - run pairs_updater first")
            return {}

        logger.info(f"Downloading data for {len(symbols)} active coins from CoinRegistry")

        # Download all timeframes for active symbols
        return self.download_all_timeframes(
            symbols=symbols,
            days=days,
            force_refresh=force_refresh
        )

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
        Load cached data for a symbol (with auto-repair).

        Delegates to load_data() which handles:
        - Corrupted file detection and deletion
        - File size validation
        - OHLCV structure validation

        Args:
            symbol: Symbol base
            timeframe: Timeframe

        Returns:
            DataFrame if cached and valid, None otherwise
        """
        return self.load_data(symbol, timeframe)

    def clear_cache(self, symbol: Optional[str] = None):
        """
        Clear cached data and metadata

        Args:
            symbol: Symbol to clear (all if None)
        """
        if symbol:
            # Clear specific symbol - data and metadata
            for file in self.data_dir.glob(f"{symbol}_*.parquet"):
                file.unlink()
                logger.info(f"Deleted cache: {file}")
            for file in self.data_dir.glob(f"{symbol}_*.meta.json"):
                file.unlink()
                logger.info(f"Deleted metadata: {file}")
        else:
            # Clear all - data and metadata
            for file in self.data_dir.glob("*.parquet"):
                file.unlink()
            for file in self.data_dir.glob("*.meta.json"):
                file.unlink()
            logger.info("Cleared all cached data and metadata")

    def _sanitize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean DataFrame: dedupe, sort, remove NaN prices.

        Args:
            df: DataFrame to sanitize

        Returns:
            Cleaned DataFrame
        """
        if df.empty:
            return df

        # Drop duplicates by timestamp (keep latest)
        df = df.drop_duplicates(subset=['timestamp'], keep='last')

        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)

        # Drop rows with NaN in critical columns
        critical_cols = ['timestamp', 'open', 'high', 'low', 'close']
        existing_cols = [c for c in critical_cols if c in df.columns]
        if existing_cols:
            df = df.dropna(subset=existing_cols)

        return df

    def save_data(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame
    ) -> Optional[Path]:
        """
        Save OHLCV data to Parquet file with atomic write.

        Uses temp file + rename pattern to prevent partial writes.
        Never saves empty DataFrames.

        Args:
            symbol: Symbol base
            timeframe: Timeframe
            df: DataFrame to save

        Returns:
            Path to saved file, or None if save failed/skipped
        """
        # Never save empty data
        if df is None or df.empty:
            logger.debug(f"Skipping save for empty DataFrame: {symbol}_{timeframe}")
            return None

        # Validate before saving
        if not self.validate_ohlcv(df):
            logger.error(f"Invalid OHLCV data, refusing to save: {symbol}_{timeframe}")
            return None

        # Ensure data is clean
        df = self._sanitize_dataframe(df)

        file_path = self.data_dir / f"{symbol}_{timeframe}.parquet"
        tmp_path = file_path.with_suffix('.parquet.tmp')

        try:
            # Write to temp file first
            df.to_parquet(tmp_path, index=False)

            # Verify temp file was written correctly
            if tmp_path.stat().st_size < MIN_PARQUET_SIZE:
                raise IOError("Written file too small, likely corrupted")

            # Atomic rename (won't leave partial files)
            tmp_path.rename(file_path)

            logger.debug(f"Saved {len(df)} candles to {file_path.name}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to save {symbol}_{timeframe}: {e}")
            # Clean up temp file if it exists
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            return None

    def load_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Load cached OHLCV data with auto-repair of corrupted files.

        If file is corrupted or too small, it is deleted and None is returned,
        triggering a fresh download on next access.

        Args:
            symbol: Symbol base
            timeframe: Timeframe

        Returns:
            DataFrame if exists and valid, None otherwise
        """
        file_path = self.data_dir / f"{symbol}_{timeframe}.parquet"

        if not file_path.exists():
            return None

        # Check file size (catch empty/truncated files)
        try:
            file_size = file_path.stat().st_size
            if file_size < MIN_PARQUET_SIZE:
                logger.warning(
                    f"File too small ({file_size} bytes), deleting: {file_path.name}"
                )
                file_path.unlink()
                return None
        except Exception as e:
            logger.warning(f"Cannot stat file {file_path.name}: {e}")
            return None

        # Try to read parquet
        try:
            df = pd.read_parquet(file_path)

            # Validate structure
            if not self.validate_ohlcv(df):
                logger.warning(f"Invalid OHLCV structure, deleting: {file_path.name}")
                file_path.unlink()
                return None

            return df

        except Exception as e:
            # File is corrupted - delete and return None (will trigger re-download)
            logger.warning(f"Corrupted parquet file, deleting: {file_path.name} - {e}")
            try:
                file_path.unlink()
            except Exception:
                pass
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

    def detect_gaps(
        self,
        df: pd.DataFrame,
        timeframe: str
    ) -> List[tuple]:
        """
        Detect gaps (missing candles) in OHLCV data.

        Args:
            df: DataFrame with timestamp column
            timeframe: Timeframe string (e.g., '15m', '1h')

        Returns:
            List of (gap_start, gap_end, missing_candles) tuples
        """
        if df.empty or len(df) < 2:
            return []

        # Ensure sorted by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)

        tf_seconds = self._timeframe_to_seconds(timeframe)
        expected_delta = pd.Timedelta(seconds=tf_seconds)

        gaps = []
        timestamps = df['timestamp']

        for i in range(1, len(timestamps)):
            actual_delta = timestamps.iloc[i] - timestamps.iloc[i-1]

            # Allow 1 second tolerance for floating point issues
            if actual_delta > expected_delta + pd.Timedelta(seconds=1):
                gap_start = timestamps.iloc[i-1]
                gap_end = timestamps.iloc[i]
                missing_candles = int(actual_delta / expected_delta) - 1
                gaps.append((gap_start, gap_end, missing_candles))

        return gaps

    def fill_gaps(
        self,
        symbol: str,
        timeframe: str
    ) -> Dict[str, Any]:
        """
        Detect and fill gaps in cached data for a symbol.

        Args:
            symbol: Symbol to check and fill
            timeframe: Timeframe to check

        Returns:
            Dict with gaps_found, candles_added, success
        """
        result = {
            'gaps_found': 0,
            'candles_added': 0,
            'success': True
        }

        # Load existing data
        df = self.load_data(symbol, timeframe)

        if df is None or df.empty:
            logger.info(f"{symbol} {timeframe}: No cached data to check")
            return result

        # Detect gaps
        gaps = self.detect_gaps(df, timeframe)
        result['gaps_found'] = len(gaps)

        if not gaps:
            logger.debug(f"{symbol} {timeframe}: No gaps detected")
            return result

        logger.info(f"{symbol} {timeframe}: Found {len(gaps)} gaps, filling...")

        # Fill each gap
        ccxt_symbol = f"{symbol}/USDT:USDT"
        tf_seconds = self._timeframe_to_seconds(timeframe)

        try:
            for gap_start, gap_end, missing_count in gaps:
                # Download missing range
                since = int((gap_start + pd.Timedelta(seconds=tf_seconds)).timestamp() * 1000)
                until = int(gap_end.timestamp() * 1000)

                all_candles = []
                current_since = since

                while current_since < until:
                    candles = self.exchange.fetch_ohlcv(
                        ccxt_symbol,
                        timeframe=timeframe,
                        since=current_since,
                        limit=1000
                    )

                    if not candles:
                        break

                    # Filter to only include candles before gap_end
                    candles = [c for c in candles if c[0] < until]
                    all_candles.extend(candles)

                    if not candles:
                        break

                    current_since = candles[-1][0] + 1

                result['candles_added'] += len(all_candles)

                if all_candles:
                    # Merge with existing data
                    new_df = pd.DataFrame(
                        all_candles,
                        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    )
                    new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms', utc=True)

                    df = pd.concat([df, new_df], ignore_index=True)

            # Deduplicate and sort
            df = df.drop_duplicates(subset=['timestamp'], keep='last')
            df = df.sort_values('timestamp').reset_index(drop=True)

            # Save updated data
            self.save_data(symbol, timeframe, df)

            logger.info(
                f"{symbol} {timeframe}: Filled {result['candles_added']} candles "
                f"across {result['gaps_found']} gaps"
            )

        except Exception as e:
            logger.error(f"{symbol} {timeframe}: Gap fill failed - {e}")
            result['success'] = False

        return result

    def verify_data_integrity(
        self,
        symbol: str,
        timeframe: str
    ) -> Dict[str, Any]:
        """
        Verify data integrity for a symbol/timeframe.

        Args:
            symbol: Symbol to verify
            timeframe: Timeframe to verify

        Returns:
            Dict with valid, candle_count, gap_count, gaps, first_date, last_date
        """
        result = {
            'valid': True,
            'candle_count': 0,
            'gap_count': 0,
            'gaps': [],
            'first_date': None,
            'last_date': None
        }

        df = self.load_data(symbol, timeframe)

        if df is None:
            result['valid'] = False
            return result

        result['candle_count'] = len(df)

        if df.empty:
            return result

        # Date range
        result['first_date'] = df['timestamp'].min()
        result['last_date'] = df['timestamp'].max()

        # Check basic OHLCV validity
        if not self.validate_ohlcv(df):
            result['valid'] = False
            return result

        # Check for gaps
        gaps = self.detect_gaps(df, timeframe)
        result['gaps'] = gaps
        result['gap_count'] = len(gaps)

        if gaps:
            result['valid'] = False

        return result

    def verify_all_data(
        self,
        symbols: List[str],
        timeframes: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Verify data integrity for all symbol/timeframe combinations.

        Args:
            symbols: List of symbols to verify
            timeframes: List of timeframes to verify

        Returns:
            Dict mapping 'SYMBOL_TF' to verification results
        """
        results = {}

        for symbol in symbols:
            for tf in timeframes:
                key = f"{symbol}_{tf}"
                results[key] = self.verify_data_integrity(symbol, tf)

        # Summary
        valid_count = sum(1 for r in results.values() if r['valid'])
        total_count = len(results)

        logger.info(f"Verified {total_count} files: {valid_count} valid, {total_count - valid_count} with issues")

        return results

    def fill_all_gaps(
        self,
        symbols: List[str],
        timeframes: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fill gaps for all symbol/timeframe combinations.

        Args:
            symbols: List of symbols
            timeframes: List of timeframes

        Returns:
            Dict mapping 'SYMBOL_TF' to fill results
        """
        results = {}

        for symbol in symbols:
            for tf in timeframes:
                key = f"{symbol}_{tf}"
                results[key] = self.fill_gaps(symbol, tf)

        # Summary
        total_gaps = sum(r['gaps_found'] for r in results.values())
        total_added = sum(r['candles_added'] for r in results.values())

        logger.info(f"Gap fill complete: {total_gaps} gaps found, {total_added} candles added")

        return results

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


def _display_verification_results(results: Dict[str, Dict]) -> None:
    """Display verification results in a table"""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Data Integrity Report")
    table.add_column("Symbol", style="cyan")
    table.add_column("TF")
    table.add_column("Candles", justify="right")
    table.add_column("Gaps", justify="right")
    table.add_column("First Date")
    table.add_column("Last Date")
    table.add_column("Status")

    for key, result in sorted(results.items()):
        parts = key.rsplit('_', 1)
        symbol = parts[0]
        tf = parts[1] if len(parts) > 1 else '?'

        status = "[green]OK[/green]" if result['valid'] else "[red]GAPS[/red]"
        first_date = result.get('first_date')
        last_date = result.get('last_date')

        first_str = first_date.strftime('%Y-%m-%d') if first_date else '-'
        last_str = last_date.strftime('%Y-%m-%d') if last_date else '-'

        table.add_row(
            symbol, tf,
            str(result['candle_count']),
            str(result['gap_count']),
            first_str,
            last_str,
            status
        )

    console.print(table)

    # Summary
    valid = sum(1 for r in results.values() if r['valid'])
    total = len(results)
    console.print(f"\n[bold]Summary:[/bold] {valid}/{total} files valid")


def _display_gap_fill_results(results: Dict[str, Dict]) -> None:
    """Display gap fill results"""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Gap Fill Report")
    table.add_column("Symbol", style="cyan")
    table.add_column("TF")
    table.add_column("Gaps Found", justify="right")
    table.add_column("Candles Added", justify="right")
    table.add_column("Status")

    for key, result in sorted(results.items()):
        parts = key.rsplit('_', 1)
        symbol = parts[0]
        tf = parts[1] if len(parts) > 1 else '?'

        status = "[green]OK[/green]" if result['success'] else "[red]FAILED[/red]"
        table.add_row(
            symbol, tf,
            str(result['gaps_found']),
            str(result['candles_added']),
            status
        )

    console.print(table)

    # Summary
    total_gaps = sum(r['gaps_found'] for r in results.values())
    total_added = sum(r['candles_added'] for r in results.values())
    console.print(f"\n[bold]Summary:[/bold] {total_gaps} gaps found, {total_added} candles added")


def main():
    """CLI entry point for manual data download"""
    import argparse
    import sys

    from rich.console import Console

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    console = Console()

    parser = argparse.ArgumentParser(
        description='Download OHLCV data from Binance',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.data.binance_downloader                     # All active coins, all TFs
  python -m src.data.binance_downloader -s BTC -s ETH      # Specific symbols
  python -m src.data.binance_downloader -t 15m -t 1h       # Specific timeframes
  python -m src.data.binance_downloader --days 30          # Last 30 days only
  python -m src.data.binance_downloader --verify           # Check integrity
  python -m src.data.binance_downloader --fill-gaps        # Fill missing candles
        """
    )
    parser.add_argument('-s', '--symbols', nargs='+', help='Symbols to download (default: all active from DB)')
    parser.add_argument('-t', '--timeframes', nargs='+', help='Timeframes to download (default: from config)')
    parser.add_argument('-d', '--days', type=int, default=None, help='Days of history (default: all)')
    parser.add_argument('-f', '--force', action='store_true', help='Force re-download (ignore cache)')
    parser.add_argument('--verify', action='store_true', help='Verify data integrity only (no download)')
    parser.add_argument('--fill-gaps', action='store_true', help='Detect and fill gaps in existing data')

    args = parser.parse_args()

    try:
        downloader = BinanceDataDownloader()
    except Exception as e:
        console.print(f"[red]Failed to initialize downloader: {e}[/red]")
        sys.exit(1)

    # Determine symbols
    if args.symbols:
        symbol_list = args.symbols
    else:
        # Get from CoinRegistry
        try:
            from src.data.coin_registry import get_active_pairs
            symbol_list = get_active_pairs()

            if not symbol_list:
                console.print("[yellow]No active coins in CoinRegistry. Using common symbols...[/yellow]")
                symbol_list = downloader.get_common_symbols()[:50]
        except Exception as e:
            console.print(f"[yellow]Could not read from CoinRegistry ({e}), using common symbols...[/yellow]")
            symbol_list = downloader.get_common_symbols()[:50]

    if not symbol_list:
        console.print("[red]No symbols to process[/red]")
        sys.exit(1)

    # Determine timeframes
    if args.timeframes:
        tf_list = args.timeframes
    else:
        tf_list = list(downloader.config.get_required('timeframes'))
        # Add regime timeframe if enabled
        regime_config = downloader.config._raw_config.get('regime', {})
        if regime_config.get('enabled', False):
            regime_tf = regime_config.get('timeframe', '1d')
            if regime_tf not in tf_list:
                tf_list.append(regime_tf)

    console.print(f"\n[bold cyan]Binance Data Downloader[/bold cyan]")
    console.print(f"Symbols: {len(symbol_list)} ({', '.join(symbol_list[:5])}{'...' if len(symbol_list) > 5 else ''})")
    console.print(f"Timeframes: {tf_list}")
    console.print(f"Days: {args.days or 'all history'}")

    if args.verify:
        console.print(f"Mode: [yellow]verify[/yellow]\n")
        results = downloader.verify_all_data(symbol_list, tf_list)
        _display_verification_results(results)

    elif args.fill_gaps:
        console.print(f"Mode: [yellow]fill-gaps[/yellow]\n")
        results = downloader.fill_all_gaps(symbol_list, tf_list)
        _display_gap_fill_results(results)

    else:
        console.print(f"Mode: [green]download[/green]\n")
        for tf in tf_list:
            console.print(f"[bold]Downloading {tf}...[/bold]")
            downloader.download_multiple(symbol_list, tf, args.days, args.force)

        console.print(f"\n[green]Download complete![/green]")


if __name__ == "__main__":
    main()
