"""
Pre-flight checks API for Go Live functionality.

Provides endpoints to check system readiness and apply fixes before going live.
All configuration is read from config.yaml (single source of truth).
"""
import logging
from datetime import datetime, UTC
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.config import load_config
from src.database.connection import get_session
from src.database.models import Subaccount, Strategy, EmergencyStopState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preflight", tags=["Preflight"])


# =============================================================================
# SCHEMAS
# =============================================================================

class CheckResult(BaseModel):
    """Result of a single preflight check"""
    name: str
    status: str  # 'pass', 'fail', 'warn'
    message: str
    details: dict = {}
    can_fix: bool = False  # Can this be fixed via API?


class SubaccountStatus(BaseModel):
    """Status of a single subaccount"""
    id: int
    exists: bool
    balance: Optional[float] = None
    status: str  # 'funded', 'underfunded', 'unknown', 'missing'


class EmergencyStopInfo(BaseModel):
    """Active emergency stop info"""
    scope: str
    scope_id: str
    reason: Optional[str] = None


class PreflightResponse(BaseModel):
    """Full preflight check response"""
    ready: bool
    checks: List[CheckResult]
    subaccounts: List[SubaccountStatus] = []
    emergency_stops: List[EmergencyStopInfo] = []
    pool_stats: dict = {}
    config_summary: dict = {}  # Summary of relevant config values


class ApplyRequest(BaseModel):
    """Request to apply fixes"""
    create_subaccounts: bool = False
    clear_emergency_stops: bool = False


class ApplyResponse(BaseModel):
    """Response from apply fixes"""
    success: bool
    actions_taken: List[str]
    errors: List[str] = []


class PrepareConfig(BaseModel):
    """Go Live configuration (read from config.yaml)"""
    # Capital settings (from hyperliquid section)
    num_subaccounts: int
    capital_per_subaccount: int
    min_operational: int

    # Pool settings (from active_pool and rotator sections)
    pool_max_size: int
    pool_min_for_live: int

    # Live settings (from hyperliquid and rotator sections)
    max_live_strategies: int
    dry_run: bool

    # Preflight checks (from go_live section)
    require_funded: bool
    require_pool: bool
    clear_emergency_stops: bool


# =============================================================================
# HELPERS
# =============================================================================

def get_config_values() -> dict:
    """Extract relevant config values for preflight checks."""
    config = load_config()

    return {
        'num_subaccounts': config.hyperliquid['subaccounts']['count'],
        'capital_per_subaccount': config.hyperliquid['funds']['topup_target_usd'],
        'min_operational': config.hyperliquid['funds']['min_operational_usd'],
        'pool_max_size': config.active_pool['max_size'],
        'pool_min_for_live': config.rotator['min_pool_size'],
        'max_live_strategies': config.rotator['max_live_strategies'],
        'dry_run': config.hyperliquid['dry_run'],
        'require_funded': config.go_live['preflight_checks']['require_funded'],
        'require_pool': config.go_live['preflight_checks']['require_pool'],
        'clear_emergency_stops': config.go_live['preflight_checks']['clear_emergency_stops'],
    }


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", response_model=PreflightResponse)
async def get_preflight_status():
    """
    Run all preflight checks and return system readiness status.

    Checks:
    1. Subaccounts exist in DB
    2. Funding status
    3. Pool size (ACTIVE + LIVE strategies)
    4. Emergency stops
    """
    cfg = get_config_values()

    checks: List[CheckResult] = []
    subaccounts: List[SubaccountStatus] = []
    emergency_stops: List[EmergencyStopInfo] = []
    pool_stats = {}

    target_subs = cfg['num_subaccounts']
    min_operational = cfg['min_operational']
    target_min_pool = cfg['pool_min_for_live']

    # ==========================================================================
    # CHECK 1: Subaccounts Exist
    # ==========================================================================
    with get_session() as session:
        existing_subs = session.query(Subaccount).all()
        existing_ids = {sa.id for sa in existing_subs}
        existing_data = {sa.id: (sa.current_balance, sa.status) for sa in existing_subs}

    needed_ids = set(range(1, target_subs + 1))
    missing_ids = needed_ids - existing_ids

    for i in range(1, target_subs + 1):
        if i not in existing_ids:
            subaccounts.append(SubaccountStatus(
                id=i,
                exists=False,
                status='missing'
            ))
        else:
            balance, status = existing_data[i]
            if balance is None:
                sa_status = 'unknown'
            elif balance >= min_operational:
                sa_status = 'funded'
            else:
                sa_status = 'underfunded'

            subaccounts.append(SubaccountStatus(
                id=i,
                exists=True,
                balance=balance,
                status=sa_status
            ))

    checks.append(CheckResult(
        name='Subaccounts Exist',
        status='pass' if not missing_ids else 'fail',
        message=f'{len(missing_ids)} missing' if missing_ids else f'All {target_subs} subaccounts exist',
        details={'missing': list(missing_ids)},
        can_fix=True  # Can create subaccounts
    ))

    # ==========================================================================
    # CHECK 2: Funding Status
    # ==========================================================================
    funded_count = sum(1 for sa in subaccounts if sa.status == 'funded')
    underfunded_count = sum(1 for sa in subaccounts if sa.status == 'underfunded')
    unknown_count = sum(1 for sa in subaccounts if sa.status in ('unknown', 'missing'))

    funding_ok = (underfunded_count == 0 and unknown_count == 0)
    if cfg['require_funded']:
        checks.append(CheckResult(
            name='Funding Status',
            status='pass' if funding_ok else 'fail',
            message=f'{funded_count}/{target_subs} funded (min ${min_operational})',
            details={
                'funded': funded_count,
                'underfunded': underfunded_count,
                'unknown': unknown_count,
                'min_operational': min_operational
            },
            can_fix=False  # Must transfer funds manually
        ))
    else:
        checks.append(CheckResult(
            name='Funding Status',
            status='pass' if funding_ok else 'warn',
            message=f'{funded_count}/{target_subs} funded (check disabled)',
            details={
                'funded': funded_count,
                'underfunded': underfunded_count,
                'unknown': unknown_count
            },
            can_fix=False
        ))

    # ==========================================================================
    # CHECK 3: Pool Size
    # ==========================================================================
    with get_session() as session:
        active_count = session.query(Strategy).filter(
            Strategy.status == 'ACTIVE'
        ).count()

        live_count = session.query(Strategy).filter(
            Strategy.status == 'LIVE'
        ).count()

    total_ready = active_count + live_count
    pool_stats = {
        'active': active_count,
        'live': live_count,
        'total': total_ready,
        'required': target_min_pool
    }

    pool_ok = total_ready >= target_min_pool
    if cfg['require_pool']:
        checks.append(CheckResult(
            name='Pool Size',
            status='pass' if pool_ok else 'fail',
            message=f'{total_ready} ready (need {target_min_pool})',
            details=pool_stats,
            can_fix=False  # Must generate more strategies
        ))
    else:
        checks.append(CheckResult(
            name='Pool Size',
            status='pass' if pool_ok else 'warn',
            message=f'{total_ready} ready (check disabled)',
            details=pool_stats,
            can_fix=False
        ))

    # ==========================================================================
    # CHECK 4: Emergency Stops
    # ==========================================================================
    with get_session() as session:
        active_stops = session.query(EmergencyStopState).filter(
            EmergencyStopState.is_stopped == True
        ).all()

        for stop in active_stops:
            emergency_stops.append(EmergencyStopInfo(
                scope=stop.scope,
                scope_id=str(stop.scope_id),
                reason=stop.stop_reason
            ))

    checks.append(CheckResult(
        name='Emergency Stops',
        status='pass' if not emergency_stops else 'warn',
        message=f'{len(emergency_stops)} active stops' if emergency_stops else 'No active stops',
        details={'count': len(emergency_stops)},
        can_fix=True if emergency_stops and cfg['clear_emergency_stops'] else False
    ))

    # ==========================================================================
    # CHECK 5: Dry Run Mode
    # ==========================================================================
    checks.append(CheckResult(
        name='Trading Mode',
        status='warn' if cfg['dry_run'] else 'pass',
        message='DRY RUN (no real trades)' if cfg['dry_run'] else 'LIVE MODE (real trades)',
        details={'dry_run': cfg['dry_run']},
        can_fix=False  # Must change in config.yaml
    ))

    # ==========================================================================
    # OVERALL READINESS
    # ==========================================================================
    # Ready if no 'fail' checks
    ready = all(c.status != 'fail' for c in checks)

    return PreflightResponse(
        ready=ready,
        checks=checks,
        subaccounts=subaccounts,
        emergency_stops=emergency_stops,
        pool_stats=pool_stats,
        config_summary={
            'num_subaccounts': target_subs,
            'capital_per_subaccount': cfg['capital_per_subaccount'],
            'min_operational': min_operational,
            'max_live_strategies': cfg['max_live_strategies'],
            'pool_max_size': cfg['pool_max_size'],
            'pool_min_for_live': target_min_pool,
            'dry_run': cfg['dry_run']
        }
    )


@router.post("/apply", response_model=ApplyResponse)
async def apply_preflight_fixes(request: ApplyRequest):
    """
    Apply fixes for preflight issues.

    Available fixes:
    - create_subaccounts: Create missing subaccounts in DB
    - clear_emergency_stops: Clear all active emergency stops
    """
    cfg = get_config_values()
    actions_taken: List[str] = []
    errors: List[str] = []

    # ==========================================================================
    # CREATE MISSING SUBACCOUNTS
    # ==========================================================================
    if request.create_subaccounts:
        target_subs = cfg['num_subaccounts']
        capital = cfg['capital_per_subaccount']

        try:
            with get_session() as session:
                existing = session.query(Subaccount).all()
                existing_ids = {sa.id for sa in existing}

                created = []
                for sa_id in range(1, target_subs + 1):
                    if sa_id not in existing_ids:
                        sa = Subaccount(
                            id=sa_id,
                            status='INACTIVE',
                            allocated_capital=capital,
                            current_balance=None,
                            peak_balance=None,
                            created_at=datetime.now(UTC)
                        )
                        session.add(sa)
                        created.append(sa_id)

                session.commit()

                if created:
                    actions_taken.append(f"Created subaccounts: {created}")
                    logger.info(f"Created subaccounts: {created}")
                else:
                    actions_taken.append("No subaccounts needed creation")

        except Exception as e:
            errors.append(f"Failed to create subaccounts: {str(e)}")
            logger.error(f"Failed to create subaccounts: {e}")

    # ==========================================================================
    # CLEAR EMERGENCY STOPS
    # ==========================================================================
    if request.clear_emergency_stops:
        if not cfg['clear_emergency_stops']:
            errors.append("Clearing emergency stops is disabled in config")
        else:
            try:
                with get_session() as session:
                    active_stops = session.query(EmergencyStopState).filter(
                        EmergencyStopState.is_stopped == True
                    ).all()

                    cleared = []
                    for stop in active_stops:
                        stop.is_stopped = False
                        stop.stop_reason = None
                        stop.stopped_at = None
                        stop.cooldown_until = None
                        cleared.append(f"{stop.scope}:{stop.scope_id}")

                    session.commit()

                    if cleared:
                        actions_taken.append(f"Cleared emergency stops: {cleared}")
                        logger.info(f"Cleared emergency stops: {cleared}")
                    else:
                        actions_taken.append("No emergency stops to clear")

            except Exception as e:
                errors.append(f"Failed to clear emergency stops: {str(e)}")
                logger.error(f"Failed to clear emergency stops: {e}")

    success = len(errors) == 0

    return ApplyResponse(
        success=success,
        actions_taken=actions_taken,
        errors=errors
    )


@router.get("/config", response_model=PrepareConfig)
async def get_prepare_config():
    """
    Get the Go Live configuration from config.yaml.

    Returns the current configuration used for preflight checks.
    To modify these values, use System > Settings in the frontend.
    """
    cfg = get_config_values()

    return PrepareConfig(
        num_subaccounts=cfg['num_subaccounts'],
        capital_per_subaccount=cfg['capital_per_subaccount'],
        min_operational=cfg['min_operational'],
        pool_max_size=cfg['pool_max_size'],
        pool_min_for_live=cfg['pool_min_for_live'],
        max_live_strategies=cfg['max_live_strategies'],
        dry_run=cfg['dry_run'],
        require_funded=cfg['require_funded'],
        require_pool=cfg['require_pool'],
        clear_emergency_stops=cfg['clear_emergency_stops']
    )
