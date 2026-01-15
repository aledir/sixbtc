# Pipeline Overview - Schema Sintetico

Questo documento mostra la pipeline completa ad alto livello. Per i dettagli di ogni fase, vedi i file `PIPELINE_XX_*.md` corrispondenti.

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. GENERAZIONE (generator daemon)                               │
├─────────────────────────────────────────────────────────────────┤
│ • Genera base code (pattern/unger/pandas_ta/ai_free/ai_assigned)│
│ • Status: GENERATED                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. VALIDAZIONE (validator daemon)                               │
├─────────────────────────────────────────────────────────────────┤
│ • Syntax check                                                  │
│ • AST lookahead check                                           │
│ • Execution test                                                │
│ • Status: VALIDATED (o FAILED)                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. PARAMETRIC OPTIMIZATION (backtester - STEP 1)                │
├─────────────────────────────────────────────────────────────────┤
│ • Testa ~1015 combo SL × TP × leverage × exit_bars              │
│ • Threshold filter: sharpe≥0.3, WR≥0.35, exp≥0.002, DD≤0.50     │
│ • Se 0 combo passano → FAILED + DELETE                          │
│ • Output: BEST COMBO (params ottimali)                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. BACKTEST IN-SAMPLE (backtester - STEP 2)                     │
├─────────────────────────────────────────────────────────────────┤
│ • Backtest 120 giorni con best params (BacktestEngine)          │
│ • Filtra con 6 threshold (stessi di PARAMETRIC + CI):           │
│   - sharpe >= 0.3, win_rate >= 35%, expectancy >= 0.002         │
│   - max_drawdown <= 50%, trades >= min_trades_is[tf]            │
│   - CI <= max_ci_is (10%) - significatività statistica          │
│ • CI = 1.96 × √(WR × (1-WR) / N) - incertezza su win rate       │
│ • Se fallisce qualsiasi threshold → REJECTED + DELETE           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. BACKTEST OUT-OF-SAMPLE (backtester - STEP 3)                 │
├─────────────────────────────────────────────────────────────────┤
│ • Backtest 60 giorni OOS con STESSI params                      │
│ • Filtra con 6 threshold (stessi di IS + CI):                   │
│   - sharpe >= 0.3, win_rate >= 35%, expectancy >= 0.002         │
│   - max_drawdown <= 50%, trades >= min_trades_oos[tf]           │
│   - CI <= max_ci_oos (15%) - significatività statistica         │
│ • Degradation check: (IS_sharpe - OOS_sharpe) / IS_sharpe ≤ 50% │
│ • Se fallisce qualsiasi threshold → REJECTED + DELETE           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. SCORE CALCULATION (backtester - STEP 4)                      │
├─────────────────────────────────────────────────────────────────┤
│ • Final score = (IS × 40%) + (OOS × 60%) × bonus                │
│ • Score check: score ≥ min_score (40)                           │
│ • Se score < 40 → REJECTED                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. SHUFFLE TEST (backtester - STEP 5)                           │
├─────────────────────────────────────────────────────────────────┤
│ • Cached by base_code_hash (lookahead = proprietà del codice)   │
│ • 100 iterazioni: segnali reali vs shuffled                     │
│ • p-value < 0.05 = edge statisticamente significativo           │
│ • Se fallisce → REJECTED                                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. WFA FIXED PARAMS (backtester - STEP 6)                       │
├─────────────────────────────────────────────────────────────────┤
│ • 4 windows espandenti (25%, 50%, 75%, 100% del periodo IS)     │
│ • Backtest ogni window con STESSI params (no ri-ottimizzazione) │
│ • Ogni window deve avere expectancy ≥ 0.002                     │
│ • Tutte e 4 le windows devono essere profittevoli               │
│ • Se fallisce → REJECTED                                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8.5 ROBUSTNESS CHECK (backtester - STEP 6.5)                    │
├─────────────────────────────────────────────────────────────────┤
│ • Formula: 0.50*oos_ratio + 0.35*trade_score + 0.15*simplicity  │
│ • oos_ratio = OOS_Sharpe / IS_Sharpe (generalization)           │
│ • trade_score = total_trades / 150 (statistical significance)   │
│ • simplicity = 1 / num_indicators (overfitting resistance)      │
│ • Threshold: robustness >= 0.80                                 │
│ • Se fallisce → resta VALIDATED, non entra in pool              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 9. POOL ENTRY (backtester - STEP 7)                             │
├─────────────────────────────────────────────────────────────────┤
│ • Pool max size: 300 strategie                                  │
│ • Se pool pieno: compete con worst, evict se meglio             │
│ • Status: ACTIVE                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 10. ROTATION → LIVE (rotator daemon)                            │
├─────────────────────────────────────────────────────────────────┤
│ • Rotator seleziona top N da ACTIVE pool                        │
│ • Deploy su subaccount Hyperliquid                              │
│ • Status: LIVE                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Indice Documenti Pipeline

| File | Contenuto |
|------|-----------|
| [PIPELINE_OVERVIEW.md](PIPELINE_OVERVIEW.md) | Schema sintetico (questo file) |
| [PIPELINE_01_GENERATOR.md](PIPELINE_01_GENERATOR.md) | Generator daemon e strategy sources |
| [PIPELINE_02_VALIDATOR.md](PIPELINE_02_VALIDATOR.md) | Validation pipeline (syntax, AST, execution) |
| [PIPELINE_03_PARAMETRIC.md](PIPELINE_03_PARAMETRIC.md) | Parametric optimization |
| [PIPELINE_04_BACKTEST_IS.md](PIPELINE_04_BACKTEST_IS.md) | Backtest In-Sample |
| [PIPELINE_05_BACKTEST_OOS.md](PIPELINE_05_BACKTEST_OOS.md) | Backtest Out-of-Sample |
| [PIPELINE_06_SCORE.md](PIPELINE_06_SCORE.md) | Score calculation |
| [PIPELINE_07_SHUFFLE.md](PIPELINE_07_SHUFFLE.md) | Shuffle test (lookahead detection) |
| [PIPELINE_08_WFA.md](PIPELINE_08_WFA.md) | Walk-Forward Analysis |
| [PIPELINE_08B_ROBUSTNESS.md](PIPELINE_08B_ROBUSTNESS.md) | Robustness Check (final gate) |
| [PIPELINE_09_POOL.md](PIPELINE_09_POOL.md) | Pool entry (leaderboard) |
| [PIPELINE_10_ROTATION.md](PIPELINE_10_ROTATION.md) | Rotation to LIVE |
| [PIPELINE_AUX.md](PIPELINE_AUX.md) | Flussi ausiliari (data, retest, sync, etc.) |
| [RISK.md](RISK.md) | Risk management e emergency stops |

## Strategy Status Lifecycle

```
GENERATED → VALIDATED → ACTIVE → LIVE → RETIRED
     ↓           ↓          ↓
  (DELETE)   (DELETE)   (RETIRED)
```
