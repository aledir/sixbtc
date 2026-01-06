"""
AI Call Tracker - Daily limit tracking with file-based persistence

Tracks AI calls per day with:
- File-based persistence (survives restarts)
- Automatic reset at midnight
- Thread-safe operations
"""

import json
import logging
import threading
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class AICallTracker:
    """
    Tracks daily AI calls with file-based persistence.
    Thread-safe, survives restarts.
    """

    def __init__(self, max_calls: int, state_file: str = "data/ai_calls.json"):
        """
        Initialize AI Call Tracker.

        Args:
            max_calls: Maximum AI calls allowed per day
            state_file: Path to JSON file for persistence
        """
        self.max_calls = max_calls
        self.state_file = Path(state_file)
        self.lock = threading.Lock()

        # Ensure data directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing state or initialize
        self._load_state()

    def _load_state(self) -> None:
        """Load state from file, reset if new day."""
        with self.lock:
            today = date.today().isoformat()

            if self.state_file.exists():
                try:
                    with open(self.state_file, 'r') as f:
                        state = json.load(f)

                    # Check if same day
                    if state.get('date') == today:
                        self._count = state.get('count', 0)
                        self._date = today
                        logger.info(
                            f"AICallTracker loaded: {self._count}/{self.max_calls} "
                            f"calls used today"
                        )
                        return
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Invalid state file, resetting: {e}")

            # New day or no state file - initialize
            self._count = 0
            self._date = today
            self._save_state_locked()
            logger.info(
                f"AICallTracker initialized: new day, "
                f"0/{self.max_calls} calls"
            )

    def _save_state_locked(self) -> None:
        """Save state to file (must hold lock)."""
        state = {
            'date': self._date,
            'count': self._count,
            'max_calls': self.max_calls,
            'updated_at': datetime.now().isoformat()
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def _check_day_reset(self) -> None:
        """Reset counter if new day (must hold lock)."""
        today = date.today().isoformat()
        if self._date != today:
            logger.info(
                f"AICallTracker: new day detected, resetting counter "
                f"({self._count} calls yesterday)"
            )
            self._count = 0
            self._date = today
            self._save_state_locked()

    def can_call(self) -> bool:
        """
        Check if we can make another AI call.

        Returns:
            True if under limit, False if limit reached
        """
        with self.lock:
            self._check_day_reset()
            return self._count < self.max_calls

    def record_call(self) -> bool:
        """
        Record an AI call.

        Returns:
            True if call was recorded, False if limit was already reached
        """
        with self.lock:
            self._check_day_reset()

            if self._count >= self.max_calls:
                logger.warning(
                    f"AICallTracker: limit reached ({self.max_calls} calls/day)"
                )
                return False

            self._count += 1
            self._save_state_locked()

            if self._count % 50 == 0 or self._count == self.max_calls:
                logger.info(
                    f"AICallTracker: {self._count}/{self.max_calls} calls today"
                )

            return True

    def remaining(self) -> int:
        """
        Get remaining calls for today.

        Returns:
            Number of calls remaining
        """
        with self.lock:
            self._check_day_reset()
            return max(0, self.max_calls - self._count)

    @property
    def count(self) -> int:
        """Current call count for today."""
        with self.lock:
            self._check_day_reset()
            return self._count

    def status(self) -> dict:
        """
        Get current status for logging/monitoring.

        Returns:
            Dict with date, count, max_calls, remaining, pct_used
        """
        with self.lock:
            self._check_day_reset()
            return {
                'date': self._date,
                'count': self._count,
                'max_calls': self.max_calls,
                'remaining': max(0, self.max_calls - self._count),
                'pct_used': round(self._count / self.max_calls * 100, 1)
            }


def seconds_until_midnight() -> int:
    """
    Calculate seconds until midnight (local time).

    Returns:
        Seconds until 00:00:00 tomorrow
    """
    now = datetime.now()
    midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
    return int((midnight - now).total_seconds())
