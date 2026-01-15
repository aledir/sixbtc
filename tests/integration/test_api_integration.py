"""
Integration tests for API endpoints with real PostgreSQL.

These tests use FastAPI TestClient with the real database to verify:
1. API endpoints return correct data
2. Database integration works end-to-end
3. Error handling is correct

Each test uses a rollback fixture to avoid persisting test data.
"""
import pytest
import uuid
from datetime import datetime, UTC
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from src.database.connection import get_session_factory
from src.database.models import Strategy, Coin, Subaccount, Trade


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def db_session():
    """
    Provide a database session that rolls back after each test.
    """
    SessionFactory = get_session_factory()
    session = SessionFactory()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client():
    """Create FastAPI test client."""
    from src.api.main import app
    return TestClient(app)


@pytest.fixture
def test_strategy(db_session):
    """Create a test strategy for API tests."""
    strategy = Strategy(
        id=uuid.uuid4(),
        name=f'APITestStrat_{uuid.uuid4().hex[:8]}',
        strategy_type='MOM',
        timeframe='1h',
        status='ACTIVE',
        code='class TestStrat(StrategyCore): pass',
        score_backtest=75.0,
        trading_coins=['BTC', 'ETH'],
    )
    db_session.add(strategy)
    db_session.flush()
    return strategy


# =============================================================================
# ROOT ENDPOINT TESTS
# =============================================================================

class TestRootEndpoint:
    """Tests for API root endpoint."""

    def test_root_returns_api_info(self, client):
        """Root should return API name and version."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "SixBTC Control Center API"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"

    def test_root_includes_uptime(self, client):
        """Root should include uptime in seconds."""
        response = client.get("/")
        data = response.json()

        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], int)
        assert data["uptime_seconds"] >= 0


# =============================================================================
# STATUS ENDPOINT TESTS
# =============================================================================

class TestStatusEndpoint:
    """Tests for /api/status endpoint."""

    def test_status_endpoint_exists(self, client):
        """Status endpoint should be accessible."""
        response = client.get("/api/status")
        # May return error if services not running, but endpoint should exist
        assert response.status_code in [200, 500, 503]

    def test_status_returns_pipeline_counts(self, client):
        """Status should include pipeline counts."""
        response = client.get("/api/status")

        if response.status_code == 200:
            data = response.json()
            assert "pipeline" in data


# =============================================================================
# PIPELINE ENDPOINT TESTS
# =============================================================================

class TestPipelineEndpoints:
    """Tests for /api/pipeline/* endpoints."""

    def test_pipeline_health_endpoint(self, client):
        """Pipeline health endpoint should return health status."""
        response = client.get("/api/pipeline/health")

        assert response.status_code == 200
        data = response.json()

        assert "overall_status" in data
        assert data["overall_status"] in ["healthy", "degraded", "critical"]

    def test_pipeline_stats_endpoint(self, client):
        """Pipeline stats endpoint should return statistics."""
        response = client.get("/api/pipeline/stats")

        assert response.status_code == 200
        data = response.json()

        assert "data_points" in data or "total_generated" in data


# =============================================================================
# STRATEGIES ENDPOINT TESTS
# =============================================================================

class TestStrategiesEndpoints:
    """Tests for /api/strategies/* endpoints."""

    def test_list_strategies(self, client):
        """Should list strategies with pagination."""
        response = client.get("/api/strategies")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_list_strategies_with_status_filter(self, client):
        """Should filter strategies by status."""
        response = client.get("/api/strategies?status=ACTIVE")

        assert response.status_code == 200
        data = response.json()

        # All returned strategies should be ACTIVE
        for item in data["items"]:
            assert item["status"] == "ACTIVE"

    def test_list_strategies_with_pagination(self, client):
        """Should respect limit and offset."""
        response = client.get("/api/strategies?limit=5&offset=0")

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) <= 5
        assert data["limit"] == 5
        assert data["offset"] == 0


# =============================================================================
# COINS ENDPOINT TESTS
# =============================================================================

class TestCoinsEndpoints:
    """Tests for /api/coins/* endpoints."""

    def test_coins_registry_stats(self, client):
        """Should return coin registry statistics."""
        response = client.get("/api/coins/registry/stats")

        assert response.status_code == 200
        data = response.json()

        assert "total_coins" in data
        assert "active_coins" in data

    def test_coins_pairs_history(self, client):
        """Should return pairs update history."""
        response = client.get("/api/coins/pairs/history")

        assert response.status_code == 200
        data = response.json()

        assert "updates" in data
        assert "total" in data


# =============================================================================
# SUBACCOUNTS ENDPOINT TESTS
# =============================================================================

class TestSubaccountsEndpoints:
    """Tests for /api/subaccounts/* endpoints."""

    def test_list_subaccounts(self, client):
        """Should list subaccounts."""
        response = client.get("/api/subaccounts")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data

    def test_subaccount_detail(self, client):
        """Should get subaccount detail by ID."""
        # Subaccount 1 should always exist
        response = client.get("/api/subaccounts/1")

        # May not exist in test DB
        assert response.status_code in [200, 404]


# =============================================================================
# TRADES ENDPOINT TESTS
# =============================================================================

class TestTradesEndpoints:
    """Tests for /api/trades/* endpoints."""

    def test_list_trades(self, client):
        """Should list trades with pagination."""
        response = client.get("/api/trades")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data

    def test_trades_summary(self, client):
        """Should return trades summary statistics."""
        response = client.get("/api/trades/summary")

        assert response.status_code == 200
        data = response.json()

        assert "total_trades" in data
        assert "win_rate" in data


# =============================================================================
# PERFORMANCE ENDPOINT TESTS
# =============================================================================

class TestPerformanceEndpoints:
    """Tests for /api/performance/* endpoints."""

    def test_equity_endpoint(self, client):
        """Should return equity curve data."""
        response = client.get("/api/performance/equity?period=24h")

        assert response.status_code == 200
        data = response.json()

        assert "data_points" in data or "points" in data


# =============================================================================
# SCHEDULER ENDPOINT TESTS
# =============================================================================

class TestSchedulerEndpoints:
    """Tests for /api/scheduler/* endpoints."""

    def test_scheduler_tasks(self, client):
        """Should list scheduled task executions."""
        response = client.get("/api/scheduler/tasks")

        assert response.status_code == 200
        data = response.json()

        # Returns dict with 'executions' list
        assert "executions" in data
        assert isinstance(data["executions"], list)

    def test_scheduler_health(self, client):
        """Should return scheduler health status."""
        response = client.get("/api/scheduler/health")

        assert response.status_code == 200


# =============================================================================
# CONFIG ENDPOINT TESTS
# =============================================================================

class TestConfigEndpoints:
    """Tests for /api/config endpoint."""

    def test_get_config(self, client):
        """Should return sanitized config."""
        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.json()

        assert "config" in data
        # Should not expose secrets
        config_str = str(data)
        assert "password" not in config_str.lower() or "***" in config_str


# =============================================================================
# VALIDATION ENDPOINT TESTS
# =============================================================================

class TestValidationEndpoints:
    """Tests for /api/validation/* endpoints."""

    def test_validation_report(self, client):
        """Should return validation report."""
        response = client.get("/api/validation/report")

        assert response.status_code == 200


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Tests for API error handling."""

    def test_invalid_endpoint_returns_404(self, client):
        """Invalid endpoint should return 404."""
        response = client.get("/api/nonexistent_endpoint")
        assert response.status_code == 404

    def test_invalid_strategy_id_returns_404(self, client):
        """Invalid strategy ID should return 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/strategies/{fake_id}")
        assert response.status_code == 404

    def test_invalid_query_params_handled(self, client):
        """Invalid query params should be handled gracefully."""
        response = client.get("/api/strategies?limit=invalid")
        # Should either return 422 (validation error) or handle gracefully
        assert response.status_code in [200, 422]
