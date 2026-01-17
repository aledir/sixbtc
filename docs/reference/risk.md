# SixBTC Risk Management

This document explains the risk management system used in SixBTC, including position sizing, margin tracking, and the diversification cap.

---

## Overview

SixBTC uses **Fixed Fractional Position Sizing** with three key mechanisms:

1. **Max Open Positions**: Hard limit of 10 concurrent positions per subaccount
2. **Dynamic Cap (Diversification)**: Limits each trade to max 10% of equity as margin
3. **Margin Tracking**: Ensures total margin never exceeds available equity

These mechanisms work together to:
- Guarantee diversification (max 10 positions)
- Prevent over-leverage
- Keep risk per trade controlled

---

## Core Formula

The position sizing follows this logic:

```
risk_amount = equity * risk_pct           # How much $ to risk (2% of equity)
notional = risk_amount / sl_pct           # Position size needed for that risk
margin = notional / leverage              # Margin required

# Apply diversification cap
max_margin = equity / max_positions       # 10% with max_positions=10
if margin > max_margin:
    margin = max_margin                   # CAP applied
    notional = margin * leverage          # Reduce notional accordingly
```

---

## The Three Equivalent Implementations

The same logic is implemented in 3 places, written differently due to technical constraints (Numba, vectorization, etc.):

### 1. Parametric Kernel (Numba)

Location: `src/backtester/parametric_backtest.py` lines 379-402

```python
# Step 1: Calculate target notional based on risk
risk_amount = equity * risk_pct
notional = risk_amount / sl_pct

# Step 2: Calculate margin
margin_needed = notional / leverage

# Step 3: Apply diversification cap
max_margin_per_trade = equity / max_positions
if margin_needed > max_margin_per_trade:
    margin_needed = max_margin_per_trade
    notional = margin_needed * leverage  # Reduce notional

# Step 4: Check margin available
if margin_needed > (equity - margin_used):
    continue  # Skip trade - insufficient margin
```

### 2. Backtest Engine (Vectorized NumPy)

Location: `src/backtester/backtest_engine.py` lines 1524-1600

```python
# Cap as fraction of equity
dynamic_cap = 1.0 / max_positions  # = 0.10 (10%)

# Position size (fraction of equity as margin)
position_size = min(
    risk_pct / (sl_pct * leverage),  # Risk-based calculation
    dynamic_cap                       # Diversification cap
)
```

### 3. Live Executor

Location: `src/executor/main_continuous.py` lines 512-527

```python
# Calculate margin needed
notional = size * current_price
margin_needed = notional / actual_leverage

# Dynamic cap: each trade uses at most 1/max_positions of equity
max_margin = account_balance / max_positions

if margin_needed > max_margin:
    # Cap size to respect diversification
    max_notional = max_margin * actual_leverage
    size = max_notional / current_price  # Reduce BEFORE sending to exchange
```

**Note**: The live executor caps the size BEFORE sending to Hyperliquid, not after rejection. This avoids wasted API calls and rate limit consumption.

---

## Why All Three Mechanisms Are Needed

### Max Open Positions (Hard Limit)

**Purpose**: Absolute limit on concurrent positions, regardless of margin availability.

```yaml
# config/config.yaml
risk:
  limits:
    max_open_positions_per_subaccount: 10
```

This is checked BEFORE any sizing calculation:

```python
# In executor and backtest
if current_open_positions >= max_positions:
    skip_signal()  # Don't even calculate size
```

**Why it's needed**: Even if margin cap allows 10 positions and you have margin for 10, this config lets you explicitly control the maximum. You could set it to 5 for more conservative trading.

**Interaction with other mechanisms**:
- If `max_open_positions = 10` and `dynamic_cap = 10%`, both allow max 10 positions
- If `max_open_positions = 5` and `dynamic_cap = 10%`, you're limited to 5 (hard limit wins)
- If `max_open_positions = 20` and `dynamic_cap = 10%`, you're limited to 10 (margin cap wins)

**Worst Case Example 1: Low Leverage (1x) - CAP APPLIED**

This is unlikely but not impossible (e.g., flash crash, black swan event).

```
Configuration:
  Equity: $10,000
  max_open_positions: 10
  risk_per_trade: 2%
  SL: 3%
  Leverage: 1x

Per-trade calculation:
  risk_amount = $10,000 * 0.02 = $200
  notional = $200 / 0.03 = $6,667
  margin = $6,667 / 1 = $6,667 (66.7%)
  max_margin = $10,000 / 10 = $1,000 (10%)

  CAP APPLIED: margin = $1,000, notional = $1,000
  actual_risk = $1,000 * 0.03 = $30 (0.3%)

With 10 positions open:
  Total margin used: 10 × $1,000 = $10,000 (100%)
  Risk per position: $30 (0.3%)

  IF ALL 10 HIT SL SIMULTANEOUSLY:
  Total loss = 10 × $30 = $300 (3% of equity)
```

**Worst Case Example 2: High Leverage (10x)**

Same scenario but with 10x leverage (all strategies use high leverage):

```
Configuration:
  Equity: $10,000
  max_open_positions: 10
  risk_per_trade: 2%
  SL: 3%
  Leverage: 10x

Per-trade calculation:
  risk_amount = $10,000 * 0.02 = $200
  notional = $200 / 0.03 = $6,667
  margin = $6,667 / 10 = $666.7 (6.67%)
  max_margin = $10,000 / 10 = $1,000 (10%)

  $666.7 < $1,000 → NO CAP APPLIED!
  actual_risk = $6,667 * 0.03 = $200 (2% - FULL TARGET RISK)

With 10 positions open:
  Total margin used: 10 × $666.7 = $6,667 (66.7%)
  Risk per position: $200 (2%)

  IF ALL 10 HIT SL SIMULTANEOUSLY:
  Total loss = 10 × $200 = $2,000 (20% of equity)
```

**Key insight**: With high leverage (10x), the margin per trade ($666.7) is below the cap ($1,000), so the full 2% risk per trade is achieved. This is the TRUE worst case scenario.

**Summary of worst case by strategy parameters**:

| SL | Leverage | Risk/Trade | 10 Positions All SL |
|----|----------|------------|---------------------|
| 3% | 1x | 0.3% (capped) | **3%** |
| 4% | 5x | 2.0% | **20%** |
| 5% | 10x | 2.0% | **20%** |
| 1% | 10x | 1.0% (capped) | **10%** |

The emergency stop at 30% portfolio drawdown provides a safety net even in this scenario.

### Dynamic Cap (Diversification)

**Purpose**: Force diversification by limiting each trade to max 10% margin.

Without dynamic cap:
```
Trade 1: margin 50% → OK (50% used)
Trade 2: margin 50% → OK (100% used)
Trade 3: margin 50% → REJECTED
Result: Only 2 positions, highly concentrated
```

With dynamic cap:
```
Trade 1: wants 50%, capped to 10% → OK (10% used)
Trade 2: wants 50%, capped to 10% → OK (20% used)
...
Trade 10: capped to 10% → OK (100% used)
Trade 11: → REJECTED (no margin)
Result: 10 positions, well diversified
```

### Margin Tracking

**Purpose**: Prevent total margin from exceeding available equity (simulates exchange behavior).

```
equity = $10,000
margin_used = $0

Trade 1: needs $1,000 margin
  → available = $10,000 - $0 = $10,000
  → $1,000 < $10,000 → OK
  → margin_used = $1,000

Trade 2: needs $1,000 margin
  → available = $10,000 - $1,000 = $9,000
  → $1,000 < $9,000 → OK
  → margin_used = $2,000

... (continue until margin_used approaches $10,000)

Trade 11: needs $1,000 margin
  → available = $10,000 - $10,000 = $0
  → $1,000 > $0 → REJECTED
```

---

## Numerical Examples

### Configuration

```yaml
risk:
  fixed_fractional:
    risk_per_trade_pct: 0.02    # 2% target risk per trade
  limits:
    max_open_positions_per_subaccount: 10
```

### Example 1: Wide SL, High Leverage (No Cap)

```
Equity: $10,000
SL: 5%
Leverage: 10x

Calculation:
  risk_amount = $10,000 * 0.02 = $200
  notional = $200 / 0.05 = $4,000
  margin = $4,000 / 10 = $400 (4% of equity)
  max_margin = $10,000 / 10 = $1,000 (10%)

  $400 < $1,000 → NO CAP APPLIED

Result:
  - Margin per trade: $400 (4%)
  - Risk per trade: $200 (2%) ← Full target risk
  - Max positions: 25 by margin, capped to 10 by config
  - Worst case (10 positions all hit SL): -20%
```

### Example 2: Tight SL, Low Leverage (Cap Applied)

```
Equity: $10,000
SL: 3%
Leverage: 1x

Calculation:
  risk_amount = $10,000 * 0.02 = $200
  notional = $200 / 0.03 = $6,667
  margin = $6,667 / 1 = $6,667 (66.7% of equity)
  max_margin = $10,000 / 10 = $1,000 (10%)

  $6,667 > $1,000 → CAP APPLIED!

  margin_capped = $1,000
  notional_capped = $1,000 * 1 = $1,000
  actual_risk = $1,000 * 0.03 = $30 (0.3% of equity)

Result:
  - Margin per trade: $1,000 (10%) ← Capped
  - Risk per trade: $30 (0.3%) ← Reduced from 2% target
  - Max positions: 10
  - Worst case (10 positions all hit SL): -3%
```

### Example 3: Medium Parameters

```
Equity: $10,000
SL: 4%
Leverage: 5x

Calculation:
  risk_amount = $10,000 * 0.02 = $200
  notional = $200 / 0.04 = $5,000
  margin = $5,000 / 5 = $1,000 (10% of equity)
  max_margin = $10,000 / 10 = $1,000 (10%)

  $1,000 = $1,000 → AT THE LIMIT (no reduction needed)

Result:
  - Margin per trade: $1,000 (10%)
  - Risk per trade: $200 (2%) ← Full target risk
  - Max positions: 10
  - Worst case (10 positions all hit SL): -20%
```

---

## Risk Per Trade Summary

| SL | Leverage | Margin/Trade | Cap Applied? | Effective Risk | Worst Case (10 pos) |
|----|----------|--------------|--------------|----------------|---------------------|
| 5% | 10x | 4% | No | 2.0% | 20% |
| 4% | 5x | 10% | At limit | 2.0% | 20% |
| 3% | 1x | 66.7% | **Yes** | 0.3% | 3% |
| 2% | 10x | 10% | At limit | 2.0% | 20% |
| 1% | 10x | 20% | **Yes** | 1.0% | 10% |
| 0.5% | 20x | 20% | **Yes** | 0.5% | 5% |

**Key insight**: The 2% risk_per_trade_pct is a TARGET, not a guarantee. The diversification cap often reduces effective risk below 2%.

---

## Real-World Data

Analysis of strategies in the ACTIVE pool shows:

| Strategy | Trades | Win Rate | Max DD | Implied Risk/Trade |
|----------|--------|----------|--------|-------------------|
| PtaStrat_VOL | 100 | 53% | 5.8% | ~0.6% |
| PGnStrat_FRC | 212 | 58% | 9.7% | ~1.0% |
| PGgStrat_VWP | 193 | 50% | 5.3% | ~0.5% |
| PGgStrat_VWM | 317 | 41% | 5.4% | ~0.5% |
| PtaStrat_VLM | 226 | 77% | 2.8% | ~0.3% |

The low max drawdowns confirm that the diversification cap is working effectively.

---

## Strategy Rotation (ACTIVE ↔ LIVE)

Strategy rotation is a critical risk management mechanism. It controls which strategies trade live and removes underperforming ones.

---

### Entry to LIVE (Rotator)

The rotator deploys strategies from ACTIVE pool to LIVE subaccounts.

**Prerequisites:**
```yaml
rotator:
  min_pool_size: 100           # Don't deploy until pool has 100+ strategies
  max_live_strategies: 10      # Max strategies trading live simultaneously
```

**Entry Criteria:**
- Strategy must be in ACTIVE pool (passed all validation + backtest + shuffle + multi-window)
- Score >= `active_pool.min_score` (currently 50)
- Subaccount available (not already occupied)

**Diversification Constraints:**
```yaml
selection:
  max_per_type: 3              # Max 3 MOM strategies, max 3 REV, etc.
  max_per_timeframe: 3         # Max 3 on 15m, max 3 on 1h, etc.
  max_per_direction: 5         # Max 5 LONG-only, max 5 SHORT-only
```

**Progressive Relaxation:**
If strict constraints can't fill all slots, the rotator progressively relaxes:
1. Round 1: All constraints (type + timeframe + direction)
2. Round 2: Relax direction (allows more same-direction strategies)
3. Round 3: Relax timeframe (allows more same-timeframe strategies)
4. Round 4: Relax all (pure score ranking)

This ensures slots get filled while preferring diversity.

---

### Exit from LIVE (Retirement Policy)

The monitor evaluates LIVE strategies and retires underperformers.

**Evaluation Frequency:**
```yaml
monitor:
  check_interval_minutes: 15   # Check every 15 minutes
```

**Retirement Triggers (any one triggers retirement):**

| Criterion | Threshold | Purpose |
|-----------|-----------|---------|
| Live score below minimum | `< 35` | Strategy no longer profitable |
| Score degradation | `> 40%` vs backtest | Edge has decayed significantly |
| Live drawdown | `> 25%` | Excessive losses (regime change) |
| Consecutive losses | `>= 10` | Regime change indicator |
| Trade frequency degradation | `> 50%` fewer than backtest | Strategy stopped firing signals |

**Minimum Trades Before Evaluation:**
```yaml
retirement:
  min_trades: 10               # Need 10 trades before evaluating
```

This prevents premature retirement due to small sample size.

---

### Retirement Criteria Explained

**1. Live Score Below Minimum (`min_score: 35`)**

If `score_live < 35`, the strategy is underperforming.
- The entry threshold is 50 (to enter ACTIVE pool)
- The retirement threshold is 35 (hysteresis to avoid flip-flopping)
- Gap of 15 points allows temporary underperformance without immediate retirement

**2. Score Degradation (`max_score_degradation: 0.40`)**

Formula: `degradation = (score_backtest - score_live) / score_backtest`

Example:
```
Backtest score: 65
Live score: 35
Degradation = (65 - 35) / 65 = 46% > 40% → RETIRE
```

This catches strategies where the edge has decayed even if absolute score is OK.

**3. Live Drawdown (`max_drawdown: 0.25`)**

Maximum acceptable loss from peak equity during live trading.
- With $100 per subaccount, max loss = $25
- Calculated from actual live trades, not backtest

**4. Consecutive Losses (`max_consecutive_losses: 10`)**

Tracks the current losing streak (most recent trades).
- 10+ consecutive losses suggests market regime has changed
- Strategy may no longer be suited to current conditions
- Early warning system before drawdown becomes severe

**5. Trade Frequency Degradation (`max_trades_degradation: 0.50`)**

Formula: `degradation = (expected_trades - actual_trades) / expected_trades`

Example:
```
Backtest: 100 trades in 150 days = 0.67 trades/day
Live: 7 days, expected = 4.67 trades, actual = 2 trades
Degradation = (4.67 - 2) / 4.67 = 57% > 50% → RETIRE
```

Requires minimum 7 days live for meaningful comparison.

This catches strategies that stopped generating signals (indicator failure, market change).

---

### Rotation Flow Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    ACTIVE POOL (max 300)                    │
│  Strategies that passed: validation + backtest + shuffle +  │
│  multi-window + score >= 50                                 │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼ Rotator (every 15 min)
                     ┌───────────────┐
                     │ Score >= 50?  │
                     │ Slot free?    │
                     │ Diversified?  │
                     └───────┬───────┘
                             │ YES
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      LIVE (max 10)                          │
│  Actually trading on Hyperliquid subaccounts                │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼ Monitor (every 15 min)
                     ┌───────────────┐
                     │ Score < 35?   │
                     │ DD > 25%?     │
                     │ 10+ losses?   │
                     │ Degraded 40%? │
                     │ Signals -50%? │
                     └───────┬───────┘
                             │ ANY YES
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                        RETIRED                              │
│  No longer trading, archived for analysis                   │
└─────────────────────────────────────────────────────────────┘
```

---

### Configuration Reference

```yaml
# config/config.yaml

rotator:
  check_interval_minutes: 15     # Deploy check frequency
  max_live_strategies: 10        # Max concurrent LIVE
  min_pool_size: 100             # Min ACTIVE before deploying

  selection:
    max_per_type: 3              # Diversification by strategy type
    max_per_timeframe: 3         # Diversification by timeframe
    max_per_direction: 5         # Diversification by direction

monitor:
  check_interval_minutes: 15     # Retirement check frequency

  retirement:
    min_score: 35                # Score floor for LIVE
    max_score_degradation: 0.40  # Max decay vs backtest
    max_drawdown: 0.25           # Max live DD
    min_trades: 10               # Min trades before eval
    max_consecutive_losses: 10   # Losing streak limit
    max_trades_degradation: 0.50 # Signal frequency decay
```

---

## Emergency Stop System

SixBTC implements a **multi-scope emergency stop system** with differentiated actions and auto-reset logic. The system is designed to protect capital at multiple levels while allowing automated recovery when conditions improve.

---

### Scope Hierarchy

Emergency stops operate at four scopes, from broadest to narrowest:

```
PORTFOLIO > SUBACCOUNT > STRATEGY > SYSTEM
```

Each scope has specific thresholds, actions, and recovery conditions.

---

### Emergency Stop Table

| Scope | Condition | Threshold | Action | Auto-Reset |
|-------|-----------|-----------|--------|------------|
| **PORTFOLIO** | Daily Loss | >= 10% | `halt_entries` | Midnight UTC |
| **PORTFOLIO** | Drawdown | >= 20% | `force_close` | 48h + rotation of losing strategies |
| **SUBACCOUNT** | Drawdown | >= 25% | `halt_entries` | After rotation (new strategy deployed) |
| **STRATEGY** | Consecutive Losses | >= 10 | `halt_entries` | 24h cooldown |
| **SYSTEM** | Data Stale | > 2 min | `halt_entries` | When data becomes valid |

---

### Actions Explained

#### `halt_entries` - Block New Trades
- **What it does**: Prevents opening new positions
- **Existing positions**: Continue running to SL/TP (not closed)
- **Purpose**: Stop the bleeding without panic-closing profitable positions

```
Scenario: Portfolio daily loss hits 10%
Action: halt_entries
Result:
  - New signals are ignored
  - Open positions continue to their exit (SL/TP)
  - At midnight UTC, trading resumes automatically
```

#### `force_close` - Emergency Close All Positions
- **What it does**: Immediately closes ALL open positions across ALL subaccounts
- **When used**: Only for portfolio-level drawdown (20%)
- **Purpose**: Panic button - cut all losses immediately

```
Scenario: Portfolio drawdown hits 20%
Action: force_close
Result:
  - ALL positions closed immediately at market
  - All subaccounts marked as STOPPED
  - Trading pauses for 48h minimum
  - After 48h, losing strategies must be rotated before resuming
```

---

### Auto-Reset Conditions

Each emergency stop has specific reset conditions:

#### 1. Daily Loss (10%) - Reset at Midnight UTC
```
Triggered: 14:30 UTC, daily loss 10.5%
Cooldown: Until 00:00 UTC next day
Action: halt_entries
At 00:00 UTC: Automatically reset, daily PnL counter reset to $0
```

#### 2. Portfolio Drawdown (20%) - Reset after 48h + Rotation
```
Triggered: Portfolio DD 22%
Cooldown: 48 hours from trigger
Condition: All strategies with loss >= rotation_loss_threshold must be rotated
Recovery:
  1. Wait 48h (mandatory cooling off)
  2. Rotator deploys new strategies to replace losers
  3. Once all losing strategies rotated, stop is cleared
  4. Trading resumes with fresh strategies
```

#### 3. Subaccount Drawdown (25%) - Reset on Rotation
```
Triggered: Subaccount 3 DD 27%
Action: halt_entries (only subaccount 3)
Other subaccounts: Continue trading normally
Recovery: When rotator deploys new strategy to subaccount 3
```

#### 4. Consecutive Losses (10) - Reset after 24h
```
Triggered: Strategy XYZ has 10 consecutive losses
Action: halt_entries (only strategy XYZ)
Cooldown: 24 hours
After 24h: Strategy can trade again
```

#### 5. Data Stale (2min) - Reset when Data Valid
```
Triggered: Balance data not updated for 3 minutes
Action: halt_entries (all trading paused)
Recovery: Immediately when data feed resumes
No cooldown - instant recovery
```

---

### Balance Tracking

The emergency stop system tracks balances for accurate drawdown calculation.

#### Automatic Balance Sync at Startup

When the executor starts, it automatically syncs `allocated_capital` from Hyperliquid:

```python
# At executor startup (src/executor/main_continuous.py)
balance_sync = BalanceSyncService(config, client)
synced = balance_sync.sync_all_subaccounts()
```

**Sync Logic:**
- If `allocated_capital` is 0 or NULL → set to actual Hyperliquid balance
- If `allocated_capital` is already set → keep existing value (respect rotator allocations)
- `current_balance` and `peak_balance` are always updated from Hyperliquid

**Why this matters:**
- No manual setup required for manually funded subaccounts
- Works for both test phase (manual funding) and production (rotator deployment)
- Ensures emergency stop calculations have correct baseline

```
Example: Test Phase Setup
1. User transfers $100 to each of 3 subaccounts on Hyperliquid
2. User starts executor
3. Balance sync runs: allocated_capital = $100 for each
4. Emergency stops work correctly (10% daily loss = $30 total)
```

#### Peak Balance (High Water Mark)
- **Definition**: Highest realized balance ever achieved
- **Updates**: Only when `current_balance > peak_balance`
- **Never decreases**: Maintains true high water mark

```python
# Drawdown calculation
drawdown = (peak_balance - current_balance) / peak_balance

# Example:
peak_balance = $10,000
current_balance = $8,500
drawdown = ($10,000 - $8,500) / $10,000 = 15%
```

#### Daily PnL Tracking
- **Resets**: At midnight UTC
- **Tracks**: Sum of realized PnL for current day
- **Used for**: Daily loss threshold (10%)

```python
# Daily loss calculation (PORTFOLIO-WIDE)
total_capital = sum(allocated_capital for all active subaccounts)
total_daily_pnl = sum(daily_pnl_usd for all active subaccounts)
daily_loss = -total_daily_pnl / total_capital  # (if negative)

# Example with 3 subaccounts @ $100 each:
total_capital = $300
total_daily_pnl = -$36  # Combined losses
daily_loss = 36/300 = 12% >= 10% threshold → halt_entries
```

**Important**: Daily loss is calculated at PORTFOLIO level, not per-subaccount. A $12 loss on one subaccount with $100 is only 4% portfolio loss (12/300), not 12%.

---

### State Persistence

Emergency stop states are persisted in the database:

```sql
-- EmergencyStopState table
scope: 'portfolio' | 'subaccount' | 'strategy' | 'system'
scope_id: 'global' | '1-10' | UUID | 'data_feed'
is_stopped: boolean
stop_reason: 'Daily loss 10.5% >= 10%'
stop_action: 'halt_entries' | 'force_close'
stopped_at: timestamp
cooldown_until: timestamp
reset_trigger: 'midnight_utc' | 'cooldown_48h_rotation' | 'rotation' | '24h' | 'data_valid'
```

**Benefits of persistence:**
- Survives process restarts
- Prevents bypass via restart
- Audit trail of all emergency events
- Consistent state across executor/rotator processes

---

### Throttling

Emergency condition checks are throttled to reduce database load:

- **Check interval**: Every 60 seconds
- **Scope**: All condition checks (portfolio DD, daily loss, etc.)
- **Exception**: `can_trade()` checks are real-time (no throttling)

This prevents excessive database queries while maintaining safety.

---

### Integration Points

#### Executor (`src/executor/main_continuous.py`)
```python
# In main loop (throttled)
triggered = emergency_manager.check_all_conditions()
for stop in triggered:
    emergency_manager.trigger_stop(...)
emergency_manager.check_auto_resets()

# Before processing signal
trade_status = emergency_manager.can_trade(subaccount_id, strategy_id)
if not trade_status['allowed']:
    logger.warning(f"Trading blocked: {trade_status['blocked_by']}")
    continue

# After trade close
emergency_manager.update_balances(subaccount_id, current_balance, pnl_delta)
```

#### Rotator (`src/rotator/main_continuous.py`)
```python
# After successful deployment
emergency_manager.reset_on_rotation(subaccount_id)

# After deployment cycle
if deployed_count > 0:
    emergency_manager.reset_portfolio_dd_after_rotation()
```

---

### Configuration Reference

```yaml
# config/config.yaml

risk:
  emergency:
    # Thresholds
    max_portfolio_drawdown: 0.20      # 20% portfolio DD → force_close
    max_daily_loss: 0.10              # 10% daily loss → halt_entries
    max_subaccount_drawdown: 0.25     # 25% subaccount DD → halt_entries
    max_consecutive_losses: 10        # 10 consecutive losses → halt_entries
    data_stale_seconds: 120           # 2 min stale data → halt_entries

    # Recovery conditions
    rotation_loss_threshold: 0.00     # Rotate strategies with loss >= 0%

  emergency_cooldowns:
    portfolio_dd_hours: 48            # 48h cooldown for portfolio DD
    strategy_hours: 24                # 24h cooldown for consecutive losses
```

---

### Scenario Examples

#### Scenario 1: Flash Crash (Daily Loss)
```
Initial State:
  Portfolio: $10,000
  Positions: 10 open

Event: Market drops 5% in 1 hour, all positions hit SL
Result: Daily loss = 10.5%

Emergency Response:
  1. halt_entries triggered at portfolio level
  2. No new positions opened
  3. Remaining positions (if any) run to SL/TP
  4. At midnight UTC: auto-reset, trading resumes
```

#### Scenario 2: Slow Bleed (Portfolio Drawdown)
```
Day 1: -8% (under daily loss threshold)
Day 2: -7% (under daily loss threshold)
Day 3: -5%
Total: Portfolio DD = 20%

Emergency Response:
  1. force_close triggered
  2. ALL positions closed immediately
  3. 48h mandatory cooldown
  4. After 48h: rotator deploys new strategies
  5. Once all losing strategies replaced: trading resumes
```

#### Scenario 3: Bad Strategy (Consecutive Losses)
```
Strategy XYZ: 10 consecutive losing trades

Emergency Response:
  1. halt_entries on strategy XYZ only
  2. Other strategies continue trading normally
  3. After 24h: strategy XYZ can trade again
  4. If losses continue: eventually retired via monitor
```

#### Scenario 4: Data Feed Outage
```
Balance data not updated for 3 minutes

Emergency Response:
  1. halt_entries on system level (all trading)
  2. No new positions anywhere
  3. When data feed resumes: immediate reset
  4. Trading continues normally
```

---

## Summary

### Per-Trade Risk Management
1. **Max positions**: Hard limit of 10 concurrent positions per subaccount
2. **Target risk**: 2% per trade (configurable)
3. **Diversification cap**: 10% margin per trade (derived from 1/max_positions)
4. **Effective risk**: Often 0.3-1% due to cap on strategies with tight SL or low leverage
5. **Worst case**: 3-20% depending on strategy parameters

### Strategy-Level Risk Management
6. **Rotation entry**: Score >= 50, diversified by type/timeframe/direction
7. **Rotation exit**: Score < 35, DD > 25%, 10+ losses, 40% degradation, 50% fewer signals
8. **LIVE diversification**: Max 3 per type, max 3 per timeframe, max 5 per direction

### System-Level Risk Management
9. **Emergency stops**: 20% portfolio DD, 10% daily loss, 25% subaccount DD
10. **Pool requirements**: Min 100 ACTIVE strategies before any deployment

The mechanisms work together across three levels:
- **Trade level**: Position sizing, margin cap, SL/TP
- **Strategy level**: Entry/exit criteria, diversification, retirement triggers
- **System level**: Emergency stops, pool thresholds, cooldowns

The system is designed to be **more conservative than it appears**. Multiple overlapping safeguards ensure that even with aggressive signals, actual risk is controlled at every level.
