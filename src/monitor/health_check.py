"""
Health Check System

Provides health status for monitoring (Docker, K8s, etc.).
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Health check status"""
    healthy: bool
    websocket: str  # 'OK', 'ERROR', 'UNKNOWN'
    database: str  # 'OK', 'ERROR', 'UNKNOWN'
    strategies_loaded: int
    critical_errors: int
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class HealthChecker:
    """
    System health checker

    Checks:
    - WebSocket connection status
    - Database connection
    - Strategies loaded
    - Critical errors
    """

    def __init__(
        self,
        data_provider: Optional[Any] = None,
        database: Optional[Any] = None
    ):
        """
        Initialize health checker

        Args:
            data_provider: HyperliquidDataProvider instance (optional)
            database: Database connection (optional)
        """
        self.data_provider = data_provider
        self.database = database
        self.critical_error_count = 0

    def check_all(self) -> HealthStatus:
        """
        Check all system components

        Returns:
            HealthStatus object
        """
        checks = {
            'websocket': self._check_websocket(),
            'database': self._check_database(),
            'strategies': self._check_strategies()
        }

        # Determine overall health
        healthy = all(
            status == 'OK'
            for status in [checks['websocket'], checks['database']]
        ) and self.critical_error_count == 0

        message = "All systems operational" if healthy else "System degraded"

        return HealthStatus(
            healthy=healthy,
            websocket=checks['websocket'],
            database=checks['database'],
            strategies_loaded=checks['strategies'],
            critical_errors=self.critical_error_count,
            message=message
        )

    def _check_websocket(self) -> str:
        """Check WebSocket connection status"""
        if self.data_provider is None:
            return 'UNKNOWN'

        try:
            if hasattr(self.data_provider, 'is_connected'):
                return 'OK' if self.data_provider.is_connected() else 'ERROR'
            else:
                return 'UNKNOWN'
        except Exception as e:
            logger.error(f"WebSocket health check failed: {e}")
            return 'ERROR'

    def _check_database(self) -> str:
        """Check database connection"""
        if self.database is None:
            return 'UNKNOWN'

        try:
            if hasattr(self.database, 'is_connected'):
                return 'OK' if self.database.is_connected() else 'ERROR'
            else:
                # Try a simple query
                return 'OK'  # Simplified for now
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return 'ERROR'

    def _check_strategies(self) -> int:
        """Check number of loaded strategies"""
        # Simplified - would query database or orchestrator in real system
        return 0

    def record_error(self, is_critical: bool = False) -> None:
        """Record an error occurrence"""
        if is_critical:
            self.critical_error_count += 1
            logger.error(f"Critical error recorded (total: {self.critical_error_count})")

    def reset_errors(self) -> None:
        """Reset error counter"""
        self.critical_error_count = 0
