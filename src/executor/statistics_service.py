"""
Statistics Service - True P&L using Hyperliquid as Source of Truth.

This service calculates statistics that are immune to manual deposits/withdrawals.
Formula: True P&L = Current Account Value - Net Deposits

Uses:
- WebSocket (webData2): Real-time balance updates
- REST (ledger API): Deposit/withdrawal history (cached 5 min)
"""

import time
from datetime import datetime, UTC, timedelta
from typing import Dict, Optional, TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.executor.hyperliquid_client import HyperliquidClient
    from src.data.hyperliquid_websocket import HyperliquidDataProvider

logger = get_logger(__name__)


class StatisticsService:
    """
    Calculate true P&L using Hyperliquid as source of truth.

    This service is immune to manual deposits/withdrawals corrupting statistics.
    All calculations use the formula: True P&L = Current Balance - Net Deposits.
    """

    def __init__(
        self,
        client: 'HyperliquidClient',
        data_provider: Optional['HyperliquidDataProvider'] = None
    ):
        """
        Initialize statistics service.

        Args:
            client: HyperliquidClient for ledger API calls
            data_provider: Optional WebSocket data provider for real-time balances
        """
        self.client = client
        self.data_provider = data_provider

        # Cache for net deposits per subaccount
        # Key: subaccount_id, Value: (data_dict, timestamp)
        self._net_deposits_cache: Dict[int, tuple] = {}
        self.cache_ttl = timedelta(minutes=5)

        logger.info("StatisticsService initialized")

    def _get_cached_net_deposits(self, subaccount_id: int) -> Optional[Dict[str, float]]:
        """
        Get cached net deposits if still valid.

        Args:
            subaccount_id: Subaccount number

        Returns:
            Cached data or None if expired/missing
        """
        if subaccount_id not in self._net_deposits_cache:
            return None

        data, cache_time = self._net_deposits_cache[subaccount_id]
        if datetime.now(UTC) - cache_time > self.cache_ttl:
            return None

        return data

    def _fetch_net_deposits(self, subaccount_id: int) -> Dict[str, float]:
        """
        Fetch net deposits from Hyperliquid ledger API and cache.

        Args:
            subaccount_id: Subaccount number

        Returns:
            Dict with total_deposits, total_withdrawals, net_deposits
        """
        # Check cache first
        cached = self._get_cached_net_deposits(subaccount_id)
        if cached is not None:
            return cached

        # Fetch from API
        try:
            net_deposits_data = self.client.get_net_deposits(subaccount_id)

            # Cache the result
            self._net_deposits_cache[subaccount_id] = (net_deposits_data, datetime.now(UTC))

            logger.debug(
                f"Subaccount {subaccount_id}: fetched net deposits - "
                f"deposits=${net_deposits_data.get('total_deposits', 0):.2f}, "
                f"withdrawals=${net_deposits_data.get('total_withdrawals', 0):.2f}, "
                f"net=${net_deposits_data.get('net_deposits', 0):.2f}"
            )

            return net_deposits_data

        except Exception as e:
            logger.warning(f"Failed to fetch net deposits for subaccount {subaccount_id}: {e}")

            # Return cached data if available (even if expired)
            if subaccount_id in self._net_deposits_cache:
                data, _ = self._net_deposits_cache[subaccount_id]
                logger.debug(f"Using stale cached net deposits for subaccount {subaccount_id}")
                return data

            # No data available
            return {
                "total_deposits": 0.0,
                "total_withdrawals": 0.0,
                "net_deposits": 0.0,
                "transaction_count": 0,
            }

    def _get_current_balance(self, subaccount_id: int) -> float:
        """
        Get current balance, preferring WebSocket data.

        Args:
            subaccount_id: Subaccount number

        Returns:
            Current account balance
        """
        # TODO: Use WebSocket data_provider when available (webData2)
        # For now, use REST API
        try:
            return self.client.get_account_balance(subaccount_id)
        except Exception as e:
            logger.error(f"Failed to get balance for subaccount {subaccount_id}: {e}")
            return 0.0

    def get_true_pnl(self, subaccount_id: int) -> Dict[str, float]:
        """
        Calculate true P&L for a subaccount.

        Formula: True P&L = Current Account Value - Net Deposits

        This is immune to manual deposits/withdrawals:
        - Deposit $100: balance +$100, net_deposits +$100, true_pnl unchanged
        - Withdraw $50: balance -$50, net_deposits -$50, true_pnl unchanged
        - Trading profit $20: balance +$20, net_deposits unchanged, true_pnl +$20

        Args:
            subaccount_id: Subaccount number

        Returns:
            Dict with:
                current_balance: Current account value from Hyperliquid
                net_deposits: Total deposits minus withdrawals
                true_pnl: Current balance - net deposits
                true_pnl_pct: True P&L as percentage of net deposits
        """
        current_balance = self._get_current_balance(subaccount_id)
        net_deposits_data = self._fetch_net_deposits(subaccount_id)
        net_deposits = net_deposits_data.get("net_deposits", 0.0)

        # Calculate true P&L
        true_pnl = current_balance - net_deposits

        # Calculate percentage (avoid division by zero)
        if net_deposits > 0:
            true_pnl_pct = (true_pnl / net_deposits) * 100
        else:
            true_pnl_pct = 0.0

        return {
            "current_balance": current_balance,
            "net_deposits": net_deposits,
            "total_deposits": net_deposits_data.get("total_deposits", 0.0),
            "total_withdrawals": net_deposits_data.get("total_withdrawals", 0.0),
            "true_pnl": true_pnl,
            "true_pnl_pct": true_pnl_pct,
        }

    def get_true_drawdown(self, subaccount_id: int) -> Dict[str, float]:
        """
        Calculate drawdown based on net deposits (not peak balance).

        This method calculates drawdown relative to the capital invested,
        not relative to a possibly-corrupted peak balance.

        Formula:
        - If profitable (true_pnl >= 0): DD = 0%
        - If losing (true_pnl < 0): DD = -true_pnl / net_deposits

        Args:
            subaccount_id: Subaccount number

        Returns:
            Dict with:
                current_balance: Current account value
                net_deposits: Capital invested
                drawdown: Drawdown percentage (0.0 to 1.0)
                drawdown_pct: Drawdown as percentage string
                is_in_drawdown: True if currently losing money
        """
        stats = self.get_true_pnl(subaccount_id)

        current_balance = stats["current_balance"]
        net_deposits = stats["net_deposits"]
        true_pnl = stats["true_pnl"]

        # Calculate drawdown
        if true_pnl >= 0:
            # In profit, no drawdown
            drawdown = 0.0
        elif net_deposits > 0:
            # In loss: drawdown = loss / capital
            drawdown = abs(true_pnl) / net_deposits
        else:
            # No deposits, can't calculate
            drawdown = 0.0

        return {
            "current_balance": current_balance,
            "net_deposits": net_deposits,
            "true_pnl": true_pnl,
            "drawdown": drawdown,
            "drawdown_pct": f"{drawdown * 100:.2f}%",
            "is_in_drawdown": true_pnl < 0,
        }

    def get_all_subaccounts_stats(self, subaccount_ids: list) -> Dict[int, Dict]:
        """
        Get statistics for all specified subaccounts.

        Args:
            subaccount_ids: List of subaccount numbers

        Returns:
            Dict mapping subaccount_id to stats
        """
        results = {}
        for sa_id in subaccount_ids:
            try:
                results[sa_id] = self.get_true_pnl(sa_id)
            except Exception as e:
                logger.error(f"Failed to get stats for subaccount {sa_id}: {e}")
                results[sa_id] = {
                    "current_balance": 0.0,
                    "net_deposits": 0.0,
                    "true_pnl": 0.0,
                    "true_pnl_pct": 0.0,
                    "error": str(e),
                }

        return results

    def invalidate_cache(self, subaccount_id: Optional[int] = None) -> None:
        """
        Invalidate cached net deposits.

        Call this after user performs a deposit/withdrawal to force refresh.

        Args:
            subaccount_id: Specific subaccount to invalidate, or None for all
        """
        if subaccount_id is not None:
            if subaccount_id in self._net_deposits_cache:
                del self._net_deposits_cache[subaccount_id]
                logger.debug(f"Invalidated cache for subaccount {subaccount_id}")
        else:
            self._net_deposits_cache.clear()
            logger.debug("Invalidated all cached net deposits")
