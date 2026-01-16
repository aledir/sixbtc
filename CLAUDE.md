# SixBTC - AI-Powered Trading System

**Python 3.11+ | Numba-JIT Backtester | Hyperliquid SDK**

---

## STARTUP - READ FIRST

**At the start of EVERY new chat session**, read `docs/PIPELINE_OVERVIEW.md` for current pipeline architecture.

---

# REGOLA ZERO - SUPREMA E INVIOLABILE

**L'UNICA COSA CHE CONTA È FARE PROFITTO.**

Tutto il resto esiste SOLO per servire questo obiettivo. IN CASO DI CONFLITTO: IL PROFITTO VINCE. SEMPRE.

---

## FUNDAMENTAL PRINCIPLES

1. **KISS** - Maximum simplicity, no over-engineering
2. **Single Responsibility** - One class/function = one purpose
3. **No Fallback, Fast Fail** - `config['key']` not `config.get('key', default)`. Missing config = crash = good
4. **No Hardcoding** - ALL parameters in `config/config.yaml`
5. **Structural Fixes Only** - Fix ROOT CAUSE, no patches
6. **Dependency Injection** - Pass dependencies, don't create internally
7. **Type Safety** - Type hints everywhere, use mypy
8. **Testability First** - Pure functions, mock externals
9. **Clean Code** - Max 400 lines/file, NO backup files, NO commented code

---

## TERMINOLOGY - CRITICAL

**There is ONLY: STRATEGY**

- One strategy = one UUID = one database record = one deployable entity
- ✅ "400 strategies from base code" NOT "400 variations of one strategy"
- Variable names: `strategies` not `variations`
- Lifecycle: `GENERATED → VALIDATED → ACTIVE → LIVE → RETIRED` (or `FAILED`)

**Caching:**
- Shuffle test: cached by `base_code_hash` (lookahead = property of base code)
- Multi-window: NOT cached (depends on parameters)

---

## LANGUAGE AND CODE STYLE

- **ALL code/comments in English**
- **ALL logs ASCII only** (no emojis)
- **Italian for chat responses only**
- PEP 8, Black (line length: 100), isort

---

## SIXBTC-SPECIFIC RULES

### Rule #1: StrategyCore Contract
All strategies inherit from `StrategyCore` with `generate_signal(df) -> Signal | None`

### Rule #2: No Lookahead Bias
- No `center=True` in rolling
- No negative shift (`shift(-1)`)
- Validation: AST analysis + shuffle test + walk-forward

### Rule #3: Timeframe Agnostic
Use `bars_in_period()` not hardcoded values. Strategies work on 15m, 30m, 1h, 2h.

### Rule #4: Hyperliquid is Source of Truth
Exchange state is canonical. Database is audit trail only.

### Rule #4b: WebSocket First
WebSocket for ALL data. REST only for actions (place order, cancel). Rate limit: 1200 req/min.

### Rule #5: No AI Prompt Hardcoding
Use Jinja2 templates in `src/generator/templates/`

### Rule #6: Walk-Forward Everything
Backtest must be stable across time windows.

### Rule #7: Metrics Thresholds
- Sharpe ≥ 1.0, Win Rate ≥ 55%, Max DD ≤ 30%, Min Trades ≥ 100

### Rule #7b: Robustness Filter
`robustness = 0.50*oos_ratio + 0.35*trade_score + 0.15*simplicity >= 0.80`

### Rule #8: Emergency Stops
- Max DD: 30% portfolio, 10% daily, 25% subaccount
- 5 consecutive losses triggers review

---

## ARCHITECTURE

### Workflow
```
GENERATION → VALIDATION → BACKTESTING → ROTATION → MONITORING
(AI/Pattern)  (syntax/AST)  (IS+OOS+shuffle)  (ACTIVE→LIVE)  (track/retire)
```

### Daemon Processes (via supervisorctl)
| Service | Purpose |
|---------|---------|
| `sixbtc:api` | FastAPI backend (port 8080) |
| `sixbtc:frontend` | Vite dev server (port 5173) |
| `sixbtc:generator` | Strategy generation |
| `sixbtc:validator` | Validation pipeline |
| `sixbtc:backtester` | Backtesting + scoring |
| `sixbtc:rotator` | ACTIVE → LIVE rotation |
| `sixbtc:executor` | Live trading execution |
| `sixbtc:monitor` | Performance dashboard |
| `sixbtc:scheduler` | Scheduled tasks |
| `sixbtc:metrics` | Metrics collection |

### Strategy Sources (generation_mode)
| Source | Abbrev | Class | Description |
|--------|--------|-------|-------------|
| `pattern` | pat | `PatStrat_*` | From pattern-discovery API |
| `pattern_gen` | pgn | `PGnStrat_*` | Smart random composition |
| `unger` | ung | `UngStrat_*` | Regime-coherent (Unger) |
| `pandas_ta` | pta | `PtaStrat_*` | Pandas-TA indicators |
| `ai_free` | aif | `AIFStrat_*` | AI chooses indicators |
| `ai_assigned` | aia | `AIAStrat_*` | AI with assigned indicators |

---

## RISK MANAGEMENT

**Fixed Fractional Position Sizing:**
```
risk_amount = equity * risk_pct
notional = risk_amount / sl_pct
margin_needed = notional / leverage
```

Skip trade if: `margin_needed > available_margin` OR `notional < 10 USDC`

---

## DEVELOPMENT WORKFLOW

### Process Management
```bash
# ALWAYS use supervisorctl (no sudo)
supervisorctl status
supervisorctl restart sixbtc:*

# NEVER start manually with python -m ...
# NEVER use pkill/kill for services
```

### Testing
```bash
pytest tests/ -v  # MUST pass after ANY change
```

---

## FRONTEND PRINCIPLES

**Goal:** Answer "Am I making money?" - user should NEVER need to open Hyperliquid.

**Hierarchy:**
1. **Overview** - P&L, equity curve, system status
2. **Trading** - Subaccounts, positions, trade history
3. **Pipeline** - 10-step funnel, backtest quality
4. **Strategies** - Rankings, details
5. **System** - Logs, tasks, settings

---

## KEY DEPENDENCIES

- **Numba**: JIT for fast backtesting
- **Hyperliquid SDK**: github.com/hyperliquid-dex/hyperliquid-python-sdk
- **Pattern Discovery**: localhost:8001
- **Binance CCXT**: Data source

---

## GOLDEN CHECKLIST

- [ ] English code/comments, ASCII logs
- [ ] No hardcoded values
- [ ] Type hints everywhere
- [ ] No files >400 lines
- [ ] Tests pass
- [ ] No lookahead bias
- [ ] Strategies inherit StrategyCore

---

**Remember**: The system's purpose is to make money.
