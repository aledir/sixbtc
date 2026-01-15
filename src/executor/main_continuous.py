"""
Continuous Executor Process

Executes trading signals on Hyperliquid for live strategies.
Monitors candle closes and generates/executes signals.
"""

import asyncio
import os
import signal
import threading
from datetime import datetime, UTC
from typing import Dict, Optional, List
from uuid import UUID
import importlib.util
import tempfile
import sys
from pathlib import Path

from src.config import load_config
from src.database import get_session, Strategy, Subaccount, Trade
from src.executor.hyperliquid_client import HyperliquidClient
from src.executor.risk_manager import RiskManager
from src.executor.trailing_service import TrailingService
from src.executor.emergency_stop_manager import EmergencyStopManager
from src.executor.balance_sync import BalanceSyncService
from src.executor.statistics_service import StatisticsService
from src.data.hyperliquid_websocket import get_data_provider, HyperliquidDataProvider
from src.data.coin_registry import get_registry, get_active_pairs, CoinNotFoundError
from src.strategies.base import StrategyCore, Signal, StopLossType, ExitType
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()
setup_logging(
    log_file='logs/executor.log',
    log_level=_config.get_required('logging.level'),
)

logger = get_logger(__name__)


class ContinuousExecutorProcess:
    """
    Continuous trading execution process.

    Monitors market data and executes signals for live strategies.
    """

    def __init__(
        self,
        client: Optional[HyperliquidClient] = None,
        risk_manager: Optional[RiskManager] = None,
        trailing_service: Optional[TrailingService] = None
    ):
        """
        Initialize the executor process with dependency injection.

        Args:
            client: HyperliquidClient instance (created if not provided)
            risk_manager: RiskManager instance (created if not provided)
            trailing_service: TrailingService instance (created if not provided)
        """
        self.config = load_config()
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Single source of truth for dry_run: hyperliquid.dry_run
        self.dry_run = self.config.get('hyperliquid.dry_run', True)

        # Rule #4b: WebSocket First - Initialize data provider FIRST
        # Data provider will be started in run_continuous() before main loop
        # Note: Pass None to let data_provider call load_config() internally
        # (passing _raw_config would break dot notation access like 'hyperliquid.user_address')
        self.data_provider: HyperliquidDataProvider = get_data_provider()

        # Components - use injected or create new (Dependency Injection pattern)
        # Pass data_provider to client for WebSocket-first data reads
        self.client = client or HyperliquidClient(
            self.config._raw_config,
            dry_run=self.dry_run,
            data_provider=self.data_provider
        )
        self.risk_manager = risk_manager or RiskManager(self.config._raw_config)
        self.trailing_service = trailing_service or TrailingService(self.client, self.config._raw_config)

        # Statistics service for true P&L calculation (Hyperliquid as source of truth)
        # Formula: True P&L = Current Balance - Net Deposits
        # This is immune to manual deposits/withdrawals corrupting statistics
        self.statistics_service = StatisticsService(self.client, self.data_provider)

        # Pass data_provider and statistics_service to emergency manager
        self.emergency_manager = EmergencyStopManager(
            self.config._raw_config,
            self.client,
            data_provider=self.data_provider,
            statistics_service=self.statistics_service
        )

        # Load trading pairs (multi-coin support)
        self.trading_pairs = self._load_trading_pairs()

        # Strategy cache
        self._strategy_cache: Dict[str, StrategyCore] = {}
        self._data_cache: Dict[str, any] = {}
        self._indicators_cache: Dict[str, any] = {}  # Cache for pre-calculated indicators

        # Track open trade metadata for TIME_BASED exits
        # key = "symbol:subaccount_id" -> {'entry_time': datetime, 'exit_after_bars': int, 'timeframe': str}
        self._time_exit_tracking: Dict[str, Dict] = {}

        # Check interval - from config (NO hardcoding)
        self.check_interval_seconds = self.config.get_required('executor.check_interval_seconds')

        # Minimum notional for Hyperliquid orders
        self.min_notional = self.config.get_required('hyperliquid.min_notional')

        logger.info(
            f"ContinuousExecutorProcess initialized: dry_run={self.dry_run}, "
            f"pairs={len(self.trading_pairs)}"
        )

    def _load_trading_pairs(self) -> List[str]:
        """Load active trading pairs from CoinRegistry"""
        pairs = get_active_pairs()

        if not pairs:
            logger.warning("No active coins in CoinRegistry, using BTC only")
            return ['BTC']

        logger.info(f"Loaded {len(pairs)} trading pairs from CoinRegistry")
        return pairs

    async def run_continuous(self):
        """Main continuous execution loop"""
        logger.info("Starting continuous execution loop")

        # Collect symbols and timeframes from LIVE strategies for WebSocket subscriptions
        # Track these as instance attributes for incremental bootstrap
        self._bootstrapped_symbols: set = set()
        self._bootstrapped_timeframes: set = set()

        with get_session() as session:
            live_strategies = session.query(Strategy).filter(Strategy.status == 'LIVE').all()
            for strat in live_strategies:
                if strat.timeframe:
                    self._bootstrapped_timeframes.add(strat.timeframe)
                if strat.trading_coins:
                    self._bootstrapped_symbols.update(strat.trading_coins)

        # Set symbols and timeframes for WebSocket candle subscriptions
        self.data_provider.symbols = list(self._bootstrapped_symbols)
        self.data_provider.timeframes = list(self._bootstrapped_timeframes)
        logger.info(
            f"WebSocket will subscribe to {len(self._bootstrapped_symbols)} symbols x "
            f"{len(self._bootstrapped_timeframes)} timeframes from LIVE strategies"
        )

        # Rule #4b: Start WebSocket data provider FIRST
        # This provides real-time prices and user data
        logger.info("Starting WebSocket data provider (Rule #4b: WebSocket First)...")

        # Bootstrap historical candles BEFORE starting WebSocket
        # This ensures strategies have enough data immediately
        logger.info("Bootstrapping historical candles via HTTP...")
        self.data_provider.bootstrap_historical_data(limit=200)

        self._ws_task = asyncio.create_task(self.data_provider.start())

        # Wait for WebSocket to establish connection and receive initial data
        logger.info("Waiting for WebSocket to be ready...")
        max_wait = 30  # seconds
        check_interval = 0.5
        waited = 0

        while waited < max_wait:
            await asyncio.sleep(check_interval)
            waited += check_interval

            # Check if we have mid prices (allMids subscription working)
            if len(self.data_provider.mid_prices) >= 50:
                logger.info(
                    f"WebSocket ready: {len(self.data_provider.mid_prices)} mid prices "
                    f"(waited {waited:.1f}s)"
                )
                break

            if waited % 5 == 0:
                logger.info(
                    f"  Waiting for WebSocket... "
                    f"({len(self.data_provider.mid_prices)} mid prices, {waited:.1f}s elapsed)"
                )

        if len(self.data_provider.mid_prices) < 50:
            logger.warning(
                f"WebSocket has only {len(self.data_provider.mid_prices)} mid prices "
                f"after {max_wait}s - continuing with REST fallback"
            )

        # Sync subaccount balances from Hyperliquid at startup
        # This initializes allocated_capital for manually funded subaccounts
        balance_sync = BalanceSyncService(self.config._raw_config, self.client)
        logger.info("Syncing subaccount balances from Hyperliquid...")
        synced = balance_sync.sync_all_subaccounts()
        if synced:
            logger.info(f"Balance sync complete: {len(synced)} subaccounts synced")
            for sub_id, balance in synced.items():
                logger.info(f"  Subaccount {sub_id}: ${balance:.2f}")
        else:
            logger.info("Balance sync: no subaccounts with funds found")

        # Validate subaccount state to prevent false emergency stops
        self._validate_subaccount_state()

        # Start trailing service
        await self.trailing_service.start()

        # Heartbeat tracking (log every 60s using WebSocket data)
        last_heartbeat = datetime.now(UTC)
        heartbeat_interval = 60  # seconds

        # Incremental bootstrap tracking (check every 5 min for new strategies)
        last_bootstrap_check = datetime.now(UTC)
        bootstrap_check_interval = 300  # 5 minutes

        while not self.shutdown_event.is_set() and not self.force_exit:
            try:
                loop_start = datetime.now(UTC)

                # Check emergency conditions (throttled internally to every 60s)
                triggered_stops = self.emergency_manager.check_all_conditions()
                for stop in triggered_stops:
                    self.emergency_manager.trigger_stop(
                        stop['scope'], stop['scope_id'], stop['reason'],
                        stop['action'], stop['reset_trigger']
                    )

                # Check auto-resets for expired cooldowns
                self.emergency_manager.check_auto_resets()

                # Get active subaccounts with LIVE strategies
                active_subaccounts = self._get_active_subaccounts()

                if active_subaccounts:
                    # Update trailing stops with current prices
                    await self._update_trailing_prices()

                    # Check TIME_BASED exits
                    await self._check_time_based_exits(active_subaccounts)

                    # Process each subaccount
                    for subaccount in active_subaccounts:
                        await self._process_subaccount(subaccount)

                # Heartbeat log (every 60s) - ALWAYS runs (Rule #4b: WebSocket data)
                now = datetime.now(UTC)
                loop_duration = (now - loop_start).total_seconds()
                if (now - last_heartbeat).total_seconds() >= heartbeat_interval:
                    last_heartbeat = now
                    self._log_heartbeat(len(active_subaccounts), loop_duration)

                # Check for new strategies (every 5 min) - incremental bootstrap
                if (now - last_bootstrap_check).total_seconds() >= bootstrap_check_interval:
                    last_bootstrap_check = now
                    await self._check_and_bootstrap_new_streams()

            except Exception as e:
                logger.error(f"Execution cycle error: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval_seconds)

        # Stop trailing service
        await self.trailing_service.stop()

        # Stop WebSocket data provider
        logger.info("Stopping WebSocket data provider...")
        await self.data_provider.stop()
        if hasattr(self, '_ws_task') and self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        logger.info("Execution loop ended")

    def _validate_subaccount_state(self):
        """
        Validate subaccount state to prevent false emergency stops.

        Checks for inconsistencies that cause false drawdown alerts:
        - peak_balance >> allocated_capital (from Hyperliquid balance bleed-through)

        Fixes issues in-place and logs warnings.
        """
        with get_session() as session:
            subaccounts = session.query(Subaccount).all()

            for sa in subaccounts:
                issues = []

                # Check: peak_balance should not be massively higher than allocated_capital
                # This happens when peak_balance was incorrectly initialized from Hyperliquid balance
                if sa.allocated_capital and sa.peak_balance:
                    if sa.peak_balance > sa.allocated_capital * 1.5:
                        issues.append(
                            f"peak_balance (${sa.peak_balance:.2f}) >> "
                            f"allocated_capital (${sa.allocated_capital:.2f})"
                        )
                        # Auto-fix: reset peak to allocated_capital
                        logger.warning(
                            f"Subaccount {sa.id}: Fixing corrupt peak_balance "
                            f"${sa.peak_balance:.2f} -> ${sa.allocated_capital:.2f}"
                        )
                        sa.peak_balance = sa.allocated_capital

                # Check: peak_balance should be set if subaccount is ACTIVE
                if sa.status == 'ACTIVE' and sa.strategy_id:
                    if sa.peak_balance is None or sa.peak_balance <= 0:
                        if sa.allocated_capital and sa.allocated_capital > 0:
                            logger.warning(
                                f"Subaccount {sa.id}: peak_balance not set for ACTIVE subaccount, "
                                f"setting to allocated_capital ${sa.allocated_capital:.2f}"
                            )
                            sa.peak_balance = sa.allocated_capital
                        else:
                            issues.append("ACTIVE subaccount has no peak_balance or allocated_capital")

                if issues:
                    logger.warning(
                        f"Subaccount {sa.id} validation issues:\n" +
                        "\n".join(f"  - {issue}" for issue in issues)
                    )

            session.commit()

    async def _check_and_bootstrap_new_streams(self) -> None:
        """
        Check for new coins/timeframes from rotated strategies and bootstrap them.

        Called every 5 minutes to detect newly deployed strategies that have
        coins/timeframes not yet in the WebSocket cache.

        Flow:
        1. Query current LIVE strategies for coins/timeframes
        2. Compare with already-bootstrapped sets
        3. If new ones found:
           a. Bootstrap historical data via HTTP
           b. Subscribe to new WebSocket candle streams
        """
        try:
            logger.info("Checking for new streams to bootstrap...")

            # Get current coins/timeframes from LIVE strategies
            current_symbols: set = set()
            current_timeframes: set = set()

            with get_session() as session:
                live_strategies = session.query(Strategy).filter(
                    Strategy.status == 'LIVE'
                ).all()

                for strat in live_strategies:
                    if strat.timeframe:
                        current_timeframes.add(strat.timeframe)
                    if strat.trading_coins:
                        current_symbols.update(strat.trading_coins)

            # Find new coins/timeframes
            new_symbols = current_symbols - self._bootstrapped_symbols
            new_timeframes = current_timeframes - self._bootstrapped_timeframes

            logger.info(
                f"Bootstrap check: current={len(current_symbols)} symbols, "
                f"bootstrapped={len(self._bootstrapped_symbols)}, "
                f"new={len(new_symbols)} ({sorted(new_symbols)[:5]}...)"
            )

            if not new_symbols and not new_timeframes:
                logger.info("No new streams to bootstrap")
                return

            # Calculate what needs bootstrapping
            # New symbols need all existing timeframes + new timeframes
            # New timeframes need all existing symbols + new symbols
            symbols_to_bootstrap = new_symbols
            timeframes_to_bootstrap = new_timeframes

            # If we have new symbols, they need existing timeframes too
            if new_symbols:
                timeframes_to_bootstrap = current_timeframes

            # If we have new timeframes, existing symbols need them too
            if new_timeframes:
                symbols_to_bootstrap = current_symbols

            total_new = len(symbols_to_bootstrap) * len(timeframes_to_bootstrap)
            logger.info(
                f"Incremental bootstrap: {len(new_symbols)} new symbols, "
                f"{len(new_timeframes)} new timeframes ({total_new} requests)"
            )

            # Bootstrap new streams via HTTP
            self.data_provider.bootstrap_historical_data(
                symbols=list(symbols_to_bootstrap),
                timeframes=list(timeframes_to_bootstrap),
                limit=200
            )

            # Subscribe to new WebSocket candle streams
            for symbol in new_symbols:
                for tf in current_timeframes:
                    await self.data_provider.subscribe_candles(symbol, tf)

            for tf in new_timeframes:
                for symbol in current_symbols:
                    await self.data_provider.subscribe_candles(symbol, tf)

            # Update tracked sets
            self._bootstrapped_symbols.update(new_symbols)
            self._bootstrapped_timeframes.update(new_timeframes)

            # Also update data_provider lists
            self.data_provider.symbols = list(self._bootstrapped_symbols)
            self.data_provider.timeframes = list(self._bootstrapped_timeframes)

            logger.info(
                f"Incremental bootstrap complete: now tracking "
                f"{len(self._bootstrapped_symbols)} symbols x "
                f"{len(self._bootstrapped_timeframes)} timeframes"
            )

        except Exception as e:
            logger.error(f"Error in incremental bootstrap: {e}", exc_info=True)

    def _log_heartbeat(self, active_subaccounts_count: int, loop_duration: float = 0.0) -> None:
        """
        Log heartbeat with WebSocket data (Rule #4b: WebSocket First).

        Shows real-time data from Hyperliquid WebSocket:
        - Account balance and positions from webData2
        - Price feed status from allMids
        - Data freshness from last update timestamp
        """
        try:
            # Get WebSocket data (from account_state object)
            mid_prices_count = len(self.data_provider.mid_prices)
            account_state = self.data_provider.account_state

            if account_state:
                positions = account_state.positions or []
                account_value = account_state.account_value or 0.0
                # Sum unrealized P&L from all positions
                unrealized_pnl = sum(p.unrealized_pnl for p in positions)
            else:
                positions = []
                account_value = 0.0
                unrealized_pnl = 0.0

            # Check data freshness
            last_update = self.data_provider.last_webdata2_update
            if last_update:
                if last_update.tzinfo is None:
                    last_update = last_update.replace(tzinfo=UTC)
                data_age = (datetime.now(UTC) - last_update).total_seconds()
                freshness = "FRESH" if data_age < 30 else f"STALE({data_age:.0f}s)"
            else:
                freshness = "NO_DATA"

            # Format positions summary
            pos_count = len(positions)
            pos_summary = f"{pos_count} pos"
            if pos_count > 0:
                symbols = [p.coin for p in positions[:3]]
                pos_summary = f"{pos_count} pos ({','.join(symbols)}{'...' if pos_count > 3 else ''})"

            logger.info(
                f"[HEARTBEAT] {active_subaccounts_count} subs | "
                f"${account_value:.2f} ({'+' if unrealized_pnl >= 0 else ''}{unrealized_pnl:.2f} uPnL) | "
                f"{pos_summary} | {mid_prices_count} prices | WS:{freshness} | loop:{loop_duration:.1f}s"
            )

        except Exception as e:
            logger.warning(f"[HEARTBEAT] Error getting WebSocket data: {e}")

    def _get_active_subaccounts(self) -> List[Dict]:
        """Get all active subaccounts with their strategies"""
        subaccounts = []

        with get_session() as session:
            results = (
                session.query(Subaccount, Strategy)
                .join(Strategy, Subaccount.strategy_id == Strategy.id)
                .filter(
                    Subaccount.status == "ACTIVE",
                    Strategy.status == "LIVE"
                )
                .all()
            )

            for subaccount, strategy in results:
                subaccounts.append({
                    'id': subaccount.id,
                    'strategy_id': str(strategy.id),
                    'strategy_name': strategy.name,
                    'strategy_code': strategy.code,
                    'timeframe': strategy.timeframe,
                    'allocated_capital': subaccount.allocated_capital,
                    'trading_coins': strategy.trading_coins or []
                })

        return subaccounts

    async def _process_subaccount(self, subaccount: Dict):
        """
        Process a single subaccount - scan tradable coins for signals

        Tradable pairs = intersection of:
        - Strategy's trading_coins (assigned at generation)
        - Currently active coins with volume >= min_volume_24h

        This ensures we only trade pairs that:
        1. Were assigned by generator and validated in backtest
        2. Are currently liquid enough for live trading
        """
        try:
            strategy_id = subaccount['strategy_id']
            strategy_name = subaccount['strategy_name']
            timeframe = subaccount['timeframe']

            # Check if trading is allowed (emergency stop check)
            trade_status = self.emergency_manager.can_trade(
                subaccount['id'],
                UUID(strategy_id) if isinstance(strategy_id, str) else strategy_id
            )
            if not trade_status['allowed']:
                logger.warning(
                    f"Trading blocked for subaccount {subaccount['id']}: "
                    f"{trade_status['blocked_by']} - {trade_status['reasons']}"
                )
                return

            # Get or load strategy instance
            strategy = self._get_strategy(
                strategy_id,
                strategy_name,
                subaccount['strategy_code']
            )

            if strategy is None:
                logger.warning(f"Could not load strategy {strategy_name}")
                return

            # Get tradable pairs for this strategy
            # CoinRegistry handles liquidity validation (no fallback)
            trading_coins = subaccount.get('trading_coins', [])
            if not trading_coins:
                logger.warning(f"Strategy {strategy_name} has no trading_coins - skipping")
                return

            trading_pairs = get_registry().get_tradable_for_strategy(
                trading_coins=trading_coins
            )

            if not trading_pairs:
                logger.warning(
                    f"Strategy {strategy_name}: no tradable pairs "
                    f"(assigned={len(trading_coins)}, liquid=0)"
                )
                return

            if len(trading_pairs) < 5:
                logger.warning(
                    f"Strategy {strategy_name} has only {len(trading_pairs)} tradable pairs "
                    f"(assigned={len(trading_coins)})"
                )

            # Scan tradable coins for signals
            for symbol in trading_pairs:
                try:
                    await self._process_coin(
                        subaccount=subaccount,
                        strategy=strategy,
                        symbol=symbol,
                        timeframe=timeframe
                    )
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    continue

        except Exception as e:
            logger.error(
                f"Error processing subaccount {subaccount['id']}: {e}",
                exc_info=True
            )

    async def _process_coin(
        self,
        subaccount: Dict,
        strategy: StrategyCore,
        symbol: str,
        timeframe: str
    ):
        """
        Process a single coin for a strategy using two-phase approach

        TWO-PHASE APPROACH:
        1. calculate_indicators(df) - Called once per data update (cached)
        2. generate_signal(df_with_indicators) - Called to generate signal

        Handles both entry signals (long/short) and exit signals (close).
        - Entry: only if no open position and within position limits
        - Exit: only if there is an open position

        Args:
            subaccount: Subaccount info dict
            strategy: Strategy instance
            symbol: Trading pair (e.g., 'BTC', 'ETH')
            timeframe: Candle timeframe
        """
        # Get market data for this coin
        data = await self._get_market_data(symbol, timeframe)

        if data is None or len(data) < 50:
            return

        # PHASE 1: Calculate indicators (cached per strategy/symbol/timeframe)
        # Cache key includes data length to invalidate when new data arrives
        strategy_id = subaccount['strategy_id']
        cache_key = f"{strategy_id}:{symbol}:{timeframe}:{len(data)}"

        if cache_key in self._indicators_cache:
            df_with_indicators = self._indicators_cache[cache_key]
        else:
            try:
                df_with_indicators = strategy.calculate_indicators(data)
                # Keep only last 10 entries to avoid memory bloat
                if len(self._indicators_cache) > 100:
                    # Remove oldest entries
                    keys_to_remove = list(self._indicators_cache.keys())[:50]
                    for k in keys_to_remove:
                        del self._indicators_cache[k]
                self._indicators_cache[cache_key] = df_with_indicators
            except Exception as e:
                logger.warning(f"calculate_indicators() failed for {symbol}: {e}")
                df_with_indicators = data

        # Check for open position
        open_trade = self._get_open_trade(subaccount['id'], symbol)

        # PHASE 2: Generate signal from pre-calculated indicators
        signal = strategy.generate_signal(df_with_indicators, symbol)

        if signal is None:
            return

        # Log signal generation (this means conditions were met!)
        logger.info(f"[SIGNAL] {symbol}/{timeframe}: {signal.direction} signal generated")

        # CASE 1: Exit signal + open position -> close it
        if signal.direction == 'close' and open_trade:
            current_price = df_with_indicators['close'].iloc[-1]
            await self._close_position(subaccount, open_trade, signal, current_price)
            return

        # CASE 2: Entry signal + no position -> open it
        if signal.direction in ['long', 'short'] and not open_trade:
            # Check max positions limit
            if self._is_at_max_positions(subaccount['id']):
                return
            await self._execute_signal(subaccount, signal, df_with_indicators, symbol)

    def _get_open_trade(self, subaccount_id: int, symbol: str) -> Optional[Dict]:
        """
        Get open trade record for this symbol (if exists)

        Args:
            subaccount_id: Subaccount ID
            symbol: Trading pair

        Returns:
            Dict with trade info or None if no open position
        """
        with get_session() as session:
            trade = (
                session.query(Trade)
                .filter(
                    Trade.subaccount_id == subaccount_id,
                    Trade.symbol == symbol,
                    Trade.exit_time.is_(None)  # Open position = no exit time
                )
                .first()
            )
            if trade:
                return {
                    'id': str(trade.id),
                    'symbol': trade.symbol,
                    'direction': trade.direction,
                    'entry_price': trade.entry_price,
                    'entry_size': trade.entry_size,
                }
            return None

    def _has_open_position(self, subaccount_id: int, symbol: str) -> bool:
        """Check if subaccount has an open position for this symbol"""
        return self._get_open_trade(subaccount_id, symbol) is not None

    def _is_at_max_positions(self, subaccount_id: int) -> bool:
        """Check if subaccount has reached max position limit"""
        max_positions = self.risk_manager.max_positions_per_subaccount

        with get_session() as session:
            open_count = (
                session.query(Trade)
                .filter(
                    Trade.subaccount_id == subaccount_id,
                    Trade.exit_time.is_(None)  # Open position = no exit time
                )
                .count()
            )
            return open_count >= max_positions

    def _get_coin_max_leverage(self, symbol: str) -> int:
        """
        Get max leverage for a coin from CoinRegistry.

        Args:
            symbol: Coin symbol (e.g., 'BTC', 'ETH')

        Returns:
            Max leverage from registry

        Raises:
            CoinNotFoundError: If coin not found or inactive
        """
        try:
            return get_registry().get_max_leverage(symbol)
        except CoinNotFoundError:
            raise ValueError(
                f"Coin {symbol} not found in CoinRegistry - cannot determine max_leverage. "
                "Run pairs_updater to sync coins from Hyperliquid."
            )

    def _get_strategy(
        self,
        strategy_id: str,
        strategy_name: str,
        code: str
    ) -> Optional[StrategyCore]:
        """Get or load strategy instance"""
        if strategy_id in self._strategy_cache:
            return self._strategy_cache[strategy_id]

        try:
            # Extract class name (supports all prefixes)
            import re
            match = re.search(r'class\s+((?:Strategy|PatStrat|UngStrat|UggStrat|AIFStrat|AIAStrat|PGnStrat|PGgStrat|PtaStrat)_\w+)\s*\(', code)
            if not match:
                return None

            class_name = match.group(1)

            # Load strategy
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name

            spec = importlib.util.spec_from_file_location(
                f"live_{class_name}",
                temp_path
            )

            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)

                if hasattr(module, class_name):
                    cls = getattr(module, class_name)
                    instance = cls()
                    self._strategy_cache[strategy_id] = instance
                    return instance

            return None

        except Exception as e:
            logger.error(f"Failed to load strategy {strategy_name}: {e}")
            return None
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def _get_market_data(self, symbol: str, timeframe: str):
        """
        Get current market data for a symbol from WebSocket cache.

        Rule #4b: WebSocket First - use RAM cache populated by:
        1. HTTP bootstrap at startup (historical candles)
        2. WebSocket real-time updates (new candles)

        NO HTTP calls at runtime - all data from RAM.

        Args:
            symbol: Trading pair (e.g., 'BTC', 'ETH')
            timeframe: Candle timeframe

        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            # Get candles from WebSocket RAM cache (Rule #4b: WebSocket First)
            df = await self.data_provider.get_candles_as_dataframe(
                symbol, timeframe, limit=200
            )

            if df is None or df.empty:
                # Only log once per coin to avoid spam
                if not hasattr(self, '_no_data_logged'):
                    self._no_data_logged = set()
                key = f"{symbol}:{timeframe}"
                if key not in self._no_data_logged:
                    logger.warning(f"No WebSocket data for {symbol}/{timeframe}")
                    self._no_data_logged.add(key)
                return None

            return df

        except Exception as e:
            logger.warning(f"Failed to get WebSocket data for {symbol}/{timeframe}: {e}")
            return None

    async def _execute_signal(
        self,
        subaccount: Dict,
        signal: Signal,
        data,
        symbol: str
    ):
        """
        Execute a trading signal for a specific coin

        Args:
            subaccount: Subaccount info dict
            signal: Trading signal
            data: Market data DataFrame
            symbol: Trading pair (e.g., 'BTC', 'ETH')
        """
        try:
            current_price = data['close'].iloc[-1]

            # Calculate position size using risk manager
            size, stop_loss, take_profit = self.risk_manager.calculate_position_size(
                signal=signal,
                account_balance=subaccount['allocated_capital'],
                current_price=current_price,
                atr=self._calculate_atr(data)
            )

            if size <= 0:
                logger.debug(f"Position size too small for {symbol}, skipping signal")
                return

            # Adjust stops for short positions
            if signal.direction == 'short':
                stop_loss, take_profit = self.risk_manager.adjust_stops_for_side(
                    signal.direction, current_price, stop_loss, take_profit
                )

            # Calculate actual leverage: min(strategy target, coin max)
            strategy_leverage = getattr(signal, 'leverage', 1)
            coin_max_leverage = self._get_coin_max_leverage(symbol)
            actual_leverage = min(strategy_leverage, coin_max_leverage)

            # Dynamic cap: each trade uses at most 1/max_positions of equity
            max_positions = self.config.get_required('risk.limits.max_open_positions_per_subaccount')
            account_balance = subaccount['allocated_capital']
            notional = size * current_price
            margin_needed = notional / actual_leverage
            max_margin = account_balance / max_positions

            if margin_needed > max_margin:
                # Cap size to respect diversification
                max_notional = max_margin * actual_leverage
                original_size = size
                size = max_notional / current_price
                logger.debug(
                    f"Size capped: {original_size:.6f} -> {size:.6f} "
                    f"(margin {margin_needed:.2f} > max {max_margin:.2f})"
                )

            # Recalculate notional after any size adjustments
            notional = size * current_price

            # Check minimum notional (Hyperliquid requirement)
            if notional < self.min_notional:
                logger.debug(
                    f"Order too small for {symbol}: notional ${notional:.2f} < "
                    f"min ${self.min_notional:.2f}, skipping"
                )
                return

            logger.info(
                f"Executing {signal.direction} {symbol} for subaccount {subaccount['id']}: "
                f"size={size:.6f}, SL={stop_loss:.2f}, TP={take_profit:.2f}, "
                f"leverage={actual_leverage}x (target={strategy_leverage}x, max={coin_max_leverage}x)"
            )

            # Set leverage (isolated mode)
            self.client.set_leverage(subaccount['id'], symbol, actual_leverage)

            if self.dry_run:
                logger.info(
                    f"[DRY RUN] Would execute order: {signal.direction} {symbol} "
                    f"size={size:.6f} @ {actual_leverage}x"
                )
                return

            # Execute order
            order_result = await self.client.place_order(
                subaccount_id=subaccount['id'],
                symbol=symbol,
                side=signal.direction,
                size=size,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            if order_result:
                self._record_trade(
                    subaccount, signal, symbol, size, current_price, stop_loss, take_profit
                )

                # Register with trailing service if sl_type=TRAILING
                sl_type = getattr(signal, 'sl_type', StopLossType.ATR)
                if sl_type == StopLossType.TRAILING:
                    sl_oid = order_result.get('stop_loss', {}).get('order_id')
                    self.trailing_service.register_trailing_position(
                        coin=symbol,
                        subaccount_id=subaccount['id'],
                        side=signal.direction,
                        entry_price=current_price,
                        position_size=size,
                        current_sl_price=stop_loss,
                        current_sl_oid=sl_oid,
                        trailing_stop_pct=getattr(signal, 'trailing_stop_pct', 0.02),
                        trailing_activation_pct=getattr(signal, 'trailing_activation_pct', 0.01),
                    )

                # Register TIME_BASED exit tracking if exit_after_bars > 0
                # Check exit_after_bars directly (templates set this, not exit_type)
                exit_after_bars = getattr(signal, 'exit_after_bars', 0)
                if exit_after_bars and exit_after_bars > 0:
                    key = f"{symbol}:{subaccount['id']}"
                    self._time_exit_tracking[key] = {
                        'entry_time': datetime.now(UTC),
                        'exit_after_bars': exit_after_bars,
                        'timeframe': subaccount.get('timeframe', '15m'),
                    }
                    logger.info(
                        f"TIME_BASED exit registered: {symbol} will exit after {exit_after_bars} bars"
                    )

        except Exception as e:
            logger.error(f"Failed to execute signal: {e}", exc_info=True)

    def _calculate_atr(self, data, period: int = 14) -> float:
        """Calculate ATR from data"""
        try:
            import talib
            atr = talib.ATR(data['high'], data['low'], data['close'], timeperiod=period)
            return atr.iloc[-1]
        except Exception:
            # Fallback calculation
            tr = data['high'] - data['low']
            return tr.rolling(period).mean().iloc[-1]

    def _record_trade(
        self,
        subaccount: Dict,
        signal: Signal,
        symbol: str,
        size: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ):
        """
        Record trade to database

        Args:
            subaccount: Subaccount info dict
            signal: Trading signal
            symbol: Trading pair (e.g., 'BTC', 'ETH')
            size: Position size
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
        """
        with get_session() as session:
            trade = Trade(
                strategy_id=subaccount['strategy_id'],
                symbol=symbol,
                subaccount_id=subaccount['id'],
                direction='LONG' if signal.direction == 'long' else 'SHORT',
                entry_time=datetime.now(UTC),
                entry_price=entry_price,
                entry_size=size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                signal_reason=signal.reason
            )
            session.add(trade)

    async def _close_position(
        self,
        subaccount: Dict,
        open_trade: Dict,
        signal: Signal,
        current_price: float
    ):
        """
        Close an open position based on indicator signal

        Args:
            subaccount: Subaccount info dict
            open_trade: Open trade record dict
            signal: Close signal
            current_price: Current market price
        """
        symbol = open_trade['symbol']
        exit_reason = signal.reason or "signal"

        logger.info(
            f"Closing position {symbol} for subaccount {subaccount['id']}: "
            f"reason={exit_reason}"
        )

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would close position {symbol}: "
                f"entry={open_trade['entry_price']:.2f}, exit={current_price:.2f}"
            )
            return

        # Close on exchange
        success = self.client.close_position(subaccount['id'], symbol, reason=exit_reason)

        if success:
            # Update trade record with exit data
            self._record_exit(open_trade, current_price, exit_reason)

    def _record_exit(
        self,
        open_trade: Dict,
        exit_price: float,
        exit_reason: str
    ):
        """
        Record exit in database

        Args:
            open_trade: Open trade record dict
            exit_price: Exit price
            exit_reason: Reason for exit
        """
        with get_session() as session:
            trade = session.query(Trade).filter(
                Trade.id == open_trade['id']
            ).first()

            if trade:
                trade.exit_time = datetime.now(UTC)
                trade.exit_price = exit_price
                trade.exit_reason = exit_reason

                # Calculate PnL
                if trade.direction == 'LONG':
                    pnl_pct = (exit_price - trade.entry_price) / trade.entry_price
                else:
                    pnl_pct = (trade.entry_price - exit_price) / trade.entry_price

                trade.pnl_pct = pnl_pct
                trade.pnl_usd = pnl_pct * trade.entry_price * trade.entry_size

                logger.info(
                    f"Trade closed: {trade.symbol} PnL={trade.pnl_usd:.2f} USD "
                    f"({pnl_pct:.2%})"
                )

                # Update emergency stop balance tracking
                subaccount_id = open_trade.get('subaccount_id')
                if subaccount_id:
                    try:
                        # Get current balance from exchange
                        current_balance = self.client.get_account_balance(subaccount_id)
                        self.emergency_manager.update_balances(
                            subaccount_id=subaccount_id,
                            current_balance=current_balance,
                            pnl_delta=trade.pnl_usd
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update emergency balance tracking: {e}")

        # Clean up time exit tracking
        key = f"{open_trade['symbol']}:{open_trade.get('subaccount_id', 0)}"
        self._time_exit_tracking.pop(key, None)

        # Unregister from trailing service
        self.trailing_service.unregister_position(
            open_trade['symbol'],
            open_trade.get('subaccount_id', 0)
        )

    async def _update_trailing_prices(self):
        """Update trailing service with current prices for all coins with trailing stops"""
        if not self.trailing_service.enabled:
            return

        for symbol in self.trading_pairs:
            try:
                price = self.client.get_current_price(symbol)
                if price and price > 0:
                    await self.trailing_service.on_price_update(symbol, price)
            except Exception as e:
                logger.debug(f"Failed to update trailing price for {symbol}: {e}")

    async def _check_time_based_exits(self, active_subaccounts: List[Dict]):
        """
        Check and execute TIME_BASED exits for all tracked positions.

        TIME_BASED exit closes a position after N bars have elapsed since entry.
        """
        if not self._time_exit_tracking:
            return

        now = datetime.now(UTC)

        for key, tracking_info in list(self._time_exit_tracking.items()):
            try:
                symbol, subaccount_id_str = key.split(':')
                subaccount_id = int(subaccount_id_str)

                entry_time = tracking_info['entry_time']
                exit_after_bars = tracking_info['exit_after_bars']
                timeframe = tracking_info['timeframe']

                # Calculate bars elapsed since entry
                bars_elapsed = self._calculate_bars_since_entry(entry_time, timeframe, now)

                if bars_elapsed >= exit_after_bars:
                    # Find the subaccount info
                    subaccount = next(
                        (s for s in active_subaccounts if s['id'] == subaccount_id),
                        None
                    )

                    if not subaccount:
                        continue

                    # Get open trade
                    open_trade = self._get_open_trade(subaccount_id, symbol)
                    if not open_trade:
                        # Position already closed, clean up tracking
                        del self._time_exit_tracking[key]
                        continue

                    # Get current price
                    data = await self._get_market_data(symbol, timeframe)
                    if data is None or len(data) == 0:
                        continue

                    current_price = data['close'].iloc[-1]

                    # Create close signal
                    close_signal = Signal(
                        direction='close',
                        reason=f'time_exit: {bars_elapsed}/{exit_after_bars} bars'
                    )

                    logger.info(
                        f"TIME_BASED exit triggered: {symbol} after {bars_elapsed} bars "
                        f"(target: {exit_after_bars})"
                    )

                    # Close the position
                    open_trade['subaccount_id'] = subaccount_id
                    await self._close_position(subaccount, open_trade, close_signal, current_price)

            except Exception as e:
                logger.error(f"Error checking time-based exit for {key}: {e}")

    def _calculate_bars_since_entry(
        self,
        entry_time: datetime,
        timeframe: str,
        current_time: datetime
    ) -> int:
        """
        Calculate how many bars have elapsed since entry.

        Args:
            entry_time: When the position was opened
            timeframe: Candle timeframe (e.g., '15m', '1h', '4h')
            current_time: Current time

        Returns:
            Number of complete bars since entry
        """
        # Parse timeframe to minutes
        tf_minutes = self._timeframe_to_minutes(timeframe)

        # Calculate elapsed time in minutes
        elapsed_seconds = (current_time - entry_time).total_seconds()
        elapsed_minutes = elapsed_seconds / 60

        return int(elapsed_minutes / tf_minutes)

    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes"""
        tf_map = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480,
            '12h': 720, '1d': 1440,
        }
        return tf_map.get(timeframe, 15)  # Default to 15m

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Shutdown requested (signal {signum})")
        self.shutdown_event.set()
        self.force_exit = True
        os._exit(0)

    def run(self):
        """Main entry point"""
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        try:
            asyncio.run(self.run_continuous())
        except KeyboardInterrupt:
            pass
        finally:
            logger.info("Executor process terminated")
