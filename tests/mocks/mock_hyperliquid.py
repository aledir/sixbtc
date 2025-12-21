"""
Mock Hyperliquid Client for Testing

IMPORTANT: This mock NEVER makes real API calls or places real orders.
Used exclusively for testing in dry-run mode.
"""

from typing import Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MockPosition:
    """Mock position data"""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    unrealized_pnl: float = 0.0
    leverage: int = 1


@dataclass
class MockOrderResponse:
    """Mock order response"""
    order_id: str
    status: str  # 'filled', 'pending', 'rejected'
    filled_size: float
    filled_price: float


class MockHyperliquidClient:
    """
    Mock Hyperliquid Client for Testing

    Simulates exchange behavior without making real API calls.
    Always operates in dry_run mode.
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.dry_run = True  # ALWAYS True for mock
        self.current_subaccount = 1

        # Mock state
        self.positions: dict[int, list[MockPosition]] = {i: [] for i in range(1, 11)}
        self.orders: list[MockOrderResponse] = []
        self.account_values: dict[int, float] = {i: 10000.0 for i in range(1, 11)}

        logger.info("MockHyperliquidClient initialized (dry_run=True)")

    def switch_subaccount(self, subaccount_id: int) -> None:
        """Switch to different subaccount"""
        if not 1 <= subaccount_id <= 10:
            raise ValueError(f"Invalid subaccount_id: {subaccount_id}")

        self.current_subaccount = subaccount_id
        logger.debug(f"Switched to subaccount {subaccount_id}")

    def get_account_state(self) -> dict[str, Any]:
        """Get current account state"""
        return {
            'subaccount_id': self.current_subaccount,
            'account_value': self.account_values[self.current_subaccount],
            'positions': self.positions[self.current_subaccount],
            'available_balance': self.account_values[self.current_subaccount]
        }

    def get_positions(self) -> list[MockPosition]:
        """Get open positions for current subaccount"""
        return self.positions[self.current_subaccount].copy()

    def place_market_order(
        self,
        symbol: str,
        side: str,
        size: float,
        reduce_only: bool = False
    ) -> MockOrderResponse:
        """
        Mock market order (no real execution)

        Returns mock response simulating successful order
        """
        logger.info(
            f"[DRY RUN] Would place market order: {side} {size} {symbol} "
            f"(subaccount {self.current_subaccount})"
        )

        # Simulate order fill
        mock_fill_price = 42000.0  # Mock price
        order_id = f"mock_{len(self.orders) + 1}"

        response = MockOrderResponse(
            order_id=order_id,
            status='filled',
            filled_size=size,
            filled_price=mock_fill_price
        )

        self.orders.append(response)

        # Update mock positions
        if not reduce_only:
            position = MockPosition(
                symbol=symbol,
                side=side,
                size=size,
                entry_price=mock_fill_price
            )
            self.positions[self.current_subaccount].append(position)

        return response

    def close_position(self, symbol: str) -> MockOrderResponse:
        """Close position for symbol"""
        logger.info(f"[DRY RUN] Would close position: {symbol}")

        # Remove position from mock state
        self.positions[self.current_subaccount] = [
            p for p in self.positions[self.current_subaccount]
            if p.symbol != symbol
        ]

        return MockOrderResponse(
            order_id=f"close_mock_{len(self.orders) + 1}",
            status='filled',
            filled_size=0.1,
            filled_price=42000.0
        )

    def close_all_positions(self) -> None:
        """Close all positions for current subaccount"""
        logger.info(
            f"[DRY RUN] Would close all positions "
            f"(subaccount {self.current_subaccount})"
        )
        self.positions[self.current_subaccount] = []

    def cancel_all_orders(self) -> None:
        """Cancel all pending orders"""
        logger.info(
            f"[DRY RUN] Would cancel all pending orders "
            f"(subaccount {self.current_subaccount})"
        )
        # No-op in mock (no pending orders state)
        pass

    def get_market_price(self, symbol: str) -> float:
        """Get current market price (mock)"""
        return 42000.0  # Mock price

    def is_connected(self) -> bool:
        """Check if connected (always True for mock)"""
        return True
