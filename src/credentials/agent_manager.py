"""
Agent Wallet Manager for Hyperliquid

Handles creation, renewal, and lifecycle management of agent wallets.
Agent wallets are API keys that can trade on behalf of master/subaccounts
but cannot withdraw funds.

Usage:
    manager = AgentManager(config)
    credential = manager.create_agent('subaccount', '0x123...', subaccount_id=1, name='Bot-001')
    expiring = manager.get_expiring_credentials(days=30)
    manager.renew_all_expiring()
"""

import os
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

from src.database.connection import get_session
from src.database.models import Credential
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AgentManager:
    """
    Manages Hyperliquid agent wallets for master and subaccounts.

    Responsibilities:
    - Create new agent wallets via approve_agent()
    - Store credentials in database
    - Track expiration and renew before expiry
    - Revoke old credentials when replaced
    """

    def __init__(self, config: Dict):
        """
        Initialize AgentManager.

        Args:
            config: Configuration dict with hyperliquid.agent_wallet section

        Raises:
            ValueError: If HL_MASTER_PRIVATE_KEY not set
        """
        self.config = config

        # Load master wallet
        master_key = os.environ.get('HL_MASTER_PRIVATE_KEY')
        if not master_key:
            raise ValueError("HL_MASTER_PRIVATE_KEY environment variable not set")

        self.master_wallet = Account.from_key(master_key)
        self.master_address = os.environ.get('HL_MASTER_ADDRESS', self.master_wallet.address)

        # API URL
        testnet = config.get('hyperliquid', {}).get('testnet', False)
        self.api_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL

        # Agent wallet config
        agent_config = config.get('hyperliquid', {}).get('agent_wallet', {})
        self.validity_days = agent_config.get('validity_days', 180)
        self.renewal_days_before = agent_config.get('renewal_days_before_expiry', 30)

        logger.info(
            f"AgentManager initialized: validity={self.validity_days}d, "
            f"renewal_before={self.renewal_days_before}d"
        )

    def _get_exchange(self, vault_address: Optional[str] = None) -> Exchange:
        """
        Create Exchange client for signing operations.

        Args:
            vault_address: Subaccount address if operating on subaccount

        Returns:
            Configured Exchange client
        """
        return Exchange(
            self.master_wallet,
            self.api_url,
            vault_address=vault_address
        )

    def create_agent(
        self,
        target_type: str,
        target_address: str,
        subaccount_id: Optional[int] = None,
        subaccount_name: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> Credential:
        """
        Create a new agent wallet and save to database.

        Args:
            target_type: 'master' or 'subaccount'
            target_address: Wallet address of the target
            subaccount_id: Subaccount number (1, 2, 3, ...) if target_type='subaccount'
            subaccount_name: Name of subaccount from Hyperliquid (e.g., 'Bot-001')
            agent_name: Name for the agent wallet (used in approve_agent)

        Returns:
            Created Credential object

        Raises:
            RuntimeError: If agent creation fails on Hyperliquid
        """
        if target_type not in ('master', 'subaccount'):
            raise ValueError(f"Invalid target_type: {target_type}")

        if target_type == 'subaccount' and subaccount_id is None:
            raise ValueError("subaccount_id required when target_type='subaccount'")

        # Use subaccount name as agent name if not specified
        if agent_name is None and subaccount_name:
            agent_name = f"sixbtc-{subaccount_name}"

        # Create Exchange client from MASTER (no vault_address)
        # Agent wallets must be created from master account, not from subaccounts.
        # The agent wallet can then be used to trade on any subaccount via vault_address.
        exchange = self._get_exchange(vault_address=None)

        logger.info(
            f"Creating agent wallet for {target_type} "
            f"(address={target_address[:10]}..., name={agent_name})"
        )

        try:
            # Call Hyperliquid approve_agent (always from master)
            response, agent_private_key = exchange.approve_agent(name=agent_name)

            if response.get('status') != 'ok':
                # Response can be a string or dict depending on error type
                error_response = response.get('response', 'Unknown error')
                if isinstance(error_response, dict):
                    error_msg = error_response.get('data', {}).get('error', str(error_response))
                else:
                    error_msg = str(error_response)
                raise RuntimeError(f"approve_agent failed: {error_msg}")

            # Derive agent address from private key
            agent_account = Account.from_key(agent_private_key)
            agent_address = agent_account.address

            # Calculate expiration
            expires_at = datetime.now(UTC) + timedelta(days=self.validity_days)

            # Deactivate any existing active credentials for this target
            self._deactivate_existing(target_type, target_address, subaccount_id)

            # Create credential record
            credential = Credential(
                credential_type='agent_wallet',
                target_type=target_type,
                target_address=target_address,
                subaccount_id=subaccount_id,
                subaccount_name=subaccount_name,
                agent_name=agent_name,
                agent_address=agent_address,
                private_key=agent_private_key,
                expires_at=expires_at,
                is_active=True
            )

            # Save to database
            with get_session() as session:
                session.add(credential)
                session.flush()
                credential_id = credential.id
                # Expunge to detach from session so we can access after session closes
                session.expunge(credential)

            logger.info(
                f"Agent wallet created: id={credential_id}, "
                f"agent={agent_address[:10]}..., expires={expires_at.date()}"
            )

            return credential

        except Exception as e:
            logger.error(f"Failed to create agent wallet: {e}")
            raise RuntimeError(f"Failed to create agent wallet: {e}") from e

    def _deactivate_existing(
        self,
        target_type: str,
        target_address: str,
        subaccount_id: Optional[int]
    ) -> int:
        """
        Deactivate existing active credentials for a target.

        Args:
            target_type: 'master' or 'subaccount'
            target_address: Wallet address
            subaccount_id: Subaccount ID if applicable

        Returns:
            Number of credentials deactivated
        """
        with get_session() as session:
            query = session.query(Credential).filter(
                Credential.target_type == target_type,
                Credential.target_address == target_address,
                Credential.is_active == True
            )

            if subaccount_id is not None:
                query = query.filter(Credential.subaccount_id == subaccount_id)

            credentials = query.all()
            count = 0

            for cred in credentials:
                cred.is_active = False
                count += 1
                logger.debug(f"Deactivated credential id={cred.id}")

            return count

    def get_active_credential(self, subaccount_id: int) -> Optional[Credential]:
        """
        Get active credential for a subaccount.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)

        Returns:
            Active Credential or None if not found
        """
        with get_session() as session:
            credential = session.query(Credential).filter(
                Credential.subaccount_id == subaccount_id,
                Credential.is_active == True,
                Credential.expires_at > datetime.now(UTC)
            ).first()

            if credential:
                # Detach from session for use outside
                session.expunge(credential)

            return credential

    def get_all_active_credentials(self) -> List[Credential]:
        """
        Get all active, non-expired credentials.

        Returns:
            List of active Credential objects
        """
        with get_session() as session:
            credentials = session.query(Credential).filter(
                Credential.is_active == True,
                Credential.expires_at > datetime.now(UTC)
            ).all()

            # Detach from session
            for cred in credentials:
                session.expunge(cred)

            return credentials

    def get_expiring_credentials(self, days: Optional[int] = None) -> List[Credential]:
        """
        Get credentials expiring within N days.

        Args:
            days: Number of days to look ahead (default: renewal_days_before)

        Returns:
            List of credentials expiring soon
        """
        if days is None:
            days = self.renewal_days_before

        cutoff = datetime.now(UTC) + timedelta(days=days)

        with get_session() as session:
            credentials = session.query(Credential).filter(
                Credential.is_active == True,
                Credential.expires_at <= cutoff,
                Credential.expires_at > datetime.now(UTC)  # Not already expired
            ).all()

            # Detach from session
            for cred in credentials:
                session.expunge(cred)

            return credentials

    def renew_credential(self, credential: Credential) -> Credential:
        """
        Renew an expiring credential.

        Creates a new agent wallet with the same name (which revokes the old one
        on Hyperliquid automatically) and updates the database.

        Args:
            credential: Credential to renew

        Returns:
            New Credential object
        """
        logger.info(
            f"Renewing credential id={credential.id} for "
            f"{credential.target_type} subaccount_id={credential.subaccount_id}"
        )

        # Create new agent with same parameters
        new_credential = self.create_agent(
            target_type=credential.target_type,
            target_address=credential.target_address,
            subaccount_id=credential.subaccount_id,
            subaccount_name=credential.subaccount_name,
            agent_name=credential.agent_name
        )

        logger.info(
            f"Credential renewed: old_id={credential.id} -> new_id={new_credential.id}, "
            f"new_expires={new_credential.expires_at.date()}"
        )

        return new_credential

    def renew_all_expiring(self) -> Dict:
        """
        Renew all credentials expiring within renewal window.

        Called by scheduler daily.

        Returns:
            Dict with renewal results:
            {
                'renewed': int,
                'failed': int,
                'errors': List[str]
            }
        """
        expiring = self.get_expiring_credentials()

        if not expiring:
            logger.info("No credentials expiring soon")
            return {'renewed': 0, 'failed': 0, 'errors': []}

        logger.info(f"Found {len(expiring)} credentials to renew")

        renewed = 0
        failed = 0
        errors = []

        for cred in expiring:
            try:
                self.renew_credential(cred)
                renewed += 1
            except Exception as e:
                failed += 1
                error_msg = f"Failed to renew credential {cred.id}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)

        logger.info(f"Renewal complete: renewed={renewed}, failed={failed}")

        return {
            'renewed': renewed,
            'failed': failed,
            'errors': errors
        }

    def revoke_credential(self, credential_id: int) -> bool:
        """
        Revoke (deactivate) a credential.

        Note: This only marks as inactive in DB. The agent wallet remains
        valid on Hyperliquid until it expires or is replaced.

        Args:
            credential_id: ID of credential to revoke

        Returns:
            True if revoked, False if not found
        """
        with get_session() as session:
            credential = session.query(Credential).filter(
                Credential.id == credential_id
            ).first()

            if not credential:
                logger.warning(f"Credential {credential_id} not found")
                return False

            credential.is_active = False
            logger.info(f"Revoked credential id={credential_id}")

            return True

    def get_credential_by_id(self, credential_id: int) -> Optional[Credential]:
        """
        Get credential by ID.

        Args:
            credential_id: Credential ID

        Returns:
            Credential or None
        """
        with get_session() as session:
            credential = session.query(Credential).filter(
                Credential.id == credential_id
            ).first()

            if credential:
                session.expunge(credential)

            return credential
