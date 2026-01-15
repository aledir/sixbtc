# COIN Pipeline

Come i coin vengono selezionati e usati nelle strategie.

---

## 0. CoinRegistry - Single Source of Truth

**File**: `src/data/coin_registry.py`

CoinRegistry è il modulo centralizzato per la gestione dei coin. Tutti i componenti del sistema usano CoinRegistry per:

| Funzione | Usata da | Descrizione |
|----------|----------|-------------|
| `get_coins_with_sufficient_data()` | Generator (CoinDirectionSelector) | Top N coin con copertura dati sufficiente |
| `get_top_coins_by_volume()` | Fallback | Top N coin per volume (senza filtro dati) |
| `get_tradable_for_strategy()` | Executor | Filtro runtime per liquidità |
| `has_sufficient_data()` | Validation | Verifica singolo coin |
| `is_tradable()` | Ovunque | Verifica coin attivo e liquido |

**Copertura dati garantita**:
- Il campo `data_coverage_days` nella tabella `coins` traccia i giorni di dati OHLCV disponibili
- `get_coins_with_sufficient_data()` filtra coin con copertura < `(is_days + oos_days) * min_coverage_pct`
- Default: (120 + 60) × 0.80 = **144 giorni minimi**
- Questo filtro avviene **prima** della generazione, non durante il backtest

---

## 1. Pipeline AUX (scheduled 2x/giorno)

Prepara i dati per i generator.

```
┌─────────────────────────────────────────────────────────────┐
│ UPDATE PAIRS (01:45, 13:45 UTC)                             │
│                                                             │
│ Hyperliquid API (224) ∩ Binance API (541) = 184 coin        │
│ Filtro volume ≥ $1M → 64 coin attivi                        │
│ Output: tabella `coins` con is_active=true                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ DATA DOWNLOADER (02:00, 14:00 UTC)                          │
│                                                             │
│ Per ogni coin attivo: scarica OHLCV da Binance              │
│ Output: 320 file parquet (64 coin × 5 timeframe)            │
│                                                             │
│ Dopo download: calcola data_coverage_days per ogni coin     │
│ usando il file 15m come riferimento.                        │
│ Coin con copertura < 144d vengono esclusi dalla generazione │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ REGIME DETECTOR (02:30, 14:30 UTC)                          │
│                                                             │
│ Input: 64 coin attivi                                       │
│ Per ogni coin con ≥90 giorni di dati:                       │
│   - Calcola regime_type (TREND/REVERSAL)                    │
│   - Calcola direction (LONG/SHORT/BOTH)                     │
│   - Calcola strength (0.0-1.0)                              │
│ Output: tabella `market_regimes` (41 coin con strength≥0.5) │
└─────────────────────────────────────────────────────────────┘
```

**Risultato AUX**: 64 coin attivi, ~60 con copertura sufficiente, 41 con regime forte.

---

## 2. Coin/Direction Selection - Due Modalità

Ogni generatore può essere configurato per usare una delle due modalità:

### Modalità 1: Volume-Based (DEFAULT)

```yaml
# config.yaml
generation:
  strategy_sources:
    unger:
      market_regime:
        enabled: false  # DEFAULT
```

**Comportamento**:
- **Coin**: Top N per volume 24h (da `trading.top_coins_limit`)
- **Direction**: Round-robin sequenziale (LONG → SHORT → BIDI → LONG → ...)

```
┌─────────────────────────────────────────────────────────────┐
│ VOLUME-BASED SELECTION                                      │
│                                                             │
│ Coin: get_top_coins_by_volume(30) → 30 coin                 │
│ Direction: round-robin cycle → LONG/SHORT/BIDI              │
│                                                             │
│ Risultato: tutti i coin, tutte le direzioni (diversificato) │
└─────────────────────────────────────────────────────────────┘
```

### Modalità 2: Regime-Based

```yaml
# config.yaml
generation:
  strategy_sources:
    unger:
      market_regime:
        enabled: true  # Usa market_regimes
```

**Comportamento**:
- **Coin**: Query `market_regimes` per direction
- **Direction**: Basata sul regime dominante (+ 50% BIDI)

```
┌─────────────────────────────────────────────────────────────┐
│ REGIME-BASED SELECTION                                      │
│                                                             │
│ Query market_regimes → group by direction                   │
│ LONG: 13 coin | SHORT: 19 coin | BOTH: 9 coin               │
│                                                             │
│ Selezione:                                                  │
│ 1. Trova direzione dominante (es. SHORT=19)                 │
│ 2. 50% usa dominante, 50% usa BIDI                          │
│                                                             │
│ Risultato: coin coerenti con regime corrente                │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Configurazione per Generatore

| Generator | Supported Directions | market_regime | Note |
|-----------|---------------------|---------------|------|
| **Unger** | LONG, SHORT, BIDI | ✅ | Vedi PIPELINE_01_GENERATOR.md |
| **Unger Genetic** | LONG, SHORT, BIDI | ✅ | Vedi PIPELINE_01_GENERATOR.md |
| **Pandas_ta** | LONG, SHORT, BIDI | ✅ | Vedi PIPELINE_01_GENERATOR.md |
| **Pattern_gen** | LONG, SHORT, BIDI | ✅ | Vedi PIPELINE_01_GENERATOR.md |
| **Pattern_gen Genetic** | LONG, SHORT, BIDI | ✅ | Vedi PIPELINE_01_GENERATOR.md |
| **AI_free** | LONG, SHORT | ✅ | No BIDI |
| **AI_assigned** | LONG, SHORT | ✅ | No BIDI |
| **Pattern** | Da pattern | ❌ | Usa `pattern.get_high_edge_coins()` |

### Esempio Config

```yaml
generation:
  strategy_sources:
    unger:
      enabled: true
      market_regime:
        enabled: false  # Volume-based (default)

    pandas_ta:
      enabled: true
      market_regime:
        enabled: true   # Regime-based

    pattern_gen:
      enabled: true
      market_regime:
        enabled: false  # Volume-based (default)
```

---

## 4. CoinDirectionSelector

Modulo centralizzato che gestisce la selezione coin/direction.

**File**: `src/generator/coin_direction_selector.py`

```python
from src.generator.coin_direction_selector import CoinDirectionSelector

# Initialize per generator
selector = CoinDirectionSelector(config, 'unger')

# Select coin and direction
direction, coins = selector.select()
# direction = 'LONG', 'SHORT', or 'BIDI'
# coins = ['BTC', 'ETH', 'SOL', ...]

# Con override (forza direzione specifica)
direction, coins = selector.select(direction_override='SHORT')
```

**Round-robin sequenziale** (per volume-based mode):
- Ciclo: LONG → SHORT → BIDI → LONG → ...
- Persistente per-generator tra chiamate
- Resetta al restart del daemon

---

## 5. Pipeline MAIN - Dove entrano i coin

### GENERATION (step 1)

**Dove sono salvati i coin**:
- **64 coin attivi** → tabella `coins` (colonna `is_active=true`)
- **41 coin con regime** → tabella `market_regimes` (colonna `strength>=0.5`)
- **trading_coins della strategia** → tabella `strategies` (colonna `trading_coins`, JSON)

**Chi salva trading_coins**: ogni generator via CoinDirectionSelector

| Generator | Modalità Default | Risultato |
|-----------|------------------|-----------|
| **Unger** | Volume-based | 30 coin (top volume) |
| **Unger Genetic** | Volume-based | 30 coin (top volume) |
| **Pandas_ta** | Volume-based | 30 coin (top volume) |
| **Pattern_gen** | Volume-based | 30 coin (top volume) |
| **Pattern_gen Genetic** | Volume-based | 30 coin (top volume) |
| **AI_free** | Volume-based | 30 coin (top volume) |
| **AI_assigned** | Volume-based | 30 coin (top volume) |
| **Pattern** | Pattern-specific | variabile (high-edge coins) |

**Config**: `trading.top_coins_limit` (default: 30)

---

### VALIDATION → PARAMETRIC → BACKTEST IS/OOS → SCORE → SHUFFLE → WFA → ROBUSTNESS

**Nessuna modifica ai coin**. Usano tutti `strategy.trading_coins`.

Durante il backtest c'è una **validazione temporanea** (safety net):
```
trading_coins (es. 30 coin)
       ↓
   coin ancora is_active? ──→ NO → escluso
       ↓ SI
   ha file parquet? ──→ NO → escluso
       ↓ SI
   copertura dati ≥80%? ──→ NO → escluso
       ↓ SI
   validated_coins (es. 27 coin)
```

⚠️ `trading_coins` NON viene modificato. I coin esclusi sono solo ignorati per quel backtest.

**NOTA**: Grazie al filtro `data_coverage_days` a monte (vedi sezione 0), questo check non dovrebbe mai scattare. È mantenuto come safety net per edge case (es. coin delistato tra generazione e backtest).

---

### POOL ENTRY (step 9)

Strategia entra nel pool ACTIVE con i suoi `trading_coins` originali.

---

### EXECUTOR (step 10 - live)

Filtro runtime su `trading_coins`:
```
trading_coins (es. 30 coin salvati)
       ↓
   coin ancora su Hyperliquid? ──→ NO → skip
       ↓ SI
   volume_24h ≥ $1M? ──→ NO → skip
       ↓ SI
   tradable_coins (es. 28 coin oggi)
```

⚠️ Anche qui `trading_coins` NON viene modificato. Il filtro è runtime.

---

## 6. Riepilogo

| Fase | Cosa succede ai coin |
|------|---------------------|
| **AUX: Update pairs** | Crea pool di 64 coin attivi |
| **AUX: Regime detector** | Classifica 41 coin con regime |
| **MAIN: Generation** | Salva coin in `trading_coins` via selector |
| **MAIN: Backtest** | Valida temporaneamente, usa quelli con dati |
| **MAIN: Executor** | Filtra runtime, usa quelli ancora liquidi |

**Regola fondamentale**: `trading_coins` viene scritto UNA volta (dal generator) e mai più modificato.

---

## 7. Quando usare quale modalità

| Scenario | Modalità | Motivazione |
|----------|----------|-------------|
| **Massima diversificazione** | Volume-based | Tutti i coin liquidi, tutte le direzioni |
| **Seguire il trend** | Regime-based | Solo coin in trend/reversal forte |
| **Bootstrap iniziale** | Volume-based | Genera molte strategie velocemente |
| **Fine-tuning** | Regime-based | Strategie più mirate al regime |

**Default consigliato**: Volume-based per tutti i generatori (massima diversificazione).
