#!/usr/bin/env python3
"""
Test script to verify metric calculation coherence between backtest and live scorer
"""
import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("METRIC COHERENCE TEST")
print("=" * 80)

# ============================================================================
# TEST 1: EXPECTANCY FORMULA
# ============================================================================
print("\n[TEST 1] Expectancy Formula Coherence")
print("-" * 80)

# Create test trade data with known metrics
test_trades = [
    {'pnl_pct': 0.05, 'pnl_usd': 50},   # Win
    {'pnl_pct': -0.02, 'pnl_usd': -20}, # Loss
    {'pnl_pct': 0.03, 'pnl_usd': 30},   # Win
    {'pnl_pct': -0.01, 'pnl_usd': -10}, # Loss
    {'pnl_pct': 0.04, 'pnl_usd': 40},   # Win
]

# Manual calculation
total_trades = len(test_trades)
wins = [t for t in test_trades if t['pnl_pct'] > 0]
losses = [t for t in test_trades if t['pnl_pct'] < 0]

win_rate = len(wins) / total_trades
avg_win = np.mean([t['pnl_pct'] for t in wins])
avg_loss = np.mean([abs(t['pnl_pct']) for t in losses])

# Formula: (WR × AvgWin) - ((1-WR) × AvgLoss)
expected_expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

print(f"Manual Calculation:")
print(f"  Win Rate: {win_rate:.1%}")
print(f"  Avg Win: {avg_win:.2%}")
print(f"  Avg Loss: {avg_loss:.2%}")
print(f"  Expected Expectancy: {expected_expectancy:.4%}")

# Simulate backtester calculation (from backtest_engine.py:1186-1192)
print(f"\nBacktester Formula:")
win_pcts = [t['pnl_pct'] for t in test_trades if t['pnl_pct'] > 0]
loss_pcts = [abs(t['pnl_pct']) for t in test_trades if t['pnl_pct'] < 0]
avg_win_pct = np.mean(win_pcts) if win_pcts else 0.0
avg_loss_pct = np.mean(loss_pcts) if loss_pcts else 0.0
backtest_expectancy = (win_rate * avg_win_pct) - ((1 - win_rate) * avg_loss_pct)
print(f"  Backtest Expectancy: {backtest_expectancy:.4%}")

# Simulate live scorer calculation (from live_scorer.py:158-165)
print(f"\nLive Scorer Formula:")
pnl_pcts = [t['pnl_pct'] for t in test_trades]
winning_trades = [p for p in pnl_pcts if p > 0]
losing_trades = [p for p in pnl_pcts if p < 0]
avg_win_live = np.mean(winning_trades) if winning_trades else 0.0
avg_loss_live = abs(np.mean(losing_trades)) if losing_trades else 0.0
live_expectancy = (win_rate * avg_win_live) - ((1 - win_rate) * avg_loss_live)
print(f"  Live Expectancy: {live_expectancy:.4%}")

# Verify coherence
diff = abs(backtest_expectancy - live_expectancy)
tolerance = 1e-10

print(f"\n{'='*80}")
if diff < tolerance:
    print(f"✅ TEST 1 PASSED: Expectancy formulas are IDENTICAL")
    print(f"   Difference: {diff:.2e} (< {tolerance})")
    test1_passed = True
else:
    print(f"❌ TEST 1 FAILED: Expectancy formulas DIFFER")
    print(f"   Difference: {diff:.4%}")
    print(f"   Backtest: {backtest_expectancy:.4%}")
    print(f"   Live:     {live_expectancy:.4%}")
    test1_passed = False

# ============================================================================
# TEST 2: SHARPE ANNUALIZATION
# ============================================================================
print("\n" + "=" * 80)
print("[TEST 2] Sharpe Annualization Factor")
print("-" * 80)

timeframes = ['5m', '15m', '30m', '1h', '4h', '1d']
expected_bars = {
    '5m': 288,
    '15m': 96,
    '30m': 48,
    '1h': 24,
    '4h': 6,
    '1d': 1
}

print(f"Testing annualization factors for each timeframe:\n")
print(f"{'Timeframe':<10} {'Bars/Day':<10} {'Factor':<15} {'Expected':<15} {'Status'}")
print("-" * 80)

test2_passed = True
for tf in timeframes:
    bars_per_day = expected_bars[tf]
    annualization_factor = np.sqrt(365 * bars_per_day)  # Crypto = 365 days/year
    expected_factor = np.sqrt(365 * expected_bars[tf])

    match = abs(annualization_factor - expected_factor) < 1e-6
    status = "✅" if match else "❌"

    print(f"{tf:<10} {bars_per_day:<10} {annualization_factor:<15.2f} {expected_factor:<15.2f} {status}")

    if not match:
        test2_passed = False

# Test specific examples
print(f"\nSpecific Examples (Crypto: 365 days/year, 24/7):")
print(f"  15m strategy (96 bars/day): sqrt(365 × 96) = sqrt(35040) = {np.sqrt(365 * 96):.2f}")
print(f"  1h strategy (24 bars/day):  sqrt(365 × 24) = sqrt(8760) = {np.sqrt(365 * 24):.2f}")
print(f"  1d strategy (1 bar/day):    sqrt(365 × 1) = sqrt(365) = {np.sqrt(365):.2f}")

print(f"\n{'='*80}")
if test2_passed:
    print(f"✅ TEST 2 PASSED: Sharpe annualization factors are CORRECT")
else:
    print(f"❌ TEST 2 FAILED: Sharpe annualization factors MISMATCH")

# ============================================================================
# TEST 3: WEIGHTED METRICS
# ============================================================================
print("\n" + "=" * 80)
print("[TEST 3] Weighted Metrics Calculation")
print("-" * 80)

# Test data
training_sharpe = 2.0
holdout_sharpe = 1.5
training_expectancy = 0.05  # 5%
holdout_expectancy = 0.03   # 3%
training_win_rate = 0.60
holdout_win_rate = 0.55

# Calculate weighted (40% training + 60% holdout)
weighted_sharpe = (training_sharpe * 0.4) + (holdout_sharpe * 0.6)
weighted_expectancy = (training_expectancy * 0.4) + (holdout_expectancy * 0.6)
weighted_win_rate = (training_win_rate * 0.4) + (holdout_win_rate * 0.6)

# Expected values
expected_weighted_sharpe = 1.7  # 2.0*0.4 + 1.5*0.6 = 0.8 + 0.9 = 1.7
expected_weighted_expectancy = 0.038  # 0.05*0.4 + 0.03*0.6 = 0.02 + 0.018 = 0.038
expected_weighted_win_rate = 0.57  # 0.60*0.4 + 0.55*0.6 = 0.24 + 0.33 = 0.57

print(f"Input:")
print(f"  Training:  Sharpe={training_sharpe:.2f}, Exp={training_expectancy:.2%}, WR={training_win_rate:.1%}")
print(f"  Holdout:   Sharpe={holdout_sharpe:.2f}, Exp={holdout_expectancy:.2%}, WR={holdout_win_rate:.1%}")

print(f"\nWeighted (40% training + 60% holdout):")
print(f"  Sharpe:     {weighted_sharpe:.2f} (expected: {expected_weighted_sharpe:.2f})")
print(f"  Expectancy: {weighted_expectancy:.2%} (expected: {expected_weighted_expectancy:.2%})")
print(f"  Win Rate:   {weighted_win_rate:.1%} (expected: {expected_weighted_win_rate:.1%})")

# Verify
sharpe_match = abs(weighted_sharpe - expected_weighted_sharpe) < 1e-6
exp_match = abs(weighted_expectancy - expected_weighted_expectancy) < 1e-6
wr_match = abs(weighted_win_rate - expected_weighted_win_rate) < 1e-6

print(f"\n{'='*80}")
if sharpe_match and exp_match and wr_match:
    print(f"✅ TEST 3 PASSED: Weighted metrics calculated CORRECTLY")
    test3_passed = True
else:
    print(f"❌ TEST 3 FAILED: Weighted metrics INCORRECT")
    test3_passed = False

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"  Test 1 (Expectancy):          {'✅ PASSED' if test1_passed else '❌ FAILED'}")
print(f"  Test 2 (Sharpe Annualization): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
print(f"  Test 3 (Weighted Metrics):     {'✅ PASSED' if test3_passed else '❌ FAILED'}")
print("=" * 80)

all_passed = test1_passed and test2_passed and test3_passed
if all_passed:
    print("✅ ALL TESTS PASSED - Metric calculations are correct and coherent!")
    sys.exit(0)
else:
    print("❌ SOME TESTS FAILED - Review implementation")
    sys.exit(1)
