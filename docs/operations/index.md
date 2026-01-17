# Operations

Gestione servizi, log e monitoring.

---

## Documentazione

| Pagina | Contenuto |
|--------|---------|
| [Troubleshooting](troubleshooting.md) | Problemi comuni e soluzioni |
| [Decision Trees](decision-trees.md) | "Ho questo problema, cosa faccio?" - guide passo-passo |
| [When to Worry](when-to-worry.md) | "Questo e' normale?" - segnali di allarme e metriche |

---

## Gestione Servizi

Tutti i servizi gestiti via supervisor:

```bash
# Avvia tutti
supervisorctl start sixbtc:*

# Ferma tutti
supervisorctl stop sixbtc:*

# Restart servizio specifico
supervisorctl restart sixbtc:executor

# Controlla stato
supervisorctl status sixbtc:*

# Segui log
supervisorctl tail -f sixbtc:api
```

!!! warning "Mai avviare manualmente"
    Usare sempre `supervisorctl`. Mai eseguire `python -m ...` direttamente.

---

## File Log

Tutti i log in `/home/bitwolf/sixbtc/logs/`:

| Servizio | File |
|---------|------|
| generator | generator.log |
| validator | validator.log |
| backtester | backtester.log |
| rotator | rotator.log |
| executor | executor.log |
| monitor | monitor.log |
| api | api.log |

Rotazione log a 10MB, mantiene 3 backup.

---

## Health Check

### Health API

```bash
curl http://localhost:8080/api/status
```

### Stato Servizi

```bash
supervisorctl status sixbtc:*
```

### Database

```bash
psql -d sixbtc -c "SELECT 1"
```

---

## Backup

### Database

```bash
pg_dump sixbtc > backup.sql
```

### Config

```bash
cp config/config.yaml config/config.yaml.bak
```

---

## Recovery

### Crash Servizio

I servizi si riavviano automaticamente via supervisor. Controllare log per root cause.

### Recovery Database

```bash
psql sixbtc < backup.sql
```

### Reset Completo

```bash
# Ferma tutti i servizi
supervisorctl stop sixbtc:*

# Reset database
dropdb sixbtc && createdb sixbtc
alembic upgrade head

# Riavvia
supervisorctl start sixbtc:*
```
