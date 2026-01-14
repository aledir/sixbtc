# 3. Parametric Optimization

**Obiettivo**: Testare ~1015 combinazioni (SL × TP × leverage × exit_bars) per trovare la configurazione ottimale per il base code.

**Daemon**: `src/backtester/main_continuous.py`
**Input**: Strategy con `status=VALIDATED`
**Output**: Best combo → procede a IS backtest finale

---

## Decision Flow

```
is_pattern_based?
   YES → has execution_type?
          YES → build_execution_type_space() (allineato al target)
          NO  → build_pattern_centered_space() (fallback)
   NO  → build_absolute_space(timeframe) (range assoluti per TF)
```

---

## Execution Type Aligned Space (PatStrat_*)

Pattern-discovery valida i pattern su target con semantiche diverse:

### TOUCH-BASED (`target_max_*`)

Verifica se prezzo **TOCCA** livello.
- Allineato con TP-based execution
- TP DEVE esistere (centrato su magnitude)
- Exit time è backstop (può essere 0)

| Parameter | Values |
|-----------|--------|
| TP | [50%, 75%, 100%, 125%, 150%] di magnitude (NO zero) |
| SL | [100%, 150%, 200%, 250%] di magnitude (max 2.5:1 ratio) |
| EXIT | [0, 100%, 150%, 200%] di holding_bars (0 = backstop off) |
| LEV | [1, 2, 3, 5, 10, 20, 40] |

**Combinazioni**: 5 × 4 × 4 × 7 = **560**

### CLOSE-BASED (tutti gli altri)

Verifica **CLOSE** a fine periodo.
- Allineato con time-based execution
- TP DISABILITATO (sempre 0)
- Exit time è primario (non può essere 0)

| Parameter | Values |
|-----------|--------|
| TP | [0] SOLO (disabilitato - time exit è primario) |
| SL | ATR-based: [400%, 600%, 800%, 1000%] di `atr_signal_median` |
| SL (fallback) | [400%, 600%, 800%, 1000%] di magnitude |
| EXIT | [50%, 75%, 100%, 125%, 150%] di holding_bars (NO zero) |
| LEV | [1, 2, 3, 5, 10, 20, 40] |

**Combinazioni**: 1 × 4 × 5 × 7 = **140**

**Rationale SL ATR-based**:
- Pattern validato con TP/SL infiniti (solo time exit)
- SL deve proteggere da perdite catastrofiche, non da noise
- `atr_signal_median` riflette volatilità storica quando pattern ha fired
- Multipliers 4-10x ATR danno spazio per oscillazioni normali

---

## Pattern-Centered Space (fallback)

Per PatStrat_* senza `execution_type`.

**Input dal pattern**:
- `base_tp_pct`: target_magnitude (es: 6%)
- `base_sl_pct`: tp × suggested_rr_ratio (default 2.0, es: 12%)
- `base_exit_bars`: holding_period (es: 20 bars)

**Espansione attorno ai valori validati**:

| Parameter | Values |
|-----------|--------|
| TP | [0] + [50%, 75%, 100%, 125%, 150%] del base → es: [0, 3%, 4.5%, 6%, 7.5%, 9%] |
| SL | [50%, 75%, 100%, 150%, 200%] del base → es: [6%, 9%, 12%, 18%, 24%] |
| EXIT | [0] + [50%, 100%, 150%, 200%] del base → es: [0, 10, 20, 30, 40] |
| LEV | [1, 2, 3, 5, 10, 20, 40] |

**Combinazioni**: 6 × 5 × 5 × 7 = 1050, minus invalide ≈ **1015**

---

## Absolute Space (AI Strategies)

Per Strategy_* (AI-generated).

**Fonte**: `parametric_constants.py` (range empirici per timeframe)

| Timeframe | SL range | TP range | Exit bars |
|-----------|----------|----------|-----------|
| 5m | 0.5-2% | 0-5% | 0-160 (13h) |
| 15m | 1-5% | 0-10% | 0-100 (25h) |
| 30m | 1.5-6% | 0-15% | 0-60 (30h) |
| 1h | 2-10% | 0-20% | 0-32 (32h) |
| 2h | 3-10% | 0-25% | 0-24 (48h) |

**Leverage**: [1, 2, 3, 5, 10, 20, 40] (tutti i TF)

**Combinazioni**: 5 × 6 × 5 × 7 = 1050, minus invalide ≈ **1015**

---

## Filtro Combinazioni Invalide

**Escluse**: `tp_pct=0 AND exit_bars=0`

**Motivo**: nessuna condizione di uscita tranne SL (no exit strategy)

**Invalide per TF**: ~35 combinazioni (5 SL × 1 TP × 1 exit × 7 lev)

---

## Numba Kernel: `_simulate_single_param_set`

### Position Sizing (Fixed Fractional)

```
risk_amount = equity × risk_pct (default 2%)
notional = risk_amount / sl_pct
margin_needed = notional / actual_leverage
```

### Diversification Cap (dynamic)

```
max_margin_per_trade = equity / max_open_positions
if margin_needed > max_margin_per_trade → cap to max_margin
Es: max_positions=10 → max 10% equity per trade → 10 trade possibili
```

### Leverage Cap (per-coin)

```
actual_lev = min(strategy_leverage, coin.max_leverage)
Es: BTC max=50x → usa fino a 40x, SHIB max=5x → usa max 5x
```

### Margin Tracking

```
margin_available = equity - margin_used
if margin_needed > margin_available → SKIP (simula exchange reject)
```

### Min Notional Check

```
if notional < 10 USDC → SKIP (Hyperliquid requirement)
```

### Execution Costs (da config)

- **Slippage**: `hyperliquid.slippage` (tipicamente 0.05%)
- **Fees**: `hyperliquid.fee_rate × 2` (entry + exit, tipicamente 0.045%)

---

## Metriche Calcolate: `_calc_metrics`

| Metrica | Calcolo |
|---------|---------|
| sharpe | Trade-based (non bar-by-bar), annualizzato. Cap: sqrt(250). Sanity: se total_return < 0, sharpe <= 0 |
| max_drawdown | (running_max - equity) / running_max, clamp [0, 1] |
| win_rate | n_wins / n_trades |
| expectancy | (WR × AvgWin%) - ((1-WR) × AvgLoss%). PnL salvato come % del notional |
| total_return | (equity_finale - iniziale) / iniziale |
| total_trades | Conteggio trade completati |

---

## Formula Score (per combo)

```
score = ( 0.50 × edge_norm      +   # expectancy su range 0-10%
          0.25 × sharpe_norm    +   # sharpe su range 0-3
          0.15 × win_rate       +   # già 0-1
          0.10 × stability      )   # 1 - max_drawdown
        × 100

Output: 0-100 (clamped)
```

---

## Threshold Filter (per ogni combo)

Da `config.yaml → backtesting.thresholds`:

| Threshold | Valore |
|-----------|--------|
| min_sharpe | 0.3 → sharpe >= 0.3 |
| min_win_rate | 0.35 → win_rate >= 35% |
| min_total_trades | 10 → total_trades >= 10 |
| min_expectancy | 0.002 → expectancy >= 0.2% per trade |
| max_drawdown | 0.50 → max_dd <= 50% |

Combinazioni che non passano TUTTI i threshold → **SCARTATE**

---

## Output

DataFrame ordinato per score DESC (solo combo che passano threshold):

| sl_pct | tp_pct | lev | exit | sharpe | max_dd | win_rate | score |
|--------|--------|-----|------|--------|--------|----------|-------|
| 2.0% | 5.0% | 3 | 20 | 1.82 | 0.15 | 0.58 | 72.4 |
| 1.5% | 3.0% | 5 | 50 | 1.65 | 0.18 | 0.55 | 68.2 |
| ... | ... | ... | ... | ... | ... | ... | ... |

→ **BEST COMBO (#1)** procede a IS backtest finale + OOS validation

---

## File Coinvolti

- `src/backtester/parametric_backtest.py` → ParametricBacktester class
- `src/backtester/parametric_constants.py` → PARAM_SPACE, LEVERAGE_VALUES
- `src/backtester/main_continuous.py` → `_run_parametric_backtest()`
