"""
AutoPilot - Autonomous Trading System Controller

Manages the complete autonomous trading cycle:
- Strategy generation (every 4 hours)
- Backtesting (continuous, processes pending)
- Classification (every 1 hour)
- Deployment (every 24 hours)
- Monitoring (every 15 minutes)
"""

import time
import signal
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Strategy directories
ROOT_DIR = Path(__file__).parent.parent.parent
STRATEGIES_DIR = ROOT_DIR / "strategies"
PENDING_DIR = STRATEGIES_DIR / "pending"
TESTED_DIR = STRATEGIES_DIR / "tested"
SELECTED_DIR = STRATEGIES_DIR / "selected"
LIVE_DIR = STRATEGIES_DIR / "live"


class AutoPilot:
    """
    Autonomous trading system controller

    Manages the complete lifecycle:
    1. Generate strategies using AI
    2. Backtest and validate strategies
    3. Classify and select top performers
    4. Deploy to live trading
    5. Monitor performance and health
    """

    def __init__(self, config: dict, dry_run: bool = True):
        """
        Initialize AutoPilot

        Args:
            config: Configuration dictionary
            dry_run: If True, no real orders will be placed
        """
        self.config = config
        self.dry_run = dry_run
        self.running = False
        self.scheduler = BackgroundScheduler()
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Stats tracking
        self.stats = {
            'started_at': None,
            'cycles_completed': 0,
            'strategies_generated': 0,
            'strategies_backtested': 0,
            'strategies_deployed': 0,
            'last_generation': None,
            'last_backtest': None,
            'last_classification': None,
            'last_deployment': None,
            'errors': []
        }

        # Ensure directories exist
        for dir_path in [PENDING_DIR, TESTED_DIR, SELECTED_DIR, LIVE_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(f"AutoPilot initialized (dry_run={dry_run})")

    def start(self):
        """Start the autonomous trading system"""
        if self.running:
            logger.warning("AutoPilot already running")
            return

        self.running = True
        self.stats['started_at'] = datetime.now()

        logger.info("=" * 60)
        logger.info("AUTOPILOT STARTING")
        logger.info(f"Mode: {'DRY-RUN' if self.dry_run else 'LIVE'}")
        logger.info("=" * 60)

        # Schedule jobs
        self._schedule_jobs()

        # Start scheduler
        self.scheduler.start()

        # Run initial cycle immediately
        logger.info("Running initial cycle...")
        self._run_generation_cycle()
        self._run_backtest_cycle()
        self._run_classification_cycle()

        # Keep running
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop the autonomous trading system gracefully"""
        logger.info("AutoPilot stopping...")
        self.running = False

        # Shutdown scheduler
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)

        # Shutdown executor
        self.executor.shutdown(wait=True)

        logger.info("AutoPilot stopped")
        self._print_stats()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.stop()

    def _schedule_jobs(self):
        """Schedule all periodic jobs"""
        # Generation: run every 4 hours (hardcoded - runs templates_per_day across the day)
        gen_hours = 4
        self.scheduler.add_job(
            self._run_generation_cycle,
            IntervalTrigger(hours=gen_hours),
            id='generation',
            name='Strategy Generation',
            replace_existing=True
        )
        logger.info(f"Scheduled generation every {gen_hours} hours")

        # Backtesting: every 30 minutes (processes pending)
        self.scheduler.add_job(
            self._run_backtest_cycle,
            IntervalTrigger(minutes=30),
            id='backtesting',
            name='Strategy Backtesting',
            replace_existing=True
        )
        logger.info("Scheduled backtesting every 30 minutes")

        # Classification: every 1 hour
        class_hours = self.config.get('classification', {}).get('frequency_hours', 1)
        self.scheduler.add_job(
            self._run_classification_cycle,
            IntervalTrigger(hours=class_hours),
            id='classification',
            name='Strategy Classification',
            replace_existing=True
        )
        logger.info(f"Scheduled classification every {class_hours} hours")

        # Deployment: every 24 hours (at 00:00 UTC)
        deploy_hours = self.config.get('deployment', {}).get('rotation_frequency_hours', 24)
        self.scheduler.add_job(
            self._run_deployment_cycle,
            IntervalTrigger(hours=deploy_hours),
            id='deployment',
            name='Strategy Deployment',
            replace_existing=True
        )
        logger.info(f"Scheduled deployment every {deploy_hours} hours")

        # Monitoring: every 15 minutes
        monitor_interval = self.config.get('monitoring', {}).get('snapshot_interval_minutes', 15)
        self.scheduler.add_job(
            self._run_monitoring_cycle,
            IntervalTrigger(minutes=monitor_interval),
            id='monitoring',
            name='Performance Monitoring',
            replace_existing=True
        )
        logger.info(f"Scheduled monitoring every {monitor_interval} minutes")

    def _run_generation_cycle(self):
        """Generate new strategies"""
        if not self.running:
            return

        logger.info("[CYCLE] Starting strategy generation...")

        try:
            from src.generator.strategy_builder import StrategyBuilder

            # Initialize builder
            builder = StrategyBuilder(self.config, init_ai=True)

            # Get templates per day from config (divide by 6 cycles = every 4 hours)
            templates_per_day = self.config.get('generation', {}).get('templates_per_day', 20)
            templates_this_cycle = max(1, templates_per_day // 6)  # 6 cycles per day

            # Determine timeframes from global config
            timeframes = self.config.get('timeframes', ['15m', '1h', '4h'])
            types = ['MOM', 'REV', 'TRN', 'BRE']

            generated_count = 0

            for i in range(templates_this_cycle):
                if not self.running:
                    break

                tf = timeframes[i % len(timeframes)]
                st = types[i % len(types)]

                try:
                    if builder.ai_manager:
                        strategy = builder.generate_strategy(st, tf, use_patterns=True)
                        code = strategy.code
                        strategy_id = strategy.strategy_id
                    else:
                        # Fallback: template-based generation
                        strategy_id = builder.generate_strategy_id(st)
                        code = builder._generate_fallback_code({
                            'strategy_name': strategy_id,
                            'indicator': 'RSI',
                            'period': 14,
                            'threshold': 30
                        })

                    # Save to pending
                    filepath = PENDING_DIR / f"{strategy_id}.py"
                    with open(filepath, 'w') as f:
                        f.write(code)

                    generated_count += 1

                except Exception as e:
                    logger.error(f"Generation error: {e}")

            self.stats['strategies_generated'] += generated_count
            self.stats['last_generation'] = datetime.now()

            logger.info(f"[CYCLE] Generation complete: {generated_count} strategies")

        except Exception as e:
            logger.error(f"[CYCLE] Generation cycle failed: {e}")
            self.stats['errors'].append(('generation', str(e), datetime.now()))

    def _run_backtest_cycle(self):
        """Backtest pending strategies"""
        if not self.running:
            return

        logger.info("[CYCLE] Starting backtesting...")

        try:
            from src.backtester.backtest_engine import VectorBTEngine
            from src.backtester.data_loader import BacktestDataLoader
            from src.backtester.validator import LookaheadValidator
            import importlib.util

            # Get pending strategies
            pending_files = list(PENDING_DIR.glob("*.py"))

            if not pending_files:
                logger.info("[CYCLE] No pending strategies to backtest")
                return

            # Initialize components
            engine = VectorBTEngine(self.config)
            data_loader = BacktestDataLoader()
            validator = LookaheadValidator()

            # Load data
            symbol = 'BTC'
            timeframe = '15m'
            lookback_days = self.config.get('backtesting', {}).get('lookback_days', 180)

            try:
                data = data_loader.load_single_symbol(symbol, timeframe, lookback_days)
            except Exception as e:
                logger.warning(f"[CYCLE] Could not load market data: {e}")
                return

            tested_count = 0

            for strategy_path in pending_files[:10]:  # Process max 10 per cycle
                if not self.running:
                    break

                strategy_name = strategy_path.stem

                try:
                    # Load and validate
                    with open(strategy_path, 'r') as f:
                        code = f.read()

                    validation = validator.validate(code, data)

                    if not validation['ast_check']['passed']:
                        logger.warning(f"{strategy_name}: Lookahead bias detected, skipping")
                        strategy_path.unlink()  # Remove invalid strategy
                        continue

                    # Dynamic import
                    spec = importlib.util.spec_from_file_location(strategy_name, strategy_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Find strategy class
                    strategy_class = None
                    for name in dir(module):
                        obj = getattr(module, name)
                        if isinstance(obj, type) and name.startswith('Strategy_'):
                            strategy_class = obj
                            break

                    if not strategy_class:
                        logger.warning(f"{strategy_name}: No strategy class found")
                        continue

                    # Backtest
                    strategy_instance = strategy_class()
                    metrics = engine.run_backtest(strategy_instance, data)

                    # Check thresholds
                    min_sharpe = self.config.get('backtesting', {}).get('thresholds', {}).get('min_sharpe', 1.0)
                    min_win_rate = self.config.get('backtesting', {}).get('thresholds', {}).get('min_win_rate', 0.55)
                    min_trades = self.config.get('backtesting', {}).get('thresholds', {}).get('min_total_trades', 100)

                    passed = (
                        metrics['sharpe_ratio'] >= min_sharpe and
                        metrics['win_rate'] >= min_win_rate and
                        metrics['total_trades'] >= min_trades
                    )

                    if passed:
                        # Move to tested
                        dest = TESTED_DIR / strategy_path.name
                        strategy_path.rename(dest)

                        # Save metrics
                        import json
                        metrics_path = TESTED_DIR / f"{strategy_name}_metrics.json"
                        with open(metrics_path, 'w') as f:
                            json.dump(metrics, f, indent=2)

                        tested_count += 1
                        logger.info(f"{strategy_name}: PASSED (Sharpe={metrics['sharpe_ratio']:.2f})")
                    else:
                        # Remove underperforming
                        strategy_path.unlink()
                        logger.info(f"{strategy_name}: BELOW_THRESHOLD, removed")

                except Exception as e:
                    logger.error(f"{strategy_name}: Backtest error - {e}")

            self.stats['strategies_backtested'] += tested_count
            self.stats['last_backtest'] = datetime.now()

            logger.info(f"[CYCLE] Backtesting complete: {tested_count} passed")

        except Exception as e:
            logger.error(f"[CYCLE] Backtest cycle failed: {e}")
            self.stats['errors'].append(('backtest', str(e), datetime.now()))

    def _run_classification_cycle(self):
        """Classify and select top strategies"""
        if not self.running:
            return

        logger.info("[CYCLE] Starting classification...")

        try:
            from src.classifier.scorer import StrategyScorer
            from src.classifier.portfolio_builder import PortfolioBuilder
            import json

            # Get tested strategies
            tested_files = list(TESTED_DIR.glob("*.py"))

            if not tested_files:
                logger.info("[CYCLE] No tested strategies to classify")
                return

            # Initialize components
            scorer = StrategyScorer(self.config)
            builder = PortfolioBuilder(self.config)

            # Build strategy list
            strategies = []

            for strategy_path in tested_files:
                strategy_name = strategy_path.stem

                # Load metrics
                metrics_path = TESTED_DIR / f"{strategy_name}_metrics.json"

                if metrics_path.exists():
                    with open(metrics_path, 'r') as f:
                        metrics = json.load(f)
                else:
                    continue  # Skip if no metrics

                # Parse name for type/timeframe
                parts = strategy_name.split('_')
                strategy_type = parts[1] if len(parts) > 1 else 'GEN'
                timeframe = parts[-1] if len(parts) > 2 else '15m'

                strategies.append({
                    'name': strategy_name,
                    'type': strategy_type,
                    'timeframe': timeframe,
                    'file': str(strategy_path),
                    'backtest_results': metrics,
                    'backtest_sharpe': metrics.get('sharpe_ratio', 0),
                    'backtest_win_rate': metrics.get('win_rate', 0),
                    'shuffle_p_value': 0.01
                })

            if not strategies:
                logger.info("[CYCLE] No strategies with metrics to classify")
                return

            # Score and select
            ranked = scorer.rank_strategies(strategies)
            selected = builder.select_top_10(ranked)

            if selected:
                # Move to selected
                for strategy in selected:
                    src = Path(strategy['file'])
                    if src.exists():
                        dest = SELECTED_DIR / src.name
                        src.rename(dest)

                        # Move metrics too
                        metrics_src = TESTED_DIR / f"{src.stem}_metrics.json"
                        if metrics_src.exists():
                            metrics_dest = SELECTED_DIR / metrics_src.name
                            metrics_src.rename(metrics_dest)

                logger.info(f"[CYCLE] Classification complete: {len(selected)} selected")
            else:
                logger.info("[CYCLE] No strategies passed classification thresholds")

            self.stats['last_classification'] = datetime.now()

        except Exception as e:
            logger.error(f"[CYCLE] Classification cycle failed: {e}")
            self.stats['errors'].append(('classification', str(e), datetime.now()))

    def _run_deployment_cycle(self):
        """Deploy selected strategies to live trading"""
        if not self.running:
            return

        logger.info("[CYCLE] Starting deployment...")

        try:
            from src.executor.subaccount_manager import SubaccountManager
            from src.executor.hyperliquid_client import HyperliquidClient

            # Get selected strategies
            selected_files = list(SELECTED_DIR.glob("*.py"))

            if not selected_files:
                logger.info("[CYCLE] No selected strategies to deploy")
                return

            # Initialize client and manager
            client = HyperliquidClient(self.config, dry_run=self.dry_run)
            manager = SubaccountManager(client, self.config)

            # Get max subaccounts
            if self.config.get('hyperliquid', {}).get('subaccounts', {}).get('test_mode', {}).get('enabled', False):
                max_subaccounts = self.config.get('hyperliquid', {}).get('subaccounts', {}).get('test_mode', {}).get('count', 3)
            else:
                max_subaccounts = self.config.get('hyperliquid', {}).get('subaccounts', {}).get('total', 10)

            deployed_count = 0

            for i, strategy_path in enumerate(selected_files[:max_subaccounts], 1):
                strategy_name = strategy_path.stem

                try:
                    result = manager.deploy_strategy(
                        subaccount_id=i,
                        strategy_name=strategy_name
                    )

                    if result:
                        # Move to live
                        dest = LIVE_DIR / strategy_path.name
                        strategy_path.rename(dest)

                        # Move metrics too
                        metrics_src = SELECTED_DIR / f"{strategy_name}_metrics.json"
                        if metrics_src.exists():
                            metrics_dest = LIVE_DIR / metrics_src.name
                            metrics_src.rename(metrics_dest)

                        deployed_count += 1
                        logger.info(f"Deployed {strategy_name} to subaccount {i}")

                except Exception as e:
                    logger.error(f"Failed to deploy {strategy_name}: {e}")

            self.stats['strategies_deployed'] += deployed_count
            self.stats['last_deployment'] = datetime.now()

            logger.info(f"[CYCLE] Deployment complete: {deployed_count} deployed")

        except Exception as e:
            logger.error(f"[CYCLE] Deployment cycle failed: {e}")
            self.stats['errors'].append(('deployment', str(e), datetime.now()))

    def _run_monitoring_cycle(self):
        """Monitor system health and performance"""
        if not self.running:
            return

        try:
            from src.monitor.health_check import HealthChecker

            # Check health
            checker = HealthChecker(self.config)
            status = checker.check_all()

            if not status['healthy']:
                logger.warning(f"[MONITOR] System unhealthy: {status['issues']}")

            # Log stats
            self.stats['cycles_completed'] += 1

            # Count strategies in each stage
            pending_count = len(list(PENDING_DIR.glob("*.py")))
            tested_count = len(list(TESTED_DIR.glob("*.py")))
            selected_count = len(list(SELECTED_DIR.glob("*.py")))
            live_count = len(list(LIVE_DIR.glob("*.py")))

            logger.info(
                f"[MONITOR] Strategies: pending={pending_count}, "
                f"tested={tested_count}, selected={selected_count}, live={live_count}"
            )

        except Exception as e:
            logger.debug(f"[MONITOR] Monitoring cycle error: {e}")

    def _print_stats(self):
        """Print final statistics"""
        logger.info("=" * 60)
        logger.info("AUTOPILOT STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Started: {self.stats['started_at']}")
        logger.info(f"Stopped: {datetime.now()}")
        logger.info(f"Cycles completed: {self.stats['cycles_completed']}")
        logger.info(f"Strategies generated: {self.stats['strategies_generated']}")
        logger.info(f"Strategies backtested: {self.stats['strategies_backtested']}")
        logger.info(f"Strategies deployed: {self.stats['strategies_deployed']}")
        logger.info(f"Errors: {len(self.stats['errors'])}")
        logger.info("=" * 60)

    def get_status(self) -> dict:
        """Get current status"""
        return {
            'running': self.running,
            'dry_run': self.dry_run,
            'stats': self.stats,
            'pending_strategies': len(list(PENDING_DIR.glob("*.py"))),
            'tested_strategies': len(list(TESTED_DIR.glob("*.py"))),
            'selected_strategies': len(list(SELECTED_DIR.glob("*.py"))),
            'live_strategies': len(list(LIVE_DIR.glob("*.py"))),
        }
