"""
Strategy Deployer - Deploy Strategies to Hyperliquid Subaccounts

Single Responsibility: Deploy selected strategies to subaccounts.

Deployment flow:
1. Get free subaccounts (no assigned strategy)
2. Assign strategy to subaccount
3. Update strategy status to LIVE
4. Initialize subaccount for trading
"""

from datetime import datetime, UTC
from typing import Dict, List, Optional
from uuid import UUID

from src.database import get_session
from src.database.models import Strategy, Subaccount
from src.database.event_tracker import EventTracker
from src.executor.hyperliquid_client import HyperliquidClient
from src.utils.logger import get_logger
from src.utils.strategy_files import save_to_live, remove_from_pool, remove_from_live

logger = get_logger(__name__)


class StrategyDeployer:
    """
    Deploys strategies to Hyperliquid subaccounts.

    Single Responsibility: Deployment only (no selection, no monitoring).
    """

    def __init__(self, config: dict, client: Optional[HyperliquidClient] = None):
        """
        Initialize deployer with config.

        Args:
            config: Configuration dict
            client: Optional HyperliquidClient (for dependency injection)

        Raises:
            KeyError: If required config sections are missing (Fast Fail)
        """
        trading_config = config['trading']

        # Get subaccount count from config (managed via setup_hyperliquid.py)
        self.n_subaccounts = config['hyperliquid']['subaccounts']['count']
        self.dry_run = config.get('hyperliquid', {}).get('dry_run', True)

        # Capital allocation
        self.total_capital = trading_config['total_capital']

        # Hyperliquid client (dependency injection)
        self.client = client or HyperliquidClient(config, dry_run=self.dry_run)

        logger.info(
            f"StrategyDeployer initialized: {self.n_subaccounts} subaccounts, "
            f"dry_run={self.dry_run}, capital=${self.total_capital}"
        )

    def get_free_subaccounts(self) -> List[Dict]:
        """
        Get subaccounts without assigned strategies.

        Creates missing subaccounts if needed.

        Returns:
            List of free subaccount dicts with id and allocated_capital
        """
        free = []

        with get_session() as session:
            # Get existing subaccounts
            existing = {s.id for s in session.query(Subaccount).all()}

            # Create missing subaccounts
            for i in range(1, self.n_subaccounts + 1):
                if i not in existing:
                    new_sa = Subaccount(
                        id=i,
                        status='PAUSED',
                        allocated_capital=0
                    )
                    session.add(new_sa)
                    logger.info(f"Created subaccount {i}")

            session.commit()

            # Get free subaccounts (no strategy assigned)
            free_subaccounts = (
                session.query(Subaccount)
                .filter(Subaccount.strategy_id.is_(None))
                .order_by(Subaccount.id.asc())
                .all()
            )

            for sa in free_subaccounts:
                free.append({
                    'id': sa.id,
                    'allocated_capital': sa.allocated_capital or 0,
                })

        return free

    async def deploy(self, strategy: Dict, subaccount_id: int) -> bool:
        """
        Deploy a strategy to a subaccount.

        Args:
            strategy: Strategy dict with id, name, code, etc.
            subaccount_id: Subaccount ID to deploy to

        Returns:
            True if deployment successful
        """
        strategy_id = strategy['id']
        strategy_name = strategy['name']

        logger.info(f"Deploying {strategy_name} to subaccount {subaccount_id}")

        # Emit deployment started event
        EventTracker.deployment_started(strategy_id, strategy_name, subaccount_id)

        try:
            # Calculate capital allocation (equal distribution)
            with get_session() as session:
                active_count = (
                    session.query(Subaccount)
                    .filter(Subaccount.status == 'ACTIVE')
                    .count()
                )
                # Include this new one in count
                capital_per = self.total_capital / (active_count + 1)

            # Update database
            with get_session() as session:
                # Update subaccount
                subaccount = session.query(Subaccount).filter(
                    Subaccount.id == subaccount_id
                ).first()

                if not subaccount:
                    logger.error(f"Subaccount {subaccount_id} not found")
                    return False

                subaccount.strategy_id = strategy_id
                subaccount.status = 'ACTIVE'
                subaccount.deployed_at = datetime.now(UTC)

                # Only set allocated_capital if not already funded
                # This respects manually funded subaccounts (e.g., test phase)
                if subaccount.allocated_capital is None or subaccount.allocated_capital == 0:
                    subaccount.allocated_capital = capital_per
                    logger.info(f"Subaccount {subaccount_id}: set allocated_capital=${capital_per:.2f}")
                else:
                    logger.info(
                        f"Subaccount {subaccount_id}: keeping existing capital=${subaccount.allocated_capital:.2f}"
                    )

                # Update strategy
                db_strategy = session.query(Strategy).filter(
                    Strategy.id == strategy_id
                ).first()

                if not db_strategy:
                    logger.error(f"Strategy {strategy_id} not found")
                    return False

                db_strategy.status = 'LIVE'
                db_strategy.live_since = datetime.now(UTC)

                session.commit()

                # Move .py file: pool/ -> live/
                remove_from_pool(db_strategy.name)
                save_to_live(db_strategy.name, db_strategy.code)

            # Emit events for successful deployment
            EventTracker.strategy_promoted_live(strategy_id, strategy_name, subaccount_id)
            EventTracker.deployment_succeeded(
                strategy_id, strategy_name, subaccount_id, capital_per
            )

            logger.info(
                f"Deployed {strategy_name} to subaccount {subaccount_id} "
                f"(capital=${capital_per:.2f})"
            )

            return True

        except Exception as e:
            # Emit deployment failed event
            EventTracker.deployment_failed(
                strategy_id, strategy_name, subaccount_id, str(e)
            )
            logger.error(f"Deployment failed for {strategy_name}: {e}")
            return False

    async def undeploy(self, strategy_id: UUID, reason: str = "retired") -> bool:
        """
        Remove a strategy from its subaccount.

        Args:
            strategy_id: Strategy UUID
            reason: Reason for removal

        Returns:
            True if undeployment successful
        """
        try:
            with get_session() as session:
                # Find subaccount with this strategy
                subaccount = (
                    session.query(Subaccount)
                    .filter(Subaccount.strategy_id == strategy_id)
                    .first()
                )

                if subaccount:
                    subaccount_id = subaccount.id

                    # Close positions if not dry run
                    if not self.dry_run:
                        await self.client.close_all_positions(subaccount_id)

                    # Free up subaccount
                    subaccount.strategy_id = None
                    subaccount.status = 'PAUSED'

                # Update strategy
                strategy = session.query(Strategy).filter(
                    Strategy.id == strategy_id
                ).first()

                if strategy:
                    # Calculate live duration if available
                    live_duration_hours = None
                    if strategy.live_since:
                        delta = datetime.now(UTC) - strategy.live_since
                        live_duration_hours = delta.total_seconds() / 3600

                    strategy.status = 'RETIRED'
                    strategy.retired_at = datetime.now(UTC)

                    # Remove .py file from live/
                    remove_from_live(strategy.name)

                    # Emit retirement event
                    EventTracker.strategy_retired(
                        strategy_id=strategy_id,
                        strategy_name=strategy.name,
                        reason=reason,
                        live_duration_hours=live_duration_hours
                    )

                    logger.info(f"Undeployed {strategy.name}: {reason}")

                session.commit()

            return True

        except Exception as e:
            logger.error(f"Undeployment failed for {strategy_id}: {e}")
            return False

    def get_deployment_stats(self) -> Dict:
        """
        Get deployment statistics.

        Returns:
            Dict with deployed_count, free_count, total_allocated_capital
        """
        with get_session() as session:
            subaccounts = session.query(Subaccount).all()

            deployed = [s for s in subaccounts if s.strategy_id is not None]
            free = [s for s in subaccounts if s.strategy_id is None]

            total_allocated = sum(s.allocated_capital or 0 for s in deployed)

            return {
                'total_subaccounts': len(subaccounts),
                'deployed_count': len(deployed),
                'free_count': len(free),
                'total_allocated_capital': total_allocated,
                'capital_per_strategy': total_allocated / len(deployed) if deployed else 0,
            }
