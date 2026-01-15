"""
Tests for the API module.

Covers:
1. Root endpoint - health check
2. ConnectionManager - WebSocket management
3. API lifespan - startup/shutdown
4. Pydantic schemas - validation
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.api.main import ConnectionManager, get_uptime_seconds


# =============================================================================
# CONNECTION MANAGER TESTS
# =============================================================================

class TestConnectionManager:
    """Tests for WebSocket ConnectionManager."""

    def test_connection_manager_init(self):
        """ConnectionManager should initialize with empty connections."""
        manager = ConnectionManager()
        assert manager.active_connections == []

    @pytest.mark.asyncio
    async def test_connect_adds_websocket(self):
        """connect() should add websocket to active connections."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()

        await manager.connect(mock_ws)

        assert mock_ws in manager.active_connections
        mock_ws.accept.assert_called_once()

    def test_disconnect_removes_websocket(self):
        """disconnect() should remove websocket from active connections."""
        manager = ConnectionManager()
        mock_ws = MagicMock()
        manager.active_connections.append(mock_ws)

        manager.disconnect(mock_ws)

        assert mock_ws not in manager.active_connections

    def test_disconnect_handles_missing_websocket(self):
        """disconnect() should handle websocket not in list."""
        manager = ConnectionManager()
        mock_ws = MagicMock()

        # Should not raise error
        manager.disconnect(mock_ws)
        assert manager.active_connections == []

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        """broadcast() should send message to all connections."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        manager.active_connections = [ws1, ws2]

        await manager.broadcast({"type": "test", "data": "hello"})

        ws1.send_json.assert_called_once_with({"type": "test", "data": "hello"})
        ws2.send_json.assert_called_once_with({"type": "test", "data": "hello"})

    @pytest.mark.asyncio
    async def test_broadcast_handles_errors(self):
        """broadcast() should continue if one connection fails."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws1.send_json.side_effect = Exception("Connection lost")
        ws2 = AsyncMock()
        manager.active_connections = [ws1, ws2]

        # Should not raise
        await manager.broadcast({"type": "test"})

        # ws2 should still receive message
        ws2.send_json.assert_called_once()


# =============================================================================
# UPTIME TESTS
# =============================================================================

class TestUptime:
    """Tests for uptime tracking."""

    def test_get_uptime_returns_positive(self):
        """get_uptime_seconds() should return positive integer."""
        uptime = get_uptime_seconds()
        assert isinstance(uptime, int)
        assert uptime >= 0


# =============================================================================
# PYDANTIC SCHEMA TESTS
# =============================================================================

class TestSchemas:
    """Tests for Pydantic schemas."""

    def test_service_info_schema(self):
        """ServiceInfo should validate correctly."""
        from src.api.schemas import ServiceInfo

        service = ServiceInfo(
            name="executor",
            status="RUNNING",
            pid=12345,
            uptime_seconds=3600,
        )
        assert service.name == "executor"
        assert service.status == "RUNNING"

    def test_service_info_optional_fields(self):
        """ServiceInfo should accept missing optional fields."""
        from src.api.schemas import ServiceInfo

        service = ServiceInfo(
            name="generator",
            status="STOPPED",
        )
        assert service.pid is None
        assert service.uptime_seconds is None

    def test_pipeline_counts_schema(self):
        """PipelineCounts should use aliases correctly."""
        from src.api.schemas import PipelineCounts

        counts = PipelineCounts(
            GENERATED=50,
            VALIDATED=30,
            ACTIVE=100,
            LIVE=5,
            RETIRED=20,
            FAILED=10,
        )
        assert counts.generated == 50
        assert counts.active == 100
        assert counts.live == 5

    def test_portfolio_summary_defaults(self):
        """PortfolioSummary should have sensible defaults."""
        from src.api.schemas import PortfolioSummary

        summary = PortfolioSummary()
        assert summary.total_pnl == 0.0
        assert summary.open_positions == 0
        assert summary.trades_today == 0

    def test_strategy_list_item_from_attributes(self):
        """StrategyListItem should work with from_attributes."""
        from src.api.schemas import StrategyListItem
        from uuid import uuid4

        item = StrategyListItem(
            id=uuid4(),
            name="TestStrat_MOM_abc12345",
            strategy_type="MOM",
            timeframe="1h",
            status="ACTIVE",
            created_at=datetime.now(),
        )
        assert "MOM" in item.name or item.strategy_type == "MOM"
        assert item.status == "ACTIVE"

    def test_backtest_metrics_optional(self):
        """BacktestMetrics should accept all optional fields."""
        from src.api.schemas import BacktestMetrics

        metrics = BacktestMetrics()
        assert metrics.sharpe_ratio is None
        assert metrics.win_rate is None

    def test_backtest_metrics_with_values(self):
        """BacktestMetrics should store provided values."""
        from src.api.schemas import BacktestMetrics

        metrics = BacktestMetrics(
            sharpe_ratio=1.5,
            win_rate=0.58,
            expectancy=0.025,
            max_drawdown=0.15,
            total_trades=150,
        )
        assert metrics.sharpe_ratio == 1.5
        assert metrics.total_trades == 150

    def test_trade_item_schema(self):
        """TradeItem should validate trade data."""
        from src.api.schemas import TradeItem
        from uuid import uuid4

        trade = TradeItem(
            id=uuid4(),
            strategy_id=uuid4(),
            symbol="BTC",
            side="long",
            status="closed",
            entry_price=50000.0,
            exit_price=51000.0,
            size=0.1,
            pnl=100.0,
            opened_at=datetime.now(),
        )
        assert trade.symbol == "BTC"
        assert trade.pnl == 100.0

    def test_subaccount_info_schema(self):
        """SubaccountInfo should validate subaccount data."""
        from src.api.schemas import SubaccountInfo

        subaccount = SubaccountInfo(
            index=1,
            status="active",
            balance=100.0,
            pnl=10.0,
            pnl_pct=0.10,
        )
        assert subaccount.index == 1
        assert subaccount.balance == 100.0

    def test_alert_schema(self):
        """Alert should validate alert data."""
        from src.api.schemas import Alert

        alert = Alert(
            level="warning",
            message="High drawdown detected",
            timestamp=datetime.now(),
        )
        assert alert.level == "warning"
        assert "drawdown" in alert.message

    def test_pipeline_stage_health_schema(self):
        """PipelineStageHealth should validate health metrics."""
        from src.api.schemas import PipelineStageHealth

        health = PipelineStageHealth(
            stage="validation",
            status="healthy",
            queue_depth=30,
            queue_limit=100,
            utilization_pct=30.0,
            processing_rate=50.0,
            active_workers=4,
            max_workers=8,
            success_rate=0.85,
            failure_rate=0.15,
            processed_last_hour=50,
            processed_last_24h=1200,
            failed_last_hour=5,
        )
        assert health.stage == "validation"
        assert health.utilization_pct == 30.0

    def test_equity_point_schema(self):
        """EquityPoint should validate equity data."""
        from src.api.schemas import EquityPoint

        point = EquityPoint(
            timestamp="2024-01-15T12:00:00",
            equity=10500.0,
            balance=10000.0,
            unrealized_pnl=500.0,
            realized_pnl=0.0,
            total_pnl=500.0,
        )
        assert point.equity == 10500.0

    def test_coin_registry_stats_schema(self):
        """CoinRegistryStatsResponse should validate stats."""
        from src.api.schemas import CoinRegistryStatsResponse

        stats = CoinRegistryStatsResponse(
            total_coins=150,
            active_coins=100,
            cache_age_seconds=300.0,
        )
        assert stats.total_coins == 150
        assert stats.active_coins == 100


# =============================================================================
# API APP STRUCTURE TESTS
# =============================================================================

class TestAPIAppStructure:
    """Tests for API app structure without running server."""

    def test_app_title(self):
        """App should have correct title."""
        from src.api.main import app
        assert app.title == "SixBTC Control Center"

    def test_app_version(self):
        """App should have correct version."""
        from src.api.main import app
        assert app.version == "1.0.0"

    def test_app_has_cors_middleware(self):
        """App should have CORS middleware configured."""
        from src.api.main import app
        # Check middleware stack
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert 'CORSMiddleware' in middleware_classes

    def test_app_has_routes(self):
        """App should have routes registered."""
        from src.api.main import app
        route_paths = [r.path for r in app.routes]

        # Should have root endpoint
        assert '/' in route_paths

        # Should have WebSocket endpoint
        assert '/ws/live' in route_paths
