# SixBTC - Detailed Development Plan

**Project**: AI-Powered Multi-Strategy Trading System
**Target**: Hyperliquid Perpetual Futures
**Timeline**: 3-4 weeks for MVP
**Test Phase**: $100 × 3 subaccounts for 1-2 weeks

---

## 📋 PROJECT OVERVIEW

### Core Objectives
1. **Generate** trading strategies using AI (pattern-based + custom logic)
2. **Backtest** strategies using VectorBT (fast, flexible)
3. **Classify** strategies by performance and market conditions
4. **Deploy** top 10 strategies to Hyperliquid (1 per subaccount)
5. **Monitor** live performance and auto-rotate underperformers

### Key Design Principles
- **Single Process**: All 10 strategies in one Python process
- **Shared Data**: WebSocket singleton + thread-safe cache
- **Multi-Timeframe**: 5m, 15m, 30m, 1h, 4h, 1d coverage
- **Deployment Agnostic**: Standalone, Supervisor, Docker, or Systemd
- **No Redis**: In-memory cache sufficient for single-process architecture
- **StrategyCore Pattern**: Same code for backtest and live

---

## 🏗️ ARCHITECTURE COMPONENTS

### High-Level Architecture
```
┌──────────────────────────────────────────────────────────────┐
│                      SIXBTC SYSTEM                            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │ HyperliquidDataProvider (Singleton)                │     │
│  │ - ONE WebSocket connection                         │     │
│  │ - Real-time OHLCV updates (all coins × TFs)        │     │
│  │ - Thread-safe shared cache                         │     │
│  └────────────────────────────────────────────────────┘     │
│                           ↓                                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │ StrategyOrchestrator (Main Process)                │     │
│  │                                                     │     │
│  │  ┌──────────────────────────────────────────┐     │     │
│  │  │ Strategy 1 (Subaccount 1, 5m, MOM)       │     │     │
│  │  │ Strategy 2 (Subaccount 2, 15m, REV)      │     │     │
│  │  │ Strategy 3 (Subaccount 3, 15m, TRN)      │     │     │
│  │  │ ...                                       │     │     │
│  │  │ Strategy 10 (Subaccount 10, 1d, BRE)     │     │     │
│  │  └──────────────────────────────────────────┘     │     │
│  │                                                     │     │
│  │  ┌──────────────────────────────────────────┐     │     │
│  │  │ APScheduler (Multi-Timeframe)            │     │     │
│  │  │ - 5m strategies every 5 minutes          │     │     │
│  │  │ - 15m strategies every 15 minutes        │     │     │
│  │  │ - 1h strategies every 1 hour             │     │     │
│  │  │ - etc.                                    │     │     │
│  │  └──────────────────────────────────────────┘     │     │
│  └────────────────────────────────────────────────────┘     │
│                           ↓                                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │ HyperliquidClient                                  │     │
│  │ - Subaccount switching (1-10)                      │     │
│  │ - Order execution (market orders + SL/TP)          │     │
│  │ - Position tracking                                │     │
│  └────────────────────────────────────────────────────┘     │
│                           ↓                                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │ PostgreSQL Database (Docker)                       │     │
│  │ - Strategies (code, params, status)                │     │
│  │ - Backtest Results (metrics, trades)               │     │
│  │ - Live Trades (execution log)                      │     │
│  │ - Performance Snapshots (monitoring)               │     │
│  └────────────────────────────────────────────────────┘     │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Module Responsibilities

| Module | Responsibility | Key Files |
|--------|---------------|-----------|
| **generator** | AI strategy creation | `ai_manager.py`, `pattern_fetcher.py`, `strategy_builder.py` |
| **backtester** | VectorBT backtesting | `vectorbt_engine.py`, `data_loader.py`, `optimizer.py`, `validator.py` |
| **classifier** | Strategy ranking | `scorer.py`, `regime_filter.py`, `portfolio_builder.py` |
| **executor** | Live trading | `hyperliquid_client.py`, `subaccount_manager.py`, `position_tracker.py` |
| **orchestration** | System coordination | `orchestrator.py`, `scheduler.py` |
| **strategies** | Strategy core | `base.py` (StrategyCore abstract class) |
| **database** | Persistence | `models.py`, `connection.py` |
| **data** | Market data | `hyperliquid_websocket.py`, `binance_downloader.py` |
| **monitor** | Dashboards | `dashboard.py`, `health_check.py` |

---

## 📅 DEVELOPMENT PHASES

### PHASE 1: Foundation (Days 1-3)

#### 1.1 Project Setup
**Goal**: Bootstrap project structure and dependencies

**Tasks**:
- [ ] Create virtual environment
- [ ] Install dependencies (`requirements.txt`)
- [ ] Setup project directory structure
- [ ] Configure `.gitignore` and `.env.example`
- [ ] Initialize Git repository

**Files Created**:
```
sixbtc/
├── .venv/
├── .env.example
├── .gitignore
├── requirements.txt
├── main.py
├── CLAUDE.md ✅
├── DEVELOPMENT_PLAN.md ✅
└── README.md
```

**Dependencies** (`requirements.txt`):
```
# Core
python>=3.11
pandas>=2.1.0
numpy>=1.25.0

# Backtesting
vectorbt>=0.26.0
ta-lib>=0.4.28
numba>=0.58.0

# Data
ccxt>=4.1.0
websocket-client>=1.6.0
hyperliquid-python-sdk>=0.3.0

# Database
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.9
alembic>=1.13.0

# AI
anthropic>=0.7.0
openai>=1.3.0
jinja2>=3.1.0

# Scheduling
apscheduler>=3.10.0

# CLI/Monitoring
click>=8.1.0
rich>=13.7.0

# Config
pyyaml>=6.0.1
python-dotenv>=1.0.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

**Deliverable**: Runnable `python main.py --help`

---

#### 1.2 Database Schema
**Goal**: Define PostgreSQL schema for all entities

**Tasks**:
- [ ] Design database schema
- [ ] Create SQLAlchemy models
- [ ] Setup Alembic migrations
- [ ] Docker Compose for PostgreSQL
- [ ] Test database connection

**Schema** (`src/database/models.py`):
```sql
-- Strategies Table
CREATE TABLE strategies (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,        -- e.g., Strategy_MOM_a7f3d8b2
    type VARCHAR(10) NOT NULL,          -- MOM, REV, TRN, BRE, etc.
    code TEXT NOT NULL,                 -- StrategyCore Python code

    -- Configuration
    timeframe VARCHAR(10) NOT NULL,     -- 5m, 15m, 1h, etc.
    params JSONB,                       -- Strategy-specific parameters

    -- Lifecycle
    status VARCHAR(20) NOT NULL,        -- PENDING, TESTED, SELECTED, LIVE, RETIRED
    created_at TIMESTAMP DEFAULT NOW(),
    deployed_at TIMESTAMP,
    retired_at TIMESTAMP,

    -- Backtest Metrics
    backtest_sharpe DECIMAL(6,3),
    backtest_sortino DECIMAL(6,3),
    backtest_max_dd DECIMAL(6,5),
    backtest_win_rate DECIMAL(6,5),
    backtest_expectancy DECIMAL(8,5),
    backtest_total_trades INTEGER,
    backtest_ed_ratio DECIMAL(8,5),
    backtest_consistency DECIMAL(6,5),

    -- Walk-Forward Validation
    wf_worst_window_sharpe DECIMAL(6,3),
    wf_stability DECIMAL(6,5),
    shuffle_p_value DECIMAL(10,8),

    -- Live Performance
    live_pnl DECIMAL(12,2),
    live_win_rate DECIMAL(6,5),
    live_total_trades INTEGER,
    live_max_dd DECIMAL(6,5),

    -- Assignment
    subaccount_id INTEGER,              -- 1-10 (NULL if not deployed)

    -- Metadata
    pattern_ids UUID[],                 -- From pattern-discovery
    ai_provider VARCHAR(50),            -- claude, gemini, codex
    generation_prompt TEXT,
    score DECIMAL(8,5),                 -- Composite score
    retire_reason TEXT
);

-- Backtest Results Table
CREATE TABLE backtest_results (
    id UUID PRIMARY KEY,
    strategy_id UUID REFERENCES strategies(id) ON DELETE CASCADE,
    run_at TIMESTAMP DEFAULT NOW(),

    -- Configuration
    symbols TEXT[],
    timeframe VARCHAR(10),
    start_date DATE,
    end_date DATE,
    initial_capital DECIMAL(12,2),

    -- Metrics (full dump from VectorBT)
    metrics JSONB,

    -- Trade list (for analysis)
    trades JSONB,

    -- Validation results
    lookahead_check_passed BOOLEAN,
    shuffle_test_p_value DECIMAL(10,8)
);

-- Live Trades Table
CREATE TABLE live_trades (
    id UUID PRIMARY KEY,
    strategy_id UUID REFERENCES strategies(id),
    subaccount_id INTEGER NOT NULL,

    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,          -- long, short

    entry_time TIMESTAMP NOT NULL,
    entry_price DECIMAL(12,6),
    size DECIMAL(12,6),
    leverage INTEGER,

    exit_time TIMESTAMP,
    exit_price DECIMAL(12,6),

    pnl DECIMAL(12,6),
    pnl_pct DECIMAL(6,5),

    stop_loss DECIMAL(12,6),
    take_profit DECIMAL(12,6),

    exit_reason VARCHAR(50),            -- tp, sl, signal, manual, emergency
    signal_reason TEXT,                 -- From Signal.reason

    -- Fees
    entry_fee DECIMAL(12,6),
    exit_fee DECIMAL(12,6),
    total_fee DECIMAL(12,6)
);

-- Performance Snapshots Table (every 15min)
CREATE TABLE performance_snapshots (
    id UUID PRIMARY KEY,
    strategy_id UUID REFERENCES strategies(id),
    subaccount_id INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),

    account_value DECIMAL(12,2),
    unrealized_pnl DECIMAL(12,2),
    realized_pnl DECIMAL(12,2),

    open_positions INTEGER,
    daily_pnl DECIMAL(12,2),
    drawdown DECIMAL(6,5)
);

-- Market Data Cache (optional - for replay/debugging)
CREATE TABLE market_data_cache (
    id UUID PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,

    open DECIMAL(12,6),
    high DECIMAL(12,6),
    low DECIMAL(12,6),
    close DECIMAL(12,6),
    volume DECIMAL(20,6),

    UNIQUE(symbol, timeframe, timestamp)
);

-- Indexes
CREATE INDEX idx_strategies_status ON strategies(status);
CREATE INDEX idx_strategies_subaccount ON strategies(subaccount_id);
CREATE INDEX idx_strategies_score ON strategies(score DESC);
CREATE INDEX idx_live_trades_strategy ON live_trades(strategy_id);
CREATE INDEX idx_live_trades_time ON live_trades(entry_time DESC);
CREATE INDEX idx_snapshots_strategy_time ON performance_snapshots(strategy_id, timestamp DESC);
```

**Docker Compose** (`docker-compose.yml`):
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    container_name: sixbtc_postgres
    environment:
      POSTGRES_DB: sixbtc
      POSTGRES_USER: sixbtc
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sixbtc"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**Deliverable**: `docker-compose up -d` + `alembic upgrade head`

---

#### 1.3 Configuration System
**Goal**: YAML-based config with environment variable resolution

**Tasks**:
- [ ] Create `config/config.yaml`
- [ ] Implement config loader with env var resolution
- [ ] Config validator (fail-fast on missing keys)
- [ ] `.env.example` template

**Config Structure** (`config/config.yaml`):
```yaml
system:
  name: "SixBTC"
  version: "1.0.0"
  deployment_mode: auto  # auto, standalone, docker, supervisor

database:
  host: ${DB_HOST}
  port: ${DB_PORT}
  database: ${DB_NAME}
  user: ${DB_USER}
  password: ${DB_PASSWORD}
  min_connections: 2
  max_connections: 10

hyperliquid:
  base_url: https://api.hyperliquid.xyz
  private_key: ${HL_PRIVATE_KEY}
  vault_address: ${HL_VAULT_ADDRESS}
  fee_rate: 0.0004  # 0.04% taker fee
  slippage: 0.0005  # 0.05% expected slippage

trading:
  timeframes:
    available: ['5m', '15m', '30m', '1h', '4h', '1d']

  data:
    symbols_source: binance_hyperliquid_intersection
    min_volume_24h: 5000000  # $5M minimum

  subaccounts:
    total: 10
    test_mode_count: 3  # Use only 3 for testing phase
    test_mode_capital: 100  # $100 per subaccount in test

risk:
  max_open_positions: 10  # Total across all subaccounts
  fixed_risk_per_trade: 0.02  # 2% of capital
  max_drawdown_emergency: 0.30  # 30% emergency stop
  max_daily_loss: 0.10  # 10% daily loss limit

generation:
  frequency_hours: 4
  batch_size: 50
  ai_providers:
    - claude
    - gemini
    - codex
  pattern_discovery:
    api_url: http://localhost:8001
    tier_filter: 1  # Only Tier 1 patterns
    min_quality_score: 0.75
  strategy_types:
    pattern_based_pct: 0.30  # 30% pattern-based
    custom_pct: 0.70         # 70% custom AI logic

backtesting:
  parallel_workers: 10
  lookback_days: 180  # 6 months
  initial_capital: 10000
  min_sharpe: 1.0
  min_win_rate: 0.55
  min_trades: 100
  max_drawdown: 0.30

  optimization:
    enabled: true
    max_parameters: 4  # Limit to prevent overfitting
    walk_forward_windows: 4

  validation:
    lookahead_ast_check: true
    shuffle_test_enabled: true
    shuffle_iterations: 100
    min_p_value: 0.05

classification:
  frequency_hours: 1
  score_weights:
    edge: 0.4
    sharpe: 0.3
    consistency: 0.2
    stability: 0.1
  max_same_type: 3  # Diversification
  max_same_timeframe: 3

deployment:
  rotation_frequency_hours: 24
  emergency_stop:
    max_drawdown: 0.30
    daily_loss: 0.10
    strategy_degradation: 0.50  # -50% vs backtest

  shutdown:
    close_positions: false  # Leave positions open on shutdown
    cancel_orders: true     # Always cancel pending orders

monitoring:
  check_interval_minutes: 15
  health_check:
    enabled: true
    port: 8080
  dashboard:
    enabled: true
    refresh_seconds: 5

logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  file: logs/sixbtc.log
  max_bytes: 10485760  # 10MB
  backup_count: 5
```

**Deliverable**: `python -m src.config.validate`

---

### PHASE 2: Data Layer (Days 4-6)

#### 2.1 Binance Data Downloader
**Goal**: Download historical OHLCV for backtesting

**Tasks**:
- [ ] CCXT Binance integration
- [ ] Download OHLCV for HL-Binance intersection
- [ ] Save to local cache (Parquet format)
- [ ] Incremental updates (only missing candles)

**Implementation** (`src/data/binance_downloader.py`):
```python
class BinanceDataDownloader:
    """Downloads historical OHLCV from Binance for backtesting"""

    def __init__(self):
        self.exchange = ccxt.binance()

    def get_common_symbols(self) -> list[str]:
        """Get intersection of Binance and Hyperliquid symbols"""
        binance_perps = self._get_binance_perps()
        hl_perps = self._get_hyperliquid_perps()

        common = set(binance_perps) & set(hl_perps)

        # Filter by volume
        filtered = [
            s for s in common
            if self._get_24h_volume(s) > config['trading']['data']['min_volume_24h']
        ]

        return sorted(filtered)

    def download_ohlcv(
        self,
        symbols: list[str],
        timeframe: str,
        days: int
    ) -> dict[str, pd.DataFrame]:
        """Download OHLCV data for multiple symbols"""
        # Implementation with caching, rate limiting, etc.
```

**Deliverable**: CSV/Parquet files in `data/binance/{symbol}_{timeframe}.parquet`

---

#### 2.2 Hyperliquid WebSocket Data Provider
**Goal**: Real-time OHLCV via WebSocket (from sevenbtc)

**Tasks**:
- [ ] Port `HyperliquidWebSocket` from sevenbtc
- [ ] Singleton pattern with thread-safe cache
- [ ] Subscribe to all symbols × timeframes
- [ ] Real-time candle updates

**Implementation** (`src/data/hyperliquid_websocket.py`):
```python
class HyperliquidDataProvider:
    """
    Singleton WebSocket data provider
    ONE connection for ALL strategies
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self.ws = HyperliquidWebSocket()
        self.cache = {}  # {symbol: {timeframe: DataFrame}}
        self.lock = threading.RLock()
        self.subscribers = []

    def subscribe_all(self, symbols: list[str], timeframes: list[str]):
        """Subscribe to all symbol × timeframe combinations"""
        for symbol in symbols:
            for tf in timeframes:
                self.ws.subscribe_candles(symbol, tf)
                self.cache[symbol][tf] = pd.DataFrame()

        # Start WebSocket listener
        threading.Thread(target=self._listen, daemon=True).start()

    def get_data(
        self,
        symbol: str,
        timeframe: str,
        lookback: int = 1000
    ) -> pd.DataFrame:
        """Thread-safe read from cache"""
        with self.lock:
            df = self.cache[symbol][timeframe]
            return df.tail(lookback).copy()

    def _listen(self):
        """WebSocket message handler"""
        while True:
            msg = self.ws.recv()
            if msg['type'] == 'candle':
                self._update_candle(msg)

    def _update_candle(self, msg: dict):
        """Update cache with new candle"""
        with self.lock:
            symbol = msg['symbol']
            tf = msg['timeframe']
            candle = msg['data']

            # Append or update last candle
            self.cache[symbol][tf] = self._append_candle(
                self.cache[symbol][tf],
                candle
            )
```

**Deliverable**: Real-time OHLCV cache operational

---

### PHASE 3: Strategy System (Days 7-10)

#### 3.1 StrategyCore Base Class
**Goal**: Abstract base for all strategies

**Implementation** (`src/strategies/base.py`):
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
import pandas as pd

@dataclass
class Signal:
    """Trading signal output"""
    direction: str  # 'long', 'short', 'close'
    size: float     # Position size (% of capital)
    stop_loss: float
    take_profit: float
    reason: str     # Explanation for logging

class StrategyCore(ABC):
    """
    Abstract base class for all strategies

    MUST be pure function:
    - Same input → same output
    - No state mutation
    - No external dependencies (DB, API, etc.)
    """

    def __init__(self, params: dict = None):
        self.params = params or {}

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        """
        Generate trading signal from OHLCV data

        Args:
            df: OHLCV DataFrame with columns [open, high, low, close, volume]

        Returns:
            Signal object if conditions met, None otherwise
        """
        pass
```

**Deliverable**: Base class + example strategy

---

#### 3.2 AI Strategy Generator
**Goal**: Generate StrategyCore classes using AI

**Tasks**:
- [ ] Port `AIManager` from fivebtc (multi-provider rotation)
- [ ] Pattern-discovery API client
- [ ] Jinja2 templates for prompts
- [ ] Strategy builder (combines patterns → code)
- [ ] Code validation (AST check)

**Implementation** (`src/generator/strategy_builder.py`):
```python
class StrategyBuilder:
    """Generates StrategyCore classes using AI"""

    def __init__(self):
        self.ai_manager = AIManager()
        self.pattern_client = PatternDiscoveryClient()
        self.template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader('src/generator/templates')
        )

    def generate_strategy(
        self,
        strategy_type: str,
        timeframe: str,
        use_patterns: bool = True
    ) -> str:
        """
        Generate StrategyCore Python code

        Returns:
            Python code as string
        """
        # 1. Get patterns if requested
        patterns = None
        if use_patterns:
            patterns = self.pattern_client.get_tier_1_patterns(
                timeframe=timeframe,
                limit=10
            )

        # 2. Build prompt
        template = self.template_env.get_template('generate_strategy.j2')
        prompt = template.render(
            strategy_type=strategy_type,
            timeframe=timeframe,
            patterns=patterns
        )

        # 3. Call AI
        code = self.ai_manager.generate(prompt)

        # 4. Validate structure
        if not self._validate_structure(code):
            # Try to fix
            code = self.ai_manager.fix_code(code, validation_errors)

        return code

    def _validate_structure(self, code: str) -> bool:
        """AST validation for StrategyCore compliance"""
        try:
            tree = ast.parse(code)

            # Check: Has class inheriting from StrategyCore
            # Check: Has generate_signal method
            # Check: No forbidden patterns (shift(-1), center=True, etc.)

            return True
        except:
            return False
```

**Prompt Template** (`src/generator/templates/generate_strategy.j2`):
```jinja2
You are an expert quantitative trader. Generate a StrategyCore class for cryptocurrency perpetual futures trading.

STRICT REQUIREMENTS:
1. Class MUST inherit from StrategyCore
2. MUST implement generate_signal(self, df: pd.DataFrame) -> Signal | None
3. Function MUST be PURE (no state, no side effects)
4. Use ONLY past data (no lookahead bias):
   - ✅ df['close'].rolling(10).max()
   - ❌ df['close'].rolling(10, center=True).max()  # FORBIDDEN
   - ✅ df['close'].iloc[-1]
   - ❌ df['close'].shift(-1)  # FORBIDDEN

STRATEGY SPECIFICATION:
- Type: {{ strategy_type }}
- Timeframe: {{ timeframe }}

{% if patterns %}
VALIDATED PATTERNS (from pattern-discovery):
{% for pattern in patterns %}
- {{ pattern.name }}: {{ pattern.formula }}
  Edge: {{ pattern.test_edge }}%, Win Rate: {{ pattern.test_win_rate }}%
  Direction: {{ pattern.target_direction }}
{% endfor %}

You may combine 2-3 patterns using AND logic for entry signals.
{% endif %}

OUTPUT FORMAT:
```python
import pandas as pd
import numpy as np
import talib as ta
from src.strategies.base import StrategyCore, Signal

class Strategy_{{ strategy_type }}_{{ id }}(StrategyCore):
    """
    [Brief description]

    Entry: [conditions]
    Exit: [TP/SL based on ATR or fixed %]
    """

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        # Minimum data check
        if len(df) < 50:
            return None

        # Calculate indicators
        # ... your logic here ...

        # Entry conditions
        if entry_conditions_met:
            return Signal(
                direction='long',  # or 'short'
                size=0.10,  # 10% of capital
                stop_loss=calculated_sl,
                take_profit=calculated_tp,
                reason="Brief explanation"
            )

        return None
```

Generate complete, production-ready code. Output ONLY the Python code block.
```

**Deliverable**: `python main.py generate --count 10` creates 10 strategies

---

### PHASE 4: Backtesting Engine (Days 11-14)

#### 4.1 VectorBT Wrapper
**Goal**: Backtest StrategyCore with VectorBT

**Implementation** (`src/backtester/vectorbt_engine.py`):
```python
class VectorBTBacktester:
    """Wraps VectorBT for backtesting StrategyCore"""

    def __init__(self, config: dict):
        self.config = config

    def backtest(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        initial_capital: float = 10000
    ) -> dict:
        """
        Run backtest on historical data

        Args:
            strategy: StrategyCore instance
            data: Multi-symbol OHLCV DataFrame
            initial_capital: Starting capital

        Returns:
            dict with metrics
        """
        # 1. Generate signals for entire dataset
        entries, exits, sizes = self._generate_signals(strategy, data)

        # 2. Run VectorBT backtest
        portfolio = vbt.Portfolio.from_signals(
            close=data['Close'],
            entries=entries,
            exits=exits,
            size=sizes,
            size_type='percent',
            fees=self.config['hyperliquid']['fee_rate'],
            slippage=self.config['hyperliquid']['slippage'],
            init_cash=initial_capital,
            cash_sharing=True
        )

        # 3. Extract metrics
        metrics = self._extract_metrics(portfolio)

        return metrics

    def _generate_signals(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame
    ) -> tuple:
        """Convert StrategyCore to VectorBT signal arrays"""
        entries = pd.DataFrame(False, index=data.index, columns=data.columns)
        exits = entries.copy()
        sizes = pd.DataFrame(0.0, index=data.index, columns=entries.columns)

        for symbol in entries.columns:
            df = self._extract_symbol_data(data, symbol)

            for i in range(len(df)):
                signal = strategy.generate_signal(df.iloc[:i+1])

                if signal:
                    if signal.direction in ['long', 'short']:
                        entries.loc[df.index[i], symbol] = True
                        sizes.loc[df.index[i], symbol] = signal.size
                    elif signal.direction == 'close':
                        exits.loc[df.index[i], symbol] = True

        return entries, exits, sizes

    def _extract_metrics(self, portfolio) -> dict:
        """Extract all relevant metrics from VectorBT portfolio"""
        return {
            'total_return': portfolio.total_return(),
            'sharpe_ratio': portfolio.sharpe_ratio(),
            'sortino_ratio': portfolio.sortino_ratio(),
            'max_drawdown': portfolio.max_drawdown(),
            'win_rate': portfolio.trades.win_rate,
            'expectancy': portfolio.trades.expectancy,
            'total_trades': portfolio.trades.count(),
            'profit_factor': portfolio.trades.profit_factor,

            # Custom metrics (from fivebtc)
            'ed_ratio': self._calculate_ed_ratio(portfolio),
            'consistency': self._calculate_consistency(portfolio),
        }
```

**Deliverable**: `python main.py backtest --strategy Strategy_MOM_abc123`

---

#### 4.2 Lookahead Validator
**Goal**: Detect lookahead bias (AST + shuffle test)

**Implementation** (`src/backtester/validator.py`):
```python
class LookaheadValidator:
    """Detects lookahead bias in strategies"""

    def validate(self, strategy_code: str, backtest_data: pd.DataFrame) -> dict:
        """
        Run validation suite

        Returns:
            {
                'ast_check_passed': bool,
                'shuffle_test_passed': bool,
                'shuffle_p_value': float,
                'violations': list[str]
            }
        """
        results = {}

        # 1. AST Analysis
        results['ast_check_passed'], violations = self._ast_check(strategy_code)
        results['violations'] = violations

        # 2. Shuffle Test
        if results['ast_check_passed']:
            p_value = self._shuffle_test(strategy, backtest_data)
            results['shuffle_p_value'] = p_value
            results['shuffle_test_passed'] = p_value < 0.05

        return results

    def _ast_check(self, code: str) -> tuple[bool, list[str]]:
        """AST-based pattern detection"""
        violations = []
        tree = ast.parse(code)

        # Check for forbidden patterns
        for node in ast.walk(tree):
            # center=True in rolling
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr') and node.func.attr == 'rolling':
                    for kw in node.keywords:
                        if kw.arg == 'center' and kw.value.value == True:
                            violations.append("rolling(center=True) detected")

            # Negative shift
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr') and node.func.attr == 'shift':
                    if node.args and isinstance(node.args[0], ast.UnaryOp):
                        if isinstance(node.args[0].op, ast.USub):
                            violations.append("Negative shift detected")

        return (len(violations) == 0, violations)

    def _shuffle_test(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        n_iterations: int = 100
    ) -> float:
        """Empirical shuffle test (from pattern-discovery)"""
        # 1. Real backtest edge
        real_edge = backtest(strategy, data).expectancy

        # 2. Shuffle test
        shuffled_edges = []
        for _ in range(n_iterations):
            signals = generate_all_signals(strategy, data)
            shuffled_signals = np.random.permutation(signals)
            shuffled_edge = backtest_with_signals(data, shuffled_signals).expectancy
            shuffled_edges.append(shuffled_edge)

        # 3. Calculate p-value
        mean = np.mean(shuffled_edges)
        std = np.std(shuffled_edges)
        z_score = (real_edge - mean) / std
        p_value = 1 - scipy.stats.norm.cdf(z_score)

        return p_value
```

**Deliverable**: Lookahead detection integrated in backtest pipeline

---

#### 4.3 Walk-Forward Optimizer
**Goal**: Optimize parameters with walk-forward validation

**Implementation** (`src/backtester/optimizer.py`):
```python
class WalkForwardOptimizer:
    """
    Parameter optimization with walk-forward validation
    Prevents overfitting by testing on out-of-sample windows
    """

    def optimize(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        param_grid: dict,
        n_windows: int = 4
    ) -> dict | None:
        """
        Walk-forward optimization

        Args:
            strategy: StrategyCore instance
            data: Historical OHLCV
            param_grid: {'param_name': [value1, value2, ...]}
            n_windows: Number of expanding windows

        Returns:
            Best params if stable, None if unstable
        """
        windows = self._create_windows(data, n_windows)
        params_per_window = []

        for train_data, test_data in windows:
            # Grid search on train set
            best_params = self._grid_search(strategy, train_data, param_grid)

            # Validate on test set (out-of-sample)
            test_metrics = self._test(strategy, test_data, best_params)

            # Reject if poor performance
            if test_metrics['sharpe'] < 1.0:
                return None

            params_per_window.append(best_params)

        # Check parameter stability across windows
        if self._are_params_stable(params_per_window):
            return self._average_params(params_per_window)
        else:
            return None  # Unstable = overfitting

    def _are_params_stable(self, params_list: list[dict]) -> bool:
        """Check if parameters are consistent across windows"""
        for key in params_list[0].keys():
            values = [p[key] for p in params_list]
            cv = np.std(values) / np.mean(values)  # Coefficient of variation

            if cv > 0.3:  # >30% variation = unstable
                return False

        return True
```

**Deliverable**: Optimized parameters with stability guarantee

---

### PHASE 5: Classifier & Deployment (Days 15-18)

#### 5.1 Strategy Scorer
**Goal**: Multi-factor scoring system

**Implementation** (`src/classifier/scorer.py`):
```python
class StrategyScorer:
    """Calculates composite score for strategy ranking"""

    def __init__(self, config: dict):
        self.weights = config['classification']['score_weights']

    def score(self, metrics: dict) -> float:
        """
        Calculate composite score

        Score = (0.4 × Edge) + (0.3 × Sharpe) + (0.2 × Consistency) + (0.1 × Stability)

        Normalized to 0-100 scale
        """
        edge_score = self._normalize(metrics['expectancy'], 0, 0.10)
        sharpe_score = self._normalize(metrics['sharpe_ratio'], 0, 3.0)
        consistency_score = metrics['consistency']  # Already 0-1
        stability_score = 1 - metrics['wf_stability']  # Lower is better

        score = (
            self.weights['edge'] * edge_score +
            self.weights['sharpe'] * sharpe_score +
            self.weights['consistency'] * consistency_score +
            self.weights['stability'] * stability_score
        )

        return score * 100  # 0-100 scale

    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize value to 0-1 range"""
        return min(max((value - min_val) / (max_val - min_val), 0), 1)
```

---

#### 5.2 Portfolio Builder (Top 10 Selector)
**Goal**: Select best 10 strategies with diversification

**Implementation** (`src/classifier/portfolio_builder.py`):
```python
class PortfolioBuilder:
    """Selects top 10 strategies with diversification constraints"""

    def select_top_10(self, strategies: list[Strategy]) -> list[Strategy]:
        """
        Select top 10 strategies ensuring:
        - Diversification (max 3 same type, max 3 same timeframe)
        - Market regime compatibility
        - Balanced risk
        """
        # 1. Filter by minimum thresholds
        eligible = [
            s for s in strategies
            if s.score > 50 and
               s.backtest_sharpe > 1.0 and
               s.backtest_win_rate > 0.55 and
               s.shuffle_p_value < 0.05
        ]

        # 2. Sort by score
        eligible.sort(key=lambda s: s.score, reverse=True)

        # 3. Select with diversification
        selected = []
        type_counts = defaultdict(int)
        tf_counts = defaultdict(int)

        for strategy in eligible:
            if len(selected) >= 10:
                break

            # Check diversification constraints
            if (type_counts[strategy.type] < 3 and
                tf_counts[strategy.timeframe] < 3):
                selected.append(strategy)
                type_counts[strategy.type] += 1
                tf_counts[strategy.timeframe] += 1

        return selected
```

---

#### 5.3 Subaccount Manager
**Goal**: Deploy strategies to Hyperliquid subaccounts

**Implementation** (`src/executor/subaccount_manager.py`):
```python
class SubaccountManager:
    """Manages deployment to 10 Hyperliquid subaccounts"""

    def __init__(self, client: HyperliquidClient):
        self.client = client
        self.assignments = {}  # {subaccount_id: strategy_id}

    def deploy_strategies(self, strategies: list[Strategy]):
        """Deploy top 10 to subaccounts 1-10"""
        for i, strategy in enumerate(strategies[:10], start=1):
            # 1. Stop previous strategy if exists
            if i in self.assignments:
                self._stop_strategy(i)

            # 2. Load new strategy
            strategy_instance = self._load_strategy(strategy)

            # 3. Assign to subaccount
            self.assignments[i] = {
                'strategy_id': strategy.id,
                'strategy': strategy_instance,
                'subaccount_id': i
            }

            # 4. Update database
            db.update_strategy(strategy.id, subaccount_id=i, status='LIVE')

            logger.info(f"Deployed {strategy.name} to subaccount {i}")

    def _stop_strategy(self, subaccount_id: int):
        """Stop strategy and close positions"""
        assignment = self.assignments[subaccount_id]

        # Close all positions for this subaccount
        self.client.switch_subaccount(subaccount_id)
        self.client.close_all_positions()

        # Update database
        db.update_strategy(
            assignment['strategy_id'],
            subaccount_id=None,
            status='RETIRED'
        )
```

---

### PHASE 6: Orchestration & Live Trading (Days 19-22)

#### 6.1 Strategy Orchestrator
**Goal**: Main process coordinating all strategies

**Implementation** (`src/orchestration/orchestrator.py`):
```python
class StrategyOrchestrator:
    """
    Main orchestrator - manages 10 live strategies
    Single process, multi-timeframe scheduling
    """

    def __init__(self, config_path: str = 'config/config.yaml'):
        self.config = load_config(config_path)

        # Singleton components
        self.data_provider = HyperliquidDataProvider()
        self.client = HyperliquidClient(self.config)
        self.db = DatabaseConnection(self.config)

        # Strategy management
        self.strategies = {}  # {subaccount_id: (strategy, metadata)}
        self.scheduler = APScheduler()

        # State
        self.running = True
        self.shutdown_event = threading.Event()

    def start(self):
        """Main entry point"""
        logger.info("Starting SixBTC Orchestrator")

        try:
            # 1. Initialize
            self._initialize()

            # 2. Load strategies
            self._load_live_strategies()

            # 3. Setup schedules
            self._setup_schedules()

            # 4. Start WebSocket
            self.data_provider.start()

            # 5. Run forever
            while self.running:
                time.sleep(1)
                if self.shutdown_event.wait(timeout=1):
                    break

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received")

        finally:
            self.shutdown()

    def _setup_schedules(self):
        """Setup per-timeframe iteration schedules"""
        # Group strategies by timeframe
        strategies_by_tf = defaultdict(list)
        for sub_id, (strategy, meta) in self.strategies.items():
            tf = meta['timeframe']
            strategies_by_tf[tf].append((sub_id, strategy, meta))

        # Schedule each group
        for tf, strategy_list in strategies_by_tf.items():
            interval_seconds = timeframe_to_seconds(tf)

            self.scheduler.add_job(
                func=self._run_iteration,
                trigger='interval',
                seconds=interval_seconds,
                args=[strategy_list],
                id=f'iteration_{tf}',
                max_instances=1  # Prevent overlap
            )

        self.scheduler.start()

    def _run_iteration(self, strategy_list: list):
        """Execute iteration for strategies on same timeframe"""
        for subaccount_id, strategy, meta in strategy_list:
            try:
                self._execute_strategy(subaccount_id, strategy, meta)
            except Exception as e:
                logger.error(f"Error in strategy {meta['name']}: {e}")

    def _execute_strategy(
        self,
        subaccount_id: int,
        strategy: StrategyCore,
        meta: dict
    ):
        """Execute single strategy iteration"""
        symbol = meta['symbol']
        timeframe = meta['timeframe']

        # 1. Get data from shared cache
        df = self.data_provider.get_data(symbol, timeframe)

        # 2. Generate signal
        signal = strategy.generate_signal(df)

        # 3. Execute if valid
        if signal:
            self._execute_signal(subaccount_id, symbol, signal)

            # Log decision
            self.db.log_decision(
                strategy_id=meta['strategy_id'],
                subaccount_id=subaccount_id,
                signal=signal
            )

    def _execute_signal(
        self,
        subaccount_id: int,
        symbol: str,
        signal: Signal
    ):
        """Execute trading signal on Hyperliquid"""
        # Switch to subaccount
        self.client.switch_subaccount(subaccount_id)

        if signal.direction in ['long', 'short']:
            # Open position
            self._open_position(subaccount_id, symbol, signal)

        elif signal.direction == 'close':
            # Close position
            self._close_position(subaccount_id, symbol)

    def shutdown(self):
        """Graceful shutdown"""
        if not self.running:
            return

        logger.info("Initiating graceful shutdown...")
        self.running = False
        self.shutdown_event.set()

        # Stop scheduler
        self.scheduler.shutdown(wait=False)

        # Cancel all pending orders
        if self.config['deployment']['shutdown']['cancel_orders']:
            for sub_id in range(1, 11):
                self.client.switch_subaccount(sub_id)
                self.client.cancel_all_orders()

        # Optionally close positions
        if self.config['deployment']['shutdown']['close_positions']:
            for sub_id in range(1, 11):
                self.client.switch_subaccount(sub_id)
                self.client.close_all_positions()

        # Close WebSocket
        self.data_provider.close()

        # Close database
        self.db.close()

        logger.info("Shutdown complete")
```

**Signal Handlers** (in `main.py`):
```python
import signal

def setup_signal_handlers(orchestrator):
    """Setup graceful shutdown on signals"""
    def handler(signum, frame):
        logger.info(f"Received signal {signum}")
        orchestrator.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handler)  # Supervisor/Docker stop
    signal.signal(signal.SIGINT, handler)   # Ctrl+C
```

---

### PHASE 7: Monitoring & Testing (Days 23-28)

#### 7.1 Monitoring Dashboard
**Goal**: Real-time performance monitoring

**Implementation** (`src/monitor/dashboard.py`):
```python
from rich.console import Console
from rich.table import Table
from rich.live import Live

class MonitorDashboard:
    """Real-time monitoring dashboard (Rich TUI)"""

    def __init__(self):
        self.console = Console()
        self.db = DatabaseConnection()

    def run(self):
        """Run live dashboard"""
        with Live(self._generate_display(), refresh_per_second=1) as live:
            while True:
                time.sleep(5)
                live.update(self._generate_display())

    def _generate_display(self):
        """Generate Rich renderable"""
        # System status
        status_table = self._system_status_table()

        # Per-strategy performance
        strategy_table = self._strategy_performance_table()

        # Recent trades
        trades_table = self._recent_trades_table()

        return Group(status_table, strategy_table, trades_table)
```

---

#### 7.2 Integration Tests
**Goal**: End-to-end testing before deployment

**Test Suite** (`tests/test_integration.py`):
```python
def test_strategy_generation():
    """Test AI generates valid StrategyCore"""
    builder = StrategyBuilder()
    code = builder.generate_strategy('MOM', '15m')

    # Validate structure
    assert 'class Strategy_' in code
    assert 'generate_signal' in code

    # Import and instantiate
    strategy = compile_strategy(code)
    assert isinstance(strategy, StrategyCore)

def test_backtest_pipeline():
    """Test full backtest pipeline"""
    strategy = load_test_strategy()
    data = load_test_data()

    backtester = VectorBTBacktester()
    results = backtester.backtest(strategy, data)

    assert 'sharpe_ratio' in results
    assert 'total_trades' in results

def test_live_execution_dry_run():
    """Test live execution without real orders"""
    orchestrator = StrategyOrchestrator(dry_run=True)
    orchestrator.start()

    # Run for 5 minutes
    time.sleep(300)
    orchestrator.shutdown()

    # Verify no errors
    assert orchestrator.error_count == 0
```

**Run Tests**: `pytest tests/ -v`

---

## 🚀 DEPLOYMENT CHECKLIST

### Pre-Production (Testing Phase)
- [ ] All unit tests pass (`pytest tests/`)
- [ ] Integration tests pass
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] `.env` configured with test credentials
- [ ] Config validated (`python -m src.config.validate`)
- [ ] PostgreSQL running (`docker-compose up -d postgres`)
- [ ] Pattern-discovery API accessible (`curl http://localhost:8001/health`)
- [ ] Binance data downloaded for common symbols
- [ ] 3 test strategies backtested successfully

### Testing Phase Deployment
```bash
# 1. Setup environment
cd /home/bitwolf/sixbtc
source .venv/bin/activate

# 2. Start database
docker-compose up -d postgres

# 3. Run migrations
alembic upgrade head

# 4. Generate test strategies
python main.py generate --count 20

# 5. Backtest all
python main.py backtest --all

# 6. Select top 3 for testing
python main.py classify --limit 3

# 7. Deploy to test subaccounts (1-3)
python main.py deploy --test-mode

# 8. Start orchestrator
python main.py run

# 9. Monitor (separate terminal)
python main.py monitor
```

### Production Deployment (After Testing Success)
```bash
# 1. Scale to full 10 subaccounts
python main.py deploy --full

# 2. Setup Supervisor (production)
sudo cp deployment/supervisor/sixbtc.conf /etc/supervisor/conf.d/
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start sixbtc:*

# 3. Verify
supervisorctl status sixbtc:*
```

---

## 📊 SUCCESS METRICS

### Testing Phase (1-2 weeks, $300 capital)
- **Uptime**: >95% (system must run 24/7)
- **Win Rate**: ≥50% (across all 3 subaccounts)
- **Max Drawdown**: <25% per subaccount
- **Execution**: Slippage <0.1%, fills >95%
- **No Critical Bugs**: Zero crashes requiring manual intervention

### Production Phase (After graduation)
- **Win Rate**: ≥55%
- **Expectancy**: >0.02 (2% edge)
- **Sharpe Ratio**: >1.0 (portfolio level)
- **Max Drawdown**: <20%
- **Uptime**: >99%

---

## 🔄 CONTINUOUS IMPROVEMENT CYCLE

### Daily
- Monitor performance dashboard
- Check for errors in logs
- Verify WebSocket connection health

### Weekly
- Review strategy performance (live vs backtest)
- Rotate underperforming strategies
- Generate new strategy batch

### Monthly
- Analyze correlation between strategies
- Update pattern-discovery library
- Optimize deployment parameters

---

## 📚 APPENDIX

### Useful Commands

```bash
# Development
python main.py generate --count 50
python main.py backtest --all
python main.py classify
python main.py deploy --dry-run

# Production
supervisorctl start sixbtc:orchestrator
supervisorctl status sixbtc:*
supervisorctl tail -f sixbtc:orchestrator

# Database
psql -h localhost -U sixbtc -d sixbtc
alembic revision --autogenerate -m "description"
alembic upgrade head

# Docker
docker-compose up -d
docker-compose logs -f postgres
docker-compose down

# Monitoring
python main.py monitor
python main.py status --subaccount 1
python main.py emergency-stop --all
```

### Emergency Procedures

**System Crash Recovery**:
```bash
# 1. Stop all processes
supervisorctl stop sixbtc:*

# 2. Check database integrity
psql -h localhost -U sixbtc -d sixbtc -c "SELECT COUNT(*) FROM strategies WHERE status='LIVE';"

# 3. Sync positions with Hyperliquid
python -m src.executor.sync_positions

# 4. Restart
supervisorctl start sixbtc:orchestrator
```

**Position Emergency Close**:
```bash
python main.py emergency-stop --subaccount 5  # Close subaccount 5
python main.py emergency-stop --all           # Close all positions
```

---

## ✅ DEVELOPMENT COMPLETION CRITERIA

This plan is considered complete when:

1. ✅ All 7 phases implemented and tested
2. ✅ Testing phase successful ($300, 3 subaccounts, 1-2 weeks)
3. ✅ Win rate ≥50%, max DD <25%, no critical bugs
4. ✅ Documentation complete (CLAUDE.md + this plan)
5. ✅ Supervisor configuration working
6. ✅ Emergency procedures tested and documented
7. ✅ Ready to scale to full 10 subaccounts in production

**Estimated Timeline**: 3-4 weeks for MVP + 1-2 weeks testing = **5-6 weeks total**

---

**Last Updated**: 2025-12-20
**Version**: 1.0.0
**Status**: Ready for Implementation
