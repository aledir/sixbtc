"""
SQLAlchemy Models for SixBTC

Database schema for:
- Strategies (generated, tested, live)
- Backtest results
- Live trades
- Performance snapshots
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, JSON,
    ForeignKey, Enum, Index
)
from sqlalchemy.dialects.postgresql import UUID
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
            "TESTED",  # Backtest complete
            "SELECTED",  # Top performer, ready for live
            "LIVE",  # Currently trading live
            "RETIRED",  # Removed from live trading
            "FAILED",  # Failed validation or backtest
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

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    tested_at = Column(DateTime)  # When backtest completed
    live_since = Column(DateTime)  # When deployed to live
    retired_at = Column(DateTime)  # When retired from live

    # Backtest optimization results
    optimal_timeframe = Column(String(10))  # TF with best performance
    backtest_pairs = Column(JSON)  # Audit trail: ["BTC", "ETH", ...]
    backtest_date = Column(DateTime)  # Date of backtest

    # Relationships
    backtest_results = relationship("BacktestResult", back_populates="strategy")
    trades = relationship("Trade", back_populates="strategy")
    performance_snapshots = relationship("PerformanceSnapshot", back_populates="strategy")
    template = relationship("StrategyTemplate", backref="strategies")

    # Indexes for fast lookups
    __table_args__ = (
        Index('idx_status_timeframe', 'status', 'timeframe'),
        Index('idx_strategy_type_status', 'strategy_type', 'status'),
        Index('idx_status_processing', 'status', 'processing_by'),  # For claim queries
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
    raw_metrics = Column(JSON)  # Full VectorBT portfolio stats

    # Multi-pair/TF optimization fields
    symbols_tested = Column(JSON)  # List of symbols: ["BTC", "ETH", ...]
    timeframe_tested = Column(String(10))  # Timeframe of this backtest
    is_optimal_tf = Column(Boolean, default=False)  # True if this is the selected TF

    # Dual-period backtest fields
    period_type = Column(String(20), default='full')  # 'full' or 'recent'
    period_days = Column(Integer)  # Number of days in this backtest period

    # Weighted score fields (only populated on 'full' period row after combining with recent)
    weighted_sharpe = Column(Float)       # 60% full + 40% recent
    weighted_win_rate = Column(Float)
    weighted_expectancy = Column(Float)
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
    pnl_usd = Column(Float)  # Profit/loss in USD
    pnl_pct = Column(Float)  # Profit/loss as % of position
    return_pct = Column(Float)  # Return on capital risked
    fees_usd = Column(Float)  # Total fees paid
    slippage_usd = Column(Float)  # Estimated slippage

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
