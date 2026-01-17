# Integrazioni

Integrazioni con servizi esterni.

---

## Panoramica

| Integrazione | Scopo |
|-------------|---------|
| [Hyperliquid](hyperliquid.md) | Exchange per trading live |
| [Balance Management](balance-management.md) | Tracking capitale |

---

## Hyperliquid

Exchange principale per trading live.

- WebSocket per dati mercato
- REST per piazzamento ordini
- Gestione subaccount

Vedi [Integrazione Hyperliquid](hyperliquid.md).

---

## Sorgenti Dati

### Binance (CCXT)

Dati OHLCV storici per backtesting.

```python
import ccxt
binance = ccxt.binance()
ohlcv = binance.fetch_ohlcv('BTC/USDT', '1h')
```

### Pattern Discovery API

API locale per rilevamento pattern.

```
http://localhost:8001/patterns
```

---

## Provider AI

### Claude (Anthropic)

Usato per generazione strategie AI.

```yaml
generator:
  claude_api_key: "..."
```

### GPT (OpenAI)

Provider AI alternativo.

```yaml
generator:
  openai_api_key: "..."
```
