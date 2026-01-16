"""
Hyperliquid WebSocket Data Provider

Real-time market data via WebSocket for live trading.
Singleton pattern - ONE connection shared by ALL strategies.

Features:
- HTTP Bootstrap: Historical candles loaded before WebSocket starts
- allMids: Real-time mid prices for all coins
- Candle streaming: OHLCV updates for subscribed coins/timeframes
- Auto-reconnection with exponential backoff

Design Principles:
- KISS: Focused on OHLCV + prices (no orderbook, trades, user data)
- Thread-safe: Asyncio locks for concurrent access
- Singleton: ONE WebSocket connection for 1000+ strategies
- Fast Fail: Crashes if WebSocket fails to connect
- No Defaults: All parameters from config
"""

import asyncio
import json
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Deque, Any, Callable

import websockets
import pandas as pd
import ccxt

from src.config.loader import load_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


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


@dataclass
class MidPrice:
    """Mid price for a coin"""
    coin: str
    price: float
    timestamp: datetime


@dataclass
class UserPosition:
    """
    User position with Rizzo parity fields.

    Rizzo parity = True Net PnL accounting for all fees and funding.
    """
    coin: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    leverage: int
    margin_used: float
    unrealized_pnl: float
    liquidation_price: float
    funding_since_open: float = 0.0
    true_net_pnl: float = 0.0
    timestamp: datetime = None


@dataclass
class AccountState:
    """Complete account state from webData2"""
    account_value: float
    total_margin_used: float
    withdrawable: float
    positions: List['UserPosition']
    timestamp: datetime


@dataclass
class UserFill:
    """Trade execution record from userFills"""
    tid: str
    oid: str
    coin: str
    side: str
    price: float
    size: float
    fee: float
    closed_pnl: float  # Non-zero only for closing fills
    direction: str  # "Open Long", "Close Short", etc.
    timestamp: datetime


@dataclass
class LedgerUpdate:
    """
    Ledger update event (deposit, withdraw, transfer).

    Used by BalanceReconciliationService to track capital changes.
    """
    timestamp: datetime
    update_type: str  # 'deposit', 'withdraw', 'internalTransfer', 'subAccountTransfer'
    amount: float
    direction: str  # 'in' or 'out'
    hash: str  # Transaction hash for deduplication
    raw_data: Dict


class HyperliquidDataProvider:
    """
    Singleton WebSocket data provider for real-time OHLCV and User Data

    Features:
    - HTTP Bootstrap: Load historical candles before WebSocket
    - ONE WebSocket connection for ALL strategies
    - Thread-safe caching with asyncio locks
    - Real-time candle updates
    - Real-time mid prices via allMids
    - User data channels: webData2, userFills, orderUpdates
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

    # Bootstrap configuration
    BOOTSTRAP_RATE_LIMIT_MS = 500  # 500ms between HTTP requests

    # User data sync configuration
    WEBDATA2_SILENCE_THRESHOLD = 120  # Force HTTP sync if silent for 120s
    HTTP_SYNC_INTERVAL = 60  # Validate WebSocket vs HTTP every 60s

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
        self._bootstrapped = False

        # CCXT client for HTTP bootstrap
        self._ccxt_client = None

        # Data storage with thread-safe locks
        # Candles: {symbol: {interval: deque([Candle, ...])}}
        self.candles: Dict[str, Dict[str, Deque[Candle]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=1000))
        )
        self.current_candles: Dict[str, Dict[str, Candle]] = defaultdict(dict)

        # Mid prices: {coin: MidPrice}
        self.mid_prices: Dict[str, MidPrice] = {}

        # =====================================================================
        # USER DATA (private subscriptions for TradeSync)
        # =====================================================================
        # User address for private WebSocket channels
        self.user_address: Optional[str] = self.config.get(
            'hyperliquid.user_address', None
        )

        # Account state from webData2
        self.account_state: Optional[AccountState] = None

        # User fills for trade reconstruction
        self.user_fills: Deque[UserFill] = deque(maxlen=1000)

        # Ledger updates for balance reconciliation (deposit, withdraw, transfer)
        self.ledger_updates: Deque[LedgerUpdate] = deque(maxlen=1000)
        self._ledger_callback: Optional[Callable] = None

        # WebSocket health monitoring
        self.last_webdata2_update: Optional[datetime] = None
        self._sync_task: Optional[asyncio.Task] = None

        # Async lock for thread-safe access
        self.async_lock = asyncio.Lock()

        # Tracked symbols and timeframes
        self.symbols: List[str] = []
        self.timeframes: List[str] = []

        if self.user_address:
            masked = f"{self.user_address[:6]}...{self.user_address[-4:]}"
            logger.info(f"HyperliquidDataProvider initialized with user: {masked}")
        else:
            logger.info("HyperliquidDataProvider initialized (no user data)")

    def _get_ccxt_client(self):
        """Get or create CCXT client for HTTP bootstrap"""
        if self._ccxt_client is None:
            self._ccxt_client = ccxt.hyperliquid({
                "enableRateLimit": True,
                "timeout": 30000,
                "rateLimit": 200,
            })
        return self._ccxt_client

    def bootstrap_historical_data(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        limit: int = 500
    ) -> None:
        """
        Bootstrap historical candles via HTTP API before WebSocket starts.

        This populates the cache so strategies have data immediately.
        Must be called BEFORE start() for best results.

        Args:
            symbols: Symbols to fetch (uses self.symbols if None)
            timeframes: Timeframes to fetch (uses self.timeframes if None)
            limit: Number of candles to fetch per symbol/timeframe
        """
        symbols = symbols or self.symbols
        timeframes = timeframes or self.timeframes

        if not symbols or not timeframes:
            logger.warning("No symbols or timeframes configured for bootstrap")
            return

        total = len(symbols) * len(timeframes)
        logger.info(
            f"Bootstrapping historical data: {len(symbols)} symbols x "
            f"{len(timeframes)} timeframes ({total} requests)"
        )

        client = self._get_ccxt_client()
        fetched = 0
        failed = 0

        for symbol in symbols:
            for tf in timeframes:
                try:
                    # Rate limiting
                    time.sleep(self.BOOTSTRAP_RATE_LIMIT_MS / 1000.0)

                    # CCXT format: BTC/USDC:USDC
                    ccxt_symbol = f"{symbol}/USDC:USDC"

                    ohlcv = client.fetch_ohlcv(ccxt_symbol, tf, None, limit)

                    if not ohlcv:
                        logger.warning(f"Empty OHLCV for {symbol} {tf}")
                        continue

                    # Convert to Candle objects and store
                    for bar in ohlcv:
                        candle = Candle(
                            timestamp=datetime.fromtimestamp(bar[0] / 1000),
                            symbol=symbol,
                            interval=tf,
                            open=float(bar[1]),
                            high=float(bar[2]),
                            low=float(bar[3]),
                            close=float(bar[4]),
                            volume=float(bar[5]) if len(bar) > 5 else 0.0,
                        )
                        self.candles[symbol][tf].append(candle)

                    fetched += 1
                    logger.debug(
                        f"Bootstrapped {symbol} {tf}: {len(ohlcv)} candles"
                    )

                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to bootstrap {symbol} {tf}: {e}")

        self._bootstrapped = True
        logger.info(
            f"Bootstrap complete: {fetched}/{total} succeeded, {failed} failed"
        )

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

    async def subscribe_all_mids(self):
        """Subscribe to all mid prices (real-time prices for all coins)"""
        subscription = {
            "method": "subscribe",
            "subscription": {"type": "allMids"},
        }
        await self.ws.send(json.dumps(subscription))
        logger.info("Subscribed to allMids (all mid prices)")

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

        # Subscribe to allMids for real-time prices
        await self.subscribe_all_mids()

        total_subscriptions = len(symbols) * len(timeframes)
        logger.info(
            f"Subscribing to {total_subscriptions} candle streams "
            f"({len(symbols)} symbols x {len(timeframes)} timeframes)"
        )

        for symbol in symbols:
            for timeframe in timeframes:
                await self.subscribe_candles(symbol, timeframe)

        logger.info("All subscriptions established")

    async def subscribe_user_data(self):
        """
        Subscribe to user data channels (requires user_address in config).

        Channels:
        - webData2: Account state and positions
        - userFills: Trade executions
        - orderUpdates: Order status changes

        Note: After WebSocket subscription, we fetch HTTP snapshot because
        Hyperliquid WebSocket sends only updates, not initial state.
        """
        if not self.user_address:
            logger.warning("Cannot subscribe to user data - no user_address in config")
            return

        # webData2: Account state and positions
        await self.ws.send(json.dumps({
            "method": "subscribe",
            "subscription": {"type": "webData2", "user": self.user_address},
        }))
        logger.info("Subscribed to webData2 (account state)")

        # userFills: Trade executions
        await self.ws.send(json.dumps({
            "method": "subscribe",
            "subscription": {"type": "userFills", "user": self.user_address},
        }))
        logger.info("Subscribed to userFills")

        # orderUpdates: Order status changes
        await self.ws.send(json.dumps({
            "method": "subscribe",
            "subscription": {"type": "orderUpdates", "user": self.user_address},
        }))
        logger.info("Subscribed to orderUpdates")

        # Fetch initial snapshot via HTTP (WebSocket only sends updates)
        await self._fetch_initial_account_state_snapshot()

        # Subscribe to ledger updates for balance reconciliation
        await self.subscribe_ledger_updates()

    async def subscribe_ledger_updates(self):
        """
        Subscribe to userNonFundingLedgerUpdates for deposit/withdraw/transfer events.

        Used by BalanceReconciliationService to automatically track capital changes.
        """
        if not self.user_address:
            logger.debug("Cannot subscribe to ledger updates - no user_address in config")
            return

        await self.ws.send(json.dumps({
            "method": "subscribe",
            "subscription": {
                "type": "userNonFundingLedgerUpdates",
                "user": self.user_address
            },
        }))
        logger.info("Subscribed to userNonFundingLedgerUpdates (balance reconciliation)")

    def set_ledger_callback(self, callback: Callable[[LedgerUpdate], None]):
        """
        Set callback for ledger updates.

        Args:
            callback: Function to call when a ledger update is received.
                      Receives LedgerUpdate object.
        """
        self._ledger_callback = callback
        logger.debug("Ledger callback registered")

    async def _fetch_initial_account_state_snapshot(self):
        """
        Fetch initial account state via HTTP API.

        CRITICAL: Hyperliquid WebSocket sends ONLY updates, not initial snapshot.
        We must fetch the current state via HTTP after subscribing.
        """
        if not self.user_address:
            return

        try:
            logger.info("Fetching initial account state via HTTP API...")

            client = self._get_ccxt_client()

            # Run sync call in executor to avoid blocking
            # CCXT requires user address in params for Hyperliquid
            loop = asyncio.get_event_loop()
            balance = await loop.run_in_executor(
                None,
                lambda: client.fetch_balance(params={'user': self.user_address})
            )

            if not balance:
                logger.warning("Empty balance response from HTTP API")
                return

            # Parse positions from balance response
            positions = []
            # CCXT returns positions in balance['info'] for derivatives
            if 'info' in balance:
                info = balance['info']
                if isinstance(info, dict):
                    positions_data = info.get('assetPositions', [])
                    for pos_data in positions_data:
                        if pos_data.get('type') != 'oneWay':
                            continue
                        pos = pos_data.get('position', {})
                        if not pos:
                            continue

                        size_str = pos.get('szi', '0')
                        size = float(size_str)
                        if size == 0:
                            continue

                        side = 'long' if size > 0 else 'short'

                        position = UserPosition(
                            coin=pos.get('coin', ''),
                            side=side,
                            size=abs(size),
                            entry_price=float(pos.get('entryPx', 0)),
                            leverage=int(pos.get('leverage', {}).get('value', 1) if isinstance(pos.get('leverage'), dict) else 1),
                            margin_used=float(pos.get('marginUsed', 0)),
                            unrealized_pnl=float(pos.get('unrealizedPnl', 0)),
                            liquidation_price=float(pos.get('liquidationPx', 0)),
                            funding_since_open=float(pos.get('cumFunding', {}).get('sinceOpen', 0)),
                            timestamp=datetime.now(),
                        )
                        positions.append(position)

            # Get account value from balance
            account_value = float(balance.get('total', {}).get('USDC', 0))
            withdrawable = float(balance.get('free', {}).get('USDC', 0))

            state = AccountState(
                account_value=account_value,
                total_margin_used=sum(p.margin_used for p in positions),
                withdrawable=withdrawable,
                positions=positions,
                timestamp=datetime.now(),
            )

            async with self.async_lock:
                self.account_state = state
                self.last_webdata2_update = datetime.now()

            logger.info(
                f"Initial snapshot: ${account_value:.2f}, "
                f"{len(positions)} positions"
            )

        except Exception as e:
            logger.error(f"Failed to fetch initial account state: {e}", exc_info=True)

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

    async def _handle_all_mids(self, data: Dict):
        """Handle all mid prices update"""
        try:
            mids_data = data["data"]["mids"]
            timestamp = datetime.now()

            async with self.async_lock:
                for coin, price_str in mids_data.items():
                    self.mid_prices[coin] = MidPrice(
                        coin=coin,
                        price=float(price_str),
                        timestamp=timestamp,
                    )

            logger.debug(f"AllMids updated: {len(mids_data)} coins")

        except Exception as e:
            logger.error(f"Error handling allMids: {e}")

    async def _handle_web_data2(self, data: Dict):
        """
        Handle user account state (webData2) and positions.

        Parses clearinghouseState.assetPositions from Hyperliquid.
        """
        try:
            self.last_webdata2_update = datetime.now()

            user_data = data["data"]
            clearinghouse = user_data.get("clearinghouseState", {})
            margin_summary = clearinghouse.get("marginSummary", {})

            # Parse positions from assetPositions
            asset_positions = clearinghouse.get("assetPositions", [])
            positions = []

            for asset_pos in asset_positions:
                if asset_pos.get("type") != "oneWay":
                    continue

                pos_data = asset_pos.get("position", {})
                if not pos_data:
                    continue

                # Determine side from size
                size_str = pos_data.get("szi", "0")
                size = float(size_str)
                if size == 0:
                    continue

                side = "long" if size > 0 else "short"
                size = abs(size)

                # Parse leverage
                leverage_data = pos_data.get("leverage", {})
                leverage_value = leverage_data.get("value", 1) if isinstance(leverage_data, dict) else 1

                # Calculate margin_used if not provided
                entry_price = float(pos_data.get("entryPx", 0))
                margin_used_raw = float(pos_data.get("marginUsed", 0))

                if margin_used_raw == 0 and entry_price > 0 and leverage_value > 0:
                    notional = size * entry_price
                    margin_used = notional / leverage_value
                else:
                    margin_used = margin_used_raw

                # Rizzo parity: cumFunding.sinceOpen
                cum_funding_data = pos_data.get("cumFunding", {})
                funding_since_open = float(cum_funding_data.get("sinceOpen", 0))

                position = UserPosition(
                    coin=pos_data.get("coin", ""),
                    side=side,
                    size=size,
                    entry_price=entry_price,
                    leverage=int(leverage_value),
                    margin_used=margin_used,
                    unrealized_pnl=float(pos_data.get("unrealizedPnl", 0)),
                    liquidation_price=float(pos_data.get("liquidationPx", 0)),
                    funding_since_open=funding_since_open,
                    timestamp=datetime.now(),
                )
                positions.append(position)

            # Calculate total margin from positions (more reliable than API value)
            total_margin_used = sum(pos.margin_used for pos in positions)

            state = AccountState(
                account_value=float(margin_summary.get("accountValue", 0)),
                total_margin_used=total_margin_used,
                withdrawable=float(clearinghouse.get("withdrawable", 0)),
                positions=positions,
                timestamp=datetime.now(),
            )

            async with self.async_lock:
                self.account_state = state

            logger.debug(
                f"webData2: ${state.account_value:.2f}, "
                f"{len(positions)} positions"
            )

        except Exception as e:
            logger.error(f"Error handling webData2: {e}", exc_info=True)

    async def _handle_user_fills(self, data: Dict):
        """
        Handle user fills (trade executions).

        Stores fills for trade reconstruction by TradeSync.
        """
        try:
            fills_data = data["data"]

            # Skip subscription confirmations
            if isinstance(fills_data, str) or not isinstance(fills_data, list):
                logger.debug("userFills: skipping subscription confirmation")
                return

            for fill_data in fills_data:
                fill = UserFill(
                    tid=fill_data.get("tid", ""),
                    oid=fill_data.get("oid", ""),
                    coin=fill_data["coin"],
                    side=fill_data["side"],
                    price=float(fill_data["px"]),
                    size=float(fill_data["sz"]),
                    fee=float(fill_data.get("fee", 0)),
                    closed_pnl=float(fill_data.get("closedPnl", 0)),
                    direction=fill_data.get("dir", ""),
                    timestamp=datetime.fromtimestamp(fill_data["time"] / 1000),
                )

                async with self.async_lock:
                    self.user_fills.append(fill)

                logger.debug(
                    f"userFill: {fill.coin} {fill.direction} "
                    f"${fill.price:.2f} x {fill.size}"
                )

        except Exception as e:
            logger.error(f"Error handling user fills: {e}", exc_info=True)

    async def _handle_ledger_update(self, data: Dict):
        """
        Handle userNonFundingLedgerUpdates (deposit, withdraw, transfer events).

        These events are used by BalanceReconciliationService to track capital changes.
        Supports: deposit, withdraw, internalTransfer, subAccountTransfer
        """
        try:
            updates_data = data.get("data", {})

            # Skip subscription confirmations (empty or string data)
            if not updates_data or isinstance(updates_data, str):
                logger.debug("userNonFundingLedgerUpdates: subscription confirmed")
                return

            # Handle both single update and list of updates
            if isinstance(updates_data, dict):
                updates_list = [updates_data]
            elif isinstance(updates_data, list):
                updates_list = updates_data
            else:
                logger.warning(f"Unexpected ledger update format: {type(updates_data)}")
                return

            for update_data in updates_list:
                # Parse the update type and amount
                # Hyperliquid format: {"time": ms, "hash": "...", "delta": {...}}
                delta = update_data.get("delta", update_data)

                update_type = delta.get("type", "unknown")
                amount = float(delta.get("usdc", 0))

                # Determine direction based on type and amount sign
                # deposit/transferIn -> 'in'
                # withdraw/transferOut -> 'out'
                if update_type in ("deposit", "internalTransfer"):
                    direction = "in" if amount > 0 else "out"
                elif update_type in ("withdraw",):
                    direction = "out"
                elif update_type == "subAccountTransfer":
                    # subAccountTransfer uses 'user' field to determine direction
                    # If receiving, amount > 0; if sending, amount < 0
                    direction = "in" if amount > 0 else "out"
                else:
                    direction = "in" if amount > 0 else "out"

                # Parse timestamp
                time_ms = update_data.get("time", 0)
                timestamp = datetime.fromtimestamp(time_ms / 1000) if time_ms else datetime.now()

                # Get transaction hash for deduplication
                tx_hash = update_data.get("hash", f"no_hash_{time_ms}")

                ledger_update = LedgerUpdate(
                    timestamp=timestamp,
                    update_type=update_type,
                    amount=abs(amount),
                    direction=direction,
                    hash=tx_hash,
                    raw_data=update_data,
                )

                async with self.async_lock:
                    self.ledger_updates.append(ledger_update)

                logger.info(
                    f"Ledger update: {update_type} {direction.upper()} "
                    f"${abs(amount):.2f} (hash: {tx_hash[:16]}...)"
                )

                # Call callback if registered
                if self._ledger_callback:
                    try:
                        self._ledger_callback(ledger_update)
                    except Exception as e:
                        logger.error(f"Error in ledger callback: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error handling ledger update: {e}", exc_info=True)

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

                elif channel == "allMids":
                    await self._handle_all_mids(data)

                elif channel == "webData2":
                    await self._handle_web_data2(data)

                elif channel == "userFills":
                    await self._handle_user_fills(data)

                elif channel == "orderUpdates":
                    # Not used by TradeSync, but log for debugging
                    logger.debug(f"orderUpdates received")

                elif channel == "userNonFundingLedgerUpdates":
                    await self._handle_ledger_update(data)

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

                # Subscribe to user data channels (if user_address configured)
                if self.user_address:
                    await self.subscribe_user_data()

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
            List of Candle objects (oldest first)
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

        Prefers allMids price, falls back to latest candle close.

        Args:
            symbol: Symbol (e.g., 'BTC')
            interval: Timeframe to use for fallback (default: '15m')

        Returns:
            Current price, or None if not available
        """
        async with self.async_lock:
            # First try allMids (most accurate)
            mid = self.mid_prices.get(symbol)
            if mid:
                return mid.price

            # Fallback to latest candle close
            candle = self.current_candles.get(symbol, {}).get(interval)
            return candle.close if candle else None

    async def get_all_prices(self) -> Dict[str, float]:
        """
        Get current prices for all coins from allMids

        Returns:
            Dict mapping symbol to price
        """
        async with self.async_lock:
            return {
                coin: mid.price
                for coin, mid in self.mid_prices.items()
            }

    def get_cached_symbols(self) -> List[str]:
        """Get list of symbols with cached data"""
        return list(self.candles.keys())

    def get_cached_timeframes(self, symbol: str) -> List[str]:
        """Get list of timeframes with cached data for a symbol"""
        return list(self.candles.get(symbol, {}).keys())

    def get_data(self, symbol: str, timeframe: str, limit: int = 1000) -> Optional[pd.DataFrame]:
        """
        Sync wrapper for get_candles_as_dataframe.

        For use in sync contexts (like Orchestrator).

        Args:
            symbol: Symbol (e.g., 'BTC')
            timeframe: Timeframe (e.g., '15m')
            limit: Max candles

        Returns:
            DataFrame or None if not available
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't use asyncio.run() in running loop
                # Return sync data from cache directly
                candles = list(self.candles.get(symbol, {}).get(timeframe, []))
                if not candles:
                    return None

                df = pd.DataFrame([
                    {
                        'timestamp': c.timestamp,
                        'open': c.open,
                        'high': c.high,
                        'low': c.low,
                        'close': c.close,
                        'volume': c.volume,
                    }
                    for c in candles[-limit:]
                ])
                df.set_index('timestamp', inplace=True)
                return df
            else:
                return asyncio.run(self.get_candles_as_dataframe(symbol, timeframe, limit))
        except RuntimeError:
            # No event loop - create one
            return asyncio.run(self.get_candles_as_dataframe(symbol, timeframe, limit))

    def get_price_sync(self, symbol: str) -> Optional[float]:
        """
        Sync wrapper to get current price.

        For use in sync contexts.

        Args:
            symbol: Symbol (e.g., 'BTC')

        Returns:
            Current price or None
        """
        mid = self.mid_prices.get(symbol)
        if mid:
            return mid.price

        # Fallback to first available timeframe
        for tf_candles in self.current_candles.get(symbol, {}).values():
            if tf_candles:
                return tf_candles.close
        return None

    def get_statistics(self) -> dict:
        """Get data provider statistics"""
        return {
            'running': self.running,
            'bootstrapped': self._bootstrapped,
            'symbols': len(self.symbols),
            'timeframes': len(self.timeframes),
            'mid_prices_count': len(self.mid_prices),
            'cached_candles': sum(
                len(tf_data) for s_data in self.candles.values() for tf_data in s_data.values()
            ),
            'user_data_enabled': self.user_address is not None,
            'positions_count': len(self.account_state.positions) if self.account_state else 0,
            'fills_count': len(self.user_fills),
        }

    # =========================================================================
    # USER DATA ACCESS METHODS (for TradeSync)
    # =========================================================================

    def get_account_state_sync(self) -> Optional[AccountState]:
        """
        Get current account state (sync version).

        Returns:
            AccountState or None if not available
        """
        return self.account_state

    def get_positions_sync(self) -> List[UserPosition]:
        """
        Get current open positions (sync version).

        Returns:
            List of UserPosition objects
        """
        if self.account_state:
            return self.account_state.positions
        return []

    def get_user_fills_sync(self, limit: int = 100) -> List[UserFill]:
        """
        Get recent user fills from WebSocket cache (sync version).

        Args:
            limit: Maximum number of fills to return

        Returns:
            List of UserFill objects (most recent first)
        """
        fills = list(self.user_fills)
        fills.reverse()  # Most recent first
        return fills[:limit]

    async def fetch_fills_http(self, limit: int = 500) -> List[Dict]:
        """
        Fetch user fills via HTTP API (for trade reconstruction).

        This fetches fills directly from Hyperliquid API, bypassing WebSocket.
        Used by TradeSync when reconstructing closed trades.

        Args:
            limit: Maximum number of fills to fetch

        Returns:
            List of fill dicts from HTTP API
        """
        if not self.user_address:
            logger.warning("Cannot fetch fills - no user_address configured")
            return []

        try:
            import aiohttp

            url = "https://api.hyperliquid.xyz/info"
            payload = {
                "type": "userFills",
                "user": self.user_address,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"HTTP fetch fills failed: {response.status}")
                        return []

                    fills = await response.json()
                    logger.debug(f"Fetched {len(fills)} fills via HTTP")
                    return fills[:limit]

        except Exception as e:
            logger.error(f"Failed to fetch fills via HTTP: {e}", exc_info=True)
            return []


# =============================================================================
# FACTORY FUNCTION (for easy instantiation)
# =============================================================================


def get_data_provider(
    symbols: Optional[List[str]] = None,
    timeframes: Optional[List[str]] = None,
    config: Optional[Dict] = None,
    bootstrap: bool = False
) -> HyperliquidDataProvider:
    """
    Get or create singleton HyperliquidDataProvider instance

    Args:
        symbols: List of symbols to track (optional, can be set later)
        timeframes: List of timeframes to track (optional, can be set later)
        config: Configuration dict (loads from file if None)
        bootstrap: If True, run HTTP bootstrap after creating provider

    Returns:
        Singleton HyperliquidDataProvider instance
    """
    provider = HyperliquidDataProvider(config=config)

    # Set symbols/timeframes if provided
    if symbols:
        provider.symbols = symbols
    if timeframes:
        provider.timeframes = timeframes

    # Bootstrap if requested
    if bootstrap and symbols and timeframes:
        provider.bootstrap_historical_data(symbols, timeframes)

    return provider
