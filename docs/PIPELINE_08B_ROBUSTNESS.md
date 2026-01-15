# 8.5 Robustness Check (Final Gate)

**Obiettivo**: Verificare che la strategia sia robusta abbastanza per il live trading, filtrando strategie overfit o con edge non affidabile.

**Input**:
- Strategy con WFA validation passed
- Risultati backtest IS e OOS
- Numero di indicatori della strategia

**Output**: PASS/FAIL -> se PASS, procede a POOL ENTRY

---

## Formula Robustness

```python
robustness = 0.50 * oos_ratio + 0.35 * trade_score + 0.15 * simplicity

Where:
- oos_ratio = min(1.0, OOS_Sharpe / IS_Sharpe)  # Generalization
- trade_score = min(1.0, total_trades / 150)    # Statistical significance
- simplicity = 1.0 / num_indicators             # Overfitting resistance
```

---

## Componenti

### 1. OOS/IS Ratio (50% peso)

Misura quanto bene la strategia generalizza a dati non visti.

| OOS/IS Ratio | Interpretazione |
|--------------|-----------------|
| 1.0 | Perfetto - OOS = IS performance |
| 0.8 | Buono - 20% degradation |
| 0.5 | Mediocre - 50% degradation |
| 0.2 | Overfit - 80% degradation |

### 2. Trade Significance (35% peso)

Misura l'affidabilita statistica basata sul numero di trade.

| Total Trades | trade_score |
|--------------|-------------|
| 150+ | 1.0 |
| 100 | 0.67 |
| 50 | 0.33 |
| 15 | 0.10 |

### 3. Simplicity (15% peso)

Meno indicatori = meno overfitting.

| Indicators | simplicity |
|------------|------------|
| 1 | 1.00 |
| 2 | 0.50 |
| 3 | 0.33 |

---

## Threshold

**Default**: `0.80` (configurabile via `backtesting.robustness.min_threshold`)

### Esempio PASS

```
IS_Sharpe: 2.5, OOS_Sharpe: 2.25 (ratio = 0.90)
Total trades: 180 (trade_score = 1.0)
Indicators: 2 (simplicity = 0.50)

robustness = 0.50 * 0.90 + 0.35 * 1.0 + 0.15 * 0.50
           = 0.45 + 0.35 + 0.075
           = 0.875 >= 0.80 -> PASS
```

### Esempio FAIL

```
IS_Sharpe: 4.0, OOS_Sharpe: 1.5 (ratio = 0.375)
Total trades: 40 (trade_score = 0.27)
Indicators: 3 (simplicity = 0.33)

robustness = 0.50 * 0.375 + 0.35 * 0.27 + 0.15 * 0.33
           = 0.1875 + 0.0945 + 0.0495
           = 0.33 < 0.80 -> FAIL (overfit + low trades)
```

---

## Differenza Score vs Robustness

| Score | Robustness |
|-------|------------|
| Misura **performance** storica | Misura **confidence** che edge sia reale |
| 0-100 scala | 0-1 scala |
| Sharpe, winrate, expectancy, drawdown | OOS/IS ratio, trade count, simplicity |
| Ranking strategies | Quality filter |

**Entrambi sono necessari per il deployment**: Score alto + Robustness alto = strategia ideale per live.

---

## Config (config.yaml)

```yaml
backtesting:
  # Robustness filter (final gate before pool entry)
  robustness:
    min_threshold: 0.80           # Minimum robustness score (0-1)
    weights:
      oos_ratio: 0.50             # OOS/IS Sharpe ratio weight
      trade_significance: 0.35    # Trade count weight
      simplicity: 0.15            # Indicator count weight
    trade_significance_target: 150  # Trades for max score
```

---

## Output

| Risultato | Azione |
|-----------|--------|
| **PASS** (robustness >= threshold) | Procede a **POOL ENTRY** |
| **FAIL** (robustness < threshold) | return (False, "robustness_below_threshold:X.XX"), status rimane **VALIDATED** |

---

## Failure Handling

La strategia che fallisce robustness check:
- **Non viene marcata FAILED** (non e un bug)
- **Non viene marcata RETIRED** (non e stata mai in pool)
- **Resta VALIDATED** - potrebbe riprovare in futuro se i dati cambiano
- **Event logged**: `robustness_check.failed` con dettagli

---

## Metrics (metrics.log)

```
[8.5/10 ROBUSTNESS] 24h: 180/200 passed (90%)
[8.5/10 ROBUSTNESS] passed_avg: 0.91 | failed_avg: 0.68 | threshold: 0.80
[8.5/10 ROBUSTNESS] pool: 0.80 to 1.00 (avg 0.91)
```

---

## File Coinvolti

- `src/backtester/main_continuous.py` -> `_calculate_robustness()`
- `src/backtester/main_continuous.py` -> robustness check in `_promote_to_active_pool()`
- `src/database/models.py` -> `Strategy.robustness_score` column
- `src/metrics/collector.py` -> `_get_robustness_stats_24h()`, `_get_pool_robustness_stats()`
- `config/config.yaml` -> `backtesting.robustness` section
