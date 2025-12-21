#!/usr/bin/env python3
"""
SixBTC - AI-Powered Multi-Strategy Trading System
Main CLI entry point
"""

import sys
from pathlib import Path

# Add src/ to Python path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

import click
from rich.console import Console

from src.config import load_config
from src.utils import setup_logging, get_logger

# Initialize console
console = Console()

# Version
VERSION = "1.0.0"


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
@click.pass_context
def generate(ctx, count):
    """Generate new trading strategies"""
    logger = ctx.obj['logger']
    logger.info(f"Generating {count} strategies...")
    console.print(f"[yellow]TODO: Implement strategy generation[/yellow]")
    console.print(f"Would generate {count} strategies")


# ==============================================================================
# BACKTESTING
# ==============================================================================

@cli.command()
@click.option('--all', 'backtest_all', is_flag=True, help='Backtest all pending strategies')
@click.option('--strategy', type=str, help='Backtest specific strategy')
@click.option('--lookback-days', type=int, default=180, help='Lookback period in days')
@click.option('--workers', type=int, default=10, help='Parallel workers')
@click.pass_context
def backtest(ctx, backtest_all, strategy, lookback_days, workers):
    """Backtest strategies"""
    logger = ctx.obj['logger']

    if strategy:
        logger.info(f"Backtesting strategy: {strategy}")
        console.print(f"[yellow]TODO: Implement backtesting[/yellow]")
        console.print(f"Would backtest strategy: {strategy}")
    elif backtest_all:
        logger.info("Backtesting all pending strategies...")
        console.print(f"[yellow]TODO: Implement backtesting[/yellow]")
        console.print(f"Would backtest all pending strategies")
        console.print(f"Lookback: {lookback_days} days, Workers: {workers}")
    else:
        console.print("[red]Error: Specify --all or --strategy <name>[/red]")


# ==============================================================================
# CLASSIFICATION & SELECTION
# ==============================================================================

@cli.command()
@click.pass_context
def classify(ctx):
    """Classify and select top strategies"""
    logger = ctx.obj['logger']
    logger.info("Running strategy classification...")
    console.print(f"[yellow]TODO: Implement classification[/yellow]")


# ==============================================================================
# DEPLOYMENT
# ==============================================================================

@cli.command()
@click.option('--dry-run', is_flag=True, help='Simulate deployment without executing')
@click.pass_context
def deploy(ctx, dry_run):
    """Deploy strategies to live trading"""
    logger = ctx.obj['logger']

    if dry_run:
        logger.info("Running deployment dry-run...")
        console.print(f"[yellow]DRY RUN: Would deploy strategies (no real orders)[/yellow]")
    else:
        logger.warning("Deploying strategies to LIVE TRADING...")
        console.print(f"[yellow]TODO: Implement live deployment[/yellow]")


# ==============================================================================
# ORCHESTRATOR COMMANDS
# ==============================================================================

@cli.command()
@click.option('--dry-run', is_flag=True, default=True, help='Run in dry-run mode (default: True)')
@click.option('--live', is_flag=True, help='Run in LIVE mode (real trading)')
@click.pass_context
def run(ctx, dry_run, live):
    """Start the main orchestrator for live trading"""
    logger = ctx.obj['logger']
    config = ctx.obj['config']

    # Determine mode
    if live:
        dry_run = False
        console.print("[bold red]WARNING: LIVE MODE ENABLED - Real trading will occur![/bold red]")
        console.print("[yellow]Press Ctrl+C within 5 seconds to cancel...[/yellow]\n")
        import time
        time.sleep(5)
    else:
        console.print("[bold green]DRY-RUN MODE - No real orders will be placed[/bold green]\n")

    try:
        from src.orchestration.orchestrator import Orchestrator

        logger.info(f"Starting orchestrator (dry_run={dry_run})...")
        console.print(f"Initializing orchestrator...\n")

        # Create orchestrator
        orch = Orchestrator(config, dry_run=dry_run)

        # Start
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
