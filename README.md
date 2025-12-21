# SixBTC - AI-Powered Multi-Strategy Trading System

**Autonomous trading system for Hyperliquid perpetual futures** powered by AI-generated strategies, VectorBT backtesting, and adaptive risk management.

## 🎯 Overview

SixBTC is a production-grade cryptocurrency trading system that:
- **Generates** trading strategies using AI (Claude, Gemini, Codex)
- **Backtests** strategies with VectorBT (1000x faster than Freqtrade)
- **Validates** strategies with lookahead detection and shuffle testing
- **Deploys** top performers to Hyperliquid subaccounts
- **Monitors** live performance and auto-rotates underperformers

### Key Features

✅ **Scalable Architecture**: Designed to scale from 10 to 1000+ live strategies
✅ **ATR-Based Risk Management**: Adaptive position sizing based on volatility
✅ **Multi-Timeframe**: Strategies across 5m, 15m, 30m, 1h, 4h, 1d
✅ **Pattern-Discovery Integration**: Leverages validated trading patterns
✅ **Walk-Forward Validation**: Prevents overfitting with rigorous testing
✅ **WebSocket-First**: Real-time market data with zero rate limits
✅ **Deployment Agnostic**: Run standalone, with Supervisor, Docker, or Systemd

## 📋 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (via Docker)
- Hyperliquid account with API access
- 16GB+ RAM (for 100+ strategies)
- Multi-core CPU (8+ cores recommended)

### Installation

```bash
# 1. Clone repository
cd /home/bitwolf
git clone <repository-url> sixbtc
cd sixbtc

# 2. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup environment variables
cp .env.example .env
nano .env  # Fill in your credentials

# 5. Start PostgreSQL
docker-compose up -d postgres

# 6. Run database migrations
alembic upgrade head

# 7. Verify setup
python main.py --help
```

### Configuration

Edit `config/config.yaml` to customize:
- Risk management parameters
- Number of subaccounts
- Strategy generation settings
- Backtesting thresholds

See [CLAUDE.md](CLAUDE.md) for detailed configuration guidelines.

## 🚀 Usage

### Generate Strategies

```bash
# Generate 50 new strategies
python main.py generate --count 50

# Monitor generation progress
python main.py status --module generator
```

### Backtest Strategies

```bash
# Backtest all pending strategies
python main.py backtest --all

# Backtest specific strategy
python main.py backtest --strategy Strategy_MOM_abc123

# Backtest with custom parameters
python main.py backtest --all --lookback-days 180 --workers 20
```

### Deploy to Live

```bash
# Classify and select top 10 strategies
python main.py classify

# Deploy to subaccounts (dry-run first)
python main.py deploy --dry-run

# Deploy for real
python main.py deploy

# Check deployment status
python main.py status --live
```

### Monitor Performance

```bash
# Real-time dashboard
python main.py monitor

# Check specific subaccount
python main.py status --subaccount 5

# View recent trades
python main.py trades --limit 50
```

### Emergency Controls

```bash
# Emergency stop all positions
python main.py emergency-stop --all

# Stop specific subaccount
python main.py emergency-stop --subaccount 3

# Pause strategy rotation
python main.py pause-rotation
```

## 📊 Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    SIXBTC SYSTEM                          │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  WebSocket Data Provider (Shared)                        │
│  ├─ Real-time OHLCV (Hyperliquid)                        │
│  └─ Thread-safe cache                                    │
│                                                           │
│  Strategy Orchestrator (Main Process)                    │
│  ├─ 10-1000 StrategyCore instances                       │
│  ├─ Multi-timeframe scheduling (APScheduler)             │
│  ├─ Adaptive execution (sync → async → hybrid)           │
│  └─ Risk management (ATR-based sizing)                   │
│                                                           │
│  Hyperliquid Client                                      │
│  ├─ Subaccount management (1-10)                         │
│  ├─ Order execution                                      │
│  └─ Position tracking                                    │
│                                                           │
│  PostgreSQL Database (Docker)                            │
│  ├─ Strategies & backtest results                        │
│  ├─ Live trades & performance                            │
│  └─ Performance snapshots                                │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) for detailed architecture.

## 🛡️ Risk Management

### ATR-Based Position Sizing

```python
# Automatic volatility adaptation
Risk per trade: 2% of subaccount capital
Stop loss: 2×ATR from entry
Take profit: 3×ATR from entry (1.5:1 R:R minimum)

# Example:
Account: $1000
BTC ATR: $1500
Stop distance: $3000
Position size: $333 (auto-calculated)
```

### Emergency Stops

- **Portfolio-level**: 30% max drawdown → stop all
- **Subaccount-level**: 25% drawdown → retire strategy
- **Strategy-level**: -50% vs backtest edge → retire
- **Daily loss limit**: 10% → pause trading

See `config/config.yaml` for full risk parameters.

## 📈 Performance Metrics

### Backtest Thresholds

- Sharpe Ratio: ≥1.0
- Win Rate: ≥55%
- Expectancy: ≥2%
- Total Trades: ≥100
- Max Drawdown: ≤30%

### Live Monitoring

- Performance snapshots: Every 15 minutes
- Strategy rotation: Daily
- Health checks: Every 5 minutes

## 🧪 Testing Phase

**Initial deployment** (before scaling):
- **Capital**: $100 × 3 subaccounts = $300 total
- **Duration**: 1-2 weeks minimum
- **Success criteria**:
  - Win rate ≥50%
  - Max DD <25%
  - No critical bugs
  - Uptime >95%

After successful testing → scale to 10 subaccounts with full capital.

## 📚 Documentation

- [CLAUDE.md](CLAUDE.md) - Development principles and coding standards
- [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) - Detailed implementation roadmap
- `config/config.yaml` - Complete configuration reference

## 🔧 Development

### Run Tests

```bash
pytest tests/ -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## 🐛 Troubleshooting

### Common Issues

**Database connection failed**:
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check credentials in .env
cat .env | grep DB_

# Restart PostgreSQL
docker-compose restart postgres
```

**WebSocket disconnected**:
```bash
# Check network connectivity
ping api.hyperliquid.xyz

# Check logs
tail -f logs/sixbtc.log | grep websocket

# Restart orchestrator
supervisorctl restart sixbtc:orchestrator
```

**Strategy generation slow**:
```bash
# Check AI provider status
python main.py status --ai-providers

# Increase parallel workers in config
# config/config.yaml → generation.parallel_workers: 20
```

## 📊 Monitoring & Logging

### Logs

```bash
# Main log
tail -f logs/sixbtc.log

# Specific module
tail -f logs/sixbtc.log | grep orchestrator

# Errors only
tail -f logs/sixbtc.log | grep ERROR
```

### Health Check

```bash
# HTTP health endpoint (if enabled)
curl http://localhost:8080/health

# Response:
# {
#   "status": "healthy",
#   "uptime": 3600,
#   "active_strategies": 10,
#   "websocket_connected": true
# }
```

## 🤝 Contributing

This is a private trading system. No external contributions accepted.

## ⚠️ Disclaimer

**USE AT YOUR OWN RISK**

- Cryptocurrency trading carries substantial risk of loss
- Past performance does not guarantee future results
- This software is provided "as is" without warranty
- Always test with small capital first
- Never risk more than you can afford to lose

## 📄 License

Proprietary - All Rights Reserved

---

**Built with**: Python, VectorBT, Hyperliquid SDK, PostgreSQL, Claude AI

**Last Updated**: 2025-12-20 | **Version**: 1.0.0
