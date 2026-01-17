# Reference

Documentazione tecnica di riferimento.

---

## Documenti

| Pagina | Contenuto |
|--------|---------|
| [Risk Management](risk.md) | Position sizing, limiti, emergency stop |
| [Coin Universe](coin.md) | Coppie trading supportate |
| [Statistiche ATR](atr-statistics.md) | Reference volatilita' |
| [Esempi Codice](coding-examples.md) | Pattern codice strategia |

---

## Quick Reference

### Ciclo di Vita Strategia

```
GENERATED -> VALIDATED -> ACTIVE -> LIVE -> RETIRED
```

### Threshold Metriche

| Metrica | Threshold |
|--------|-----------|
| Sharpe | >= 1.0 |
| Win Rate | >= 55% |
| Max DD | <= 30% |
| Min Trade | >= 100 |

### Formula Robustezza

```
robustness = 0.50*oos_ratio + 0.35*trade_score + 0.15*simplicity >= 0.80
```

### Position Sizing

```
risk_amount = equity * risk_pct
notional = risk_amount / sl_pct
margin_needed = notional / leverage
```

Salta trade se: `margin_needed > available_margin` OPPURE `notional < 10 USDC`
