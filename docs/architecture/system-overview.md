# System Overview

Descrizione dettagliata dei componenti.

---

## Principi Core

Da CLAUDE.md:

1. **KISS** - Massima semplicita', no over-engineering
2. **Single Responsibility** - Una classe/funzione = uno scopo
3. **No Fallback, Fast Fail** - Config mancante = crash = bene
4. **No Hardcoding** - TUTTI i parametri in config.yaml
5. **Dependency Injection** - Passa dipendenze, non crearle internamente
6. **Type Safety** - Type hints ovunque

---

## Responsabilita' Componenti

### Componenti Pipeline

| Componente | Scopo | Input | Output |
|-----------|---------|-------|--------|
| Generator | Crea codice strategia | Prompt, pattern | Codice Python |
| Validator | Check sintassi + lookahead | Codice | Pass/fail |
| Backtester | Test su dati storici | Strategia + dati | Metriche |
| Scorer | Applica threshold | Metriche | Score |
| Rotator | Promuove strategie | Strategie scored | Allocazione LIVE |

### Componenti Execution

| Componente | Scopo |
|-----------|---------|
| Executor | Esegue trading live, gestisce posizioni |
| Monitor | Traccia performance, triggera retirement |
| Scheduler | Esegue task periodici (sync, cleanup) |
| Metrics | Raccoglie metriche sistema |

### Infrastruttura

| Componente | Scopo |
|-----------|---------|
| API | Backend FastAPI (71 endpoint) |
| Frontend | Dashboard React (Vite) |
| Database | PostgreSQL (11 tabelle) |

---

## Decisioni di Design Chiave

### Perche' WebSocket invece di REST?

Il rate limit REST e' 1200 req/min. Con multiple strategie e posizioni, raggiungeremmo i limiti velocemente. WebSocket fornisce:

- Update prezzi real-time
- Notifiche cambio posizioni
- Eventi fill
- Nessun rate limit per letture

REST e' usato solo per azioni (place order, cancel order).

### Perche' Numba JIT?

Il backtesting Python puro era troppo lento. Numba JIT compila gli hot path a codice nativo:

- 50x+ speedup sui loop di backtest
- Codice Python ancora leggibile
- Type hints enforced a compile time

### Perche' Una Strategia = Un UUID?

Design precedenti avevano "strategia base + variazioni" che causava confusione:

- Difficile tracciare quale variazione performava
- Gestione lifecycle complessa
- Query database richiedevano join

Ora: una strategia = un UUID = un record. Semplice.
