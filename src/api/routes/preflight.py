"""
Pre-flight checks API for Go Live functionality.

Provides endpoints to check system readiness and apply fixes before going live.
"""
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import List, Optional

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.database.connection import get_session
from src.database.models import Subaccount, Strategy, EmergencyStopState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preflight", tags=["Preflight"])

# Paths
PREPARE_CONFIG_PATH = Path("config/prepare_live.yaml")
MAIN_CONFIG_PATH = Path("config/config.yaml")


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


class ConfigMismatch(BaseModel):
    """Single config mismatch"""
    key: str
    current: str
    target: str


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
    config_mismatches: List[ConfigMismatch] = []
    subaccounts: List[SubaccountStatus] = []
    emergency_stops: List[EmergencyStopInfo] = []
    pool_stats: dict = {}
    target_config: dict = {}  # What prepare_live.yaml wants


class ApplyRequest(BaseModel):
    """Request to apply fixes"""
    create_subaccounts: bool = False
    clear_emergency_stops: bool = False


class ApplyResponse(BaseModel):
    """Response from apply fixes"""
    success: bool
    actions_taken: List[str]
    errors: List[str] = []


# =============================================================================
# HELPERS
# =============================================================================

def load_prepare_config() -> dict:
    """Load prepare_live.yaml configuration."""
    if not PREPARE_CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="prepare_live.yaml not found")

    with open(PREPARE_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_main_config() -> dict:
    """Load main config.yaml."""
    if not MAIN_CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")

    with open(MAIN_CONFIG_PATH) as f:
        return yaml.safe_load(f)


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", response_model=PreflightResponse)
async def get_preflight_status():
    """
    Run all preflight checks and return system readiness status.

    Checks:
    1. Config alignment (config.yaml vs prepare_live.yaml)
    2. Subaccounts exist in DB
    3. Funding status
    4. Pool size (ACTIVE + LIVE strategies)
    5. Emergency stops
    """
    prep_config = load_prepare_config()
    main_config = load_main_config()

    checks: List[CheckResult] = []
    config_mismatches: List[ConfigMismatch] = []
    subaccounts: List[SubaccountStatus] = []
    emergency_stops: List[EmergencyStopInfo] = []
    pool_stats = {}

    # Extract target values
    target_subs = prep_config['capital']['num_subaccounts']
    target_capital = prep_config['capital']['capital_per_subaccount']
    min_operational = prep_config['capital']['min_operational']
    target_max_live = prep_config['live']['max_live_strategies']
    target_pool_max = prep_config['pool']['max_size']
    target_min_pool = prep_config['pool']['min_for_live']
    target_dry_run = prep_config['live']['dry_run']

    # ==========================================================================
    # CHECK 1: Config Alignment
    # ==========================================================================
    mismatches = []

    # Subaccounts count
    current_subs = main_config.get('subaccounts', {}).get('count', 5)
    if current_subs != target_subs:
        mismatches.append(ConfigMismatch(
            key='subaccounts.count',
            current=str(current_subs),
            target=str(target_subs)
        ))

    # Max live strategies
    current_max = main_config.get('rotator', {}).get('max_live_strategies', 5)
    if current_max != target_max_live:
        mismatches.append(ConfigMismatch(
            key='rotator.max_live_strategies',
            current=str(current_max),
            target=str(target_max_live)
        ))

    # Pool max size
    current_pool = main_config.get('active_pool', {}).get('max_size', 300)
    if current_pool != target_pool_max:
        mismatches.append(ConfigMismatch(
            key='active_pool.max_size',
            current=str(current_pool),
            target=str(target_pool_max)
        ))

    # Min pool size
    current_min = main_config.get('rotator', {}).get('min_pool_size', 100)
    if current_min != target_min_pool:
        mismatches.append(ConfigMismatch(
            key='rotator.min_pool_size',
            current=str(current_min),
            target=str(target_min_pool)
        ))

    # Dry run
    current_dry = main_config.get('trading', {}).get('dry_run', True)
    if current_dry != target_dry_run:
        mismatches.append(ConfigMismatch(
            key='trading.dry_run',
            current=str(current_dry),
            target=str(target_dry_run)
        ))

    # Fund settings
    current_topup = main_config.get('funds', {}).get('topup_target_usd', 100)
    if current_topup != target_capital:
        mismatches.append(ConfigMismatch(
            key='funds.topup_target_usd',
            current=str(current_topup),
            target=str(target_capital)
        ))

    current_min_op = main_config.get('funds', {}).get('min_operational_usd', 50)
    if current_min_op != min_operational:
        mismatches.append(ConfigMismatch(
            key='funds.min_operational_usd',
            current=str(current_min_op),
            target=str(min_operational)
        ))

    config_mismatches = mismatches
    checks.append(CheckResult(
        name='Config Alignment',
        status='pass' if not mismatches else 'warn',
        message=f'{len(mismatches)} mismatches' if mismatches else 'Config aligned',
        details={'mismatch_count': len(mismatches)},
        can_fix=False  # Config changes must be manual
    ))

    # ==========================================================================
    # CHECK 2: Subaccounts Exist
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
    # CHECK 3: Funding Status
    # ==========================================================================
    funded_count = sum(1 for sa in subaccounts if sa.status == 'funded')
    underfunded_count = sum(1 for sa in subaccounts if sa.status == 'underfunded')
    unknown_count = sum(1 for sa in subaccounts if sa.status in ('unknown', 'missing'))

    funding_ok = (underfunded_count == 0 and unknown_count == 0)
    if prep_config['checks'].get('require_funded', True):
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
    # CHECK 4: Pool Size
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
    if prep_config['checks'].get('require_pool', True):
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
    # CHECK 5: Emergency Stops
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
        can_fix=True if emergency_stops else False
    ))

    # ==========================================================================
    # OVERALL READINESS
    # ==========================================================================
    # Ready if no 'fail' checks
    ready = all(c.status != 'fail' for c in checks)

    return PreflightResponse(
        ready=ready,
        checks=checks,
        config_mismatches=config_mismatches,
        subaccounts=subaccounts,
        emergency_stops=emergency_stops,
        pool_stats=pool_stats,
        target_config={
            'num_subaccounts': target_subs,
            'capital_per_subaccount': target_capital,
            'min_operational': min_operational,
            'max_live_strategies': target_max_live,
            'pool_max_size': target_pool_max,
            'pool_min_for_live': target_min_pool,
            'dry_run': target_dry_run
        }
    )


@router.post("/apply", response_model=ApplyResponse)
async def apply_preflight_fixes(request: ApplyRequest):
    """
    Apply fixes for preflight issues.

    Available fixes:
    - create_subaccounts: Create missing subaccounts in DB
    - clear_emergency_stops: Clear all active emergency stops

    Note: Config changes must be done manually (not via API for safety).
    """
    prep_config = load_prepare_config()
    actions_taken: List[str] = []
    errors: List[str] = []

    # ==========================================================================
    # CREATE MISSING SUBACCOUNTS
    # ==========================================================================
    if request.create_subaccounts:
        target_subs = prep_config['capital']['num_subaccounts']
        capital = prep_config['capital']['capital_per_subaccount']

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
