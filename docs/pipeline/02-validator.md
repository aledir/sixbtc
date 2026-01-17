# 2. Validator

Il Validator daemon verifica che le strategie generate siano sintatticamente corrette, senza lookahead bias e funzionanti a runtime.

**Daemon**: `src/validator/main_continuous.py`
**Input**: Strategy con `status=GENERATED`
**Output**: `status=VALIDATED` (o DELETE se fallisce)

---

## Flow

```
STEP 1: Syntax Validation    (<100ms)
           ↓
STEP 2: Lookahead AST Detection    (<50ms)
           ↓
STEP 3: Execution Validation    (100-500ms)
           ↓
      ALL STEPS PASSED
           ↓
   status = VALIDATED
           ↓
      Backtester Queue
```

---

## STEP 1: SYNTAX VALIDATION

**Timing**: <100ms

### Controlli

1. **Python syntax valido** (`ast.parse`)
2. **Import obbligatori**:
   - pandas (o pd)
   - StrategyCore, Signal da `src.strategies.base`
3. **Esattamente 1 classe** che eredita da StrategyCore
4. **Nome classe valido** (prefisso):
   - `PatStrat_TYPE_hash` (es: `PatStrat_MOM_abc123`)
   - `UngStrat_TYPE_hash` (es: `UngStrat_CRS_def456`) - Smart
   - `UggStrat_TYPE_hash` (es: `UggStrat_BRK_abc123`) - Genetic
   - `PGnStrat_TYPE_hash` (es: `PGnStrat_THR_12ab34cd`) - Smart
   - `PGgStrat_TYPE_hash` (es: `PGgStrat_CRS_56ef78gh`) - Genetic
   - `PtaStrat_TYPE_hash` (es: `PtaStrat_VOL_789abc`)
   - `AIFStrat_TYPE_hash` (es: `AIFStrat_REV_789abc`)
   - `AIAStrat_TYPE_hash` (es: `AIAStrat_TRN_fedcba`)
5. **Metodo** `generate_signal(df)` deve esistere

### Warnings (non bloccanti)

- `generate_signal` senza return statement
- `generate_signal` con < 3 statements
- Hardcoded timeframe ('5m', '15m', ecc.)

### Errori tipici

- `[X] "Syntax error at line 15: invalid syntax"`
- `[X] "Missing required import: Signal"`
- `[X] "No class inheriting from StrategyCore found"`
- `[X] "Invalid class name format: bad_name"`

**FAIL → DELETE strategy**

---

## STEP 2: LOOKAHEAD AST DETECTION

**Timing**: <50ms

Static code analysis (AST parsing) per pattern che usano dati futuri.

### Pattern cercati

**Pattern 1: `rolling(center=True)`**
```python
[X] df['close'].rolling(20, center=True).mean()
[OK] df['close'].rolling(20).mean()
```

**Pattern 2: `shift(-N)` con valori negativi**
```python
[X] df['close'].shift(-5)    # 5 bar nel futuro
[OK] df['close'].shift(5)     # 5 bar nel passato
```

**Pattern 3: `expanding(center=True)`**
```python
[X] df['close'].expanding(center=True).max()
[OK] df['close'].expanding().max()
```

**Pattern 4: `iloc[i + offset]` con offset positivo**
```python
[X] df.iloc[i + 5]   # Potrebbe accedere al futuro in loop
[OK] df.iloc[i - 5]   # Look back
```

**FAIL → DELETE strategy**

---

## STEP 3: EXECUTION VALIDATION

**Timing**: 100-500ms

Runtime validation su dati sintetici (500 bar).

### Fasi

#### 3a. Module Loading
- Scrive codice in file temporaneo
- Carica come modulo Python (`importlib`)
- Verifica subclass di StrategyCore

#### 3b. Instantiation
- Crea istanza: `strategy = StrategyClass()`
- Se fallisce: TypeError, missing arguments, ecc.

#### 3c. Signal Generation Test
- **Two-phase approach**:
  1. `strategy.calculate_indicators(df)`
  2. `strategy.generate_signal(df_with_indicators)`
- Testa in **5 punti**: [50, 100, 200, 300, last_bar]
- Valida: `Signal` o `None`, direction in [long, short, close]

#### 3d. Edge Case Testing
- Dati di varie lunghezze: [0, 1, 5, 10, 50, 100, 500]
- Warning se eccezione (non blocking)

### Errori tipici

- `[X] "Failed to load strategy class from code"`
- `[X] "Failed to instantiate: TypeError: missing argument"`
- `[X] "generate_signal raised exception at bar 100: NameError"`
- `[X] "generate_signal returned str, expected Signal or None"`

### Warnings (non bloccanti)

- `[!] "Strategy generated 0 signals on test data"`
- `[!] "Strategy generated very few signals (2)"`

**FAIL → DELETE strategy**

---

## Note Importanti

- **Shuffle test** (lookahead empirico) è **POST-BACKTEST**, non qui
- **Deletion immediata** se qualsiasi step fallisce
- **Parallel execution**: ThreadPoolExecutor (4 workers)
- **Backpressure**: se VALIDATED queue > limit, validator rallenta
- **Nessun caching**: ogni strategia validata indipendentemente

---

## File Coinvolti

- `src/validator/syntax_validator.py` → SyntaxValidator
- `src/validator/lookahead_detector.py` → LookaheadDetector
- `src/validator/execution_validator.py` → ExecutionValidator
- `src/validator/main_continuous.py` → ValidatorProcess
