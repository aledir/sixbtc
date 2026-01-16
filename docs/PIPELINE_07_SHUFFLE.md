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

## Output

| Risultato | Azione |
|-----------|--------|
| **PASS** | Procede a **WFA FIXED PARAMS** |
| **FAIL** | return (False, "shuffle_test_failed"), status = **RETIRED** (non DELETE, code riusabile) |

---

## File Coinvolti

- `src/backtester/main_continuous.py` → `_promote_to_active_pool()`
- `src/validator/lookahead_test.py` → `LookaheadTester.validate()`
