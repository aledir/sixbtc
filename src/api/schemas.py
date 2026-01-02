"""
Pydantic schemas for API request/response models
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# SERVICE STATUS
# =============================================================================

class ServiceInfo(BaseModel):
    """Single service status"""
    name: str
    status: str  # RUNNING, STOPPED, ERROR
    pid: Optional[int] = None
    uptime_seconds: Optional[int] = None


class PipelineCounts(BaseModel):
    """Strategy counts by status"""
    generated: int = Field(alias="GENERATED", default=0)
    validated: int = Field(alias="VALIDATED", default=0)
    tested: int = Field(alias="TESTED", default=0)
    selected: int = Field(alias="SELECTED", default=0)
    live: int = Field(alias="LIVE", default=0)
    retired: int = Field(alias="RETIRED", default=0)
    failed: int = Field(alias="FAILED", default=0)

    class Config:
        populate_by_name = True


class PortfolioSummary(BaseModel):
    """Portfolio performance summary"""
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    pnl_24h: float = 0.0
    pnl_24h_pct: float = 0.0
    pnl_7d: float = 0.0
    pnl_7d_pct: float = 0.0
    max_drawdown: float = 0.0
    open_positions: int = 0
    trades_today: int = 0


class Alert(BaseModel):
    """System alert"""
    level: str  # info, warning, error
    message: str
    timestamp: datetime


class StatusResponse(BaseModel):
    """Main status endpoint response"""
    uptime_seconds: int
    pipeline: Dict[str, int]
    services: List[ServiceInfo]
    portfolio: PortfolioSummary
    alerts: List[Alert] = []


# =============================================================================
# STRATEGIES
# =============================================================================

class StrategyListItem(BaseModel):
    """Strategy in list view"""
    id: UUID
    name: str
    strategy_type: Optional[str] = None
    timeframe: Optional[str] = None
    status: str
    sharpe_ratio: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: Optional[int] = None
    total_pnl: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BacktestMetrics(BaseModel):
    """Backtest result metrics"""
    sharpe_ratio: Optional[float] = None
    win_rate: Optional[float] = None
    expectancy: Optional[float] = None
    max_drawdown: Optional[float] = None
    total_trades: Optional[int] = None
    total_return: Optional[float] = None
    ed_ratio: Optional[float] = None
    consistency: Optional[float] = None
    period_type: Optional[str] = None
    period_days: Optional[int] = None


class StrategyDetail(BaseModel):
    """Full strategy detail"""
    id: UUID
    name: str
    strategy_type: Optional[str] = None
    timeframe: Optional[str] = None
    status: str
    code: Optional[str] = None
    pattern_ids: Optional[List[str]] = None
    pattern_coins: Optional[List[str]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    backtest: Optional[BacktestMetrics] = None
    live_pnl: Optional[float] = None
    live_trades: Optional[int] = None

    class Config:
        from_attributes = True


class StrategiesResponse(BaseModel):
    """Paginated strategies list"""
    items: List[StrategyListItem]
    total: int
    limit: int
    offset: int


# =============================================================================
# TRADES
# =============================================================================

class TradeItem(BaseModel):
    """Trade record"""
    id: UUID
    strategy_id: UUID
    strategy_name: Optional[str] = None
    symbol: str
    side: str  # long, short
    status: str  # open, closed
    entry_price: float
    exit_price: Optional[float] = None
    size: float
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    subaccount_index: Optional[int] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TradesResponse(BaseModel):
    """Paginated trades list"""
    items: List[TradeItem]
    total: int
    limit: int
    offset: int


class TradesSummary(BaseModel):
    """Aggregated trade statistics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0


# =============================================================================
# SUBACCOUNTS
# =============================================================================

class SubaccountInfo(BaseModel):
    """Subaccount status"""
    index: int
    status: str  # active, idle, error
    strategy_id: Optional[UUID] = None
    strategy_name: Optional[str] = None
    balance: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    open_positions: int = 0
    last_trade_at: Optional[datetime] = None


class SubaccountsResponse(BaseModel):
    """All subaccounts"""
    items: List[SubaccountInfo]
    total_balance: float
    total_pnl: float


# =============================================================================
# SERVICES (Supervisor)
# =============================================================================

class ServiceControl(BaseModel):
    """Service control request"""
    action: str  # start, stop, restart


class ServiceControlResponse(BaseModel):
    """Service control response"""
    success: bool
    message: str
    service: str
    action: str


# =============================================================================
# LOGS
# =============================================================================

class LogLine(BaseModel):
    """Single log line"""
    timestamp: datetime
    level: str
    logger: str
    message: str


class LogsResponse(BaseModel):
    """Log lines response"""
    service: str
    lines: List[LogLine]
    total_lines: int


# =============================================================================
# CONFIG
# =============================================================================

class ConfigResponse(BaseModel):
    """Configuration response (sanitized, no secrets)"""
    config: Dict[str, Any]


# =============================================================================
# EQUITY / PERFORMANCE
# =============================================================================

class EquityPoint(BaseModel):
    """Single equity data point"""
    timestamp: datetime
    equity: float
    pnl: float


class EquityResponse(BaseModel):
    """Equity curve data"""
    points: List[EquityPoint]
    start_equity: float
    current_equity: float
    total_return_pct: float
