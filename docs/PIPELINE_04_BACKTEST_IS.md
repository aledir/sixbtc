# 4. Backtest IS (In-Sample) Finale

**Obiettivo**: Eseguire backtest completo sui dati IN-SAMPLE con i best params dalla parametric optimization. Produce le metriche ufficiali IS.

**Daemon**: `src/backtester/main_continuous.py`
**Input**:
- strategy_instance con params applicati (sl_pct, tp_pct, lev, exit)
- is_data: 120 giorni di dati (Dict symbol -> DataFrame)
- best_params da PARAMETRIC OPTIMIZATION (best combo)

**Output**: is_result → procede a BACKTEST OOS

---

## Applicazione Best Params

Prima del backtest, i best params da PARAMETRIC vengono applicati:

```python
strategy_instance.sl_pct = best_params['sl_pct']         # 0.02
strategy_instance.tp_pct = best_params['tp_pct']         # 0.05
strategy_instance.leverage = best_params['leverage']     # 3
strategy_instance.exit_after_bars = best_params['exit_bars']  # 20
```

Questi sono i best params dalla parametric optimization (combo #1 per score, che ha passato threshold + robustness).

---

## _run_multi_symbol_backtest()

Portfolio backtest con vincoli realistici:

- **Max concurrent positions**: da config (default 10)
- **Shared capital pool**: tutte le posizioni condividono equity
- **Position priority**: ordine temporale dei segnali
- **Multi-symbol**: tutti i coins assegnati alla strategia

### Filtro dati

- `min_bars = 100` (default per IS)
- Simboli con < 100 bars → esclusi
- Se nessun simbolo valido → return `{total_trades: 0}`

### Engine

`BacktestEngine.backtest()`
- Usa parametri timeframe per Sharpe annualization corretta
- Simula margin tracking, fees, slippage

---

## Metriche Output (is_result)

| Metrica | Descrizione |
|---------|-------------|
| sharpe_ratio | Annualizzato, trade-based |
| win_rate | n_wins / total_trades |
| expectancy | (WR * AvgWin%) - ((1-WR) * AvgLoss%) |
| max_drawdown | Peak-to-trough massimo |
| total_trades | Numero trade completati |
| total_return | (equity_finale - iniziale) / iniziale |
| avg_trade_pnl | PnL medio per trade |
| profit_factor | gross_profit / gross_loss |

---

## Validazione IS (5 Threshold)

IS applica gli **STESSI 5 threshold di PARAMETRIC**:

1. `sharpe >= 0.3`
2. `win_rate >= 35%`
3. `expectancy >= 0.002`
4. `max_drawdown <= 50%`
5. `trades >= min_trades_is[timeframe]`

Se fallisce qualsiasi threshold:
- **DELETE strategy** (reason: "IS sharpe/wr/exp/dd/trades too low/high")

> Questo cattura discrepanze tra kernel PARAMETRIC e BacktestEngine (~2-3% delle strategie potrebbero avere metriche leggermente diverse a causa di differenze nell'allineamento dati)

---

## Differenza da PARAMETRIC

| PARAMETRIC | IS FINALE |
|------------|-----------|
| ~1015 combinazioni | 1 sola (best params) |
| Numba kernel veloce | BacktestEngine completo |
| Metriche aggregate | Metriche dettagliate + equity curve |
| Per trovare best | Per metriche ufficiali |

- Il parametric usa kernel Numba ottimizzato per velocità
- IS finale usa BacktestEngine per metriche complete e accurate

---

## Output

- `is_result`: Dict con tutte le metriche IS
- Se `total_trades == 0` → **DELETE strategy**
- Altrimenti → procede a **BACKTEST OOS**

---

## File Coinvolti

- `src/backtester/main_continuous.py` → `_run_multi_symbol_backtest()`
- `src/backtester/backtest_engine.py` → `BacktestEngine.backtest()`
