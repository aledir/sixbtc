# Frontend Development Principles

## REGOLA ZERO del Frontend

**Il frontend deve rispondere a UNA domanda: "Sto facendo soldi o no?"**

L'utente NON deve aprire Hyperliquid per nessun motivo. Il frontend deve mostrare TUTTO ciò che serve per monitorare e gestire il sistema di trading.

---

## Principi Fondamentali

### 1. Profit First - Sempre Visibile

```
┌─────────────────────────────────────────────────────────────────┐
│ L'INFORMAZIONE PIÙ IMPORTANTE È IL PROFITTO/PERDITA            │
│                                                                 │
│ In OGNI pagina deve essere chiaro:                              │
│ - Portfolio P&L totale (realized + unrealized)                  │
│ - Trend: sto guadagnando o perdendo?                           │
│ - Drawdown attuale vs max consentito                           │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Hyperliquid Replacement

Il frontend deve mostrare TUTTO ciò che Hyperliquid mostra:
- **Account Value**: Equity totale del portfolio
- **Positions**: Tutte le posizioni aperte con entry, size, P&L
- **Orders**: Ordini pendenti
- **Trade History**: Storico completo dei trade
- **Funding**: Funding rates se rilevanti
- **Balances**: Per ogni subaccount

### 3. Gerarchia delle Informazioni

**Livello 1 - Overview (colpo d'occhio)**
- P&L totale (il numero più grande nella pagina)
- Equity curve (capire il trend)
- Stato sistema (LIVE/DRY_RUN, HEALTHY/ISSUES)
- Posizioni aperte (quante, P&L unrealized)

**Livello 2 - Trading (dettaglio operativo)**
- Subaccounts con P&L individuale
- Posizioni per subaccount
- Trade history recente
- Metriche live (win rate, drawdown)

**Livello 3 - Pipeline (fabbrica strategie)**
- Funnel completo 10 step con conversion rates
- Backtest quality (IS/OOS pass rates, scores)
- Failure analysis (dove si perde efficienza)
- Pool quality e throughput

**Livello 4 - Strategie e Rankings**
- Classifica strategie per score
- Dettaglio singola strategia
- Codice e parametri

**Livello 5 - Sistema**
- Logs, Tasks, Settings

### 4. No Pagine Ridondanti

- Ogni pagina ha UNO scopo chiaro
- Se due pagine mostrano le stesse info → merge
- Se una pagina non aiuta a fare soldi → elimina

### 5. Performance

- Dati critici (P&L, positions) devono caricare in <1 secondo
- Usare WebSocket per real-time dove possibile
- Lazy load per dati storici/grafici pesanti
- Cache aggressiva per dati che cambiano poco

### 6. Mobile First ma Desktop Complete

- Mobile: KPIs essenziali, azioni rapide
- Desktop: Tutti i dettagli, grafici completi, tabelle

---

## Struttura Pagine

```
SIDEBAR MENU:
├── Overview        → P&L, Equity, Status sistema, Mini-pipeline
├── Trading         → Subaccounts, Positions, Trade History
├── Pipeline        → Funnel 10-step, Backtest quality, Failures
├── Strategies      → Lista strategie, Rankings, Dettagli
├── System          → Tasks, Logs, Settings (collassato)
```

---

## Metriche da Mostrare per Categoria

### P&L (sempre visibile)
- Total P&L (realized + unrealized)
- P&L % sul capitale deployato
- P&L 24h, 7d, 30d
- Max Drawdown attuale

### Pipeline Health
- Strategies generated/24h
- Conversion rate per stage
- Pass rate IS/OOS backtest
- Pool utilization (size/limit)
- Avg score pool

### Live Trading
- Strategies live
- Open positions count
- Win rate live
- Avg trade duration
- Slippage/execution quality
