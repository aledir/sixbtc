# Configurazione

Impostazioni essenziali config.yaml.

---

## Posizione File Config

```
config/config.yaml
```

---

## Impostazioni Essenziali

### Hyperliquid

```yaml
hyperliquid:
  wallet_address: "0x..."
  private_key: "..."  # Mai committare!
  testnet: false
```

### Database

```yaml
database:
  url: "postgresql://bitwolf@localhost/sixbtc"
```

### Risk Management

```yaml
risk:
  max_portfolio_dd: 0.30      # 30% max drawdown portfolio
  max_daily_dd: 0.10          # 10% max drawdown giornaliero
  max_subaccount_dd: 0.25     # 25% max DD per-subaccount
  consecutive_loss_review: 5  # Review dopo 5 loss consecutive
```

---

## Configurazione Servizi

### Generator

```yaml
generator:
  interval_seconds: 300       # Genera ogni 5 min
  batch_size: 10              # Strategie per batch
  sources:
    - pattern
    - unger
    - ai_free
```

### Backtester

```yaml
backtester:
  is_ratio: 0.7               # 70% in-sample
  min_trades: 100
  sharpe_threshold: 1.0
  winrate_threshold: 0.55
  max_dd_threshold: 0.30
```

---

## Reference Completo

Vedi [Config Reference](../config/reference.md) per tutti i 50+ parametri.
