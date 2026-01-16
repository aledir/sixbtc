"""
Balance Reconciliation Service

Automatically reconciles allocated_capital based on ledger updates from Hyperliquid.
Solves the "phantom capital" problem where subaccounts have allocated_capital > 0
but were never actually funded on Hyperliquid.

Features:
1. Startup catchup: Recovers missed events during downtime via HTTP API
2. Real-time tracking: WebSocket callback for live ledger updates
3. Automatic adjustment: Updates allocated_capital based on deposit/withdraw events

Policy:
- Deposit/Transfer IN -> allocated_capital += amount
- Withdraw/Transfer OUT -> allocated_capital -= amount
- Never allows allocated_capital < 0 (uses max(0, ...))
- Deposit also updates peak_balance if it becomes higher
- CRITICAL: If allocated_capital > 0 but NO deposit events found -> zero out allocated_capital
"""

from datetime import datetime, UTC, timedelta
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from src.database.connection import get_session
from src.database.models import Subaccount
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.executor.hyperliquid_client import HyperliquidClient
    from src.data.hyperliquid_websocket import HyperliquidDataProvider, LedgerUpdate

logger = get_logger(__name__)


class BalanceReconciliationService:
    """
    Reconciles allocated_capital based on ledger updates from Hyperliquid.

    Handles:
    - Startup catchup: Fetch missed events via HTTP
    - Real-time updates: WebSocket callback
    - Phantom capital detection: Zero out allocated_capital if no deposits found
    """

    def __init__(
        self,
        client: 'HyperliquidClient',
        data_provider: Optional['HyperliquidDataProvider'] = None,
        config: Optional[Dict] = None
    ):
        """
        Initialize balance reconciliation service.

        Args:
            client: HyperliquidClient for HTTP queries
            data_provider: WebSocket data provider for real-time updates
            config: Configuration dict
        """
        self.client = client
        self.data_provider = data_provider
        self.config = config or {}

        # Configuration (nested under hyperliquid in config.yaml)
        hl_config = self.config.get('hyperliquid', {})
        recon_config = hl_config.get('balance_reconciliation', {})
        self.enabled = recon_config.get('enabled', True)
        self.catchup_lookback_days = recon_config.get('catchup_lookback_days', 7)

        # Track processed transaction hashes to avoid duplicates
        self._processed_hashes: Set[str] = set()

        # Register WebSocket callback if data_provider is available
        if self.data_provider and self.enabled:
            self.data_provider.set_ledger_callback(self._on_ledger_update)
            logger.info("BalanceReconciliationService: WebSocket callback registered")

        logger.info(
            f"BalanceReconciliationService initialized: enabled={self.enabled}, "
            f"lookback={self.catchup_lookback_days} days"
        )

    async def startup_catchup(self) -> int:
        """
        Reconcile allocated_capital with actual balance at startup.

        Simple rule: allocated_capital = current_balance
        This ensures DD calculation is always based on actual funds.

        Returns:
            Number of subaccounts reconciled
        """
        if not self.enabled:
            logger.info("Balance reconciliation disabled, skipping catchup")
            return 0

        logger.info("Starting balance reconciliation...")

        reconciled_count = 0

        # Calculate time range for ledger (for tracking hashes only)
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        start_ms = now_ms - (self.catchup_lookback_days * 24 * 60 * 60 * 1000)

        with get_session() as session:
            # Only reconcile ACTIVE subaccounts - PAUSED/STOPPED have stale data
            subaccounts = session.query(Subaccount).filter(
                Subaccount.status == 'ACTIVE'
            ).all()

            for sa in subaccounts:
                try:
                    # Skip subaccounts without credentials configured
                    if sa.id not in self.client._subaccount_credentials:
                        logger.debug(f"Subaccount {sa.id}: no credentials, skipping")
                        continue

                    old_allocated = sa.allocated_capital or 0
                    old_current = sa.current_balance or 0

                    # Get actual balance from Hyperliquid (source of truth)
                    try:
                        actual_balance = self.client.get_account_balance(sa.id)
                    except Exception as e:
                        logger.warning(f"Subaccount {sa.id}: cannot get balance - {e}")
                        continue

                    # Update current_balance to actual
                    sa.current_balance = actual_balance

                    # SIMPLE RULE: allocated_capital = actual_balance
                    # This ensures no DD discrepancy from stale allocated values
                    needs_update = False
                    reason = ""

                    if actual_balance <= 0:
                        # No funds - zero everything
                        if old_allocated > 0:
                            reason = f"PHANTOM (allocated=${old_allocated:.2f}, balance=$0)"
                            sa.allocated_capital = 0
                            sa.peak_balance = 0
                            needs_update = True
                    else:
                        # Has funds - ensure allocated matches balance
                        # This prevents false DD when allocated > balance due to withdrawals
                        diff = abs(old_allocated - actual_balance)
                        if diff > 1.0:  # Only fix significant differences (>$1)
                            reason = f"MISMATCH (allocated=${old_allocated:.2f}, balance=${actual_balance:.2f})"
                            sa.allocated_capital = actual_balance
                            # Peak should be at least current balance
                            if sa.peak_balance is None or sa.peak_balance < actual_balance:
                                sa.peak_balance = actual_balance
                                sa.peak_balance_updated_at = datetime.now(UTC)
                            needs_update = True

                    if needs_update:
                        logger.info(
                            f"Subaccount {sa.id}: reconciling - {reason} -> "
                            f"allocated=${sa.allocated_capital:.2f}"
                        )
                        reconciled_count += 1

                    # Track ledger hashes for real-time deduplication
                    try:
                        events = self.client.get_ledger_updates(
                            subaccount_id=sa.id,
                            start_time=start_ms,
                            end_time=now_ms
                        )
                        for event in events:
                            tx_hash = event.get('hash', '')
                            if tx_hash:
                                self._processed_hashes.add(tx_hash)
                    except Exception:
                        pass  # Ledger tracking is best-effort

                except Exception as e:
                    logger.error(
                        f"Subaccount {sa.id}: error during reconciliation - {e}",
                        exc_info=True
                    )

            session.commit()

        logger.info(f"Balance reconciliation complete: {reconciled_count} subaccounts fixed")

        return reconciled_count

    def _on_ledger_update(self, update: 'LedgerUpdate') -> None:
        """
        Callback for real-time ledger updates from WebSocket.

        Args:
            update: LedgerUpdate dataclass from WebSocket
        """
        if not self.enabled:
            return

        try:
            # Skip duplicates
            if update.hash in self._processed_hashes:
                logger.debug(f"Ledger update {update.hash[:16]}... already processed, skipping")
                return

            self._processed_hashes.add(update.hash)

            # Resolve which subaccount this update belongs to
            # For now, we apply to the first subaccount (master) since WebSocket
            # subscription is on master address. In future, could parse raw_data
            # to determine exact subaccount.
            subaccount_id = self._resolve_subaccount_id(update)

            if subaccount_id is None:
                logger.warning(
                    f"Could not resolve subaccount for ledger update: "
                    f"{update.update_type} ${update.amount:.2f}"
                )
                return

            with get_session() as session:
                adjusted = self._apply_adjustment(
                    session=session,
                    subaccount_id=subaccount_id,
                    amount=update.amount,
                    direction=update.direction,
                    event_type=update.update_type,
                    timestamp=int(update.timestamp.timestamp() * 1000)
                )

                if adjusted:
                    session.commit()
                    logger.info(
                        f"Real-time ledger update applied: subaccount {subaccount_id}, "
                        f"{update.update_type} {update.direction.upper()} ${update.amount:.2f}"
                    )

        except Exception as e:
            logger.error(f"Error processing real-time ledger update: {e}", exc_info=True)

    def _resolve_subaccount_id(self, update: 'LedgerUpdate') -> Optional[int]:
        """
        Resolve which subaccount a ledger update belongs to.

        Args:
            update: LedgerUpdate from WebSocket

        Returns:
            Subaccount ID or None if cannot resolve
        """
        # Try to extract destination/user address from raw_data
        raw_data = update.raw_data or {}
        delta = raw_data.get('delta', raw_data)

        # Check for destination address
        destination = delta.get('destination', '').lower()
        user = delta.get('user', '').lower()

        # Try to match with configured subaccount addresses
        for sub_id, creds in self.client._subaccount_credentials.items():
            sub_address = creds.get('address', '').lower()
            if sub_address and (sub_address == destination or sub_address == user):
                return sub_id

        # Default to first subaccount if we can't determine
        if self.client._subaccount_credentials:
            return min(self.client._subaccount_credentials.keys())

        return None

    def _apply_adjustment(
        self,
        session,
        subaccount_id: int,
        amount: float,
        direction: str,
        event_type: str,
        timestamp: int
    ) -> bool:
        """
        Apply a single adjustment to allocated_capital.

        Args:
            session: Database session
            subaccount_id: Subaccount ID
            amount: Amount to adjust
            direction: 'in' or 'out'
            event_type: Type of event (deposit, withdraw, etc.)
            timestamp: Event timestamp in ms

        Returns:
            True if adjustment was applied
        """
        if amount <= 0:
            return False

        if direction not in ('in', 'out'):
            logger.warning(f"Unknown direction '{direction}' for {event_type}, skipping")
            return False

        sa = session.query(Subaccount).filter(
            Subaccount.id == subaccount_id
        ).first()

        if not sa:
            logger.warning(f"Subaccount {subaccount_id} not found in database")
            return False

        old_allocated = sa.allocated_capital or 0

        if direction == 'in':
            # Deposit/Transfer IN -> increase allocated_capital
            sa.allocated_capital = old_allocated + amount

            # Also update peak_balance if this deposit makes it higher
            if sa.peak_balance is None or sa.allocated_capital > sa.peak_balance:
                sa.peak_balance = sa.allocated_capital
                sa.peak_balance_updated_at = datetime.now(UTC)

            logger.debug(
                f"Subaccount {subaccount_id}: {event_type} IN +${amount:.2f}, "
                f"allocated_capital ${old_allocated:.2f} -> ${sa.allocated_capital:.2f}"
            )

        else:  # direction == 'out'
            # Withdraw/Transfer OUT -> decrease allocated_capital
            # Never go below zero
            sa.allocated_capital = max(0, old_allocated - amount)

            logger.debug(
                f"Subaccount {subaccount_id}: {event_type} OUT -${amount:.2f}, "
                f"allocated_capital ${old_allocated:.2f} -> ${sa.allocated_capital:.2f}"
            )

        return True

    def get_reconciliation_status(self) -> Dict:
        """
        Get current reconciliation status for all subaccounts.

        Returns:
            Dict with status information
        """
        status = {
            'enabled': self.enabled,
            'processed_events': len(self._processed_hashes),
            'subaccounts': {}
        }

        with get_session() as session:
            subaccounts = session.query(Subaccount).all()

            for sa in subaccounts:
                status['subaccounts'][sa.id] = {
                    'allocated_capital': sa.allocated_capital,
                    'current_balance': sa.current_balance,
                    'peak_balance': sa.peak_balance,
                    'status': sa.status,
                }

        return status
