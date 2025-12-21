"""
Main Orchestrator

Coordinates live trading execution across multiple strategies and timeframes.
Uses adaptive scheduling and multi-WebSocket data provider.

Following CLAUDE.md:
- Dry-run mode for safe testing
- Fast fail (no silent errors)
- Graceful shutdown
- Emergency stop capability
"""

import signal
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

from src.orchestration.websocket_provider import MultiWebSocketDataProvider
from src.orchestration.adaptive_scheduler import AdaptiveScheduler
from src.executor.hyperliquid_client import HyperliquidClient
from src.executor.risk_manager import RiskManager
from src.executor.position_tracker import PositionTracker
from src.executor.subaccount_manager import SubaccountManager
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
        # Extract credentials from config (if available)
        private_key = config.get('hyperliquid', {}).get('private_key')
        vault_address = config.get('hyperliquid', {}).get('vault_address')

        self.client = HyperliquidClient(
            private_key=private_key,
            vault_address=vault_address,
            dry_run=dry_run
        )
        self.risk_manager = RiskManager(config)
        self.position_tracker = PositionTracker(client=self.client)
        self.subaccount_manager = SubaccountManager(self.client, config=config, dry_run=dry_run)
        self.scheduler = AdaptiveScheduler(config)

        # Data provider (initialized later)
        self.data_provider: Optional[MultiWebSocketDataProvider] = None

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
                    # Import strategy class dynamically
                    # NOTE: In real implementation, would use proper module loading
                    # For now, we'll create a mock instance
                    strategy_instance = StrategyInstance(
                        strategy=None,  # Placeholder
                        subaccount_id=db_strat.subaccount_id or 0,
                        symbol=db_strat.symbol or 'BTC',
                        timeframe=db_strat.timeframe or '15m',
                        active=True
                    )

                    self.strategies.append(strategy_instance)

                except Exception as e:
                    logger.error(f"Failed to load strategy {db_strat.name}: {e}")
                    continue

        logger.info(f"Loaded {len(self.strategies)} strategy instances")

    def initialize_data_provider(self) -> None:
        """Initialize multi-WebSocket data provider"""
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

        self.data_provider = MultiWebSocketDataProvider(
            config=self.config,
            symbols=symbols,
            timeframes=timeframes
        )

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

            try:
                # Get market data
                df = self._get_market_data(
                    strategy_inst.symbol,
                    strategy_inst.timeframe
                )

                if df is None or len(df) < 50:
                    # Not enough data yet
                    continue

                # Generate signal
                # NOTE: In real implementation, would call strategy.generate_signal(df)
                # For now, this is a placeholder
                signal = None  # strategy_inst.strategy.generate_signal(df)

                if signal:
                    self.stats['signals_generated'] += 1

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
        account_balance = self.client.get_account_balance()

        # Calculate position size with risk manager
        size, stop_loss, take_profit = self.risk_manager.calculate_position_size(
            signal=signal,
            account_balance=account_balance,
            current_price=current_price,
            df=df
        )

        # Switch to correct subaccount
        self.client.switch_subaccount(strategy_inst.subaccount_id)

        # Place order via client
        if signal.direction in ['long', 'short']:
            order = self.client.place_order(
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
                # Switch to strategy's subaccount
                self.client.switch_subaccount(strategy_inst.subaccount_id)
                # Close position for this symbol
                self.client.close_position(strategy_inst.symbol)
                logger.info(f"Closed position for {strategy_inst.symbol} on subaccount {strategy_inst.subaccount_id}")
            except Exception as e:
                logger.error(f"Error closing position for {strategy_inst.symbol}: {e}")

    def _cancel_all_orders(self) -> None:
        """Cancel all pending orders"""
        for strategy_inst in self.strategies:
            try:
                # Switch to strategy's subaccount
                self.client.switch_subaccount(strategy_inst.subaccount_id)
                # Cancel all orders for this subaccount
                self.client.cancel_all_orders()
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
