Pipeline Completa Aggiornata:

┌─────────────────────────────────────────────────────────────────┐
│ 1. GENERAZIONE (generator daemon)                               │
├─────────────────────────────────────────────────────────────────┤
│ • AI genera base code (pattern/ai_free/ai_assigned)             │
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
│ • Backtest 120 giorni con best params                           │
│ • Portfolio simulation realistico (margin, max 10 pos, fees)    │
│ • Calcola metriche IS: sharpe, win_rate, expectancy, DD, trades │
│ • Min trades check (timeframe-dependent)                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. BACKTEST OUT-OF-SAMPLE (backtester - STEP 3)                 │
├─────────────────────────────────────────────────────────────────┤
│ • Backtest 30 giorni OOS con STESSI params                      │
│ • Degradation check: (1 - OOS_sharpe/IS_sharpe) ≤ 50%           │
│ • OOS sharpe ≥ 0 (positivo)                                     │
│ • 0 trades OOS = OK (pattern dormiente)                         │
│ • Calcola recency bonus/penalty                                 │
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









╔══════════════════════════════════════════════════════════════════════════════╗
║                              1. GENERATOR                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Decision Flow:                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ _should_use_patterns() → pattern disponibili?                          │  ║
║  │    YES → genera PATTERN                                                │  ║
║  │    NO  → if both AI sources enabled:                                   │  ║
║  │            random(ai_free_ratio) → AI_FREE (70%) o AI_ASSIGNED (30%)   │  ║
║  │          else:                                                         │  ║
║  │            usa l'unica source enabled                                  │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ PATTERN (generation_mode='pattern')                                    │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ Fonte: pattern-discovery API (http://localhost:8001)                   │  ║
║  │ Endpoint: /patterns (Tier 1, PRODUCTION status)                        │  ║
║  │                                                                        │  ║
║  │ Generazione (2 modalità):                                              │  ║
║  │   A. DirectPatternGenerator (zero AI cost) - preferita                 │  ║
║  │      - Embed diretto formula_source dal pattern                        │  ║
║  │   B. AI Wrapping - fallback se direct fallisce                         │  ║
║  │      - Template: generate_from_pattern_v2.j2                           │  ║
║  │                                                                        │  ║
║  │ Parametri base (dal pattern):                                          │  ║
║  │   - direction: target_direction ('long'/'short')                       │  ║
║  │   - tp_pct: target_magnitude / 100                                     │  ║
║  │   - sl_pct: tp_pct × suggested_rr_ratio (default 2.0)                  │  ║
║  │   - exit_after_bars: da holding_period + timeframe                     │  ║
║  │   - timeframe: DAL PATTERN (non random)                                │  ║
║  │                                                                        │  ║
║  │ Coins: pattern.get_high_edge_coins()                                   │  ║
║  │   - Filtra coin_performance: edge >= min_edge, signals >= min_signals  │  ║
║  │   - Max coins da config, ordinati per edge                             │  ║
║  │                                                                        │  ║
║  │ Prefisso: PatStrat_TYPE_8charID (es: PatStrat_MOM_a7f3d8b2)            │  ║
║  │ DB: pattern_ids=[uuid], pattern_coins=[...], pattern_based=True        │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ AI_FREE (generation_mode='ai_free')                                    │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ Fonte: AI genera template (Jinja2)                                     │  ║
║  │ Template: generate_template.j2                                         │  ║
║  │                                                                        │  ║
║  │ Generazione:                                                           │  ║
║  │   Step 1: TemplateGenerator.generate_template()                        │  ║
║  │           - AI sceglie LIBERAMENTE indicatori (91 disponibili)         │  ║
║  │           - Output: StrategyTemplate con placeholder Jinja2            │  ║
║  │           - Costo: 1 AI call                                           │  ║
║  │   Step 2: ParametricGenerator.generate_strategies()                    │  ║
║  │           - Jinja2 rendering (zero AI cost)                            │  ║
║  │           - 1 strategy base (backtester fa parametric optimization)    │  ║
║  │                                                                        │  ║
║  │ Parametri base: NESSUNO (strategy base senza params specifici)         │  ║
║  │   - Backtester fa ~1015 combo optimization (SL × TP × lev × exit)      │  ║
║  │                                                                        │  ║
║  │ Coins: gestiti dal backtester (top N per volume, scroll-down)          │  ║
║  │                                                                        │  ║
║  │ Prefisso: Strategy_TYPE_8charID (es: Strategy_REV_c4b9f1e7)            │  ║
║  │ DB: template_id=uuid, pattern_based=False                              │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ AI_ASSIGNED (generation_mode='ai_assigned')                            │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ Fonte: IndicatorCombinator + AI template                               │  ║
║  │ Template: generate_template.j2 (con indicatori assegnati)              │  ║
║  │                                                                        │  ║
║  │ Generazione:                                                           │  ║
║  │   Step 1: IndicatorCombinator.get_combination()                        │  ║
║  │           - Main indicators: 2-3 (prefer 2)                            │  ║
║  │           - Filter indicators: 0-2                                     │  ║
║  │           - Pool: 91 indicatori (VALID_INDICATORS)                     │  ║
║  │           - Tracking: UsedIndicatorCombination table                   │  ║
║  │           - Space: ~112 miliardi combo uniche                          │  ║
║  │   Step 2: TemplateGenerator.generate_template()                        │  ║
║  │           - AI usa SOLO indicatori assegnati (no freedom)              │  ║
║  │           - Costo: 1 AI call                                           │  ║
║  │   Step 3: ParametricGenerator (zero AI cost)                           │  ║
║  │                                                                        │  ║
║  │ Parametri base: NESSUNO (identico a ai_free)                           │  ║
║  │                                                                        │  ║
║  │ Coins: gestiti dal backtester (top N per volume, scroll-down)          │  ║
║  │                                                                        │  ║
║  │ Prefisso: Strategy_TYPE_8charID (es: Strategy_MOM_f2e5d8a1)            │  ║
║  │ DB: template_id=uuid, pattern_based=False + UsedIndicatorCombination   │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  Output: Strategy record con status=GENERATED                                ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ TABELLA COMPARATIVA                                                    │  ║
║  ├──────────────┬──────────────┬───────────────┬──────────────────────────┤  ║
║  │              │   PATTERN    │   AI_FREE     │      AI_ASSIGNED         │  ║
║  ├──────────────┼──────────────┼───────────────┼──────────────────────────┤  ║
║  │ Prefisso     │ PatStrat_    │ Strategy_     │ Strategy_                │  ║
║  │ Indicatori   │ Da formula   │ AI sceglie    │ IndicatorCombinator      │  ║
║  │ Params base  │ Da pattern   │ Nessuno       │ Nessuno                  │  ║
║  │ Coins        │ Per-edge     │ Backtester    │ Backtester               │  ║
║  │ AI calls     │ 0 o 1        │ 1             │ 1                        │  ║
║  │ Timeframe    │ Dal pattern  │ Random        │ Random                   │  ║
║  │ RR ratio     │ suggested_rr │ -             │ -                        │  ║
║  └──────────────┴──────────────┴───────────────┴──────────────────────────┘  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝



╔══════════════════════════════════════════════════════════════════════════════╗
║                              2. VALIDATOR                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Input: Strategy con status=GENERATED                                        ║
║  Output: status=VALIDATED (o DELETE se fallisce)                             ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ STEP 1: SYNTAX VALIDATION                                     <100ms   │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │ Controlli:                                                             │  ║
║  │   1. Python syntax valido (ast.parse)                                  │  ║
║  │   2. Import obbligatori:                                               │  ║
║  │      - pandas (o pd)                                                   │  ║
║  │      - StrategyCore, Signal da src.strategies.base                     │  ║
║  │   3. Esattamente 1 classe che eredita da StrategyCore                  │  ║
║  │   4. Nome classe valido:                                               │  ║
║  │      - Strategy_TYPE_hash (es: Strategy_MOM_abc123)                    │  ║
║  │      - PatStrat_TYPE_hash (es: PatStrat_REV_def456)                    │  ║
║  │   5. Metodo generate_signal(df) deve esistere                          │  ║
║  │                                                                        │  ║
║  │ Warnings (non bloccanti):                                              │  ║
║  │   - generate_signal senza return statement                             │  ║
║  │   - generate_signal con < 3 statements                                 │  ║
║  │   - Hardcoded timeframe ('5m', '15m', ecc.)                            │  ║
║  │                                                                        │  ║
║  │ Errori tipici:                                                         │  ║
║  │   [X] "Syntax error at line 15: invalid syntax"                        │  ║
║  │   [X] "Missing required import: Signal"                                │  ║
║  │   [X] "No class inheriting from StrategyCore found"                    │  ║
║  │   [X] "Invalid class name format: bad_name"                            │  ║
║  │                                                                        │  ║
║  │ FAIL -> DELETE strategy                                                │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                      |                                       ║
║                                      v                                       ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ STEP 2: LOOKAHEAD AST DETECTION                                <50ms   │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │ Static code analysis (AST parsing) per pattern che usano dati futuri   │  ║
║  │                                                                        │  ║
║  │ Pattern cercati:                                                       │  ║
║  │                                                                        │  ║
║  │   Pattern 1: rolling(center=True)                                      │  ║
║  │   [X] df['close'].rolling(20, center=True).mean()                      │  ║
║  │   [OK] df['close'].rolling(20).mean()                                  │  ║
║  │                                                                        │  ║
║  │   Pattern 2: shift(-N) con valori negativi                             │  ║
║  │   [X] df['close'].shift(-5)    # 5 bar nel futuro                      │  ║
║  │   [OK] df['close'].shift(5)     # 5 bar nel passato                    │  ║
║  │                                                                        │  ║
║  │   Pattern 3: expanding(center=True)                                    │  ║
║  │   [X] df['close'].expanding(center=True).max()                         │  ║
║  │   [OK] df['close'].expanding().max()                                   │  ║
║  │                                                                        │  ║
║  │   Pattern 4: iloc[i + offset] con offset positivo                      │  ║
║  │   [X] df.iloc[i + 5]   # Potrebbe accedere al futuro in loop           │  ║
║  │   [OK] df.iloc[i - 5]   # Look back                                    │  ║
║  │                                                                        │  ║
║  │ FAIL -> DELETE strategy                                                │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                      |                                       ║
║                                      v                                       ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ STEP 3: EXECUTION VALIDATION                               100-500ms   │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │ Runtime validation su dati sintetici (500 bar)                         │  ║
║  │                                                                        │  ║
║  │ Fasi:                                                                  │  ║
║  │   3a. Module Loading                                                   │  ║
║  │       - Scrive codice in file temporaneo                               │  ║
║  │       - Carica come modulo Python (importlib)                          │  ║
║  │       - Verifica subclass di StrategyCore                              │  ║
║  │                                                                        │  ║
║  │   3b. Instantiation                                                    │  ║
║  │       - Crea istanza: strategy = StrategyClass()                       │  ║
║  │       - Se fallisce: TypeError, missing arguments, ecc.                │  ║
║  │                                                                        │  ║
║  │   3c. Signal Generation Test                                           │  ║
║  │       - Two-phase approach:                                            │  ║
║  │         1. strategy.calculate_indicators(df)                           │  ║
║  │         2. strategy.generate_signal(df_with_indicators)                │  ║
║  │       - Testa in 5 punti: [50, 100, 200, 300, last_bar]                │  ║
║  │       - Valida: Signal o None, direction in [long, short, close]       │  ║
║  │                                                                        │  ║
║  │   3d. Edge Case Testing                                                │  ║
║  │       - Dati di varie lunghezze: [0, 1, 5, 10, 50, 100, 500]           │  ║
║  │       - Warning se eccezione (non blocking)                            │  ║
║  │                                                                        │  ║
║  │ Errori tipici:                                                         │  ║
║  │   [X] "Failed to load strategy class from code"                        │  ║
║  │   [X] "Failed to instantiate: TypeError: missing argument"             │  ║
║  │   [X] "generate_signal raised exception at bar 100: NameError"         │  ║
║  │   [X] "generate_signal returned str, expected Signal or None"          │  ║
║  │                                                                        │  ║
║  │ Warnings (non bloccanti):                                              │  ║
║  │   [!] "Strategy generated 0 signals on test data"                      │  ║
║  │   [!] "Strategy generated very few signals (2)"                        │  ║
║  │                                                                        │  ║
║  │ FAIL -> DELETE strategy                                                │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                      |                                       ║
║                                      v                                       ║
║                          ALL STEPS PASSED                                    ║
║                                      |                                       ║
║                                      v                                       ║
║                      strategy.status = VALIDATED                             ║
║                                      |                                       ║
║                                      v                                       ║
║                         -> Backtester Queue                                  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ NOTE IMPORTANTI                                                        │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ - Shuffle test (lookahead empirico) e' POST-BACKTEST, non qui          │  ║
║  │ - Deletion immediata se qualsiasi step fallisce                        │  ║
║  │ - Parallel execution: ThreadPoolExecutor (4 workers)                   │  ║
║  │ - Backpressure: se VALIDATED queue > limit, validator rallenta         │  ║
║  │ - Nessun caching: ogni strategia validata indipendentemente            │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  File coinvolti:                                                             ║
║  - src/validator/syntax_validator.py    -> SyntaxValidator                   ║
║  - src/validator/lookahead_detector.py  -> LookaheadDetector                 ║
║  - src/validator/execution_validator.py -> ExecutionValidator                ║
║  - src/validator/main_continuous.py     -> ValidatorProcess                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝




╔══════════════════════════════════════════════════════════════════════════════╗
║                         3. PARAMETRIC OPTIMIZATION                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Obiettivo: Testare ~1015 combinazioni (SL × TP × leverage × exit_bars)      ║
║             per trovare la configurazione ottimale per il base code.         ║
║                                                                              ║
║  Decision Flow:                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ is_pattern_based?                                                      │  ║
║  │    YES → has execution_type?                                           │  ║
║  │           YES → build_execution_type_space() (allineato al target)     │  ║
║  │           NO  → build_pattern_centered_space() (fallback)              │  ║
║  │    NO  → build_absolute_space(timeframe) (range assoluti per TF)       │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ EXECUTION TYPE ALIGNED SPACE (PREFERITO per PatStrat_*)               │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ Pattern-discovery valida i pattern su target con semantiche diverse:   │  ║
║  │                                                                        │  ║
║  │ TOUCH-BASED (target_max_*): verifica se prezzo TOCCA livello          │  ║
║  │   → Allineato con TP-based execution                                   │  ║
║  │   → TP DEVE esistere (centrato su magnitude)                           │  ║
║  │   → Exit time è backstop (può essere 0)                                │  ║
║  │                                                                        │  ║
║  │ CLOSE-BASED (tutti gli altri): verifica CLOSE a fine periodo          │  ║
║  │   → Allineato con time-based execution                                 │  ║
║  │   → TP DISABILITATO (sempre 0)                                         │  ║
║  │   → Exit time è primario (non può essere 0)                            │  ║
║  │                                                                        │  ║
║  │ ┌───────────────────────────────────────────────────────────────────┐  │  ║
║  │ │ TOUCH_BASED SPACE                                                │  │  ║
║  │ ├───────────────────────────────────────────────────────────────────┤  │  ║
║  │ │ TP:   [50%, 75%, 100%, 125%, 150%] di magnitude (NO zero)        │  │  ║
║  │ │ SL:   [100%, 150%, 200%, 250%] di magnitude (max 2.5:1 ratio)    │  │  ║
║  │ │ EXIT: [0, 100%, 150%, 200%] di holding_bars (0 = backstop off)   │  │  ║
║  │ │ LEV:  [1, 2, 3, 5, 10, 20, 40]                                   │  │  ║
║  │ │ Combinazioni: 5 × 4 × 4 × 7 = 560                                │  │  ║
║  │ └───────────────────────────────────────────────────────────────────┘  │  ║
║  │                                                                        │  ║
║  │ ┌───────────────────────────────────────────────────────────────────┐  │  ║
║  │ │ CLOSE_BASED SPACE                                                │  │  ║
║  │ ├───────────────────────────────────────────────────────────────────┤  │  ║
║  │ │ TP:   [0] SOLO (disabilitato - time exit è primario)             │  │  ║
║  │ │ SL:   [200%, 300%, 400%, 500%] di magnitude (wider per respiro)  │  │  ║
║  │ │ EXIT: [50%, 75%, 100%, 125%, 150%] di holding_bars (NO zero)     │  │  ║
║  │ │ LEV:  [1, 2, 3, 5, 10, 20, 40]                                   │  │  ║
║  │ │ Combinazioni: 1 × 4 × 5 × 7 = 140                                │  │  ║
║  │ └───────────────────────────────────────────────────────────────────┘  │  ║
║  │                                                                        │  ║
║  │ File: target_selector.py (selezione), parametric_backtest.py (spazio)  │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ PATTERN-CENTERED SPACE (fallback per PatStrat_* senza execution_type)  │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ Input dal pattern:                                                     │  ║
║  │   - base_tp_pct: target_magnitude (es: 6%)                             │  ║
║  │   - base_sl_pct: tp × suggested_rr_ratio (default 2.0, es: 12%)        │  ║
║  │   - base_exit_bars: holding_period (es: 20 bars)                       │  ║
║  │                                                                        │  ║
║  │ Espansione attorno ai valori validati:                                 │  ║
║  │   TP:   [0] + [50%, 75%, 100%, 125%, 150%] del base                    │  ║
║  │         → es: [0, 3%, 4.5%, 6%, 7.5%, 9%]                              │  ║
║  │   SL:   [50%, 75%, 100%, 150%, 200%] del base                          │  ║
║  │         → es: [6%, 9%, 12%, 18%, 24%]                                  │  ║
║  │   EXIT: [0] + [50%, 100%, 150%, 200%] del base                         │  ║
║  │         → es: [0, 10, 20, 30, 40]                                      │  ║
║  │   LEV:  [1, 2, 3, 5, 10, 20, 40] (da LEVERAGE_VALUES)                  │  ║
║  │                                                                        │  ║
║  │ Logica: pattern-discovery ha validato statisticamente i valori base.   │  ║
║  │         L'ottimizzazione esplora variazioni attorno a questi.          │  ║
║  │                                                                        │  ║
║  │ Combinazioni: 6 × 5 × 5 × 7 = 1050, minus invalide ≈ 1015              │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ ABSOLUTE SPACE (per Strategy_*)                                        │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ Fonte: parametric_constants.py (range empirici per timeframe)          │  ║
║  │                                                                        │  ║
║  │ ┌──────────┬────────────────────┬─────────────────────┬─────────────┐  │  ║
║  │ │ Timeframe│ SL range           │ TP range            │ Exit bars   │  │  ║
║  │ ├──────────┼────────────────────┼─────────────────────┼─────────────┤  │  ║
║  │ │ 5m       │ 0.5-2%             │ 0-5%                │ 0-160 (13h) │  │  ║
║  │ │ 15m      │ 1-5%               │ 0-10%               │ 0-100 (25h) │  │  ║
║  │ │ 30m      │ 1.5-6%             │ 0-15%               │ 0-60 (30h)  │  │  ║
║  │ │ 1h       │ 2-10%              │ 0-20%               │ 0-32 (32h)  │  │  ║
║  │ │ 2h       │ 3-10%              │ 0-25%               │ 0-24 (48h)  │  │  ║
║  │ └──────────┴────────────────────┴─────────────────────┴─────────────┘  │  ║
║  │                                                                        │  ║
║  │ Leverage: [1, 2, 3, 5, 10, 20, 40] (tutti i TF)                        │  ║
║  │                                                                        │  ║
║  │ Logica: AI strategies non hanno valori base validati.                  │  ║
║  │         Si usano range calibrati empiricamente per ogni TF.            │  ║
║  │                                                                        │  ║
║  │ Combinazioni: 5 × 6 × 5 × 7 = 1050, minus invalide ≈ 1015              │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ FILTRO COMBINAZIONI INVALIDE                                           │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ Escluse: tp_pct=0 AND exit_bars=0                                      │  ║
║  │ Motivo: nessuna condizione di uscita tranne SL (no exit strategy)      │  ║
║  │ Invalide per TF: ~35 combinazioni (5 SL × 1 TP × 1 exit × 7 lev)       │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ NUMBA KERNEL: _simulate_single_param_set                               │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ Position Sizing (Fixed Fractional):                                    │  ║
║  │   risk_amount = equity × risk_pct (default 2%)                         │  ║
║  │   notional = risk_amount / sl_pct                                      │  ║
║  │   margin_needed = notional / actual_leverage                           │  ║
║  │                                                                        │  ║
║  │ Leverage Cap (per-coin):                                               │  ║
║  │   actual_lev = min(strategy_leverage, coin.max_leverage)               │  ║
║  │   Es: BTC max=50x → usa fino a 40x, SHIB max=5x → usa max 5x           │  ║
║  │                                                                        │  ║
║  │ Margin Tracking:                                                       │  ║
║  │   margin_available = equity - margin_used                              │  ║
║  │   if margin_needed > margin_available → SKIP (simula exchange reject)  │  ║
║  │                                                                        │  ║
║  │ Min Notional Check:                                                    │  ║
║  │   if notional < 10 USDC → SKIP (Hyperliquid requirement)               │  ║
║  │                                                                        │  ║
║  │ Execution Costs (da config):                                           │  ║
║  │   Slippage: hyperliquid.slippage (tipicamente 0.05%)                   │  ║
║  │   Fees: hyperliquid.fee_rate × 2 (entry + exit, tipicamente 0.045%)    │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ METRICHE CALCOLATE: _calc_metrics                                      │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ sharpe:       Trade-based (non bar-by-bar), annualizzato               │  ║
║  │               Cap: sqrt(250) per evitare inflazione                    │  ║
║  │               Sanity: se total_return < 0, sharpe <= 0                 │  ║
║  │                                                                        │  ║
║  │ max_drawdown: (running_max - equity) / running_max, clamp [0, 1]       │  ║
║  │                                                                        │  ║
║  │ win_rate:     n_wins / n_trades                                        │  ║
║  │                                                                        │  ║
║  │ expectancy:   (WR × AvgWin%) - ((1-WR) × AvgLoss%)                     │  ║
║  │               Nota: PnL salvato come % del notional (non USD)          │  ║
║  │                                                                        │  ║
║  │ total_return: (equity_finale - iniziale) / iniziale                    │  ║
║  │                                                                        │  ║
║  │ total_trades: Conteggio trade completati                               │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ FORMULA SCORE (per combo)                                              │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │   score = ( 0.50 × edge_norm      +   # expectancy su range 0-10%      │  ║
║  │             0.25 × sharpe_norm    +   # sharpe su range 0-3            │  ║
║  │             0.15 × win_rate       +   # già 0-1                        │  ║
║  │             0.10 × stability      )   # 1 - max_drawdown               │  ║
║  │           × 100                                                        │  ║
║  │                                                                        │  ║
║  │   Output: 0-100 (clamped)                                              │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ THRESHOLD FILTER (per ogni combo)                                      │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ Da config.yaml → backtesting.thresholds:                               │  ║
║  │                                                                        │  ║
║  │   min_sharpe:      0.3    → sharpe >= 0.3                              │  ║
║  │   min_win_rate:    0.35   → win_rate >= 35%                            │  ║
║  │   min_total_trades: 10    → total_trades >= 10                         │  ║
║  │   min_expectancy:  0.002  → expectancy >= 0.2% per trade               │  ║
║  │   max_drawdown:    0.50   → max_dd <= 50%                              │  ║
║  │                                                                        │  ║
║  │ Combinazioni che non passano TUTTI i threshold → SCARTATE              │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  Output:                                                                     ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ DataFrame ordinato per score DESC (solo combo che passano threshold):  │  ║
║  │                                                                        │  ║
║  │ ┌───────┬───────┬─────┬──────┬────────┬────────┬────────┬───────────┐  │  ║
║  │ │sl_pct │tp_pct │ lev │ exit │ sharpe │ max_dd │win_rate│   score   │  │  ║
║  │ ├───────┼───────┼─────┼──────┼────────┼────────┼────────┼───────────┤  │  ║
║  │ │ 2.0%  │ 5.0%  │  3  │  20  │  1.82  │  0.15  │  0.58  │   72.4    │  │  ║
║  │ │ 1.5%  │ 3.0%  │  5  │  50  │  1.65  │  0.18  │  0.55  │   68.2    │  │  ║
║  │ │ ...   │ ...   │ ... │ ...  │  ...   │  ...   │  ...   │   ...     │  │  ║
║  │ └───────┴───────┴─────┴──────┴────────┴────────┴────────┴───────────┘  │  ║
║  │                                                                        │  ║
║  │ → BEST COMBO (#1) procede a IS backtest finale + OOS validation        │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  File coinvolti:                                                             ║
║  - src/backtester/parametric_backtest.py    → ParametricBacktester class     ║
║  - src/backtester/parametric_constants.py   → PARAM_SPACE, LEVERAGE_VALUES   ║
║  - src/backtester/main_continuous.py        → _run_parametric_backtest()     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝






╔══════════════════════════════════════════════════════════════════════════════╗
║                          4. BACKTEST IS FINALE                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Obiettivo: Eseguire backtest completo sui dati IN-SAMPLE con i best params  ║
║             dalla parametric optimization. Produce le metriche ufficiali IS. ║
║                                                                              ║
║  Input:                                                                      ║
║    - strategy_instance con params applicati (sl_pct, tp_pct, lev, exit)      ║
║    - is_data: 120 giorni di dati (Dict symbol -> DataFrame)                  ║
║    - best_params da PARAMETRIC OPTIMIZATION (best combo)                     ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ APPLICAZIONE BEST PARAMS                                               │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  Prima del backtest, i best params da PARAMETRIC vengono applicati:    │  ║
║  │                                                                        │  ║
║  │    strategy_instance.sl_pct = best_params['sl_pct']         # 0.02     │  ║
║  │    strategy_instance.tp_pct = best_params['tp_pct']         # 0.05     │  ║
║  │    strategy_instance.leverage = best_params['leverage']     # 3        │  ║
║  │    strategy_instance.exit_after_bars = best_params['exit_bars']  # 20  │  ║
║  │                                                                        │  ║
║  │  Nota: Questi sono i best params dalla parametric optimization         │  ║
║  │        (combo #1 per score, che ha passato threshold + robustness)     │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ _run_multi_symbol_backtest()                                           │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  Portfolio backtest con vincoli realistici:                            │  ║
║  │                                                                        │  ║
║  │    - Max concurrent positions: da config (default 10)                  │  ║
║  │    - Shared capital pool: tutte le posizioni condividono equity        │  ║
║  │    - Position priority: ordine temporale dei segnali                   │  ║
║  │    - Multi-symbol: tutti i coins assegnati alla strategia              │  ║
║  │                                                                        │  ║
║  │  Filtro dati:                                                          │  ║
║  │    - min_bars = 100 (default per IS)                                   │  ║
║  │    - Simboli con < 100 bars -> esclusi                                 │  ║
║  │    - Se nessun simbolo valido -> return {total_trades: 0}              │  ║
║  │                                                                        │  ║
║  │  Engine: BacktestEngine.backtest()                                     │  ║
║  │    - Usa parametri timeframe per Sharpe annualization corretta         │  ║
║  │    - Simula margin tracking, fees, slippage                            │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ METRICHE OUTPUT (is_result)                                            │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  ┌──────────────────┬──────────────────────────────────────────────┐   │  ║
║  │  │ Metrica          │ Descrizione                                  │   │  ║
║  │  ├──────────────────┼──────────────────────────────────────────────┤   │  ║
║  │  │ sharpe_ratio     │ Annualizzato, trade-based                    │   │  ║
║  │  │ win_rate         │ n_wins / total_trades                        │   │  ║
║  │  │ expectancy       │ (WR * AvgWin%) - ((1-WR) * AvgLoss%)         │   │  ║
║  │  │ max_drawdown     │ Peak-to-trough massimo                       │   │  ║
║  │  │ total_trades     │ Numero trade completati                      │   │  ║
║  │  │ total_return     │ (equity_finale - iniziale) / iniziale        │   │  ║
║  │  │ avg_trade_pnl    │ PnL medio per trade                          │   │  ║
║  │  │ profit_factor    │ gross_profit / gross_loss                    │   │  ║
║  │  └──────────────────┴──────────────────────────────────────────────┘   │  ║
║  │                                                                        │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ VALIDAZIONE IS                                                         │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  Controllo minimo:                                                     │  ║
║  │    if is_result['total_trades'] == 0:                                  │  ║
║  │        DELETE strategy ("No trades in IS")                             │  ║
║  │                                                                        │  ║
║  │  Nota: Altri threshold (sharpe, win_rate, ecc.) sono gia' stati        │  ║
║  │        verificati durante PARAMETRIC OPTIMIZATION. Qui si controlla    │  ║
║  │        solo che il backtest finale produca trade.                      │  ║
║  │                                                                        │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ DIFFERENZA DA PARAMETRIC                                               │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  ┌─────────────────────┬─────────────────────────────────────────┐     │  ║
║  │  │ PARAMETRIC          │ IS FINALE                               │     │  ║
║  │  ├─────────────────────┼─────────────────────────────────────────┤     │  ║
║  │  │ ~1015 combinazioni  │ 1 sola (best params)                    │     │  ║
║  │  │ Numba kernel veloce │ BacktestEngine completo                 │     │  ║
║  │  │ Metriche aggregate  │ Metriche dettagliate + equity curve     │     │  ║
║  │  │ Per trovare best    │ Per metriche ufficiali                  │     │  ║
║  │  └─────────────────────┴─────────────────────────────────────────┘     │  ║
║  │                                                                        │  ║
║  │  Il parametric usa kernel Numba ottimizzato per velocita'.             │  ║
║  │  IS finale usa BacktestEngine per metriche complete e accurate.        │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  Output:                                                                     ║
║    - is_result: Dict con tutte le metriche IS                                ║
║    - Se total_trades == 0 -> DELETE strategy                                 ║
║    - Altrimenti -> procede a BACKTEST OOS                                    ║
║                                                                              ║
║  File coinvolti:                                                             ║
║  - src/backtester/main_continuous.py -> _run_multi_symbol_backtest()         ║
║  - src/backtester/backtest_engine.py -> BacktestEngine.backtest()            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝







╔══════════════════════════════════════════════════════════════════════════════╗
║                           5. BACKTEST OOS                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Obiettivo: Testare la strategia su dati OUT-OF-SAMPLE (30 giorni recenti)   ║
║             per verificare che non sia overfittata sui dati IS.              ║
║                                                                              ║
║  Input:                                                                      ║
║    - strategy_instance con best params da parametric                         ║
║    - oos_data: 30 giorni piu' recenti (Dict symbol -> DataFrame)             ║
║    - is_result: metriche dal backtest IS                                     ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ TIMELINE DATI                                                          │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  150 giorni totali:                                                    │  ║
║  │  ════════════════════════════════════════════════════════════════════  │  ║
║  │                                                                        │  ║
║  │  [--- IN-SAMPLE (120 giorni) ---][-- OOS (30 giorni) --]               │  ║
║  │  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^               │  ║
║  │  Parametric optimization          Validazione anti-overfit             │  ║
║  │                                                                        │  ║
║  │  OOS = dati PIU' RECENTI = "come performa ADESSO"                      │  ║
║  │  IS e OOS sono NON-OVERLAPPING (nessun data leakage)                   │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ ESECUZIONE BACKTEST OOS                                                │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  Stesso engine di IS, ma con parametri diversi:                        │  ║
║  │    - min_bars = 20 (vs 100 per IS)                                     │  ║
║  │    - Periodo piu' corto = meno bars disponibili                        │  ║
║  │                                                                        │  ║
║  │  oos_result = _run_multi_symbol_backtest(                              │  ║
║  │      strategy_instance,                                                │  ║
║  │      oos_data,                                                         │  ║
║  │      timeframe,                                                        │  ║
║  │      min_bars=20    # Lower threshold per OOS                          │  ║
║  │  )                                                                     │  ║
║  │                                                                        │  ║
║  │  Se oos_data ha < 5 simboli validi -> oos_result = None                │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ _validate_oos(): VALIDAZIONE ANTI-OVERFITTING                          │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  Step 1: Controllo IS (prerequisito)                                   │  ║
║  │    - is_trades >= min_trades_is[timeframe]                             │  ║
║  │    - is_sharpe >= min_sharpe (0.3, da config)                          │  ║
║  │    Se fallisce -> REJECT (IS non ha edge)                              │  ║
║  │                                                                        │  ║
║  │  Step 2: Controllo OOS trades                                          │  ║
║  │    - oos_trades >= min_trades_oos[timeframe]                           │  ║
║  │    Se fallisce -> REJECT (dati insufficienti)                          │  ║
║  │                                                                        │  ║
║  │  Step 3: Calcolo degradation                                           │  ║
║  │                                                                        │  ║
║  │              is_sharpe - oos_sharpe                                    │  ║
║  │    degrad = ──────────────────────────                                 │  ║
║  │                    is_sharpe                                           │  ║
║  │                                                                        │  ║
║  │    degrad > 0: OOS peggiore di IS (normale)                            │  ║
║  │    degrad < 0: OOS migliore di IS (bonus!)                             │  ║
║  │    degrad = 0: Performance identica                                    │  ║
║  │                                                                        │  ║
║  │  Step 4: Check overfitting                                             │  ║
║  │    - Se degradation > oos_max_degradation (50%) -> REJECT              │  ║
║  │    - Motivo: "Overfitted: OOS 60% worse than IS"                       │  ║
║  │                                                                        │  ║
║  │  Step 5: Check OOS Sharpe minimo                                       │  ║
║  │    - oos_sharpe >= oos_min_sharpe (0.0, da config)                     │  ║
║  │    - Deve essere almeno non negativo                                   │  ║
║  │                                                                        │  ║
║  │  Step 6: Calcolo OOS bonus/penalty                                     │  ║
║  │    - OOS >= IS: bonus = min(0.20, |degrad| * 0.5)                      │  ║
║  │    - OOS < IS:  penalty = -degrad * 0.10                               │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ MIN TRADES PER TIMEFRAME (da config)                                   │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  ┌───────────┬─────────────┬─────────────┐                             │  ║
║  │  │ Timeframe │ min_is      │ min_oos     │                             │  ║
║  │  ├───────────┼─────────────┼─────────────┤                             │  ║
║  │  │ 5m        │ 500         │ 50          │                             │  ║
║  │  │ 15m       │ 300         │ 30          │                             │  ║
║  │  │ 30m       │ 200         │ 20          │                             │  ║
║  │  │ 1h        │ 100         │ 10          │                             │  ║
║  │  │ 2h        │ 50          │ 5           │                             │  ║
║  │  └───────────┴─────────────┴─────────────┘                             │  ║
║  │                                                                        │  ║
║  │  Timeframe alti = meno opportunita' = soglie piu' basse                │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ MOTIVI DI REJECT                                                       │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  [X] "IS trades insufficient: 45 < 100 (for 1h)"                       │  ║
║  │  [X] "IS Sharpe too low: 0.25 < 0.3"                                   │  ║
║  │  [X] "OOS trades insufficient: 8 < 10 (for 1h)"                        │  ║
║  │  [X] "Overfitted: OOS 65% worse than IS"                               │  ║
║  │  [X] "OOS Sharpe too low: -0.15 < 0.0"                                 │  ║
║  │                                                                        │  ║
║  │  REJECT -> DELETE strategy                                             │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ _calculate_final_metrics(): METRICHE FINALI                            │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  Pesi: IS = 40%, OOS = 60% (recency = "adesso conta di piu'")          │  ║
║  │                                                                        │  ║
║  │  Metriche pesate:                                                      │  ║
║  │    weighted_sharpe   = is_sharpe * 0.4 + oos_sharpe * 0.6              │  ║
║  │    weighted_expect   = is_expect * 0.4 + oos_expect * 0.6              │  ║
║  │    weighted_win_rate = is_wr * 0.4 + oos_wr * 0.6                      │  ║
║  │    weighted_max_dd   = is_dd * 0.4 + oos_dd * 0.6                      │  ║
║  │                                                                        │  ║
║  │  Score parziali:                                                       │  ║
║  │    is_score  = 0.5*sharpe + 0.3*expect + 0.2*win_rate                  │  ║
║  │    oos_score = 0.5*sharpe + 0.3*expect + 0.2*win_rate                  │  ║
║  │                                                                        │  ║
║  │  Final score:                                                          │  ║
║  │    final = (is_score * 0.4 + oos_score * 0.6) * (1 + oos_bonus)        │  ║
║  │                                                                        │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  Output:                                                                     ║
║    - validation: {passed, reason, degradation, oos_bonus}                    ║
║    - final_result: Dict con tutte le metriche pesate + final_score           ║
║    - Se passed=False -> DELETE strategy                                      ║
║    - Se passed=True  -> procede a SCORE + SHUFFLE + POOL ENTRY               ║
║                                                                              ║
║  File coinvolti:                                                             ║
║  - src/backtester/main_continuous.py -> _validate_oos()                      ║
║  - src/backtester/main_continuous.py -> _calculate_final_metrics()           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝







╔══════════════════════════════════════════════════════════════════════════════╗
║                            6. SCORE CALCULATION                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Obiettivo: Calcolare lo score finale della strategia combinando metriche    ║
║             IS e OOS per il ranking nel pool.                                ║
║                                                                              ║
║  Input:                                                                      ║
║    - backtest_result: BacktestResult con metriche IS                         ║
║    - final_result: metriche pesate IS+OOS                                    ║
║    - degradation: (is_sharpe - oos_sharpe) / is_sharpe                       ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ FORMULA SCORE (5 componenti)                                           │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  BacktestScorer.score_from_backtest_result()                           │  ║
║  │                                                                        │  ║
║  │  Formula:                                                              │  ║
║  │    score = ( 0.40 * expectancy_norm +                                  │  ║
║  │              0.25 * sharpe_norm +                                      │  ║
║  │              0.10 * win_rate_norm +                                    │  ║
║  │              0.15 * drawdown_norm +                                    │  ║
║  │              0.10 * recency_norm ) * 100                               │  ║
║  │                                                                        │  ║
║  │  Normalizzazioni:                                                      │  ║
║  │    expectancy_norm: [0, 0.10] -> [0, 1]   (0-10% edge)                 │  ║
║  │    sharpe_norm:     [0, 3.0]  -> [0, 1]                                │  ║
║  │    win_rate_norm:   gia' [0, 1]                                        │  ║
║  │    drawdown_norm:   1 - (dd / 0.30)       (30% max = 0)                │  ║
║  │    recency_norm:    0.5 - degradation     (OOS vs IS)                  │  ║
║  │                                                                        │  ║
║  │  Output: score 0-100                                                   │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ SCORE THRESHOLD CHECK                                                  │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  if score < pool_min_score (40):                                       │  ║
║  │      -> SKIP tutti i test successivi (shuffle, WFA)                    │  ║
║  │      -> EventTracker.backtest_score_rejected()                         │  ║
║  │      -> return (False, "score_below_threshold:38.5")                   │  ║
║  │      -> status = RETIRED                                               │  ║
║  │                                                                        │  ║
║  │  Solo strategie con score >= 40 procedono al shuffle test.             │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  Output:                                                                     ║
║    - score >= 40 -> procede a SHUFFLE TEST                                   ║
║    - score < 40  -> RETIRED (no point testing further)                       ║
║                                                                              ║
║  File coinvolti:                                                             ║
║  - src/backtester/main_continuous.py -> _promote_to_active_pool()            ║
║  - src/scorer/backtest_scorer.py     -> BacktestScorer                       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝





╔══════════════════════════════════════════════════════════════════════════════╗
║                            7. SHUFFLE TEST                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Obiettivo: Rilevare lookahead bias NON catturato dall'AST analysis          ║
║             tramite test empirico sui dati shuffled.                         ║
║                                                                              ║
║  Input:                                                                      ║
║    - strategy: model con code e base_code_hash                               ║
║    - score >= 40 (threshold passato)                                         ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ LOGICA SHUFFLE TEST                                                    │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  1. Carica 30 giorni di BTC data (timeframe della strategia)           │  ║
║  │  2. Genera segnali su dati ORIGINALI                                   │  ║
║  │  3. SHUFFLE le righe del DataFrame (rompe correlazioni temporali)      │  ║
║  │  4. Genera segnali su dati SHUFFLED                                    │  ║
║  │  5. Confronta: se segnali IDENTICI -> LOOKAHEAD BIAS                   │  ║
║  │                                                                        │  ║
║  │  Perche' funziona:                                                     │  ║
║  │    - Strategia legittima: segnali dipendono da SEQUENZA temporale      │  ║
║  │    - Shuffle rompe sequenza -> segnali DIVERSI                         │  ║
║  │    - Se segnali uguali: sta guardando valori "assoluti", non sequenza  │  ║
║  │      (es: df['future_price'] > df['close'])                            │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ CACHING (by base_code_hash)                                            │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  - Lookahead e' proprieta' del BASE CODE, non dei parametri            │  ║
║  │  - Se base code passa -> tutte le strategie parametriche passano       │  ║
║  │  - Cache in ValidationCache table                                      │  ║
║  │  - Cache HIT: ~0ms, Cache MISS: ~50-100ms                              │  ║
║  │                                                                        │  ║
║  │  Lookup: ValidationCache.get(base_code_hash, 'shuffle_test')           │  ║
║  │    - EXISTS + passed=True  -> skip test, return PASS                   │  ║
║  │    - EXISTS + passed=False -> skip test, return FAIL                   │  ║
║  │    - NOT EXISTS -> esegui test, salva risultato                        │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  Output:                                                                     ║
║    - PASS -> procede a WFA FIXED PARAMS                                      ║
║    - FAIL -> return (False, "shuffle_test_failed")                           ║
║              Strategy status = RETIRED (non DELETE, code riusabile)          ║
║                                                                              ║
║  File coinvolti:                                                             ║
║  - src/backtester/main_continuous.py -> _promote_to_active_pool()            ║
║  - src/validator/lookahead_test.py   -> LookaheadTester.validate()           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝






╔══════════════════════════════════════════════════════════════════════════════╗
║                          8. WFA FIXED PARAMS                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Obiettivo: Verificare che i best params (da parametric optimization)        ║
║             funzionino su TUTTO il periodo storico, non solo su una parte.   ║
║                                                                              ║
║  Input:                                                                      ║
║    - strategy con best_params fissi                                          ║
║    - dati IS completi (120 giorni)                                           ║
║    - shuffle test passato                                                    ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ EXPANDING WINDOWS (4 finestre)                                         │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  IS Data (120 giorni):                                                 │  ║
║  │  ════════════════════════════════════════════════════════════════════  │  ║
║  │                                                                        │  ║
║  │  Window 1 (25%):  ███████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │  ║
║  │                   └── giorni 1-30                                      │  ║
║  │                                                                        │  ║
║  │  Window 2 (50%):  ██████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │  ║
║  │                   └── giorni 1-60                                      │  ║
║  │                                                                        │  ║
║  │  Window 3 (75%):  █████████████████████████████████░░░░░░░░░░░░░░░░░   │  ║
║  │                   └── giorni 1-90                                      │  ║
║  │                                                                        │  ║
║  │  Window 4 (100%): ██████████████████████████████████████████████████   │  ║
║  │                   └── giorni 1-120                                     │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ LOGICA WFA FIXED PARAMS                                                │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  Per ogni window:                                                      │  ║
║  │    1. Slice dati: _slice_data_by_percentage(is_data, pct)              │  ║
║  │    2. Backtest con params FISSI (NO ri-ottimizzazione!)                │  ║
║  │    3. Calcola expectancy per la window                                 │  ║
║  │                                                                        │  ║
║  │  Criterio di successo:                                                 │  ║
║  │    - TUTTE e 4 le windows devono avere expectancy >= 0.002 (0.2%)      │  ║
║  │    - Se anche UNA sola window fallisce -> strategia FAIL               │  ║
║  │                                                                        │  ║
║  │  Esempio PASS:                                                         │  ║
║  │    W1: exp=0.0035, W2: exp=0.0028, W3: exp=0.0041, W4: exp=0.0032      │  ║
║  │    -> Tutte >= 0.002 -> PASS                                           │  ║
║  │                                                                        │  ║
║  │  Esempio FAIL:                                                         │  ║
║  │    W1: exp=0.0035, W2: exp=0.0012, W3: exp=0.0041, W4: exp=0.0032      │  ║
║  │    -> W2 < 0.002 -> FAIL ("insufficient_profitable_windows:3/4")       │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ DIFFERENZA DALLA VECCHIA WFA                                           │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  ┌───────────────────────┬───────────────────────────────────────┐     │  ║
║  │  │ VECCHIA WFA           │ NUOVA WFA (FIXED PARAMS)              │     │  ║
║  │  ├───────────────────────┼───────────────────────────────────────┤     │  ║
║  │  │ Ri-ottimizza params   │ Params FISSI (da parametric)          │     │  ║
║  │  │ ogni window           │                                       │     │  ║
║  │  ├───────────────────────┼───────────────────────────────────────┤     │  ║
║  │  │ Check: CV params      │ Check: expectancy >= 0.002            │     │  ║
║  │  │ (stabilita')          │ (profitability)                       │     │  ║
║  │  ├───────────────────────┼───────────────────────────────────────┤     │  ║
║  │  │ ~4200 simulazioni     │ 4 simulazioni (1 per window)          │     │  ║
║  │  │ (4 × 1050 combo)      │                                       │     │  ║
║  │  ├───────────────────────┼───────────────────────────────────────┤     │  ║
║  │  │ Output: optimal_params│ Output: pass/fail                     │     │  ║
║  │  └───────────────────────┴───────────────────────────────────────┘     │  ║
║  │                                                                        │  ║
║  │  Vantaggio: Molto piu' veloce, verifica che i params ottimizzati       │  ║
║  │             siano generalizzabili su tutto il periodo.                 │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  Config (config.yaml):                                                       ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │  wfa_validation:                                                       │  ║
║  │    enabled: true                                                       │  ║
║  │    window_percentages: [0.25, 0.50, 0.75, 1.0]                         │  ║
║  │    min_expectancy: 0.002       # 0.2% per window                       │  ║
║  │    min_profitable_windows: 4   # Tutte devono passare                  │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  Output:                                                                     ║
║    - PASS (4/4 windows) -> procede a POOL ENTRY                              ║
║    - FAIL (<4 windows)  -> return (False, "insufficient_profitable_windows") ║
║                           Strategy status = RETIRED                          ║
║                                                                              ║
║  File coinvolti:                                                             ║
║  - src/backtester/main_continuous.py -> _run_wfa_fixed_params()              ║
║  - src/backtester/main_continuous.py -> _slice_data_by_percentage()          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝







╔══════════════════════════════════════════════════════════════════════════════╗
║                             9. POOL ENTRY                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Obiettivo: Inserire la strategia validata nel pool ACTIVE (leaderboard)     ║
║             competendo con le strategie esistenti per score.                 ║
║                                                                              ║
║  Input:                                                                      ║
║    - strategy che ha passato: Score >= 40, Shuffle, WFA                      ║
║    - score finale calcolato                                                  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ POOL RULES (leaderboard logic)                                         │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  PoolManager.try_enter_pool(strategy_id, score)                        │  ║
║  │                                                                        │  ║
║  │  Regole (con lock per thread safety):                                  │  ║
║  │                                                                        │  ║
║  │    Rule 1: score < min_score (40)                                      │  ║
║  │            -> RETIRED (non entra mai)                                  │  ║
║  │                                                                        │  ║
║  │    Rule 2: pool_count < max_size (300)                                 │  ║
║  │            -> ENTRA (c'e' spazio)                                      │  ║
║  │            -> status = ACTIVE                                          │  ║
║  │                                                                        │  ║
║  │    Rule 3: pool pieno AND score > worst_score                          │  ║
║  │            -> EVICT worst strategy (status = RETIRED)                  │  ║
║  │            -> ENTRA al suo posto                                       │  ║
║  │            -> status = ACTIVE                                          │  ║
║  │                                                                        │  ║
║  │    Rule 4: pool pieno AND score <= worst_score                         │  ║
║  │            -> NON entra                                                │  ║
║  │            -> status = RETIRED                                         │  ║
║  │                                                                        │  ║
║  │  Lock: _pool_lock garantisce atomicita' check+insert                   │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ ESEMPIO LEADERBOARD                                                    │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  Pool (max 300, attuale 300):                                          │  ║
║  │    n.1:   Strategy_A  score=92.5                                       │  ║
║  │    n.2:   Strategy_B  score=88.2                                       │  ║
║  │    ...                                                                 │  ║
║  │    n.299: Strategy_Y  score=45.1                                       │  ║
║  │    n.300: Strategy_Z  score=42.3  <- WORST                             │  ║
║  │                                                                        │  ║
║  │  Nuova strategia con score=48.7:                                       │  ║
║  │    -> 48.7 > 42.3 (worst)                                              │  ║
║  │    -> Strategy_Z RETIRED                                               │  ║
║  │    -> Nuova strategia ENTRA al n.299                                   │  ║
║  │                                                                        │  ║
║  │  Nuova strategia con score=41.0:                                       │  ║
║  │    -> 41.0 < 42.3 (worst)                                              │  ║
║  │    -> Nuova strategia RETIRED (non abbastanza buona)                   │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ EVENTI EMESSI                                                          │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  EventTracker.backtest_scored(...)        # Score calcolato            │  ║
║  │  EventTracker.shuffle_test_passed(...)    # Shuffle test passato       │  ║
║  │  EventTracker.pool_attempted(...)         # Tentativo ingresso pool    │  ║
║  │  EventTracker.pool_entered(...)           # Ingresso pool riuscito     │  ║
║  │  EventTracker.pool_rejected(...)          # Ingresso pool rifiutato    │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  Output:                                                                     ║
║    - ENTERED  -> strategy.status = ACTIVE, nel pool, pronta per ROTATION     ║
║    - REJECTED -> strategy.status = RETIRED, fuori pool                       ║
║                                                                              ║
║  File coinvolti:                                                             ║
║  - src/backtester/main_continuous.py -> _promote_to_active_pool()            ║
║  - src/scorer/pool_manager.py        -> PoolManager.try_enter_pool()         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝






╔══════════════════════════════════════════════════════════════════════════════╗
║                          10. ROTATION -> LIVE                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Obiettivo: Selezionare le migliori strategie dal pool ACTIVE e deployarle   ║
║             sui subaccount Hyperliquid per il trading LIVE.                  ║
║                                                                              ║
║  Daemon: ContinuousRotatorProcess (src/rotator/main_continuous.py)           ║
║  Intervallo: check_interval_minutes (default 5 min)                          ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ STEP 1: CHECK FREE SLOTS                                               │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  StrategySelector.get_free_slots()                                     │  ║
║  │                                                                        │  ║
║  │    free_slots = max_live_strategies - live_count                       │  ║
║  │                                                                        │  ║
║  │  Esempio:                                                              │  ║
║  │    max_live_strategies = 10 (config)                                   │  ║
║  │    live_count = 7 (strategie con status=LIVE)                          │  ║
║  │    free_slots = 3                                                      │  ║
║  │                                                                        │  ║
║  │  Se free_slots = 0 -> SKIP (nessuno slot disponibile)                  │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ STEP 2: CHECK POOL READY                                               │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  StrategySelector.is_pool_ready()                                      │  ║
║  │                                                                        │  ║
║  │    active_count >= min_pool_size                                       │  ║
║  │                                                                        │  ║
║  │  Esempio:                                                              │  ║
║  │    min_pool_size = 50 (config)                                         │  ║
║  │    active_count = 23 (strategie con status=ACTIVE)                     │  ║
║  │    pool_ready = False -> SKIP (pool non abbastanza maturo)             │  ║
║  │                                                                        │  ║
║  │  Logica: Aspettare che il pool sia popolato prima di deployare,        │  ║
║  │          per avere una selezione migliore.                             │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ STEP 3: SELECT CANDIDATES (con diversificazione)                       │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  StrategySelector.get_candidates(slots_available)                      │  ║
║  │                                                                        │  ║
║  │  Filtri applicati:                                                     │  ║
║  │    1. status = 'ACTIVE' (nel pool)                                     │  ║
║  │    2. score_backtest >= min_score (40)                                 │  ║
║  │    3. ORDER BY score_backtest DESC                                     │  ║
║  │                                                                        │  ║
║  │  Vincoli diversificazione (check vs LIVE esistenti):                   │  ║
║  │    - max_per_type: 3 (es: max 3 MOM, max 3 REV, etc.)                  │  ║
║  │    - max_per_timeframe: 3 (es: max 3 su 15m, max 3 su 1h)              │  ║
║  │                                                                        │  ║
║  │  Esempio selezione:                                                    │  ║
║  │                                                                        │  ║
║  │    LIVE esistenti: 2 MOM, 2 REV, 1 TRN (su 15m, 30m, 1h)               │  ║
║  │    slots_available: 2                                                  │  ║
║  │                                                                        │  ║
║  │    Candidato #1: Strategy_MOM_abc (score=78, type=MOM, tf=15m)         │  ║
║  │      -> MOM count: 2+1=3 <= max_per_type(3) OK                         │  ║
║  │      -> 15m count: 2+1=3 <= max_per_timeframe(3) OK                    │  ║
║  │      -> SELEZIONATO                                                    │  ║
║  │                                                                        │  ║
║  │    Candidato #2: Strategy_MOM_def (score=75, type=MOM, tf=15m)         │  ║
║  │      -> MOM count: 3+1=4 > max_per_type(3) SKIP                        │  ║
║  │                                                                        │  ║
║  │    Candidato #3: Strategy_BRE_ghi (score=72, type=BRE, tf=2h)          │  ║
║  │      -> BRE count: 0+1=1 <= max_per_type(3) OK                         │  ║
║  │      -> 2h count: 0+1=1 <= max_per_timeframe(3) OK                     │  ║
║  │      -> SELEZIONATO                                                    │  ║
║  │                                                                        │  ║
║  │    Output: [Strategy_MOM_abc, Strategy_BRE_ghi]                        │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ STEP 4: GET FREE SUBACCOUNTS                                           │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  StrategyDeployer.get_free_subaccounts()                               │  ║
║  │                                                                        │  ║
║  │  Subaccount libero: strategy_id IS NULL                                │  ║
║  │                                                                        │  ║
║  │  Se subaccount non esistono -> creati automaticamente                  │  ║
║  │    n_subaccounts da config (default 10)                                │  ║
║  │                                                                        │  ║
║  │  Output: [{id: 1, allocated_capital: 0}, {id: 5, allocated_capital: 0}]│  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ STEP 5: DEPLOY                                                         │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  Per ogni (candidate, free_subaccount):                                │  ║
║  │                                                                        │  ║
║  │    StrategyDeployer.deploy(strategy, subaccount_id)                    │  ║
║  │                                                                        │  ║
║  │    1. Calcola capital allocation:                                      │  ║
║  │       capital_per = total_capital / (active_subaccounts + 1)           │  ║
║  │       Es: $10,000 / 8 = $1,250 per subaccount                          │  ║
║  │                                                                        │  ║
║  │    2. Update Subaccount:                                               │  ║
║  │       subaccount.strategy_id = strategy_id                             │  ║
║  │       subaccount.status = 'ACTIVE'                                     │  ║
║  │       subaccount.allocated_capital = capital_per                       │  ║
║  │       subaccount.deployed_at = now()                                   │  ║
║  │                                                                        │  ║
║  │    3. Update Strategy:                                                 │  ║
║  │       strategy.status = 'LIVE'                                         │  ║
║  │       strategy.live_since = now()                                      │  ║
║  │                                                                        │  ║
║  │    4. Emit events:                                                     │  ║
║  │       EventTracker.strategy_promoted_live()                            │  ║
║  │       EventTracker.deployment_succeeded()                              │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ UNDEPLOY (quando strategia viene ritirata)                             │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  StrategyDeployer.undeploy(strategy_id, reason)                        │  ║
║  │                                                                        │  ║
║  │  Trigger:                                                              │  ║
║  │    - Monitor rileva degradation (live score << backtest score)         │  ║
║  │    - Re-test fallisce (OOS peggiorato)                                 │  ║
║  │    - Manuale (admin command)                                           │  ║
║  │                                                                        │  ║
║  │  Azioni:                                                               │  ║
║  │    1. Chiudi posizioni aperte (se non dry_run)                         │  ║
║  │    2. Libera subaccount:                                               │  ║
║  │       subaccount.strategy_id = NULL                                    │  ║
║  │       subaccount.status = 'PAUSED'                                     │  ║
║  │    3. Update strategia:                                                │  ║
║  │       strategy.status = 'RETIRED'                                      │  ║
║  │       strategy.retired_at = now()                                      │  ║
║  │    4. Emit event:                                                      │  ║
║  │       EventTracker.strategy_retired()                                  │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ STRATEGY STATUS LIFECYCLE (completo)                                   │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                        │  ║
║  │  GENERATED --> VALIDATED --> [ACTIVE pool] --> LIVE --> RETIRED        │  ║
║  │       |            |              |             |                      │  ║
║  │       v            v              v             v                      │  ║
║  │    (DELETE)     (DELETE)      (RETIRED)    (RETIRED)                   │  ║
║  │                                                                        │  ║
║  │  Nota: FAILED non e' uno status, la strategia viene DELETE             │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  Config (config.yaml):                                                       ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │  rotator:                                                              │  ║
║  │    check_interval_minutes: 5                                           │  ║
║  │    max_live_strategies: 10                                             │  ║
║  │    min_pool_size: 50        # Aspetta che pool sia maturo              │  ║
║  │    selection:                                                          │  ║
║  │      max_per_type: 3        # Max strategie stesso tipo                │  ║
║  │      max_per_timeframe: 3   # Max strategie stesso TF                  │  ║
║  │                                                                        │  ║
║  │  hyperliquid:                                                          │  ║
║  │    subaccounts:                                                        │  ║
║  │      count: 10              # Numero subaccount disponibili            │  ║
║  │    dry_run: true            # Se true, no ordini reali                 │  ║
║  │                                                                        │  ║
║  │  trading:                                                              │  ║
║  │    total_capital: 10000     # Capitale totale da distribuire           │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  File coinvolti:                                                             ║
║  - src/rotator/main_continuous.py -> ContinuousRotatorProcess                ║
║  - src/rotator/selector.py        -> StrategySelector                        ║
║  - src/rotator/deployer.py        -> StrategyDeployer                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝