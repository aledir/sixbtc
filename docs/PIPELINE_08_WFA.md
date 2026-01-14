# 8. WFA Fixed Params (Walk-Forward Analysis)

**Obiettivo**: Verificare che i best params (da parametric optimization) funzionino su TUTTO il periodo storico, non solo su una parte.

**Input**:
- strategy con best_params fissi
- dati IS completi (120 giorni)
- shuffle test passato

**Output**: PASS/FAIL → se PASS, procede a POOL ENTRY

---

## Expanding Windows (4 finestre)

```
IS Data (120 giorni):
════════════════════════════════════════════════════════════════════

Window 1 (25%):  ███████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
                 └── giorni 1-30

Window 2 (50%):  ██████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░
                 └── giorni 1-60

Window 3 (75%):  █████████████████████████████████░░░░░░░░░░░░░░░░░
                 └── giorni 1-90

Window 4 (100%): ██████████████████████████████████████████████████
                 └── giorni 1-120
```

---

## Logica WFA Fixed Params

Per ogni window:
1. Slice dati: `_slice_data_by_percentage(is_data, pct)`
2. Backtest con params **FISSI** (NO ri-ottimizzazione!)
3. Calcola expectancy per la window

### Criterio di successo

- **TUTTE e 4** le windows devono avere `expectancy >= 0.002` (0.2%)
- Se anche **UNA sola** window fallisce → strategia **FAIL**

### Esempio PASS

```
W1: exp=0.0035, W2: exp=0.0028, W3: exp=0.0041, W4: exp=0.0032
→ Tutte >= 0.002 → PASS
```

### Esempio FAIL

```
W1: exp=0.0035, W2: exp=0.0012, W3: exp=0.0041, W4: exp=0.0032
→ W2 < 0.002 → FAIL ("insufficient_profitable_windows:3/4")
```

---

## Differenza dalla Vecchia WFA

| VECCHIA WFA | NUOVA WFA (FIXED PARAMS) |
|-------------|--------------------------|
| Ri-ottimizza params ogni window | Params **FISSI** (da parametric) |
| Check: CV params (stabilità) | Check: expectancy >= 0.002 (profitability) |
| ~4200 simulazioni (4 × 1050 combo) | 4 simulazioni (1 per window) |
| Output: optimal_params | Output: pass/fail |

**Vantaggio**: Molto più veloce, verifica che i params ottimizzati siano generalizzabili su tutto il periodo.

---

## Config (config.yaml)

```yaml
wfa_validation:
  enabled: true
  window_percentages: [0.25, 0.50, 0.75, 1.0]
  min_expectancy: 0.002       # 0.2% per window
  min_profitable_windows: 4   # Tutte devono passare
```

---

## Output

| Risultato | Azione |
|-----------|--------|
| **PASS** (4/4 windows) | Procede a **POOL ENTRY** |
| **FAIL** (<4 windows) | return (False, "insufficient_profitable_windows"), status = **RETIRED** |

---

## File Coinvolti

- `src/backtester/main_continuous.py` → `_run_wfa_fixed_params()`
- `src/backtester/main_continuous.py` → `_slice_data_by_percentage()`
