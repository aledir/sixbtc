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
from src.executor.hyperliquid_client import HyperliquidClient
from src.utils.logger import get_logger

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
        from src.config.loader import get_subaccount_count

        trading_config = config['trading']

        # Auto-detect N subaccounts from .env
        self.n_subaccounts = get_subaccount_count()
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
                subaccount.allocated_capital = capital_per
                subaccount.deployed_at = datetime.now(UTC)

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

            logger.info(
                f"Deployed {strategy_name} to subaccount {subaccount_id} "
                f"(capital=${capital_per:.2f})"
            )

            return True

        except Exception as e:
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
                    strategy.status = 'RETIRED'
                    strategy.retired_at = datetime.now(UTC)
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
