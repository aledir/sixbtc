#!/usr/bin/env python3
"""
Test completo del ciclo di vita di una strategia

Testa:
1. Generazione strategia (da template)
2. Salvataggio nel database
3. Backtesting con VectorBT
4. Classificazione e scoring
5. Deployment simulato su subaccount
6. Esecuzione segnali in dry-run

Eseguire con:
    python scripts/test_lifecycle.py
"""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from datetime import datetime
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def test_lifecycle():
    """Test the complete strategy lifecycle"""

    console.print(Panel.fit(
        "[bold cyan]SixBTC - Test Ciclo di Vita Strategia[/bold cyan]\n"
        "Testa generazione -> backtest -> classificazione -> deployment -> esecuzione",
        border_style="cyan"
    ))

    results = {}

    # =========================================================================
    # PHASE 1: Generate a test strategy
    # =========================================================================
    console.print("\n[bold]FASE 1: Generazione Strategia con AI[/bold]")

    try:
        from src.generator.strategy_builder import StrategyBuilder
        from src.config import load_config
        import random

        # Load full config (includes 'ai' section for Claude CLI)
        config = load_config()

        # Initialize builder with full config (enables AI)
        builder = StrategyBuilder(config._raw_config)

        # Random strategy type for diversity
        strategy_types = ['MOM', 'REV', 'TRN', 'BRE']
        strategy_type = random.choice(strategy_types)

        # Random timeframe for diversity
        timeframes = ['15m', '1h', '4h']
        timeframe = random.choice(timeframes)

        console.print(f"  Generating [cyan]{strategy_type}[/cyan] strategy for [cyan]{timeframe}[/cyan]...")

        # Generate unique strategy using AI (Claude CLI)
        generated = builder.generate_strategy(
            strategy_type=strategy_type,
            timeframe=timeframe,
            use_patterns=False  # No pattern-discovery for test
        )

        code = generated.code
        strategy_id = f"Strategy_{strategy_type}_{generated.strategy_id}"

        results['generation'] = {
            'status': 'OK' if generated.validation_passed else 'FAILED',
            'strategy_id': strategy_id,
            'valid': generated.validation_passed,
            'ai_provider': generated.ai_provider,
            'errors': generated.validation_errors
        }

        console.print(f"  Strategy ID: [cyan]{strategy_id}[/cyan]")
        console.print(f"  AI Provider: [cyan]{generated.ai_provider}[/cyan]")
        console.print(f"  Validation: [{'green' if generated.validation_passed else 'red'}]{generated.validation_passed}[/]")
        if generated.validation_errors:
            for err in generated.validation_errors[:3]:
                console.print(f"    [yellow]{err}[/yellow]")

    except Exception as e:
        results['generation'] = {'status': 'ERROR', 'error': str(e)}
        console.print(f"  [red]Errore: {e}[/red]")
        import traceback
        traceback.print_exc()

    # =========================================================================
    # PHASE 2: Save to database
    # =========================================================================
    console.print("\n[bold]FASE 2: Salvataggio nel Database[/bold]")

    try:
        from src.database import get_session, Strategy

        with get_session() as session:
            # Create strategy record
            strategy_record = Strategy(
                name=strategy_id,
                code=code,
                strategy_type='MOM',
                timeframe='15m',
                status='GENERATED'
            )

            session.add(strategy_record)
            session.commit()

            # Verify saved
            saved = session.query(Strategy).filter(Strategy.name == strategy_id).first()

            results['database'] = {
                'status': 'OK' if saved else 'FAILED',
                'strategy_id': strategy_id
            }

            console.print(f"  Salvato nel database: [green]OK[/green]")
            console.print(f"  Status: {saved.status if saved else 'N/A'}")

    except Exception as e:
        results['database'] = {'status': 'ERROR', 'error': str(e)}
        console.print(f"  [red]Errore: {e}[/red]")

    # =========================================================================
    # PHASE 3: Backtest with VectorBT
    # =========================================================================
    console.print("\n[bold]FASE 3: Backtesting con VectorBT[/bold]")

    try:
        from src.backtester.backtest_engine import VectorBTEngine

        # Create sample OHLCV data with realistic price action
        # that will trigger RSI signals (trends + reversals)
        np.random.seed(42)
        dates = pd.date_range(start='2024-01-01', periods=1000, freq='15min')

        # Generate price with trending periods that create RSI extremes
        close = [50000.0]
        for i in range(999):
            # Create alternating trend/reversal patterns
            cycle_pos = i % 100  # 100-bar cycles
            if cycle_pos < 30:
                # Strong uptrend (RSI will go high)
                change = abs(np.random.randn()) * 150 + 50
            elif cycle_pos < 50:
                # Correction down (RSI will drop)
                change = -abs(np.random.randn()) * 200 - 100
            elif cycle_pos < 80:
                # Strong downtrend (RSI will go low)
                change = -abs(np.random.randn()) * 150 - 50
            else:
                # Recovery up (RSI will rise)
                change = abs(np.random.randn()) * 200 + 100
            close.append(close[-1] + change)

        close = np.array(close)

        data = pd.DataFrame({
            'timestamp': dates,
            'open': close - np.random.rand(1000) * 50,
            'high': close + np.random.rand(1000) * 100 + 50,
            'low': close - np.random.rand(1000) * 100 - 50,
            'close': close,
            'volume': 1000 + np.abs(np.random.randn(1000)) * 100
        })

        # Load strategy class from code
        exec_globals = {}
        exec(code, exec_globals)

        # Find strategy class
        strategy_class = None
        for name, obj in exec_globals.items():
            if name.startswith('Strategy_') and isinstance(obj, type):
                strategy_class = obj
                break

        if strategy_class:
            strategy_instance = strategy_class()

            # Run backtest
            engine = VectorBTEngine()
            metrics = engine.run_backtest(
                strategy=strategy_instance,
                data=data,
                initial_capital=10000
            )

            results['backtest'] = {
                'status': 'OK',
                'metrics': metrics
            }

            console.print(f"  Total Trades: {metrics.get('total_trades', 0)}")
            console.print(f"  Win Rate: {metrics.get('win_rate', 0):.1%}")
            console.print(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
            console.print(f"  Max Drawdown: {metrics.get('max_drawdown', 0):.1%}")
        else:
            results['backtest'] = {'status': 'FAILED', 'error': 'Strategy class not found'}
            console.print(f"  [red]Classe strategia non trovata[/red]")

    except Exception as e:
        results['backtest'] = {'status': 'ERROR', 'error': str(e)}
        console.print(f"  [red]Errore: {e}[/red]")

    # =========================================================================
    # PHASE 4: Classification and scoring
    # =========================================================================
    console.print("\n[bold]FASE 4: Classificazione e Scoring[/bold]")

    try:
        from src.classifier.scorer import StrategyScorer

        scorer = StrategyScorer(config._raw_config if hasattr(config, '_raw_config') else {
            'classification': {
                'scoring': {
                    'edge_weight': 0.4,
                    'sharpe_weight': 0.3,
                    'stability_weight': 0.3,
                    'min_sharpe': 0.5,
                    'min_win_rate': 0.45,
                    'max_drawdown': 0.40,
                    'min_trades': 10
                }
            }
        })

        # Create strategy data for scoring
        strategy_data = {
            'id': strategy_id,
            'name': strategy_id,
            'type': 'MOM',
            'timeframe': '15m',
            'symbol': 'BTC',
            'backtest_results': results.get('backtest', {}).get('metrics', {}),
            'backtest_sharpe': results.get('backtest', {}).get('metrics', {}).get('sharpe_ratio', 0),
            'backtest_win_rate': results.get('backtest', {}).get('metrics', {}).get('win_rate', 0),
            'shuffle_p_value': 0.01
        }

        # Score strategy
        ranked = scorer.rank_strategies([strategy_data])

        if ranked:
            score = ranked[0].get('score', 0)
            results['classification'] = {
                'status': 'OK',
                'score': score
            }
            console.print(f"  Score: [cyan]{score:.2f}[/cyan]")
        else:
            results['classification'] = {'status': 'FAILED', 'error': 'No ranking'}
            console.print(f"  [yellow]Nessun ranking disponibile[/yellow]")

    except Exception as e:
        results['classification'] = {'status': 'ERROR', 'error': str(e)}
        console.print(f"  [red]Errore: {e}[/red]")

    # =========================================================================
    # PHASE 5: Simulated deployment
    # =========================================================================
    console.print("\n[bold]FASE 5: Deployment Simulato[/bold]")

    try:
        from src.executor.subaccount_manager import SubaccountManager

        manager = SubaccountManager({
            'dry_run': True,
            'hyperliquid': {
                'subaccounts': {
                    'total': 10,
                    'test_mode': {'enabled': True, 'count': 3, 'capital_per_account': 100}
                }
            }
        })

        # Assign strategy to subaccount
        success = manager.assign_strategy(
            subaccount_id=1,
            strategy_id=strategy_id
        )

        results['deployment'] = {
            'status': 'OK' if success else 'FAILED',
            'subaccount': 1
        }

        console.print(f"  Subaccount: 1")
        console.print(f"  Assegnazione: [{'green' if success else 'red'}]{'OK' if success else 'FAILED'}[/]")

    except Exception as e:
        results['deployment'] = {'status': 'ERROR', 'error': str(e)}
        console.print(f"  [red]Errore: {e}[/red]")

    # =========================================================================
    # PHASE 6: Signal execution (dry-run)
    # =========================================================================
    console.print("\n[bold]FASE 6: Esecuzione Segnali (dry-run)[/bold]")

    try:
        from unittest.mock import patch, MagicMock
        from src.executor.hyperliquid_client import HyperliquidClient

        # Mock the Info API to avoid real network calls
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [
                {'name': 'BTC', 'szDecimals': 4, 'maxLeverage': 50}
            ]}
            mock_info_instance.all_mids.return_value = {'BTC': '50000.0'}
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(dry_run=True)

            # Generate a signal
            if strategy_class:
                signal = strategy_instance.generate_signal(data)

                if signal:
                    # Place dry-run order
                    order = client.place_market_order(
                        symbol='BTC',
                        side=signal.direction,
                        size=0.01,
                        stop_loss=49000.0,
                        take_profit=51000.0
                    )

                    results['execution'] = {
                        'status': 'OK',
                        'signal': signal.direction,
                        'order_id': order.order_id if order else None
                    }

                    console.print(f"  Segnale: [cyan]{signal.direction}[/cyan]")
                    console.print(f"  Order ID: [green]{order.order_id if order else 'N/A'}[/green]")
                else:
                    results['execution'] = {'status': 'OK', 'signal': 'None'}
                    console.print(f"  Segnale: [yellow]Nessuno (condizioni non soddisfatte)[/yellow]")
            else:
                results['execution'] = {'status': 'SKIPPED'}
                console.print(f"  [yellow]Skipped (no strategy class)[/yellow]")

    except Exception as e:
        results['execution'] = {'status': 'ERROR', 'error': str(e)}
        console.print(f"  [red]Errore: {e}[/red]")

    # =========================================================================
    # CLEANUP: Remove test strategy from database
    # =========================================================================
    console.print("\n[bold]CLEANUP[/bold]")

    try:
        from src.database import get_session, Strategy

        with get_session() as session:
            session.query(Strategy).filter(Strategy.name == strategy_id).delete()
            session.commit()
            console.print(f"  Strategia di test rimossa dal database: [green]OK[/green]")

    except Exception as e:
        console.print(f"  [yellow]Cleanup: {e}[/yellow]")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    console.print("\n" + "=" * 60)
    console.print("[bold]RIEPILOGO TEST CICLO DI VITA[/bold]")
    console.print("=" * 60)

    table = Table()
    table.add_column("Fase", style="cyan")
    table.add_column("Status")
    table.add_column("Dettagli")

    phases = [
        ('Generazione', 'generation'),
        ('Database', 'database'),
        ('Backtest', 'backtest'),
        ('Classificazione', 'classification'),
        ('Deployment', 'deployment'),
        ('Esecuzione', 'execution')
    ]

    all_ok = True
    for phase_name, phase_key in phases:
        result = results.get(phase_key, {})
        status = result.get('status', 'N/A')

        if status == 'OK':
            status_str = "[green]OK[/green]"
        elif status == 'SKIPPED':
            status_str = "[yellow]SKIPPED[/yellow]"
        elif status == 'ERROR':
            status_str = "[red]ERROR[/red]"
            all_ok = False
        else:
            status_str = f"[red]{status}[/red]"
            all_ok = False

        details = ""
        if 'error' in result:
            details = result['error'][:40]
        elif 'metrics' in result:
            m = result['metrics']
            details = f"Sharpe={m.get('sharpe_ratio', 0):.2f}, WR={m.get('win_rate', 0):.1%}"
        elif 'score' in result:
            details = f"Score={result['score']:.2f}"
        elif 'signal' in result:
            details = f"Signal={result['signal']}"

        table.add_row(phase_name, status_str, details)

    console.print(table)

    if all_ok:
        console.print("\n[bold green]TUTTI I TEST PASSATI[/bold green]")
    else:
        console.print("\n[bold red]ALCUNI TEST FALLITI[/bold red]")

    return all_ok


if __name__ == '__main__':
    success = test_lifecycle()
    sys.exit(0 if success else 1)
