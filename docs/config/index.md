# Configurazione

Parametri e impostazioni config.yaml.

---

## Panoramica

Tutta la configurazione in `config/config.yaml`.

**Principio**: Nessun valore hardcoded. Config mancante = crash = bene.

---

## Documentazione

| Pagina | Contenuto |
|--------|---------|
| [Reference](reference.md) | Tutti i 50+ parametri |

---

## Struttura Config

```yaml
# Database
database:
  url: "postgresql://..."

# Hyperliquid
hyperliquid:
  wallet_address: "0x..."
  private_key: "..."

# Risk management
risk:
  max_portfolio_dd: 0.30
  ...

# Generator
generator:
  interval_seconds: 300
  ...

# Backtester
backtester:
  is_ratio: 0.7
  ...

# Executor
executor:
  poll_interval: 1.0
  ...
```

---

## Variabili Ambiente

Alcune impostazioni sovrascrivibili via environment:

| Variabile | Chiave Config |
|----------|------------|
| `DATABASE_URL` | `database.url` |
| `HL_WALLET` | `hyperliquid.wallet_address` |
| `HL_KEY` | `hyperliquid.private_key` |

---

## Validazione

Il config e' validato allo startup. Valori richiesti mancanti causano crash immediato.

```python
# Bene - crash se mancante
db_url = config['database']['url']

# Male - fallimento silenzioso
db_url = config.get('database', {}).get('url', 'default')
```
