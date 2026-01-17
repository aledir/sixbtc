# Balance Management Architecture

This document explains how SixBTC tracks and reconciles subaccount balances.

## Overview

SixBTC uses three key metrics to track capital in each subaccount:

| Field | Purpose | Updated By |
|-------|---------|------------|
| `allocated_capital` | Initial capital allocated to subaccount | Deployer + Reconciliation |
| `current_balance` | Real-time account value from Hyperliquid | BalanceSync + EmergencyManager |
| `peak_balance` | Highest value for drawdown calculation | Deployer + EmergencyManager |

## The Phantom Capital Problem

**Problem**: False drawdown alerts caused by "phantom capital" in database.

**Scenario**:
1. Rotator deploys strategy to subaccount, sets `allocated_capital = $83.33`
2. User never actually transfers funds to Hyperliquid
3. System calculates: `DD = ($83.33 - $0) / $83.33 = 100%`
4. Emergency stop triggers incorrectly

**Solution**: `BalanceReconciliationService` detects phantom capital by checking if deposit events exist for the subaccount. If `allocated_capital > 0` but no deposit events found, it zeros out the phantom capital.

## Capital Flow

```
[Hyperliquid Exchange]
        |
        | WebSocket: userNonFundingLedgerUpdates
        v
[BalanceReconciliationService]
        |
        | Updates allocated_capital
        v
[PostgreSQL Database]
        |
        | Read by
        v
[StatisticsService / EmergencyManager]
```

## Services

### BalanceSyncService (`balance_sync.py`)

**Purpose**: Initialize balances at startup from Hyperliquid.

**Policy**:
- Only initializes `allocated_capital` if it's 0 or NULL
- Always updates `current_balance`
- Never overwrites existing `allocated_capital` (respects Deployer allocations)
- Does NOT set `peak_balance` (prevents false emergency stops)

### BalanceReconciliationService (`balance_reconciliation.py`)

**Purpose**: Track deposits/withdrawals to adjust `allocated_capital`.

**Features**:
- **Startup Catchup**: Fetches missed events via HTTP API
- **Real-time Tracking**: WebSocket callback for live updates
- **Phantom Capital Detection**: Zeros out unfunded allocations

**Policy**:
- Deposit/Transfer IN: `allocated_capital += amount`
- Withdraw/Transfer OUT: `allocated_capital -= amount`
- Never allows `allocated_capital < 0`
- Updates `peak_balance` when deposits increase it

### StatisticsService (`statistics_service.py`)

**Purpose**: Calculate true P&L immune to manual deposits/withdrawals.

**Formula**: `True P&L = Current Balance - Allocated Capital`

This works because `allocated_capital` now tracks the actual capital that was deposited, adjusted for any withdrawals.

## Event Types

The reconciliation service handles these Hyperliquid ledger event types:

| Type | Direction | Effect |
|------|-----------|--------|
| `deposit` | IN | +allocated_capital |
| `withdraw` | OUT | -allocated_capital |
| `internalTransfer` | IN/OUT | +/- allocated_capital |
| `subAccountTransfer` | IN/OUT | +/- allocated_capital |
| `send` | IN/OUT | +/- allocated_capital |

## Configuration

```yaml
hyperliquid:
  balance_reconciliation:
    enabled: true
    catchup_lookback_days: 7      # Days to look back at startup
    ws_silence_threshold_sec: 120 # Staleness warning threshold
```

## Troubleshooting

### False Drawdown Alerts

**Symptom**: "Portfolio DD 30% >= 20%" when no real losses occurred.

**Diagnosis**:
1. Check subaccounts with `allocated_capital > 0` but `current_balance = 0`
2. These are phantom capital entries

**Solution**:
1. Restart executor - reconciliation service will detect and zero phantom capital
2. Or manually run: `UPDATE subaccounts SET allocated_capital = 0 WHERE current_balance = 0`

### Missing Ledger Events

**Symptom**: `allocated_capital` doesn't match actual deposits.

**Diagnosis**:
1. Check `catchup_lookback_days` in config
2. If deposits were > 7 days ago, increase lookback

**Solution**:
1. Increase `catchup_lookback_days` temporarily
2. Restart executor to re-run catchup
3. Reset to normal value after sync

### WebSocket Disconnection

**Symptom**: Real-time updates not being processed.

**Diagnosis**:
1. Check logs for "WebSocket connection closed"
2. Check `last_webdata2_update` in data provider

**Solution**:
1. WebSocket auto-reconnects with exponential backoff
2. Missed events recovered via HTTP at next startup

## Data Flow Diagram

```
[User deposits on Hyperliquid]
            |
            v
[Hyperliquid API] --WebSocket--> [HyperliquidDataProvider]
            |                              |
            |                    _handle_ledger_update()
            |                              |
            v                              v
[BalanceReconciliationService] <---- callback
            |
            | _apply_adjustment()
            v
[Database: Subaccount.allocated_capital]
            |
            v
[EmergencyStopManager.check_drawdowns()]
            |
            v
[Correct DD calculation, no false alerts]
```

## Related Files

- `src/executor/balance_sync.py` - Startup balance initialization
- `src/executor/balance_reconciliation.py` - Deposit/withdrawal tracking
- `src/executor/statistics_service.py` - True P&L calculation
- `src/data/hyperliquid_websocket.py` - WebSocket subscription
- `src/executor/emergency_stop_manager.py` - Drawdown monitoring
