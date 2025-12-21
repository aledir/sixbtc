"""
Unit tests for HealthChecker

Tests system health monitoring functionality.
"""

import pytest
from src.monitor.health_check import HealthChecker, HealthStatus


class MockDataProvider:
    """Mock data provider for testing"""
    def __init__(self, connected=True):
        self._connected = connected
    
    def is_connected(self):
        return self._connected


class MockDatabase:
    """Mock database for testing"""
    def __init__(self, connected=True):
        self._connected = connected
    
    def is_connected(self):
        return self._connected


class TestHealthChecker:
    """Test suite for HealthChecker"""

    def test_init_no_dependencies(self):
        """Test initialization without dependencies"""
        checker = HealthChecker()
        
        assert checker.data_provider is None
        assert checker.database is None
        assert checker.critical_error_count == 0

    def test_init_with_dependencies(self):
        """Test initialization with dependencies"""
        data_provider = MockDataProvider()
        database = MockDatabase()
        
        checker = HealthChecker(
            data_provider=data_provider,
            database=database
        )
        
        assert checker.data_provider is data_provider
        assert checker.database is database

    def test_check_all_healthy(self):
        """Test health check when all systems OK"""
        data_provider = MockDataProvider(connected=True)
        database = MockDatabase(connected=True)
        
        checker = HealthChecker(
            data_provider=data_provider,
            database=database
        )
        
        status = checker.check_all()
        
        assert status.healthy is True
        assert status.websocket == 'OK'
        assert status.database == 'OK'
        assert status.critical_errors == 0
        assert "operational" in status.message.lower()

    def test_check_all_websocket_down(self):
        """Test health check with WebSocket down"""
        data_provider = MockDataProvider(connected=False)
        database = MockDatabase(connected=True)
        
        checker = HealthChecker(
            data_provider=data_provider,
            database=database
        )
        
        status = checker.check_all()
        
        assert status.healthy is False
        assert status.websocket == 'ERROR'
        assert status.database == 'OK'
        assert "degraded" in status.message.lower()

    def test_check_all_database_down(self):
        """Test health check with database down"""
        data_provider = MockDataProvider(connected=True)
        database = MockDatabase(connected=False)
        
        checker = HealthChecker(
            data_provider=data_provider,
            database=database
        )
        
        status = checker.check_all()
        
        assert status.healthy is False
        assert status.websocket == 'OK'
        assert status.database == 'ERROR'

    def test_check_all_no_providers(self):
        """Test health check without providers (UNKNOWN state)"""
        checker = HealthChecker()
        
        status = checker.check_all()
        
        # Without providers, status is UNKNOWN (not healthy)
        assert status.websocket == 'UNKNOWN'
        assert status.database == 'UNKNOWN'

    def test_record_error_critical(self):
        """Test recording critical error"""
        checker = HealthChecker()
        
        assert checker.critical_error_count == 0
        
        checker.record_error(is_critical=True)
        assert checker.critical_error_count == 1
        
        checker.record_error(is_critical=True)
        assert checker.critical_error_count == 2

    def test_record_error_non_critical(self):
        """Test recording non-critical error"""
        checker = HealthChecker()
        
        checker.record_error(is_critical=False)
        assert checker.critical_error_count == 0

    def test_reset_errors(self):
        """Test resetting error counter"""
        checker = HealthChecker()
        
        checker.record_error(is_critical=True)
        checker.record_error(is_critical=True)
        assert checker.critical_error_count == 2
        
        checker.reset_errors()
        assert checker.critical_error_count == 0

    def test_critical_errors_affect_health(self):
        """Test that critical errors mark system unhealthy"""
        data_provider = MockDataProvider(connected=True)
        database = MockDatabase(connected=True)
        
        checker = HealthChecker(
            data_provider=data_provider,
            database=database
        )
        
        # Initially healthy
        status = checker.check_all()
        assert status.healthy is True
        
        # Record critical error
        checker.record_error(is_critical=True)
        
        # Now unhealthy
        status = checker.check_all()
        assert status.healthy is False
        assert status.critical_errors == 1

    def test_health_status_to_dict(self):
        """Test HealthStatus to_dict conversion"""
        status = HealthStatus(
            healthy=True,
            websocket='OK',
            database='OK',
            strategies_loaded=10,
            critical_errors=0,
            message="All good"
        )
        
        result = status.to_dict()
        
        assert isinstance(result, dict)
        assert result['healthy'] is True
        assert result['websocket'] == 'OK'
        assert result['database'] == 'OK'
        assert result['strategies_loaded'] == 10
        assert result['critical_errors'] == 0
        assert result['message'] == "All good"

    def test_check_websocket_exception_handling(self):
        """Test WebSocket check handles exceptions"""
        class BrokenDataProvider:
            def is_connected(self):
                raise RuntimeError("Connection check failed")
        
        checker = HealthChecker(data_provider=BrokenDataProvider())
        
        status = checker.check_all()
        
        # Should return ERROR, not crash
        assert status.websocket == 'ERROR'
        assert status.healthy is False

    def test_check_database_exception_handling(self):
        """Test database check handles exceptions"""
        class BrokenDatabase:
            def is_connected(self):
                raise RuntimeError("Database connection failed")
        
        checker = HealthChecker(database=BrokenDatabase())
        
        status = checker.check_all()
        
        # Should return ERROR, not crash
        assert status.database == 'ERROR'
        assert status.healthy is False
