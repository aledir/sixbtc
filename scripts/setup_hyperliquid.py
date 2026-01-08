#!/usr/bin/env python3
"""
Hyperliquid Setup Script for SixBTC

Initial setup for Hyperliquid integration:
1. Verifies connection to Hyperliquid
2. Lists/validates existing subaccounts
3. Creates missing subaccounts (if needed)
4. Creates agent wallets for each subaccount
5. Saves credentials to database
6. (Optional) Executes initial funding

Usage:
    python scripts/setup_hyperliquid.py [OPTIONS]

Options:
    --dry-run       Simulate without executing (show what would happen)
    --fund          Execute initial funding after setup
    --skip-validation  Skip naming validation (dangerous)
    --count N       Override subaccount count (default: from config)

Requirements:
    - HL_MASTER_ADDRESS and HL_MASTER_PRIVATE_KEY in .env
    - Database connection configured
    - config/config.yaml with hyperliquid section

Examples:
    # First run - dry run to see what will happen
    python scripts/setup_hyperliquid.py --dry-run

    # Execute setup
    python scripts/setup_hyperliquid.py

    # Execute setup with initial funding
    python scripts/setup_hyperliquid.py --fund
"""

import argparse
import os
import sys
from datetime import datetime, UTC

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.config import load_config
from src.database.connection import get_session
from src.database.models import Credential
from src.utils.logger import get_logger, setup_logging


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Setup Hyperliquid subaccounts and agent wallets for SixBTC"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate without executing'
    )
    parser.add_argument(
        '--fund',
        action='store_true',
        help='Execute initial funding after setup'
    )
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip naming validation (dangerous)'
    )
    parser.add_argument(
        '--count',
        type=int,
        help='Override subaccount count (default: from config)'
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging(log_file='logs/setup_hyperliquid.log', log_level='INFO')
    logger = get_logger(__name__)

    logger.info("=" * 60)
    logger.info("SixBTC Hyperliquid Setup")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("[DRY RUN MODE - No changes will be made]")

    # Load config
    try:
        config = load_config()
        raw_config = config._raw_config
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    # Check required environment variables
    master_address = os.environ.get('HL_MASTER_ADDRESS')
    master_key = os.environ.get('HL_MASTER_PRIVATE_KEY')

    if not master_address or not master_key:
        logger.error(
            "Missing required environment variables!\n"
            "Please set HL_MASTER_ADDRESS and HL_MASTER_PRIVATE_KEY in .env"
        )
        sys.exit(1)

    logger.info(f"Master address: {master_address[:10]}...{master_address[-4:]}")

    # Get target count
    target_count = args.count
    if target_count is None:
        target_count = raw_config.get('hyperliquid', {}).get('subaccounts', {}).get('count', 10)

    logger.info(f"Target subaccount count: {target_count}")

    # Import managers
    try:
        from src.subaccount.manager import SubaccountManager, NamingMismatchError
        from src.credentials.agent_manager import AgentManager
        from src.funds.manager import FundManager
    except ImportError as e:
        logger.error(f"Failed to import managers: {e}")
        sys.exit(1)

    # =========================================================================
    # PHASE 1: Verify Connection
    # =========================================================================
    logger.info("")
    logger.info("Phase 1: Verifying Hyperliquid connection...")

    try:
        subaccount_mgr = SubaccountManager(raw_config)
        logger.info("Connection verified - SubaccountManager initialized")
    except Exception as e:
        logger.error(f"Failed to connect to Hyperliquid: {e}")
        sys.exit(1)

    # =========================================================================
    # PHASE 2: List/Validate Subaccounts
    # =========================================================================
    logger.info("")
    logger.info("Phase 2: Checking existing subaccounts...")

    try:
        # Show ALL subaccounts from Hyperliquid for display
        all_existing = subaccount_mgr.list_subaccounts(include_all=True)
        logger.info(f"Found {len(all_existing)} existing subaccounts:")

        for i, sub in enumerate(all_existing, 1):
            addr_display = f"{sub['address'][:10]}...{sub['address'][-4:]}"
            managed = " (managed)" if i <= target_count else ""
            logger.info(f"  {i}. {sub['name']} ({addr_display}){managed}")

        # Get managed subaccounts only (up to target_count)
        existing = subaccount_mgr.list_subaccounts()  # Default: managed only

        if all_existing and not args.skip_validation:
            logger.info("Validating naming pattern...")
            try:
                subaccount_mgr.validate_naming(all_existing, target_count)
                logger.info("Naming validation passed")
            except NamingMismatchError as e:
                logger.error(str(e))
                logger.error(
                    "Use --skip-validation to bypass (dangerous) or fix the naming mismatch"
                )
                sys.exit(1)
        elif args.skip_validation:
            logger.warning("Naming validation SKIPPED (--skip-validation flag)")

    except Exception as e:
        logger.error(f"Failed to list subaccounts: {e}")
        sys.exit(1)

    # =========================================================================
    # PHASE 3: Create Missing Subaccounts
    # =========================================================================
    logger.info("")
    logger.info("Phase 3: Creating missing subaccounts...")

    if len(existing) >= target_count:
        logger.info(f"All {target_count} subaccounts already exist")
    else:
        needed = target_count - len(existing)
        logger.info(f"Need to create {needed} subaccounts")

        if args.dry_run:
            for i in range(len(existing) + 1, target_count + 1):
                name = subaccount_mgr.naming_pattern.format(i)
                logger.info(f"  [DRY RUN] Would create: {name}")
        else:
            try:
                existing = subaccount_mgr.ensure_subaccounts(target_count)
                logger.info(f"Subaccounts created. Total: {len(existing)}")
            except Exception as e:
                logger.error(f"Failed to create subaccounts: {e}")
                sys.exit(1)

    # =========================================================================
    # PHASE 4: Create Agent Wallets
    # =========================================================================
    logger.info("")
    logger.info("Phase 4: Creating agent wallets...")

    try:
        agent_mgr = AgentManager(raw_config)
    except Exception as e:
        logger.error(f"Failed to initialize AgentManager: {e}")
        sys.exit(1)

    # Check existing credentials
    credentials_created = 0
    credentials_existing = 0

    for i, sub in enumerate(existing, 1):
        existing_cred = agent_mgr.get_active_credential(i)

        if existing_cred:
            logger.info(
                f"  {sub['name']}: Active credential exists "
                f"(expires: {existing_cred.expires_at.date()})"
            )
            credentials_existing += 1
            continue

        # Need to create credential
        if args.dry_run:
            logger.info(f"  {sub['name']}: [DRY RUN] Would create agent wallet")
        else:
            try:
                cred = agent_mgr.create_agent(
                    target_type='subaccount',
                    target_address=sub['address'],
                    subaccount_id=i,
                    subaccount_name=sub['name']
                )
                logger.info(
                    f"  {sub['name']}: Agent wallet created "
                    f"(expires: {cred.expires_at.date()})"
                )
                credentials_created += 1
            except Exception as e:
                logger.error(f"  {sub['name']}: Failed to create agent wallet: {e}")

    logger.info(
        f"Agent wallets: {credentials_created} created, {credentials_existing} existing"
    )

    # =========================================================================
    # PHASE 5: Initial Funding (Optional)
    # =========================================================================
    if args.fund:
        logger.info("")
        logger.info("Phase 5: Initial funding...")

        try:
            fund_mgr = FundManager(raw_config)
            balances = fund_mgr.get_all_balances()

            logger.info(f"Master balance: ${balances['master']:.2f}")

            for sub_id, sub_info in balances['subaccounts'].items():
                logger.info(
                    f"  {sub_info['name']}: ${sub_info['balance']:.2f} ({sub_info['status']})"
                )

            if args.dry_run:
                logger.info("[DRY RUN] Would execute fund check (no transfers)")
            else:
                result = fund_mgr.check_all_subaccounts()
                logger.info(
                    f"Funding complete: topped_up={result['topped_up']}, "
                    f"partial={result['partial_topup']}, skipped={result['skipped']}"
                )

                for alert in result.get('alerts', []):
                    logger.warning(f"  Alert [{alert['level']}]: {alert['message']}")

        except Exception as e:
            logger.error(f"Funding failed: {e}")
    else:
        logger.info("")
        logger.info("Phase 5: Funding skipped (use --fund to enable)")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("Setup Complete!")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("")
        logger.info("This was a DRY RUN. No changes were made.")
        logger.info("Run without --dry-run to execute the setup.")
    else:
        # Verify credentials in DB
        with get_session() as session:
            active_creds = session.query(Credential).filter(
                Credential.is_active == True,
                Credential.expires_at > datetime.now(UTC)
            ).count()

        logger.info("")
        logger.info(f"Active credentials in database: {active_creds}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Verify credentials: SELECT * FROM credentials WHERE is_active = true;")
        logger.info("  2. Start executor: python -m src.executor.main_continuous")
        logger.info("  3. Monitor logs: tail -f logs/executor.log")

        if not args.fund:
            logger.info("")
            logger.info(
                "NOTE: Subaccounts may need funding before trading. "
                "Run with --fund or use FundManager manually."
            )


if __name__ == '__main__':
    main()
