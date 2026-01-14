# 7. Shuffle Test

**Obiettivo**: Rilevare lookahead bias NON catturato dall'AST analysis tramite test empirico sui dati shuffled.

**Input**:
- strategy: model con code e base_code_hash
- score >= 40 (threshold passato)

**Output**: PASS/FAIL → se PASS, procede a WFA FIXED PARAMS

---

## Logica Shuffle Test

1. Carica 30 giorni di BTC data (timeframe della strategia)
2. Genera segnali su dati **ORIGINALI**
3. **SHUFFLE** le righe del DataFrame (rompe correlazioni temporali)
4. Genera segnali su dati **SHUFFLED**
5. Confronta: se segnali **IDENTICI** → **LOOKAHEAD BIAS**

### Perché funziona

- **Strategia legittima**: segnali dipendono da SEQUENZA temporale
- Shuffle rompe sequenza → segnali **DIVERSI**
- Se segnali uguali: sta guardando valori "assoluti", non sequenza (es: `df['future_price'] > df['close']`)

---

## Caching (by base_code_hash)

- Lookahead è proprietà del **BASE CODE**, non dei parametri
- Se base code passa → tutte le strategie parametriche passano
- Cache in `ValidationCache` table
- Cache HIT: ~0ms, Cache MISS: ~50-100ms

### Lookup

`ValidationCache.get(base_code_hash, 'shuffle_test')`

| Risultato | Azione |
|-----------|--------|
| EXISTS + passed=True | Skip test, return PASS |
| EXISTS + passed=False | Skip test, return FAIL |
| NOT EXISTS | Esegui test, salva risultato |

---

## Output

| Risultato | Azione |
|-----------|--------|
| **PASS** | Procede a **WFA FIXED PARAMS** |
| **FAIL** | return (False, "shuffle_test_failed"), status = **RETIRED** (non DELETE, code riusabile) |

---

## File Coinvolti

- `src/backtester/main_continuous.py` → `_promote_to_active_pool()`
- `src/validator/lookahead_test.py` → `LookaheadTester.validate()`
