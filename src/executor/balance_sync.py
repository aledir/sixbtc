"""
Balance Sync Service - Initialize allocated_capital from Hyperliquid.

Syncs balance at executor startup to handle:
1. Manually funded subaccounts (test phase)
2. Recovery after crash (re-establish baseline)
3. External transfers to subaccounts

Policy:
- Only initializes allocated_capital if it's 0 or NULL
- Never overwrites rotator's allocation during normal operation
- Always updates current_balance and peak_balance
"""

import logging
from datetime import datetime, UTC
from typing import Dict, Optional

from src.database.connection import get_session
from src.database.models import Subaccount

logger = logging.getLogger(__name__)


class BalanceSyncService:
    """Sync subaccount balances from Hyperliquid at startup."""

    def __init__(self, config: dict, client):
        """
        Initialize balance sync service.

        Args:
            config: Raw config dict
            client: HyperliquidClient instance
        """
        self.config = config
        self.client = client

    def sync_all_subaccounts(self) -> Dict[int, float]:
        """
        Sync balance for all subaccounts with funds on Hyperliquid.

        For each subaccount:
        - Fetches actual balance from Hyperliquid
        - Sets allocated_capital if not already set (0 or NULL)
        - Always updates current_balance
        - Initializes peak_balance if not set

        Returns:
            Dict mapping subaccount_id -> balance synced
        """
        results = {}

        with get_session() as session:
            # Only sync ACTIVE subaccounts - ignore PAUSED/STOPPED/RETIRED
            # Old subaccounts with stale allocated_capital cause false DD alerts
            subaccounts = session.query(Subaccount).filter(
                Subaccount.status == 'ACTIVE'
            ).all()

            for sa in subaccounts:
                try:
                    actual_balance = self.client.get_account_balance(sa.id)

                    if actual_balance <= 0:
                        logger.debug(f"Subaccount {sa.id}: skipping (balance={actual_balance})")
                        continue

                    # Initialize allocated_capital ONLY if not set
                    # This respects both manual funding AND rotator allocations
                    if sa.allocated_capital is None or sa.allocated_capital == 0:
                        sa.allocated_capital = actual_balance
                        logger.info(
                            f"Subaccount {sa.id}: initialized allocated_capital=${actual_balance:.2f} "
                            f"from Hyperliquid balance"
                        )

                    # Always sync current_balance (track actual state)
                    old_balance = sa.current_balance
                    sa.current_balance = actual_balance

                    if old_balance != actual_balance:
                        logger.debug(
                            f"Subaccount {sa.id}: current_balance "
                            f"${old_balance or 0:.2f} -> ${actual_balance:.2f}"
                        )

                    # IMPORTANT: Do NOT initialize peak_balance from Hyperliquid balance!
                    # peak_balance must be based on allocated_capital (set by deployer)
                    # Otherwise, manual Hyperliquid funding causes false 90% drawdown alerts.
                    # See: Root cause analysis of EmergencyStopState bug.
                    #
                    # peak_balance is set by:
                    # 1. StrategyDeployer when deploying (= allocated_capital)
                    # 2. EmergencyStopManager when profits increase peak
                    #
                    # Only update timestamp to show data sync is fresh
                    if sa.peak_balance is not None and sa.peak_balance > 0:
                        sa.peak_balance_updated_at = datetime.now(UTC)

                    results[sa.id] = actual_balance

                except ValueError as e:
                    # Subaccount not configured in Hyperliquid
                    logger.debug(f"Subaccount {sa.id}: not configured in Hyperliquid - {e}")
                except RuntimeError as e:
                    # API error
                    logger.error(f"Subaccount {sa.id}: failed to fetch balance - {e}")
                except Exception as e:
                    logger.error(f"Subaccount {sa.id}: unexpected error during sync - {e}")

            session.commit()

        return results

    def force_sync_allocated(self, subaccount_id: int) -> Optional[float]:
        """
        Force update allocated_capital from Hyperliquid.

        Use when user explicitly wants to reset baseline (e.g., after manual top-up).
        This will overwrite existing allocated_capital.

        Args:
            subaccount_id: Subaccount ID to sync

        Returns:
            New allocated_capital value, or None if failed
        """
        try:
            actual_balance = self.client.get_account_balance(subaccount_id)

            if actual_balance <= 0:
                logger.warning(
                    f"Subaccount {subaccount_id}: cannot force sync - "
                    f"balance is {actual_balance}"
                )
                return None

            with get_session() as session:
                sa = session.query(Subaccount).filter(
                    Subaccount.id == subaccount_id
                ).first()

                if not sa:
                    logger.error(f"Subaccount {subaccount_id}: not found in database")
                    return None

                old_allocated = sa.allocated_capital
                sa.allocated_capital = actual_balance
                sa.current_balance = actual_balance

                # Force sync resets the baseline - peak_balance = new allocated_capital
                # This is intentional: user explicitly requested a reset
                sa.peak_balance = actual_balance
                sa.peak_balance_updated_at = datetime.now(UTC)
                session.commit()

                logger.info(
                    f"Subaccount {subaccount_id}: force synced allocated_capital "
                    f"${old_allocated or 0:.2f} -> ${actual_balance:.2f}"
                )
                return actual_balance

        except Exception as e:
            logger.error(f"Subaccount {subaccount_id}: force sync failed - {e}")
            return None

    def get_sync_status(self) -> Dict[int, dict]:
        """
        Get current sync status for all subaccounts.

        Returns:
            Dict mapping subaccount_id -> status info
        """
        status = {}

        with get_session() as session:
            subaccounts = session.query(Subaccount).all()

            for sa in subaccounts:
                status[sa.id] = {
                    'allocated_capital': sa.allocated_capital,
                    'current_balance': sa.current_balance,
                    'peak_balance': sa.peak_balance,
                    'peak_balance_updated_at': sa.peak_balance_updated_at,
                    'status': sa.status,
                    'needs_sync': (
                        sa.allocated_capital is None or
                        sa.allocated_capital == 0
                    )
                }

        return status
