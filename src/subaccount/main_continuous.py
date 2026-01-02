"""
Subaccount Manager Process

Manages strategy deployment, rotation, and capital rebalancing:
1. Deploy SELECTED strategies to free subaccounts
2. Monitor live strategy performance
3. Retire underperforming strategies
4. Rebalance capital across subaccounts
"""

import asyncio
import os
import signal
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.config import load_config
from src.database import get_session, Strategy, Subaccount, BacktestResult, PerformanceSnapshot
from src.executor.hyperliquid_client import HyperliquidClient
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()._raw_config
setup_logging(
    log_file='logs/subaccount.log',
    log_level=_config.get('logging', {}).get('level', 'INFO'),
)

logger = get_logger(__name__)


class SubaccountManagerProcess:
    """
    Continuous subaccount management process.

    Handles the lifecycle of strategies on Hyperliquid subaccounts.
    """

    def __init__(self):
        """Initialize the subaccount manager"""
        self.config = load_config()._raw_config
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Process configuration (from subaccount_manager section)
        subaccount_config = self.config.get('subaccount_manager', {})
        self.rotation_interval_hours = subaccount_config.get('rotation_interval_hours', 24)
        self.rebalance_enabled = subaccount_config.get('rebalance_enabled', True)

        # Retirement thresholds
        risk_config = self.config.get('risk', {})
        self.max_degradation = 0.50  # 50% worse than backtest
        self.max_drawdown = risk_config.get('max_subaccount_drawdown', 0.25)

        # Trading configuration
        trading_config = self.config.get('trading', {})
        subaccount_config = self.config.get('subaccount_manager', {})
        self.dry_run = subaccount_config.get('dry_run', True)

        # Hyperliquid client
        self.client = HyperliquidClient(self.config, dry_run=self.dry_run)

        # Number of subaccounts
        self.n_subaccounts = trading_config.get('n_subaccounts', 10)

        logger.info(
            f"SubaccountManagerProcess initialized: "
            f"rotation={self.rotation_interval_hours}h, "
            f"rebalance={self.rebalance_enabled}, "
            f"dry_run={self.dry_run}"
        )

    async def run_continuous(self):
        """Main continuous management loop"""
        logger.info("Starting continuous subaccount management loop")

        while not self.shutdown_event.is_set() and not self.force_exit:
            try:
                # 1. Evaluate live strategy performance
                await self._evaluate_live_strategies()

                # 2. Deploy new strategies to free slots
                await self._deploy_strategies()

                # 3. Rebalance capital (if enabled)
                if self.rebalance_enabled:
                    await self._rebalance_capital()

            except Exception as e:
                logger.error(f"Management cycle error: {e}", exc_info=True)

            # Wait for next rotation cycle
            await self._wait_interval()

        logger.info("Subaccount management loop ended")

    async def _evaluate_live_strategies(self):
        """Evaluate and retire underperforming strategies"""
        logger.info("Evaluating live strategy performance")

        live_strategies = self._get_live_strategies()

        for strategy in live_strategies:
            try:
                degradation = self._calculate_degradation(strategy)
                current_dd = strategy.get('current_drawdown', 0)

                if degradation > self.max_degradation:
                    logger.warning(
                        f"Strategy {strategy['name']} degradation {degradation:.2%} > "
                        f"{self.max_degradation:.2%}, retiring"
                    )
                    await self._retire_strategy(strategy)

                elif current_dd > self.max_drawdown:
                    logger.warning(
                        f"Strategy {strategy['name']} drawdown {current_dd:.2%} > "
                        f"{self.max_drawdown:.2%}, retiring"
                    )
                    await self._retire_strategy(strategy)

            except Exception as e:
                logger.error(f"Error evaluating {strategy['name']}: {e}")

    def _get_live_strategies(self) -> List[Dict]:
        """Get all live strategies with their performance data"""
        strategies = []

        with get_session() as session:
            results = (
                session.query(Strategy, Subaccount, BacktestResult)
                .join(Subaccount, Strategy.id == Subaccount.strategy_id)
                .join(BacktestResult, Strategy.id == BacktestResult.strategy_id)
                .filter(Strategy.status == "LIVE")
                .all()
            )

            for strategy, subaccount, backtest in results:
                strategies.append({
                    'id': str(strategy.id),
                    'name': strategy.name,
                    'subaccount_id': subaccount.id,
                    'live_since': strategy.live_since,
                    'backtest_sharpe': backtest.sharpe_ratio,
                    'backtest_win_rate': backtest.win_rate,
                    'live_win_rate': subaccount.win_rate,
                    'current_drawdown': subaccount.current_drawdown or 0,
                    'total_pnl': subaccount.total_pnl or 0
                })

        return strategies

    def _calculate_degradation(self, strategy: Dict) -> float:
        """
        Calculate performance degradation vs backtest.

        Returns:
            Degradation factor (0 = same as backtest, 1 = 100% worse)
        """
        backtest_wr = strategy.get('backtest_win_rate', 0.5)
        live_wr = strategy.get('live_win_rate')

        if live_wr is None or backtest_wr <= 0:
            return 0

        # Degradation = how much worse is live vs backtest
        degradation = (backtest_wr - live_wr) / backtest_wr

        return max(0, degradation)

    async def _retire_strategy(self, strategy: Dict):
        """Retire a strategy from live trading"""
        logger.info(f"Retiring strategy {strategy['name']}")

        if not self.dry_run:
            # Close any open positions
            await self.client.close_all_positions(strategy['subaccount_id'])

        with get_session() as session:
            # Update strategy status
            db_strategy = session.query(Strategy).filter(Strategy.id == strategy['id']).first()
            if db_strategy:
                db_strategy.status = "RETIRED"
                db_strategy.retired_at = datetime.utcnow()

            # Free up subaccount
            subaccount = (
                session.query(Subaccount)
                .filter(Subaccount.id == strategy['subaccount_id'])
                .first()
            )
            if subaccount:
                subaccount.strategy_id = None
                subaccount.status = "PAUSED"

    async def _deploy_strategies(self):
        """Deploy SELECTED strategies to free subaccounts"""
        logger.info("Checking for strategies to deploy")

        # Get free subaccounts
        free_slots = self._get_free_subaccounts()

        if not free_slots:
            logger.debug("No free subaccounts available")
            return

        # Get SELECTED strategies not yet deployed
        selected = self._get_selected_strategies()

        if not selected:
            logger.debug("No SELECTED strategies to deploy")
            return

        # Deploy strategies to free slots
        for slot, strategy in zip(free_slots, selected):
            try:
                await self._deploy_to_subaccount(slot, strategy)
            except Exception as e:
                logger.error(f"Failed to deploy {strategy['name']}: {e}")

    def _get_free_subaccounts(self) -> List[Dict]:
        """Get subaccounts without assigned strategies"""
        free = []

        with get_session() as session:
            # Get all subaccounts
            subaccounts = session.query(Subaccount).all()

            existing_ids = {s.id for s in subaccounts}

            # Add any missing subaccounts
            for i in range(1, self.n_subaccounts + 1):
                if i not in existing_ids:
                    new_sa = Subaccount(id=i, status="PAUSED", allocated_capital=0)
                    session.add(new_sa)

            session.commit()

            # Get free subaccounts
            for sa in session.query(Subaccount).filter(Subaccount.strategy_id.is_(None)).all():
                free.append({
                    'id': sa.id,
                    'allocated_capital': sa.allocated_capital
                })

        return free

    def _get_selected_strategies(self) -> List[Dict]:
        """Get SELECTED strategies not yet deployed"""
        strategies = []

        with get_session() as session:
            results = (
                session.query(Strategy)
                .filter(Strategy.status == "SELECTED")
                .all()
            )

            for strategy in results:
                # Check if already deployed
                deployed = (
                    session.query(Subaccount)
                    .filter(Subaccount.strategy_id == strategy.id)
                    .first()
                )

                if not deployed:
                    strategies.append({
                        'id': str(strategy.id),
                        'name': strategy.name,
                        'type': strategy.strategy_type,
                        'timeframe': strategy.timeframe
                    })

        return strategies

    async def _deploy_to_subaccount(self, slot: Dict, strategy: Dict):
        """Deploy a strategy to a subaccount"""
        logger.info(f"Deploying {strategy['name']} to subaccount {slot['id']}")

        with get_session() as session:
            # Update subaccount
            subaccount = session.query(Subaccount).filter(Subaccount.id == slot['id']).first()
            if subaccount:
                subaccount.strategy_id = strategy['id']
                subaccount.status = "ACTIVE"

            # Update strategy status
            db_strategy = session.query(Strategy).filter(Strategy.id == strategy['id']).first()
            if db_strategy:
                db_strategy.status = "LIVE"
                db_strategy.live_since = datetime.utcnow()

        logger.info(f"Deployed {strategy['name']} to subaccount {slot['id']}")

    async def _rebalance_capital(self):
        """Rebalance capital across active subaccounts"""
        logger.debug("Checking capital rebalance")

        with get_session() as session:
            active_subaccounts = (
                session.query(Subaccount)
                .filter(Subaccount.status == "ACTIVE")
                .all()
            )

            if not active_subaccounts:
                return

            # Get total capital from config
            total_capital = self.config.get('trading', {}).get('total_capital', 1000)
            capital_per_subaccount = total_capital / len(active_subaccounts)

            for sa in active_subaccounts:
                if abs(sa.allocated_capital - capital_per_subaccount) > 10:
                    logger.info(
                        f"Rebalancing subaccount {sa.id}: "
                        f"${sa.allocated_capital:.2f} -> ${capital_per_subaccount:.2f}"
                    )
                    sa.allocated_capital = capital_per_subaccount

    async def _wait_interval(self):
        """Wait for next rotation cycle"""
        wait_seconds = self.rotation_interval_hours * 3600

        logger.debug(f"Waiting {self.rotation_interval_hours}h until next rotation")

        while wait_seconds > 0 and not self.shutdown_event.is_set():
            sleep_time = min(60, wait_seconds)
            await asyncio.sleep(sleep_time)
            wait_seconds -= sleep_time

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
            logger.info("Subaccount manager process terminated")
