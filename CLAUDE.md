# SixBTC - AI-Powered Trading System Development Guide

**Last Updated**: 2026-01-15 | **Python**: 3.11+ | **Core**: Numba-JIT Backtester + Hyperliquid SDK

---

## 🚀 STARTUP - READ FIRST

**At the start of EVERY new chat session**, read `docs/PIPELINE_OVERVIEW.md` to understand the current pipeline architecture. This file contains the detailed flow of strategy generation, validation, backtesting, and deployment.

```bash
# First action in every new session:
Read /home/bitwolf/sixbtc/docs/PIPELINE_OVERVIEW.md
```

---

# ███████████████████████████████████████████████████████████████████████████████
# ██                                                                           ██
# ██   REGOLA ZERO - SUPREMA E INVIOLABILE                                     ██
# ██                                                                           ██
# ██   L'UNICA COSA CHE CONTA È FARE PROFITTO.                                 ██
# ██                                                                           ██
# ██   Tutto il resto - architettura, codice pulito, best practices,           ██
# ██   pattern, testing - esiste SOLO per servire questo obiettivo.            ██
# ██                                                                           ██
# ██   OGNI decisione deve rispondere a UNA domanda:                           ██
# ██   "Questo mi aiuta a fare più soldi?"                                     ██
# ██                                                                           ██
# ██   Se la risposta è NO → non farlo.                                        ██
# ██   Se la risposta è SÌ → fallo, anche se viola altre regole.               ██
# ██                                                                           ██
# ██   IN CASO DI CONFLITTO TRA QUALSIASI REGOLA E IL PROFITTO:                ██
# ██   IL PROFITTO VINCE. SEMPRE. SENZA ECCEZIONI.                             ██
# ██                                                                           ██
# ███████████████████████████████████████████████████████████████████████████████

---

## 🏗️ FUNDAMENTAL PRINCIPLES

### 1. KISS - Keep It Simple, Stupid
- Maximum simplicity in all solutions
- No over-engineering or unnecessary complexity
- If it can be done in 10 lines instead of 100, do it in 10
- Prefer clear, maintainable code over clever abstractions

### 2. Single Responsibility
- Every class/function has ONE clear purpose
- If it does multiple things, split it
- Clean separation of concerns across modules
- Each module is independently testable

### 3. No Fallback, Fast Fail
```python
# ❌ WRONG - Masks configuration problems
timeout = config.get('timeout', 30)
api_key = os.getenv('API_KEY', 'default_key')

# ✅ CORRECT - Forces proper configuration
timeout = config['timeout']  # Crash if missing = good!
api_key = os.environ['API_KEY']  # Must be in environment
```

**Rationale**: Silent failures and defaults hide critical issues. If config is missing, crash immediately during startup, not during live trading.

### 4. No Hardcoding - Configuration is Sacred
```python
# ❌ FORBIDDEN - Hardcoded values
MAX_POSITIONS = 10
STOP_LOSS_PCT = 0.02
TIMEFRAME = '15m'

# ✅ REQUIRED - Everything from config
max_positions = config['risk']['max_open_positions']
stop_loss = config['risk']['fixed_risk_per_trade']
timeframe = config['trading']['timeframes']['intraday']
```

**Rules**:
- ALL behavioral parameters → `config/config.yaml`
- NO defaults in code (except pure math/display operations)
- Missing config = system crash = correct behavior
- Never use `dict.get()` with defaults for config values

### 5. Structural Fixes Only - NO PATCHES
```
🚫 PATCH MENTALITY (Forbidden):
- Quick fixes that mask symptoms
- Workarounds that bypass root causes
- "Good enough for now" temporary solutions

✅ STRUCTURAL MENTALITY (Required):
- Identify and solve ROOT CAUSE
- Clean, permanent solutions
- Improve architecture while fixing
```

**Example**:
```python
# ❌ PATCH - Masks the problem
try:
    result = unreliable_function()
except Exception:
    result = None  # Band-aid!

# ✅ STRUCTURAL - Fixes root cause
def reliable_function():
    # Redesigned logic that doesn't fail
    return properly_calculated_result()
```

### 6. Dependency Injection
```python
# ❌ WRONG - Creates dependencies internally
class Executor:
    def __init__(self):
        self.client = HyperliquidClient()  # Hardcoded dependency

# ✅ CORRECT - Injects dependencies
class Executor:
    def __init__(self, client: HyperliquidClient):
        self.client = client  # Testable, flexible
```

### 7. Type Safety
- Type hints everywhere
- Use `mypy` for static type checking
- Explicit error types (custom exceptions, not string codes)
- Immutable configuration after load

### 8. Testability First
- Every function testable in isolation
- Pure functions where possible (same input → same output)
- Mock external dependencies in tests
- Integration tests for critical paths

### 9. Modular Atomicity
- Each module is self-contained and atomic
- Clear, minimal interfaces between modules
- No circular dependencies
- Easy to replace/upgrade individual components

### 10. Clean Code Over Everything
- **Max 400 lines per file** - Split if exceeded
- **NO backup files** (_old.py, _legacy.py, _backup.py)
- **NO commented-out code blocks** - Git is the backup
- **NO deprecated code** - Delete, don't comment
- **Mandatory cleanup**: Every code change must leave the codebase cleaner than before

---

## ⚠️ TERMINOLOGY - CRITICAL

### THERE IS ONLY ONE CONCEPT: STRATEGY

**FUNDAMENTAL RULE - NO EXCEPTIONS**:
There is NO such thing as "parametric variation", "template instance", or "strategy variant".
There is ONLY: **STRATEGY**.

**WHAT IS A STRATEGY**:
- ✅ A unique entity with: UUID, code, parameters, backtest results, deployment capability
- ✅ Each strategy is INDEPENDENT and COMPLETE
- ✅ How it was generated (AI prompt, pattern-based, parametric expansion) is IRRELEVANT to its identity
- ✅ One strategy = one UUID = one database record = one deployable entity

**CORRECT TERMINOLOGY**:
- ✅ "Parametric backtest generates 400 STRATEGIES from base code"
- ✅ "Each strategy has unique code (parameters embedded), unique UUID, unique results"
- ✅ "The fact that 400 strategies derive from the same base code is a GENERATION DETAIL, not an ontological property"
- ✅ "Pattern-based generates 1 strategy, AI-based generates 400 strategies - both are just STRATEGIES"

**INCORRECT TERMINOLOGY** (causes confusion and bugs):
- ❌ "Parametric variation" → Say: "strategy generated via parametric expansion"
- ❌ "Template vs variations" → Say: "base code → N strategies"
- ❌ "Variant #47 of template abc123" → Say: "strategy xyz789"
- ❌ "Combination" when referring to a strategy → Say: "strategy"

**NAMING CONVENTION**:
- ✅ `Strategy_MOM_xyz789` (ONE UUID - the strategy's unique ID)
- ❌ `Strategy_MOM_abc123_p8a9f2d1c` (double UUID - implies template hierarchy)

**CODE IMPLICATIONS**:
- Variable names: `strategies` not `variations`, `generated_strategies` not `template_instances`
- No "template_id" field in Strategy model (it's just metadata, not identity)
- Each strategy goes through FULL pipeline: GENERATED → VALIDATED → ACTIVE → LIVE → RETIRED (or FAILED at any stage)
- Pattern-based strategies = AI-based strategies = Parametric strategies (all are STRATEGIES)

**WHY THIS MATTERS**:
- Prevents confusion like "400 variations of one strategy" (wrong - 400 separate strategies)
- Ensures uniform treatment in pipeline (all strategies follow same flow)
- Each strategy is scored and validated independently

**CACHING CLARIFICATION**:
- **Shuffle test**: CAN be cached by `base_code_hash` because lookahead bias is a property of the BASE CODE, not parameters. If base code has no lookahead, all parametric strategies from it won't have lookahead either.
- **Multi-window validation**: CANNOT be cached because consistency across time windows depends on PARAMETERS. Each strategy must be tested independently.

**EXCEPTIONS** (where "combination" IS correct):
- ✅ "Parameter combination" = the SET of parameters (SL × TP × leverage × exit) used to generate a strategy
- ✅ "Symbol × timeframe combinations" = data planning (not strategies)
- ✅ Mathematical context: "5 × 5 × 4 × 3 = 300 parameter combinations → 300 strategies"

**GOLDEN RULE**:
If it has a UUID and lives in the `strategies` table → it's a **STRATEGY**.
Period. No prefixes, no hierarchies, no "types of strategies".

---

## 🌍 LANGUAGE AND CODE STYLE

### Rule #0: Language Requirements
- **ALL code and comments MUST be in English**
- **ALL log messages MUST use ASCII characters only** (no emojis)
- **NO Italian or other languages** in code, comments, or logs
- **EXCEPTION: Use Italian for chat responses with the user** (but never in code)
- **EXCEPTION: Rich dashboard displays may use unicode symbols (●, •, ─, etc.)**

**Examples**:
```python
# ❌ WRONG
logger.info("📊 Strategia generata con successo!")  # Emoji + Italian

# ✅ CORRECT
logger.info("Strategy generated successfully")  # English + ASCII

# ✅ CORRECT for Rich dashboards only
console.print("● RUNNING", style="green")  # Unicode OK in UI
```

### Code Formatting
- **PEP 8** compliance
- **Black** formatter (line length: 100)
- **isort** for import organization
- **Descriptive variable names** (no single-letter except loop counters)

---

## 🎯 SIXBTC-SPECIFIC RULES

### Rule #1: StrategyCore is the Contract
```python
# ✅ REQUIRED - All strategies must inherit from StrategyCore
class Strategy_MOM_a7f3d8b2(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        # Pure function - no state, no side effects
        pass
```

**Why**: Ensures same code works in both backtest and live (Hyperliquid SDK).

### Rule #2: No Lookahead Bias
```python
# ❌ FORBIDDEN - Uses future data
df['swing_high'] = df['high'].rolling(11, center=True).max()  # center=True!
future_price = df['close'].shift(-1)  # Negative shift!

# ✅ CORRECT - Only past data
df['swing_high'] = df['high'].rolling(10).max()  # Lookback only
current_price = df['close'].iloc[-1]  # Current bar
```

**Validation**:
1. AST analysis for forbidden patterns
2. Shuffle test for empirical validation
3. Walk-forward testing for temporal stability

### Rule #3: Timeframe Agnostic Design
```python
# ❌ WRONG - Hardcoded timeframe
bars_24h = 96  # Assumes 15m timeframe

# ✅ CORRECT - Dynamic calculation
from src.features.timeframe import bars_in_period
bars_24h = bars_in_period('24h')  # Works with any TF
```

**Requirement**: Strategies must work on 15m, 30m, 1h, 2h without code changes.

### Rule #4: Hyperliquid is Source of Truth
- Exchange state is canonical for positions, orders, balance
- Database is audit trail and metadata only
- In case of discrepancy, Hyperliquid prevails ALWAYS
- Sync local state with exchange before every critical operation

### Rule #4b: WebSocket First - IMPERATIVE
```
┌─────────────────────────────────────────────────────────────────────────┐
│ WEBSOCKET È OBBLIGATORIO E PRIORITARIO                                  │
│                                                                         │
│ Per QUALSIASI comunicazione con Hyperliquid:                           │
│ 1. PRIMA: Verifica se WebSocket può essere usato                       │
│ 2. SOLO SE IMPOSSIBILE: Usa REST API (con rate limits!)                │
│                                                                         │
│ "Impossibile" significa:                                                │
│ - L'endpoint non esiste su WebSocket                                   │
│ - Documentazione Hyperliquid conferma che non è supportato             │
│ - NON significa "è più facile usare REST"                              │
└─────────────────────────────────────────────────────────────────────────┘
```

**WebSocket implementation**: `src/data/hyperliquid_websocket.py`
- `HyperliquidDataProvider` singleton class
- Supports: `allMids`, `candle`, `webData2` (account state), `userFills`, `orderUpdates`
- Auto-reconnection with exponential backoff
- Use this for ALL real-time data needs

**When REST API is allowed** (only after verifying WebSocket is impossible):
```python
# ❌ FORBIDDEN - REST for data that WebSocket provides
balance = client.get_account_balance()  # Wrong! Use webData2 subscription

# ✅ CORRECT - REST only for actions (place order, cancel, etc.)
client.place_order(order)  # OK - WebSocket doesn't support order placement
```

**If using REST API, MUST respect Hyperliquid rate limits:**
- Max 1200 requests per minute (20/second)
- Implement exponential backoff on 429 errors
- Use caching where appropriate
- Log all REST calls for monitoring

**Rationale**: WebSocket provides real-time updates without polling overhead. REST polling wastes resources and can hit rate limits. The `data stale` issue we encountered is a direct consequence of not using WebSocket for balance updates.

### Rule #5: No AI Prompt Hardcoding
```python
# ❌ FORBIDDEN - Hardcoded prompts
prompt = f"Generate a strategy with RSI < {threshold}"

# ✅ REQUIRED - Use Jinja2 templates
from jinja2 import Environment
template = env.get_template('generate_strategy.j2')
prompt = template.render(threshold=threshold, patterns=patterns)
```

**Location**: All templates in `src/generator/templates/`

### Rule #6: Walk-Forward Everything
- Backtest results must be stable across time windows
- Parameter optimization requires walk-forward validation
- Reject strategies that don't generalize
- Use pattern-discovery's 4-window validation approach

### Rule #7: Metrics-Driven Development
```python
# Every backtest must track:
- Sharpe Ratio (min: 1.0)
- Win Rate (min: 0.55)
- Expectancy (must be positive)
- Max Drawdown (max: 0.30)
- Total Trades (min: 100)
- ED Ratio (Expectancy/Drawdown efficiency)
- Consistency (Time-In-Profit percentage)
```

**Rejection criteria**: If any metric fails threshold, strategy is discarded.

### Rule #7b: Robustness Filtering
```python
# Every strategy entering ACTIVE pool must pass robustness check:
# Formula: robustness = 0.50*oos_ratio + 0.35*trade_score + 0.15*simplicity
#
# Components:
# - oos_ratio = OOS_Sharpe / IS_Sharpe (generalization to unseen data)
# - trade_score = total_trades / 150 (statistical significance)
# - simplicity = 1 / num_indicators (overfitting resistance)
#
# Threshold: robustness >= 0.80
```

**Why**: Score measures historical performance. Robustness measures confidence
the edge is real. Both are needed for live deployment.

### Rule #8: Emergency Stop Discipline
```python
# Automatic stops (non-negotiable):
- Max Drawdown: 30% (portfolio level)
- Daily Loss: 10% (single day)
- Strategy Degradation: -50% vs backtest edge

# Manual intervention required if:
- 3+ consecutive losing days
- Correlation breakdown (live vs backtest)
- Execution quality deteriorates
```

---

## 📂 ARCHITECTURE OVERVIEW

### Module Structure
```
sixbtc/
├── src/
│   ├── ai/                     # AI provider integration
│   │   └── providers.py        # Claude, Gemini, etc.
│   │
│   ├── api/                    # REST API endpoints
│   │   └── routes.py           # FastAPI routes
│   │
│   ├── backtester/             # Numba-JIT backtest engine
│   │   ├── backtest_engine.py  # Portfolio simulation (Numba-optimized)
│   │   ├── data_loader.py      # Binance data downloader
│   │   ├── parametric_backtest.py  # Parameter optimization
│   │   ├── multi_window_validator.py  # 4-window consistency test
│   │   ├── validator.py        # AST lookahead + shuffle test
│   │   └── main_continuous.py  # Backtester daemon
│   │
│   ├── config/                 # Configuration
│   │   └── loader.py           # YAML config reader (Fast Fail)
│   │
│   ├── data/                   # Market data management
│   │   ├── coin_registry.py    # Tradeable coins from Hyperliquid
│   │   └── pairs_updater.py    # Updates coin metadata 2x/day
│   │
│   ├── database/               # PostgreSQL layer
│   │   ├── models.py           # SQLAlchemy models
│   │   └── connection.py       # Connection pool
│   │
│   ├── executor/               # Live trading
│   │   ├── hyperliquid_client.py  # Hyperliquid SDK wrapper
│   │   ├── position_tracker.py    # Track open positions
│   │   ├── risk_manager.py        # Position sizing, stops
│   │   ├── trailing_service.py    # Trailing stop management
│   │   └── main_continuous.py     # Executor daemon
│   │
│   ├── generator/              # AI strategy generation
│   │   ├── direct_generator.py    # AI calls → code generation
│   │   ├── parametric_generator.py # Template expansion
│   │   ├── pattern_fetcher.py     # Query pattern-discovery API
│   │   ├── strategy_builder.py    # Combine patterns → StrategyCore
│   │   ├── indicator_combinator.py # For ai_assigned mode
│   │   ├── templates/             # Jinja2 prompts
│   │   └── main_continuous.py     # Generator daemon
│   │
│   ├── metrics/                # Performance metrics
│   │   └── collector.py        # Pipeline metrics snapshots
│   │
│   ├── monitor/                # Live monitoring
│   │   ├── dashboard.py        # Rich console dashboard
│   │   └── main_continuous.py  # Monitor daemon
│   │
│   ├── orchestration/          # Execution orchestration
│   │   └── scheduler.py        # Adaptive execution scheduler
│   │
│   ├── processes/              # Process management
│   │   └── manager.py          # Multi-daemon coordination
│   │
│   ├── rotator/                # ACTIVE → LIVE rotation
│   │   ├── selector.py         # Strategy selection
│   │   ├── deployer.py         # Subaccount deployment
│   │   └── main_continuous.py  # Rotator daemon
│   │
│   ├── scheduler/              # Task scheduling
│   │   └── main_continuous.py  # Scheduler daemon
│   │
│   ├── scorer/                 # Strategy scoring
│   │   ├── backtest_scorer.py  # Unified score formula
│   │   ├── live_scorer.py      # Live performance scoring
│   │   └── pool_manager.py     # ACTIVE pool management (max 300)
│   │
│   ├── strategies/             # Strategy core
│   │   └── base.py             # StrategyCore abstract class
│   │
│   ├── subaccount/             # Subaccount management
│   │   ├── allocator.py        # Capital allocation
│   │   └── main_continuous.py  # Subaccount daemon
│   │
│   ├── utils/                  # Utilities
│   │   └── logger.py           # Logging setup (ASCII only)
│   │
│   └── validator/              # Validation pipeline
│       ├── syntax_validator.py    # Python syntax check
│       ├── lookahead_test.py      # AST analysis
│       ├── execution_validator.py # Execution safety
│       └── main_continuous.py     # Validator daemon
│
├── config/
│   └── config.yaml             # Master configuration
│
├── data/                       # Market data cache
│   └── binance/                # OHLCV data
│
├── main.py                     # CLI entry point (scaffold)
├── CLAUDE.md                   # This file
└── tests/                      # Test suite
```

### Workflow Overview
```
┌────────────────────────────────────────────────────────────────┐
│ PHASE 1: GENERATION                                            │
├────────────────────────────────────────────────────────────────┤
│ Generator daemon: AI/Pattern → base code                       │
│ Output: strategies (status: GENERATED)                         │
└────────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────┐
│ PHASE 2: VALIDATION (3 phases)                                 │
├────────────────────────────────────────────────────────────────┤
│ Validator daemon: syntax → AST lookahead → execution test      │
│ Output: strategies (status: VALIDATED or FAILED)               │
└────────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────┐
│ PHASE 3: BACKTESTING                                           │
├────────────────────────────────────────────────────────────────┤
│ Backtester daemon: in-sample (120d) + out-of-sample (30d)      │
│ Score calculation (unified formula)                            │
│ If score >= min_score:                                         │
│   - Shuffle test (cached by base_code_hash)                    │
│   - Multi-window validation (NOT cached - per-strategy)        │
│ Output: strategies (status: ACTIVE pool or FAILED)             │
└────────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────┐
│ PHASE 4: ROTATION                                              │
├────────────────────────────────────────────────────────────────┤
│ Rotator daemon: selects top from ACTIVE → deploys to subaccounts│
│ Output: strategies (status: LIVE)                              │
└────────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────┐
│ PHASE 5: MONITORING                                            │
├────────────────────────────────────────────────────────────────┤
│ Monitor daemon: tracks live performance, retires underperformers│
│ Output: strategies (status: RETIRED if degraded)               │
└────────────────────────────────────────────────────────────────┘
```

### Daemon Processes

The system runs as **8 independent daemon processes**, each with its own `main_continuous.py`:

| Daemon | Location | Purpose |
|--------|----------|---------|
| **Generator** | `src/generator/main_continuous.py` | Creates strategies via AI/patterns |
| **Validator** | `src/validator/main_continuous.py` | Syntax, AST, execution validation |
| **Backtester** | `src/backtester/main_continuous.py` | Backtest, score, shuffle, multi-window |
| **Rotator** | `src/rotator/main_continuous.py` | ACTIVE → LIVE rotation |
| **Executor** | `src/executor/main_continuous.py` | Live trading on Hyperliquid |
| **Monitor** | `src/monitor/main_continuous.py` | Performance tracking dashboard |
| **Scheduler** | `src/scheduler/main_continuous.py` | Scheduled tasks (pairs update, etc.) |
| **Subaccount** | `src/subaccount/main_continuous.py` | Subaccount allocation management |

**Running daemons:**
```bash
# Each daemon runs independently
python -m src.generator.main_continuous
python -m src.validator.main_continuous
python -m src.backtester.main_continuous
python -m src.executor.main_continuous
# etc.
```

### Strategy Status Lifecycle

```
GENERATED → VALIDATED → ACTIVE → LIVE → RETIRED
     ↓           ↓          ↓
   FAILED     FAILED     FAILED
```

**Status definitions:**
- `GENERATED`: Created by AI, awaiting validation
- `VALIDATED`: Passed syntax/AST/execution checks
- `ACTIVE`: In pool (max 300), passed backtest + shuffle + multi-window
- `LIVE`: Currently trading live on subaccount
- `RETIRED`: Removed from live trading
- `FAILED`: Failed at any stage (validation, backtest, or tests)

### Strategy Sources and generation_mode

Strategy sources are configured in `config.yaml` under `generation.strategy_sources`.
The `generation_mode` field in the database tracks where each strategy came from.

**Config sources map 1:1 to generation_mode values:**

| Config (strategy_sources) | generation_mode | Abbrev | Class Name | Description |
|---------------------------|-----------------|--------|------------|-------------|
| `pattern` | `pattern` | pat | `PatStrat_*` | From pattern-discovery API |
| `pattern_gen` | `pattern_gen` | pgn | `PGnStrat_*` | Smart random composition |
| `pattern_gen` (genetic) | `pattern_gen_genetic` | pgg | `PGgStrat_*` | Genetic evolution from pool |
| `unger` | `unger` | ung | `UngStrat_*` | Regime-coherent (Unger method) |
| `unger` (genetic) | `unger_genetic` | ugg | `UggStrat_*` | Genetic evolution from pool |
| `pandas_ta` | `pandas_ta` | pta | `PtaStrat_*` | Pandas-TA indicator combinations |
| `ai_free` | `ai_free` | aif | `AIFStrat_*` | AI freely chooses indicators |
| `ai_assigned` | `ai_assigned` | aia | `AIAStrat_*` | AI uses IndicatorCombinator-assigned indicators |

**Config example:**
```yaml
generation:
  strategy_sources:
    pattern:
      enabled: true            # PatStrat_* from pattern-discovery API
    ai_free:
      enabled: true            # AIFStrat_* - AI chooses indicators freely
    ai_assigned:
      enabled: true            # AIAStrat_* - AI uses IndicatorCombinator

  # When both AI sources enabled, ratio controls the mix
  ai_free_ratio: 0.7           # 70% ai_free, 30% ai_assigned
```

**Flow by source:**

All sources follow the same pipeline:
`Generator → Validator → Backtester (parametric optimization) → Pool`

The backtester applies optimized parameters (SL, TP, leverage, exit_bars) to the strategy, but the `generation_mode` remains unchanged throughout the pipeline.

**Validation caching:**
- **Shuffle test**: Cached by `base_code_hash` (lookahead = property of base code)
- **Multi-window**: NOT cached (consistency = property of parameters, each strategy tested independently)

---

## 🚀 SCALABILITY (Future Plans)

**Current implementation**: Sync execution with `ThreadPoolExecutor` for parallel backtesting.

**Future scalability tiers** (not yet implemented):

| Strategies | Mode | Status |
|-----------|------|--------|
| **1-100** | Sync + ThreadPool | ✅ Current |
| **100-500** | Async + ProcessPool | 🔮 Planned |
| **500+** | Hybrid (multi-process + async) | 🔮 Planned |
| **1000+** | Distributed (Redis + multiple servers) | 🔮 Planned |

**Note**: The architecture is designed to scale, but advanced execution modes will be implemented when needed.

---

## 💰 RISK MANAGEMENT (Fixed Fractional Position Sizing)

### Position Sizing Formula

SixBTC uses **Fixed Fractional** position sizing with **margin tracking**.

```python
# Risk-based position sizing
risk_amount = equity * risk_pct      # How much to risk in USD
notional = risk_amount / sl_pct      # Position size needed for that risk
margin_needed = notional / leverage  # Margin required

# Margin check (simulate exchange)
if margin_needed > (equity - margin_used):
    skip_trade()  # Insufficient margin

# Minimum notional check (Hyperliquid requirement)
if notional < min_notional:  # 10 USDC
    skip_trade()
```

**Example**:
```
Account: $10,000
Risk: 2% = $200
SL: 2%
Leverage: 3x

notional = $200 / 2% = $10,000
margin_needed = $10,000 / 3 = $3,333

If SL hit: Loss = $10,000 x 2% = $200 = 2% of account ✓
```

### Why Margin Tracking Matters

Without tracking, the backtest can "use" more margin than available:

```
❌ WITHOUT tracking (bug):
Trade 1: uses $10,000 margin (100%)
Trade 2: uses $10,000 margin (100%)
Total: $20,000 margin with $10,000 equity = IMPOSSIBLE

✅ WITH tracking (correct):
Trade 1: uses $3,333 margin → margin_used = $3,333
Trade 2: available = $10,000 - $3,333 = $6,667
         needs $3,333 → OK, margin_used = $6,666
Trade 3: available = $3,334, needs $3,333 → OK
Trade 4: available = $1, needs $3,333 → REJECTED (like exchange would)
```

---

### Risk Management Config

```yaml
# config/config.yaml
risk:
  fixed_fractional:
    risk_per_trade_pct: 0.02       # 2% risk per trade
    max_position_size_pct: 0.20   # Max 20% of equity per position

  limits:
    max_open_positions_per_subaccount: 10

  emergency:
    max_portfolio_drawdown: 0.30  # 30% total DD
    max_daily_loss: 0.10          # 10% daily DD
    max_subaccount_drawdown: 0.25 # 25% subaccount DD
    max_consecutive_losses: 5

hyperliquid:
  min_notional: 10.0  # Minimum trade size in USDC
```

---

## 🔧 DEVELOPMENT WORKFLOW

### 1. Setup Phase
```bash
# Activate environment
source /home/bitwolf/sixbtc/.venv/bin/activate

# Verify configuration loads without errors
python -c "from src.config import load_config; load_config()"

# Test database connection
python -c "from src.database.connection import get_engine; get_engine().connect()"

# Test Hyperliquid API (requires valid credentials)
python -c "from src.executor.hyperliquid_client import HyperliquidClient; HyperliquidClient()"
```

### 2. Process Management with Supervisor

**CRITICAL RULES:**
1. **Always use `supervisorctl` (without sudo)** to manage sixbtc services
2. **Never start processes manually** with `python -m ...` - this duplicates processes
3. **Never use `pkill` or `kill`** to stop services - use supervisorctl
4. **Check for zombie processes** before and after operations

```bash
# Check status of all services
supervisorctl status

# Start/stop/restart individual services
supervisorctl start sixbtc:api
supervisorctl stop sixbtc:executor
supervisorctl restart sixbtc:backtester

# Restart all sixbtc services
supervisorctl restart sixbtc:*

# Check for zombie processes (should return nothing)
ps aux | grep -E "(zombie|defunct|\<Z\>)" | grep -v grep

# If zombies exist, investigate and clean up parent process
```

**Available sixbtc services:**
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

### 3. CLI (Scaffold - Limited Functionality)
```bash
# Basic status check
python main.py status

# Note: Most functionality is in the daemon processes, not CLI
```

### 4. Testing Requirements
**MANDATORY**: After ANY modification, run:
```bash
pytest tests/ -v
# MUST show: ALL TESTS PASSED
```

**No proof = Not done**

---

## 📊 MULTI-TIMEFRAME COVERAGE

### Requirement
Strategies must be generated and tested across ALL configured timeframes:
- **15m** - Short-term momentum
- **30m** - Intraday swings
- **1h** - Short-term trends
- **2h** - Medium-term swing trades

### Implementation
```python
# Strategy generation distributes across timeframes (from config)
TIMEFRAMES = ['15m', '30m', '1h', '2h']

# Each generation cycle creates strategies for ALL timeframes
for tf in TIMEFRAMES:
    strategies = generate_strategies(
        count=8,  # 8 strategies per TF
        timeframe=tf,
        patterns=fetch_patterns(timeframe=tf)
    )
```

### Backtesting
```python
# Each strategy backtested on its target timeframe
backtest_results = backtest_strategy(
    strategy=strategy,
    timeframe=strategy.timeframe,  # Match generation TF
    data=load_data(timeframe=strategy.timeframe)
)
```

### Portfolio Diversification
```python
# Top 10 selection ensures timeframe diversity
selected = select_top_10(
    strategies=all_tested,
    max_per_timeframe=3,  # Max 3 strategies on same TF
    max_same_type=2       # Max 2 MOM strategies, etc.
)
```

---

## 🧪 TESTING PHASE PLAN

### Initial Testing Parameters
- **Capital**: $100 per subaccount × 3 subaccounts = **$300 total**
- **Duration**: 1-2 weeks minimum
- **Subaccounts**: 1, 2, 3 (out of 10 available)
- **Strategies**: Top 3 performing strategies from backtests

### Success Criteria (Testing Phase)
- **Win Rate**: ≥50% (lower threshold for small sample)
- **Max Drawdown**: <25% per subaccount
- **No Emergency Stops**: System must handle gracefully
- **Execution Quality**: Slippage <0.1%, fills >95%
- **No Critical Bugs**: System must run 24/7 without crashes

### Graduation to Full Deployment
After testing phase passes:
- Scale to 10 subaccounts
- Increase capital per subaccount
- Enable full strategy rotation (daily)
- Activate all monitoring and emergency systems

---

## 🚨 COMMON PITFALLS TO AVOID

### 1. Overfitting in Backtests
❌ **Wrong**: Optimize 20 parameters to maximize backtest Sharpe
✅ **Right**: Optimize 3-4 critical parameters, validate with shuffle test

### 2. Ignoring Execution Costs
❌ **Wrong**: Backtest without fees/slippage
✅ **Right**: Include 0.04% fee + 0.02% slippage in all backtests

### 3. Lookahead Bias
❌ **Wrong**: Trust backtest results blindly
✅ **Right**: Run AST checker + shuffle test + walk-forward validation

### 4. Deployment Without Paper Trading
❌ **Wrong**: Deploy directly to live after backtest
✅ **Right**: Test phase with $100 subaccounts first

### 5. Lack of Diversification
❌ **Wrong**: Deploy 10 momentum strategies in trending market
✅ **Right**: Mix types (MOM, REV, TRN) and timeframes (15m to 2h)

---

## 📚 EXTERNAL REFERENCES

### Key Dependencies
- **Numba**: https://numba.pydata.org/ (JIT compilation for fast backtesting)
- **Hyperliquid SDK**: https://github.com/hyperliquid-dex/hyperliquid-python-sdk
- **Pattern Discovery**: Internal API at `http://localhost:8001`
- **Binance CCXT**: https://docs.ccxt.com/

### Related Projects
- **fivebtc**: Strategy generator with Freqtrade (reference for AI system)
- **sevenbtc**: Live trading bot with Claude AI (reference for Hyperliquid integration)
- **pattern-discovery**: Trading pattern validator (data source)

---

## 📊 PATTERN-DISCOVERY API - ATR STATISTICS

### Overview

Pattern-discovery now provides **ATR statistics** for each pattern, calculated during walk-forward validation. These statistics describe the volatility conditions when the pattern historically fired signals.

### New Fields in PatternResponse

```python
# From pattern-discovery API: GET /api/v1/patterns
{
    "name": "return_24h_gt_pos6",
    "tier": 1,
    "test_edge": 0.045,
    # ... existing fields ...

    # NEW: ATR statistics (price-normalized, e.g., 0.03 = 3% of price)
    "atr_signal_median": 0.0113,  # Median ATR when pattern signals fire
    "atr_signal_std": 0.0081,     # Std dev of ATR at signals
    "atr_signal_min": 0.0014,     # Min ATR observed at signals
    "atr_signal_max": 0.3884,     # Max ATR observed at signals
}
```

### What ATR Statistics Mean

- **atr_signal_median**: The typical volatility when this pattern fires. If a pattern has `atr_signal_median = 0.02` (2%), it means historically the pattern triggered when ATR was around 2% of price.

- **atr_signal_std**: How variable the volatility conditions are. High std = pattern fires in both calm and volatile markets. Low std = pattern is specific to certain volatility regimes.

- **atr_signal_min/max**: The range of volatility where the pattern has been observed to work.

### Usage in SixBTC - Volatility Quality Filter

Use ATR statistics to skip signals in abnormally low volatility (where edge may not exist):

```python
# In direct_generator template or strategy code
def generate_signal(self, df: pd.DataFrame) -> Signal | None:
    entry_condition = self._check_entry(df)

    if entry_condition:
        # Calculate current ATR (price-normalized)
        atr = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        atr_normalized = atr / df['close']
        current_atr = atr_normalized.iloc[-1]

        # Skip if current ATR < 50% of pattern's historical median
        # Pattern was validated on data with higher volatility
        atr_threshold = {atr_signal_median} * 0.5

        if current_atr < atr_threshold:
            return None  # Low volatility - skip signal

        return Signal(...)
```

### Why This Matters

1. **Empirical vs Arbitrary**: Instead of hardcoding `atr_threshold = 1.0`, use the pattern's actual historical volatility profile.

2. **Pattern-Specific**: A momentum pattern might need high volatility (`atr_signal_median = 0.03`), while a mean-reversion pattern might work in calmer markets (`atr_signal_median = 0.01`).

3. **Quality Filter**: If current market is much calmer than when the pattern was validated, the edge may not exist.

### Recommended Thresholds

| Scenario | Threshold | Use Case |
|----------|-----------|----------|
| Conservative | `atr_signal_median * 0.7` | Skip only extreme low volatility |
| Standard | `atr_signal_median * 0.5` | Skip when ATR is half the norm |
| Aggressive | `atr_signal_median * 0.3` | Only skip very dead markets |

### API Endpoint

```bash
# Get patterns with ATR statistics
curl "http://localhost:8001/api/v1/patterns?tier=1"

# Response includes atr_signal_* fields for all patterns
```

### ATR-Based Stop Loss for Close-Based Patterns

For `close_based` patterns (time-based exit), the SL is calculated using ATR instead of target magnitude:

```python
# In parametric_backtest.py build_execution_type_space():
if execution_type == 'close_based':
    if atr_signal_median:
        # ATR-based SL: volatility-aware protection
        sl_values = [atr_signal_median * mult for mult in [2.0, 3.0, 4.0, 5.0]]
    else:
        # Fallback: wider magnitude-based (less accurate)
        sl_values = [base_magnitude * mult for mult in [4.0, 6.0, 8.0, 10.0]]
```

**Why ATR-based SL?**
- Pattern-discovery validates close_based patterns with no SL (only time exit)
- Real trading needs SL for risk management
- Using magnitude-based SL can be too tight or too loose
- ATR reflects actual volatility when pattern fired → appropriate SL level

**Example:**
- Pattern `return_24h_gt_pos6`: magnitude=3%, atr_signal_median=1.13%
- Old SL (magnitude×2-5): [6%, 9%, 12%, 15%]
- New SL (ATR×2-5): [2.3%, 3.4%, 4.5%, 5.6%]
- The new values are tighter but more aligned with actual volatility

---

## ✅ GOLDEN CHECKLIST

Before pushing ANY code:
- [ ] All code and comments in English
- [ ] No hardcoded values (everything in config.yaml)
- [ ] Type hints on all functions
- [ ] No files >400 lines
- [ ] No backup files (_old.py, etc.)
- [ ] Tests pass: `pytest tests/ -v`
- [ ] No lookahead bias (AST check + shuffle test)
- [ ] Strategies inherit from StrategyCore
- [ ] Database operations use SQLAlchemy models
- [ ] Logging uses ASCII only (no emojis)
- [ ] **docs/PIPELINE_*.md updated** if code/config changes affect pipeline behavior

---

**Remember**: The system's purpose is to make money. Every decision should optimize for profitability, risk management, and system reliability—in that order.
