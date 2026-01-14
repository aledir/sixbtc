# Flussi Ausiliari (Support Flows)

Questa sezione documenta i flussi ausiliari che supportano la pipeline principale.
Non fanno parte del flusso GENERATED → LIVE, ma sono essenziali per il funzionamento.

---

## Scheduler Tasks (Quick Reference)

Tutti i task di manutenzione giornaliera eseguono tra 01:00 e 02:00 UTC (low-activity window), intervallati ogni 5 minuti.

| # | Task | Orario UTC | Descrizione |
|---|------|------------|-------------|
| 1 | **daily_restart_services** | 01:00 | Riavvia tutti i servizi sixbtc via supervisorctl (tranne lo scheduler). Previene memory leak. |
| 2 | **refresh_market_regimes** | 01:05 | Ricalcola regime di mercato (TREND/REVERSAL/MIXED) per tutti i coin attivi. |
| 3 | **renew_agent_wallets** | 01:10 | Verifica credenziali agent wallet Hyperliquid in scadenza (entro 30gg) e le rinnova. |
| 4 | **check_subaccount_funds** | 01:15 | Controlla balance subaccount. Se sotto soglia, esegue topup dal master wallet. |
| 5 | **cleanup_tmp_dir** | 01:20 | Elimina file temporanei in `/tmp` più vecchi di 24h. |
| 6 | **cleanup_old_events** | 01:25 | Elimina record `StrategyEvent` più vecchi di 7gg dal DB. |
| 7 | **cleanup_stale_strategies** | 01:30 | Elimina strategie bloccate in GENERATED/VALIDATED da più di 1 giorno. |
| 8 | **cleanup_old_failed** | 01:35 | Elimina strategie FAILED più vecchie di 7gg dal DB. |
| 9 | **cleanup_old_retired** | 01:40 | Elimina strategie RETIRED (evicted dal pool) più vecchie di 7gg dal DB. |
| 10 | **update_pairs** | 01:45, 13:45 | Aggiorna lista coin tradabili da Hyperliquid × Binance. |
| 11 | **download_data** | 02:00, 14:00 | Scarica dati OHLCV da Binance per tutti i coin attivi. |
| - | **cleanup_zombie_processes** | ogni 3h | Trova e uccide processi Python zombie/orfani di sixbtc. |
| - | **cleanup_stale_processing** | ogni 30min | Rilascia strategie bloccate in processing > 30 min. |
| - | **refresh_data_cache** | ogni 4h | Preload BTC data per tutti i TF configurati (mantiene cache calda). |

---

## Riepilogo Flussi

| Flow | Frequenza | Descrizione |
|------|-----------|-------------|
| **A1. CoinRegistry + PairsUpdater** | 2x/day (01:45, 13:45 UTC) | Aggiorna lista coin tradabili |
| **A2. BinanceDownloader** | 2x/day (02:00, 14:00 UTC) | Scarica dati OHLCV |
| **A3. Re-Backtest ACTIVE** | quando backtester idle | Mantiene pool "fresco" |
| **A4. TradeSync** | ogni 15s (Monitor cycle) | Sincronizza trade da Hyperliquid |
| **A5. Metrics Collector** | ogni 60s | Raccoglie metriche pipeline |
| **A6. Scheduler Tasks** | vari (30min - 24h) | Task di manutenzione |
| **A7. Pool Manager** | ad ogni pool entry | Gestisce leaderboard ACTIVE |

---

## A1. Coin Registry & Pairs Update

**Obiettivo**: Mantenere aggiornata la lista dei coin tradabili.

### Pairs Updater (scheduled)

**Schedule**: 01:45 e 13:45 UTC

`PairsUpdater.update()`:

1. **Fetch Hyperliquid markets**
   - GET `/info` type=metaAndAssetCtxs
   - Estrae: symbol, volume_24h, price, max_leverage

2. **Intersezione con Binance**
   - Solo symbol disponibili su ENTRAMBI gli exchange
   - Binance = fonte dati OHLCV, Hyperliquid = esecuzione

3. **Filter + Sort**
   - volume_24h >= min_volume_usd (config)
   - ORDER BY volume_24h DESC
   - LIMIT top_pairs_count (default 50)

4. **Upsert to DB** (coins table)
   - Nuovi coin: INSERT
   - Esistenti: UPDATE (volume, price, leverage)
   - Non più in top N: is_active = false

### Coin Registry (runtime cache)

`CoinRegistry`: Singleton thread-safe con cache

**Cache policy**:
- TTL: 5 minuti (CACHE_TTL_SECONDS)
- Auto-invalidation: se coins.updated_at > cache_time

**API**:
- `get_active_pairs(min_volume, limit)` → List[str]
- `get_coin(symbol)` → CoinInfo
- `get_max_leverage(symbol)` → int
- `is_tradable(symbol)` → bool
- `get_tradable_for_strategy(...)` → List[str]

**Usato da**: Backtester, Executor, Rotator, Generator

### Config

```yaml
data_scheduler:
  enabled: true
  top_pairs_count: 200
  min_volume_usd: 0
  update_pairs_hours: [1, 13]     # Run at 01:45 and 13:45 UTC
  update_pairs_minute: 45
  download_data_hours: [2, 14]    # Run at 02:00 and 14:00 UTC
  download_data_minute: 0
```

### File Coinvolti

- `src/data/pairs_updater.py` → PairsUpdater
- `src/data/coin_registry.py` → CoinRegistry (singleton)
- `src/data/data_scheduler.py` → DataScheduler (orchestration)

---

## A2. Binance Data Downloader

**Obiettivo**: Scaricare e mantenere aggiornati i dati OHLCV da Binance.

### Download Flow (scheduled)

**Schedule**: 02:00 e 14:00 UTC (15min dopo update_pairs)

`BinanceDownloader.download_for_pairs()`:

1. Legge coin attivi da CoinRegistry

2. Per ogni symbol × timeframe:
   - Check cache esistente
   - Parquet: `data/binance/{symbol}_{tf}.parquet`
   - Metadata: `data/binance/{symbol}_{tf}.meta.json`

3. Determina azione:
   - No cache → download da listing date
   - Cache completa → forward update solo
   - Cache incompleta → backfill + forward update

4. Download via CCXT (Binance Futures)
   - Paginated (1000 candle per request)
   - Rate limited automatico

5. Validate + Save
   - OHLCV validation (no negative, high >= low)
   - Atomic write (temp file + rename)
   - Update metadata

### Auto-Healing Features

**Corrupted file detection**:
- File size < MIN_PARQUET_SIZE (12 bytes) → delete + re-download
- Parquet read error → delete + re-download
- Invalid OHLCV structure → delete + re-download

**Gap detection + fill**:
- `detect_gaps(df, timeframe)` → List[(start, end, missing_count)]
- `fill_gaps(symbol, timeframe)` → backfill missing candles
- CLI: `python -m src.data.binance_downloader --fill-gaps`

**Metadata tracking (is_full_history)**:
- true = cache contiene TUTTI i dati da listing date
- false = cache parziale (es. solo ultimi 30 giorni)

### Storage Format

**Location**: `data/binance/`

**Files per symbol/timeframe**:
- `{symbol}_{tf}.parquet` # OHLCV data
- `{symbol}_{tf}.meta.json` # Metadata

**Parquet columns**:
- timestamp (datetime64[ns, UTC])
- open, high, low, close (float64)
- volume (float64)

### CLI Usage

```bash
# Download all active coins, all timeframes
python -m src.data.binance_downloader

# Download specific symbols
python -m src.data.binance_downloader -s BTC -s ETH

# Verify data integrity
python -m src.data.binance_downloader --verify

# Fill gaps in existing data
python -m src.data.binance_downloader --fill-gaps
```

### File Coinvolti

- `src/data/binance_downloader.py` → BinanceDataDownloader
- `src/data/data_scheduler.py` → DataScheduler.download_data()
- `src/backtester/data_loader.py` → BacktestDataLoader (consumer)

---

## A3. Re-Backtest ACTIVE Strategies

**Obiettivo**: Mantenere il pool ACTIVE "fresco" ri-testando periodicamente le strategie per verificare che l'edge sia ancora valido.

### Re-Test Flow (FIFO)

**Trigger**: Backtester idle (no VALIDATED in queue)
**Config**: `backtesting.retest.interval_days` (default: 3)

1. **`_get_strategy_needing_retest()`**
   - Query: ACTIVE WHERE last_backtested_at < (now - interval_days)
   - ORDER BY last_backtested_at ASC (FIFO: oldest first)
   - LIMIT 1

2. **`_retest_strategy()`**
   - Solo assigned TF (non tutti i TF come primo backtest)
   - Stessi parametri (no parametric optimization)
   - IS (120 giorni) + OOS (60 giorni) backtest

3. **Validation**
   - Same OOS validation as initial backtest
   - Se fallisce OOS → RETIRED

4. **Score recalculation**
   - Stesso BacktestScorer
   - Nuovo score basato su dati recenti

5. **`PoolManager.revalidate_after_retest()`**
   - Se new_score < min_score → RETIRED
   - Se new_score < min(pool) AND pool full → RETIRED
   - Altrimenti: update score + last_backtested_at

### Perché serve il Re-Test

**Market regime change**:
- Strategia momentum funzionava in trend, ora mercato laterale
- Pattern che funzionava non genera più segnali
- Volatilità cambiata, SL/TP non più ottimali

**Data freshness**:
- Score calcolato 30 giorni fa su dati vecchi
- Re-test usa dati recenti → score più rappresentativo

**Pool quality**:
- Evita "zombie strategies" che occupano slot
- Libera spazio per strategie nuove e migliori

### Differenze Re-Test vs Primo Backtest

| Aspetto | Primo Backtest | Re-Test |
|---------|----------------|---------|
| Timeframes | Tutti (4 TF) | Solo assigned TF |
| Parametric opt | Sì (~1015 combo) | No (stessi params) |
| Shuffle test | Sì | No |
| WFA validation | Sì (4 windows) | No |
| Pool entry | Compete per slot | Già in pool |
| Failure action | DELETE | RETIRED |

Re-test è più veloce: ~10x meno costoso del primo backtest

### Config

```yaml
backtesting:
  retest:
    interval_days: 3      # Re-test ogni 3 giorni
```

### File Coinvolti

- `src/backtester/main_continuous.py` → `_get_strategy_needing_retest()`
- `src/backtester/main_continuous.py` → `_retest_strategy()`
- `src/scorer/pool_manager.py` → `revalidate_after_retest()`

---

## A4. Trade Sync (LIVE)

**Obiettivo**: Sincronizzare i trade chiusi da Hyperliquid al database per calcolare le metriche di performance live.

### Sync Flow

**Trigger**: ogni ciclo Monitor (15 secondi)

`TradeSync.sync_cycle()`:

1. **Monitor posizioni via WebSocket** (webData2)
   - Mantiene `_last_positions` dict
   - Confronta con posizioni attuali

2. **Detect closed positions**
   - Posizione in `_last_positions` ma non in current → CHIUSA

3. **Fetch fills via HTTP API**
   - GET fills per symbol
   - Lookback: fills_lookback_days (default 7)

4. **Reconstruct trade**
   - Entry fills + Exit fill
   - Calcola: entry_price, exit_price, pnl, duration

5. **Update Trade record nel DB**
   - Se Trade esiste: update con exit data
   - Se non esiste: create completo

### Principio: Hyperliquid è Source of Truth

- Exchange state è **CANONICO** per posizioni, ordini, balance
- Database è **AUDIT TRAIL** e metadata only
- In caso di discrepanza, **Hyperliquid PREVALE** sempre

**Implicazioni**:
- Trade table può essere ricostruita da fills
- Non ci sono "lost trades" (exchange li ha sempre)
- Sync può recuperare trade mancanti (lookback)

### Config

```yaml
hyperliquid:
  trade_sync:
    enabled: true
    fills_lookback_days: 7
```

### File Coinvolti

- `src/executor/trade_sync.py` → TradeSync
- `src/monitor/main_continuous.py` → chiama `sync_cycle()` ogni iterazione

---

## A5. Metrics Collector

**Obiettivo**: Raccogliere snapshot delle metriche pipeline per monitoring e trend analysis.

### Collection Flow

**Interval**: 60 secondi

`MetricsCollector.collect_snapshot()`:

**[QUEUE]** Strategy counts by status
- GENERATED, VALIDATED, ACTIVE, LIVE, RETIRED counts
- Utilization % vs queue limits

**[FUNNEL 24H]** Conversion rates
- generated → validated rate
- validated → active rate
- active → live rate

**[TIMING]** Processing time per stage
- Avg seconds in GENERATED
- Avg seconds in VALIDATED
- Avg seconds in backtest

**[FAILURES 24H]** Rejection counts + reasons
- validation_failed: syntax, lookahead, execution
- backtest_failed: no trades, OOS degraded, shuffle failed

**[BACKPRESSURE]** Queue saturation
- OK: < 80% capacity
- WARNING: 80-95%
- OVERFLOW: > 95%

**[POOL]** ACTIVE pool statistics
- count, min/max/avg score
- quality metrics (sharpe, win_rate)
- breakdown by source (pattern, unger, pandas_ta, ai_free, ...)

**[RETEST 24H]** Pool freshness
- Strategies re-tested in last 24h
- Pass/fail rate

**[LIVE]** Live trading stats
- Strategies currently LIVE
- Rotations in last 24h

### Storage

**Table**: `pipeline_metrics_snapshots`

**Columns**:
- timestamp
- overall_status (HEALTHY, WARNING, CRITICAL)
- queue_* (counts per status)
- utilization_* (percentages)
- throughput_* (items/minute)
- success_rate_* (per stage)
- avg_sharpe, avg_win_rate (pool quality)

### File Coinvolti

- `src/metrics/collector.py` → MetricsCollector
- `src/database/models.py` → PipelineMetricsSnapshot
- `src/api/routes/metrics.py` → API endpoints
- `web/src/pages/PipelineHealth.tsx` → Dashboard UI

---

## A6. Scheduler Tasks (Maintenance)

**Obiettivo**: Task di manutenzione schedulati che mantengono il sistema pulito e funzionante.

### Schedule Overview

Tutti i task giornalieri eseguono tra **01:00 e 02:00 UTC**, intervallati ogni 5 minuti.
Questa finestra è scelta perché è un periodo di bassa attività per i mercati crypto.

### Task Giornalieri (01:00-01:45 UTC)

| # | Task | Orario | Descrizione |
|---|------|--------|-------------|
| 1 | **daily_restart_services** | 01:00 | Riavvia servizi sixbtc via supervisorctl (tranne scheduler) |
| 2 | **refresh_market_regimes** | 01:05 | Ricalcola regime (TREND/REVERSAL/MIXED) per coin attivi |
| 3 | **renew_agent_wallets** | 01:10 | Rinnova agent wallet in scadenza (entro 30gg) |
| 4 | **check_subaccount_funds** | 01:15 | Topup subaccount da master se balance basso |
| 5 | **cleanup_tmp_dir** | 01:20 | Elimina file /tmp > 24h |
| 6 | **cleanup_old_events** | 01:25 | Elimina StrategyEvent > 7 giorni |
| 7 | **cleanup_stale_strategies** | 01:30 | Elimina strategie stuck in GENERATED/VALIDATED > 1 giorno |
| 8 | **cleanup_old_failed** | 01:35 | Elimina strategie FAILED > 7 giorni |
| 9 | **cleanup_old_retired** | 01:40 | Elimina strategie RETIRED (evicted) > 7 giorni |

### Task Data Scheduler

| # | Task | Orario | Descrizione |
|---|------|--------|-------------|
| 10 | **update_pairs** | 01:45, 13:45 | Aggiorna lista coin tradabili (vedi A1) |
| 11 | **download_data** | 02:00, 14:00 | Scarica OHLCV da Binance (vedi A2) |

### Task Periodici

**cleanup_zombie_processes** (ogni 3h)
- Trova processi Python zombie/orfani
- Kill processi bloccati o duplicati
- Protegge processi gestiti da supervisor

**cleanup_stale_processing** (ogni 30 min)
- Rilascia strategy bloccate in processing > 30 min
- Resetta processing_by = NULL, processing_started_at = NULL
- Previene deadlock da crash

**refresh_data_cache** (ogni 4h)
- Preload BTC data per tutti i TF configurati
- Mantiene cache calda per backtester

### Dettaglio Task

**daily_restart_services**
- Restart di tutti i servizi sixbtc (tranne scheduler stesso)
- Previene memory leaks, stale connections
- Usa supervisorctl per restart controllato

**renew_agent_wallets**
- Verifica credenziali agent wallet Hyperliquid
- Se scadenza < 30 giorni → rinnova automaticamente
- Crea nuovo agent wallet via HL API
- Salva in Credential table

**check_subaccount_funds**
- Verifica balance ogni subaccount
- Se < min_operational_usd (default $50) → topup da master
- Target: topup_target_usd (default $100)
- Policy: MAI transfer tra subaccount
- Rispetta master_reserve_usd

**cleanup_tmp_dir**
- Pulisce /tmp da file temporanei vecchi
- max_age_hours: 24 (default)
- Skip file di sistema

**cleanup_old_events**
- Elimina record StrategyEvent > max_age_days
- Tabella audit che cresce velocemente
- Default: 7 giorni retention

**cleanup_stale_strategies**
- Strategie stuck in GENERATED o VALIDATED
- Probabilmente orfane (crash validator/backtester)
- Safe to delete: non saranno mai processate
- Default: > 1 giorno = stale

**refresh_market_regimes**
- Ricalcola regime di mercato per tutti i coin attivi
- Usa metodo Unger: confronta profitability di breakout vs reversal test
- Risultati: TREND, REVERSAL, o MIXED
- Salvati in `market_regimes` table
- Usati da Unger Generator per generare strategie regime-appropriate

**update_pairs** (Data Scheduler)
- Fetch markets da Hyperliquid API
- Intersezione con Binance (per dati OHLCV)
- Filter per volume minimo + sort per volume
- Upsert in `coins` table
- Dettagli in sezione A1

**download_data** (Data Scheduler)
- Scarica OHLCV da Binance per tutti i coin attivi
- Esegue 5 min dopo update_pairs
- Supporta backfill + forward update
- Auto-healing per file corrotti
- Dettagli in sezione A2

### Config

```yaml
scheduler:
  tasks:
    cleanup_zombie_processes:
      enabled: true
      interval_hours: 3

    daily_restart_services:
      enabled: true
      interval_hours: 24
      restart_hour: 1
      restart_minute: 0

    renew_agent_wallets:
      enabled: true
      interval_hours: 24
      run_hour: 1
      run_minute: 10

    check_subaccount_funds:
      enabled: true
      interval_hours: 24
      run_hour: 1
      run_minute: 15

    cleanup_tmp_dir:
      enabled: true
      interval_hours: 24
      run_hour: 1
      run_minute: 20
      max_age_hours: 24

    cleanup_old_events:
      enabled: true
      interval_hours: 24
      run_hour: 1
      run_minute: 25
      max_age_days: 7

    cleanup_stale_strategies:
      enabled: true
      interval_hours: 24
      run_hour: 1
      run_minute: 30
      max_age_days: 1

    cleanup_old_failed:
      enabled: true
      interval_hours: 24
      run_hour: 1
      run_minute: 35
      max_age_days: 7

    cleanup_old_retired:
      enabled: true
      interval_hours: 24
      run_hour: 1
      run_minute: 40
      max_age_days: 7

# Market regime detection (Unger method)
regime:
  enabled: true
  # refresh_market_regimes runs at 01:05 UTC

# Data scheduler (update_pairs + download_data)
data_scheduler:
  enabled: true
  top_pairs_count: 200
  min_volume_usd: 0
  update_pairs_hours: [1, 13]     # Run at 01:45 and 13:45 UTC
  update_pairs_minute: 45
  download_data_hours: [2, 14]    # Run at 02:00 and 14:00 UTC
  download_data_minute: 0
```

### File Coinvolti

- `src/scheduler/main_continuous.py` → ContinuousSchedulerProcess
- `src/scheduler/task_tracker.py` → Tracking esecuzione task
- `src/credentials/agent_manager.py` → AgentManager
- `src/funds/manager.py` → FundManager
- `src/generator/regime/detector.py` → RegimeDetector (refresh_market_regimes)
- `src/data/pairs_updater.py` → PairsUpdater (update_pairs)
- `src/data/binance_downloader.py` → BinanceDataDownloader (download_data)

---

## A7. Pool Manager (Leaderboard)

**Obiettivo**: Gestire il pool ACTIVE con logica leaderboard (max N strategie).

### Pool Rules

**Config**:
- max_size: 300 (massimo strategie in ACTIVE)
- min_score: 40 (score minimo per entrare)

**Regole di ingresso**:

| Rule | Condizione | Azione |
|------|------------|--------|
| 1 | score < min_score | → RETIRED (non entra mai) |
| 2 | pool NOT full AND score >= min_score | → ACTIVE (entra direttamente) |
| 3 | pool FULL AND score > min(pool) | → EVICT worst + ACTIVE (prende il posto) |
| 4 | pool FULL AND score <= min(pool) | → RETIRED (non abbastanza buona) |

### API

**`PoolManager.try_enter_pool(strategy_id, score)`**
- Returns: (success: bool, reason: str)
- Thread-safe (lock per evitare race condition)
- Applica le 4 regole sopra

**`PoolManager.revalidate_after_retest(strategy_id, new_score)`**
- Returns: (still_active: bool, reason: str)
- Chiamato dopo re-backtest
- Se score degradato troppo → RETIRED

**`PoolManager.get_pool_stats()`**
- Returns: {count, min_score, max_score, avg_score, available_slots}

**`PoolManager.get_worst_strategy_in_pool()`**
- Returns: (id, name, score) or None

### Config

```yaml
active_pool:
  max_size: 300
  min_score: 40
```

### File Coinvolti

- `src/scorer/pool_manager.py` → PoolManager
