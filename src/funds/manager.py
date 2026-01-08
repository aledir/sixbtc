"""
Fund Manager for Hyperliquid Subaccounts

Handles fund transfers and automatic top-up for subaccounts.
Policy: Topup only from master, NEVER between subaccounts.

Usage:
    manager = FundManager(config)
    balances = manager.get_all_balances()
    result = manager.check_all_subaccounts()
"""

import os
from datetime import datetime, UTC
from enum import Enum
from typing import Dict, List, Optional

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

from src.subaccount.manager import SubaccountManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SubaccountStatus(str, Enum):
    """Subaccount balance status."""
    HEALTHY = "HEALTHY"           # >= min_operational
    LOW_FUNDS = "LOW_FUNDS"       # min_tradeable <= balance < min_operational
    INSUFFICIENT = "INSUFFICIENT"  # < min_tradeable (cannot trade)


class FundManager:
    """
    Manages fund transfers and automatic top-up for Hyperliquid subaccounts.

    Policy:
    - Topup only from master account
    - NEVER transfer between subaccounts
    - Respect master reserve (never drain master below threshold)

    Responsibilities:
    - Check subaccount balances
    - Execute transfers from master to subaccounts
    - Automatic top-up when balance falls below threshold
    - Alert generation for low balance situations
    """

    def __init__(self, config: Dict):
        """
        Initialize FundManager.

        Args:
            config: Configuration dict with hyperliquid.funds section

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

        # Fund config
        funds_config = config.get('hyperliquid', {}).get('funds', {})
        self.min_operational = funds_config.get('min_operational_usd', 50)
        self.topup_target = funds_config.get('topup_target_usd', 100)
        self.master_reserve = funds_config.get('master_reserve_usd', 100)
        self.min_tradeable = funds_config.get('min_tradeable_usd', 15)

        # Subaccount manager for listing
        self.subaccount_manager = SubaccountManager(config)

        logger.info(
            f"FundManager initialized: min_op=${self.min_operational}, "
            f"target=${self.topup_target}, reserve=${self.master_reserve}, "
            f"min_trade=${self.min_tradeable}"
        )

    def get_master_balance(self) -> float:
        """
        Get master account balance (available for transfers).

        Returns:
            Balance in USD
        """
        try:
            user_state = self.info.user_state(self.master_address)
            margin_summary = user_state.get('marginSummary', {})
            account_value = float(margin_summary.get('accountValue', 0))
            return account_value
        except Exception as e:
            logger.error(f"Failed to get master balance: {e}")
            raise

    def get_subaccount_balance(self, address: str) -> float:
        """
        Get subaccount balance.

        Args:
            address: Subaccount wallet address

        Returns:
            Balance in USD
        """
        try:
            user_state = self.info.user_state(address)
            margin_summary = user_state.get('marginSummary', {})
            account_value = float(margin_summary.get('accountValue', 0))
            return account_value
        except Exception as e:
            logger.error(f"Failed to get balance for {address[:10]}...: {e}")
            raise

    def get_all_balances(self) -> Dict:
        """
        Get balances for master and all subaccounts.

        Returns:
            Dict with structure:
            {
                'master': float,
                'subaccounts': {
                    1: {'address': str, 'name': str, 'balance': float, 'status': str},
                    2: {...},
                    ...
                }
            }
        """
        result = {
            'master': self.get_master_balance(),
            'subaccounts': {}
        }

        subaccounts = self.subaccount_manager.list_subaccounts()

        for i, sub in enumerate(subaccounts, 1):
            balance = self.get_subaccount_balance(sub['address'])
            status = self.get_subaccount_status(balance)

            result['subaccounts'][i] = {
                'address': sub['address'],
                'name': sub['name'],
                'balance': balance,
                'status': status.value
            }

        return result

    def get_subaccount_status(self, balance: float) -> SubaccountStatus:
        """
        Determine subaccount status based on balance.

        Args:
            balance: Current balance in USD

        Returns:
            SubaccountStatus enum value
        """
        if balance >= self.min_operational:
            return SubaccountStatus.HEALTHY
        elif balance >= self.min_tradeable:
            return SubaccountStatus.LOW_FUNDS
        else:
            return SubaccountStatus.INSUFFICIENT

    def transfer_to_subaccount(self, subaccount_address: str, amount_usd: float) -> bool:
        """
        Transfer USD from master to subaccount.

        Args:
            subaccount_address: Destination subaccount address
            amount_usd: Amount to transfer in USD

        Returns:
            True if successful

        Raises:
            RuntimeError: If transfer fails
        """
        if amount_usd <= 0:
            raise ValueError(f"Invalid transfer amount: {amount_usd}")

        # Convert to Hyperliquid format (amount in "raw" units - 6 decimals)
        # sub_account_transfer expects usd in smallest units (1 = $0.000001)
        usd_raw = int(amount_usd * 1_000_000)

        logger.info(f"Transferring ${amount_usd:.2f} to {subaccount_address[:10]}...")

        try:
            result = self.exchange.sub_account_transfer(
                sub_account_user=subaccount_address,
                is_deposit=True,  # True = master -> subaccount
                usd=usd_raw
            )

            if result.get('status') != 'ok':
                error_msg = result.get('response', {}).get('data', {}).get('error', 'Unknown error')
                raise RuntimeError(f"Transfer failed: {error_msg}")

            logger.info(f"Transfer successful: ${amount_usd:.2f} to {subaccount_address[:10]}...")
            return True

        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            raise RuntimeError(f"Transfer failed: {e}") from e

    def transfer_from_subaccount(self, subaccount_address: str, amount_usd: float) -> bool:
        """
        Transfer USD from subaccount back to master.

        Args:
            subaccount_address: Source subaccount address
            amount_usd: Amount to transfer in USD

        Returns:
            True if successful

        Raises:
            RuntimeError: If transfer fails
        """
        if amount_usd <= 0:
            raise ValueError(f"Invalid transfer amount: {amount_usd}")

        usd_raw = int(amount_usd * 1_000_000)

        logger.info(f"Withdrawing ${amount_usd:.2f} from {subaccount_address[:10]}...")

        try:
            result = self.exchange.sub_account_transfer(
                sub_account_user=subaccount_address,
                is_deposit=False,  # False = subaccount -> master
                usd=usd_raw
            )

            if result.get('status') != 'ok':
                error_msg = result.get('response', {}).get('data', {}).get('error', 'Unknown error')
                raise RuntimeError(f"Withdrawal failed: {error_msg}")

            logger.info(f"Withdrawal successful: ${amount_usd:.2f} from {subaccount_address[:10]}...")
            return True

        except Exception as e:
            logger.error(f"Withdrawal failed: {e}")
            raise RuntimeError(f"Withdrawal failed: {e}") from e

    def check_and_topup(self, subaccount_id: int, subaccount_address: str) -> Dict:
        """
        Check subaccount balance and execute top-up if needed.

        Args:
            subaccount_id: Subaccount number (1, 2, 3, ...)
            subaccount_address: Subaccount wallet address

        Returns:
            Dict with result:
            {
                'action': 'none' | 'topup_full' | 'topup_partial' | 'skipped',
                'amount': float,
                'old_balance': float,
                'new_balance': float,
                'reason': str,
                'alert_level': 'info' | 'warning' | 'critical'
            }
        """
        sub_balance = self.get_subaccount_balance(subaccount_address)
        status = self.get_subaccount_status(sub_balance)

        result = {
            'subaccount_id': subaccount_id,
            'action': 'none',
            'amount': 0,
            'old_balance': sub_balance,
            'new_balance': sub_balance,
            'reason': '',
            'alert_level': 'info'
        }

        # Check if topup needed
        if status == SubaccountStatus.HEALTHY:
            result['reason'] = f"Balance ${sub_balance:.2f} >= min_operational ${self.min_operational}"
            return result

        # Calculate needed topup
        topup_needed = self.topup_target - sub_balance

        # Get master available funds
        master_balance = self.get_master_balance()
        master_available = master_balance - self.master_reserve

        if master_available <= 0:
            # Master has no available funds
            result['action'] = 'skipped'
            result['reason'] = (
                f"Master balance ${master_balance:.2f} below reserve ${self.master_reserve}"
            )
            result['alert_level'] = 'critical'

            if status == SubaccountStatus.INSUFFICIENT:
                result['reason'] += f" - Subaccount CANNOT TRADE (balance ${sub_balance:.2f})"

            logger.critical(
                f"Bot-{subaccount_id:03d} needs topup but master insufficient! "
                f"Master=${master_balance:.2f}, reserve=${self.master_reserve}"
            )
            return result

        if master_available >= topup_needed:
            # Full topup possible
            try:
                self.transfer_to_subaccount(subaccount_address, topup_needed)
                result['action'] = 'topup_full'
                result['amount'] = topup_needed
                result['new_balance'] = sub_balance + topup_needed
                result['reason'] = f"Topped up ${sub_balance:.2f} -> ${result['new_balance']:.2f}"
                result['alert_level'] = 'info'

                logger.info(
                    f"Bot-{subaccount_id:03d} topped up: "
                    f"${sub_balance:.2f} -> ${result['new_balance']:.2f}"
                )
            except Exception as e:
                result['action'] = 'skipped'
                result['reason'] = f"Transfer failed: {e}"
                result['alert_level'] = 'critical'
                logger.error(f"Topup failed for Bot-{subaccount_id:03d}: {e}")

        else:
            # Partial topup (master doesn't have enough)
            try:
                self.transfer_to_subaccount(subaccount_address, master_available)
                result['action'] = 'topup_partial'
                result['amount'] = master_available
                result['new_balance'] = sub_balance + master_available
                result['reason'] = (
                    f"Partial topup ${sub_balance:.2f} -> ${result['new_balance']:.2f} "
                    f"(master low: ${master_balance:.2f})"
                )
                result['alert_level'] = 'warning'

                logger.warning(
                    f"Bot-{subaccount_id:03d} partial topup: "
                    f"${sub_balance:.2f} -> ${result['new_balance']:.2f} "
                    f"(master balance low: ${master_balance:.2f})"
                )
            except Exception as e:
                result['action'] = 'skipped'
                result['reason'] = f"Transfer failed: {e}"
                result['alert_level'] = 'critical'
                logger.error(f"Partial topup failed for Bot-{subaccount_id:03d}: {e}")

        # Check if still insufficient after topup attempt
        if result['new_balance'] < self.min_tradeable:
            result['alert_level'] = 'critical'
            result['reason'] += f" - STILL BELOW TRADING MINIMUM ${self.min_tradeable}"
            logger.critical(
                f"Bot-{subaccount_id:03d} balance ${result['new_balance']:.2f} "
                f"BELOW TRADING MINIMUM - Rotator will skip"
            )

        return result

    def check_all_subaccounts(self) -> Dict:
        """
        Check all subaccounts and execute top-ups where needed.

        Called by scheduler daily.

        Returns:
            Dict with results:
            {
                'checked': int,
                'topped_up': int,
                'partial_topup': int,
                'skipped': int,
                'healthy': int,
                'alerts': List[Dict]
            }
        """
        subaccounts = self.subaccount_manager.list_subaccounts()

        results = {
            'checked': 0,
            'topped_up': 0,
            'partial_topup': 0,
            'skipped': 0,
            'healthy': 0,
            'alerts': []
        }

        logger.info(f"Checking {len(subaccounts)} subaccounts for funding")

        for i, sub in enumerate(subaccounts, 1):
            results['checked'] += 1

            check_result = self.check_and_topup(i, sub['address'])

            if check_result['action'] == 'none':
                results['healthy'] += 1
            elif check_result['action'] == 'topup_full':
                results['topped_up'] += 1
            elif check_result['action'] == 'topup_partial':
                results['partial_topup'] += 1
            elif check_result['action'] == 'skipped':
                results['skipped'] += 1

            # Collect alerts (warning and critical only)
            if check_result['alert_level'] in ('warning', 'critical'):
                results['alerts'].append({
                    'subaccount_id': i,
                    'name': sub['name'],
                    'level': check_result['alert_level'],
                    'message': check_result['reason']
                })

        logger.info(
            f"Fund check complete: checked={results['checked']}, "
            f"healthy={results['healthy']}, topped_up={results['topped_up']}, "
            f"partial={results['partial_topup']}, skipped={results['skipped']}"
        )

        return results
