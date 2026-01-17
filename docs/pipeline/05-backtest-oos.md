# 5. Backtest OOS (Out-of-Sample)

**Obiettivo**: Testare la strategia su dati OUT-OF-SAMPLE (60 giorni recenti) per verificare che non sia overfittata sui dati IS.

**Daemon**: `src/backtester/main_continuous.py`
**Input**:
- strategy_instance con best params da parametric
- oos_data: 60 giorni più recenti (Dict symbol -> DataFrame)
- is_result: metriche dal backtest IS

**Output**: validation + final_result → procede a SCORE + SHUFFLE + POOL ENTRY

---

## Timeline Dati

```
180 giorni totali:
════════════════════════════════════════════════════════════════════

[--- IN-SAMPLE (120 giorni) ---][-- OOS (60 giorni) --]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^
Parametric optimization          Validazione anti-overfit

OOS = dati PIÙ RECENTI = "come performa ADESSO"
IS e OOS sono NON-OVERLAPPING (nessun data leakage)
```

---

## Esecuzione Backtest OOS

Stesso engine di IS, ma con parametri diversi:
- `min_bars = 20` (vs 100 per IS)
- Periodo più corto = meno bars disponibili

```python
oos_result = _run_multi_symbol_backtest(
    strategy_instance,
    oos_data,
    timeframe,
    min_bars=20    # Lower threshold per OOS
)
```

Se oos_data ha < 5 simboli validi → `oos_result = None`

---

## _validate_oos(): 6 Threshold + Degradation Check

OOS applica gli **STESSI 5 threshold di IS + CI filter**:

1. `oos_trades >= min_trades_oos[timeframe]`
2. `oos_sharpe >= 0.3` (stesso di IS, non 0.0)
3. `oos_win_rate >= 35%`
4. `oos_expectancy >= 0.002`
5. `oos_max_drawdown <= 50%`
6. `CI <= max_ci_oos (15%)` - significatività statistica

### CI Filter (Confidence Interval)

```
CI = 1.96 × √(WR × (1-WR) / N)
```

Il CI misura l'incertezza sul win rate. OOS ha soglia più alta (15% vs 10% IS) perché ha meno dati (60 vs 120 giorni).

**Esempio**:
- N=50, WR=55% → CI = 13.8% ✓ passa
- N=30, WR=50% → CI = 17.9% ✗ troppa incertezza

### Degradation Check (anti-overfitting)

```
            is_sharpe - oos_sharpe
degrad = ────────────────────────── <= 50%
                is_sharpe
```

- `degrad > 0`: OOS peggiore di IS (normale)
- `degrad < 0`: OOS migliore di IS (bonus!)
- `degrad > 50%`: **REJECT** ("Overfitted")

### OOS Bonus/Penalty (per score finale)

- OOS >= IS: `bonus = min(0.20, |degrad| * 0.5)`
- OOS < IS: `penalty = -degrad * 0.10`

---

## Min Trades per Timeframe (da config)

| Timeframe | min_is | min_oos | CI at min (WR=50%) |
|-----------|--------|---------|-------------------|
| 15m | 120 | 60 | IS: 8.9%, OOS: 12.6% |
| 30m | 80 | 40 | IS: 11.0%, OOS: 15.5% |
| 1h | 50 | 25 | IS: 13.9%, OOS: 19.6% |
| 2h | 30 | 15 | IS: 17.9%, OOS: 25.3% |

**Nota**: Con max_ci_is=10% e max_ci_oos=15%, strategie 1h/2h devono avere più trades del minimo OPPURE WR più alto per passare il CI filter.

Timeframe alti = meno opportunità = soglie più basse, ma CI filter garantisce significatività statistica

---

## Motivi di Reject

**OOS threshold failures**:
- `[X] "OOS trades insufficient: 8 < 60 (for 15m)"`
- `[X] "OOS sharpe too low: 0.15 < 0.3"`
- `[X] "OOS win_rate too low: 30.0% < 35.0%"`
- `[X] "OOS expectancy too low: 0.0010 < 0.002"`
- `[X] "OOS drawdown too high: 55.0% > 50%"`
- `[X] "OOS CI too high: 18.5% > 15.0%"` (troppa incertezza statistica)
- `[X] "Overfitted: OOS 65% worse than IS"`

**REJECT → DELETE strategy**

---

## _calculate_final_metrics(): Metriche Finali

**Pesi**: IS = 40%, OOS = 60% (recency = "adesso conta di più")

### Metriche pesate

```python
weighted_sharpe   = is_sharpe * 0.4 + oos_sharpe * 0.6
weighted_expect   = is_expect * 0.4 + oos_expect * 0.6
weighted_win_rate = is_wr * 0.4 + oos_wr * 0.6
weighted_max_dd   = is_dd * 0.4 + oos_dd * 0.6
```

### Score parziali

```python
is_score  = 0.5*sharpe + 0.3*expect + 0.2*win_rate
oos_score = 0.5*sharpe + 0.3*expect + 0.2*win_rate
```

### Final score

```python
final = (is_score * 0.4 + oos_score * 0.6) * (1 + oos_bonus)
```

---

## Output

- `validation`: `{passed, reason, degradation, oos_bonus}`
- `final_result`: Dict con tutte le metriche pesate + final_score
- Se `passed=False` → **DELETE strategy**
- Se `passed=True` → procede a **SCORE + SHUFFLE + POOL ENTRY**

---

## File Coinvolti

- `src/backtester/main_continuous.py` → `_validate_oos()`
- `src/backtester/main_continuous.py` → `_calculate_final_metrics()`
