# COIN Pipeline

Questo documento descrive il percorso completo dei coin attraverso il sistema SixBTC, dalla selezione iniziale fino al live trading.

---

## Overview

```
Hyperliquid API (224 coin)
        ↓
    [PAIRS UPDATER] ← Binance API (541 coin)
        ↓
   64 coin attivi (is_active=true)
        ↓
   [BINANCE DOWNLOADER]
        ↓
   320 file parquet (64 coin × 5 TF)
        ↓
   [REGIME DETECTOR]
        ↓
   41 coin con regime forte (strength ≥ 0.5)
        ↓
   [GENERATORS]
        ↓
   Strategia con trading_coins (9-30 coin)
        ↓
   [BACKTESTER]
        ↓
   Strategia ACTIVE
        ↓
   [EXECUTOR]
        ↓
   Ordini su Hyperliquid
```

---

## 1. PAIRS UPDATER

**Schedule**: 2x al giorno (01:45, 13:45 UTC)

**Input**:
- API Hyperliquid → lista perpetual correnti
- API Binance → lista perpetual disponibili

**Flusso**:
```
Hyperliquid API → 224 perpetual
Binance API → 541 perpetual
        ↓
Intersezione (su entrambi) → 184 coin
        ↓
Filtro volume ≥ $1M → ~70 coin
        ↓
Salva in DB: coins.is_active = true
```

**Output**:
- Tabella `coins`: ~64 coin attivi (numero varia con volumi di mercato)
- Tabella `coins`: ~185 coin totali (include storici inattivi)

**Note**:
- Il numero 224 non è hardcoded, viene dall'API Hyperliquid in tempo reale
- Coin nuovi su HL appaiono automaticamente al prossimo ciclo
- Coin delistati da HL diventano `is_active=false` automaticamente
- Il filtro volume ($1M) è configurabile in `config.yaml` → `trading.min_volume_24h`

---

## 2. BINANCE DOWNLOADER

**Schedule**: 2x al giorno (02:00, 14:00 UTC) - 15 min dopo pairs_updater

**Input**: Coin attivi da tabella `coins` (is_active=true)

**Flusso**:
```
Per ogni coin attivo (~64):
  Per ogni timeframe [15m, 30m, 1h, 2h, 1d]:
    Scarica OHLCV da Binance
    Salva in data/binance/{SYMBOL}_{TF}.parquet
```

**Output**:
- ~320 file parquet (64 coin × 5 timeframe)
- Ogni file contiene ultimi 365+ giorni di candele OHLCV

**Note**:
- I dati vengono da Binance (non Hyperliquid) per maggiore storico
- File corrotti vengono auto-riparati (re-download)
- Supporta backfill per nuovi coin

---

## 3. REGIME DETECTOR

**Schedule**: 2x al giorno (02:30, 14:30 UTC) - 30 min dopo download_data

**Input**: File parquet daily (`*_1d.parquet`) per coin attivi

**Flusso**:
```
Per ogni coin attivo (~64):
  Se ha ≥ 90 giorni di dati daily:
    Esegue breakout test (trend-following)
    Esegue reversal test (mean-reversion)
    Calcola regime_type: TREND o REVERSAL
    Calcola direction: LONG, SHORT, o BOTH
    Calcola strength: 0.0 - 1.0
    Salva in market_regimes
  Altrimenti:
    Skip (dati insufficienti)
```

**Output** (tabella `market_regimes`):
- ~66 coin con regime calcolato
- ~41 coin con strength ≥ 0.5 (usabili dai generator regime-aware)

**Breakdown per Direction** (strength ≥ 0.5):

| Direction | Count | Descrizione |
|-----------|-------|-------------|
| LONG | ~13 | Solo long profittevole storicamente |
| SHORT | ~19 | Solo short profittevole storicamente |
| BOTH | ~9 | Entrambe le direzioni profittevoli |

**Breakdown per Regime Type** (strength ≥ 0.5):

| Regime | Count | Descrizione |
|--------|-------|-------------|
| TREND | ~25 | Breakout test più profittevole |
| REVERSAL | ~16 | Reversal test più profittevole |

**Note**:
- Coin nuovi (< 90 giorni di dati) non hanno regime
- Coin senza regime non vengono usati da Unger/Pandas_ta
- Coin senza regime VENGONO usati da Pattern_gen (usa top 30 by volume)

---

## 4. GENERATORS

### 4.1 UNGER (`UngStrat_*`) - ATTIVO

**Input**: Tabella `market_regimes` (strength ≥ 0.5)

**Selezione coin**:
```
50% delle volte → direzione dominante (SHORT se più coin SHORT)
50% delle volte → BIDI (usa coin con direction=BOTH)
```

**Coin assegnati a `trading_coins`**:
- Se direction=LONG → ~13 coin (tutti i LONG)
- Se direction=SHORT → ~19 coin (tutti i SHORT)
- Se direction=BIDI → ~9 coin (tutti i BOTH)

---

### 4.2 UNGER GENETIC (`UggStrat_*`) - ATTIVO

**Input**: Strategie ACTIVE Unger con score ≥ 40

**Selezione coin**: Eredita `trading_coins` dal parent (con possibili mutazioni)

**Coin assegnati**: Stessi del parent (~9-19 coin)

---

### 4.3 PANDAS_TA (`PtaStrat_*`) - ATTIVO

**Input**: Tabella `market_regimes` (strength ≥ 0.5)

**Selezione coin**: Identica a Unger
```
50% delle volte → direzione dominante
50% delle volte → BIDI
```

**Coin assegnati a `trading_coins`**:
- Se direction=LONG → ~13 coin
- Se direction=SHORT → ~19 coin
- Se direction=BIDI → ~9 coin

---

### 4.4 PATTERN_GEN (`PGnStrat_*`) - ATTIVO

**Input**: Tabella `coins` (is_active=true) - **NON usa market_regimes**

**Selezione coin**:
```
get_top_coins_by_volume(30) → top 30 coin per volume 24h
```

**Coin assegnati a `trading_coins`**: 30 coin (top per volume, indipendente dal regime)

**Note**: Include anche coin nuovi senza regime (se nel top 30 per volume)

---

### 4.5 PATTERN_GEN GENETIC (`PGgStrat_*`) - ATTIVO

**Input**: Strategie ACTIVE pattern_gen con score ≥ 40

**Selezione coin**: Eredita `trading_coins` dal parent

**Coin assegnati**: 30 coin (stessi del parent)

---

### 4.6 PATTERN (`PatStrat_*`) - DISATTIVO

**Input**: Pattern-discovery API (servizio esterno)

**Selezione coin**: Coin specifici dal pattern (basati su edge statistico)

**Coin assegnati**: Variabile (definiti dal pattern stesso)

---

### 4.7 AI_FREE (`AIFStrat_*`) - DISATTIVO

**Input**: Prompt AI + indicatori scelti liberamente dall'AI

**Selezione coin**: `get_top_coins_by_volume(30)`

**Coin assegnati**: 30 coin

---

### 4.8 AI_ASSIGNED (`AIAStrat_*`) - DISATTIVO

**Input**: Prompt AI + indicatori pre-assegnati da IndicatorCombinator

**Selezione coin**: `get_top_coins_by_volume(30)`

**Coin assegnati**: 30 coin

---

### Riepilogo Generators

| Generator | Stato | Coin Source | Coin Count | Classe |
|-----------|-------|-------------|------------|--------|
| Unger | Attivo | market_regimes (direction) | 9-19 | `UngStrat_*` |
| Unger Genetic | Attivo | Eredita da parent | 9-19 | `UggStrat_*` |
| Pandas_ta | Attivo | market_regimes (direction) | 9-19 | `PtaStrat_*` |
| Pattern_gen | Attivo | Top 30 by volume | 30 | `PGnStrat_*` |
| Pattern_gen Genetic | Attivo | Eredita da parent | 30 | `PGgStrat_*` |
| Pattern | Disattivo | Pattern-discovery API | Variabile | `PatStrat_*` |
| AI_free | Disattivo | Top 30 by volume | 30 | `AIFStrat_*` |
| AI_assigned | Disattivo | Top 30 by volume | 30 | `AIAStrat_*` |

---

## 5. BACKTESTER

**Schedule**: Continuo (processa strategie VALIDATED)

**Input**: Strategia con `trading_coins` (9-30 coin a seconda del generator)

**Validazione coin** (3 livelli):
```
trading_coins (es. 19 coin dalla strategia)
        ↓
Level 1: Liquidity filter
  - Coin ancora is_active=true?
  - Rimuove coin delistati/illiquidi
        ↓
Level 2: Cache filter
  - File parquet esiste per questo coin/timeframe?
  - Rimuove coin senza dati
        ↓
Level 3: Coverage filter
  - Almeno 80% dei giorni richiesti coperti?
  - Rimuove coin con troppi gap nei dati
        ↓
validated_coins (es. 17 coin dopo filtri)
```

**Output**: Backtest eseguito su `validated_coins`

**Note**:
- Se troppi coin vengono filtrati, la strategia può fallire per "insufficient trades"
- Il backtester NON modifica `trading_coins` della strategia (solo valida temporaneamente)

---

## 6. EXECUTOR

**Schedule**: Continuo (esegue strategie LIVE)

**Input**: Strategia LIVE con `trading_coins`

**Filtro runtime**:
```
trading_coins (es. 19 coin dalla strategia)
        ↓
is_tradable(coin):
  - is_active = true (coin ancora su Hyperliquid)
  - volume_24h ≥ soglia configurata
        ↓
tradable_coins (es. 18 coin dopo filtro)
        ↓
Per ogni nuova candela:
  Per ogni tradable_coin:
    Calcola indicatori
    Verifica entry condition
    Se signal → esegue ordine su Hyperliquid
```

**Output**: Ordini eseguiti su Hyperliquid

**Note**:
- Coin delistati vengono automaticamente esclusi (ordini rifiutati da HL)
- Coin illiquidi vengono filtrati per evitare slippage eccessivo
- La strategia continua a funzionare con meno coin (no crash)

---

## Coin Lifecycle

```
[NUOVO SU HYPERLIQUID]
        ↓
pairs_updater lo aggiunge a coins (is_active=true)
        ↓
binance_downloader inizia a scaricare dati
        ↓
[ATTESA 90 GIORNI per dati sufficienti]
        ↓
regime_detector lo classifica (TREND/REVERSAL, LONG/SHORT/BOTH)
        ↓
[DISPONIBILE PER GENERATORS REGIME-AWARE]
        ↓
generators lo includono in trading_coins delle nuove strategie
        ↓
backtester lo usa per testare strategie
        ↓
executor lo usa per trading live
        ↓
[SE DELISTATO DA HYPERLIQUID]
        ↓
pairs_updater lo marca is_active=false
        ↓
Strategie esistenti continuano ma senza questo coin
(ordini rifiutati, segnali ignorati)
```

---

## FAQ

**Q: Cosa succede se un coin scende sotto $1M di volume?**
A: Al prossimo ciclo pairs_updater diventa `is_active=false`. Le strategie che lo avevano in `trading_coins` continuano a funzionare ma con un coin in meno.

**Q: Cosa succede se un coin cambia regime (da LONG a SHORT)?**
A: Le strategie esistenti continuano con la direzione originale. Se non performano, il meccanismo di rotazione le ritira. Nuove strategie useranno il nuovo regime.

**Q: Come vengono trattati i coin nuovi senza regime?**
A: Unger e Pandas_ta li ignorano (richiedono regime). Pattern_gen li include se sono nel top 30 per volume.

**Q: I coin sono ordinati in qualche modo?**
A: Sì, per volume 24h decrescente in tutte le query.
