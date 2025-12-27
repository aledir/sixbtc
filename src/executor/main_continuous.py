"""
Continuous Executor Process

Executes trading signals on Hyperliquid for live strategies.
Monitors candle closes and generates/executes signals.
"""

import asyncio
import os
import signal
import threading
from datetime import datetime
from typing import Dict, Optional, List
import importlib.util
import tempfile
import sys
from pathlib import Path

from src.config import load_config
from src.database import get_session, Strategy, Subaccount, Trade, Coin
from src.executor.hyperliquid_client import HyperliquidClient
from src.executor.risk_manager import RiskManager
from src.strategies.base import StrategyCore, Signal
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()._raw_config
setup_logging(
    log_file=_config.get('logging', {}).get('file', 'logs/sixbtc.log'),
    log_level=_config.get('logging', {}).get('level', 'INFO'),
)

logger = get_logger(__name__)


class ContinuousExecutorProcess:
    """
    Continuous trading execution process.

    Monitors market data and executes signals for live strategies.
    """

    def __init__(self):
        """Initialize the executor process"""
        self.config = load_config()._raw_config
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Process configuration (from subaccount_manager section for dry_run)
        subaccount_config = self.config.get('subaccount_manager', {})
        self.dry_run = subaccount_config.get('dry_run', True)

        # Components
        self.client = HyperliquidClient(self.config, dry_run=self.dry_run)
        self.risk_manager = RiskManager(self.config)

        # Load trading pairs (multi-coin support)
        self.trading_pairs = self._load_trading_pairs()

        # Strategy cache
        self._strategy_cache: Dict[str, StrategyCore] = {}
        self._data_cache: Dict[str, any] = {}

        # Check interval
        self.check_interval_seconds = 15  # Check every 15 seconds

        logger.info(
            f"ContinuousExecutorProcess initialized: dry_run={self.dry_run}, "
            f"pairs={len(self.trading_pairs)}"
        )

    def _load_trading_pairs(self) -> List[str]:
        """Load active trading pairs from database"""
        with get_session() as session:
            coins = session.query(Coin.symbol).filter(
                Coin.is_active == True
            ).order_by(Coin.volume_24h.desc()).all()

            if not coins:
                logger.warning("No active coins in database, using BTC only")
                return ['BTC']

            pairs = [c.symbol for c in coins]
            logger.info(f"Loaded {len(pairs)} trading pairs from database")
            return pairs

    async def run_continuous(self):
        """Main continuous execution loop"""
        logger.info("Starting continuous execution loop")

        while not self.shutdown_event.is_set() and not self.force_exit:
            try:
                # Get active subaccounts with LIVE strategies
                active_subaccounts = self._get_active_subaccounts()

                if not active_subaccounts:
                    await asyncio.sleep(self.check_interval_seconds)
                    continue

                # Process each subaccount
                for subaccount in active_subaccounts:
                    await self._process_subaccount(subaccount)

            except Exception as e:
                logger.error(f"Execution cycle error: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval_seconds)

        logger.info("Execution loop ended")

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
                    'allocated_capital': subaccount.allocated_capital
                })

        return subaccounts

    async def _process_subaccount(self, subaccount: Dict):
        """
        Process a single subaccount - scan all coins for signals

        Like Freqtrade: 1 strategy → N coins
        Each strategy scans all coins and generates signals where it finds opportunities.
        """
        try:
            strategy_id = subaccount['strategy_id']
            strategy_name = subaccount['strategy_name']
            timeframe = subaccount['timeframe']

            # Get or load strategy instance
            strategy = self._get_strategy(
                strategy_id,
                strategy_name,
                subaccount['strategy_code']
            )

            if strategy is None:
                logger.warning(f"Could not load strategy {strategy_name}")
                return

            # Scan all coins for signals
            for symbol in self.trading_pairs:
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
        Process a single coin for a strategy

        Args:
            subaccount: Subaccount info dict
            strategy: Strategy instance
            symbol: Trading pair (e.g., 'BTC', 'ETH')
            timeframe: Candle timeframe
        """
        # Check if we already have a position for this symbol on this subaccount
        if self._has_open_position(subaccount['id'], symbol):
            return

        # Check if we've hit max positions for this subaccount
        if self._is_at_max_positions(subaccount['id']):
            return

        # Get market data for this coin
        data = await self._get_market_data(symbol, timeframe)

        if data is None or len(data) < 50:
            return

        # Generate signal (pass symbol for per-coin leverage)
        signal = strategy.generate_signal(data, symbol)

        if signal and signal.direction in ['long', 'short']:
            await self._execute_signal(subaccount, signal, data, symbol)

    def _has_open_position(self, subaccount_id: int, symbol: str) -> bool:
        """Check if subaccount has an open position for this symbol"""
        with get_session() as session:
            open_trade = (
                session.query(Trade)
                .filter(
                    Trade.subaccount_id == subaccount_id,
                    Trade.symbol == symbol,
                    Trade.exit_time.is_(None)  # Open position = no exit time
                )
                .first()
            )
            return open_trade is not None

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
        Get max leverage for a coin from database.

        Args:
            symbol: Coin symbol (e.g., 'BTC', 'ETH')

        Returns:
            Max leverage from DB, defaults to 10 if not found
        """
        with get_session() as session:
            coin = session.query(Coin).filter(Coin.symbol == symbol).first()
            if coin:
                return coin.max_leverage

        # Default fallback
        logger.warning(f"Coin {symbol} not found in DB, using default max_leverage=10")
        return 10

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
            # Extract class name
            import re
            match = re.search(r'class\s+(Strategy_\w+)\s*\(', code)
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
        Get current market data for a symbol

        Args:
            symbol: Trading pair (e.g., 'BTC', 'ETH')
            timeframe: Candle timeframe

        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            # Use cache key to avoid reloading same data
            cache_key = f"{symbol}_{timeframe}"

            # Check cache (valid for 60 seconds)
            if cache_key in self._data_cache:
                cached_data, cached_time = self._data_cache[cache_key]
                if (datetime.utcnow() - cached_time).seconds < 60:
                    return cached_data

            # Load fresh data
            from src.backtester.data_loader import BacktestDataLoader
            loader = BacktestDataLoader()
            data = loader.load_single_symbol(symbol, timeframe, days=7)

            # Update cache
            self._data_cache[cache_key] = (data, datetime.utcnow())

            return data

        except Exception as e:
            logger.debug(f"Failed to get market data for {symbol}: {e}")
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

            logger.info(
                f"Executing {signal.direction} {symbol} for subaccount {subaccount['id']}: "
                f"size={size:.6f}, SL={stop_loss:.2f}, TP={take_profit:.2f}, "
                f"leverage={actual_leverage}x (target={strategy_leverage}x, max={coin_max_leverage}x)"
            )

            # Set leverage (isolated mode)
            self.client.set_leverage(symbol, actual_leverage)

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
                entry_time=datetime.utcnow(),
                entry_price=entry_price,
                entry_size=size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                signal_reason=signal.reason
            )
            session.add(trade)

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
