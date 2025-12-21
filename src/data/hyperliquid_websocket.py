"""
Hyperliquid WebSocket Data Provider

Real-time market data via WebSocket for live trading.
Singleton pattern - ONE connection shared by ALL strategies.

Design Principles:
- KISS: Focused on OHLCV data only (no orderbook, funding, trades)
- Thread-safe: Asyncio locks for concurrent access
- Singleton: ONE WebSocket connection for 1000+ strategies
- Fast Fail: Crashes if WebSocket fails to connect
- No Defaults: All parameters from config
"""

import asyncio
import json
import logging
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Deque

import websockets
import pandas as pd

from src.config.loader import load_config

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """OHLCV Candle data"""
    timestamp: datetime
    symbol: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class HyperliquidDataProvider:
    """
    Singleton WebSocket data provider for real-time OHLCV

    Features:
    - ONE WebSocket connection for ALL strategies
    - Thread-safe caching with asyncio locks
    - Real-time candle updates
    - Automatic reconnection with exponential backoff
    - Multi-symbol, multi-timeframe support
    """

    _instance = None
    _lock = threading.Lock()

    WS_URL = "wss://api.hyperliquid.xyz/ws"

    # Reconnection configuration
    RECONNECT_DELAY_INITIAL = 1.0
    RECONNECT_DELAY_MAX = 60.0
    RECONNECT_DELAY_MULTIPLIER = 2.0

    def __new__(cls, *args, **kwargs):
        """Singleton pattern - only one instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Dict] = None, bootstrap: bool = False):
        """
        Initialize WebSocket data provider (once per application)

        Args:
            config: Configuration dict (loads from file if None)
            bootstrap: If True, skip initialization (already initialized)
        """
        # Prevent re-initialization
        if hasattr(self, '_initialized') and not bootstrap:
            return

        self._initialized = True

        # Load configuration
        self.config = config or load_config()

        # WebSocket connection
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False

        # Data storage with thread-safe locks
        # Candles: {symbol: {interval: deque([Candle, ...])}}
        self.candles: Dict[str, Dict[str, Deque[Candle]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=1000))
        )
        self.current_candles: Dict[str, Dict[str, Candle]] = defaultdict(dict)

        # Async lock for thread-safe access
        self.async_lock = asyncio.Lock()

        # Tracked symbols and timeframes
        self.symbols: List[str] = []
        self.timeframes: List[str] = []

        logger.info("HyperliquidDataProvider initialized (Singleton)")

    async def connect(self) -> bool:
        """Establish WebSocket connection"""
        try:
            logger.info(f"Connecting to Hyperliquid WebSocket: {self.WS_URL}")

            # WebSocket configuration from config
            ping_interval = self.config.get('hyperliquid.websocket.ping_interval', 20)
            ping_timeout = self.config.get('hyperliquid.websocket.ping_timeout', 10)

            self.ws = await websockets.connect(
                self.WS_URL,
                ping_interval=ping_interval,
                ping_timeout=ping_timeout,
            )

            self.running = True
            logger.info("Connected to Hyperliquid WebSocket")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            return False

    async def subscribe_candles(self, symbol: str, interval: str):
        """
        Subscribe to candle updates for a symbol

        Args:
            symbol: Symbol (e.g., 'BTC')
            interval: Timeframe (e.g., '15m', '1h', '4h')
        """
        subscription = {
            "method": "subscribe",
            "subscription": {
                "type": "candle",
                "coin": symbol,
                "interval": interval
            },
        }

        await self.ws.send(json.dumps(subscription))
        logger.debug(f"Subscribed to {symbol} {interval} candles")

    async def subscribe_all(
        self,
        symbols: List[str],
        timeframes: List[str]
    ):
        """
        Subscribe to all symbol × timeframe combinations

        Args:
            symbols: List of symbols (e.g., ['BTC', 'ETH', 'SOL'])
            timeframes: List of timeframes (e.g., ['15m', '1h', '4h'])
        """
        self.symbols = symbols
        self.timeframes = timeframes

        total_subscriptions = len(symbols) * len(timeframes)
        logger.info(
            f"Subscribing to {total_subscriptions} candle streams "
            f"({len(symbols)} symbols × {len(timeframes)} timeframes)"
        )

        for symbol in symbols:
            for timeframe in timeframes:
                await self.subscribe_candles(symbol, timeframe)

        logger.info("All subscriptions established")

    async def _handle_candle(self, data: Dict):
        """Handle candle update message"""
        try:
            candle_data = data["data"]
            symbol = candle_data["s"]  # Symbol
            interval = candle_data.get("i", "")

            candle = Candle(
                timestamp=datetime.fromtimestamp(candle_data["t"] / 1000),
                symbol=symbol,
                interval=interval,
                open=float(candle_data["o"]),
                high=float(candle_data["h"]),
                low=float(candle_data["l"]),
                close=float(candle_data["c"]),
                volume=float(candle_data.get("v", 0)),
            )

            async with self.async_lock:
                # Update current candle
                self.current_candles[symbol][interval] = candle

                # Update or append to candle history
                candle_deque = self.candles[symbol][interval]

                if candle_deque and candle_deque[-1].timestamp == candle.timestamp:
                    # Same timestamp - update in-progress candle
                    candle_deque[-1] = candle
                else:
                    # New candle - append to history
                    candle_deque.append(candle)

            logger.debug(
                f"Candle update: {symbol} {interval} "
                f"C=${candle.close:.2f} V={candle.volume:.0f}"
            )

        except Exception as e:
            logger.error(f"Error handling candle: {e}")

    async def _message_handler(self):
        """Main message processing loop"""
        try:
            async for message in self.ws:
                data = json.loads(message)

                if "channel" not in data:
                    continue

                channel = data["channel"]

                # Route to appropriate handler
                if channel == "candle":
                    await self._handle_candle(data)

                elif channel == "subscriptionResponse":
                    sub_data = data.get('data', {})
                    logger.debug(f"Subscription confirmed: {sub_data}")

                else:
                    logger.debug(f"Ignoring channel: {channel}")

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e}")
            raise

        except Exception as e:
            logger.error(f"Message handler error: {e}", exc_info=True)
            raise

    async def _cleanup_connection(self):
        """Clean up connection state before reconnection"""
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

        logger.info("Connection cleaned up")

    async def start(self):
        """
        Start WebSocket client with auto-reconnection

        Implements exponential backoff reconnection loop
        """
        reconnect_delay = self.RECONNECT_DELAY_INITIAL

        while True:
            try:
                # Attempt connection
                if not await self.connect():
                    logger.error(
                        f"Failed to connect, retrying in {reconnect_delay:.1f}s..."
                    )
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(
                        reconnect_delay * self.RECONNECT_DELAY_MULTIPLIER,
                        self.RECONNECT_DELAY_MAX
                    )
                    continue

                # Reset delay on successful connect
                reconnect_delay = self.RECONNECT_DELAY_INITIAL

                # Subscribe to all channels
                await self.subscribe_all(self.symbols, self.timeframes)

                logger.info("WebSocket started - message handler running...")

                # Run message handler (blocks until disconnect)
                await self._message_handler()

            except websockets.exceptions.ConnectionClosed:
                logger.warning(
                    f"Connection lost, reconnecting in {reconnect_delay:.1f}s..."
                )
                await self._cleanup_connection()
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(
                    reconnect_delay * self.RECONNECT_DELAY_MULTIPLIER,
                    self.RECONNECT_DELAY_MAX
                )

            except asyncio.CancelledError:
                logger.info("WebSocket shutdown requested")
                await self._cleanup_connection()
                self.running = False
                break

            except Exception as e:
                logger.error(
                    f"Unexpected error, reconnecting in {reconnect_delay:.1f}s: {e}"
                )
                await self._cleanup_connection()
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(
                    reconnect_delay * self.RECONNECT_DELAY_MULTIPLIER,
                    self.RECONNECT_DELAY_MAX
                )

    async def stop(self):
        """Stop WebSocket client"""
        self.running = False

        if self.ws:
            await self.ws.close()
            logger.info("WebSocket closed")

    # =========================================================================
    # DATA ACCESS METHODS (Thread-safe)
    # =========================================================================

    async def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: int = 1000
    ) -> List[Candle]:
        """
        Get candles for a symbol and interval

        Args:
            symbol: Symbol (e.g., 'BTC')
            interval: Timeframe (e.g., '15m', '1h')
            limit: Maximum number of candles to return

        Returns:
            List of Candle objects (most recent first)
        """
        async with self.async_lock:
            candles = list(self.candles.get(symbol, {}).get(interval, []))

            if not candles:
                logger.warning(
                    f"No cached candles for {symbol} {interval}"
                )
                return []

            return candles[-limit:]

    async def get_candles_as_dataframe(
        self,
        symbol: str,
        interval: str,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Get candles as pandas DataFrame

        Args:
            symbol: Symbol (e.g., 'BTC')
            interval: Timeframe (e.g., '15m', '1h')
            limit: Maximum number of candles

        Returns:
            DataFrame with columns [timestamp, open, high, low, close, volume]
        """
        candles = await self.get_candles(symbol, interval, limit)

        if not candles:
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'timestamp': c.timestamp,
                'open': c.open,
                'high': c.high,
                'low': c.low,
                'close': c.close,
                'volume': c.volume,
            }
            for c in candles
        ])

        df.set_index('timestamp', inplace=True)
        return df

    async def get_current_price(self, symbol: str, interval: str = '15m') -> Optional[float]:
        """
        Get current price for a symbol

        Args:
            symbol: Symbol (e.g., 'BTC')
            interval: Timeframe to use (default: '15m')

        Returns:
            Current close price, or None if not available
        """
        async with self.async_lock:
            candle = self.current_candles.get(symbol, {}).get(interval)
            return candle.close if candle else None

    def get_cached_symbols(self) -> List[str]:
        """Get list of symbols with cached data"""
        return list(self.candles.keys())

    def get_cached_timeframes(self, symbol: str) -> List[str]:
        """Get list of timeframes with cached data for a symbol"""
        return list(self.candles.get(symbol, {}).keys())


# =============================================================================
# FACTORY FUNCTION (for easy instantiation)
# =============================================================================


def get_data_provider(
    symbols: Optional[List[str]] = None,
    timeframes: Optional[List[str]] = None,
    config: Optional[Dict] = None
) -> HyperliquidDataProvider:
    """
    Get or create singleton HyperliquidDataProvider instance

    Args:
        symbols: List of symbols to track (optional, can be set later)
        timeframes: List of timeframes to track (optional, can be set later)
        config: Configuration dict (loads from file if None)

    Returns:
        Singleton HyperliquidDataProvider instance
    """
    provider = HyperliquidDataProvider(config=config)

    # Set symbols/timeframes if provided
    if symbols:
        provider.symbols = symbols
    if timeframes:
        provider.timeframes = timeframes

    return provider
