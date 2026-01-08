#!/usr/bin/env python3
"""
Test script for HyperliquidClient multi-subaccount implementation.

Run with:
    python scripts/test_hyperliquid_client.py [--level N]

Levels:
    1: Read-only tests (no credentials needed, safe)
    2: Dry-run tests (mock orders, no real execution)
    3: Database credential tests (checks stored credentials)
    4: Balance tests (reads real balances from subaccounts)
    5: Micro-trade test (LIVE - places $10 order, requires confirmation)
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.loader import load_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def test_level_1_readonly():
    """Level 1: Read-only API tests (no credentials needed)"""
    print("\n" + "=" * 60)
    print("LEVEL 1: READ-ONLY API TESTS")
    print("=" * 60)

    from src.executor.hyperliquid_client import HyperliquidClient

    # Initialize in dry_run mode
    client = HyperliquidClient(dry_run=True)

    results = {
        "health_check": False,
        "asset_metadata": False,
        "current_prices": False,
        "btc_price": False,
    }

    # Test 1: Health check
    print("\n[1/4] Testing health_check()...")
    try:
        health = client.health_check()
        print(f"  Status: {health['status']}")
        print(f"  Dry-run: {health['dry_run']}")
        print(f"  Subaccounts configured: {health['subaccount_count']}")
        results["health_check"] = health["status"] == "healthy"
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 2: Asset metadata
    print("\n[2/4] Testing asset metadata (sz_decimals, max_leverage)...")
    try:
        btc_decimals = client.get_sz_decimals("BTC")
        btc_leverage = client.get_max_leverage("BTC")
        print(f"  BTC: sz_decimals={btc_decimals}, max_leverage={btc_leverage}x")

        eth_decimals = client.get_sz_decimals("ETH")
        eth_leverage = client.get_max_leverage("ETH")
        print(f"  ETH: sz_decimals={eth_decimals}, max_leverage={eth_leverage}x")

        results["asset_metadata"] = btc_decimals > 0 and btc_leverage > 0
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 3: Get all prices
    print("\n[3/4] Testing get_current_prices()...")
    try:
        prices = client.get_current_prices()
        print(f"  Retrieved prices for {len(prices)} assets")
        # Show top 5
        top_5 = list(prices.items())[:5]
        for symbol, price in top_5:
            print(f"  {symbol}: ${price:,.2f}")
        results["current_prices"] = len(prices) > 0
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 4: Get specific price
    print("\n[4/4] Testing get_current_price('BTC')...")
    try:
        btc_price = client.get_current_price("BTC")
        print(f"  BTC price: ${btc_price:,.2f}")
        results["btc_price"] = btc_price > 0
    except Exception as e:
        print(f"  ERROR: {e}")

    # Summary
    print("\n" + "-" * 60)
    passed = sum(results.values())
    total = len(results)
    print(f"LEVEL 1 RESULTS: {passed}/{total} tests passed")
    for test, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {test}")

    return all(results.values())


def test_level_2_dryrun():
    """Level 2: Dry-run order tests"""
    print("\n" + "=" * 60)
    print("LEVEL 2: DRY-RUN ORDER TESTS")
    print("=" * 60)

    from src.executor.hyperliquid_client import HyperliquidClient, OrderStatus

    client = HyperliquidClient(dry_run=True)

    results = {
        "place_long": False,
        "place_short": False,
        "place_with_sl_tp": False,
        "trigger_order": False,
    }

    # Test 1: Place long order
    print("\n[1/4] Testing place_market_order(long)...")
    try:
        order = client.place_market_order(
            subaccount_id=1,
            symbol="BTC",
            side="long",
            size=0.001
        )
        print(f"  Order ID: {order.order_id}")
        print(f"  Status: {order.status}")
        print(f"  Entry price: ${order.entry_price:,.2f}")
        results["place_long"] = (
            order.order_id.startswith("dry_run_") and
            order.status == OrderStatus.FILLED
        )
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 2: Place short order
    print("\n[2/4] Testing place_market_order(short)...")
    try:
        order = client.place_market_order(
            subaccount_id=2,  # Different subaccount
            symbol="ETH",
            side="short",
            size=0.01
        )
        print(f"  Order ID: {order.order_id}")
        print(f"  Status: {order.status}")
        results["place_short"] = order.status == OrderStatus.FILLED
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 3: Order with SL/TP
    print("\n[3/4] Testing place_order_with_sl_tp()...")
    try:
        result = client.place_order_with_sl_tp(
            subaccount_id=1,
            symbol="BTC",
            side="long",
            size=0.001,
            stop_loss=90000.0,
            take_profit=110000.0
        )
        print(f"  Status: {result['status']}")
        print(f"  Entry: {result['entry']}")
        print(f"  SL: {result['stop_loss']}")
        print(f"  TP: {result['take_profit']}")
        results["place_with_sl_tp"] = result["status"] == "ok"
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 4: Trigger order (SL)
    print("\n[4/4] Testing place_trigger_order(sl)...")
    try:
        result = client.place_trigger_order(
            subaccount_id=1,
            symbol="BTC",
            side="sell",
            size=0.001,
            trigger_price=90000.0,
            order_type="sl"
        )
        print(f"  Status: {result['status']}")
        print(f"  Trigger price: ${result['trigger_price']:,.2f}")
        results["trigger_order"] = result is not None
    except Exception as e:
        print(f"  ERROR: {e}")

    # Summary
    print("\n" + "-" * 60)
    passed = sum(results.values())
    total = len(results)
    print(f"LEVEL 2 RESULTS: {passed}/{total} tests passed")
    for test, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {test}")

    return all(results.values())


def test_level_3_credentials():
    """Level 3: Database credential tests"""
    print("\n" + "=" * 60)
    print("LEVEL 3: DATABASE CREDENTIAL TESTS")
    print("=" * 60)

    from datetime import datetime, UTC
    from sqlalchemy import text
    from src.database.connection import get_session
    from src.database.models import Credential

    results = {
        "db_connection": False,
        "credentials_found": False,
        "credentials_valid": False,
    }

    # Test 1: Database connection
    print("\n[1/3] Testing database connection...")
    try:
        with get_session() as session:
            # Simple query to test connection
            session.execute(text("SELECT 1"))
        print("  Database connection OK")
        results["db_connection"] = True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    # Test 2: Query credentials
    print("\n[2/3] Querying subaccount credentials...")
    try:
        with get_session() as session:
            credentials = session.query(Credential).filter(
                Credential.is_active == True,
                Credential.target_type == 'subaccount'
            ).all()

        print(f"  Found {len(credentials)} active credentials")
        results["credentials_found"] = len(credentials) > 0

        if credentials:
            for cred in credentials:
                days_left = (cred.expires_at - datetime.now(UTC)).days
                addr_display = f"{cred.target_address[:6]}...{cred.target_address[-4:]}"
                print(f"  Subaccount {cred.subaccount_id}: {addr_display} (expires in {days_left} days)")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 3: Validate credentials not expired
    print("\n[3/3] Validating credential expiration...")
    try:
        with get_session() as session:
            valid_credentials = session.query(Credential).filter(
                Credential.is_active == True,
                Credential.target_type == 'subaccount',
                Credential.expires_at > datetime.now(UTC)
            ).all()

        print(f"  Valid (non-expired) credentials: {len(valid_credentials)}")
        results["credentials_valid"] = len(valid_credentials) > 0

        if not valid_credentials:
            print("  WARNING: No valid credentials found!")
            print("  Run: python scripts/setup_hyperliquid.py")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Summary
    print("\n" + "-" * 60)
    passed = sum(results.values())
    total = len(results)
    print(f"LEVEL 3 RESULTS: {passed}/{total} tests passed")
    for test, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {test}")

    return all(results.values())


def test_level_4_balances():
    """Level 4: Read real balances from subaccounts"""
    print("\n" + "=" * 60)
    print("LEVEL 4: REAL BALANCE TESTS (READ-ONLY)")
    print("=" * 60)

    from src.executor.hyperliquid_client import HyperliquidClient

    # IMPORTANT: Still dry_run=True, but credentials allow real balance reads
    client = HyperliquidClient(dry_run=True)

    results = {
        "client_init": False,
        "balance_read": False,
        "positions_read": False,
    }

    # Test 1: Client initialization with credentials
    print("\n[1/3] Initializing client with credentials...")
    try:
        configured_subaccounts = list(client._subaccount_credentials.keys())
        print(f"  Configured subaccounts: {configured_subaccounts}")
        results["client_init"] = len(configured_subaccounts) > 0
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    if not results["client_init"]:
        print("  No credentials found - run scripts/setup_hyperliquid.py first")
        return False

    # Test 2: Read balances
    print("\n[2/3] Reading balances from configured subaccounts...")
    try:
        total_balance = 0
        for subaccount_id in configured_subaccounts:
            try:
                balance = client.get_account_balance(subaccount_id)
                total_balance += balance
                print(f"  Subaccount {subaccount_id}: ${balance:,.2f}")
            except Exception as e:
                print(f"  Subaccount {subaccount_id}: ERROR - {e}")

        print(f"  TOTAL: ${total_balance:,.2f}")
        results["balance_read"] = True
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 3: Read positions
    print("\n[3/3] Reading positions from configured subaccounts...")
    try:
        for subaccount_id in configured_subaccounts:
            try:
                positions = client.get_positions(subaccount_id)
                if positions:
                    print(f"  Subaccount {subaccount_id}: {len(positions)} positions")
                    for pos in positions:
                        print(f"    {pos.symbol}: {pos.side} {pos.size} @ ${pos.entry_price:,.2f}")
                else:
                    print(f"  Subaccount {subaccount_id}: no open positions")
            except Exception as e:
                print(f"  Subaccount {subaccount_id}: ERROR - {e}")
        results["positions_read"] = True
    except Exception as e:
        print(f"  ERROR: {e}")

    # Summary
    print("\n" + "-" * 60)
    passed = sum(results.values())
    total = len(results)
    print(f"LEVEL 4 RESULTS: {passed}/{total} tests passed")
    for test, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {test}")

    return all(results.values())


def test_level_5_microtrade():
    """Level 5: LIVE micro-trade test (requires confirmation)"""
    print("\n" + "=" * 60)
    print("LEVEL 5: LIVE MICRO-TRADE TEST")
    print("=" * 60)
    print("\nWARNING: This will place a REAL order on Hyperliquid!")
    print("A small BTC long position (~$15 notional) will be opened and closed.")
    print()

    confirm = input("Type 'YES' to proceed: ")
    if confirm != "YES":
        print("Aborted.")
        return False

    from src.executor.hyperliquid_client import HyperliquidClient

    # Initialize in LIVE mode (dry_run=False)
    try:
        client = HyperliquidClient(dry_run=False)
    except ValueError as e:
        print(f"ERROR: Cannot initialize live client: {e}")
        print("Ensure HL_MASTER_ADDRESS is set and credentials exist in database.")
        return False

    results = {
        "place_order": False,
        "verify_position": False,
        "close_position": False,
    }

    # Use first available subaccount
    subaccount_id = list(client._subaccount_credentials.keys())[0]
    print(f"\nUsing subaccount {subaccount_id}")

    # Get current BTC price
    btc_price = client.get_current_price("BTC")
    print(f"Current BTC price: ${btc_price:,.2f}")

    # Calculate micro position (min notional is $10)
    # Target ~$15 notional
    size = round(15 / btc_price, 5)
    print(f"Position size: {size} BTC (~${size * btc_price:.2f} notional)")

    # Test 1: Place order
    print("\n[1/3] Placing LIVE market order...")
    try:
        order = client.place_market_order(
            subaccount_id=subaccount_id,
            symbol="BTC",
            side="long",
            size=size
        )
        if order:
            print(f"  Order ID: {order.order_id}")
            print(f"  Fill price: ${order.entry_price:,.2f}")
            print(f"  Size filled: {order.size}")
            results["place_order"] = True
        else:
            print("  Order failed!")
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    # Test 2: Verify position
    print("\n[2/3] Verifying position...")
    import time
    time.sleep(2)  # Wait for exchange state update

    try:
        position = client.get_position(subaccount_id, "BTC")
        if position:
            print(f"  Position found: {position.side} {position.size} BTC")
            print(f"  Entry: ${position.entry_price:,.2f}")
            print(f"  Unrealized PnL: ${position.unrealized_pnl:,.2f}")
            results["verify_position"] = True
        else:
            print("  No position found (may have been filled and closed)")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 3: Close position
    print("\n[3/3] Closing position...")
    try:
        success = client.close_position(subaccount_id, "BTC", reason="Test close")
        if success:
            print("  Position closed successfully")
            results["close_position"] = True
        else:
            print("  Close failed (position may not exist)")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Summary
    print("\n" + "-" * 60)
    passed = sum(results.values())
    total = len(results)
    print(f"LEVEL 5 RESULTS: {passed}/{total} tests passed")
    for test, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {test}")

    return all(results.values())


def main():
    parser = argparse.ArgumentParser(description="Test HyperliquidClient implementation")
    parser.add_argument(
        "--level", "-l",
        type=int,
        default=2,
        choices=[1, 2, 3, 4, 5],
        help="Test level (1=readonly, 2=dryrun, 3=credentials, 4=balances, 5=live)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("HYPERLIQUID CLIENT TEST SUITE")
    print("=" * 60)
    print(f"Running tests up to level {args.level}")

    all_passed = True

    # Level 1: Read-only
    if args.level >= 1:
        if not test_level_1_readonly():
            all_passed = False
            if args.level > 1:
                print("\nLevel 1 failed - stopping tests")
                return 1

    # Level 2: Dry-run
    if args.level >= 2:
        if not test_level_2_dryrun():
            all_passed = False
            if args.level > 2:
                print("\nLevel 2 failed - stopping tests")
                return 1

    # Level 3: Credentials
    if args.level >= 3:
        if not test_level_3_credentials():
            all_passed = False
            if args.level > 3:
                print("\nLevel 3 failed - stopping tests")
                return 1

    # Level 4: Balances
    if args.level >= 4:
        if not test_level_4_balances():
            all_passed = False
            if args.level > 4:
                print("\nLevel 4 failed - stopping tests")
                return 1

    # Level 5: Live micro-trade
    if args.level >= 5:
        if not test_level_5_microtrade():
            all_passed = False

    # Final summary
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED")
        return 0
    else:
        print("SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
