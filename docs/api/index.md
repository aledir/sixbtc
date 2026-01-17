# Reference API

Backend FastAPI con 71 endpoint.

---

## Panoramica

Base URL: `http://localhost:8080/api`

Autenticazione: Nessuna (solo uso interno)

---

## Gruppi Endpoint

| Gruppo | Prefisso | Endpoint | Descrizione |
|-------|--------|-----------|-------------|
| Status | `/status` | 3 | Stato sistema |
| Strategies | `/strategies` | 12 | CRUD strategie |
| Backtests | `/backtests` | 6 | Risultati backtest |
| Trades | `/trades` | 8 | Storico trade |
| Positions | `/positions` | 5 | Posizioni correnti |
| Subaccounts | `/subaccounts` | 7 | Gestione subaccount |
| Pipeline | `/pipeline` | 8 | Stato pipeline |
| Generator | `/generator` | 4 | Controllo generazione |
| Metrics | `/metrics` | 6 | Metriche sistema |
| Tasks | `/tasks` | 5 | Task schedulati |
| Config | `/config` | 4 | Configurazione |
| Emergency | `/emergency` | 3 | Controlli emergenza |

---

## Endpoint Chiave

### Status

```
GET /api/status
```

Ritorna stato sistema, health servizi, alert.

### Strategies

```
GET /api/strategies                    # Lista strategie
GET /api/strategies/{id}               # Ottieni strategia
GET /api/strategies/{id}/metrics       # Ottieni metriche
POST /api/strategies/{id}/retire       # Ritira strategia
```

### Trades

```
GET /api/trades                        # Lista trade
GET /api/trades/stats                  # Statistiche trade
GET /api/trades/pnl                    # Riepilogo P&L
```

### Pipeline

```
GET /api/pipeline/status               # Funnel pipeline
GET /api/pipeline/stats                # Statistiche generazione
POST /api/generator/trigger            # Triggera generazione
```

---

## Formato Response

Tutti gli endpoint ritornano JSON:

```json
{
  "data": { ... },
  "error": null,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

Errori:

```json
{
  "data": null,
  "error": {
    "code": "NOT_FOUND",
    "message": "Strategia non trovata"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Rate Limit

Nessun rate limit per API interna.

Hyperliquid REST: 1200 req/min

---

## File Chiave

| File | Scopo |
|------|---------|
| `src/api/main.py` | App FastAPI |
| `src/api/routes/*.py` | Handler route |
| `src/api/schemas.py` | Modelli Pydantic |
