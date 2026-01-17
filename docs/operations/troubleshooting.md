# Troubleshooting

Problemi comuni e soluzioni.

---

## Problemi Servizi

### Servizio Non Parte

**Sintomo**: Il servizio mostra FATAL o BACKOFF in supervisorctl

**Controlla**:
```bash
supervisorctl tail sixbtc:<servizio>
cat logs/<servizio>.log
```

**Cause comuni**:
- Valore config mancante (controlla config.yaml)
- Porta gia' in uso
- Connessione database fallita
- Errore import Python

---

### API Non Raggiungibile

**Sintomo**: `curl localhost:8080` fallisce

**Controlla**:
```bash
supervisorctl status sixbtc:api
netstat -tulpn | grep 8080
```

**Soluzioni**:
- Restart API: `supervisorctl restart sixbtc:api`
- Controlla conflitto porta
- Controlla log: `cat logs/api.log`

---

### Disconnessioni WebSocket

**Sintomo**: Executor perde connessione a Hyperliquid

**Controlla**:
```bash
cat logs/executor.log | grep -i websocket
```

**Soluzioni**:
- Controlla connessione internet
- Verifica stato Hyperliquid
- Executor si riconnette automaticamente, aspetta 30s

---

## Problemi Pipeline

### Nessuna Strategia Generata

**Sintomo**: Non appaiono nuove strategie

**Controlla**:
```bash
cat logs/generator.log
curl localhost:8080/api/pipeline/status
```

**Cause comuni**:
- Generator in pausa
- Problemi API key (per sorgenti AI)
- Pattern discovery API down

---

### Strategie Bloccate in GENERATED

**Sintomo**: Strategie non avanzano a VALIDATED

**Controlla**:
```bash
supervisorctl status sixbtc:validator
cat logs/validator.log
```

**Soluzioni**:
- Restart validator
- Controlla errori AST nei log

---

### Tutte le Strategie FAILED

**Sintomo**: Alto tasso fallimento in backtest

**Controlla**:
```bash
curl localhost:8080/api/strategies?status=FAILED
cat logs/backtester.log
```

**Cause comuni**:
- Threshold troppo stretti
- Problemi qualita' dati
- Lookahead nel codice generato

---

## Problemi Trading

### Ordini Non Eseguiti

**Sintomo**: Ordini piazzati ma non eseguiti

**Controlla**:
```bash
cat logs/executor.log | grep -i order
```

**Cause comuni**:
- Margine insufficiente
- Prezzo si e' mosso (slippage)
- Problemi Hyperliquid

---

### Perdite Inattese

**Sintomo**: Perdite nonostante buon backtest

**Controlla**:
- Metriche strategia su dashboard
- Storico trade per pattern
- Analisi slippage

**Soluzioni**:
- Review segnali strategia
- Controlla lookahead (shuffle test)
- Aggiusta parametri rischio

---

## Problemi Database

### Connessione Rifiutata

**Sintomo**: I servizi non si connettono al database

**Controlla**:
```bash
sudo systemctl status postgresql
psql -d sixbtc -c "SELECT 1"
```

**Soluzioni**:
- Avvia PostgreSQL: `sudo systemctl start postgresql`
- Controlla credenziali in config.yaml

---

### Disco Pieno

**Sintomo**: Errori database, crash servizi

**Controlla**:
```bash
df -h
du -sh logs/*
```

**Soluzioni**:
- Pulisci vecchi log
- Vacuum database
- Aggiungi spazio disco

---

## Quick Reference

| Problema | Primo Step |
|----------|------------|
| Servizio down | `supervisorctl status sixbtc:*` |
| Errore API | `cat logs/api.log` |
| Niente strategie | `cat logs/generator.log` |
| Problemi trading | `cat logs/executor.log` |
| Problemi DB | `sudo systemctl status postgresql` |

---

## Ottenere Aiuto

1. Controlla i log prima
2. Rivedi questa pagina
3. Controlla config.yaml
4. Restart servizio interessato
5. Controlla CLAUDE.md per le regole
