# SixBTC

Sistema di trading automatico - Documentazione interna.

---

## Cosa Sto Cercando?

| Ho bisogno di... | Vai a... |
|------------------|----------|
| **Capire un parametro** | [Config Reference](config/reference.md) - tutti i parametri spiegati |
| **Risolvere un problema** | [Troubleshooting](operations/troubleshooting.md) |
| **Capire cosa fare se...** | [Decision Trees](operations/decision-trees.md) |
| **Sapere quando preoccuparmi** | [When to Worry](operations/when-to-worry.md) |
| **Capire la pipeline** | [Pipeline Overview](pipeline/index.md) |
| **Gestire servizi** | [Operations](operations/index.md) |

---

## Quick Commands

```bash
# Stato servizi
supervisorctl status sixbtc:*

# Restart tutto
supervisorctl restart sixbtc:*

# Seguire log specifico
supervisorctl tail -f sixbtc:executor

# Health check API
curl -s http://localhost:8080/api/status | jq .

# Pool ACTIVE count
curl -s http://localhost:8080/api/strategies?status=ACTIVE | jq '.count'

# Strategie LIVE
curl -s http://localhost:8080/api/strategies?status=LIVE | jq '.strategies[] | {name, score, subaccount}'
```

---

## Architettura in 30 Secondi

```
Generator → Validator → Backtester → Pool ACTIVE → Rotator → LIVE → Monitor
   |            |            |             |           |         |       |
  crea       valida      testa        ranking      promo    trada   ritira
```

**Strategia** = un UUID = un record database. Ciclo di vita:

```
GENERATED → VALIDATED → ACTIVE → LIVE → RETIRED
     ↓           ↓          ↓
  DELETE     DELETE     (rimane nel pool)
```

**Servizi chiave**:

| Servizio | Cosa fa | Log da controllare |
|----------|---------|-------------------|
| `generator` | Crea strategie | Niente nuove strategie? Controlla qui |
| `backtester` | Testa strategie | Troppe FAILED? Controlla qui |
| `rotator` | Promuove a LIVE | Nessuna LIVE? Controlla qui |
| `executor` | Esegue trade | Ordini non eseguiti? Controlla qui |
| `monitor` | Ritira strategie | Retirement inatteso? Controlla qui |

---

## Parametri Critici

I parametri che impattano di più (dettagli in [Config Reference](config/reference.md)):

| Parametro | Valore | Effetto |
|-----------|--------|---------|
| `hyperliquid.dry_run` | `true` | **MASTER SWITCH** - `true` = no trading reale |
| `risk.fixed_fractional.risk_per_trade_pct` | `0.02` | 2% del capitale rischiato per trade |
| `backtesting.robustness.min_threshold` | `0.80` | Gate finale per entrare ACTIVE |
| `active_pool.min_score` | `40` | Score minimo per essere ACTIVE |
| `monitor.retirement.max_drawdown` | `0.25` | 25% DD → strategia ritirata |

---

## Struttura Documentazione

| Sezione | Quando usarla |
|---------|---------------|
| [Config Reference](config/reference.md) | "Cosa fa questo parametro?" "Perche' questo valore?" |
| [Pipeline](pipeline/index.md) | "Come funziona lo step X?" |
| [Operations](operations/index.md) | "Come gestisco i servizi?" "Dove sono i log?" |
| [Troubleshooting](operations/troubleshooting.md) | "Qualcosa non funziona" |
| [Decision Trees](operations/decision-trees.md) | "Ho questo problema, cosa faccio?" |
| [When to Worry](operations/when-to-worry.md) | "Questo e' normale o devo preoccuparmi?" |
| [Database](database/index.md) | "Qual e' lo schema?" "Che query uso?" |
| [API Reference](api/index.md) | "Che endpoint ci sono?" |
| [Hyperliquid](integrations/hyperliquid.md) | "Come funziona l'integrazione exchange?" |

---

## Regole Fondamentali

!!! danger "Hyperliquid e' Source of Truth"
    Lo stato su exchange e' quello vero. Il database e' audit trail.

!!! warning "No Lookahead"

    - No `center=True` in rolling
    - No `shift(-1)`
    - Shuffle test + AST validation sempre attivi

!!! tip "Sempre supervisorctl"
    Mai `python -m ...` manualmente. Crea zombie.

---

## Checklist Giornaliera

```bash
# 1. Servizi OK?
supervisorctl status sixbtc:* | grep -v RUNNING

# 2. Pool ACTIVE sano?
curl -s http://localhost:8080/api/pool/stats | jq .

# 3. Emergency stops attivi?
curl -s http://localhost:8080/api/risk/status | jq .

# 4. Errori recenti?
tail -20 logs/executor.log | grep -i error
```

Se qualcosa non va: [Troubleshooting](operations/troubleshooting.md) e [Decision Trees](operations/decision-trees.md).
