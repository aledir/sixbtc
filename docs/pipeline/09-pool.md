# 9. Pool Entry

**Obiettivo**: Inserire la strategia validata nel pool ACTIVE (leaderboard) competendo con le strategie esistenti per score.

**Input**:
- strategy che ha passato: Score >= 40, Shuffle, WFA
- score finale calcolato

**Output**: ENTERED/REJECTED → se ENTERED, status = ACTIVE, pronta per ROTATION

---

## Pool Rules (leaderboard logic)

`PoolManager.try_enter_pool(strategy_id, score)`

### Regole (con lock per thread safety)

| Rule | Condizione | Azione |
|------|------------|--------|
| 1 | score < min_score (40) | → **RETIRED** (non entra mai) |
| 2 | pool_count < max_size (300) | → **ENTRA** (c'è spazio), status = ACTIVE |
| 3 | pool pieno AND score > worst_score | → **EVICT** worst strategy (RETIRED), **ENTRA** al suo posto, status = ACTIVE |
| 4 | pool pieno AND score <= worst_score | → **NON ENTRA**, status = RETIRED |

**Lock**: `_pool_lock` garantisce atomicità check+insert

---

## Esempio Leaderboard

```
Pool (max 300, attuale 300):
  n.1:   Strategy_A  score=92.5
  n.2:   Strategy_B  score=88.2
  ...
  n.299: Strategy_Y  score=45.1
  n.300: Strategy_Z  score=42.3  <- WORST
```

**Nuova strategia con score=48.7**:
- 48.7 > 42.3 (worst)
- Strategy_Z **RETIRED**
- Nuova strategia **ENTRA** al n.299

**Nuova strategia con score=41.0**:
- 41.0 < 42.3 (worst)
- Nuova strategia **RETIRED** (non abbastanza buona)

---

## Eventi Emessi

| Evento | Descrizione |
|--------|-------------|
| `EventTracker.backtest_scored(...)` | Score calcolato |
| `EventTracker.shuffle_test_passed(...)` | Shuffle test passato |
| `EventTracker.pool_attempted(...)` | Tentativo ingresso pool |
| `EventTracker.pool_entered(...)` | Ingresso pool riuscito |
| `EventTracker.pool_rejected(...)` | Ingresso pool rifiutato |

---

## Output

| Risultato | Azione |
|-----------|--------|
| **ENTERED** | strategy.status = ACTIVE, nel pool, pronta per ROTATION |
| **REJECTED** | strategy.status = RETIRED, fuori pool |

---

## File Coinvolti

- `src/backtester/main_continuous.py` → `_promote_to_active_pool()`
- `src/scorer/pool_manager.py` → `PoolManager.try_enter_pool()`
