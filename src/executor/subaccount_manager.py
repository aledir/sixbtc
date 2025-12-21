"""
Subaccount Manager - Hyperliquid Subaccount Management

Manages deployment of strategies to 10 Hyperliquid subaccounts.
"""

import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class SubaccountManager:
    """
    Manages deployment to Hyperliquid subaccounts

    Each of the 10 subaccounts runs one strategy.
    This class handles:
    - Strategy assignment to subaccounts
    - Starting/stopping strategies
    - Position management per subaccount
    """

    def __init__(self, client_or_config=None, config: Optional[Dict] = None, dry_run: bool = True):
        """
        Initialize subaccount manager

        Args:
            client_or_config: Either HyperliquidClient instance or config dict
            config: Configuration dict (when first param is client)
            dry_run: If True, no real orders (ALWAYS use True for testing)
        """
        # Handle different initialization patterns:
        # 1. SubaccountManager(mock_client, dry_run=True)  # Test with client
        # 2. SubaccountManager(config_dict)  # Production with config
        # 3. SubaccountManager(client, config=config_dict)  # Both

        # Determine if first arg is client or config
        if client_or_config is not None and isinstance(client_or_config, dict):
            # First arg is config dict
            config = client_or_config
            client = None
        else:
            # First arg is client (or None)
            client = client_or_config

        if config is not None and isinstance(config, dict):
            # Config provided - extract settings (NO defaults, fast fail)
            try:
                self.dry_run = config['development']['testing']['dry_run']
            except KeyError:
                # Fallback for test configs that may not have nested structure
                self.dry_run = config['dry_run']

            # Get subaccount config from hyperliquid section
            subaccount_config = config['hyperliquid']['subaccounts']
            self.total_subaccounts = subaccount_config['total']

            # For test mode, use test_mode config
            test_mode = subaccount_config.get('test_mode', {})
            if test_mode.get('enabled', False):
                self.active_subaccounts = test_mode['count']
                self.capital_per_account = test_mode['capital_per_account']
            else:
                # Production mode - all subaccounts active, no default capital
                self.active_subaccounts = self.total_subaccounts
                self.capital_per_account = None  # Must be set externally in production

            # Create client if not provided
            if client is None:
                from src.executor.hyperliquid_client import HyperliquidClient
                self.client = HyperliquidClient(config=config)
            else:
                self.client = client
        else:
            # No config - use defaults (test mode)
            self.client = client
            self.dry_run = dry_run
            self.total_subaccounts = 10
            self.active_subaccounts = 3
            self.capital_per_account = 100

        self.assignments: Dict[int, Optional[Dict[str, Any]]] = {
            i: None for i in range(1, 11)
        }
        self.subaccount_strategies: Dict[int, str] = {}

        logger.info(
            f"SubaccountManager initialized (dry_run={self.dry_run}, "
            f"total={self.total_subaccounts}, active={self.active_subaccounts})"
        )

    def deploy_strategy(
        self,
        strategy_id: str,
        strategy_instance: Any,
        subaccount_id: int,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Deploy strategy to subaccount

        Args:
            strategy_id: Unique strategy identifier
            strategy_instance: StrategyCore instance
            subaccount_id: Target subaccount (1-10)
            metadata: Optional metadata dict

        Returns:
            True if deployed successfully
        """
        if not 1 <= subaccount_id <= 10:
            logger.error(f"Invalid subaccount_id: {subaccount_id}")
            return False

        # Stop any existing strategy
        if self.assignments[subaccount_id] is not None:
            logger.info(f"Stopping existing strategy on subaccount {subaccount_id}")
            self.stop_strategy(subaccount_id)

        # Assign new strategy
        self.assignments[subaccount_id] = {
            'strategy_id': strategy_id,
            'strategy': strategy_instance,
            'metadata': metadata or {},
            'deployed_at': None  # Would use datetime in real implementation
        }

        logger.info(
            f"Deployed strategy {strategy_id} to subaccount {subaccount_id} "
            f"(dry_run={self.dry_run})"
        )

        return True

    def stop_strategy(self, subaccount_id: int, close_positions: bool = True) -> bool:
        """
        Stop strategy on subaccount

        Args:
            subaccount_id: Subaccount to stop (1-10)
            close_positions: If True, close all positions

        Returns:
            True if stopped successfully
        """
        if not 1 <= subaccount_id <= 10:
            logger.error(f"Invalid subaccount_id: {subaccount_id}")
            return False

        assignment = self.assignments[subaccount_id]
        if assignment is None:
            logger.warning(f"No strategy running on subaccount {subaccount_id}")
            return False

        strategy_id = assignment['strategy_id']

        # Close positions if requested
        if close_positions:
            logger.info(
                f"Closing positions on subaccount {subaccount_id} (dry_run={self.dry_run})"
            )
            if not self.dry_run:
                self.client.switch_subaccount(subaccount_id)
                self.client.close_all_positions()
            else:
                logger.info(f"[DRY RUN] Would close positions on subaccount {subaccount_id}")

        # Remove assignment
        self.assignments[subaccount_id] = None

        logger.info(f"Stopped strategy {strategy_id} on subaccount {subaccount_id}")

        return True

    def get_assignment(self, subaccount_id: int) -> Optional[Dict[str, Any]]:
        """Get current strategy assignment for subaccount"""
        if not 1 <= subaccount_id <= 10:
            return None
        return self.assignments[subaccount_id]

    def get_all_assignments(self) -> Dict[int, Optional[Dict[str, Any]]]:
        """Get all subaccount assignments"""
        return self.assignments.copy()

    def get_active_count(self) -> int:
        """Get number of active strategies"""
        return sum(1 for a in self.assignments.values() if a is not None)

    def stop_all_strategies(self, close_positions: bool = True) -> None:
        """
        Stop all strategies across all subaccounts

        Args:
            close_positions: If True, close all positions
        """
        logger.info("Stopping all strategies...")

        for subaccount_id in range(1, 11):
            if self.assignments[subaccount_id] is not None:
                self.stop_strategy(subaccount_id, close_positions=close_positions)

        logger.info("All strategies stopped")

    def deploy_batch(
        self,
        strategies: list[Dict[str, Any]],
        start_subaccount: int = 1
    ) -> int:
        """
        Deploy multiple strategies starting from specified subaccount

        Args:
            strategies: List of strategy dicts with:
                - strategy_id: Unique ID
                - strategy: StrategyCore instance
                - metadata: Optional metadata
            start_subaccount: Starting subaccount ID (1-10)

        Returns:
            Number of strategies deployed successfully
        """
        deployed_count = 0

        for i, strategy in enumerate(strategies):
            subaccount_id = start_subaccount + i

            if subaccount_id > 10:
                logger.warning(
                    f"Subaccount {subaccount_id} > 10, "
                    f"stopping batch deployment"
                )
                break

            success = self.deploy_strategy(
                strategy_id=strategy['strategy_id'],
                strategy_instance=strategy['strategy'],
                subaccount_id=subaccount_id,
                metadata=strategy.get('metadata')
            )

            if success:
                deployed_count += 1

        logger.info(f"Deployed {deployed_count}/{len(strategies)} strategies")
        return deployed_count

    def get_subaccount_balance(self, subaccount_id: int) -> float:
        """
        Get balance for specific subaccount

        Args:
            subaccount_id: Subaccount ID (1-10)

        Returns:
            Balance in USD
        """
        if not 1 <= subaccount_id <= 10:
            logger.error(f"Invalid subaccount_id: {subaccount_id}")
            return 0.0

        # Switch to subaccount and get state
        self.client.switch_subaccount(subaccount_id)
        state = self.client.get_account_state()

        # Handle different response formats
        if isinstance(state, dict):
            # Mock client format
            if 'account_value' in state:
                return float(state['account_value'])
            # Real client format
            balance_str = state.get('marginSummary', {}).get('accountValue', '0.0')
            return float(balance_str)

        return 0.0

    def get_subaccount_positions(self, subaccount_id: int) -> list:
        """
        Get positions for specific subaccount

        Args:
            subaccount_id: Subaccount ID (1-10)

        Returns:
            List of position dicts
        """
        if not 1 <= subaccount_id <= 10:
            logger.error(f"Invalid subaccount_id: {subaccount_id}")
            return []

        # Switch to subaccount and get positions
        self.client.switch_subaccount(subaccount_id)
        return self.client.get_open_positions()

    def assign_strategy(self, subaccount_id: int, strategy_id: str) -> bool:
        """
        Assign strategy to subaccount

        Args:
            subaccount_id: Subaccount ID (1-10)
            strategy_id: Strategy identifier

        Returns:
            True if assigned successfully
        """
        if not 1 <= subaccount_id <= 10:
            logger.error(f"Invalid subaccount_id: {subaccount_id}")
            return False

        # Check if already assigned
        if subaccount_id in self.subaccount_strategies:
            logger.warning(
                f"Subaccount {subaccount_id} already has strategy "
                f"{self.subaccount_strategies[subaccount_id]}"
            )
            return False

        # Assign strategy
        self.subaccount_strategies[subaccount_id] = strategy_id
        logger.info(f"Assigned strategy {strategy_id} to subaccount {subaccount_id}")

        return True

    def emergency_stop(self, reason: str) -> None:
        """
        Execute emergency stop - stop all strategies and close positions

        Args:
            reason: Reason for emergency stop
        """
        logger.critical(f"EMERGENCY STOP TRIGGERED: {reason}")

        # Stop all strategies
        self.stop_all_strategies(close_positions=True)

        logger.critical("Emergency stop completed")

    def stop_all(self) -> None:
        """
        Alias for stop_all_strategies (for test compatibility)
        """
        self.stop_all_strategies(close_positions=True)
