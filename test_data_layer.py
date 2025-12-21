#!/usr/bin/env python3
"""
Test Data Layer

Tests both BinanceDataDownloader and HyperliquidDataProvider
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.binance_downloader import BinanceDataDownloader
from src.data.hyperliquid_websocket import get_data_provider
from src.utils.logger import setup_logging

logger = setup_logging()


def test_binance_downloader():
    """Test Binance data downloader"""
    logger.info("=" * 80)
    logger.info("TESTING BINANCE DATA DOWNLOADER")
    logger.info("=" * 80)

    downloader = BinanceDataDownloader()

    # Test 1: Get common symbols
    logger.info("\n1. Fetching Binance-Hyperliquid common symbols...")
    try:
        common_symbols = downloader.get_common_symbols()
        logger.info(f"   Found {len(common_symbols)} common symbols")
        logger.info(f"   Top 10: {common_symbols[:10]}")
    except Exception as e:
        logger.error(f"   Failed: {e}")
        return False

    # Test 2: Download OHLCV for one symbol
    logger.info("\n2. Downloading BTC 15m data (180 days)...")
    try:
        df = downloader.download_ohlcv('BTC', '15m', days=180)
        logger.info(f"   Downloaded {len(df)} candles")
        logger.info(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        logger.info(f"   Last close: ${df['close'].iloc[-1]:,.2f}")
    except Exception as e:
        logger.error(f"   Failed: {e}")
        return False

    # Test 3: Check cached data
    logger.info("\n3. Checking cached data...")
    cached_symbols = downloader.get_cached_symbols()
    logger.info(f"   Cached symbols: {len(cached_symbols)}")

    logger.info("\nBinance downloader tests PASSED")
    return True


async def test_hyperliquid_websocket():
    """Test Hyperliquid WebSocket data provider"""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING HYPERLIQUID WEBSOCKET DATA PROVIDER")
    logger.info("=" * 80)

    # Test symbols and timeframes
    test_symbols = ['BTC', 'ETH', 'SOL']
    test_timeframes = ['15m', '1h']

    # Get singleton provider
    provider = get_data_provider(
        symbols=test_symbols,
        timeframes=test_timeframes
    )

    logger.info(f"\nTesting with {test_symbols} on {test_timeframes}")

    # Start WebSocket in background
    logger.info("\n1. Starting WebSocket connection...")
    websocket_task = asyncio.create_task(provider.start())

    # Wait for connection and initial data
    logger.info("   Waiting 10 seconds for data to accumulate...")
    await asyncio.sleep(10)

    # Test 2: Check cached data
    logger.info("\n2. Checking cached candles...")
    for symbol in test_symbols:
        for timeframe in test_timeframes:
            candles = await provider.get_candles(symbol, timeframe, limit=10)
            logger.info(
                f"   {symbol} {timeframe}: {len(candles)} candles cached"
            )

            if candles:
                latest = candles[-1]
                logger.info(
                    f"      Latest: {latest.timestamp} "
                    f"C=${latest.close:.2f} V={latest.volume:.0f}"
                )

    # Test 3: Get as DataFrame
    logger.info("\n3. Testing DataFrame conversion...")
    df = await provider.get_candles_as_dataframe('BTC', '15m', limit=100)
    logger.info(f"   BTC 15m DataFrame: {len(df)} rows")
    logger.info(f"   Columns: {list(df.columns)}")

    if not df.empty:
        logger.info(f"   Last close: ${df['close'].iloc[-1]:,.2f}")

    # Test 4: Current price
    logger.info("\n4. Testing current price...")
    for symbol in test_symbols:
        price = await provider.get_current_price(symbol, '15m')
        logger.info(f"   {symbol} current price: ${price:,.2f}")

    # Stop WebSocket
    logger.info("\n5. Stopping WebSocket...")
    await provider.stop()
    websocket_task.cancel()

    try:
        await websocket_task
    except asyncio.CancelledError:
        pass

    logger.info("\nHyperliquid WebSocket tests PASSED")
    return True


async def main():
    """Run all tests"""
    logger.info("SixBTC Data Layer Tests")
    logger.info("=" * 80)

    # Test 1: Binance Downloader
    if not test_binance_downloader():
        logger.error("Binance downloader tests FAILED")
        return 1

    # Test 2: Hyperliquid WebSocket
    try:
        if not await test_hyperliquid_websocket():
            logger.error("Hyperliquid WebSocket tests FAILED")
            return 1
    except Exception as e:
        logger.error(f"Hyperliquid WebSocket tests FAILED: {e}", exc_info=True)
        return 1

    logger.info("\n" + "=" * 80)
    logger.info("ALL DATA LAYER TESTS PASSED")
    logger.info("=" * 80)
    return 0


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
