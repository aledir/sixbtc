# Guida Completa ai Parametri

Questa pagina spiega TUTTI i parametri di `config/config.yaml`, cosa fanno, perché hanno quei valori, e cosa succede se li cambi.

---

## Come Leggere Questa Guida

Ogni parametro è documentato così:

| Campo | Significato |
|-------|-------------|
| **Valore** | Il valore attuale nel tuo config |
| **Cosa fa** | Spiegazione chiara |
| **Perché questo valore** | La logica dietro la scelta |
| **Se lo aumenti** | Conseguenze di un valore più alto |
| **Se lo diminuisci** | Conseguenze di un valore più basso |
| **Quando cambiarlo** | Scenari in cui ha senso modificarlo |

---

## Hyperliquid - Exchange

### `hyperliquid.dry_run`

| Campo | Valore |
|-------|--------|
| **Valore attuale** | `true` |
| **Cosa fa** | Flag MASTER che blocca TUTTO il trading reale. Quando `true`, gli ordini vengono loggati ma MAI inviati a Hyperliquid. |
| **Perché `true`** | Sicurezza. Mai fare trading accidentale. |
| **Se `false`** | Il sistema inizia a tradare con soldi veri. **ATTENZIONE**: assicurati che tutto funzioni prima. |
| **Quando cambiarlo** | Solo quando sei pronto per il live trading e hai verificato che le strategie funzionano in paper trading. |

!!! danger "Prima di mettere `false`"
    1. Verifica che le strategie LIVE abbiano score > 40
    2. Controlla che i subaccount abbiano fondi
    3. Verifica che non ci siano emergency stops attivi
    4. Inizia con capital basso per testare

---

### `hyperliquid.subaccounts.count`

| Campo | Valore |
|-------|--------|
| **Valore attuale** | `8` |
| **Cosa fa** | Numero di subaccount da creare/gestire. Ogni subaccount può avere UNA strategia LIVE alla volta. |
| **Perché `8`** | Compromesso tra diversificazione e gestione. Con $500 totali, 8 subaccount = ~$60 ciascuno. |
| **Se lo aumenti** | Più strategie LIVE contemporaneamente, ma meno capitale per ciascuna. Più diversificazione, meno size per trade. |
| **Se lo diminuisci** | Meno strategie LIVE, più capitale per ciascuna. Trades più grandi, meno diversificazione. |
| **Quando cambiarlo** | Se aumenti il capitale totale, puoi aumentare i subaccount. Regola: almeno $50-100 per subaccount. |

```
Esempio con $500 totale:
- 8 subaccount = $62.50 ciascuno ✓
- 10 subaccount = $50 ciascuno (minimo)
- 5 subaccount = $100 ciascuno (più concentrato)
```

---

### `hyperliquid.funds`

Gestione automatica fondi tra master e subaccount.

#### `min_operational_usd: 150`

| Campo | Valore |
|-------|--------|
| **Cosa fa** | Quando un subaccount scende sotto $150, triggera un topup automatico dal master. |
| **Perché `150`** | Serve margine per aprire posizioni. Con leva 5x e risk 2%, servono circa $100-150 per trade normali. |
| **Se lo aumenti** | Topup più frequenti, subaccount sempre "pieni". Più margine disponibile, meno rischio di skip trade per margin insufficiente. |
| **Se lo diminuisci** | Topup meno frequenti. Rischi di non avere margine quando serve. |

#### `topup_target_usd: 200`

| Campo | Valore |
|-------|--------|
| **Cosa fa** | Quando scatta il topup, riporta il subaccount a $200. |
| **Perché `200`** | Buffer sopra il minimo. Non vuoi topup ogni giorno. |
| **Formula** | `topup_amount = topup_target - current_balance` |

#### `master_reserve_usd: 100`

| Campo | Valore |
|-------|--------|
| **Cosa fa** | Il master wallet non scende MAI sotto $100. Protegge da drain completo. |
| **Perché `100`** | Riserva di emergenza. Se tutti i subaccount perdono, hai ancora $100. |

#### `min_tradeable_usd: 15`

| Campo | Valore |
|-------|--------|
| **Cosa fa** | Se un subaccount ha meno di $15, non può tradare (skip trade). |
| **Perché `15`** | Hyperliquid ha minimum notional di $10. Con fees e slippage, servono almeno $15 per essere sicuri. |

---

### `hyperliquid.fee_rate` e `slippage`

| Parametro | Valore | Cosa fa |
|-----------|--------|---------|
| `fee_rate` | `0.00045` | 0.045% taker fee. Usato nel backtest per simulare costi reali. |
| `slippage` | `0.0005` | 0.05% slippage stimato. Aggiunto al prezzo di entry/exit nel backtest. |

**Perché questi valori**: Sono i valori reali di Hyperliquid. Il backtest deve essere realistico.

**Se li aumenti**: Backtest più conservativo (meno profit). Strategie che passano sono più robuste.

**Se li diminuisci**: Backtest ottimistico. Rischi di avere strategie che sembrano buone ma perdono nel live.

!!! tip "Consiglio"
    Non toccare questi valori a meno che Hyperliquid cambi le fee.

---

## Risk Management

### `risk.fixed_fractional.risk_per_trade_pct`

| Campo | Valore |
|-------|--------|
| **Valore attuale** | `0.02` (2%) |
| **Cosa fa** | Percentuale del capitale che rischi per ogni trade. Se hai $500 e risk 2%, rischi $10 per trade. |
| **Formula** | `risk_amount = equity * risk_pct` → `$500 * 0.02 = $10` |

**Perché 2%**: Standard nel trading. Abbastanza per crescere, non troppo per sopravvivere a losing streaks.

| Se rischi | 10 loss consecutive = | Recovery needed |
|-----------|----------------------|-----------------|
| 1% | -10% | +11% |
| 2% | -18% | +22% |
| 5% | -40% | +67% |
| 10% | -65% | +186% |

**Quando aumentarlo**: Mai oltre 5%. Aumenta solo se hai winrate > 60% e Sharpe > 2.

**Quando diminuirlo**: Se hai molti loss consecutivi, o se il capitale è basso e vuoi sopravvivere più a lungo.

---

### `risk.fixed_fractional.max_position_size_pct`

| Campo | Valore |
|-------|--------|
| **Valore attuale** | `0.20` (20%) |
| **Cosa fa** | Massima percentuale del capitale in una singola posizione. Cap assoluto. |
| **Perché `0.20`** | Anche con SL stretto, non vuoi mai più del 20% in un trade. Protegge da eventi estremi (gap, flash crash). |

**Esempio**:
```
Equity: $500
Max position: $500 * 20% = $100 notional
Con leva 5x: $100 notional richiede $20 margine
```

---

### `risk.limits.max_open_positions_per_subaccount`

| Campo | Valore |
|-------|--------|
| **Valore attuale** | `10` |
| **Cosa fa** | Massimo numero di posizioni aperte contemporaneamente per subaccount. |
| **Perché `10`** | Ogni subaccount ha UNA strategia. 10 posizioni = la strategia può avere fino a 10 coin in play. |

---

### Emergency Stops

Gli emergency stop sono protezioni automatiche che scattano quando qualcosa va storto.

#### `risk.emergency.max_portfolio_drawdown: 0.20`

| Campo | Valore |
|-------|--------|
| **Cosa fa** | Se il portfolio totale perde 20% dal picco, CHIUDE TUTTE le posizioni. |
| **Azione** | `force_close` - chiusura immediata di tutto |
| **Cooldown** | 48 ore + richiede rotation per reset |
| **Perché 20%** | Perdita significativa ma recuperabile. Oltre il 20%, la psicologia diventa difficile. |

**Se lo aumenti (es. 30%)**: Più tollerante. Rischi di perdere di più prima che scatti.

**Se lo diminuisci (es. 10%)**: Più sensibile. Scatta più spesso, potenzialmente durante normali oscillazioni.

!!! warning "Questo è un kill switch"
    Quando scatta, TUTTO si ferma. Devi aspettare 48h E fare una rotation prima di riprendere.

#### `risk.emergency.max_daily_loss: 0.10`

| Campo | Valore |
|-------|--------|
| **Cosa fa** | Se perdi 10% in un giorno, blocca NUOVE posizioni. Le esistenti continuano fino a SL/TP. |
| **Azione** | `halt_entries` - solo nuove entry bloccate |
| **Reset** | Automatico a mezzanotte UTC |
| **Perché 10%** | Giornata molto negativa. Meglio fermarsi e ricominciare domani. |

#### `risk.emergency.max_consecutive_losses: 10`

| Campo | Valore |
|-------|--------|
| **Cosa fa** | 10 loss di fila = blocca nuove entry. Segnale che il regime di mercato è cambiato. |
| **Perché 10** | Statisticamente improbabile con strategia funzionante. 10 loss = qualcosa non va. |
| **Cooldown** | 24 ore |

**Cosa fare quando scatta**:

1. Controlla i log della strategia
2. Verifica se il mercato è cambiato (volatilità, trend)
3. Considera di ritirare la strategia manualmente

---

## Backtest - I Parametri Più Importanti

Il backtest determina quali strategie passano. Questi parametri sono CRITICI.

### `backtesting.is_days` e `oos_days`

| Campo | Valore |
|-------|--------|
| `is_days` | `120` (4 mesi) |
| `oos_days` | `60` (2 mesi) |
| **Totale** | 180 giorni (6 mesi) |

**Come funziona**:
```
|<------ IS (120 giorni) ------>|<-- OOS (60 giorni) -->|
|        Training data          |    Validation data    |
|   Ottimizza parametri qui     |   Testa qui (no opt)  |
```

**Perché questi valori**:

- IS 120 giorni: Abbastanza dati per trovare pattern stabili
- OOS 60 giorni: Abbastanza recente per validare che funziona ORA

**Se aumenti IS**: Più dati per training, ma meno recenti. Strategie potrebbero essere "vecchie".

**Se aumenti OOS**: Test più lungo, ma IS più corto. Meno dati per trovare pattern.

!!! tip "Regola pratica"
    OOS dovrebbe essere 30-50% di IS. Il ratio attuale (60/120 = 50%) è corretto.

---

### `backtesting.min_trades`

| Timeframe | IS Min | OOS Min |
|-----------|--------|---------|
| 15m | 120 | 60 |
| 30m | 80 | 40 |
| 1h | 50 | 25 |
| 2h | 30 | 15 |

**Cosa fa**: Numero minimo di trade per considerare i risultati statisticamente validi.

**Perché valori diversi per TF**: Timeframe più alti = meno candele = meno opportunità di trade. I minimi sono scalati.

**Se li aumenti**: Strategie devono tradare di più. Filtri strategie rare ma potenzialmente buone.

**Se li diminuisci**: Accetti strategie con meno trade. RISCHIO: risultati potrebbero essere fortuna.

!!! warning "Trade count e significatività statistica"
    Con 30 trade, il confidence interval è ~35%. Con 100 trade, scende a ~20%.
    Meno trade = più rumore = meno affidabile.

---

### `backtesting.thresholds`

Questi sono i GATE che una strategia deve passare.

| Threshold | Valore | Significato |
|-----------|--------|-------------|
| `min_sharpe` | `0.3` | Sharpe ratio minimo. < 0.3 = troppo rumoroso. |
| `min_win_rate` | `0.35` | Win rate minimo 35%. Sotto = troppi loss. |
| `max_drawdown` | `0.50` | Max drawdown 50%. Sopra = troppo rischioso. |
| `min_total_trades` | `10` | Minimo assoluto trade. |
| `min_expectancy` | `0.002` | 0.2% minimo per trade. Sotto = non vale la pena. |

**Perché questi valori**:

- **Sharpe 0.3**: Molto basso, ma è solo il minimo. Lo score considera Sharpe nel ranking.
- **Win rate 35%**: Permette strategie trend-following che vincono poco ma vincono grosso.
- **Max DD 50%**: Alto, ma il backtest è normalizzato. Nel live con position sizing corretto, DD reale sarà molto minore.
- **Expectancy 0.2%**: $2 su $1000 per trade. Minimo per coprire fees e avere edge.

**Quando stringerli**:

- Se hai troppe strategie ACTIVE e vuoi solo le migliori
- Se noti che strategie con basso Sharpe performano male nel live

**Quando allargarli**:

- Se hai poche strategie e vuoi più varietà
- Se stai testando nuovi tipi di pattern

---

### `backtesting.out_of_sample.max_degradation`

| Campo | Valore |
|-------|--------|
| **Valore** | `0.50` (50%) |
| **Cosa fa** | Se le metriche OOS sono peggiori del 50% rispetto a IS, la strategia fallisce. |
| **Esempio** | IS Sharpe = 2.0, OOS Sharpe = 0.8 → degradation = 60% → FAIL |

**Perché 50%**: Un po' di degradazione è normale (il mercato cambia). Ma oltre 50% indica overfitting.

**Formula**:
```
degradation = (IS_metric - OOS_metric) / IS_metric
se degradation > 0.50 → FAIL
```

**Se lo stringi (es. 30%)**: Solo strategie molto stabili passano. Meno strategie, ma più robuste.

**Se lo allarghi (es. 70%)**: Più strategie passano. Rischi di avere strategie overfit.

---

### `backtesting.robustness`

Il robustness score è l'ULTIMO filtro prima che una strategia entri nel pool ACTIVE.

```yaml
robustness:
  min_threshold: 0.80
  weights:
    oos_ratio: 0.50        # 50% peso
    trade_significance: 0.35  # 35% peso
    simplicity: 0.15       # 15% peso
```

**Formula**:
```
robustness = 0.50 * (oos_sharpe / is_sharpe) +
             0.35 * min(total_trades / 150, 1) +
             0.15 * (1 - indicator_count / 5)
```

**Componenti**:

1. **OOS Ratio (50%)**: Quanto bene la strategia generalizza. OOS/IS Sharpe vicino a 1 = ottimo.

2. **Trade Significance (35%)**: Più trade = più significativo statisticamente. 150+ trade = score pieno.

3. **Simplicity (15%)**: Meno indicatori = meno overfitting. 1 indicatore = score pieno, 5 = zero.

**Esempio**:
```
Strategia A: OOS/IS=0.9, 200 trades, 2 indicatori
robustness = 0.50*0.9 + 0.35*1.0 + 0.15*0.6 = 0.45+0.35+0.09 = 0.89 ✓

Strategia B: OOS/IS=0.5, 80 trades, 4 indicatori
robustness = 0.50*0.5 + 0.35*0.53 + 0.15*0.2 = 0.25+0.19+0.03 = 0.47 ✗
```

---

## Scorer - Come Viene Calcolato lo Score

Lo score determina il RANKING nel pool ACTIVE e chi va LIVE.

```yaml
scorer:
  weights:
    expectancy: 0.40
    sharpe: 0.25
    win_rate: 0.10
    drawdown: 0.15
    recency: 0.10
```

**Formula completa**:
```
Score = (0.40 * E_norm + 0.25 * S_norm + 0.10 * WR_norm +
         0.15 * DD_norm + 0.10 * Rec_norm) * 100
```

**Normalizzazioni**:
```
E_norm = min(expectancy / 0.01, 1)     # 1% expectancy = 100
S_norm = min(sharpe / 2.0, 1)          # Sharpe 2.0 = 100
WR_norm = win_rate                      # 60% = 60
DD_norm = 1 - min(max_dd / 0.50, 1)    # 0% DD = 100, 50% DD = 0
Rec_norm = min(oos_sharpe/is_sharpe, 1) # OOS=IS = 100
```

**Perché questi pesi**:

| Componente | Peso | Motivazione |
|------------|------|-------------|
| Expectancy | 40% | L'edge reale. Quanto guadagni per trade. |
| Sharpe | 25% | Risk-adjusted return. Importante per leva. |
| Win Rate | 10% | Psicologico. Vincere spesso aiuta la disciplina. |
| Drawdown | 15% | Protezione. DD alto = rischio rovina. |
| Recency | 10% | Performance recente. Il mercato cambia. |

**Esempio di calcolo**:
```
Strategia: expectancy=0.8%, sharpe=1.5, WR=55%, DD=20%, OOS/IS=0.85

E_norm = min(0.008/0.01, 1) = 0.80
S_norm = min(1.5/2.0, 1) = 0.75
WR_norm = 0.55
DD_norm = 1 - min(0.20/0.50, 1) = 0.60
Rec_norm = min(0.85, 1) = 0.85

Score = (0.40*0.80 + 0.25*0.75 + 0.10*0.55 + 0.15*0.60 + 0.10*0.85) * 100
Score = (0.32 + 0.1875 + 0.055 + 0.09 + 0.085) * 100
Score = 73.75
```

---

## Active Pool - Il Leaderboard

```yaml
active_pool:
  max_size: 100
  min_score: 40
```

**Come funziona**:

1. Strategia passa tutti i test → calcola score
2. Se score >= 40 → entra nel pool ACTIVE
3. Pool ordinato per score (leaderboard)
4. Se pool > 100, le peggiori vengono eliminate
5. Rotator prende le top N dal leaderboard per LIVE

**Perché `max_size: 100`**: Con 8 subaccount, 100 = 12x buffer. Abbastanza varietà per rotation.

**Perché `min_score: 40`**: Score 40 = strategia decente ma non eccezionale. È il minimo accettabile.

---

## Rotator - Chi Va LIVE

```yaml
rotator:
  check_interval_minutes: 15
  max_live_strategies: 8
  min_pool_size: 30
  selection:
    max_per_type: 3
    max_per_timeframe: 3
    max_per_direction: 5
```

### `min_pool_size: 30`

**Cosa fa**: Il sistema NON mette strategie LIVE finché non ci sono almeno 30 ACTIVE.

**Perché**: Assicura diversificazione. Con meno di 30, potresti avere tutte strategie simili.

### Diversification Limits

| Limite | Valore | Significato |
|--------|--------|-------------|
| `max_per_type` | 3 | Max 3 strategie dello stesso tipo (MOM, REV, etc) |
| `max_per_timeframe` | 3 | Max 3 strategie sullo stesso TF (15m, 1h, etc) |
| `max_per_direction` | 5 | Max 5 LONG, 5 SHORT, 5 BIDI |

**Esempio**: Se hai già 3 strategie MOM LIVE, la prossima MOM nel leaderboard viene saltata.

---

## Monitor - Retirement Policy

```yaml
monitor:
  check_interval_minutes: 15
  retirement:
    min_score: 35
    max_score_degradation: 0.40
    max_drawdown: 0.25
    min_trades: 10
    max_consecutive_losses: 10
```

### Quando una strategia viene ritirata

| Condizione | Threshold | Significato |
|------------|-----------|-------------|
| Score basso | < 35 | Performance live scadente |
| Degradazione | > 40% | Live molto peggio di backtest |
| Drawdown | > 25% | Sta perdendo troppo |
| Consecutive losses | >= 10 | Regime di mercato cambiato |

**Cosa succede al retirement**:

1. Status → RETIRED
2. Subaccount liberato
3. Posizioni chiuse (o lasciate a SL/TP)
4. Prossimo ciclo rotation: nuova strategia ACTIVE prende il posto

---

## Generation - Sorgenti Strategie

```yaml
generation:
  strategy_sources:
    pattern:
      enabled: false
    pattern_gen:
      enabled: true
    unger:
      enabled: true
    pandas_ta:
      enabled: true
```

### Tipi di Sorgente

| Sorgente | Prefisso | Descrizione |
|----------|----------|-------------|
| `pattern` | PatStrat_ | Da pattern-discovery API (disabilitato) |
| `pattern_gen` | PGnStrat_ | Generator interno con composizione smart |
| `unger` | UngStrat_ | Strategie regime-coherent (Unger method) |
| `pandas_ta` | PtaStrat_ | Combinazioni di indicatori pandas-TA |
| `ai_free` | AIFStrat_ | AI sceglie liberamente (se abilitato) |
| `ai_assigned` | AIAStrat_ | AI con indicatori assegnati (se abilitato) |

### `pattern_gen.genetic`

```yaml
pattern_gen:
  genetic:
    enabled: true
    min_pool_score: 40
    min_pool_size: 50
    smart_ratio: 0.70
    genetic_ratio: 0.30
```

**Come funziona**:

1. Quando pool ACTIVE >= 50 strategie con score >= 40
2. 70% delle nuove strategie sono "smart" (template + parametric)
3. 30% sono "genetic" (crossover + mutation da strategie esistenti)

**Perché**: Le strategie migliori "si riproducono". Evolution-inspired optimization.

---

## Pipeline - Flow Control

```yaml
pipeline:
  queue_limits:
    generated: 100
    validated: 100
  validated_backpressure:
    low_threshold: 20
    high_threshold: 50
```

### Backpressure System

Il sistema si auto-regola per non sovraccaricare.

```
Generator ──→ Queue GENERATED (max 100) ──→ Validator
                                                 ↓
Rotator ←── Pool ACTIVE (max 100) ←── Queue VALIDATED (max 100) ←── Backtester
```

**Come funziona**:

1. Se VALIDATED queue > 50 → Generator PAUSA
2. Se VALIDATED queue < 20 → Generator RIPRENDE
3. Hysteresis (20-50) evita oscillazioni continue

**Perché**: Se backtester è lento, non ha senso generare 1000 strategie che aspettano.

---

## Trading - Live Execution

```yaml
trading:
  total_capital: 500
  min_volume_24h: 1000000
  pairs_mode: 'strict'
```

### `min_volume_24h: 1000000`

**Cosa fa**: Trade solo su coin con volume 24h > $1M.

**Perché**: Volume basso = slippage alto = costi nascosti.

### `pairs_mode: 'strict'`

**Opzioni**:

- `strict`: Trade SOLO coppie che sono state backtested
- `adaptive`: Trade anche coppie simili
- `intersection`: Trade solo coppie presenti in tutti i dataset

**Consiglio**: Tieni `strict`. Non vuoi tradare coppie mai testate.

---

## Funding Rates

```yaml
funding:
  enabled: true
  backfill_days: 180
  fallback_hourly_rate: 0.0001
```

**Cosa fa**: Applica funding rates nel backtest per simulare costi reali di posizioni overnight.

**Perché abilitato**: Su Hyperliquid paghi/ricevi funding ogni 8 ore. Ignorarlo falsifica il backtest.

---

## Scheduler - Manutenzione Automatica

Tutti i task girano alle 01:00-02:00 UTC.

| Task | Cosa fa | Intervallo |
|------|---------|------------|
| `daily_restart_services` | Restart tutti i servizi | 24h |
| `renew_agent_wallets` | Rinnova wallet se scadono in < 30 giorni | 24h |
| `check_subaccount_funds` | Topup subaccount se sotto minimo | 24h |
| `cleanup_tmp_dir` | Pulisce /tmp vecchio > 24h | 24h |
| `cleanup_old_events` | Elimina eventi > 7 giorni | 24h |
| `cleanup_stale_strategies` | Elimina strategie bloccate > 1 giorno | 24h |
| `cleanup_old_failed` | Elimina FAILED > 7 giorni | 24h |
| `cleanup_old_retired` | Elimina RETIRED > 7 giorni | 24h |
| `sync_balances` | Sincronizza balance da Hyperliquid | 5 min |

---

## Checklist Configurazione

### Prima di andare LIVE

- [ ] `hyperliquid.dry_run` = `true` inizialmente
- [ ] `hyperliquid.user_address` = il tuo wallet
- [ ] `trading.total_capital` = capitale reale
- [ ] Verifica pool ACTIVE >= 30 strategie
- [ ] Verifica subaccount hanno fondi
- [ ] Nessun emergency stop attivo

### Tuning Conservativo (meno rischio)

```yaml
risk:
  fixed_fractional:
    risk_per_trade_pct: 0.01  # 1% invece di 2%
backtesting:
  thresholds:
    min_sharpe: 0.5           # Più alto
    min_win_rate: 0.40        # Più alto
monitor:
  retirement:
    max_drawdown: 0.15        # Più sensibile
```

### Tuning Aggressivo (più rischio, più reward)

```yaml
risk:
  fixed_fractional:
    risk_per_trade_pct: 0.03  # 3%
backtesting:
  robustness:
    min_threshold: 0.70       # Più permissivo
active_pool:
  min_score: 35               # Accetta strategie peggiori
```

!!! danger "Attenzione"
    Tuning aggressivo = più drawdown, più volatilità, potenzialmente più rovina.
