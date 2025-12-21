"""
Multi-WebSocket Data Provider

Manages multiple WebSocket connections to Hyperliquid for >100 symbols.
Thread-safe shared cache for real-time market data.

Following CLAUDE.md:
- No hardcoded values (all from config)
- Fast fail (no silent errors)
- Type safety (full type hints)
- KISS principle (simple design)
"""

import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CandleData:
    """Real-time candle data"""
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class MarketCache:
    """Thread-safe market data cache"""
    data: Dict[str, pd.DataFrame] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)
    last_update: Dict[str, datetime] = field(default_factory=dict)


class MultiWebSocketDataProvider:
    """
    Manages multiple WebSocket connections for >100 symbols

    Hyperliquid WebSocket limit: ~100-150 symbols per connection
    Solution: Multiple WebSocket connections with shared cache

    Scalability:
    - 100 symbols → 1 WebSocket
    - 500 symbols → 5 WebSockets
    - 1000 symbols → 10 WebSockets

    Args:
        config: Configuration dictionary
        symbols: List of trading symbols
        timeframes: List of timeframes to subscribe

    Example:
        provider = MultiWebSocketDataProvider(
            config=config,
            symbols=['BTC', 'ETH', 'SOL'],
            timeframes=['15m', '1h']
        )
        provider.start()
        df = provider.get_data('BTC', '15m')
    """

    def __init__(
        self,
        config: dict,
        symbols: List[str],
        timeframes: List[str]
    ):
        self.config = config
        self.symbols = symbols
        self.timeframes = timeframes

        # Get config (fast fail if missing)
        ws_config = config['hyperliquid']['websocket']
        self.max_symbols_per_ws = ws_config['max_symbols_per_connection']
        self.auto_reconnect = ws_config['auto_reconnect']

        # Shared cache
        self.cache = MarketCache()

        # WebSocket connections (placeholder - actual WS in future)
        self.websockets: List[dict] = []
        self.threads: List[threading.Thread] = []
        self.running = False

        logger.info(
            f"MultiWebSocketDataProvider initialized: "
            f"{len(symbols)} symbols, {len(timeframes)} timeframes"
        )

    def start(self) -> None:
        """Start all WebSocket connections"""
        if self.running:
            raise RuntimeError("WebSocket provider already running")

        self.running = True

        # Split symbols across connections
        symbol_chunks = self._chunk_symbols()

        logger.info(f"Starting {len(symbol_chunks)} WebSocket connections")

        for i, chunk in enumerate(symbol_chunks):
            # Create WebSocket connection (mock for now)
            ws = {
                'id': i,
                'symbols': chunk,
                'timeframes': self.timeframes,
                'connected': False
            }
            self.websockets.append(ws)

            # Start listener thread
            thread = threading.Thread(
                target=self._listen,
                args=[ws],
                daemon=True,
                name=f"WSProvider-{i}"
            )
            thread.start()
            self.threads.append(thread)

        logger.info(f"Started {len(self.websockets)} WebSocket connections")

    def stop(self) -> None:
        """Stop all WebSocket connections"""
        if not self.running:
            return

        logger.info("Stopping WebSocket provider")
        self.running = False

        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=5.0)

        self.websockets.clear()
        self.threads.clear()

        logger.info("WebSocket provider stopped")

    def get_data(
        self,
        symbol: str,
        timeframe: str,
        lookback: int = 1000
    ) -> Optional[pd.DataFrame]:
        """
        Get market data for symbol/timeframe

        Args:
            symbol: Trading symbol (e.g., 'BTC')
            timeframe: Timeframe (e.g., '15m')
            lookback: Number of bars to return

        Returns:
            DataFrame with OHLCV data or None if not available
        """
        key = f"{symbol}_{timeframe}"

        with self.cache.lock:
            if key not in self.cache.data:
                return None

            df = self.cache.data[key]

            # Return last N bars
            if len(df) > lookback:
                return df.iloc[-lookback:].copy()

            return df.copy()

    def get_last_update(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """Get timestamp of last data update"""
        key = f"{symbol}_{timeframe}"

        with self.cache.lock:
            return self.cache.last_update.get(key)

    def is_data_fresh(
        self,
        symbol: str,
        timeframe: str,
        max_age_seconds: int = 60
    ) -> bool:
        """Check if data is fresh (updated recently)"""
        last_update = self.get_last_update(symbol, timeframe)

        if last_update is None:
            return False

        age = (datetime.now() - last_update).total_seconds()
        return age <= max_age_seconds

    def _chunk_symbols(self) -> List[List[str]]:
        """Split symbols into chunks for multiple WebSocket connections"""
        chunks = []
        chunk_size = self.max_symbols_per_ws

        for i in range(0, len(self.symbols), chunk_size):
            chunk = self.symbols[i:i + chunk_size]
            chunks.append(chunk)

        return chunks

    def _listen(self, ws: dict) -> None:
        """
        WebSocket listener thread

        Updates shared cache with real-time data

        NOTE: This is a mock implementation.
        Real implementation would use Hyperliquid WebSocket API.
        """
        ws_id = ws['id']
        symbols = ws['symbols']
        timeframes = ws['timeframes']

        logger.info(
            f"WebSocket {ws_id} listening: "
            f"{len(symbols)} symbols × {len(timeframes)} TFs"
        )

        # Mock: Mark as connected
        ws['connected'] = True

        # Real implementation would:
        # 1. Connect to Hyperliquid WebSocket
        # 2. Subscribe to candle updates for symbols/timeframes
        # 3. Listen for messages in loop
        # 4. Update cache with new candle data
        # 5. Handle reconnections if auto_reconnect=True

        while self.running:
            try:
                # Mock: Simulate receiving WebSocket message
                # In real implementation:
                # msg = ws_connection.recv()
                # candle = self._parse_candle(msg)
                # self._update_cache(candle)

                threading.Event().wait(1.0)  # Sleep 1s

            except Exception as e:
                logger.error(f"WebSocket {ws_id} error: {e}")

                if self.auto_reconnect:
                    logger.info(f"WebSocket {ws_id} reconnecting...")
                    threading.Event().wait(5.0)  # Wait before reconnect
                else:
                    break

        ws['connected'] = False
        logger.info(f"WebSocket {ws_id} stopped")

    def _update_cache(self, candle: CandleData) -> None:
        """Update cache with new candle data (thread-safe)"""
        key = f"{candle.symbol}_{candle.timeframe}"

        with self.cache.lock:
            # Create new DataFrame if needed
            if key not in self.cache.data:
                self.cache.data[key] = pd.DataFrame(columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume'
                ])

            df = self.cache.data[key]

            # Append new candle
            new_row = pd.DataFrame([{
                'timestamp': candle.timestamp,
                'open': candle.open,
                'high': candle.high,
                'low': candle.low,
                'close': candle.close,
                'volume': candle.volume
            }])

            df = pd.concat([df, new_row], ignore_index=True)

            # Limit cache size (keep last N bars)
            max_bars = self.config['trading']['data']['lookback_bars']
            if len(df) > max_bars:
                df = df.iloc[-max_bars:]

            self.cache.data[key] = df
            self.cache.last_update[key] = datetime.now()

    def get_statistics(self) -> dict:
        """Get provider statistics"""
        with self.cache.lock:
            return {
                'running': self.running,
                'websockets': len(self.websockets),
                'connected': sum(1 for ws in self.websockets if ws.get('connected')),
                'symbols': len(self.symbols),
                'timeframes': len(self.timeframes),
                'cached_pairs': len(self.cache.data),
                'total_bars': sum(len(df) for df in self.cache.data.values())
            }
