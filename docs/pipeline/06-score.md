# 6. Score Calculation

**Obiettivo**: Calcolare lo score finale della strategia combinando metriche IS e OOS per il ranking nel pool.

**Input**:
- backtest_result: BacktestResult con metriche IS
- final_result: metriche pesate IS+OOS
- degradation: `(is_sharpe - oos_sharpe) / is_sharpe`

**Output**: score → se >= 40, procede a SHUFFLE TEST

---

## Formula Score (5 componenti)

`BacktestScorer.score_from_backtest_result()`

```python
score = ( 0.40 * expectancy_norm +
          0.25 * sharpe_norm +
          0.10 * win_rate_norm +
          0.15 * drawdown_norm +
          0.10 * recency_norm ) * 100
```

### Normalizzazioni

| Componente | Range Input | Range Output |
|------------|-------------|--------------|
| expectancy_norm | [0, 0.10] | [0, 1] (0-10% edge) |
| sharpe_norm | [0, 3.0] | [0, 1] |
| win_rate_norm | [0, 1] | già [0, 1] |
| drawdown_norm | [0, 0.30] | `1 - (dd / 0.30)` (30% max = 0) |
| recency_norm | - | `0.5 - degradation` (OOS vs IS) |

**Output**: score 0-100

---

## Score Threshold Check

```python
if score < pool_min_score (40):
    -> SKIP tutti i test successivi (shuffle, WFA)
    -> EventTracker.backtest_score_rejected()
    -> return (False, "score_below_threshold:38.5")
    -> status = RETIRED
```

Solo strategie con **score >= 40** procedono al shuffle test.

---

## Output

| Condizione | Azione |
|------------|--------|
| score >= 40 | Procede a **SHUFFLE TEST** |
| score < 40 | **RETIRED** (no point testing further) |

---

## File Coinvolti

- `src/backtester/main_continuous.py` → `_promote_to_active_pool()`
- `src/scorer/backtest_scorer.py` → BacktestScorer
