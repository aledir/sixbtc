"""
Statistics Service - True P&L using allocated_capital as base.

This service calculates statistics that are immune to:
- Manual deposits/withdrawals
- Internal transfers between subaccounts
- peak_balance corruption

Formula: True P&L = Current Balance - Allocated Capital
"""

from datetime import datetime, UTC
from typing import Dict, Optional, TYPE_CHECKING

from src.database import get_session, Subaccount
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.executor.hyperliquid_client import HyperliquidClient
    from src.data.hyperliquid_websocket import HyperliquidDataProvider

logger = get_logger(__name__)


class StatisticsService:
    """
    Calculate true P&L using allocated_capital as the base.

    This approach is immune to:
    1. Manual deposits/withdrawals (they don't change allocated_capital)
    2. Internal transfers between subaccounts
    3. peak_balance corruption bugs

    Formula: True P&L = current_balance - allocated_capital
    """

    def __init__(
        self,
        client: 'HyperliquidClient',
        data_provider: Optional['HyperliquidDataProvider'] = None
    ):
        """
        Initialize statistics service.

        Args:
            client: HyperliquidClient for balance queries
            data_provider: Optional WebSocket data provider for real-time balances
        """
        self.client = client
        self.data_provider = data_provider
        logger.info("StatisticsService initialized")

    def _get_subaccount_data(self, subaccount_id: int) -> Dict[str, float]:
        """
        Get subaccount data from database.

        Args:
            subaccount_id: Subaccount number

        Returns:
            Dict with allocated_capital, current_balance, peak_balance
        """
        with get_session() as session:
            sa = session.query(Subaccount).filter(
                Subaccount.id == subaccount_id
            ).first()

            if not sa:
                logger.warning(f"Subaccount {subaccount_id} not found in database")
                return {
                    "allocated_capital": 0.0,
                    "current_balance": 0.0,
                    "peak_balance": 0.0,
                }

            return {
                "allocated_capital": sa.allocated_capital or 0.0,
                "current_balance": sa.current_balance or 0.0,
                "peak_balance": sa.peak_balance or 0.0,
            }

    def _get_current_balance_from_hl(self, subaccount_id: int) -> float:
        """
        Get current balance directly from Hyperliquid (source of truth).

        Args:
            subaccount_id: Subaccount number

        Returns:
            Current account balance
        """
        try:
            return self.client.get_account_balance(subaccount_id)
        except Exception as e:
            logger.error(f"Failed to get balance from HL for subaccount {subaccount_id}: {e}")
            # Fallback to DB
            data = self._get_subaccount_data(subaccount_id)
            return data["current_balance"]

    def get_true_pnl(self, subaccount_id: int) -> Dict[str, float]:
        """
        Calculate true P&L for a subaccount.

        Formula: True P&L = Current Balance - Allocated Capital

        This is immune to manual deposits/withdrawals and internal transfers
        because allocated_capital is set once at deployment and never changes.

        Args:
            subaccount_id: Subaccount number

        Returns:
            Dict with:
                current_balance: Current account value from Hyperliquid
                allocated_capital: Initial capital allocated to this subaccount
                true_pnl: Current balance - allocated capital (profit/loss in $)
                true_pnl_pct: True P&L as percentage of allocated capital
        """
        # Get allocated_capital from DB (set once at deployment)
        db_data = self._get_subaccount_data(subaccount_id)
        allocated_capital = db_data["allocated_capital"]

        # Get current balance from Hyperliquid (source of truth)
        current_balance = self._get_current_balance_from_hl(subaccount_id)

        # Calculate true P&L
        true_pnl = current_balance - allocated_capital

        # Calculate percentage (avoid division by zero)
        if allocated_capital > 0:
            true_pnl_pct = (true_pnl / allocated_capital) * 100
        else:
            true_pnl_pct = 0.0

        return {
            "current_balance": current_balance,
            "allocated_capital": allocated_capital,
            "true_pnl": true_pnl,
            "true_pnl_pct": true_pnl_pct,
            # Legacy fields for backwards compatibility
            "net_deposits": allocated_capital,
            "total_deposits": allocated_capital,
            "total_withdrawals": 0.0,
        }

    def get_true_drawdown(self, subaccount_id: int) -> Dict[str, float]:
        """
        Calculate drawdown relative to allocated_capital.

        Formula:
        - If profitable (current >= allocated): DD = 0%
        - If losing (current < allocated): DD = (allocated - current) / allocated

        Args:
            subaccount_id: Subaccount number

        Returns:
            Dict with:
                current_balance: Current account value
                allocated_capital: Initial capital
                drawdown: Drawdown percentage (0.0 to 1.0)
                drawdown_pct: Drawdown as percentage string
                is_in_drawdown: True if currently losing money
        """
        stats = self.get_true_pnl(subaccount_id)

        current_balance = stats["current_balance"]
        allocated_capital = stats["allocated_capital"]
        true_pnl = stats["true_pnl"]

        # Calculate drawdown
        if true_pnl >= 0:
            # In profit or break-even, no drawdown
            drawdown = 0.0
        elif allocated_capital > 0:
            # In loss: drawdown = loss / capital
            drawdown = abs(true_pnl) / allocated_capital
        else:
            # No capital allocated, can't calculate
            drawdown = 0.0

        # Cap at 100%
        drawdown = min(drawdown, 1.0)

        return {
            "current_balance": current_balance,
            "allocated_capital": allocated_capital,
            "net_deposits": allocated_capital,  # Legacy compatibility
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
                    "allocated_capital": 0.0,
                    "true_pnl": 0.0,
                    "true_pnl_pct": 0.0,
                    "error": str(e),
                }

        return results

    def get_portfolio_stats(self) -> Dict[str, float]:
        """
        Get portfolio-level statistics across all active subaccounts.

        Returns:
            Dict with:
                total_allocated: Sum of all allocated_capital
                total_current: Sum of all current_balance
                total_pnl: Total P&L in $
                total_pnl_pct: Total P&L as percentage
                drawdown: Portfolio drawdown (0.0 to 1.0)
        """
        with get_session() as session:
            subaccounts = session.query(Subaccount).filter(
                Subaccount.status.in_(['ACTIVE', 'PAUSED'])
            ).all()

            if not subaccounts:
                return {
                    "total_allocated": 0.0,
                    "total_current": 0.0,
                    "total_pnl": 0.0,
                    "total_pnl_pct": 0.0,
                    "drawdown": 0.0,
                }

            total_allocated = sum(sa.allocated_capital or 0 for sa in subaccounts)
            total_current = sum(sa.current_balance or 0 for sa in subaccounts)

            total_pnl = total_current - total_allocated

            if total_allocated > 0:
                total_pnl_pct = (total_pnl / total_allocated) * 100
                if total_pnl < 0:
                    drawdown = abs(total_pnl) / total_allocated
                else:
                    drawdown = 0.0
            else:
                total_pnl_pct = 0.0
                drawdown = 0.0

            return {
                "total_allocated": total_allocated,
                "total_current": total_current,
                "total_pnl": total_pnl,
                "total_pnl_pct": total_pnl_pct,
                "drawdown": min(drawdown, 1.0),
                "subaccount_count": len(subaccounts),
            }
