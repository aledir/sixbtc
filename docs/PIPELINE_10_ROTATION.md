# 10. Rotation → LIVE

**Obiettivo**: Selezionare le migliori strategie dal pool ACTIVE e deployarle sui subaccount Hyperliquid per il trading LIVE.

**Daemon**: `ContinuousRotatorProcess` (`src/rotator/main_continuous.py`)
**Intervallo**: `check_interval_minutes` (default 5 min)

---

## STEP 1: Check Free Slots

`StrategySelector.get_free_slots()`

```python
free_slots = max_live_strategies - live_count
```

**Esempio**:
- max_live_strategies = 10 (config)
- live_count = 7 (strategie con status=LIVE)
- free_slots = 3

Se free_slots = 0 → **SKIP** (nessuno slot disponibile)

---

## STEP 2: Check Pool Ready

`StrategySelector.is_pool_ready()`

```python
active_count >= min_pool_size
```

**Esempio**:
- min_pool_size = 50 (config)
- active_count = 23 (strategie con status=ACTIVE)
- pool_ready = False → **SKIP** (pool non abbastanza maturo)

**Logica**: Aspettare che il pool sia popolato prima di deployare, per avere una selezione migliore.

---

## STEP 3: Select Candidates (con diversificazione)

`StrategySelector.get_candidates(slots_available)`

### Filtri applicati

1. status = 'ACTIVE' (nel pool)
2. score_backtest >= min_score (40)
3. ORDER BY score_backtest DESC

### Vincoli diversificazione (check vs LIVE esistenti)

- `max_per_type`: 3 (es: max 3 MOM, max 3 REV, etc.)
- `max_per_timeframe`: 3 (es: max 3 su 15m, max 3 su 1h)

### Esempio selezione

```
LIVE esistenti: 2 MOM, 2 REV, 1 TRN (su 15m, 30m, 1h)
slots_available: 2

Candidato #1: Strategy_MOM_abc (score=78, type=MOM, tf=15m)
  → MOM count: 2+1=3 <= max_per_type(3) OK
  → 15m count: 2+1=3 <= max_per_timeframe(3) OK
  → SELEZIONATO

Candidato #2: Strategy_MOM_def (score=75, type=MOM, tf=15m)
  → MOM count: 3+1=4 > max_per_type(3) SKIP

Candidato #3: Strategy_BRE_ghi (score=72, type=BRE, tf=2h)
  → BRE count: 0+1=1 <= max_per_type(3) OK
  → 2h count: 0+1=1 <= max_per_timeframe(3) OK
  → SELEZIONATO

Output: [Strategy_MOM_abc, Strategy_BRE_ghi]
```

---

## STEP 4: Get Free Subaccounts

`StrategyDeployer.get_free_subaccounts()`

Subaccount libero: `strategy_id IS NULL`

Se subaccount non esistono → creati automaticamente (n_subaccounts da config, default 10)

Output: `[{id: 1, allocated_capital: 0}, {id: 5, allocated_capital: 0}]`

---

## STEP 5: Deploy

Per ogni (candidate, free_subaccount):

`StrategyDeployer.deploy(strategy, subaccount_id)`

1. **Calcola capital allocation**:
   ```python
   capital_per = total_capital / (active_subaccounts + 1)
   # Es: $10,000 / 8 = $1,250 per subaccount
   ```

2. **Update Subaccount**:
   ```python
   subaccount.strategy_id = strategy_id
   subaccount.status = 'ACTIVE'
   subaccount.allocated_capital = capital_per
   subaccount.deployed_at = now()
   ```

3. **Update Strategy**:
   ```python
   strategy.status = 'LIVE'
   strategy.live_since = now()
   ```

4. **Emit events**:
   - `EventTracker.strategy_promoted_live()`
   - `EventTracker.deployment_succeeded()`

---

## Undeploy (quando strategia viene ritirata)

`StrategyDeployer.undeploy(strategy_id, reason)`

### Trigger

- Monitor rileva degradation (live score << backtest score)
- Re-test fallisce (OOS peggiorato)
- Manuale (admin command)

### Azioni

1. Chiudi posizioni aperte (se non dry_run)
2. Libera subaccount:
   ```python
   subaccount.strategy_id = NULL
   subaccount.status = 'PAUSED'
   ```
3. Update strategia:
   ```python
   strategy.status = 'RETIRED'
   strategy.retired_at = now()
   ```
4. Emit event: `EventTracker.strategy_retired()`

---

## Strategy Status Lifecycle (completo)

```
GENERATED --> VALIDATED --> [ACTIVE pool] --> LIVE --> RETIRED
     |            |              |             |
     v            v              v             v
  (DELETE)     (DELETE)      (RETIRED)    (RETIRED)
```

**Nota**: FAILED non è uno status, la strategia viene DELETE

---

## Config (config.yaml)

```yaml
rotator:
  check_interval_minutes: 5
  max_live_strategies: 10
  min_pool_size: 50        # Aspetta che pool sia maturo
  selection:
    max_per_type: 3        # Max strategie stesso tipo
    max_per_timeframe: 3   # Max strategie stesso TF

hyperliquid:
  subaccounts:
    count: 10              # Numero subaccount disponibili
  dry_run: true            # Se true, no ordini reali

trading:
  total_capital: 10000     # Capitale totale da distribuire
```

---

## File Coinvolti

- `src/rotator/main_continuous.py` → ContinuousRotatorProcess
- `src/rotator/selector.py` → StrategySelector
- `src/rotator/deployer.py` → StrategyDeployer
