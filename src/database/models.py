"""
SQLAlchemy Models for SixBTC

Database schema for:
- Strategies (generated, tested, live)
- Backtest results
- Live trades
- Performance snapshots
"""

import uuid
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, JSON,
    ForeignKey, Enum, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# ==============================================================================
# STRATEGY TEMPLATES
# ==============================================================================

class StrategyTemplate(Base):
    """
    Parameterized strategy template

    AI generates templates with Jinja2 placeholders.
    ParametricGenerator creates strategy variations from templates.
    """
    __tablename__ = "strategy_templates"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identity
    name = Column(String(255), unique=True, nullable=False, index=True)
    # Example: "TPL_MOM_abc123"

    strategy_type = Column(String(50), nullable=False, index=True)
    # Example: "MOM", "REV", "TRN", "BRE", "VOL", "SCA"

    timeframe = Column(String(10), nullable=False, index=True)
    # Example: "15m", "1h", "4h"

    # Template code with Jinja2 placeholders
    code_template = Column(Text, nullable=False)
    # Example: rsi = ta.RSI(df['close'], timeperiod={{ rsi_period }})

    # Parameter schema (defines variable parameters and their values)
    parameters_schema = Column(JSON, nullable=False)
    # Example: {
    #   "rsi_period": {"type": "int", "values": [7, 14, 21, 28]},
    #   "threshold": {"type": "int", "values": [25, 30, 35]},
    #   "atr_mult": {"type": "float", "values": [1.5, 2.0, 2.5]}
    # }

    # Template structure (1-21, defines entry/exit components)
    structure_id = Column(Integer, nullable=True, index=True)
    # Maps to VALID_STRUCTURES in template_generator.py
    # 1-7: Long only, 8-14: Short only, 15-21: Bidirectional

    # Generation metadata
    ai_provider = Column(String(50))
    generation_prompt = Column(Text)

    # Tracking
    strategies_generated = Column(Integer, default=0)
    strategies_profitable = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_template_type_timeframe', 'strategy_type', 'timeframe'),
    )

    def __repr__(self):
        return f"<StrategyTemplate(name={self.name}, type={self.strategy_type})>"


# ==============================================================================
# STRATEGIES
# ==============================================================================

class Strategy(Base):
    """
    Trading strategy model

    Lifecycle: generated → pending → tested → selected → live → retired
    """
    __tablename__ = "strategies"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identity
    name = Column(String(255), unique=True, nullable=False, index=True)
    # Example: "Strategy_MOM_abc123_15m"

    strategy_type = Column(String(50), nullable=False, index=True)
    # Example: "MOM" (Momentum), "REV" (Reversal), "TRN" (Trend), etc.

    timeframe = Column(String(10), nullable=False, index=True)
    # Example: "15m", "1h", "4h", "1d"

    # Status
    status = Column(
        Enum(
            "GENERATED",  # Created by AI, not validated yet
            "VALIDATED",  # Passed 4-phase validation (syntax, AST, shuffle, execution)
            "ACTIVE",     # Backtest complete, in pool (max 300, leaderboard logic)
            "LIVE",       # Currently trading live
            "RETIRED",    # Removed from live trading
            "FAILED",     # Failed validation or backtest
            # Legacy values still in DB enum but not used:
            # "TESTED" - renamed to ACTIVE
            # "SELECTED" - removed (direct ACTIVE -> LIVE flow)
            name="strategy_status"
        ),
        nullable=False,
        default="GENERATED",
        index=True
    )

    # Process coordination (for multi-process architecture)
    processing_by = Column(String(100), nullable=True, index=True)
    # Process ID currently working on this strategy (e.g., "validator-001")
    processing_started_at = Column(DateTime, nullable=True)
    # When processing started (for timeout detection)

    # Pipeline completion timestamps (for accurate throughput metrics)
    validation_completed_at = Column(DateTime, nullable=True)
    # When validation phase completed
    backtest_completed_at = Column(DateTime, nullable=True)
    # When backtesting completed (similar to tested_at but more precise)
    processing_completed_at = Column(DateTime, nullable=True)
    # When overall processing completed for this stage

    # Code
    code = Column(Text, nullable=False)
    # Full Python code for the strategy (StrategyCore subclass)

    # Generation metadata
    ai_provider = Column(String(50))  # "claude", "gemini", "codex"
    generation_prompt = Column(Text)  # Prompt used to generate strategy
    pattern_based = Column(Boolean, default=False)  # From pattern-discovery?
    pattern_ids = Column(JSON)  # List of pattern IDs if pattern-based

    # Template-based generation
    template_id = Column(UUID(as_uuid=True), ForeignKey("strategy_templates.id"), nullable=True, index=True)
    # If generated from template, link to parent template
    generation_mode = Column(String(20), default="ai")  # "ai", "pattern", "template"
    parameters = Column(JSON)  # Parameters used if template-based
    parametric_backtest_metrics = Column(JSONB, nullable=True)  # Stores training/holdout metrics from parametric optimization

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    tested_at = Column(DateTime)  # When initial backtest completed
    last_backtested_at = Column(DateTime)  # When last re-backtested (for ACTIVE pool FIFO)
    live_since = Column(DateTime)  # When deployed to live
    retired_at = Column(DateTime)  # When retired from live

    # Backtest optimization results
    optimal_timeframe = Column(String(10))  # TF with best performance
    backtest_pairs = Column(JSON)  # Audit trail: ["BTC", "ETH", ...]
    backtest_date = Column(DateTime)  # Date of backtest

    # Pattern-specific coin selection (from pattern's coin_performance)
    pattern_coins = Column(JSON)  # High-edge coins: ["ME", "RENDER", ...]

    # Base code hash for batch processing and shuffle test caching
    # SHA256 of base code BEFORE parameter embedding (same for all variations)
    base_code_hash = Column(String(64), nullable=True, index=True)

    # Backtest score (from BacktestResult, cached for ranking)
    score_backtest = Column(Float)  # Composite score 0-100

    # Live performance metrics (calculated from Trade records)
    score_live = Column(Float)  # Composite score 0-100
    win_rate_live = Column(Float)  # Win rate from live trades
    expectancy_live = Column(Float)  # Avg profit per trade (%)
    sharpe_live = Column(Float)  # Sharpe ratio from live returns
    max_drawdown_live = Column(Float)  # Max drawdown from live equity curve
    total_trades_live = Column(Integer, default=0)  # Number of closed live trades
    total_pnl_live = Column(Float, default=0.0)  # Total PnL in USD
    last_live_update = Column(DateTime)  # Last time live metrics were updated

    # Backtest vs Live comparison
    live_degradation_pct = Column(Float)  # (backtest_score - live_score) / backtest_score

    # Relationships (cascade delete for child records when strategy is deleted)
    backtest_results = relationship("BacktestResult", back_populates="strategy", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="strategy", cascade="all, delete-orphan")
    performance_snapshots = relationship("PerformanceSnapshot", back_populates="strategy", cascade="all, delete-orphan")
    template = relationship("StrategyTemplate", backref="strategies")

    # Indexes for fast lookups
    __table_args__ = (
        Index('idx_status_timeframe', 'status', 'timeframe'),
        Index('idx_strategy_type_status', 'strategy_type', 'status'),
        Index('idx_status_processing', 'status', 'processing_by'),  # For claim queries
        Index('idx_status_base_code_hash', 'status', 'base_code_hash'),  # For batch claim by hash
    )

    def __repr__(self):
        return f"<Strategy(name={self.name}, type={self.strategy_type}, status={self.status})>"


# ==============================================================================
# BACKTEST RESULTS
# ==============================================================================

class BacktestResult(Base):
    """
    Backtest results for a strategy

    Walk-forward validation results stored here.
    """
    __tablename__ = "backtest_results"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to strategy
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=False, index=True)

    # Backtest parameters
    lookback_days = Column(Integer, nullable=False)  # 180 days default
    initial_capital = Column(Float, nullable=False)  # $10,000 default
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # Performance metrics (aggregate across all symbols)
    total_trades = Column(Integer, nullable=False)
    win_rate = Column(Float)  # 0.55 = 55%
    sharpe_ratio = Column(Float)
    expectancy = Column(Float)  # Average profit per trade (%)
    max_drawdown = Column(Float)  # 0.30 = 30%
    final_equity = Column(Float)
    total_return_pct = Column(Float)

    # Walk-forward validation results
    walk_forward_enabled = Column(Boolean, default=True)
    walk_forward_windows = Column(Integer, default=4)
    walk_forward_stability = Column(Float)  # Std dev of edge across windows
    worst_window_edge = Column(Float)  # Edge in worst-performing window

    # Validation checks
    lookahead_check_passed = Column(Boolean)  # AST analysis
    shuffle_test_passed = Column(Boolean)  # Empirical validation
    shuffle_test_p_value = Column(Float)  # p-value from shuffle test

    # Per-symbol breakdown (JSON)
    per_symbol_results = Column(JSON)  # {symbol: {trades, win_rate, etc.}}

    # Raw metrics (JSON - for detailed analysis)
    raw_metrics = Column(JSON)  # Full portfolio stats

    # Multi-pair/TF optimization fields
    symbols_tested = Column(JSON)  # List of symbols: ["BTC", "ETH", ...]
    timeframe_tested = Column(String(10))  # Timeframe of this backtest
    is_optimal_tf = Column(Boolean, default=False)  # True if this is the selected TF

    # Dual-period backtest fields
    period_type = Column(String(20), default='full')  # 'full' or 'recent'
    period_days = Column(Integer)  # Number of days in this backtest period

    # Weighted score fields (only populated on 'full' period row after combining with recent)
    weighted_sharpe = Column(Float)       # 60% full + 40% recent (legacy composite score)
    weighted_win_rate = Column(Float)
    weighted_expectancy = Column(Float)

    # Individual weighted metrics (training 40% + holdout 60%) - for accurate classifier ranking
    weighted_sharpe_pure = Column(Float, nullable=True)  # Sharpe only (no composite)
    weighted_walk_forward_stability = Column(Float, nullable=True)  # Stability metric
    weighted_max_drawdown = Column(Float, nullable=True)  # Max drawdown weighted

    recency_ratio = Column(Float)         # recent_sharpe / full_sharpe (measures "in-form")
    recency_penalty = Column(Float)       # 0-20% penalty for poor recent performance

    # Link to corresponding recent period result
    recent_result_id = Column(UUID(as_uuid=True), ForeignKey("backtest_results.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    strategy = relationship("Strategy", back_populates="backtest_results")

    def __repr__(self):
        return f"<BacktestResult(strategy={self.strategy_id}, sharpe={self.sharpe_ratio:.2f}, trades={self.total_trades})>"


# ==============================================================================
# PIPELINE METRICS SNAPSHOTS
# ==============================================================================

class PipelineMetricsSnapshot(Base):
    """
    Time-series snapshots of pipeline metrics.

    Collected every 5 minutes by metrics collector service.
    Used for historical analysis and trend visualization.
    """
    __tablename__ = 'pipeline_metrics_snapshots'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Queue depths (counts)
    queue_generated = Column(Integer, nullable=False, default=0)
    queue_validated = Column(Integer, nullable=False, default=0)
    queue_active = Column(Integer, nullable=False, default=0)  # Pool size (max 300)
    queue_live = Column(Integer, nullable=False, default=0)
    queue_retired = Column(Integer, nullable=False, default=0)
    queue_failed = Column(Integer, nullable=False, default=0)
    # Legacy columns (kept for backwards compatibility with existing data)
    queue_tested = Column(Integer, nullable=True, default=0)  # Renamed to queue_active
    queue_selected = Column(Integer, nullable=True, default=0)  # Removed state

    # Throughput (strategies/hour for each stage)
    throughput_generation = Column(Float, nullable=True)  # NULL = not calculated
    throughput_validation = Column(Float, nullable=True)
    throughput_backtesting = Column(Float, nullable=True)
    throughput_classification = Column(Float, nullable=True)

    # Utilization (0.0-1.0, percentage of queue limit used)
    utilization_generated = Column(Float, nullable=True)
    utilization_validated = Column(Float, nullable=True)
    utilization_active = Column(Float, nullable=True)  # Pool utilization (queue_active / max_size)
    # Legacy (kept for backwards compatibility)
    utilization_tested = Column(Float, nullable=True)  # Renamed to utilization_active

    # Success rates (0.0-1.0)
    success_rate_validation = Column(Float, nullable=True)
    success_rate_backtesting = Column(Float, nullable=True)

    # Bottleneck detection
    bottleneck_stage = Column(String(50), nullable=True)  # 'validation', 'backtesting', etc.

    # Overall system status
    overall_status = Column(String(20), nullable=False)  # 'healthy', 'degraded', 'critical'

    # Quality metrics (from TESTED strategies)
    avg_sharpe = Column(Float, nullable=True)
    avg_win_rate = Column(Float, nullable=True)
    avg_expectancy = Column(Float, nullable=True)

    # Pattern vs AI breakdown
    pattern_count = Column(Integer, nullable=False, default=0)
    ai_count = Column(Integer, nullable=False, default=0)

    # Indexes for time-series queries
    __table_args__ = (
        Index('idx_metrics_timestamp', 'timestamp'),
        Index('idx_metrics_status_time', 'overall_status', 'timestamp'),
    )

    def __repr__(self):
        return f"<PipelineMetricsSnapshot(timestamp={self.timestamp}, status={self.overall_status})>"


# ==============================================================================
# LIVE TRADES
# ==============================================================================

class Trade(Base):
    """
    Live trading record

    One row per trade (entry + exit).
    """
    __tablename__ = "trades"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to strategy
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=False, index=True)

    # Trade identification
    symbol = Column(String(20), nullable=False, index=True)  # "BTC", "ETH", etc.
    subaccount_id = Column(Integer, nullable=False, index=True)  # 0-9
    direction = Column(Enum("LONG", "SHORT", name="trade_direction"), nullable=False)

    # Entry
    entry_time = Column(DateTime, nullable=False, index=True)
    entry_price = Column(Float, nullable=False)
    entry_size = Column(Float, nullable=False)  # Position size in asset units
    entry_order_id = Column(String(255))  # Hyperliquid order ID

    # Exit
    exit_time = Column(DateTime, index=True)
    exit_price = Column(Float)
    exit_size = Column(Float)
    exit_order_id = Column(String(255))
    exit_reason = Column(String(100))  # "take_profit", "stop_loss", "signal", "emergency"

    # Risk management
    stop_loss = Column(Float)  # Absolute price
    take_profit = Column(Float)  # Absolute price
    atr_at_entry = Column(Float)  # ATR value at entry

    # Results
    pnl_usd = Column(Float)  # Profit/loss in USD (net after fees)
    pnl_pct = Column(Float)  # Profit/loss as % of position
    return_pct = Column(Float)  # Return on capital risked
    fees_usd = Column(Float)  # Total fees paid
    slippage_usd = Column(Float)  # Estimated slippage

    # Hyperliquid sync fields
    position_id = Column(String(255), index=True)  # Hyperliquid exit_tid for dedup
    leverage = Column(Integer, default=1)  # Actual leverage used (1-50x)
    entry_fee_usd = Column(Float)  # Fee on entry side
    exit_fee_usd = Column(Float)  # Fee on exit side
    duration_minutes = Column(Integer)  # Trade duration in minutes

    # Iteration tracking
    iteration = Column(Integer)  # Monitor iteration when trade closed
    entry_iteration = Column(Integer)  # Monitor iteration when trade opened

    # Metadata
    signal_reason = Column(Text)  # Why strategy entered trade
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    strategy = relationship("Strategy", back_populates="trades")

    # Indexes for fast lookups
    __table_args__ = (
        Index('idx_entry_time', 'entry_time'),
        Index('idx_symbol_subaccount', 'symbol', 'subaccount_id'),
    )

    def __repr__(self):
        return f"<Trade(symbol={self.symbol}, direction={self.direction}, pnl={self.pnl_usd:.2f})>"


# ==============================================================================
# PERFORMANCE SNAPSHOTS
# ==============================================================================

class PerformanceSnapshot(Base):
    """
    Performance snapshot (every 15 minutes)

    Tracks live performance metrics for monitoring and analysis.
    """
    __tablename__ = "performance_snapshots"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to strategy (NULL = portfolio-level snapshot)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), index=True)

    # Snapshot time
    snapshot_time = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)

    # Performance metrics
    total_trades = Column(Integer, default=0)
    open_trades = Column(Integer, default=0)
    win_rate = Column(Float)
    sharpe_ratio = Column(Float)
    total_pnl_usd = Column(Float)
    total_return_pct = Column(Float)
    max_drawdown = Column(Float)

    # Portfolio metrics (if strategy_id is NULL)
    total_capital = Column(Float)  # Total portfolio value
    available_capital = Column(Float)  # Uninvested capital
    total_exposure = Column(Float)  # Total position value

    # Recent performance (last 24h, 7d, 30d)
    pnl_24h = Column(Float)
    pnl_7d = Column(Float)
    pnl_30d = Column(Float)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    strategy = relationship("Strategy", back_populates="performance_snapshots")

    # Indexes for time-series queries
    __table_args__ = (
        Index('idx_snapshot_time', 'snapshot_time'),
        Index('idx_strategy_snapshot', 'strategy_id', 'snapshot_time'),
    )

    def __repr__(self):
        return f"<PerformanceSnapshot(strategy={self.strategy_id}, time={self.snapshot_time}, pnl={self.total_pnl_usd:.2f})>"


# ==============================================================================
# COINS
# ==============================================================================

class Coin(Base):
    """
    Tradeable coin/asset model

    Stores coin metadata including max leverage from Hyperliquid API.
    Updated by pairs_updater.py (runs 2x/day).
    """
    __tablename__ = "coins"

    # Primary key - symbol name (e.g., 'BTC', 'ETH')
    symbol = Column(String(20), primary_key=True)

    # Hyperliquid max leverage for this coin
    max_leverage = Column(Integer, nullable=False)

    # Market data (updated with pairs_updater)
    volume_24h = Column(Float)  # 24h trading volume in USD
    price = Column(Float)  # Current price

    # Status
    is_active = Column(Boolean, default=True, index=True)
    # True = in trading whitelist, eligible for trading

    # Timestamps
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Coin(symbol={self.symbol}, max_leverage={self.max_leverage}, active={self.is_active})>"


# ==============================================================================
# SUBACCOUNTS
# ==============================================================================

class Subaccount(Base):
    """
    Subaccount management model

    Tracks allocation and performance per Hyperliquid subaccount (1-10).
    """
    __tablename__ = "subaccounts"

    # Primary key
    id = Column(Integer, primary_key=True)  # 1-10
    # Directly maps to Hyperliquid subaccount ID

    # Current strategy assignment
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), index=True)

    # Capital allocation
    allocated_capital = Column(Float, nullable=False, default=0.0)
    current_balance = Column(Float)  # Current USD balance
    unrealized_pnl = Column(Float)  # Unrealized P&L from open positions

    # Performance metrics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)
    win_rate = Column(Float)

    # Risk metrics
    max_drawdown = Column(Float)
    current_drawdown = Column(Float)
    open_positions_count = Column(Integer, default=0)

    # Status
    status = Column(
        Enum(
            "ACTIVE",  # Currently trading
            "PAUSED",  # Temporarily suspended
            "STOPPED",  # Emergency stopped
            name="subaccount_status"
        ),
        nullable=False,
        default="ACTIVE"
    )

    # Timestamps
    last_trade_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    strategy = relationship("Strategy", backref="subaccounts")

    def __repr__(self):
        return f"<Subaccount(id={self.id}, strategy={self.strategy_id}, balance={self.current_balance:.2f})>"


# ==============================================================================
# SCHEDULED TASKS TRACKING
# ==============================================================================

class ScheduledTaskExecution(Base):
    """Track execution of scheduled tasks"""
    __tablename__ = "scheduled_task_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_name = Column(String(100), nullable=False, index=True)
    task_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Results
    error_message = Column(Text, nullable=True)
    task_metadata = Column(JSONB, nullable=True)

    # Trigger source
    triggered_by = Column(String(100), nullable=True)

    # Relationship to pairs update details
    pairs_update_details = relationship(
        "PairsUpdateLog",
        back_populates="execution",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_task_executions_lookup', 'task_name', 'started_at'),
    )

    def __repr__(self):
        return f"<ScheduledTaskExecution(id={self.id}, task={self.task_name}, status={self.status})>"


class PairsUpdateLog(Base):
    """Detailed log for pairs update operations"""
    __tablename__ = "pairs_update_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey('scheduled_task_executions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Update metrics
    total_pairs = Column(Integer, nullable=False)
    new_pairs = Column(Integer, nullable=False)
    updated_pairs = Column(Integer, nullable=False)
    deactivated_pairs = Column(Integer, nullable=False)

    # Snapshot
    top_10_symbols = Column(JSONB, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationship
    execution = relationship("ScheduledTaskExecution", back_populates="pairs_update_details")

    def __repr__(self):
        return f"<PairsUpdateLog(id={self.id}, total_pairs={self.total_pairs})>"


# ==============================================================================
# VALIDATION CACHE
# ==============================================================================

class ValidationCache(Base):
    """
    Cache for expensive validation tests (shuffle test, multi-window).

    Stores results by base_code_hash to skip redundant tests on
    parametric variations of the same base code.
    """
    __tablename__ = "validation_caches"

    # Primary key - hash of base code (BEFORE parameter embedding)
    code_hash = Column(String(64), primary_key=True)

    # Shuffle test result
    shuffle_passed = Column(Boolean, nullable=True)

    # Multi-window validation result
    multi_window_passed = Column(Boolean, nullable=True)
    multi_window_reason = Column(String(200), nullable=True)

    # Timestamp for potential TTL/expiration
    validated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    def __repr__(self):
        return (
            f"<ValidationCache(hash={self.code_hash[:8]}..., "
            f"shuffle={self.shuffle_passed}, multi_window={self.multi_window_passed})>"
        )


# ==============================================================================
# STRATEGY EVENTS (Pipeline Tracking)
# ==============================================================================

class StrategyEvent(Base):
    """
    Immutable event log for pipeline tracking.

    Events persist even when strategies are deleted, enabling:
    - Accurate success rates (not affected by DELETE)
    - Failure reason tracking
    - Timing analysis per phase
    - Pipeline funnel visualization

    Event types by stage:
    - generation: created
    - validation: syntax_started, syntax_passed, syntax_failed,
                  lookahead_started, lookahead_passed, lookahead_failed,
                  execution_started, execution_passed, execution_failed,
                  completed
    - backtest: started, tf_completed, scored, score_rejected
    - shuffle_test: started, passed, failed
    - multi_window: started, passed, failed
    - pool: attempted, entered, rejected
    - deployment: started, succeeded, failed
    - live: promoted, retired
    - emergency: stop_triggered
    """
    __tablename__ = 'strategy_events'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True,
                       default=lambda: datetime.now(UTC))

    # Strategy identification (name persists even if strategy deleted)
    strategy_id = Column(UUID(as_uuid=True), nullable=True)  # NULL if strategy deleted
    strategy_name = Column(String(100), nullable=False, index=True)
    base_code_hash = Column(String(64), nullable=True)  # For template tracking

    # Event classification
    event_type = Column(String(50), nullable=False, index=True)
    # Examples: "syntax_passed", "shuffle_failed", "pool_entered"

    stage = Column(String(30), nullable=False, index=True)
    # Examples: "generation", "validation", "backtest", "shuffle_test", "pool", "live"

    status = Column(String(20), nullable=False)
    # One of: "started", "passed", "failed", "completed"

    # Timing (milliseconds)
    duration_ms = Column(Integer, nullable=True)

    # Flexible event data (JSON for extensibility)
    # Note: "metadata" is reserved by SQLAlchemy, so we use "event_data"
    event_data = Column(JSON, nullable=True)
    # Examples:
    # validation_failed: {"reason": "ast_forbidden", "pattern": "shift(-1)", "line": 42}
    # backtest_scored: {"score": 67, "sharpe": 1.2, "win_rate": 0.58}
    # shuffle_failed: {"original_signals": 100, "shuffled_signals": 95}
    # pool_rejected: {"reason": "score_below_min", "min_in_pool": 72}

    __table_args__ = (
        Index('idx_events_timestamp', 'timestamp'),
        Index('idx_events_stage_status', 'stage', 'status'),
        Index('idx_events_type_time', 'event_type', 'timestamp'),
        Index('idx_events_strategy_time', 'strategy_name', 'timestamp'),
    )

    def __repr__(self):
        return f"<StrategyEvent({self.event_type}, {self.strategy_name}, {self.status})>"


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def create_all_tables(engine):
    """
    Create all tables in database

    Args:
        engine: SQLAlchemy engine

    Usage:
        >>> from src.database.models import create_all_tables
        >>> from src.database.connection import get_engine
        >>> engine = get_engine()
        >>> create_all_tables(engine)
    """
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """
    Drop all tables in database (DANGEROUS!)

    Args:
        engine: SQLAlchemy engine
    """
    Base.metadata.drop_all(engine)
