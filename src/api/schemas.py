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
    active: int = Field(alias="ACTIVE", default=0)
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
    trading_coins: Optional[List[str]] = None
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
# PIPELINE HEALTH
# =============================================================================

class PipelineStageHealth(BaseModel):
    """Health metrics for a single pipeline stage"""
    stage: str  # "generation", "validation", "backtesting", "classification"
    status: str  # "healthy", "backpressure", "stalled", "error"
    queue_depth: int  # Current strategies in this stage
    queue_limit: int  # Configured limit from config
    utilization_pct: float  # queue_depth / queue_limit * 100

    # Processing metrics (last 1 hour)
    processing_rate: float  # Strategies/hour
    avg_processing_time: Optional[float] = None  # Seconds per strategy
    active_workers: int  # Current parallel processes
    max_workers: int  # Configured parallelism

    # Quality metrics
    success_rate: float  # % strategies passing this stage
    failure_rate: float  # % failing

    # Recent activity
    processed_last_hour: int
    processed_last_24h: int
    failed_last_hour: int


class PipelineHealthResponse(BaseModel):
    """Full pipeline health status"""
    timestamp: datetime
    overall_status: str  # "healthy", "degraded", "critical"
    stages: List[PipelineStageHealth]
    bottleneck: Optional[str] = None  # Stage name if identified
    throughput_strategies_per_hour: float  # End-to-end
    critical_issues: List[str] = []  # Actionable alerts


class PipelineTimeSeriesPoint(BaseModel):
    """Single data point in pipeline time series"""
    timestamp: datetime
    stage: str
    throughput: float  # Strategies/hour
    avg_processing_time: Optional[float] = None  # Seconds
    queue_depth: int
    failures: int


class PipelineStatsResponse(BaseModel):
    """Historical pipeline statistics"""
    period_hours: int
    data_points: List[PipelineTimeSeriesPoint]
    total_generated: int
    total_validated: int
    total_active: int
    total_live: int
    overall_throughput: float
    bottleneck_stage: str


class QualityBucket(BaseModel):
    """Strategy count in quality range"""
    range: str  # "0-20", "20-40", "40-60", "60-80", "80-100"
    count: int
    avg_sharpe: float
    avg_win_rate: float


class QualityDistribution(BaseModel):
    """Quality distribution for one stage"""
    stage: str  # "ACTIVE", "LIVE"
    buckets: List[QualityBucket]
    by_type: Dict[str, int]  # {"MOM": 45, "REV": 23, ...}
    by_timeframe: Dict[str, int]  # {"15m": 30, "1h": 25, ...}


class QualityDistributionResponse(BaseModel):
    """Quality distribution across stages"""
    distributions: List[QualityDistribution]


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


# =============================================================================
# STRATEGY RANKINGS
# =============================================================================

class RankedStrategy(BaseModel):
    """Single ranked strategy"""
    id: UUID
    name: str
    strategy_type: str
    timeframe: str
    status: str
    score: Optional[float] = None
    sharpe: Optional[float] = None
    expectancy: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: Optional[int] = None
    max_drawdown: Optional[float] = None
    ranking_type: str  # "backtest" or "live"

    # Live-specific fields
    score_backtest: Optional[float] = None
    total_pnl: Optional[float] = None
    degradation_pct: Optional[float] = None
    last_update: Optional[datetime] = None


class RankingResponse(BaseModel):
    """Strategy ranking response"""
    ranking_type: str  # "backtest" or "live"
    count: int
    strategies: List[RankedStrategy]
    avg_score: float
    avg_sharpe: Optional[float] = None
    avg_pnl: Optional[float] = None  # Live only


# =============================================================================
# DEGRADATION MONITORING
# =============================================================================

class DegradationPoint(BaseModel):
    """Single strategy degradation data point"""
    id: UUID
    name: str
    strategy_type: str
    timeframe: str
    score_backtest: Optional[float] = None
    score_live: Optional[float] = None
    degradation_pct: Optional[float] = None
    total_pnl: Optional[float] = None
    total_trades_live: Optional[int] = None
    live_since: Optional[datetime] = None


class DegradationResponse(BaseModel):
    """Degradation analysis response"""
    total_live_strategies: int
    degrading_count: int  # degradation > threshold
    avg_degradation: float
    worst_degraders: List[DegradationPoint]
    all_points: List[DegradationPoint]  # For scatter plot


# ============================================================================
# Performance Analytics Schemas
# ============================================================================


class EquityPoint(BaseModel):
    """Single point in equity curve"""

    timestamp: str
    equity: float
    balance: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float


class PerformanceEquityResponse(BaseModel):
    """Equity curve with performance metrics"""

    period: str  # "24h", "7d", etc.
    subaccount_id: int | None = None
    data_points: List[EquityPoint]

    # Summary metrics
    start_equity: float
    end_equity: float
    peak_equity: float
    max_drawdown: float  # As decimal (0.15 = 15% drawdown)
    current_drawdown: float
    total_return: float  # As decimal (0.05 = 5% return)


# ============================================================================
# Scheduled Tasks Schemas
# ============================================================================

class TaskExecutionDetailResponse(BaseModel):
    """Single task execution detail"""
    id: str
    task_name: str
    task_type: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    metadata: dict = {}
    triggered_by: str = 'system'


class TaskExecutionListResponse(BaseModel):
    """List of task executions"""
    executions: List[TaskExecutionDetailResponse]
    total: int


class TaskStatsResponse(BaseModel):
    """Statistics for a specific task"""
    task_name: str
    period_hours: int
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_duration_seconds: Optional[float] = None
    failure_rate: float
    last_execution: Optional[str] = None


class TaskTriggerRequest(BaseModel):
    """Request to manually trigger a task"""
    triggered_by: str


class TaskTriggerResponse(BaseModel):
    """Response from task trigger"""
    success: bool
    message: str
    execution_id: Optional[str] = None


# ============================================================================
# Coin Registry Schemas
# ============================================================================

class CoinRegistryStatsResponse(BaseModel):
    """CoinRegistry cache statistics"""
    total_coins: int
    active_coins: int
    cache_age_seconds: Optional[float] = None
    db_updated_at: Optional[str] = None


class PairsUpdateDetailResponse(BaseModel):
    """Detailed pairs update result"""
    execution_id: str
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: str
    total_pairs: int
    new_pairs: int
    updated_pairs: int
    deactivated_pairs: int
    top_10_symbols: List[str] = []


class PairsUpdateHistoryResponse(BaseModel):
    """History of pairs updates"""
    updates: List[PairsUpdateDetailResponse]
    total: int
