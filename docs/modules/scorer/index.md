# Modulo Scorer

Scoring e ranking strategie.

---

## Panoramica

Lo Scorer:

1. Riceve metriche backtest
2. Applica threshold
3. Calcola score robustezza
4. Classifica strategie

---

## Formula Scoring

```
robustness = 0.50 * oos_ratio + 0.35 * trade_score + 0.15 * simplicity
```

Dove:

- `oos_ratio` = Performance OOS / Performance IS
- `trade_score` = numero trade normalizzato
- `simplicity` = inverso della complessita' codice

**Threshold**: `robustness >= 0.80`

---

## Threshold Metriche

| Metrica | Threshold | Azione Fallimento |
|--------|-----------|-------------|
| Sharpe Ratio | >= 1.0 | FAILED |
| Win Rate | >= 55% | FAILED |
| Max Drawdown | <= 30% | FAILED |
| Numero Trade | >= 100 | FAILED |
| OOS Ratio | >= 0.7 | FAILED |

---

## Configurazione

```yaml
scorer:
  sharpe_threshold: 1.0
  winrate_threshold: 0.55
  max_dd_threshold: 0.30
  min_trades: 100
  robustness_threshold: 0.80
```

---

## File Chiave

| File | Scopo |
|------|---------|
| `src/scorer/main.py` | Logica scoring |
| `src/scorer/metrics.py` | Calcolo metriche |
| `src/scorer/robustness.py` | Formula robustezza |
