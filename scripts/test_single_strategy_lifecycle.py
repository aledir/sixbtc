#!/usr/bin/env python3
"""
Single Strategy Lifecycle Test

Tests the complete flow:
1. GENERATOR: Create one template with AI, generate parametric variations
2. VALIDATOR: Validate the generated strategy code
3. BACKTESTER: Run backtest on the strategy
4. CLASSIFIER: Score and rank the strategy

Usage:
    python scripts/test_single_strategy_lifecycle.py
"""

import sys
import time
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.database import get_session
from src.database.models import Strategy, StrategyTemplate, BacktestResult

console = Console()


def phase_header(phase_num: int, title: str):
    """Print phase header"""
    console.print()
    console.print(Panel(
        f"[bold white]PHASE {phase_num}: {title}[/bold white]",
        style="cyan",
        width=60
    ))


def step(msg: str):
    """Print step message"""
    console.print(f"  [dim]>[/dim] {msg}")


def success(msg: str):
    """Print success message"""
    console.print(f"  [green]OK[/green] {msg}")


def error(msg: str):
    """Print error message"""
    console.print(f"  [red]ERROR[/red] {msg}")


def test_generator() -> tuple[StrategyTemplate, list]:
    """
    Phase 1: Generate one template and its parametric variations
    """
    phase_header(1, "GENERATOR")

    config = load_config()._raw_config

    # 1.1 Generate template with AI
    step("Initializing TemplateGenerator...")
    from src.generator.template_generator import TemplateGenerator, VALID_STRUCTURES

    generator = TemplateGenerator(config)
    success(f"TemplateGenerator ready ({len(VALID_STRUCTURES)} structures)")

    # Pick a specific structure for testing
    structure = VALID_STRUCTURES[0]  # First valid structure
    strategy_type = "MOM"
    timeframe = "1h"

    step(f"Generating template: {strategy_type}/{timeframe}/structure_{structure.id}")
    console.print(f"    Structure: entry_long={structure.entry_long}, entry_short={structure.entry_short}, "
                  f"TP={structure.take_profit}, exit={structure.exit_indicator}, time_exit={structure.time_exit}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("Calling AI...", total=None)
        template = generator.generate_template(strategy_type, timeframe, structure)

    if not template:
        error("Template generation failed!")
        return None, []

    success(f"Template created: {template.name}")
    console.print(f"    Parameters: {list(template.parameters_schema.keys())}")

    # Count variations
    from src.generator.parametric_generator import ParametricGenerator
    param_gen = ParametricGenerator()
    variation_count = param_gen.count_variations(template)
    console.print(f"    Possible variations: {variation_count}")

    # 1.2 Generate parametric variations (limit to 2 for testing)
    step("Generating parametric variations (max 2 for test)...")
    variations = param_gen.generate_variations(template, max_variations=2)

    valid_count = sum(1 for v in variations if v.validation_passed)
    success(f"Generated {len(variations)} variations, {valid_count} valid")

    # 1.3 Save template to DB
    step("Saving template to database...")
    with get_session() as session:
        session.add(template)
        session.flush()
        template_id = template.id
    success(f"Template saved with ID: {template_id}")

    # 1.4 Save strategies to DB
    step("Saving strategies to database...")
    saved_strategies = []
    with get_session() as session:
        for var in variations:
            if var.validation_passed:
                strategy = Strategy(
                    name=var.strategy_id,
                    strategy_type=var.strategy_type,
                    timeframe=var.timeframe,
                    code=var.code,
                    parameters=var.parameters,
                    status='GENERATED',  # Enum requires uppercase
                    template_id=template_id
                )
                session.add(strategy)
                saved_strategies.append(strategy)
        session.flush()
        # Get IDs
        strategy_ids = [s.id for s in saved_strategies]

    success(f"Saved {len(strategy_ids)} strategies to DB")

    return template, strategy_ids


def test_validator(strategy_ids: list) -> list:
    """
    Phase 2: Validate strategy code
    """
    phase_header(2, "VALIDATOR")

    from src.validator.syntax_validator import SyntaxValidator
    from src.validator.lookahead_detector import LookaheadDetector

    validator = SyntaxValidator()
    lookahead = LookaheadDetector()

    valid_ids = []

    with get_session() as session:
        for sid in strategy_ids:
            strategy = session.query(Strategy).filter_by(id=sid).first()
            if not strategy:
                continue

            step(f"Validating {strategy.name}...")

            # Syntax check
            syntax_result = validator.validate(strategy.code)
            if not syntax_result.passed:
                error(f"Syntax errors: {syntax_result.errors}")
                strategy.status = 'FAILED'
                strategy.error_message = str(syntax_result.errors)
                continue

            # Lookahead check
            lookahead_result = lookahead.validate(strategy.code)
            if not lookahead_result.passed:
                error(f"Lookahead bias: {lookahead_result.violations}")
                strategy.status = 'FAILED'
                strategy.error_message = str(lookahead_result.violations)
                continue

            strategy.status = 'VALIDATED'
            valid_ids.append(sid)
            success(f"{strategy.name} passed validation")

    console.print(f"\n  [bold]Validation results:[/bold] {len(valid_ids)}/{len(strategy_ids)} passed")
    return valid_ids


def instantiate_strategy(code: str, strategy_name: str):
    """
    Dynamically instantiate a strategy from code string

    Args:
        code: Python code defining the strategy class
        strategy_name: Name of the strategy class

    Returns:
        StrategyCore instance or None
    """
    import importlib.util
    import tempfile
    import os

    # Write code to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        # Load module from temp file
        spec = importlib.util.spec_from_file_location("temp_strategy", temp_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the strategy class (all prefixes)
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and (
                name.startswith('Strategy_') or
                name.startswith('PatStrat_') or
                name.startswith('PGnStrat_') or
                name.startswith('PGgStrat_') or
                name.startswith('UngStrat_') or
                name.startswith('UggStrat_') or
                name.startswith('PtaStrat_') or
                name.startswith('AIFStrat_') or
                name.startswith('AIAStrat_')
            ):
                return obj()

        return None
    except Exception as e:
        console.print(f"    [red]Failed to instantiate: {e}[/red]")
        return None
    finally:
        os.unlink(temp_path)


def test_backtester(strategy_ids: list) -> list:
    """
    Phase 3: Backtest strategies
    """
    phase_header(3, "BACKTESTER")

    if not strategy_ids:
        error("No strategies to backtest!")
        return []

    config = load_config()

    step("Initializing backtester...")
    from src.backtester.backtest_engine import BacktestEngine
    from src.backtester.data_loader import BinanceDataLoader
    from datetime import timedelta

    backtester = BacktestEngine(config)
    data_loader = BinanceDataLoader()
    success("Backtester ready")

    # Get a coin to test with
    step("Selecting test coin...")
    with get_session() as session:
        from src.database.models import Coin
        coin = session.query(Coin).filter_by(is_active=True).first()
        if not coin:
            error("No active coins!")
            return []
        test_symbol = coin.symbol
    success(f"Using {test_symbol} for backtest")

    backtested_ids = []

    with get_session() as session:
        for sid in strategy_ids:
            strategy_db = session.query(Strategy).filter_by(id=sid).first()
            if not strategy_db:
                continue

            step(f"Backtesting {strategy_db.name} on {test_symbol}...")

            try:
                # Instantiate strategy from code
                strategy_instance = instantiate_strategy(
                    strategy_db.code,
                    strategy_db.name
                )

                if not strategy_instance:
                    error("Failed to instantiate strategy")
                    strategy_db.status = 'FAILED'
                    strategy_db.error_message = 'Failed to instantiate'
                    continue

                # Load data (no dates = use all available cached data)
                data = data_loader.load_ohlcv(
                    symbol=test_symbol,
                    timeframe=strategy_db.timeframe
                )

                if data is None or len(data) < 100:
                    error(f"Not enough data for {test_symbol}")
                    strategy_db.status = 'FAILED'
                    strategy_db.error_message = 'Insufficient data'
                    continue

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                    transient=True
                ) as progress:
                    task = progress.add_task("Running backtest...", total=None)

                    # backtest() now requires Dict[str, pd.DataFrame]
                    result = backtester.backtest(
                        strategy=strategy_instance,
                        data={test_symbol: data},
                        max_positions=4
                    )

                if result and result.get('total_trades', 0) > 0:
                    # Save result
                    from datetime import timedelta
                    now = datetime.now()
                    backtest = BacktestResult(
                        strategy_id=strategy_db.id,
                        lookback_days=60,
                        initial_capital=10000,
                        start_date=result.get('start_date') or (now - timedelta(days=60)),
                        end_date=result.get('end_date') or now,
                        total_trades=result.get('total_trades', 0),
                        win_rate=result.get('win_rate', 0),
                        sharpe_ratio=result.get('sharpe_ratio', 0),
                        max_drawdown=result.get('max_drawdown', 0),
                        total_return_pct=result.get('total_return', 0),
                        expectancy=result.get('expectancy', 0),
                        final_equity=result.get('final_equity', 10000),
                        timeframe_tested=strategy_db.timeframe,
                        symbols_tested=[test_symbol]
                    )
                    session.add(backtest)

                    strategy_db.status = 'TESTED'
                    backtested_ids.append(sid)

                    success(f"{strategy_db.name}: {result.get('total_trades')} trades, "
                           f"WR={result.get('win_rate', 0):.1%}, "
                           f"Sharpe={result.get('sharpe_ratio', 0):.2f}")
                else:
                    console.print(f"    [yellow]No trades generated[/yellow]")
                    strategy_db.status = 'TESTED'
                    strategy_db.error_message = 'No trades generated'

            except Exception as e:
                error(f"Backtest failed: {e}")
                strategy_db.status = 'FAILED'
                strategy_db.error_message = str(e)

    console.print(f"\n  [bold]Backtest results:[/bold] {len(backtested_ids)}/{len(strategy_ids)} completed with trades")
    return backtested_ids


def test_classifier(strategy_ids: list):
    """
    Phase 4: Score and classify strategies
    """
    phase_header(4, "CLASSIFIER")

    if not strategy_ids:
        error("No strategies to classify!")
        return

    config = load_config()._raw_config

    step("Loading backtest results...")

    # Create results table
    table = Table(title="Strategy Scores")
    table.add_column("Strategy", style="cyan")
    table.add_column("Trades", justify="right")
    table.add_column("Win Rate", justify="right")
    table.add_column("Sharpe", justify="right")
    table.add_column("Max DD", justify="right")
    table.add_column("Score", justify="right", style="green")

    with get_session() as session:
        for sid in strategy_ids:
            strategy = session.query(Strategy).filter_by(id=sid).first()
            if not strategy:
                continue

            # Get best backtest result
            result = session.query(BacktestResult)\
                .filter_by(strategy_id=sid)\
                .order_by(BacktestResult.sharpe_ratio.desc())\
                .first()

            if not result:
                continue

            # Calculate composite score
            # Weights from config
            weights = config.get('classification', {}).get('score_weights', {})
            edge_w = weights.get('edge', 0.4)
            sharpe_w = weights.get('sharpe', 0.3)
            consistency_w = weights.get('consistency', 0.2)
            stability_w = weights.get('stability', 0.1)

            # Normalize metrics (0-1 scale)
            sharpe_norm = min(result.sharpe_ratio / 3.0, 1.0) if result.sharpe_ratio > 0 else 0
            wr_norm = result.win_rate if result.win_rate else 0
            dd_norm = 1 - min(abs(result.max_drawdown) / 0.3, 1.0) if result.max_drawdown else 0.5

            # Composite score
            score = (
                sharpe_w * sharpe_norm +
                consistency_w * wr_norm +
                stability_w * dd_norm +
                edge_w * (result.expectancy / 0.05 if result.expectancy else 0)
            )
            score = min(score, 1.0)  # Cap at 1.0

            # Update strategy status
            strategy.status = 'SELECTED'  # Mark as classified/selected

            table.add_row(
                strategy.name,
                str(result.total_trades),
                f"{result.win_rate:.1%}" if result.win_rate else "N/A",
                f"{result.sharpe_ratio:.2f}" if result.sharpe_ratio else "N/A",
                f"{result.max_drawdown:.1%}" if result.max_drawdown else "N/A",
                f"{score:.3f}"
            )

    console.print()
    console.print(table)


def show_final_summary():
    """Show final database state"""
    console.print()
    console.print(Panel("[bold]FINAL SUMMARY[/bold]", style="green", width=60))

    with get_session() as session:
        from sqlalchemy import func

        # Templates
        templates = session.query(StrategyTemplate).count()
        console.print(f"  Templates in DB: {templates}")

        # Strategies by status
        status_counts = session.query(
            Strategy.status,
            func.count(Strategy.id)
        ).group_by(Strategy.status).all()

        console.print(f"  Strategies by status:")
        for status, count in status_counts:
            console.print(f"    - {status}: {count}")

        # Backtest results
        backtests = session.query(BacktestResult).count()
        console.print(f"  Backtest results: {backtests}")

        # Best backtest result
        best = session.query(BacktestResult)\
            .order_by(BacktestResult.sharpe_ratio.desc())\
            .first()

        if best:
            strategy = session.query(Strategy).filter_by(id=best.strategy_id).first()
            console.print(f"\n  [green]Best result:[/green]")
            console.print(f"    Strategy: {strategy.name if strategy else 'N/A'}")
            console.print(f"    Sharpe: {best.sharpe_ratio:.2f}")
            console.print(f"    Win Rate: {best.win_rate:.1%}")


def main():
    console.print(Panel(
        "[bold cyan]SINGLE STRATEGY LIFECYCLE TEST[/bold cyan]\n"
        "Generator → Validator → Backtester → Classifier",
        width=60
    ))

    start_time = time.time()

    try:
        # Phase 1: Generator
        template, strategy_ids = test_generator()
        if not strategy_ids:
            error("Generator failed - aborting test")
            return 1

        # Phase 2: Validator
        valid_ids = test_validator(strategy_ids)
        if not valid_ids:
            error("All strategies failed validation - aborting test")
            return 1

        # Phase 3: Backtester
        backtested_ids = test_backtester(valid_ids)

        # Phase 4: Classifier
        test_classifier(backtested_ids if backtested_ids else valid_ids)

        # Final summary
        show_final_summary()

        elapsed = time.time() - start_time
        console.print()
        console.print(f"[green]Test completed in {elapsed:.1f}s[/green]")
        return 0

    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
        return 1
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
