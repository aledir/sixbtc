# SixBTC - Project Structure

```
sixbtc/
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore patterns
├── CLAUDE.md                    # Development principles & architecture
├── DEVELOPMENT_PLAN.md          # 7-phase implementation roadmap
├── README.md                    # User guide & quick start
├── SUMMARY.md                   # Project summary & key decisions
├── docker-compose.yml           # PostgreSQL container
├── main.py                      # CLI entry point (to be created)
├── requirements.txt             # Python dependencies (to be created)
├── alembic.ini                  # Alembic configuration (to be created)
│
├── config/
│   └── config.yaml              # Master configuration (500+ lines)
│
├── src/                         # Source code
│   ├── generator/               # AI strategy generation
│   │   ├── __init__.py
│   │   ├── ai_manager.py       # Multi-provider rotation
│   │   ├── pattern_fetcher.py  # Pattern-discovery API client
│   │   ├── strategy_builder.py # Combine patterns → StrategyCore
│   │   └── templates/          # Jinja2 prompt templates
│   │
│   ├── backtester/              # VectorBT backtesting engine
│   │   ├── __init__.py
│   │   ├── vectorbt_engine.py  # Backtest executor
│   │   ├── data_loader.py      # Binance data loader
│   │   ├── optimizer.py        # Walk-forward parameter tuning
│   │   └── validator.py        # Lookahead + shuffle test
│   │
│   ├── classifier/              # Strategy ranking & selection
│   │   ├── __init__.py
│   │   ├── scorer.py           # Multi-factor scoring
│   │   ├── regime_filter.py    # Market condition filters
│   │   └── portfolio_builder.py # Top N selector
│   │
│   ├── executor/                # Live trading execution
│   │   ├── __init__.py
│   │   ├── hyperliquid_client.py # From sevenbtc
│   │   ├── subaccount_manager.py # Manage 10 subaccounts
│   │   ├── position_tracker.py   # Track open positions
│   │   ├── position_sizer.py     # ATR-based sizing
│   │   └── risk_manager.py       # Risk limits enforcement
│   │
│   ├── orchestration/           # System coordination
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # Main orchestrator
│   │   ├── adaptive_scheduler.py # Mode selection (sync/async/hybrid)
│   │   └── graceful_shutdown.py  # Shutdown handler
│   │
│   ├── strategies/              # Strategy base classes
│   │   ├── __init__.py
│   │   └── base.py             # StrategyCore abstract class
│   │
│   ├── database/                # PostgreSQL layer
│   │   ├── __init__.py
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── connection.py       # Connection pool
│   │   └── migrations/         # Alembic migrations
│   │
│   ├── data/                    # Market data providers
│   │   ├── __init__.py
│   │   ├── hyperliquid_websocket.py # Live WebSocket
│   │   ├── multi_websocket.py       # Multi-WS manager
│   │   ├── binance_downloader.py    # Historical data
│   │   └── shared_cache.py          # Thread-safe cache
│   │
│   ├── monitor/                 # Monitoring & dashboards
│   │   ├── __init__.py
│   │   ├── dashboard.py        # Rich TUI dashboard
│   │   └── health_check.py     # HTTP health endpoint
│   │
│   └── config/                  # Config loader
│       ├── __init__.py
│       └── loader.py           # YAML config loader
│
├── strategies/                  # Generated strategy files
│   ├── generated/              # AI-generated code
│   ├── pending/                # Awaiting validation
│   ├── tested/                 # Backtested strategies
│   ├── selected/               # Top N selected for deployment
│   ├── live/                   # Currently deployed (symlinks)
│   └── retired/                # Underperforming strategies
│
├── data/                        # Market data cache
│   ├── binance/                # Historical OHLCV (Parquet)
│   └── cache/                  # Temporary data
│
├── logs/                        # Log files
│   └── sixbtc.log              # Main log file
│
├── tests/                       # Test suite
│   ├── __init__.py
│   ├── test_generator.py
│   ├── test_backtester.py
│   ├── test_executor.py
│   ├── test_orchestrator.py
│   └── test_integration.py     # End-to-end tests
│
├── scripts/                     # Utility scripts
│   ├── init_db.sql             # Database initialization
│   ├── backup.sh               # Backup script
│   └── deploy.sh               # Deployment script
│
└── deployment/                  # Deployment configurations
    ├── supervisor/
    │   └── sixbtc.conf         # Supervisor config
    └── docker/
        └── Dockerfile          # Docker image (optional)
```

## Key Directories

### **src/** - Source Code
All Python source code, organized by module responsibility.

### **strategies/** - Generated Strategies
File-based strategy storage with lifecycle management:
- `generated/` - Raw AI output
- `pending/` - Awaiting validation
- `tested/` - Backtested with metrics
- `selected/` - Top performers selected
- `live/` - Currently deployed (symlinks to tested/)
- `retired/` - Underperformers removed from live

### **data/** - Market Data
- `binance/` - Historical OHLCV for backtesting (Parquet format)
- `cache/` - Temporary data, cleared periodically

### **logs/** - System Logs
All log files (rotated automatically).

### **tests/** - Test Suite
Unit tests and integration tests.

### **deployment/** - Deployment Configs
Supervisor, Docker, and other deployment configurations.

---

## File Naming Conventions

### **Strategies**
```
Strategy_{TYPE}_{UUID8}.py

Examples:
- Strategy_MOM_a7f3d8b2.py  # Momentum strategy
- Strategy_REV_b8c9d0e1.py  # Mean reversion
- Strategy_TRN_c9d0e1f2.py  # Trend following
```

### **Data Files**
```
{symbol}_{timeframe}_{start}_{end}.parquet

Examples:
- BTC_15m_20240101_20240630.parquet
- ETH_1h_20240101_20240630.parquet
```

### **Logs**
```
sixbtc.log                    # Main log (rotated)
sixbtc.log.1, .2, .3, ...    # Rotated backups
```

---

## Module Dependencies

```
orchestrator
├── generator (creates strategies)
├── backtester (validates strategies)
├── classifier (ranks strategies)
├── executor (trades live)
│   ├── hyperliquid_client
│   ├── position_sizer (ATR-based)
│   └── risk_manager
└── data
    ├── hyperliquid_websocket (live)
    └── binance_downloader (historical)

All modules depend on:
- database (PostgreSQL)
- config (YAML)
```

---

**Last Updated**: 2025-12-20
**Status**: Foundation Complete
