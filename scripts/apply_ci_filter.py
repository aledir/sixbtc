#!/usr/bin/env python3
"""
Apply CI (Confidence Interval) filter to existing ACTIVE pool.

This script retroactively applies the new CI filter to all ACTIVE strategies,
marking those that fail as FAILED with reason 'ci_filter_update'.

Run with --dry-run to see what would change without making modifications.

Usage:
    python scripts/apply_ci_filter.py --dry-run    # Preview changes
    python scripts/apply_ci_filter.py              # Apply changes
"""

import argparse
import math
import sys
from collections import defaultdict
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/home/bitwolf/sixbtc')

from src.config import load_config
from src.database import get_session
from src.database.models import Strategy, BacktestResult


def calculate_ci(win_rate: float, n_trades: int) -> float:
    """
    Calculate 95% Confidence Interval for win rate.

    CI = 1.96 * sqrt(WR * (1-WR) / N)

    Returns 1.0 (100%) if inputs are invalid.
    """
    if n_trades <= 0 or win_rate <= 0 or win_rate >= 1:
        return 1.0
    return 1.96 * math.sqrt(win_rate * (1 - win_rate) / n_trades)


def main():
    parser = argparse.ArgumentParser(description='Apply CI filter to ACTIVE pool')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying database')
    args = parser.parse_args()

    # Load config
    config = load_config()

    # Get CI thresholds from config
    max_ci_is = config.get_required('backtesting.max_ci.in_sample')
    max_ci_oos = config.get_required('backtesting.max_ci.out_of_sample')

    # Get min_trades per timeframe (indexed by tf position)
    min_trades_is = config.get_required('backtesting.min_trades.in_sample')
    min_trades_oos = config.get_required('backtesting.min_trades.out_of_sample')

    # Timeframe to index mapping
    tf_to_idx = {'15m': 0, '30m': 1, '1h': 2, '2h': 3}

    print(f"CI Filter Application Script")
    print(f"=" * 60)
    print(f"Config thresholds:")
    print(f"  max_ci_is:  {max_ci_is:.1%}")
    print(f"  max_ci_oos: {max_ci_oos:.1%}")
    print(f"  min_trades_is:  {min_trades_is}")
    print(f"  min_trades_oos: {min_trades_oos}")
    print(f"")
    print(f"Mode: {'DRY RUN (no changes)' if args.dry_run else 'LIVE (will modify DB)'}")
    print(f"=" * 60)
    print()

    with get_session() as session:
        # Get all ACTIVE strategies
        active_strategies = session.query(Strategy).filter(
            Strategy.status == 'ACTIVE'
        ).all()

        print(f"Found {len(active_strategies)} ACTIVE strategies")
        print()

        # Track results by timeframe
        stats = defaultdict(lambda: {'total': 0, 'pass': 0, 'fail_is_ci': 0, 'fail_oos_ci': 0, 'fail_both': 0, 'no_data': 0})
        failed_strategies = []

        for strategy in active_strategies:
            tf = strategy.timeframe
            tf_idx = tf_to_idx.get(tf, 3)  # Default to 2h thresholds if unknown

            stats[tf]['total'] += 1

            # Get backtest results
            is_result = session.query(BacktestResult).filter(
                BacktestResult.strategy_id == strategy.id,
                BacktestResult.period_type == 'in_sample'
            ).first()

            oos_result = session.query(BacktestResult).filter(
                BacktestResult.strategy_id == strategy.id,
                BacktestResult.period_type == 'out_of_sample'
            ).first()

            # Check if we have data
            if not is_result:
                stats[tf]['no_data'] += 1
                continue

            # Get metrics
            is_trades = is_result.total_trades or 0
            is_win_rate = is_result.win_rate or 0

            oos_trades = oos_result.total_trades if oos_result else 0
            oos_win_rate = oos_result.win_rate if oos_result else 0

            # Calculate CI
            is_ci = calculate_ci(is_win_rate, is_trades)
            oos_ci = calculate_ci(oos_win_rate, oos_trades) if oos_trades > 0 else 1.0

            # Check thresholds
            fail_is_ci = is_ci > max_ci_is
            fail_oos_ci = oos_ci > max_ci_oos if oos_trades > 0 else False

            if fail_is_ci or fail_oos_ci:
                reason_parts = []
                if fail_is_ci:
                    reason_parts.append(f"IS_CI={is_ci:.1%}>{max_ci_is:.0%}")
                    stats[tf]['fail_is_ci'] += 1
                if fail_oos_ci:
                    reason_parts.append(f"OOS_CI={oos_ci:.1%}>{max_ci_oos:.0%}")
                    stats[tf]['fail_oos_ci'] += 1
                if fail_is_ci and fail_oos_ci:
                    stats[tf]['fail_both'] += 1

                reason = f"ci_filter_update: {', '.join(reason_parts)}"
                failed_strategies.append({
                    'strategy': strategy,
                    'tf': tf,
                    'is_trades': is_trades,
                    'is_wr': is_win_rate,
                    'is_ci': is_ci,
                    'oos_trades': oos_trades,
                    'oos_wr': oos_win_rate,
                    'oos_ci': oos_ci,
                    'reason': reason,
                })
            else:
                stats[tf]['pass'] += 1

        # Print summary by timeframe
        print("Summary by Timeframe:")
        print("-" * 80)
        print(f"{'TF':<6} {'Total':<8} {'Pass':<8} {'Fail IS':<10} {'Fail OOS':<10} {'Fail Both':<10} {'No Data':<8}")
        print("-" * 80)

        total_all = 0
        fail_all = 0

        for tf in ['15m', '30m', '1h', '2h']:
            s = stats[tf]
            total_all += s['total']
            fail_count = s['fail_is_ci'] + s['fail_oos_ci'] - s['fail_both']  # Avoid double counting
            fail_all += fail_count
            print(f"{tf:<6} {s['total']:<8} {s['pass']:<8} {s['fail_is_ci']:<10} {s['fail_oos_ci']:<10} {s['fail_both']:<10} {s['no_data']:<8}")

        print("-" * 80)
        print(f"{'TOTAL':<6} {total_all:<8} {total_all - fail_all:<8} {fail_all:<10}")
        print()

        # Print failed strategies details
        if failed_strategies:
            print(f"\nStrategies that will be marked FAILED ({len(failed_strategies)}):")
            print("-" * 100)
            print(f"{'Name':<35} {'TF':<5} {'IS_trades':<10} {'IS_WR':<8} {'IS_CI':<8} {'OOS_trades':<11} {'OOS_WR':<8} {'OOS_CI':<8}")
            print("-" * 100)

            for item in sorted(failed_strategies, key=lambda x: (x['tf'], -x['is_ci'])):
                s = item['strategy']
                print(f"{s.name:<35} {item['tf']:<5} {item['is_trades']:<10} {item['is_wr']:.1%}    {item['is_ci']:.1%}    {item['oos_trades']:<11} {item['oos_wr']:.1%}    {item['oos_ci']:.1%}")
            print()

        # Apply changes if not dry run
        if not args.dry_run and failed_strategies:
            print(f"\nApplying changes...")
            for item in failed_strategies:
                strategy = item['strategy']
                strategy.status = 'FAILED'
                strategy.retired_at = datetime.utcnow()
                strategy.retired_reason = 'ci_filter_update'

            session.commit()
            print(f"Marked {len(failed_strategies)} strategies as FAILED")
        elif args.dry_run and failed_strategies:
            print(f"\n[DRY RUN] Would mark {len(failed_strategies)} strategies as FAILED")
            print("Run without --dry-run to apply changes")
        else:
            print("\nNo strategies to update")


if __name__ == '__main__':
    main()
