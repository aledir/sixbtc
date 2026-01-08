"""
Main Orchestrator

Coordinates live trading execution across multiple strategies and timeframes.
Uses adaptive scheduling and Hyperliquid WebSocket data provider.

Following CLAUDE.md:
- Dry-run mode for safe testing
- Fast fail (no silent errors)
- Graceful shutdown
- Emergency stop capability
"""

import signal
import importlib.util
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Type
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

from src.data.hyperliquid_websocket import HyperliquidDataProvider
from src.orchestration.adaptive_scheduler import AdaptiveScheduler
from src.executor.hyperliquid_client import HyperliquidClient
from src.executor.risk_manager import RiskManager
from src.executor.position_tracker import PositionTracker
from src.strategies.base import StrategyCore, Signal
from src.database.connection import get_session
from src.database.models import Strategy
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StrategyInstance:
    """Live strategy instance"""
    strategy: StrategyCore
    subaccount_id: int
    symbol: str
    timeframe: str
    active: bool = True


class Orchestrator:
    """
    Main orchestrator for live trading

    Coordinates:
    - Strategy execution across timeframes
    - Data provider (WebSocket)
    - Risk management
    - Position tracking
    - Emergency stops

    Args:
        config: Configuration dictionary
        dry_run: If True, simulate orders (no real trades)

    Example:
        orchestrator = Orchestrator(config, dry_run=True)
        orchestrator.start()
    """

    def __init__(self, config: dict, dry_run: bool = True):
        self.config = config
        self.dry_run = dry_run
        self.running = False
        self.shutdown_requested = False

        # Components
        self.client = HyperliquidClient(config=config, dry_run=dry_run)
        self.risk_manager = RiskManager(config)
        self.position_tracker = PositionTracker(client=self.client)
        self.scheduler = AdaptiveScheduler(config)

        # Data provider (initialized later)
        self.data_provider: Optional[HyperliquidDataProvider] = None

        # Active strategies
        self.strategies: List[StrategyInstance] = []

        # Statistics
        self.stats = {
            'start_time': None,
            'iterations': 0,
            'signals_generated': 0,
            'orders_placed': 0,
            'errors': 0
        }

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        mode_str = "DRY-RUN MODE" if dry_run else "LIVE MODE"
        logger.info(f"Orchestrator initialized ({mode_str})")

    def load_strategies(self) -> None:
        """Load active strategies from database"""
        logger.info("Loading active strategies from database")

        with get_session() as session:
            # Get deployed strategies (status = LIVE)
            db_strategies = session.query(Strategy).filter(
                Strategy.status == 'LIVE'
            ).all()

            logger.info(f"Found {len(db_strategies)} live strategies in database")

            # Load strategy instances
            self.strategies = []

            for db_strat in db_strategies:
                try:
                    # Dynamically load strategy class from stored code
                    strategy_class = self._load_strategy_class(
                        db_strat.name,
                        db_strat.code
                    )

                    if strategy_class is None:
                        logger.error(f"Failed to load class for {db_strat.name}")
                        continue

                    # Instantiate strategy
                    strategy_obj = strategy_class()

                    strategy_instance = StrategyInstance(
                        strategy=strategy_obj,
                        subaccount_id=db_strat.subaccount_id or 0,
                        symbol=db_strat.symbol or 'BTC',
                        timeframe=db_strat.timeframe or '15m',
                        active=True
                    )

                    self.strategies.append(strategy_instance)
                    logger.info(f"Loaded strategy: {db_strat.name}")

                except Exception as e:
                    logger.error(f"Failed to load strategy {db_strat.name}: {e}")
                    continue

        logger.info(f"Loaded {len(self.strategies)} strategy instances")

    def _load_strategy_class(
        self,
        name: str,
        code: str
    ) -> Optional[Type[StrategyCore]]:
        """
        Dynamically load a strategy class from code string.

        Args:
            name: Strategy name (used as module name)
            code: Python code containing the strategy class

        Returns:
            Strategy class if successful, None otherwise
        """
        if not code:
            logger.error(f"No code found for strategy {name}")
            return None

        try:
            # Write code to temp file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False
            ) as f:
                f.write(code)
                temp_path = Path(f.name)

            # Load module from file
            spec = importlib.util.spec_from_file_location(name, temp_path)

            if spec is None or spec.loader is None:
                logger.error(f"Failed to create module spec for {name}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)

            # Find the strategy class (subclass of StrategyCore)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type) and
                    issubclass(attr, StrategyCore) and
                    attr is not StrategyCore
                ):
                    logger.debug(f"Found strategy class: {attr_name}")
                    return attr

            logger.error(f"No StrategyCore subclass found in {name}")
            return None

        except Exception as e:
            logger.error(f"Error loading strategy {name}: {e}", exc_info=True)
            return None

        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()

    def initialize_data_provider(self) -> None:
        """Initialize Hyperliquid WebSocket data provider"""
        # Collect all symbols/timeframes from strategies
        symbols = set()
        timeframes = set()

        for strat in self.strategies:
            symbols.add(strat.symbol)
            timeframes.add(strat.timeframe)

        symbols = sorted(list(symbols))
        timeframes = sorted(list(timeframes))

        logger.info(
            f"Initializing data provider: {len(symbols)} symbols, "
            f"{len(timeframes)} timeframes"
        )

        # Get singleton data provider
        self.data_provider = HyperliquidDataProvider(config=self.config)
        self.data_provider.symbols = symbols
        self.data_provider.timeframes = timeframes

    def start(self) -> None:
        """Start orchestrator"""
        if self.running:
            raise RuntimeError("Orchestrator already running")

        logger.info("Starting orchestrator")

        # Load strategies
        self.load_strategies()

        if len(self.strategies) == 0:
            logger.warning("No strategies to run. Exiting.")
            return

        # Initialize data provider
        self.initialize_data_provider()

        if self.data_provider:
            self.data_provider.start()

        # Determine execution mode
        mode = self.scheduler.determine_mode(len(self.strategies))
        logger.info(f"Execution mode: {mode} ({len(self.strategies)} strategies)")

        self.running = True
        self.stats['start_time'] = datetime.now()

        # Main execution loop
        try:
            self._run_loop()
        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop orchestrator gracefully"""
        if not self.running:
            return

        logger.info("Stopping orchestrator")

        self.running = False

        # Stop data provider
        if self.data_provider:
            self.data_provider.stop()

        # Close positions if configured
        if self.config['deployment']['shutdown']['close_positions']:
            logger.info("Closing all positions")
            self._close_all_positions()

        # Cancel pending orders if configured
        if self.config['deployment']['shutdown']['cancel_orders']:
            logger.info("Canceling all pending orders")
            self._cancel_all_orders()

        logger.info("Orchestrator stopped")

    def emergency_stop(self) -> None:
        """Emergency stop - immediately halt all trading"""
        logger.critical("EMERGENCY STOP TRIGGERED")

        self.running = False

        # Close all positions immediately
        self._close_all_positions()

        # Cancel all orders
        self._cancel_all_orders()

        # Stop data provider
        if self.data_provider:
            self.data_provider.stop()

        logger.critical("EMERGENCY STOP COMPLETE")

    def _run_loop(self) -> None:
        """Main execution loop"""
        logger.info("Starting main execution loop")

        while self.running and not self.shutdown_requested:
            try:
                # Auto-switch execution mode if needed
                self.scheduler.auto_switch(len(self.strategies))

                # Execute strategies
                self._execute_iteration()

                # Update statistics
                self.stats['iterations'] += 1

                # Check emergency conditions
                self._check_emergency_conditions()

                # Sleep before next iteration (adaptive based on timeframe)
                import time
                time.sleep(1.0)  # 1 second for now

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                self.shutdown_requested = True
                break

            except Exception as e:
                logger.error(f"Iteration error: {e}", exc_info=True)
                self.stats['errors'] += 1

                # Emergency stop if too many errors
                if self.stats['errors'] > 10:
                    logger.critical("Too many errors, emergency stop")
                    self.emergency_stop()
                    break

    def _execute_iteration(self) -> None:
        """Execute one iteration of strategy evaluation"""
        for strategy_inst in self.strategies:
            if not strategy_inst.active:
                continue

            if strategy_inst.strategy is None:
                logger.warning(f"Strategy instance has no strategy object")
                continue

            try:
                # Get market data
                df = self._get_market_data(
                    strategy_inst.symbol,
                    strategy_inst.timeframe
                )

                if df is None or len(df) < 50:
                    # Not enough data yet
                    continue

                # Generate signal from strategy
                signal = strategy_inst.strategy.generate_signal(df)

                if signal:
                    self.stats['signals_generated'] += 1
                    logger.info(
                        f"Signal generated: {signal.direction} {strategy_inst.symbol} "
                        f"(reason: {signal.reason})"
                    )

                    # Execute signal
                    self._execute_signal(strategy_inst, signal)

            except Exception as e:
                logger.error(
                    f"Error executing strategy {strategy_inst.symbol}: {e}",
                    exc_info=True
                )

    def _get_market_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get market data from data provider"""
        if self.data_provider is None:
            return None

        return self.data_provider.get_data(symbol, timeframe)

    def _execute_signal(self, strategy_inst: StrategyInstance, signal: Signal) -> None:
        """Execute trading signal"""
        logger.info(
            f"Executing signal: {signal.direction} {strategy_inst.symbol} "
            f"(subaccount {strategy_inst.subaccount_id})"
        )

        # Get current market data
        df = self._get_market_data(strategy_inst.symbol, strategy_inst.timeframe)
        if df is None:
            logger.warning("No market data available")
            return

        current_price = df['close'].iloc[-1]
        subaccount_id = strategy_inst.subaccount_id
        account_balance = self.client.get_account_balance(subaccount_id)

        # Calculate position size with risk manager
        size, stop_loss, take_profit = self.risk_manager.calculate_position_size(
            signal=signal,
            account_balance=account_balance,
            current_price=current_price,
            df=df
        )

        # Place order via client (subaccount_id as first parameter)
        if signal.direction in ['long', 'short']:
            order = self.client.place_order(
                subaccount_id=subaccount_id,
                symbol=strategy_inst.symbol,
                side='buy' if signal.direction == 'long' else 'sell',
                size=size,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            if order:
                self.stats['orders_placed'] += 1
                logger.info(f"Order placed: {order}")

        elif signal.direction == 'close':
            # Close position
            self.client.close_position(
                subaccount_id=subaccount_id,
                symbol=strategy_inst.symbol
            )

    def _check_emergency_conditions(self) -> None:
        """Check for emergency stop conditions"""
        # Check max drawdown
        # Check daily loss
        # Check consecutive losses
        # etc.
        pass

    def _close_all_positions(self) -> None:
        """Close all open positions"""
        for strategy_inst in self.strategies:
            try:
                self.client.close_position(
                    subaccount_id=strategy_inst.subaccount_id,
                    symbol=strategy_inst.symbol
                )
                logger.info(f"Closed position for {strategy_inst.symbol} on subaccount {strategy_inst.subaccount_id}")
            except Exception as e:
                logger.error(f"Error closing position for {strategy_inst.symbol}: {e}")

    def _cancel_all_orders(self) -> None:
        """Cancel all pending orders"""
        # Track already-cancelled subaccounts to avoid duplicates
        cancelled_subaccounts = set()

        for strategy_inst in self.strategies:
            if strategy_inst.subaccount_id in cancelled_subaccounts:
                continue

            try:
                self.client.cancel_all_orders(strategy_inst.subaccount_id)
                cancelled_subaccounts.add(strategy_inst.subaccount_id)
                logger.info(f"Cancelled orders for subaccount {strategy_inst.subaccount_id}")
            except Exception as e:
                logger.error(f"Error canceling orders for subaccount {strategy_inst.subaccount_id}: {e}")

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown_requested = True

    def get_statistics(self) -> dict:
        """Get orchestrator statistics"""
        runtime = None
        if self.stats['start_time']:
            runtime = (datetime.now() - self.stats['start_time']).total_seconds()

        return {
            'running': self.running,
            'dry_run': self.dry_run,
            'runtime_seconds': runtime,
            'active_strategies': sum(1 for s in self.strategies if s.active),
            'total_strategies': len(self.strategies),
            'execution_mode': self.scheduler.current_mode,
            **self.stats,
            'data_provider': self.data_provider.get_statistics() if self.data_provider else None
        }
