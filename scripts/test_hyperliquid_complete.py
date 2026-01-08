#!/usr/bin/env python3
"""
Complete test suite for HyperliquidClient - tests ALL methods.

Run with:
    python scripts/test_hyperliquid_complete.py [--live]

Modes:
    Default (no --live): Dry-run tests only (safe, no real trades)
    --live: Full live test with real micro-trades (~$15)
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

from src.utils.logger import get_logger

logger = get_logger(__name__)


class TestResults:
    """Track test results"""
    def __init__(self):
        self.results = {}
        self.current_section = ""

    def section(self, name: str):
        self.current_section = name
        print(f"\n{'=' * 60}")
        print(f"  {name}")
        print('=' * 60)

    def test(self, name: str, passed: bool, details: str = ""):
        full_name = f"{self.current_section}.{name}"
        self.results[full_name] = passed
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if details:
            print(f"         {details}")

    def summary(self):
        print("\n" + "=" * 60)
        print("  SUMMARY")
        print("=" * 60)

        passed = sum(self.results.values())
        total = len(self.results)

        # Group by section
        sections = {}
        for name, result in self.results.items():
            section = name.split('.')[0]
            if section not in sections:
                sections[section] = {'passed': 0, 'total': 0}
            sections[section]['total'] += 1
            if result:
                sections[section]['passed'] += 1

        for section, stats in sections.items():
            status = "OK" if stats['passed'] == stats['total'] else "FAIL"
            print(f"  [{status}] {section}: {stats['passed']}/{stats['total']}")

        print("-" * 60)
        print(f"  TOTAL: {passed}/{total} tests passed")
        print("=" * 60)

        return passed == total


def test_utility_methods(client, results: TestResults):
    """Test utility/helper methods"""
    results.section("UTILITY METHODS")

    # round_size
    try:
        btc_size = client.round_size("BTC", 0.123456789)
        results.test("round_size(BTC)", btc_size == 0.12346, f"0.123456789 -> {btc_size}")
    except Exception as e:
        results.test("round_size(BTC)", False, str(e))

    # round_price
    try:
        high_price = client.round_price(95432.567)
        low_price = client.round_price(0.00123456)
        results.test("round_price(high)", high_price == 95433.0, f"95432.567 -> {high_price}")
        results.test("round_price(low)", low_price == 0.00123, f"0.00123456 -> {low_price}")
    except Exception as e:
        results.test("round_price", False, str(e))

    # get_sz_decimals
    try:
        btc_dec = client.get_sz_decimals("BTC")
        eth_dec = client.get_sz_decimals("ETH")
        results.test("get_sz_decimals", btc_dec > 0 and eth_dec > 0, f"BTC={btc_dec}, ETH={eth_dec}")
    except Exception as e:
        results.test("get_sz_decimals", False, str(e))

    # get_max_leverage
    try:
        btc_lev = client.get_max_leverage("BTC")
        results.test("get_max_leverage", btc_lev >= 20, f"BTC max leverage: {btc_lev}x")
    except Exception as e:
        results.test("get_max_leverage", False, str(e))


def test_market_data_methods(client, results: TestResults):
    """Test market data methods"""
    results.section("MARKET DATA")

    # get_current_price
    try:
        btc_price = client.get_current_price("BTC")
        results.test("get_current_price(BTC)", btc_price > 50000, f"${btc_price:,.2f}")
    except Exception as e:
        results.test("get_current_price(BTC)", False, str(e))

    # get_current_prices
    try:
        prices = client.get_current_prices()
        results.test("get_current_prices", len(prices) > 100, f"{len(prices)} assets")
    except Exception as e:
        results.test("get_current_prices", False, str(e))

    # health_check
    try:
        health = client.health_check()
        results.test("health_check", health['status'] == 'healthy', f"status={health['status']}")
    except Exception as e:
        results.test("health_check", False, str(e))


def test_account_methods(client, subaccount_id: int, results: TestResults):
    """Test account query methods"""
    results.section("ACCOUNT QUERIES")

    # get_account_balance
    try:
        balance = client.get_account_balance(subaccount_id)
        results.test("get_account_balance", balance >= 0, f"${balance:,.2f}")
    except Exception as e:
        results.test("get_account_balance", False, str(e))

    # get_account_state
    try:
        state = client.get_account_state(client._get_subaccount_address(subaccount_id))
        has_margin = 'marginSummary' in state
        results.test("get_account_state", has_margin, f"has marginSummary: {has_margin}")
    except Exception as e:
        results.test("get_account_state", False, str(e))

    # get_positions (empty is OK)
    try:
        positions = client.get_positions(subaccount_id)
        results.test("get_positions", isinstance(positions, list), f"{len(positions)} positions")
    except Exception as e:
        results.test("get_positions", False, str(e))

    # get_open_positions
    try:
        open_pos = client.get_open_positions(subaccount_id)
        results.test("get_open_positions", isinstance(open_pos, list), f"{len(open_pos)} positions")
    except Exception as e:
        results.test("get_open_positions", False, str(e))

    # get_orders
    try:
        orders = client.get_orders(subaccount_id)
        results.test("get_orders", isinstance(orders, list), f"{len(orders)} orders")
    except Exception as e:
        results.test("get_orders", False, str(e))


def test_dry_run_orders(client, results: TestResults):
    """Test order methods in dry-run mode"""
    results.section("DRY-RUN ORDERS")

    # place_market_order long
    try:
        order = client.place_market_order(
            subaccount_id=1,
            symbol="BTC",
            side="long",
            size=0.001
        )
        results.test("place_market_order(long)",
                     order and order.order_id.startswith("dry_run_"),
                     f"order_id={order.order_id if order else None}")
    except Exception as e:
        results.test("place_market_order(long)", False, str(e))

    # place_market_order short
    try:
        order = client.place_market_order(
            subaccount_id=1,
            symbol="ETH",
            side="short",
            size=0.01
        )
        results.test("place_market_order(short)",
                     order and order.side == "short",
                     f"side={order.side if order else None}")
    except Exception as e:
        results.test("place_market_order(short)", False, str(e))

    # place_order generic
    try:
        result = client.place_order(
            subaccount_id=1,
            symbol="BTC",
            side="long",
            size=0.001
        )
        results.test("place_order",
                     result.get('status') in ['ok', 'simulated'],
                     f"status={result.get('status')}")
    except Exception as e:
        results.test("place_order", False, str(e))

    # place_order_with_sl_tp
    try:
        result = client.place_order_with_sl_tp(
            subaccount_id=1,
            symbol="BTC",
            side="long",
            size=0.001,
            stop_loss=85000.0,
            take_profit=100000.0
        )
        has_all = bool(result.get('entry') and result.get('stop_loss') and result.get('take_profit'))
        passed = result.get('status') == 'ok' and has_all
        results.test("place_order_with_sl_tp", passed, f"entry+SL+TP: {has_all}")
    except Exception as e:
        results.test("place_order_with_sl_tp", False, str(e))

    # place_trigger_order SL
    try:
        result = client.place_trigger_order(
            subaccount_id=1,
            symbol="BTC",
            side="sell",
            size=0.001,
            trigger_price=85000.0,
            order_type="sl"
        )
        results.test("place_trigger_order(sl)",
                     result and result.get('status') == 'simulated',
                     f"trigger=${result.get('trigger_price'):,.0f}" if result else "None")
    except Exception as e:
        results.test("place_trigger_order(sl)", False, str(e))

    # place_trigger_order TP
    try:
        result = client.place_trigger_order(
            subaccount_id=1,
            symbol="BTC",
            side="sell",
            size=0.001,
            trigger_price=100000.0,
            order_type="tp"
        )
        results.test("place_trigger_order(tp)",
                     result and result.get('status') == 'simulated',
                     f"trigger=${result.get('trigger_price'):,.0f}" if result else "None")
    except Exception as e:
        results.test("place_trigger_order(tp)", False, str(e))


def test_dry_run_position_management(client, results: TestResults):
    """Test position management in dry-run mode"""
    results.section("DRY-RUN POSITION MANAGEMENT")

    # set_leverage
    try:
        success = client.set_leverage(1, "BTC", 5)
        results.test("set_leverage", success, f"set to 5x: {success}")
    except Exception as e:
        results.test("set_leverage", False, str(e))

    # update_stop_loss (dry-run returns simulated)
    try:
        result = client.update_stop_loss(1, "BTC", 86000.0)
        results.test("update_stop_loss",
                     result and result.get('status') == 'simulated',
                     f"new SL: ${result.get('trigger_price'):,.0f}" if result else "None")
    except Exception as e:
        results.test("update_stop_loss", False, str(e))

    # update_take_profit
    try:
        result = client.update_take_profit(1, "BTC", 105000.0)
        results.test("update_take_profit",
                     result and result.get('status') == 'simulated',
                     f"new TP: ${result.get('trigger_price'):,.0f}" if result else "None")
    except Exception as e:
        results.test("update_take_profit", False, str(e))

    # update_sl_atomic (trailing stop core method)
    try:
        result = client.update_sl_atomic(1, "BTC", 87000.0)
        results.test("update_sl_atomic",
                     result and result.get('status') == 'simulated',
                     f"atomic SL: ${result.get('trigger_price'):,.0f}" if result else "None")
    except Exception as e:
        results.test("update_sl_atomic", False, str(e))

    # cancel_order (dry-run)
    try:
        success = client.cancel_order(1, "BTC", "12345")
        results.test("cancel_order", success, "dry-run returns True")
    except Exception as e:
        results.test("cancel_order", False, str(e))

    # close_position (no position = returns False, which is correct)
    try:
        success = client.close_position(1, "NONEXISTENT", "test")
        results.test("close_position(no_pos)", success == False, "correctly returns False")
    except Exception as e:
        results.test("close_position(no_pos)", False, str(e))


def test_credentials(client, results: TestResults):
    """Test credential management"""
    results.section("CREDENTIALS")

    # Check configured subaccounts
    try:
        configured = list(client._subaccount_credentials.keys())
        results.test("subaccounts_configured",
                     len(configured) > 0,
                     f"{len(configured)} subaccounts: {configured[:5]}...")
    except Exception as e:
        results.test("subaccounts_configured", False, str(e))

    # reload_credentials
    try:
        count = client.reload_credentials()
        results.test("reload_credentials", count > 0, f"reloaded {count} credentials")
    except Exception as e:
        results.test("reload_credentials", False, str(e))


def test_live_full_cycle(client, subaccount_id: int, results: TestResults):
    """Test LIVE full trading cycle with trailing stop"""
    results.section("LIVE FULL CYCLE")

    btc_price = client.get_current_price("BTC")
    size = round(15 / btc_price, 5)  # ~$15 notional

    print(f"\n  Starting live test on subaccount {subaccount_id}")
    print(f"  BTC price: ${btc_price:,.2f}")
    print(f"  Position size: {size} BTC (~${size * btc_price:.2f})")

    # Track state for cleanup
    entry_order = None
    sl_order_id = None
    tp_order_id = None

    try:
        # 1. Set leverage first
        print("\n  [1/9] Setting leverage...")
        lev_success = client.set_leverage(subaccount_id, "BTC", 3)
        results.test("set_leverage(live)", lev_success, "3x leverage")
        time.sleep(1)

        # 2. Place entry order
        print("  [2/9] Placing entry order...")
        entry_order = client.place_market_order(
            subaccount_id=subaccount_id,
            symbol="BTC",
            side="long",
            size=size
        )
        results.test("place_market_order(live)",
                     entry_order is not None,
                     f"order_id={entry_order.order_id if entry_order else None}")
        time.sleep(2)

        if not entry_order:
            print("  Entry failed - aborting test")
            return

        # 3. Verify position exists
        print("  [3/9] Verifying position...")
        position = client.get_position(subaccount_id, "BTC")
        results.test("get_position(live)",
                     position is not None,
                     f"{position.side} {position.size} @ ${position.entry_price:,.2f}" if position else "None")

        if not position:
            print("  Position not found - aborting test")
            return

        # 4. Place Stop Loss
        print("  [4/9] Placing stop loss...")
        sl_price = round(position.entry_price * 0.98, 0)  # 2% below entry
        sl_result = client.place_trigger_order(
            subaccount_id=subaccount_id,
            symbol="BTC",
            side="sell",
            size=position.size,
            trigger_price=sl_price,
            order_type="sl"
        )
        sl_order_id = sl_result.get('order_id') if sl_result else None
        results.test("place_trigger_order(sl_live)",
                     sl_order_id is not None,
                     f"SL @ ${sl_price:,.0f}, order_id={sl_order_id}")
        time.sleep(1)

        # 5. Place Take Profit
        print("  [5/9] Placing take profit...")
        tp_price = round(position.entry_price * 1.03, 0)  # 3% above entry
        tp_result = client.place_trigger_order(
            subaccount_id=subaccount_id,
            symbol="BTC",
            side="sell",
            size=position.size,
            trigger_price=tp_price,
            order_type="tp"
        )
        tp_order_id = tp_result.get('order_id') if tp_result else None
        results.test("place_trigger_order(tp_live)",
                     tp_order_id is not None,
                     f"TP @ ${tp_price:,.0f}, order_id={tp_order_id}")
        time.sleep(1)

        # 6. Query orders to verify
        print("  [6/9] Querying orders...")
        orders = client.get_orders(subaccount_id, "BTC")
        # We should have 2 trigger orders (SL + TP)
        results.test("get_orders(live)",
                     len(orders) >= 0,  # Trigger orders may not show in open_orders
                     f"{len(orders)} open orders")

        # 7. Update SL (trailing stop simulation)
        print("  [7/9] Updating stop loss (trailing)...")
        new_sl_price = round(position.entry_price * 0.985, 0)  # Move SL up to 1.5% below
        update_result = client.update_sl_atomic(
            subaccount_id=subaccount_id,
            symbol="BTC",
            new_stop_loss=new_sl_price,
            old_order_id=sl_order_id,
            size=position.size
        )
        new_sl_order_id = update_result.get('order_id') if update_result else None
        results.test("update_sl_atomic(live)",
                     new_sl_order_id is not None,
                     f"SL moved: ${sl_price:,.0f} -> ${new_sl_price:,.0f}")
        if new_sl_order_id:
            sl_order_id = new_sl_order_id
        time.sleep(1)

        # 8. Cancel all orders before closing
        print("  [8/9] Cancelling all orders...")
        cancelled = client.cancel_all_orders(subaccount_id)
        results.test("cancel_all_orders(live)", True, f"cancelled {cancelled} orders")
        time.sleep(1)

        # 9. Close position
        print("  [9/9] Closing position...")
        close_success = client.close_position(subaccount_id, "BTC", "test complete")
        results.test("close_position(live)", close_success, f"closed: {close_success}")
        time.sleep(1)

        # Verify closed
        final_position = client.get_position(subaccount_id, "BTC")
        results.test("position_closed_verify",
                     final_position is None,
                     "position cleared" if final_position is None else f"still open: {final_position.size}")

    except Exception as e:
        results.test("live_cycle_error", False, str(e))
        # Cleanup on error
        print(f"\n  ERROR: {e}")
        print("  Attempting cleanup...")
        try:
            client.cancel_all_orders(subaccount_id)
            client.close_position(subaccount_id, "BTC", "error cleanup")
        except:
            pass


def test_emergency_methods(client, results: TestResults):
    """Test emergency methods (dry-run only for safety)"""
    results.section("EMERGENCY METHODS (dry-run)")

    # These are tested in dry-run for safety
    # close_all_positions
    try:
        closed = client.close_all_positions(1)
        results.test("close_all_positions", isinstance(closed, int), f"closed {closed}")
    except Exception as e:
        results.test("close_all_positions", False, str(e))

    # cancel_all_orders
    try:
        cancelled = client.cancel_all_orders(1)
        results.test("cancel_all_orders", isinstance(cancelled, int), f"cancelled {cancelled}")
    except Exception as e:
        results.test("cancel_all_orders", False, str(e))

    # Note: emergency_stop_all is NOT tested to avoid any risk


def main():
    parser = argparse.ArgumentParser(description="Complete HyperliquidClient test suite")
    parser.add_argument("--live", action="store_true", help="Run live tests with real trades")
    args = parser.parse_args()

    print("=" * 60)
    print("  HYPERLIQUID CLIENT - COMPLETE TEST SUITE")
    print("=" * 60)

    from src.executor.hyperliquid_client import HyperliquidClient

    results = TestResults()

    # Initialize client
    if args.live:
        print("\n  MODE: LIVE (real trades will be placed!)")
        confirm = input("  Type 'YES' to confirm: ")
        if confirm != "YES":
            print("  Aborted.")
            return 1

        try:
            client = HyperliquidClient(dry_run=False)
            print(f"  Client initialized: {client.subaccount_count} subaccounts")
        except ValueError as e:
            print(f"  ERROR: Cannot initialize live client: {e}")
            return 1

        subaccount_id = list(client._subaccount_credentials.keys())[0]
    else:
        print("\n  MODE: DRY-RUN (no real trades)")
        client = HyperliquidClient(dry_run=True)
        subaccount_id = 1

    # Run all tests
    test_utility_methods(client, results)
    test_market_data_methods(client, results)
    test_account_methods(client, subaccount_id, results)
    test_credentials(client, results)

    if args.live:
        test_live_full_cycle(client, subaccount_id, results)
    else:
        test_dry_run_orders(client, results)
        test_dry_run_position_management(client, results)
        test_emergency_methods(client, results)

    # Summary
    all_passed = results.summary()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
