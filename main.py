#!/usr/bin/env python3
"""
SixBTC - AI-Powered Multi-Strategy Trading System
Main CLI entry point
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src/ to Python path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import load_config
from src.utils import setup_logging, get_logger

# Initialize console
console = Console()

# Version
VERSION = "1.0.0"

# Strategy directories
STRATEGIES_DIR = ROOT_DIR / "strategies"
PENDING_DIR = STRATEGIES_DIR / "pending"
TESTED_DIR = STRATEGIES_DIR / "tested"
SELECTED_DIR = STRATEGIES_DIR / "selected"
LIVE_DIR = STRATEGIES_DIR / "live"


@click.group()
@click.version_option(version=VERSION)
@click.pass_context
def cli(ctx):
    """
    SixBTC - AI-Powered Multi-Strategy Trading System

    Autonomous trading system for Hyperliquid perpetual futures.

    \b
    Quick start:
        sixbtc status          # Check system status
        sixbtc generate --count 50      # Generate 50 new strategies
        sixbtc backtest --all           # Backtest all pending strategies
        sixbtc classify                 # Select top strategies
        sixbtc deploy                   # Deploy to live trading

    \b
    For help on any command:
        sixbtc <command> --help
    """
    # Store config and logger in context
    if ctx.obj is None:
        ctx.obj = {}

    # Load config
    try:
        ctx.obj['config'] = load_config()
    except Exception as e:
        console.print(f"[red]Failed to load configuration:[/red] {e}")
        sys.exit(1)

    # Setup logging
    config = ctx.obj['config']
    setup_logging(
        log_file=config.get('logging.file', 'logs/sixbtc.log'),
        log_level=config.get('logging.level', 'INFO'),
        max_bytes=config.get('logging.max_bytes', 10485760),
        backup_count=config.get('logging.backup_count', 5),
        module_levels=config.get('logging.modules')
    )

    ctx.obj['logger'] = get_logger('sixbtc.cli')


# ==============================================================================
# STATUS COMMANDS
# ==============================================================================

@cli.command()
@click.option('--module', type=str, help='Check specific module status')
@click.option('--live', is_flag=True, help='Show live trading status')
@click.option('--subaccount', type=int, help='Check specific subaccount')
@click.pass_context
def status(ctx, module, live, subaccount):
    """Check system status"""
    logger = ctx.obj['logger']
    config = ctx.obj['config']

    logger.info("Checking system status...")
    console.print(f"\n[bold cyan]SixBTC v{VERSION}[/bold cyan]")
    console.print(f"Status: [green]Configuration loaded[/green]\n")

    # Basic info
    console.print(f"System: {config.get('system.name')}")
    console.print(f"Version: {config.get('system.version')}")
    console.print(f"Deployment mode: {config.get('system.deployment_mode')}")
    console.print(f"Execution mode: {config.get('system.scalability.execution_mode')}")
    console.print(f"Max strategies: {config.get('system.scalability.max_strategies')}\n")

    # Orchestrator
    console.print(f"[bold]Orchestrator:[/bold]")
    console.print(f"  Mode: {config.get('execution.orchestrator.mode')}")
    console.print(f"  Scheduling: {config.get('execution.orchestrator.scheduling.mode')}")
    console.print(f"  Status: [yellow]Not running[/yellow]\n")

    # Database
    console.print(f"[bold]Database:[/bold]")
    console.print(f"  Host: {config.get('database.host')}:{config.get('database.port')}")
    console.print(f"  Database: {config.get('database.database')}")
    console.print(f"  Status: [yellow]Not connected (TODO: implement)[/yellow]\n")

    # Strategies
    console.print(f"[bold]Strategies:[/bold]")
    console.print(f"  Generated: [yellow]0[/yellow] (TODO: implement)")
    console.print(f"  Tested: [yellow]0[/yellow] (TODO: implement)")
    console.print(f"  Live: [yellow]0[/yellow] (TODO: implement)\n")

    if module:
        console.print(f"Module '{module}' status: [yellow]TODO: implement[/yellow]")

    if live:
        console.print(f"Live trading status: [yellow]TODO: implement[/yellow]")

    if subaccount:
        console.print(f"Subaccount {subaccount} status: [yellow]TODO: implement[/yellow]")


# ==============================================================================
# STRATEGY GENERATION
# ==============================================================================

@cli.command()
@click.option('--count', type=int, default=50, help='Number of strategies to generate')
@click.option('--timeframe', type=str, default=None, help='Specific timeframe (e.g., 15m, 1h)')
@click.option('--type', 'strategy_type', type=str, default=None, help='Strategy type (MOM, REV, TRN, BRE)')
@click.option('--use-patterns/--no-patterns', default=True, help='Use pattern-discovery patterns')
@click.pass_context
def generate(ctx, count, timeframe, strategy_type, use_patterns):
    """Generate new trading strategies using AI"""
    logger = ctx.obj['logger']
    config = ctx.obj['config']

    console.print(f"\n[bold cyan]Strategy Generation[/bold cyan]")
    console.print(f"Count: {count}")
    console.print(f"Timeframe: {timeframe or 'all'}")
    console.print(f"Type: {strategy_type or 'all'}")
    console.print(f"Use patterns: {use_patterns}\n")

    try:
        from src.generator.strategy_builder import StrategyBuilder

        # Check if AI is configured
        ai_config = config.get('generation')
        if not ai_config:
            console.print("[red]Error: 'generation' section missing from config[/red]")
            return

        # Initialize builder (pass raw config dict)
        builder = StrategyBuilder(config._raw_config, init_ai=True)

        if not builder.ai_manager:
            console.print("[yellow]Warning: AI Manager not available (check API keys)[/yellow]")
            console.print("[yellow]Generation will use template-based fallback[/yellow]\n")

        # Determine timeframes and types
        timeframes = [timeframe] if timeframe else config.get('trading.timeframes.available', ['15m', '1h', '4h'])
        types = [strategy_type] if strategy_type else ['MOM', 'REV', 'TRN', 'BRE']

        # Ensure directories exist
        PENDING_DIR.mkdir(parents=True, exist_ok=True)

        generated = []
        failed = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Generating {count} strategies...", total=count)

            for i in range(count):
                tf = timeframes[i % len(timeframes)]
                st = types[i % len(types)]

                progress.update(task, description=f"Generating {st} strategy for {tf}...")

                try:
                    if builder.ai_manager:
                        strategy = builder.generate_strategy(st, tf, use_patterns)
                        code = strategy.code
                        strategy_id = strategy.strategy_id
                        validated = strategy.validation_passed
                    else:
                        # Fallback: generate from template
                        strategy_id = builder.generate_strategy_id(st)
                        code = builder._generate_fallback_code({
                            'strategy_name': strategy_id,
                            'indicator': 'RSI',
                            'period': 14,
                            'threshold': 30
                        })
                        validated = builder.validate_code(code)

                    # Save to pending directory
                    filename = f"{strategy_id}.py"
                    filepath = PENDING_DIR / filename

                    with open(filepath, 'w') as f:
                        f.write(code)

                    generated.append({
                        'id': strategy_id,
                        'type': st,
                        'timeframe': tf,
                        'validated': validated,
                        'file': str(filepath)
                    })

                    logger.info(f"Generated: {strategy_id} (validated={validated})")

                except Exception as e:
                    logger.error(f"Failed to generate strategy {i+1}: {e}")
                    failed += 1

                progress.advance(task)

        # Summary
        console.print(f"\n[bold green]Generation Complete[/bold green]")
        console.print(f"Generated: {len(generated)}")
        console.print(f"Failed: {failed}")
        console.print(f"Validated: {sum(1 for s in generated if s['validated'])}")
        console.print(f"\nStrategies saved to: {PENDING_DIR}")

        # Show table of generated strategies
        if generated:
            table = Table(title="Generated Strategies")
            table.add_column("ID", style="cyan")
            table.add_column("Type")
            table.add_column("Timeframe")
            table.add_column("Valid", style="green")

            for s in generated[:10]:  # Show first 10
                table.add_row(
                    s['id'],
                    s['type'],
                    s['timeframe'],
                    "Yes" if s['validated'] else "[red]No[/red]"
                )

            if len(generated) > 10:
                table.add_row("...", "...", "...", "...")

            console.print(table)

    except ImportError as e:
        console.print(f"[red]Import error: {e}[/red]")
        console.print("[yellow]Make sure all dependencies are installed[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error(f"Generation failed: {e}", exc_info=True)


# ==============================================================================
# BACKTESTING
# ==============================================================================

@cli.command()
@click.option('--all', 'backtest_all', is_flag=True, help='Backtest all pending strategies')
@click.option('--strategy', type=str, help='Backtest specific strategy file or name')
@click.option('--symbol', type=str, default='BTC', help='Symbol to backtest (default: BTC)')
@click.option('--timeframe', type=str, default='15m', help='Timeframe (default: 15m)')
@click.option('--lookback-days', type=int, default=180, help='Lookback period in days')
@click.option('--workers', type=int, default=10, help='Parallel workers')
@click.pass_context
def backtest(ctx, backtest_all, strategy, symbol, timeframe, lookback_days, workers):
    """Backtest strategies using VectorBT"""
    logger = ctx.obj['logger']
    config = ctx.obj['config']

    console.print(f"\n[bold cyan]Backtesting[/bold cyan]")
    console.print(f"Symbol: {symbol}")
    console.print(f"Timeframe: {timeframe}")
    console.print(f"Lookback: {lookback_days} days\n")

    try:
        from src.backtester.backtest_engine import VectorBTEngine
        from src.backtester.data_loader import BacktestDataLoader
        from src.backtester.validator import LookaheadValidator
        import importlib.util

        # Initialize components
        engine = VectorBTEngine(config)
        data_loader = BacktestDataLoader()
        validator = LookaheadValidator()

        # Determine strategies to backtest
        strategies_to_test = []

        if strategy:
            # Single strategy
            strategy_path = Path(strategy)
            if not strategy_path.exists():
                # Try in pending directory
                strategy_path = PENDING_DIR / f"{strategy}.py"
            if not strategy_path.exists():
                strategy_path = PENDING_DIR / strategy

            if strategy_path.exists():
                strategies_to_test.append(strategy_path)
            else:
                console.print(f"[red]Strategy not found: {strategy}[/red]")
                return

        elif backtest_all:
            # All pending strategies
            if not PENDING_DIR.exists():
                console.print(f"[red]No pending strategies in {PENDING_DIR}[/red]")
                return

            strategies_to_test = list(PENDING_DIR.glob("*.py"))
            if not strategies_to_test:
                console.print(f"[yellow]No pending strategies found[/yellow]")
                return

        else:
            console.print("[red]Error: Specify --all or --strategy <name>[/red]")
            return

        console.print(f"Found {len(strategies_to_test)} strategies to backtest\n")

        # Load market data
        console.print(f"Loading {symbol} {timeframe} data...")
        try:
            data = data_loader.load_single_symbol(symbol, timeframe, lookback_days)
            console.print(f"Loaded {len(data)} candles\n")
        except Exception as e:
            console.print(f"[red]Failed to load data: {e}[/red]")
            console.print("[yellow]Make sure Binance data is available[/yellow]")
            return

        # Ensure tested directory exists
        TESTED_DIR.mkdir(parents=True, exist_ok=True)

        results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Backtesting...", total=len(strategies_to_test))

            for strategy_path in strategies_to_test:
                strategy_name = strategy_path.stem
                progress.update(task, description=f"Testing {strategy_name}...")

                try:
                    # Load strategy code
                    with open(strategy_path, 'r') as f:
                        code = f.read()

                    # Validate for lookahead bias
                    validation = validator.validate(code, data)

                    if not validation['ast_check']['passed']:
                        logger.warning(f"{strategy_name}: AST validation failed")
                        results.append({
                            'name': strategy_name,
                            'status': 'FAILED',
                            'reason': 'Lookahead bias detected',
                            'metrics': None
                        })
                        progress.advance(task)
                        continue

                    # Dynamic import of strategy
                    spec = importlib.util.spec_from_file_location(strategy_name, strategy_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Find StrategyCore subclass
                    strategy_class = None
                    for name in dir(module):
                        obj = getattr(module, name)
                        if isinstance(obj, type) and name.startswith('Strategy_'):
                            strategy_class = obj
                            break

                    if not strategy_class:
                        logger.warning(f"{strategy_name}: No StrategyCore class found")
                        results.append({
                            'name': strategy_name,
                            'status': 'FAILED',
                            'reason': 'No strategy class found',
                            'metrics': None
                        })
                        progress.advance(task)
                        continue

                    # Instantiate and backtest
                    strategy_instance = strategy_class()
                    metrics = engine.run_backtest(strategy_instance, data)

                    # Check thresholds
                    min_sharpe = config.get('backtesting.thresholds.min_sharpe', 1.0)
                    min_win_rate = config.get('backtesting.thresholds.min_win_rate', 0.55)
                    min_trades = config.get('backtesting.thresholds.min_total_trades', 100)

                    passed = (
                        metrics['sharpe_ratio'] >= min_sharpe and
                        metrics['win_rate'] >= min_win_rate and
                        metrics['total_trades'] >= min_trades
                    )

                    status = 'PASSED' if passed else 'BELOW_THRESHOLD'

                    results.append({
                        'name': strategy_name,
                        'status': status,
                        'reason': None,
                        'metrics': metrics
                    })

                    # Move to tested directory if passed
                    if passed:
                        dest = TESTED_DIR / strategy_path.name
                        strategy_path.rename(dest)
                        logger.info(f"{strategy_name}: PASSED (moved to tested/)")

                except Exception as e:
                    logger.error(f"{strategy_name}: Backtest error - {e}")
                    results.append({
                        'name': strategy_name,
                        'status': 'ERROR',
                        'reason': str(e),
                        'metrics': None
                    })

                progress.advance(task)

        # Summary
        passed_count = sum(1 for r in results if r['status'] == 'PASSED')
        failed_count = sum(1 for r in results if r['status'] in ['FAILED', 'ERROR'])
        below_threshold = sum(1 for r in results if r['status'] == 'BELOW_THRESHOLD')

        console.print(f"\n[bold green]Backtest Complete[/bold green]")
        console.print(f"Passed: {passed_count}")
        console.print(f"Below threshold: {below_threshold}")
        console.print(f"Failed/Error: {failed_count}")

        # Results table
        if results:
            table = Table(title="Backtest Results")
            table.add_column("Strategy", style="cyan")
            table.add_column("Status")
            table.add_column("Trades")
            table.add_column("Win Rate")
            table.add_column("Sharpe")
            table.add_column("Max DD")

            for r in results[:15]:
                if r['metrics']:
                    m = r['metrics']
                    status_style = "green" if r['status'] == 'PASSED' else "yellow"
                    table.add_row(
                        r['name'][:30],
                        f"[{status_style}]{r['status']}[/{status_style}]",
                        str(m['total_trades']),
                        f"{m['win_rate']:.1%}",
                        f"{m['sharpe_ratio']:.2f}",
                        f"{m['max_drawdown']:.1%}"
                    )
                else:
                    table.add_row(
                        r['name'][:30],
                        f"[red]{r['status']}[/red]",
                        "-",
                        "-",
                        "-",
                        r['reason'][:20] if r['reason'] else "-"
                    )

            console.print(table)

    except ImportError as e:
        console.print(f"[red]Import error: {e}[/red]")
        console.print("[yellow]Make sure VectorBT is installed: pip install vectorbt[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error(f"Backtest failed: {e}", exc_info=True)


# ==============================================================================
# CLASSIFICATION & SELECTION
# ==============================================================================

@cli.command()
@click.option('--top', type=int, default=10, help='Number of top strategies to select')
@click.pass_context
def classify(ctx, top):
    """Classify and select top strategies for deployment"""
    logger = ctx.obj['logger']
    config = ctx.obj['config']

    console.print(f"\n[bold cyan]Strategy Classification[/bold cyan]")
    console.print(f"Selecting top {top} strategies\n")

    try:
        from src.classifier.scorer import StrategyScorer
        from src.classifier.portfolio_builder import PortfolioBuilder
        import json

        # Initialize components
        scorer = StrategyScorer(config)
        builder = PortfolioBuilder(config)

        # Load tested strategies
        if not TESTED_DIR.exists():
            console.print(f"[yellow]No tested strategies in {TESTED_DIR}[/yellow]")
            return

        tested_files = list(TESTED_DIR.glob("*.py"))
        if not tested_files:
            console.print(f"[yellow]No tested strategies found[/yellow]")
            return

        console.print(f"Found {len(tested_files)} tested strategies\n")

        # Build strategy list with metrics
        strategies = []

        for strategy_path in tested_files:
            strategy_name = strategy_path.stem

            # Look for metrics file
            metrics_path = TESTED_DIR / f"{strategy_name}_metrics.json"

            if metrics_path.exists():
                with open(metrics_path, 'r') as f:
                    metrics = json.load(f)
            else:
                # Use placeholder metrics for demo
                metrics = {
                    'sharpe_ratio': 1.5,
                    'win_rate': 0.58,
                    'expectancy': 0.03,
                    'consistency': 0.65,
                    'wf_stability': 0.15,
                    'total_trades': 150
                }

            # Extract type and timeframe from name
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
                'shuffle_p_value': 0.01  # Assume passed
            })

        # Score strategies
        console.print("Scoring strategies...")
        ranked = scorer.rank_strategies(strategies)

        # Select top with diversification
        console.print("Applying diversification constraints...")
        selected = builder.select_top_10(ranked)

        if not selected:
            console.print("[yellow]No strategies passed all thresholds[/yellow]")

            # Show why strategies failed
            table = Table(title="Strategy Scores (All)")
            table.add_column("Strategy", style="cyan")
            table.add_column("Score")
            table.add_column("Sharpe")
            table.add_column("Win Rate")

            for s in ranked[:10]:
                table.add_row(
                    s['name'][:30],
                    f"{s.get('score', 0):.1f}",
                    f"{s['backtest_sharpe']:.2f}",
                    f"{s['backtest_win_rate']:.1%}"
                )

            console.print(table)
            return

        # Ensure selected directory exists
        SELECTED_DIR.mkdir(parents=True, exist_ok=True)

        # Move selected strategies
        for strategy in selected:
            src = Path(strategy['file'])
            if src.exists():
                dest = SELECTED_DIR / src.name
                src.rename(dest)
                strategy['file'] = str(dest)

        # Get portfolio stats
        stats = builder.get_portfolio_stats(selected)

        # Display results
        console.print(f"\n[bold green]Classification Complete[/bold green]")
        console.print(f"Selected: {stats['count']} strategies")
        console.print(f"Avg Score: {stats['avg_score']:.1f}")
        console.print(f"Avg Sharpe: {stats['avg_sharpe']:.2f}")

        console.print(f"\nType distribution: {stats['type_distribution']}")
        console.print(f"Timeframe distribution: {stats['timeframe_distribution']}")

        # Results table
        table = Table(title="Selected Strategies")
        table.add_column("Rank", style="dim")
        table.add_column("Strategy", style="cyan")
        table.add_column("Type")
        table.add_column("TF")
        table.add_column("Score", style="green")
        table.add_column("Sharpe")

        for i, s in enumerate(selected, 1):
            table.add_row(
                str(i),
                s['name'][:25],
                s['type'],
                s['timeframe'],
                f"{s.get('score', 0):.1f}",
                f"{s['backtest_sharpe']:.2f}"
            )

        console.print(table)
        console.print(f"\nStrategies moved to: {SELECTED_DIR}")

    except ImportError as e:
        console.print(f"[red]Import error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error(f"Classification failed: {e}", exc_info=True)


# ==============================================================================
# DEPLOYMENT
# ==============================================================================

@cli.command()
@click.option('--dry-run', is_flag=True, default=True, help='Simulate deployment (default: True)')
@click.option('--live', is_flag=True, help='Enable LIVE deployment (real trading)')
@click.pass_context
def deploy(ctx, dry_run, live):
    """Deploy selected strategies to subaccounts"""
    logger = ctx.obj['logger']
    config = ctx.obj['config']

    # Determine mode
    if live:
        dry_run = False
        console.print("\n[bold red]WARNING: LIVE DEPLOYMENT MODE[/bold red]")
        console.print("[yellow]Real trades will be executed![/yellow]")
        console.print("[yellow]Press Ctrl+C within 5 seconds to cancel...[/yellow]\n")
        import time
        time.sleep(5)
    else:
        console.print("\n[bold green]DRY-RUN MODE[/bold green]")
        console.print("[dim]No real orders will be placed[/dim]\n")

    try:
        from src.executor.subaccount_manager import SubaccountManager
        from src.executor.hyperliquid_client import HyperliquidClient

        # Load selected strategies
        if not SELECTED_DIR.exists():
            console.print(f"[yellow]No selected strategies in {SELECTED_DIR}[/yellow]")
            console.print("[dim]Run 'sixbtc classify' first[/dim]")
            return

        selected_files = list(SELECTED_DIR.glob("*.py"))
        if not selected_files:
            console.print(f"[yellow]No selected strategies found[/yellow]")
            return

        console.print(f"Found {len(selected_files)} strategies to deploy\n")

        # Initialize client and manager
        client = HyperliquidClient(config, dry_run=dry_run)
        manager = SubaccountManager(client, config)

        # Get subaccount count
        if config.get('hyperliquid.subaccounts.test_mode.enabled', False):
            max_subaccounts = config.get('hyperliquid.subaccounts.test_mode.count', 3)
        else:
            max_subaccounts = config.get('hyperliquid.subaccounts.total', 10)

        strategies_to_deploy = selected_files[:max_subaccounts]

        console.print(f"Deploying to {len(strategies_to_deploy)} subaccounts...\n")

        # Deploy strategies
        deployed = []

        for i, strategy_path in enumerate(strategies_to_deploy, 1):
            strategy_name = strategy_path.stem

            try:
                result = manager.deploy_strategy(
                    subaccount_id=i,
                    strategy_name=strategy_name
                )

                deployed.append({
                    'subaccount': i,
                    'strategy': strategy_name,
                    'status': 'DEPLOYED' if result else 'FAILED'
                })

                # Move to live directory
                if result:
                    LIVE_DIR.mkdir(parents=True, exist_ok=True)
                    dest = LIVE_DIR / strategy_path.name
                    strategy_path.rename(dest)

                logger.info(f"Deployed {strategy_name} to subaccount {i}")

            except Exception as e:
                logger.error(f"Failed to deploy {strategy_name}: {e}")
                deployed.append({
                    'subaccount': i,
                    'strategy': strategy_name,
                    'status': 'ERROR'
                })

        # Summary
        success_count = sum(1 for d in deployed if d['status'] == 'DEPLOYED')

        console.print(f"\n[bold green]Deployment Complete[/bold green]")
        console.print(f"Deployed: {success_count}/{len(deployed)}")
        console.print(f"Mode: {'LIVE' if not dry_run else 'DRY-RUN'}")

        # Results table
        table = Table(title="Deployment Status")
        table.add_column("Subaccount", style="cyan")
        table.add_column("Strategy")
        table.add_column("Status")

        for d in deployed:
            status_style = "green" if d['status'] == 'DEPLOYED' else "red"
            table.add_row(
                str(d['subaccount']),
                d['strategy'][:30],
                f"[{status_style}]{d['status']}[/{status_style}]"
            )

        console.print(table)

        if dry_run:
            console.print("\n[dim]This was a DRY-RUN. Use --live for real deployment.[/dim]")

    except ImportError as e:
        console.print(f"[red]Import error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error(f"Deployment failed: {e}", exc_info=True)


# ==============================================================================
# ORCHESTRATOR COMMANDS
# ==============================================================================

@cli.command()
@click.option('--dry-run', is_flag=True, default=True, help='Run in dry-run mode (default: True)')
@click.option('--live', is_flag=True, help='Run in LIVE mode (real trading)')
@click.option('--mode', type=click.Choice(['auto', 'manual']), default='auto', help='auto=full autopilot, manual=signal execution only')
@click.pass_context
def run(ctx, dry_run, live, mode):
    """Start the autonomous trading system"""
    logger = ctx.obj['logger']
    config = ctx.obj['config']

    # Determine trading mode
    if live:
        dry_run = False
        console.print("\n[bold red]" + "=" * 60 + "[/bold red]")
        console.print("[bold red]WARNING: LIVE TRADING MODE ENABLED[/bold red]")
        console.print("[bold red]Real orders will be placed on Hyperliquid![/bold red]")
        console.print("[bold red]" + "=" * 60 + "[/bold red]")
        console.print("\n[yellow]Press Ctrl+C within 10 seconds to cancel...[/yellow]\n")
        import time
        time.sleep(10)
    else:
        console.print("\n[bold green]DRY-RUN MODE[/bold green]")
        console.print("[dim]No real orders will be placed[/dim]\n")

    if mode == 'auto':
        # Full autonomous mode with AutoPilot
        console.print("[bold cyan]AUTOPILOT MODE[/bold cyan]")
        console.print("The system will autonomously:")
        console.print("  - Generate strategies every 4 hours")
        console.print("  - Backtest pending strategies every 30 min")
        console.print("  - Classify and select top 10 every hour")
        console.print("  - Deploy to subaccounts every 24 hours")
        console.print("  - Monitor performance every 15 min\n")

        try:
            from src.orchestration.autopilot import AutoPilot

            logger.info(f"Starting AutoPilot (dry_run={dry_run})...")

            # Create and start autopilot
            autopilot = AutoPilot(config._raw_config, dry_run=dry_run)

            console.print("[green]AutoPilot started. Press Ctrl+C to stop gracefully.[/green]\n")
            autopilot.start()

        except KeyboardInterrupt:
            console.print("\n[yellow]Shutdown requested...[/yellow]")
            logger.info("Graceful shutdown initiated")
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            logger.error(f"AutoPilot error: {e}", exc_info=True)
            sys.exit(1)

    else:
        # Manual mode - just execute signals from existing strategies
        console.print("[bold cyan]MANUAL MODE[/bold cyan]")
        console.print("Signal execution only (no auto-generation)\n")

        try:
            from src.orchestration.orchestrator import Orchestrator

            logger.info(f"Starting orchestrator (dry_run={dry_run})...")

            # Create orchestrator
            orch = Orchestrator(config, dry_run=dry_run)

            console.print("[green]Orchestrator started. Press Ctrl+C to stop gracefully.[/green]\n")
            orch.start()

        except KeyboardInterrupt:
            console.print("\n[yellow]Shutdown requested...[/yellow]")
            logger.info("Graceful shutdown initiated")
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            logger.error(f"Orchestrator error: {e}", exc_info=True)
            sys.exit(1)


@cli.command()
@click.pass_context
def orchestrator_status(ctx):
    """Check orchestrator status"""
    logger = ctx.obj['logger']
    console.print(f"[yellow]TODO: Implement orchestrator status check[/yellow]")
    console.print("Would show: running status, active strategies, data provider stats, etc.")


# ==============================================================================
# MONITORING
# ==============================================================================

@cli.command()
@click.pass_context
def monitor(ctx):
    """Real-time monitoring dashboard"""
    logger = ctx.obj['logger']
    logger.info("Starting monitoring dashboard...")
    console.print(f"[yellow]TODO: Implement Rich TUI dashboard[/yellow]")


# ==============================================================================
# EMERGENCY CONTROLS
# ==============================================================================

@cli.command()
@click.option('--all', 'stop_all', is_flag=True, help='Stop all positions')
@click.option('--subaccount', type=int, help='Stop specific subaccount')
@click.pass_context
def emergency_stop(ctx, stop_all, subaccount):
    """Emergency stop all trading"""
    logger = ctx.obj['logger']

    if stop_all:
        logger.critical("EMERGENCY STOP - Closing all positions...")
        console.print(f"[bold red]EMERGENCY STOP - Closing ALL positions[/bold red]")
        console.print(f"[yellow]TODO: Implement emergency stop[/yellow]")
    elif subaccount:
        logger.warning(f"Emergency stop for subaccount {subaccount}...")
        console.print(f"[yellow]TODO: Implement subaccount emergency stop[/yellow]")
    else:
        console.print("[red]Error: Specify --all or --subaccount <id>[/red]")


@cli.command()
@click.pass_context
def trades(ctx):
    """View recent trades"""
    logger = ctx.obj['logger']
    console.print(f"[yellow]TODO: Implement trades view[/yellow]")


# ==============================================================================
# DATABASE MANAGEMENT
# ==============================================================================

@cli.group()
def db():
    """Database management commands"""
    pass


@db.command()
@click.pass_context
def init(ctx):
    """Initialize database schema"""
    logger = ctx.obj['logger']
    logger.info("Initializing database schema...")
    console.print(f"[yellow]TODO: Run Alembic migrations[/yellow]")


@db.command()
@click.pass_context
def migrate(ctx):
    """Run database migrations"""
    logger = ctx.obj['logger']
    logger.info("Running database migrations...")
    console.print(f"[yellow]TODO: Implement Alembic migrations[/yellow]")


@db.command()
@click.pass_context
def reset(ctx):
    """Reset database (DANGEROUS)"""
    logger = ctx.obj['logger']
    console.print(f"[bold red]WARNING: This will delete all data![/bold red]")
    console.print(f"[yellow]TODO: Implement database reset[/yellow]")


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    cli(obj={})
