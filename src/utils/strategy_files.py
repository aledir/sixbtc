"""
Strategy file management for pool and live directories.

Saves strategy .py files when entering ACTIVE/LIVE status,
removes them when leaving those states.
"""

import logging
from pathlib import Path
from uuid import UUID

logger = logging.getLogger(__name__)

# Directory paths
STRATEGIES_DIR = Path("/home/bitwolf/sixbtc/strategies")
POOL_DIR = STRATEGIES_DIR / "pool"
LIVE_DIR = STRATEGIES_DIR / "live"


def _ensure_dirs():
    """Ensure pool and live directories exist."""
    POOL_DIR.mkdir(parents=True, exist_ok=True)
    LIVE_DIR.mkdir(parents=True, exist_ok=True)


def _get_filename(strategy_name: str) -> str:
    """Generate filename from strategy name."""
    return f"{strategy_name}.py"


def save_to_pool(strategy_name: str, code: str) -> bool:
    """
    Save strategy code to pool directory.
    Called when strategy enters ACTIVE status.
    """
    try:
        _ensure_dirs()
        filepath = POOL_DIR / _get_filename(strategy_name)
        filepath.write_text(code)
        logger.debug(f"Saved {strategy_name} to pool/")
        return True
    except Exception as e:
        logger.error(f"Failed to save {strategy_name} to pool: {e}")
        return False


def remove_from_pool(strategy_name: str) -> bool:
    """
    Remove strategy file from pool directory.
    Called when strategy leaves ACTIVE (retired or promoted to LIVE).
    """
    try:
        filepath = POOL_DIR / _get_filename(strategy_name)
        if filepath.exists():
            filepath.unlink()
            logger.debug(f"Removed {strategy_name} from pool/")
        return True
    except Exception as e:
        logger.error(f"Failed to remove {strategy_name} from pool: {e}")
        return False


def save_to_live(strategy_name: str, code: str) -> bool:
    """
    Save strategy code to live directory.
    Called when strategy enters LIVE status.
    """
    try:
        _ensure_dirs()
        filepath = LIVE_DIR / _get_filename(strategy_name)
        filepath.write_text(code)
        logger.debug(f"Saved {strategy_name} to live/")
        return True
    except Exception as e:
        logger.error(f"Failed to save {strategy_name} to live: {e}")
        return False


def remove_from_live(strategy_name: str) -> bool:
    """
    Remove strategy file from live directory.
    Called when strategy leaves LIVE (retired).
    """
    try:
        filepath = LIVE_DIR / _get_filename(strategy_name)
        if filepath.exists():
            filepath.unlink()
            logger.debug(f"Removed {strategy_name} from live/")
        return True
    except Exception as e:
        logger.error(f"Failed to remove {strategy_name} from live: {e}")
        return False


def sync_directories_with_db(session) -> dict:
    """
    Sync pool/ and live/ directories with database state.
    Useful for startup or recovery.

    Returns dict with counts of added/removed files.
    """
    from src.database.models import Strategy

    _ensure_dirs()

    stats = {"pool_added": 0, "pool_removed": 0, "live_added": 0, "live_removed": 0}

    # Get current ACTIVE and LIVE strategies from DB
    active_strategies = session.query(Strategy).filter(Strategy.status == 'ACTIVE').all()
    live_strategies = session.query(Strategy).filter(Strategy.status == 'LIVE').all()

    active_names = {s.name for s in active_strategies}
    live_names = {s.name for s in live_strategies}

    # Sync pool directory
    existing_pool = {f.stem for f in POOL_DIR.glob("*.py")}

    # Add missing files
    for s in active_strategies:
        if s.name not in existing_pool:
            save_to_pool(s.name, s.code)
            stats["pool_added"] += 1

    # Remove stale files
    for name in existing_pool - active_names:
        remove_from_pool(name)
        stats["pool_removed"] += 1

    # Sync live directory
    existing_live = {f.stem for f in LIVE_DIR.glob("*.py")}

    # Add missing files
    for s in live_strategies:
        if s.name not in existing_live:
            save_to_live(s.name, s.code)
            stats["live_added"] += 1

    # Remove stale files
    for name in existing_live - live_names:
        remove_from_live(name)
        stats["live_removed"] += 1

    if any(stats.values()):
        logger.info(f"Directory sync: {stats}")

    return stats
