# 1. Generator

Il Generator daemon crea strategie base da diverse sorgenti configurabili.

**Daemon**: `src/generator/main_continuous.py`
**Output**: Strategy record con `status=GENERATED`

---

## Decision Flow: ROUND-ROBIN

```
Enabled sources (config): [pattern, pattern_gen, unger, pandas_ta,
                           ai_free, ai_assigned]

Ogni ciclo:
  source = enabled_sources[index % len(enabled_sources)]
  index += 1

  Ciclo 1: pattern    → se esaurito, skip
  Ciclo 2: pattern_gen→ genera sempre
  Ciclo 3: unger      → se no regime coins, skip
  Ciclo 4: pandas_ta  → genera sempre (regime-aware)
  Ciclo 5: ai_free    → se AI limit, skip
  Ciclo 6: ai_assigned→ se AI limit, skip
  Ciclo 7: pattern    → (ricomincia)
  ...

Config per controllare il mix:
  - Solo gratis: abilita pattern_gen + unger + pandas_ta
  - Solo AI: disabilita pattern_gen + unger + pandas_ta
```

---

## Strategy Sources

### PATTERN (`generation_mode='pattern'`)

**Fonte**: pattern-discovery API (`http://localhost:8001`)
**Endpoint**: `/patterns` (Tier 1, PRODUCTION status)

**Generazione (2 modalità)**:
- **A. DirectPatternGenerator** (zero AI cost) - preferita
  - Embed diretto `formula_source` dal pattern
- **B. AI Wrapping** - fallback se direct fallisce
  - Template: `generate_from_pattern_v2.j2`

**Parametri base** (dal pattern):
- `direction`: `target_direction` ('long'/'short')
- `tp_pct`: `target_magnitude / 100`
- `sl_pct`: `tp_pct × suggested_rr_ratio` (default 2.0)
- `exit_after_bars`: da `holding_period` + timeframe
- `timeframe`: DAL PATTERN (non random)

**Coins**: `pattern.get_high_edge_coins()`
- Filtra `coin_performance`: edge >= min_edge, signals >= min_signals
- Max coins da config, ordinati per edge

**Prefisso**: `PatStrat_TYPE_8charID` (es: `PatStrat_MOM_a7f3d8b2`)
**DB**: `pattern_ids=[uuid], pattern_coins=[...], pattern_based=True`

---

### AI_FREE (`generation_mode='ai_free'`)

**Fonte**: AI genera template (Jinja2)
**Template**: `generate_template.j2`

**Generazione**:
1. `TemplateGenerator.generate_template()`
   - AI sceglie LIBERAMENTE indicatori (91 disponibili)
   - Output: `StrategyTemplate` con placeholder Jinja2
   - Costo: 1 AI call
2. `ParametricGenerator.generate_strategies()`
   - Jinja2 rendering (zero AI cost)
   - 1 strategy base (backtester fa parametric optimization)

**Parametri base**: NESSUNO (strategy base senza params specifici)
- Backtester fa ~1015 combo optimization (SL × TP × lev × exit)

**Coins**: gestiti dal backtester (top N per volume, scroll-down)

**Prefisso**: `AIFStrat_TYPE_8charID` (es: `AIFStrat_REV_c4b9f1e7`)
**DB**: `template_id=uuid, pattern_based=False`

---

### AI_ASSIGNED (`generation_mode='ai_assigned'`)

**Fonte**: IndicatorCombinator + AI template
**Template**: `generate_template.j2` (con indicatori assegnati)

**Generazione**:
1. `IndicatorCombinator.get_combination()`
   - Main indicators: 2-3 (prefer 2)
   - Filter indicators: 0-2
   - Pool: 91 indicatori (VALID_INDICATORS)
   - Tracking: `UsedIndicatorCombination` table
   - Space: ~112 miliardi combo uniche
2. `TemplateGenerator.generate_template()`
   - AI usa SOLO indicatori assegnati (no freedom)
   - Costo: 1 AI call
3. `ParametricGenerator` (zero AI cost)

**Parametri base**: NESSUNO (identico a ai_free)

**Coins**: gestiti dal backtester (top N per volume, scroll-down)

**Prefisso**: `AIAStrat_TYPE_8charID` (es: `AIAStrat_MOM_f2e5d8a1`)
**DB**: `template_id=uuid, pattern_based=False + UsedIndicatorCombination`

---

### PATTERN_GEN (`generation_mode='pattern_gen'`)

**Fonte**: Building Blocks interni + FormulaComposer

**Module**: `src/generator/pattern_gen/`
- `building_blocks.py`: 36 blocks in 5 categorie
- `formula_composer.py`: composizione formule
- `generator.py`: PatternGenGenerator (adaptive mode)
- `genetic_generator.py`: GeneticPatternGenerator (evoluzione)
- `genetic_operators.py`: selection, crossover, mutation

#### FASE 1 - SMART GENERATION (PGnStrat_)

**Composizione**:
- 50% Parametric: singolo block con parametri variati
- 30% Template: 2-3 blocks combinati con AND
- 20% Innovative: sequential, multi-lookback, volatility

**Space**: ~7,700 strategie base (× TF × direction)
**Dedup**: `formula_hash` evita duplicati

#### FASE 2 - GENETIC EVOLUTION (PGgStrat_)

**Pool**: ACTIVE pattern_gen con score >= 40
**Fitness**: `score_backtest` (deferred, già calcolato)

**Operatori**:
- Tournament selection (size=3)
- Block crossover (combina blocks da 2 genitori)
- Block mutation (swap/add/remove, rate=20%)

**Attivazione**: pool >= 50 ACTIVE strategies
**Ratio**: 70% smart / 30% genetic (configurable)
**Space**: infinito (evolve continuamente)

#### Adaptive Mode Selection

- pool < 50 → Solo Smart (bootstrap)
- pool >= 50 → 70% Smart / 30% Genetic
- smart esaurito → Solo Genetic

#### Categorie Blocks

| Categoria | Descrizione |
|-----------|-------------|
| THR | Threshold (RSI, Stoch, CCI, Williams%R, MFI) |
| CRS | Crossover (EMA, MACD, Stoch, ADX) |
| VOL | Volatility (Bollinger, ATR, Keltner, Donchian) |
| PRC | Price Action (Inside Bar, Engulfing, Hammer, Doji) |
| STA | Statistical (Z-score, Percentile, StdDev) |

**AI calls**: 0 (tutto da building blocks)
**Parametri**: SL, TP, leverage, exit_bars (randomizzati da range)

**Prefissi**:
- `PGnStrat_TYPE_hash` (Smart: parametric/template/innovative)
- `PGgStrat_TYPE_hash` (Genetic: evolved from pool)

**DB**: `generation_mode='pattern_gen', ai_provider='pattern_gen'`

---

### UNGER (`generation_mode='unger'`)

**Fonte**: Cataloghi Unger v2 + Market Regime Detector

**Cataloghi** (`src/generator/unger/catalogs/`):
- 128 Entry Conditions (9 categorie)
- 92 Entry Filters (6 categorie)
- 15 Exit Conditions
- 5 SL Types + 5 TP Types + 6 Trailing Configs
- 11 Exit Mechanisms
- Space totale: ~15-30 milioni di strategie

**Generazione regime-aware**:
1. RegimeDetector analizza tutti i coin (90 giorni, daily)
2. Raggruppa per (type, direction):
   - TREND: breakout, crossover, volatility entries
   - REVERSAL: mean_reversion, threshold, candlestick entries
   - MIXED: tutte le categorie
3. Per ogni gruppo: top N coin per volume
4. Genera strategie coerenti col regime

**Parametri**: embedded nel codice (da catalogo, non AI)
**AI calls**: 0 (tutto da catalogo)

**Prefisso**: `UngStrat_TYPE_8charID` (es: `UngStrat_CRS_a7f3d8b2`)
**DB**: `pattern_coins=[...], ai_provider='unger', pattern_based=False`

---

### UNGER_GENETIC (`generation_mode='unger_genetic'`)

**Fonte**: Evoluzione genetica di strategie ACTIVE unger

**Operazioni genetiche**:
- Tournament Selection (size=3)
- Crossover componenti (80%): entry, filters, exit mechanism, SL/TP
- Mutation (20%): cambia componenti o parametri
- Mutazione parametri: ±10-20% sui valori numerici

**Attivazione**:
- `config.generation.strategy_sources.unger.genetic.enabled = true`
- Pool ACTIVE unger >= min_pool_size (default: 50)
- Probabilita' genetic_ratio (default: 30%)

**Prefisso**: `UggStrat_TYPE_8charID` (es: `UggStrat_BRK_abc12345`)
**DB**: `generation_mode='unger_genetic', ai_provider='unger'`

---

### PANDAS_TA (`generation_mode='pandas_ta'`)

**Fonte**: Indicatori pandas_ta + Matrici Compatibilità

**Cataloghi** (`src/generator/pandas_ta/catalogs/`):
- **42 Indicatori in 5 categorie**:
  - momentum (11): RSI, STOCH_K, CCI, WILLR, CMO, ROC, MOM, TSI...
  - trend (10): EMA, SMA, SUPERTREND, PSAR, HMA, DEMA, TEMA...
  - crossover (6): MACD, PPO, TRIX, ADX, AROON, DPO
  - volatility (7): BBANDS, ATR, NATR, KC, DONCHIAN, MASSI, UI
  - volume (8): OBV, AD, ADOSC, CMF, EFI, NVI, PVI, VWAP
- 7 Condition Types: threshold_below/above, crossed_above/below, between, slope_up/down
- 19 Incompatible Pairs (es: RSI+STOCH_K = ridondanti)
- 15 Recommended Combos (es: RSI+ADX = mean reversion + trend)
- Riuso 11 Exit Mechanisms da Unger
- Space totale: ~158 milioni di strategie

**Generazione**:
1. Seleziona 1-3 indicatori (30% single, 50% double, 20% triple)
2. Verifica compatibilità (no pair ridondanti)
3. Assegna condition type e threshold (valori market-sensible)
4. Seleziona Exit Mechanism (11 logiche TP/EC/TS)
5. Genera codice via Jinja2 template

**Regime-aware**:
- TREND: usa indicatori trend + crossover + volatility
- REVERSAL: usa indicatori momentum (RSI, STOCH_K, CCI, etc.)
- MIXED: tutti gli indicatori disponibili

**AI calls**: 0 (tutto da catalogo + template)

**Prefisso**: `PtaStrat_TYPE_8charID` (es: `PtaStrat_MOM_a7f3d8b2`)
**DB**: `pattern_coins=[...], ai_provider='pandas_ta', pattern_based=False`

---

## Tabella Comparativa Sources

| | pat | pgn | pgg | ung | pta | aif | aia |
|---|---|---|---|---|---|---|---|
| **Prefix** | Pat | PGn | PGg | Ung | Pta | AIF | AIA |
| **Indicators** | formula | blocks | blocks | catalog | pandas_ta | AI | combo |
| **AI calls** | 0-1 | 0 | 0 | 0 | 0 | 1 | 1 |
| **Cost** | free | free | free | free | free | 1call | 1call |
| **Space** | 150 | 7.7K | evol | 30M | 158M | inf | 1K |
| **Exit** | 11 | 11 | 11 | 11 | 11 | custom | custom |

---

## Mapping Sources (1:1 con config.yaml)

| Abbr | Class | generation_mode | Config key |
|------|-------|-----------------|------------|
| pat | PatStrat_ | pattern | pattern |
| pgn | PGnStrat_ | pattern_gen | pattern_gen |
| pgg | PGgStrat_ | pattern_gen_genetic | pattern_gen.genetic |
| ung | UngStrat_ | unger | unger |
| ugg | UggStrat_ | unger_genetic | unger.genetic |
| pta | PtaStrat_ | pandas_ta | pandas_ta |
| aif | AIFStrat_ | ai_free | ai_free |
| aia | AIAStrat_ | ai_assigned | ai_assigned |

---

## Direction: BIDI

Le strategie BIDI (bidirectional) possono aprire sia LONG che SHORT.

**Generatori con supporto BIDI**: Unger, Pandas_ta, Pattern_gen (e varianti genetic)

### Logica BIDI

Ogni strategia BIDI ha **due entry condition indipendenti**:
- `entry_long`: condizione per entrare LONG (es. RSI < 30, Breakout N-Bar High)
- `entry_short`: condizione per entrare SHORT (es. RSI > 70, Breakout N-Bar Low)

```python
# Generazione segnali
long_signal = entry_long_condition(df)   # Indipendente
short_signal = entry_short_condition(df) # Indipendente
entry_signal = long_signal | short_signal

# Direzione determinata da quale signal è attivo
if long_signal: direction = 'long'
elif short_signal: direction = 'short'
```

### Implementazione per Generatore

| Generator | LONG Entry | SHORT Entry |
|-----------|------------|-------------|
| **Unger** | `entry_condition_long` da catalogo | `entry_condition_short` da catalogo (stessa categoria) |
| **Pandas_ta** | `entry_conditions_long` (1-3 indicatori) | `entry_conditions_short` (1-3 indicatori) |
| **Pattern_gen** | Block LONG da `building_blocks` | Block SHORT da `building_blocks` |

### Selezione Entry Coerenti

I generatori preferiscono entry "gemelle" dalla stessa categoria:
- Unger: `BRK_01` (Breakout High) + `BRK_02` (Breakout Low)
- Pandas_ta: RSI < 30 (oversold) + RSI > 70 (overbought)
- Pattern_gen: Block threshold LONG + Block threshold SHORT

### Generatori senza BIDI

- **AI_free / AI_assigned**: Solo LONG o SHORT (Claude non genera BIDI)
- **Pattern**: Direction dal pattern (`target_direction`)

---

## Log Format

```
[1/10 GEN] 24h: N | pat=X, pgn=X, pgg=X, ung=X, ugg=X, pta=X, aif=X, aia=X
[9/10 POOL] src: pat=X, pgn=X, pgg=X, ung=X, ugg=X, pta=X, aif=X, aia=X
```

---

## File Coinvolti

- `src/generator/main_continuous.py` → ContinuousGeneratorProcess
- `src/generator/direct_generator.py` → DirectPatternGenerator
- `src/generator/template_generator.py` → TemplateGenerator
- `src/generator/parametric_generator.py` → ParametricGenerator
- `src/generator/indicator_combinator.py` → IndicatorCombinator
- `src/generator/pattern_gen/` → PatternGen module
- `src/generator/unger/` → Unger module
- `src/generator/pandas_ta/` → PandasTA module
