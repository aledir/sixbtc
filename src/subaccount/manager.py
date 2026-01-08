"""
Subaccount Manager for Hyperliquid

Handles creation and management of Hyperliquid subaccounts.
Does NOT handle funds - see FundManager for that.

Usage:
    manager = SubaccountManager(config)
    subaccounts = manager.list_subaccounts()
    manager.ensure_subaccounts(count=10)
"""

import os
import re
from datetime import datetime, UTC
from typing import Dict, List, Optional

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

from src.utils.logger import get_logger

logger = get_logger(__name__)


class NamingMismatchError(Exception):
    """
    Raised when subaccount names don't match the expected pattern.

    Contains detailed instructions for the user on how to fix.
    """

    def __init__(self, expected: List[str], found: List[str]):
        self.expected = expected
        self.found = found
        self.message = self._build_message()
        super().__init__(self.message)

    def _build_message(self) -> str:
        expected_list = '\n'.join(f'  - {n}' for n in self.expected)
        found_list = '\n'.join(f'  - {n}' for n in self.found)

        return f"""
ERROR: Subaccount naming mismatch detected!

Expected (from config pattern):
{expected_list}

Found on Hyperliquid:
{found_list}

Please fix by either:
  1. Rename subaccounts on app.hyperliquid.xyz to match pattern
  2. Change naming_pattern in config.yaml to match existing names

Then run this script again.
"""


class SubaccountManager:
    """
    Manages Hyperliquid subaccounts.

    Responsibilities:
    - List existing subaccounts from Hyperliquid API
    - Create new subaccounts
    - Validate naming against config pattern
    - Ensure required number of subaccounts exist

    Does NOT handle:
    - Fund transfers (see FundManager)
    - Agent wallet creation (see AgentManager)
    """

    def __init__(self, config: Dict):
        """
        Initialize SubaccountManager.

        Args:
            config: Configuration dict with hyperliquid.subaccounts section

        Raises:
            ValueError: If required environment variables not set
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

        # Create clients
        self.exchange = Exchange(self.master_wallet, self.api_url)
        self.info = Info(self.api_url, skip_ws=True)

        # Subaccount config
        subaccount_config = config.get('hyperliquid', {}).get('subaccounts', {})
        self.target_count = subaccount_config.get('count', 10)
        self.naming_pattern = subaccount_config.get('naming_pattern', 'Bot-{:03d}')

        logger.info(
            f"SubaccountManager initialized: target_count={self.target_count}, "
            f"pattern={self.naming_pattern}"
        )

    def list_subaccounts(self, include_all: bool = False) -> List[Dict]:
        """
        Get list of subaccounts from Hyperliquid.

        Args:
            include_all: If True, return ALL subaccounts from Hyperliquid.
                         If False (default), return only managed subaccounts
                         (up to target_count from config).

        Returns:
            List of dicts with 'name' and 'address' keys, sorted by name
        """
        try:
            # Query subaccounts for master address
            result = self.info.query_sub_accounts(self.master_address)

            if not result:
                logger.info("No subaccounts found")
                return []

            subaccounts = []
            for sub in result:
                subaccounts.append({
                    'name': sub.get('name', ''),
                    'address': sub.get('subAccountUser', ''),
                    'clearinghouseState': sub.get('clearinghouseState', {})
                })

            # Sort by name for consistent ordering
            subaccounts.sort(key=lambda x: x['name'])

            # Limit to managed subaccounts unless include_all is True
            if not include_all and len(subaccounts) > self.target_count:
                subaccounts = subaccounts[:self.target_count]

            logger.info(f"Found {len(subaccounts)} subaccounts")
            return subaccounts

        except Exception as e:
            logger.error(f"Failed to list subaccounts: {e}")
            raise

    def create_subaccount(self, name: str) -> str:
        """
        Create a new subaccount on Hyperliquid.

        Args:
            name: Name for the subaccount (e.g., 'Bot-001')

        Returns:
            Address of the created subaccount

        Raises:
            RuntimeError: If creation fails
        """
        logger.info(f"Creating subaccount: {name}")

        try:
            result = self.exchange.create_sub_account(name)

            if result.get('status') != 'ok':
                error_msg = result.get('response', {}).get('data', {}).get('error', 'Unknown error')
                raise RuntimeError(f"create_sub_account failed: {error_msg}")

            # Extract subaccount address from response
            sub_address = result.get('response', {}).get('data', {}).get('subAccountUser')

            if not sub_address:
                raise RuntimeError("No subAccountUser in response")

            logger.info(f"Subaccount created: name={name}, address={sub_address[:10]}...")
            return sub_address

        except Exception as e:
            logger.error(f"Failed to create subaccount {name}: {e}")
            raise RuntimeError(f"Failed to create subaccount: {e}") from e

    def generate_expected_names(self, count: int) -> List[str]:
        """
        Generate expected subaccount names from pattern.

        Args:
            count: Number of names to generate

        Returns:
            List of expected names (e.g., ['Bot-001', 'Bot-002', ...])
        """
        return [self.naming_pattern.format(i) for i in range(1, count + 1)]

    def validate_naming(self, existing: List[Dict], expected_count: int) -> bool:
        """
        Validate that existing subaccount names match the expected pattern.

        Args:
            existing: List of existing subaccounts from list_subaccounts()
            expected_count: Number of subaccounts expected

        Returns:
            True if all names match

        Raises:
            NamingMismatchError: If names don't match (with instructions)
        """
        if not existing:
            # No existing subaccounts - nothing to validate
            return True

        existing_names = [sub['name'] for sub in existing]
        expected_names = self.generate_expected_names(len(existing))

        # Check if all existing names are in expected pattern
        # We only check existing ones, not the full expected_count
        mismatches = []
        for i, name in enumerate(existing_names):
            expected = expected_names[i] if i < len(expected_names) else f"(index {i})"
            if name != expected:
                mismatches.append((expected, name))

        if mismatches:
            # Build full expected list for error message
            all_expected = self.generate_expected_names(max(len(existing), expected_count))
            raise NamingMismatchError(
                expected=all_expected[:len(existing)],
                found=existing_names
            )

        logger.info(f"Naming validation passed: {len(existing)} subaccounts match pattern")
        return True

    def ensure_subaccounts(self, count: Optional[int] = None) -> List[Dict]:
        """
        Ensure the required number of subaccounts exist.

        1. Lists existing subaccounts
        2. Validates naming (Fast Fail if mismatch)
        3. Creates missing subaccounts

        Args:
            count: Target number of subaccounts (default: from config)

        Returns:
            List of all subaccounts (existing + newly created)

        Raises:
            NamingMismatchError: If existing names don't match pattern
            RuntimeError: If count would decrease (not supported)
        """
        if count is None:
            count = self.target_count

        logger.info(f"Ensuring {count} subaccounts exist")

        # Get existing subaccounts
        existing = self.list_subaccounts()
        existing_count = len(existing)

        # Check if count would decrease
        if count < existing_count:
            raise RuntimeError(
                f"Cannot reduce subaccount count from {existing_count} to {count}. "
                f"Hyperliquid does not support deleting subaccounts. "
                f"Please set count >= {existing_count} in config.yaml"
            )

        # Validate naming of existing subaccounts
        self.validate_naming(existing, count)

        # Create missing subaccounts
        if existing_count < count:
            needed = count - existing_count
            logger.info(f"Creating {needed} new subaccounts")

            for i in range(existing_count + 1, count + 1):
                name = self.naming_pattern.format(i)
                try:
                    address = self.create_subaccount(name)
                    existing.append({
                        'name': name,
                        'address': address,
                        'clearinghouseState': {}
                    })
                except Exception as e:
                    logger.error(f"Failed to create subaccount {name}: {e}")
                    raise

        logger.info(f"Subaccount setup complete: {len(existing)} subaccounts")
        return existing

    def get_subaccount_by_id(self, subaccount_id: int) -> Optional[Dict]:
        """
        Get subaccount by ID (1-indexed).

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)

        Returns:
            Subaccount dict or None if not found
        """
        existing = self.list_subaccounts()

        if subaccount_id < 1 or subaccount_id > len(existing):
            return None

        # Subaccounts are 1-indexed, list is 0-indexed
        return existing[subaccount_id - 1]

    def get_subaccount_address(self, subaccount_id: int) -> Optional[str]:
        """
        Get address for a subaccount by ID.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)

        Returns:
            Address string or None if not found
        """
        sub = self.get_subaccount_by_id(subaccount_id)
        return sub['address'] if sub else None
