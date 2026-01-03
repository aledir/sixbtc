"""
Trailing Stop Service for SixBTC

Implements delayed trailing stop with activation threshold:
1. DORMANT: SL stays at original level until price exceeds entry + activation_pct
2. ACTIVE: SL trails high-water mark at trail_pct distance

Adapted from sevenbtc's production implementation.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TrailingState:
    """State for a single trailing stop position"""
    coin: str
    subaccount_id: int
    side: str  # "long" | "short"
    entry_price: float
    activation_price: float  # entry +/- activation_pct
    high_water_mark: float  # Best price seen since activation
    current_sl_price: float
    current_sl_oid: Optional[str]
    position_size: float
    is_active: bool = False  # False = dormant, True = trailing active
    last_update_time: float = field(default_factory=time.time)
    trailing_stop_pct: float = 0.02  # Trail by this % from HWM
    trailing_activation_pct: float = 0.01  # Activate after this % profit


class TrailingService:
    """
    Real-time trailing stop service.

    Monitors positions and adjusts SL when:
    1. Price exceeds activation threshold (entry + activation_pct)
    2. New SL would be significantly better than current
    3. Cooldown period has elapsed

    Usage:
        service = TrailingService(client, config)
        await service.start()

        # On each price update:
        await service.on_price_update(coin, price)

        # When opening a position with trailing:
        service.register_trailing_position(coin, subaccount_id, ...)
    """

    def __init__(self, client: Any, config: dict):
        """
        Initialize TrailingService.

        Args:
            client: HyperliquidClient instance for order operations
            config: Config dict with trailing settings
        """
        self.client = client
        self.config = config

        # Extract trailing config - NO defaults (Fast Fail principle)
        trailing_config = config['risk']['trailing']

        self.enabled = trailing_config['enabled']
        self.min_adjustment_pct = trailing_config['min_adjustment_pct']
        self.update_cooldown_sec = trailing_config['update_cooldown_sec']
        self.breakeven_buffer_pct = trailing_config['breakeven_buffer_pct']

        # State tracking
        self.trailing_states: Dict[str, TrailingState] = {}  # key = "coin:subaccount_id"
        self.lock = asyncio.Lock()
        self._running = False

        if self.enabled:
            logger.info("TrailingService initialized")
            logger.info(f"  Min adjustment: {self.min_adjustment_pct*100:.2f}%")
            logger.info(f"  Cooldown: {self.update_cooldown_sec}s")
            logger.info(f"  Breakeven buffer: {self.breakeven_buffer_pct*100:.2f}%")

    async def start(self) -> None:
        """Start the trailing service."""
        if not self.enabled:
            logger.info("TrailingService disabled in config")
            return

        self._running = True
        logger.info("TrailingService started")

    async def stop(self) -> None:
        """Stop the trailing service."""
        self._running = False
        self.trailing_states.clear()
        logger.info("TrailingService stopped")

    def register_trailing_position(
        self,
        coin: str,
        subaccount_id: int,
        side: str,
        entry_price: float,
        position_size: float,
        current_sl_price: float,
        current_sl_oid: Optional[str],
        trailing_stop_pct: float = 0.02,
        trailing_activation_pct: float = 0.01,
    ) -> None:
        """
        Register a new position for trailing stop management.

        Called when opening a position with sl_type=TRAILING.

        Args:
            coin: Trading pair (e.g., 'BTC')
            subaccount_id: Subaccount ID
            side: 'long' or 'short'
            entry_price: Position entry price
            position_size: Position size
            current_sl_price: Initial stop loss price
            current_sl_oid: Stop loss order ID
            trailing_stop_pct: Trail distance (e.g., 0.02 = 2%)
            trailing_activation_pct: Activation threshold (e.g., 0.01 = 1%)
        """
        if not self.enabled:
            return

        key = f"{coin}:{subaccount_id}"

        # Calculate activation price
        if side == 'long':
            activation_price = entry_price * (1 + trailing_activation_pct)
        else:
            activation_price = entry_price * (1 - trailing_activation_pct)

        state = TrailingState(
            coin=coin,
            subaccount_id=subaccount_id,
            side=side,
            entry_price=entry_price,
            activation_price=activation_price,
            high_water_mark=entry_price,
            current_sl_price=current_sl_price,
            current_sl_oid=current_sl_oid,
            position_size=position_size,
            is_active=False,
            trailing_stop_pct=trailing_stop_pct,
            trailing_activation_pct=trailing_activation_pct,
        )

        self.trailing_states[key] = state
        logger.info(
            f"Trailing registered: {coin} subaccount={subaccount_id} "
            f"{side.upper()} @ ${entry_price:.2f}"
        )
        logger.info(
            f"  Activation: ${activation_price:.2f} ({trailing_activation_pct*100:.1f}% profit)"
        )
        logger.info(f"  Trail distance: {trailing_stop_pct*100:.1f}%")

    def unregister_position(self, coin: str, subaccount_id: int) -> None:
        """
        Unregister a position when it's closed.

        Args:
            coin: Trading pair
            subaccount_id: Subaccount ID
        """
        key = f"{coin}:{subaccount_id}"
        if key in self.trailing_states:
            state = self.trailing_states.pop(key)
            logger.info(
                f"Trailing unregistered: {coin} subaccount={subaccount_id} "
                f"(was_active={state.is_active})"
            )

    async def on_price_update(self, coin: str, price: float) -> None:
        """
        Handle real-time price update.

        Called for every price update from WebSocket or polling.

        Args:
            coin: Trading pair (e.g., 'BTC')
            price: Current price
        """
        if not self.enabled or not self._running:
            return

        async with self.lock:
            # Check all subaccounts with this coin
            for key, state in list(self.trailing_states.items()):
                if not key.startswith(f"{coin}:"):
                    continue

                await self._process_price_update(state, price)

    async def _process_price_update(self, state: TrailingState, price: float) -> None:
        """Process price update for a single position."""
        # Check activation
        if not state.is_active:
            if self._check_activation(state, price):
                state.is_active = True
                state.high_water_mark = price
                logger.info(
                    f"Trailing ACTIVATED: {state.coin} @ ${price:.2f} "
                    f"(threshold ${state.activation_price:.2f})"
                )
            return

        # Update high water mark
        if state.side == 'long':
            if price > state.high_water_mark:
                state.high_water_mark = price
        else:  # short
            if price < state.high_water_mark:
                state.high_water_mark = price

        # Calculate new SL
        new_sl = self._calculate_new_sl(state)

        # Check if update is significant enough
        if not self._is_significant_update(state, new_sl):
            return

        # Check cooldown
        if time.time() - state.last_update_time < self.update_cooldown_sec:
            return

        # Execute update (outside lock context if needed)
        await self._execute_sl_update(state, new_sl)

    def _check_activation(self, state: TrailingState, price: float) -> bool:
        """Check if price has crossed activation threshold."""
        if state.side == 'long':
            return price >= state.activation_price
        else:  # short
            return price <= state.activation_price

    def _calculate_new_sl(self, state: TrailingState) -> float:
        """
        Calculate new SL price based on high water mark.

        Applies breakeven buffer to ensure we don't exit at exact breakeven
        (which would be a loss after fees).
        """
        trail_pct = state.trailing_stop_pct

        if state.side == 'long':
            theoretical_sl = state.high_water_mark * (1 - trail_pct)
            # Floor at entry + buffer (minimum profit)
            floor_price = state.entry_price * (1 + self.breakeven_buffer_pct)
            return max(theoretical_sl, floor_price)
        else:  # short
            theoretical_sl = state.high_water_mark * (1 + trail_pct)
            # Ceiling at entry - buffer
            ceiling_price = state.entry_price * (1 - self.breakeven_buffer_pct)
            return min(theoretical_sl, ceiling_price)

    def _is_significant_update(self, state: TrailingState, new_sl: float) -> bool:
        """Check if the SL update is significant enough to execute."""
        if state.side == 'long':
            # For long: new SL must be higher than current + min_adjustment
            if state.current_sl_price <= 0:
                return True
            improvement = (new_sl - state.current_sl_price) / state.current_sl_price
            return improvement >= self.min_adjustment_pct
        else:  # short
            # For short: new SL must be lower than current - min_adjustment
            if state.current_sl_price <= 0:
                return True
            improvement = (state.current_sl_price - new_sl) / state.current_sl_price
            return improvement >= self.min_adjustment_pct

    async def _execute_sl_update(self, state: TrailingState, new_sl: float) -> bool:
        """
        Execute the SL update via client.

        Uses atomic pattern: place new → verify → cancel old.
        """
        old_sl = state.current_sl_price
        coin = state.coin

        logger.info(
            f"Trailing update: {coin} SL ${old_sl:.2f} -> ${new_sl:.2f} "
            f"(HWM: ${state.high_water_mark:.2f})"
        )

        try:
            # Use client's atomic update method (place new → cancel old)
            # This is safer: if placement fails, old SL still protects position
            result = self.client.update_sl_atomic(
                symbol=coin,
                new_stop_loss=new_sl,
                old_order_id=state.current_sl_oid,
                size=state.position_size,
            )

            if result:
                # Update state
                state.current_sl_price = new_sl
                state.current_sl_oid = result.get('order_id', state.current_sl_oid)
                state.last_update_time = time.time()
                logger.info(f"Trailing update SUCCESS: {coin} SL now ${new_sl:.2f}")
                return True
            else:
                logger.error(f"Trailing update FAILED: {coin}")
                return False

        except Exception as e:
            logger.error(f"Error executing trailing update for {coin}: {e}")
            return False

    def get_trailing_status(self) -> Dict[str, dict]:
        """Get current trailing status for all positions (for debugging/dashboard)."""
        status = {}
        for key, state in self.trailing_states.items():
            status[key] = {
                'coin': state.coin,
                'subaccount_id': state.subaccount_id,
                'side': state.side,
                'entry_price': state.entry_price,
                'activation_price': state.activation_price,
                'high_water_mark': state.high_water_mark,
                'current_sl': state.current_sl_price,
                'is_active': state.is_active,
                'trail_pct': state.trailing_stop_pct,
            }
        return status
