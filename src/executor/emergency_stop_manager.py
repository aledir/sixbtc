"""
Emergency Stop Manager - Multi-Scope Emergency Stop Logic

Manages emergency stops at four scopes:
1. PORTFOLIO: All subaccounts combined
   - daily_loss >= 10% → halt_entries (reset at midnight UTC)
   - drawdown >= 20% → force_close (reset after 48h + rotation)
2. SUBACCOUNT: Single slot 1-10
   - drawdown >= 25% → halt_entries (reset on rotation)
3. STRATEGY: Single strategy
   - consecutive_losses >= 10 → halt_entries (reset after 24h)
4. SYSTEM: System-level issues
   - data_stale > 2min → halt_entries (reset when data valid)

Actions:
- halt_entries: Block new trades, let existing run to SL/TP
- force_close: Close ALL positions immediately (panic button)

Rule #4b: WebSocket First
- When data_provider is set, data_stale check uses WebSocket timestamp
- This is the real source of truth for data freshness
"""

import logging
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.database.connection import get_session
from src.database.models import (
    EmergencyStopState,
    Strategy,
    Subaccount,
    Trade,
)

# TYPE_CHECKING imports to avoid circular dependencies
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.executor.statistics_service import StatisticsService

logger = logging.getLogger(__name__)


class EmergencyStopManager:
    """
    Centralized emergency stop logic with multi-scope support.

    Thread-safe via database state. No in-memory caching of state.
    Throttled checks to reduce database load.
    """

    # Actions
    ACTION_HALT_ENTRIES = "halt_entries"
    ACTION_FORCE_CLOSE = "force_close"

    # Scopes
    SCOPE_PORTFOLIO = "portfolio"
    SCOPE_SUBACCOUNT = "subaccount"
    SCOPE_STRATEGY = "strategy"
    SCOPE_SYSTEM = "system"

    # Reset triggers
    RESET_MIDNIGHT_UTC = "midnight_utc"
    RESET_COOLDOWN_48H_ROTATION = "cooldown_48h_rotation"
    RESET_ROTATION = "rotation"
    RESET_24H = "24h"
    RESET_DATA_VALID = "data_valid"

    def __init__(
        self,
        config: dict,
        hyperliquid_client=None,
        data_provider=None,
        statistics_service: Optional['StatisticsService'] = None
    ):
        """
        Initialize with config thresholds.

        Args:
            config: Full config dict with 'risk.emergency' section
            hyperliquid_client: Optional client for force_close action
            data_provider: HyperliquidDataProvider for WebSocket health check (Rule #4b)
            statistics_service: Optional StatisticsService for true P&L stats
        """
        emergency = config['risk']['emergency']
        cooldowns = config['risk'].get('emergency_cooldowns', {})

        # WebSocket data provider for staleness check (Rule #4b)
        self.data_provider = data_provider

        # Statistics service for true P&L calculation (Hyperliquid as source of truth)
        self.statistics_service = statistics_service

        # Thresholds
        self.max_portfolio_drawdown = emergency['max_portfolio_drawdown']
        self.max_daily_loss = emergency['max_daily_loss']
        self.max_subaccount_drawdown = emergency['max_subaccount_drawdown']
        self.max_consecutive_losses = emergency['max_consecutive_losses']
        self.data_stale_seconds = emergency.get('data_stale_seconds', 120)
        self.rotation_loss_threshold = emergency.get('rotation_loss_threshold', 0.0)

        # Cooldown periods
        self.portfolio_dd_cooldown_hours = cooldowns.get('portfolio_dd_hours', 48)
        self.strategy_cooldown_hours = cooldowns.get('strategy_hours', 24)

        # Throttling
        self.check_interval_seconds = 60
        self.last_check_time: Optional[datetime] = None

        # Client for force_close
        self.client = hyperliquid_client

        logger.info(
            f"EmergencyStopManager initialized: "
            f"portfolio_dd={self.max_portfolio_drawdown:.0%}, "
            f"daily_loss={self.max_daily_loss:.0%}, "
            f"subaccount_dd={self.max_subaccount_drawdown:.0%}, "
            f"consecutive_losses={self.max_consecutive_losses}"
        )

    # =========================================================================
    # STATE CHECKING
    # =========================================================================

    def is_stopped(self, scope: str, scope_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if scope is currently stopped.

        Returns:
            (is_stopped, reason) - reason is None if not stopped
        """
        with get_session() as session:
            state = session.query(EmergencyStopState).filter(
                EmergencyStopState.scope == scope,
                EmergencyStopState.scope_id == scope_id
            ).first()

            if state and state.is_stopped:
                return (True, state.stop_reason)
            return (False, None)

    def is_portfolio_stopped(self) -> Tuple[bool, Optional[str]]:
        """Check if portfolio-level stop is active."""
        return self.is_stopped(self.SCOPE_PORTFOLIO, "global")

    def is_subaccount_stopped(self, subaccount_id: int) -> Tuple[bool, Optional[str]]:
        """Check if subaccount-level stop is active."""
        return self.is_stopped(self.SCOPE_SUBACCOUNT, str(subaccount_id))

    def is_strategy_stopped(self, strategy_id: UUID) -> Tuple[bool, Optional[str]]:
        """Check if strategy-level stop is active."""
        return self.is_stopped(self.SCOPE_STRATEGY, str(strategy_id))

    def is_system_stopped(self) -> Tuple[bool, Optional[str]]:
        """Check if system-level stop is active."""
        return self.is_stopped(self.SCOPE_SYSTEM, "data_feed")

    def can_trade(self, subaccount_id: int, strategy_id: UUID) -> Dict:
        """
        Check if trading is allowed for this subaccount/strategy combination.

        Checks all scopes in order of severity: portfolio > system > subaccount > strategy

        Returns:
            {
                'allowed': bool,
                'blocked_by': ['portfolio_daily_loss', 'subaccount_dd', ...],
                'reasons': ['Daily loss 10.5% >= 10%', ...],
                'cooldown_until': datetime or None
            }
        """
        blocked_by = []
        reasons = []
        max_cooldown = None

        with get_session() as session:
            # Check all relevant stops
            checks = [
                (self.SCOPE_PORTFOLIO, "global"),
                (self.SCOPE_SYSTEM, "data_feed"),
                (self.SCOPE_SUBACCOUNT, str(subaccount_id)),
                (self.SCOPE_STRATEGY, str(strategy_id)),
            ]

            for scope, scope_id in checks:
                state = session.query(EmergencyStopState).filter(
                    EmergencyStopState.scope == scope,
                    EmergencyStopState.scope_id == scope_id
                ).first()

                if state and state.is_stopped:
                    blocked_by.append(f"{scope}_{scope_id}")
                    reasons.append(state.stop_reason or "Unknown reason")
                    if state.cooldown_until:
                        if max_cooldown is None or state.cooldown_until > max_cooldown:
                            max_cooldown = state.cooldown_until

        return {
            'allowed': len(blocked_by) == 0,
            'blocked_by': blocked_by,
            'reasons': reasons,
            'cooldown_until': max_cooldown
        }

    # =========================================================================
    # CONDITION CHECKING (throttled)
    # =========================================================================

    def check_all_conditions(self) -> List[Dict]:
        """
        Check all emergency conditions and return triggered stops.

        Throttled to check every 60 seconds to reduce database load.

        Returns:
            List of triggered stops with scope, scope_id, reason, action, reset_trigger
        """
        now = datetime.now(UTC)

        # Throttle checks
        if self.last_check_time is not None:
            elapsed = (now - self.last_check_time).total_seconds()
            if elapsed < self.check_interval_seconds:
                return []

        self.last_check_time = now
        triggered = []

        # 1. Portfolio daily loss
        result = self._check_portfolio_daily_loss()
        if result:
            triggered.append(result)

        # 2. Portfolio drawdown
        result = self._check_portfolio_drawdown()
        if result:
            triggered.append(result)

        # 3. Subaccount drawdowns
        results = self._check_subaccount_drawdowns()
        triggered.extend(results)

        # 4. Strategy consecutive losses
        results = self._check_strategy_consecutive_losses()
        triggered.extend(results)

        # 5. Data stale check
        result = self._check_data_stale()
        if result:
            triggered.append(result)

        return triggered

    def _check_portfolio_daily_loss(self) -> Optional[Dict]:
        """Check portfolio daily loss against threshold."""
        with get_session() as session:
            # Check if already stopped for daily loss
            existing = session.query(EmergencyStopState).filter(
                EmergencyStopState.scope == self.SCOPE_PORTFOLIO,
                EmergencyStopState.scope_id == "global",
                EmergencyStopState.is_stopped == True,
                EmergencyStopState.reset_trigger == self.RESET_MIDNIGHT_UTC
            ).first()
            if existing:
                return None  # Already stopped

            # Sum daily_pnl_usd across all active subaccounts
            subaccounts = session.query(Subaccount).filter(
                Subaccount.status.in_(['ACTIVE', 'PAUSED'])
            ).all()

            total_capital = sum(sa.allocated_capital or 0 for sa in subaccounts)
            total_daily_pnl = sum(sa.daily_pnl_usd or 0 for sa in subaccounts)

            if total_capital <= 0:
                return None

            # Daily loss is negative PnL as percentage
            daily_loss_pct = -total_daily_pnl / total_capital if total_daily_pnl < 0 else 0

            if daily_loss_pct >= self.max_daily_loss:
                return {
                    'scope': self.SCOPE_PORTFOLIO,
                    'scope_id': 'global',
                    'reason': f"Daily loss {daily_loss_pct:.1%} >= {self.max_daily_loss:.0%}",
                    'action': self.ACTION_HALT_ENTRIES,
                    'reset_trigger': self.RESET_MIDNIGHT_UTC
                }

        return None

    def _check_portfolio_drawdown(self) -> Optional[Dict]:
        """
        Check portfolio drawdown against threshold.

        Portfolio drawdown is calculated relative to total allocated_capital:
        DD = (total_allocated - total_current) / total_allocated

        This approach is immune to peak_balance corruption.
        """
        with get_session() as session:
            # Check if already stopped for DD
            existing = session.query(EmergencyStopState).filter(
                EmergencyStopState.scope == self.SCOPE_PORTFOLIO,
                EmergencyStopState.scope_id == "global",
                EmergencyStopState.is_stopped == True,
                EmergencyStopState.reset_trigger == self.RESET_COOLDOWN_48H_ROTATION
            ).first()
            if existing:
                return None  # Already stopped

            subaccounts = session.query(Subaccount).filter(
                Subaccount.status.in_(['ACTIVE', 'PAUSED'])
            ).all()

            if not subaccounts:
                return None

            # Sum up allocated capital and current balance across all subaccounts
            # CRITICAL: Only include subaccounts with actual balance data
            # Skip subaccounts where current_balance IS NULL (never used)
            subaccounts_with_balance = [
                sa for sa in subaccounts
                if sa.current_balance is not None and sa.allocated_capital
            ]

            if not subaccounts_with_balance:
                return None  # No subaccounts with balance data yet

            total_allocated = sum(sa.allocated_capital for sa in subaccounts_with_balance)
            total_current = sum(sa.current_balance for sa in subaccounts_with_balance)

            if total_allocated <= 0:
                return None

            # Calculate portfolio drawdown
            if total_current >= total_allocated:
                drawdown = 0.0  # In profit or break-even
            else:
                drawdown = (total_allocated - total_current) / total_allocated

            # Sanity check
            drawdown = min(drawdown, 1.0)

            if drawdown >= self.max_portfolio_drawdown:
                return {
                    'scope': self.SCOPE_PORTFOLIO,
                    'scope_id': 'global',
                    'reason': f"Portfolio DD {drawdown:.1%} >= {self.max_portfolio_drawdown:.0%}",
                    'action': self.ACTION_FORCE_CLOSE,
                    'reset_trigger': self.RESET_COOLDOWN_48H_ROTATION
                }

        return None

    def _check_subaccount_drawdowns(self) -> List[Dict]:
        """
        Check each subaccount's drawdown against threshold.

        Drawdown is calculated relative to allocated_capital (initial funding):
        DD = (allocated_capital - current_balance) / allocated_capital

        This approach is immune to peak_balance corruption because:
        1. allocated_capital is set once when subaccount is funded
        2. It represents the true capital at risk for this subaccount
        3. Internal transfers between subaccounts don't affect it
        """
        triggered = []

        with get_session() as session:
            subaccounts = session.query(Subaccount).filter(
                Subaccount.status == 'ACTIVE'
            ).all()

            for sa in subaccounts:
                # Check if already stopped
                existing = session.query(EmergencyStopState).filter(
                    EmergencyStopState.scope == self.SCOPE_SUBACCOUNT,
                    EmergencyStopState.scope_id == str(sa.id),
                    EmergencyStopState.is_stopped == True
                ).first()
                if existing:
                    continue

                # Use allocated_capital as base (immune to peak_balance corruption)
                # allocated_capital = what we initially funded this subaccount with
                base_capital = sa.allocated_capital or 0.0

                if base_capital <= 0:
                    # No capital allocated yet, skip
                    continue

                # CRITICAL: Distinguish NULL (never used) vs 0 (real 100% DD)
                # - current_balance IS NULL → subaccount created but never traded, skip DD calc
                # - current_balance == 0 → real 100% drawdown, must trigger stop
                if sa.current_balance is None:
                    # Subaccount never used - no balance data yet, skip
                    continue

                # Get current balance (can be 0 for real 100% DD)
                current = sa.current_balance
                if self.data_provider and self.data_provider.account_state:
                    # TODO: WebSocket shows main account, not subaccounts
                    # For now, rely on DB balance which is synced from REST API
                    pass

                # Calculate drawdown: how much have we lost relative to initial capital
                if current >= base_capital:
                    drawdown = 0.0  # In profit or break-even, no drawdown
                else:
                    drawdown = (base_capital - current) / base_capital

                # Sanity check: drawdown should never exceed 100%
                # (can happen if current_balance is negative due to fees/funding)
                drawdown = min(drawdown, 1.0)

                if drawdown >= self.max_subaccount_drawdown:
                    triggered.append({
                        'scope': self.SCOPE_SUBACCOUNT,
                        'scope_id': str(sa.id),
                        'reason': f"Subaccount {sa.id} DD {drawdown:.1%} >= {self.max_subaccount_drawdown:.0%}",
                        'action': self.ACTION_HALT_ENTRIES,
                        'reset_trigger': self.RESET_ROTATION
                    })

        return triggered

    def _check_strategy_consecutive_losses(self) -> List[Dict]:
        """Check each LIVE strategy's consecutive losses."""
        triggered = []

        with get_session() as session:
            strategies = session.query(Strategy).filter(
                Strategy.status == 'LIVE'
            ).all()

            for strat in strategies:
                # Check if already stopped
                existing = session.query(EmergencyStopState).filter(
                    EmergencyStopState.scope == self.SCOPE_STRATEGY,
                    EmergencyStopState.scope_id == str(strat.id),
                    EmergencyStopState.is_stopped == True
                ).first()
                if existing:
                    continue

                consec = self._count_consecutive_losses(strat.id, session)

                if consec >= self.max_consecutive_losses:
                    triggered.append({
                        'scope': self.SCOPE_STRATEGY,
                        'scope_id': str(strat.id),
                        'reason': f"Strategy {strat.name} consecutive losses {consec} >= {self.max_consecutive_losses}",
                        'action': self.ACTION_HALT_ENTRIES,
                        'reset_trigger': self.RESET_24H
                    })

        return triggered

    def _count_consecutive_losses(self, strategy_id: UUID, session: Session) -> int:
        """Count current streak of consecutive losing trades."""
        limit = self.max_consecutive_losses + 5

        trades = (
            session.query(Trade)
            .filter(
                Trade.strategy_id == strategy_id,
                Trade.exit_time.isnot(None)
            )
            .order_by(Trade.exit_time.desc())
            .limit(limit)
            .all()
        )

        consecutive = 0
        for trade in trades:
            if trade.pnl_usd is not None and trade.pnl_usd < 0:
                consecutive += 1
            else:
                break

        return consecutive

    def _check_data_stale(self) -> Optional[Dict]:
        """
        Check if data feed is stale (>2min old).

        Rule #4b: WebSocket First
        - When data_provider is set, check WebSocket timestamp (source of truth)
        - Fall back to database timestamps if no data_provider
        """
        with get_session() as session:
            # Check if already stopped
            existing = session.query(EmergencyStopState).filter(
                EmergencyStopState.scope == self.SCOPE_SYSTEM,
                EmergencyStopState.scope_id == "data_feed",
                EmergencyStopState.is_stopped == True
            ).first()
            if existing:
                return None

            now = datetime.now(UTC)
            stale_threshold = timedelta(seconds=self.data_stale_seconds)

            # Rule #4b: Check WebSocket timestamp first (source of truth)
            if self.data_provider:
                last_update = self.data_provider.last_webdata2_update
                if last_update:
                    # Ensure timezone-aware comparison
                    if last_update.tzinfo is None:
                        last_update = last_update.replace(tzinfo=UTC)
                    age = now - last_update
                    if age > stale_threshold:
                        return {
                            'scope': self.SCOPE_SYSTEM,
                            'scope_id': 'data_feed',
                            'reason': f"WebSocket data stale for {age.total_seconds():.0f}s > {self.data_stale_seconds}s",
                            'action': self.ACTION_HALT_ENTRIES,
                            'reset_trigger': self.RESET_DATA_VALID
                        }
                    # WebSocket data is fresh - no staleness issue
                    return None
                else:
                    # WebSocket hasn't received webData2 yet - check if provider is running
                    if self.data_provider.running:
                        # Provider running but no data yet - give it time
                        logger.debug("WebSocket running but no webData2 received yet")
                        return None
                    # Fall through to database check

            # Fallback: Check database timestamps (when no data_provider)
            subaccounts = session.query(Subaccount).filter(
                Subaccount.status == 'ACTIVE'
            ).all()

            if not subaccounts:
                return None

            for sa in subaccounts:
                if sa.peak_balance_updated_at:
                    age = now - sa.peak_balance_updated_at.replace(tzinfo=UTC)
                    if age > stale_threshold:
                        return {
                            'scope': self.SCOPE_SYSTEM,
                            'scope_id': 'data_feed',
                            'reason': f"Balance data stale for {age.total_seconds():.0f}s > {self.data_stale_seconds}s",
                            'action': self.ACTION_HALT_ENTRIES,
                            'reset_trigger': self.RESET_DATA_VALID
                        }

        return None

    # =========================================================================
    # STOP ACTIONS
    # =========================================================================

    def trigger_stop(
        self,
        scope: str,
        scope_id: str,
        reason: str,
        action: str,
        reset_trigger: str
    ):
        """
        Trigger an emergency stop for a scope.

        Updates state in database, logs event, executes action.
        Idempotent - won't double-trigger if already stopped.

        Args:
            scope: 'portfolio', 'subaccount', 'strategy', 'system'
            scope_id: 'global', '1'-'10', UUID, 'data_feed'
            reason: Human-readable reason
            action: 'halt_entries' or 'force_close'
            reset_trigger: When/how to auto-reset
        """
        now = datetime.now(UTC)

        # Calculate cooldown_until based on reset_trigger
        cooldown_until = None
        if reset_trigger == self.RESET_MIDNIGHT_UTC:
            # Next midnight UTC
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            cooldown_until = tomorrow
        elif reset_trigger == self.RESET_COOLDOWN_48H_ROTATION:
            cooldown_until = now + timedelta(hours=self.portfolio_dd_cooldown_hours)
        elif reset_trigger == self.RESET_24H:
            cooldown_until = now + timedelta(hours=self.strategy_cooldown_hours)
        # RESET_ROTATION and RESET_DATA_VALID have no fixed cooldown

        with get_session() as session:
            # Check if already stopped (idempotent)
            state = session.query(EmergencyStopState).filter(
                EmergencyStopState.scope == scope,
                EmergencyStopState.scope_id == scope_id
            ).first()

            if state and state.is_stopped:
                logger.debug(f"Emergency stop already active for {scope}:{scope_id}")
                return

            if state:
                state.is_stopped = True
                state.stop_reason = reason
                state.stop_action = action
                state.stopped_at = now
                state.cooldown_until = cooldown_until
                state.reset_trigger = reset_trigger
            else:
                state = EmergencyStopState(
                    scope=scope,
                    scope_id=scope_id,
                    is_stopped=True,
                    stop_reason=reason,
                    stop_action=action,
                    stopped_at=now,
                    cooldown_until=cooldown_until,
                    reset_trigger=reset_trigger
                )
                session.add(state)

            session.commit()

        # Log critical event
        logger.critical(f"EMERGENCY STOP [{scope}:{scope_id}] {action}: {reason}")

        # Execute action
        self._execute_action(scope, scope_id, action, reason)

    def _execute_action(self, scope: str, scope_id: str, action: str, reason: str):
        """Execute the stop action."""
        if action == self.ACTION_HALT_ENTRIES:
            self._execute_halt_entries(scope, scope_id)
        elif action == self.ACTION_FORCE_CLOSE:
            self._execute_force_close(reason)

    def _execute_halt_entries(self, scope: str, scope_id: str):
        """
        Block new entries for scope.

        For halt_entries, we just update the state - the executor will
        check can_trade() before opening new positions.
        """
        logger.warning(f"Halt entries active for {scope}:{scope_id}")

        # Update subaccount status if applicable
        if scope == self.SCOPE_SUBACCOUNT:
            try:
                subaccount_id = int(scope_id)
            except ValueError:
                logger.warning(f"Invalid subaccount scope_id: {scope_id}")
                return

            with get_session() as session:
                sa = session.query(Subaccount).filter(
                    Subaccount.id == subaccount_id
                ).first()
                if sa:
                    sa.status = 'PAUSED'
                    session.commit()

    def _execute_force_close(self, reason: str):
        """
        Close ALL positions immediately (portfolio-level panic button).

        Calls Hyperliquid to close all positions across all subaccounts.
        """
        logger.critical(f"FORCE CLOSE ALL POSITIONS: {reason}")

        if self.client is None:
            logger.error("Cannot force close - no Hyperliquid client available")
            return

        try:
            # Close all positions via Hyperliquid client
            self.client.emergency_stop_all(reason)
            logger.info("Force close executed successfully")
        except Exception as e:
            logger.error(f"Force close failed: {e}")

        # Update all subaccount statuses
        with get_session() as session:
            session.query(Subaccount).filter(
                Subaccount.status == 'ACTIVE'
            ).update({'status': 'STOPPED'})
            session.commit()

    # =========================================================================
    # AUTO-RESET LOGIC
    # =========================================================================

    def check_auto_resets(self) -> List[Dict]:
        """
        Check for stops that can be auto-reset.

        Returns:
            List of resets performed
        """
        now = datetime.now(UTC)
        resets = []

        with get_session() as session:
            # Get all active stops
            stops = session.query(EmergencyStopState).filter(
                EmergencyStopState.is_stopped == True
            ).all()

            for stop in stops:
                should_reset = False
                reset_reason = None

                if stop.reset_trigger == self.RESET_MIDNIGHT_UTC:
                    # Reset at midnight UTC
                    if stop.cooldown_until and now >= stop.cooldown_until:
                        should_reset = True
                        reset_reason = "Daily reset at midnight UTC"

                elif stop.reset_trigger == self.RESET_COOLDOWN_48H_ROTATION:
                    # Reset after 48h cooldown AND strategies rotated
                    if stop.cooldown_until and now >= stop.cooldown_until:
                        if self._check_portfolio_dd_rotation_ready(session):
                            should_reset = True
                            reset_reason = f"Cooldown {self.portfolio_dd_cooldown_hours}h expired + strategies rotated"

                elif stop.reset_trigger == self.RESET_24H:
                    # Reset 24h after last loss
                    if stop.cooldown_until and now >= stop.cooldown_until:
                        should_reset = True
                        reset_reason = f"Cooldown {self.strategy_cooldown_hours}h expired"

                elif stop.reset_trigger == self.RESET_DATA_VALID:
                    # Reset when data is no longer stale
                    if not self._is_data_still_stale(session):
                        should_reset = True
                        reset_reason = "Data feed restored"

                # RESET_ROTATION is handled by reset_on_rotation()

                if should_reset:
                    self._reset_stop(stop.scope, stop.scope_id, reset_reason, session)
                    resets.append({
                        'scope': stop.scope,
                        'scope_id': stop.scope_id,
                        'reason': reset_reason
                    })

            session.commit()

        return resets

    def _check_portfolio_dd_rotation_ready(self, session: Session) -> bool:
        """
        Check if all losing strategies have been rotated.

        For 48h+rotation reset, we need:
        1. 48h cooldown passed
        2. All strategies with loss >= rotation_loss_threshold rotated
        """
        # Get strategies that were LIVE when DD triggered
        # For simplicity, check if any LIVE strategy has negative total_pnl_live
        strategies = session.query(Strategy).filter(
            Strategy.status == 'LIVE'
        ).all()

        for strat in strategies:
            pnl = strat.total_pnl_live or 0
            if pnl < -self.rotation_loss_threshold:
                # Still have losing strategies that haven't been rotated
                return False

        return True

    def _is_data_still_stale(self, session: Session) -> bool:
        """Check if data is still stale."""
        subaccounts = session.query(Subaccount).filter(
            Subaccount.status.in_(['ACTIVE', 'PAUSED'])
        ).all()

        if not subaccounts:
            return False

        now = datetime.now(UTC)
        stale_threshold = timedelta(seconds=self.data_stale_seconds)

        for sa in subaccounts:
            if sa.peak_balance_updated_at:
                update_time = sa.peak_balance_updated_at
                if update_time.tzinfo is None:
                    update_time = update_time.replace(tzinfo=UTC)
                age = now - update_time
                if age > stale_threshold:
                    return True

        return False

    def reset_on_rotation(self, subaccount_id: int):
        """
        Reset subaccount stop when rotator assigns new strategy.

        Called by Rotator after successful deployment.
        """
        with get_session() as session:
            state = session.query(EmergencyStopState).filter(
                EmergencyStopState.scope == self.SCOPE_SUBACCOUNT,
                EmergencyStopState.scope_id == str(subaccount_id),
                EmergencyStopState.reset_trigger == self.RESET_ROTATION,
                EmergencyStopState.is_stopped == True
            ).first()

            if state:
                self._reset_stop(
                    self.SCOPE_SUBACCOUNT,
                    str(subaccount_id),
                    "New strategy deployed via rotation",
                    session
                )
                session.commit()
                logger.info(f"Reset subaccount {subaccount_id} stop after rotation")

    def reset_portfolio_dd_after_rotation(self):
        """
        Reset portfolio DD stop after cooldown + rotation complete.

        Called by Rotator when all losing strategies have been rotated.
        """
        with get_session() as session:
            state = session.query(EmergencyStopState).filter(
                EmergencyStopState.scope == self.SCOPE_PORTFOLIO,
                EmergencyStopState.scope_id == "global",
                EmergencyStopState.reset_trigger == self.RESET_COOLDOWN_48H_ROTATION,
                EmergencyStopState.is_stopped == True
            ).first()

            if state and state.cooldown_until:
                now = datetime.now(UTC)
                if now >= state.cooldown_until:
                    self._reset_stop(
                        self.SCOPE_PORTFOLIO,
                        "global",
                        "Cooldown expired + losing strategies rotated",
                        session
                    )
                    session.commit()
                    logger.info("Reset portfolio DD stop after rotation")

    def _reset_stop(self, scope: str, scope_id: str, reason: str, session: Session):
        """Reset a stop state."""
        state = session.query(EmergencyStopState).filter(
            EmergencyStopState.scope == scope,
            EmergencyStopState.scope_id == scope_id
        ).first()

        if state:
            state.is_stopped = False
            state.stop_reason = None
            state.stopped_at = None
            state.cooldown_until = None

        logger.info(f"Auto-reset [{scope}:{scope_id}]: {reason}")

        # Re-activate subaccount if it was paused/stopped
        if scope == self.SCOPE_SUBACCOUNT:
            sa = session.query(Subaccount).filter(
                Subaccount.id == int(scope_id),
                Subaccount.status.in_(['PAUSED', 'STOPPED'])
            ).first()
            if sa:
                sa.status = 'ACTIVE'

        elif scope == self.SCOPE_PORTFOLIO:
            # Re-activate all stopped/paused subaccounts
            session.query(Subaccount).filter(
                Subaccount.status.in_(['PAUSED', 'STOPPED'])
            ).update({'status': 'ACTIVE'})

    # =========================================================================
    # BALANCE TRACKING
    # =========================================================================

    def update_balances(
        self,
        subaccount_id: int,
        current_balance: float,
        pnl_delta: float
    ):
        """
        Update balance tracking for a subaccount.

        Called after each trade close to track:
        - current_balance
        - peak_balance (high water mark)
        - daily_pnl_usd (resets at midnight UTC)

        Args:
            subaccount_id: Subaccount ID
            current_balance: Current realized balance in USD
            pnl_delta: PnL from this trade (positive or negative)
        """
        now = datetime.now(UTC)

        with get_session() as session:
            sa = session.query(Subaccount).filter(
                Subaccount.id == subaccount_id
            ).first()

            if not sa:
                logger.warning(f"Subaccount {subaccount_id} not found for balance update")
                return

            # Update current balance
            sa.current_balance = current_balance

            # Update peak balance (high water mark) - only increase, never decrease
            # CRITICAL: Do NOT initialize peak_balance from current_balance!
            # peak_balance must be set by deployer (from allocated_capital).
            # Only UPDATE peak if already set AND current is higher (profits).
            if sa.peak_balance is not None and sa.peak_balance > 0:
                if current_balance > sa.peak_balance:
                    sa.peak_balance = current_balance
                    sa.peak_balance_updated_at = now
                    logger.debug(f"Subaccount {subaccount_id}: new peak ${current_balance:.2f}")
                else:
                    # Still update timestamp to show data is fresh
                    sa.peak_balance_updated_at = now
            # If peak_balance is None, don't set it - deployer handles initialization

            # Update daily PnL (reset if new day)
            today = now.date()
            if sa.daily_pnl_reset_date is None:
                sa.daily_pnl_usd = pnl_delta
                sa.daily_pnl_reset_date = now
            elif sa.daily_pnl_reset_date.date() != today:
                # New day - reset daily PnL
                sa.daily_pnl_usd = pnl_delta
                sa.daily_pnl_reset_date = now
            else:
                # Same day - accumulate
                sa.daily_pnl_usd = (sa.daily_pnl_usd or 0) + pnl_delta

            session.commit()

            logger.debug(
                f"Balance updated for subaccount {subaccount_id}: "
                f"balance=${current_balance:.2f}, peak=${sa.peak_balance:.2f}, "
                f"daily_pnl=${sa.daily_pnl_usd:.2f}"
            )

    def mark_data_fresh(self, subaccount_id: int):
        """
        Mark data as fresh for a subaccount.

        Called when we successfully fetch balance from exchange.
        This helps prevent false data_stale triggers.
        """
        now = datetime.now(UTC)

        with get_session() as session:
            sa = session.query(Subaccount).filter(
                Subaccount.id == subaccount_id
            ).first()

            if sa:
                sa.peak_balance_updated_at = now
                session.commit()

    def reset_data_stale(self):
        """
        Reset data stale stop when data becomes valid again.

        Called when data feed is restored.
        """
        with get_session() as session:
            state = session.query(EmergencyStopState).filter(
                EmergencyStopState.scope == self.SCOPE_SYSTEM,
                EmergencyStopState.scope_id == "data_feed",
                EmergencyStopState.is_stopped == True
            ).first()

            if state:
                self._reset_stop(
                    self.SCOPE_SYSTEM,
                    "data_feed",
                    "Data feed restored",
                    session
                )
                session.commit()
                logger.info("Reset data stale stop - data feed restored")

    def check_portfolio_dd_rotation_ready(self) -> bool:
        """
        Check if all losing strategies have been rotated.

        Public wrapper for _check_portfolio_dd_rotation_ready.
        Used by Rotator to check if portfolio DD stop can be reset.
        """
        with get_session() as session:
            return self._check_portfolio_dd_rotation_ready(session)

    # =========================================================================
    # TRUE P&L STATISTICS (Hyperliquid as source of truth)
    # =========================================================================

    def get_true_pnl_stats(self, subaccount_id: int) -> Optional[Dict]:
        """
        Get true P&L statistics for a subaccount using Hyperliquid as source of truth.

        Formula: True P&L = Current Balance - Net Deposits

        This is immune to manual deposits/withdrawals corrupting statistics.
        Requires statistics_service to be initialized.

        Args:
            subaccount_id: Subaccount number

        Returns:
            Dict with true_pnl, true_pnl_pct, net_deposits, current_balance
            or None if statistics_service not available
        """
        if self.statistics_service is None:
            logger.debug("StatisticsService not available - cannot calculate true P&L")
            return None

        try:
            return self.statistics_service.get_true_pnl(subaccount_id)
        except Exception as e:
            logger.error(f"Failed to get true P&L for subaccount {subaccount_id}: {e}")
            return None

    def get_true_drawdown_stats(self, subaccount_id: int) -> Optional[Dict]:
        """
        Get true drawdown statistics for a subaccount using Hyperliquid.

        True drawdown = loss from invested capital (net_deposits), not from peak.
        This is immune to manual deposits/withdrawals corrupting statistics.

        Args:
            subaccount_id: Subaccount number

        Returns:
            Dict with drawdown, drawdown_pct, is_in_drawdown
            or None if statistics_service not available
        """
        if self.statistics_service is None:
            logger.debug("StatisticsService not available - cannot calculate true drawdown")
            return None

        try:
            return self.statistics_service.get_true_drawdown(subaccount_id)
        except Exception as e:
            logger.error(f"Failed to get true drawdown for subaccount {subaccount_id}: {e}")
            return None

    def get_all_subaccounts_true_stats(self) -> Dict[int, Dict]:
        """
        Get true P&L statistics for all active subaccounts.

        Returns:
            Dict mapping subaccount_id to stats
        """
        if self.statistics_service is None:
            return {}

        with get_session() as session:
            subaccounts = session.query(Subaccount).filter(
                Subaccount.status.in_(['ACTIVE', 'PAUSED'])
            ).all()
            subaccount_ids = [sa.id for sa in subaccounts]

        return self.statistics_service.get_all_subaccounts_stats(subaccount_ids)
