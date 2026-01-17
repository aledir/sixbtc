# Processi

11 daemon services gestiti da supervisor.

---

## Panoramica Servizi

| Servizio | Priorita' | Scopo | Restart Policy |
|---------|----------|---------|----------------|
| generator | 100 | Generazione strategie | unexpected |
| validator | 200 | Validazione sintassi/AST | unexpected |
| backtester | 300 | Test IS + OOS | unexpected |
| rotator | 400 | Promozione ACTIVE -> LIVE | unexpected |
| executor | 500 | Trading live | always |
| monitor | 700 | Tracking performance | always |
| scheduler | 800 | Task periodici | unexpected |
| metrics | 850 | Metriche sistema | always |
| api | 900 | Backend FastAPI | always |
| frontend | 901 | Vite dev server | always |
| docs | 902 | MkDocs server | always |

---

## Gestione Servizi

```bash
# Avvia tutti
supervisorctl start sixbtc:*

# Ferma tutti
supervisorctl stop sixbtc:*

# Restart specifico
supervisorctl restart sixbtc:executor

# Controlla stato
supervisorctl status sixbtc:*

# Segui log
supervisorctl tail -f sixbtc:api
```

!!! warning "Mai avviare manualmente"
    Usare sempre supervisorctl. Mai eseguire `python -m ...` direttamente.

---

## Dettagli Processi

### Generator (priorita' 100)

```ini
command=python -u src/processes/generator.py
autorestart=unexpected
```

- Esegue loop di generazione
- Source: pattern, unger, ai_free, ai_assigned, pattern_gen, pandas_ta
- Intervallo configurabile via config.yaml

### Validator (priorita' 200)

- Analisi AST per rilevamento lookahead
- Validazione sintassi
- Check signature strategia

### Backtester (priorita' 300)

- Kernel compilati Numba-JIT
- Test in-sample + out-of-sample
- Shuffle test per validazione lookahead

### Rotator (priorita' 400)

- Promuove ACTIVE -> LIVE in base allo score
- Gestisce allocazione subaccount
- Gestisce retirement

### Executor (priorita' 500)

```ini
autorestart=true  # Critico - sempre restart
```

- Loop trading live
- Connessione WebSocket a Hyperliquid
- Gestione posizioni

### Monitor (priorita' 700)

- Tracking P&L
- Metriche performance
- Trigger emergency stop

### Scheduler (priorita' 800)

- Task periodici (data sync, cleanup)
- Scheduling cron-like

### Metrics (priorita' 850)

- Raccolta metriche sistema
- Health check

### API (priorita' 900)

```ini
command=uvicorn src.api.main:app --host 0.0.0.0 --port 8080
```

- 71 endpoint REST
- Serve dati al frontend

### Frontend (priorita' 901)

```ini
command=npm run dev -- --host 0.0.0.0 --port 5173
```

- Vite dev server
- Dashboard React

---

## Posizioni Log

Tutti i log in `/home/bitwolf/sixbtc/logs/`:

| Servizio | File Log |
|---------|----------|
| generator | generator.log |
| validator | validator.log |
| backtester | backtester.log |
| rotator | rotator.log |
| executor | executor.log |
| monitor | monitor.log |
| scheduler | scheduler.log |
| metrics | metrics.log |
| api | api.log |
| frontend | frontend.log |

Log gestiti da Python logging con rotazione.
