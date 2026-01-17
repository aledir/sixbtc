# Quickstart

SixBTC funzionante in 10 minuti.

---

## 1. Avvia Servizi

```bash
# Avvia tutti i servizi
supervisorctl start sixbtc:*

# Verifica che siano tutti running
supervisorctl status sixbtc:*
```

Output atteso - tutti devono mostrare `RUNNING`:

```
sixbtc:api              RUNNING   pid 1234, uptime 0:01:00
sixbtc:frontend         RUNNING   pid 1235, uptime 0:01:00
sixbtc:generator        RUNNING   pid 1236, uptime 0:01:00
...
```

---

## 2. Accedi alla Dashboard

Apri browser su: `http://localhost:5173`

- **Overview**: P&L, equity curve, stato sistema
- **Trading**: Subaccount, posizioni, trade history
- **Strategies**: Ranking e dettagli strategie
- **Pipeline**: Metriche funnel generazione
- **System**: Log, task, configurazione

---

## 3. Verifica Flusso Dati

Controlla che i servizi funzionino:

```bash
# Controlla log
tail -f logs/generator.log
tail -f logs/executor.log

# Health check API
curl http://localhost:8080/api/status
```

---

## 4. Prima Generazione Strategia

Il generator gira automaticamente. Per triggerare manualmente:

```bash
# Via API
curl -X POST http://localhost:8080/api/generator/trigger

# Controlla stato
curl http://localhost:8080/api/strategies?status=GENERATED
```

---

## 5. Monitora Pipeline

Guarda le strategie fluire attraverso la pipeline:

1. **Generator**: Crea codice strategia
2. **Validator**: Check sintassi, AST, lookahead
3. **Backtester**: Esegue test IS + OOS
4. **Scorer**: Applica threshold
5. **Rotator**: Promuove a LIVE

La pagina Pipeline nella dashboard mostra le metriche del funnel.

---

## Troubleshooting

| Problema | Soluzione |
|----------|----------|
| Servizio non parte | Controlla `logs/<servizio>.log` |
| API non raggiungibile | Verifica che porta 8080 non sia in uso |
| Errori database | Controlla che PostgreSQL sia running |
| Nessuna strategia generata | Controlla log generator, verifica API keys |

Vedi [Troubleshooting](../operations/troubleshooting.md) per altro.
