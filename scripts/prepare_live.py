#!/usr/bin/env python3
"""
Pre-Live Setup Script

Prepares sixbtc system for live trading by:
1. Updating config.yaml with capital/pool settings
2. Creating missing subaccounts in database
3. Verifying funding status
4. Checking pool size requirements
5. Clearing lingering emergency stops

Usage:
    python scripts/prepare_live.py              # Interactive mode
    python scripts/prepare_live.py --check      # Check-only (no changes)
    python scripts/prepare_live.py --force      # Skip confirmations
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, UTC

import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.loader import load_config
from src.database.connection import get_session
from src.database.models import Subaccount, Strategy, EmergencyStopState

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class PreLiveSetup:
    """Orchestrates pre-live setup steps."""

    def __init__(self, config_path: str = "config/prepare_live.yaml"):
        self.config_path = Path(config_path)
        self.main_config_path = Path("config/config.yaml")
        self.prepare_config = self._load_prepare_config()
        self.issues = []
        self.actions = []

    def _load_prepare_config(self) -> dict:
        """Load prepare_live.yaml configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path) as f:
            return yaml.safe_load(f)

    def _load_main_config(self) -> dict:
        """Load main config.yaml."""
        with open(self.main_config_path) as f:
            return yaml.safe_load(f)

    def _save_main_config(self, config: dict):
        """Save main config.yaml."""
        with open(self.main_config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    def check_all(self) -> bool:
        """
        Run all checks and return True if ready for live.

        Returns:
            True if all checks pass, False otherwise
        """
        self.issues = []
        self.actions = []

        logger.info("=" * 60)
        logger.info("PRE-LIVE SETUP CHECK")
        logger.info("=" * 60)

        # 1. Check config alignment
        self._check_config_alignment()

        # 2. Check subaccounts exist in DB
        self._check_subaccounts_exist()

        # 3. Check funding status
        self._check_funding_status()

        # 4. Check pool size
        self._check_pool_size()

        # 5. Check emergency stops
        self._check_emergency_stops()

        # Summary
        logger.info("")
        logger.info("=" * 60)
        if self.issues:
            logger.warning(f"ISSUES FOUND: {len(self.issues)}")
            for issue in self.issues:
                logger.warning(f"  - {issue}")
        else:
            logger.info("ALL CHECKS PASSED")

        if self.actions:
            logger.info("")
            logger.info(f"ACTIONS NEEDED: {len(self.actions)}")
            for action in self.actions:
                logger.info(f"  - {action}")

        logger.info("=" * 60)

        return len(self.issues) == 0

    def _check_config_alignment(self):
        """Check if config.yaml matches prepare_live settings."""
        logger.info("")
        logger.info("[1/5] Checking config alignment...")

        main_config = self._load_main_config()
        prep = self.prepare_config

        mismatches = []

        # Check subaccounts count
        current_subs = main_config.get('subaccounts', {}).get('count', 5)
        target_subs = prep['capital']['num_subaccounts']
        if current_subs != target_subs:
            mismatches.append(f"subaccounts.count: {current_subs} -> {target_subs}")

        # Check max_live_strategies
        current_max = main_config.get('rotator', {}).get('max_live_strategies', 5)
        target_max = prep['live']['max_live_strategies']
        if current_max != target_max:
            mismatches.append(f"rotator.max_live_strategies: {current_max} -> {target_max}")

        # Check pool size
        current_pool = main_config.get('active_pool', {}).get('max_size', 300)
        target_pool = prep['pool']['max_size']
        if current_pool != target_pool:
            mismatches.append(f"active_pool.max_size: {current_pool} -> {target_pool}")

        # Check min_pool_size (sbarramento)
        current_min = main_config.get('rotator', {}).get('min_pool_size', 100)
        target_min = prep['pool']['min_for_live']
        if current_min != target_min:
            mismatches.append(f"rotator.min_pool_size: {current_min} -> {target_min}")

        # Check dry_run
        current_dry = main_config.get('trading', {}).get('dry_run', True)
        target_dry = prep['live']['dry_run']
        if current_dry != target_dry:
            mismatches.append(f"trading.dry_run: {current_dry} -> {target_dry}")

        # Check fund settings
        current_topup = main_config.get('funds', {}).get('topup_target_usd', 100)
        target_topup = prep['capital']['capital_per_subaccount']
        if current_topup != target_topup:
            mismatches.append(f"funds.topup_target_usd: {current_topup} -> {target_topup}")

        current_min_op = main_config.get('funds', {}).get('min_operational_usd', 50)
        target_min_op = prep['capital']['min_operational']
        if current_min_op != target_min_op:
            mismatches.append(f"funds.min_operational_usd: {current_min_op} -> {target_min_op}")

        if mismatches:
            logger.warning(f"  Config mismatches: {len(mismatches)}")
            for m in mismatches:
                logger.warning(f"    {m}")
            self.actions.append(f"Update config.yaml ({len(mismatches)} changes)")
        else:
            logger.info("  Config aligned with prepare_live.yaml")

        self._config_mismatches = mismatches

    def _check_subaccounts_exist(self):
        """Check if required subaccounts exist in database."""
        logger.info("")
        logger.info("[2/5] Checking subaccounts in database...")

        target_count = self.prepare_config['capital']['num_subaccounts']

        with get_session() as session:
            existing = session.query(Subaccount).all()
            existing_ids = {sa.id for sa in existing}

        needed = set(range(1, target_count + 1))
        missing = needed - existing_ids

        if missing:
            logger.warning(f"  Missing subaccounts: {sorted(missing)}")
            self.actions.append(f"Create subaccounts: {sorted(missing)}")
        else:
            logger.info(f"  All {target_count} subaccounts exist")

        self._missing_subaccounts = sorted(missing)

    def _check_funding_status(self):
        """Check funding status of subaccounts."""
        logger.info("")
        logger.info("[3/5] Checking funding status...")

        target_count = self.prepare_config['capital']['num_subaccounts']
        min_operational = self.prepare_config['capital']['min_operational']

        funded = []
        underfunded = []
        unknown = []

        with get_session() as session:
            subaccounts = session.query(Subaccount).filter(
                Subaccount.id <= target_count
            ).all()

            # Extract data while in session
            subaccount_data = [(sa.id, sa.current_balance) for sa in subaccounts]
            existing_ids = {sa.id for sa in subaccounts}

        for sa_id, balance in subaccount_data:
            if balance is None:
                unknown.append(sa_id)
            elif balance >= min_operational:
                funded.append((sa_id, balance))
            else:
                underfunded.append((sa_id, balance))

        # Check for missing subaccounts too
        for i in range(1, target_count + 1):
            if i not in existing_ids:
                unknown.append(i)

        logger.info(f"  Funded (>= ${min_operational}): {len(funded)}")
        for sa_id, bal in funded:
            logger.info(f"    Sub {sa_id}: ${bal:.2f}")

        if underfunded:
            logger.warning(f"  Underfunded: {len(underfunded)}")
            for sa_id, bal in underfunded:
                logger.warning(f"    Sub {sa_id}: ${bal:.2f}")
            self.actions.append(f"Fund subaccounts: {[s[0] for s in underfunded]}")

        if unknown:
            logger.warning(f"  Unknown balance: {unknown}")
            self.actions.append(f"Check balance for subaccounts: {unknown}")

        if self.prepare_config['checks']['require_funded']:
            if underfunded or unknown:
                self.issues.append(f"Not all subaccounts are funded")

        self._funding_status = {
            'funded': funded,
            'underfunded': underfunded,
            'unknown': unknown
        }

    def _check_pool_size(self):
        """Check if ACTIVE pool meets minimum requirements."""
        logger.info("")
        logger.info("[4/5] Checking strategy pool...")

        min_for_live = self.prepare_config['pool']['min_for_live']

        with get_session() as session:
            active_count = session.query(Strategy).filter(
                Strategy.status == 'ACTIVE'
            ).count()

            live_count = session.query(Strategy).filter(
                Strategy.status == 'LIVE'
            ).count()

        total_ready = active_count + live_count

        logger.info(f"  ACTIVE strategies: {active_count}")
        logger.info(f"  LIVE strategies: {live_count}")
        logger.info(f"  Total ready: {total_ready}")
        logger.info(f"  Required minimum: {min_for_live}")

        if self.prepare_config['checks']['require_pool']:
            if total_ready < min_for_live:
                self.issues.append(
                    f"Pool too small: {total_ready} < {min_for_live} required"
                )
            else:
                logger.info(f"  Pool size OK")

        self._pool_status = {
            'active': active_count,
            'live': live_count,
            'total': total_ready,
            'required': min_for_live
        }

    def _check_emergency_stops(self):
        """Check for lingering emergency stops."""
        logger.info("")
        logger.info("[5/5] Checking emergency stops...")

        with get_session() as session:
            active_stops = session.query(EmergencyStopState).filter(
                EmergencyStopState.is_stopped == True
            ).all()

            # Extract data while in session
            stop_data = [
                (stop.scope, stop.scope_id, stop.stop_reason)
                for stop in active_stops
            ]

        if stop_data:
            logger.warning(f"  Active emergency stops: {len(stop_data)}")
            for scope, scope_id, reason in stop_data:
                logger.warning(f"    [{scope}:{scope_id}] {reason}")
            self.actions.append(f"Clear {len(stop_data)} emergency stops")
        else:
            logger.info("  No active emergency stops")

        self._active_stops = stop_data

    def apply_changes(self, force: bool = False) -> bool:
        """
        Apply all necessary changes.

        Args:
            force: Skip confirmation prompts

        Returns:
            True if changes applied successfully
        """
        if not self.actions:
            logger.info("No changes needed.")
            return True

        logger.info("")
        logger.info("=" * 60)
        logger.info("APPLYING CHANGES")
        logger.info("=" * 60)

        if not force:
            print(f"\nApply {len(self.actions)} changes? [y/N] ", end="")
            response = input().strip().lower()
            if response != 'y':
                logger.info("Aborted by user.")
                return False

        # 1. Update config.yaml
        if hasattr(self, '_config_mismatches') and self._config_mismatches:
            self._apply_config_changes()

        # 2. Create missing subaccounts
        if hasattr(self, '_missing_subaccounts') and self._missing_subaccounts:
            self._create_missing_subaccounts()

        # 3. Clear emergency stops
        if (hasattr(self, '_active_stops') and self._active_stops
                and self.prepare_config['checks']['clear_emergency_stops']):
            self._clear_emergency_stops()

        logger.info("")
        logger.info("Changes applied. Run check again to verify.")
        return True

    def _apply_config_changes(self):
        """Update config.yaml with prepare_live settings."""
        logger.info("")
        logger.info("Updating config.yaml...")

        main_config = self._load_main_config()
        prep = self.prepare_config

        # Ensure nested dicts exist
        if 'subaccounts' not in main_config:
            main_config['subaccounts'] = {}
        if 'rotator' not in main_config:
            main_config['rotator'] = {}
        if 'active_pool' not in main_config:
            main_config['active_pool'] = {}
        if 'trading' not in main_config:
            main_config['trading'] = {}
        if 'funds' not in main_config:
            main_config['funds'] = {}

        # Apply changes
        main_config['subaccounts']['count'] = prep['capital']['num_subaccounts']
        main_config['rotator']['max_live_strategies'] = prep['live']['max_live_strategies']
        main_config['rotator']['min_pool_size'] = prep['pool']['min_for_live']
        main_config['active_pool']['max_size'] = prep['pool']['max_size']
        main_config['trading']['dry_run'] = prep['live']['dry_run']
        main_config['funds']['topup_target_usd'] = prep['capital']['capital_per_subaccount']
        main_config['funds']['min_operational_usd'] = prep['capital']['min_operational']

        self._save_main_config(main_config)
        logger.info("  Config updated")

    def _create_missing_subaccounts(self):
        """Create missing subaccounts in database."""
        logger.info("")
        logger.info("Creating missing subaccounts...")

        capital = self.prepare_config['capital']['capital_per_subaccount']

        with get_session() as session:
            for sa_id in self._missing_subaccounts:
                sa = Subaccount(
                    id=sa_id,
                    status='INACTIVE',
                    allocated_capital=capital,
                    current_balance=None,  # Will be set when funded
                    peak_balance=None,
                    created_at=datetime.now(UTC)
                )
                session.add(sa)
                logger.info(f"  Created subaccount {sa_id}")
            session.commit()

    def _clear_emergency_stops(self):
        """Clear lingering emergency stops."""
        logger.info("")
        logger.info("Clearing emergency stops...")

        with get_session() as session:
            for scope, scope_id, _ in self._active_stops:
                state = session.query(EmergencyStopState).filter(
                    EmergencyStopState.scope == scope,
                    EmergencyStopState.scope_id == scope_id
                ).first()
                if state:
                    state.is_stopped = False
                    state.stop_reason = None
                    state.stopped_at = None
                    state.cooldown_until = None
                    logger.info(f"  Cleared [{scope}:{scope_id}]")
            session.commit()


def main():
    parser = argparse.ArgumentParser(description="Pre-live setup for sixbtc")
    parser.add_argument(
        '--check', '-c',
        action='store_true',
        help='Check-only mode (no changes)'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Skip confirmation prompts'
    )
    parser.add_argument(
        '--config',
        default='config/prepare_live.yaml',
        help='Path to prepare_live.yaml config'
    )
    args = parser.parse_args()

    try:
        setup = PreLiveSetup(config_path=args.config)
        ready = setup.check_all()

        if args.check:
            sys.exit(0 if ready else 1)

        if not ready or setup.actions:
            success = setup.apply_changes(force=args.force)
            if not success:
                sys.exit(1)

            # Re-check after changes
            if setup.actions:
                logger.info("")
                logger.info("Re-checking after changes...")
                ready = setup.check_all()

        if ready:
            logger.info("")
            logger.info("=" * 60)
            logger.info("READY FOR LIVE TRADING")
            logger.info("=" * 60)
            logger.info("Next steps:")
            logger.info("  1. Ensure funds are transferred to subaccounts")
            logger.info("  2. Restart supervisor: supervisorctl restart all")
            logger.info("  3. Monitor logs and dashboard")
            sys.exit(0)
        else:
            logger.warning("")
            logger.warning("NOT READY - resolve issues above")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
