# Flusso Dati

Come i dati fluiscono nel sistema.

---

## Flusso Strategia

```mermaid
sequenceDiagram
    participant G as Generator
    participant V as Validator
    participant B as Backtester
    participant R as Rotator
    participant E as Executor
    participant DB as Database

    G->>DB: Insert strategia (GENERATED)
    V->>DB: Legge GENERATED
    V->>DB: Update a VALIDATED o FAILED
    B->>DB: Legge VALIDATED
    B->>DB: Update metriche, set ACTIVE o FAILED
    R->>DB: Legge ACTIVE
    R->>DB: Update a LIVE
    E->>DB: Legge LIVE
    E->>E: Esegue trade
```

---

## Flusso Dati di Mercato

```mermaid
sequenceDiagram
    participant HL as Hyperliquid
    participant WS as WebSocket
    participant E as Executor
    participant M as Monitor
    participant DB as Database

    HL->>WS: Update prezzi
    WS->>E: Dati candele
    E->>E: Genera segnali
    E->>HL: Piazza ordini (REST)
    HL->>WS: Eventi fill
    WS->>E: Update posizioni
    E->>DB: Registra trade
    M->>DB: Legge trade
    M->>M: Calcola P&L
```

---

## Sorgenti Dati

### Dati Prezzo

| Sorgente | Uso |
|--------|-------|
| Hyperliquid WebSocket | Candele live, fill, posizioni |
| Binance CCXT | Dati storici per backtesting |

### Generazione Strategia

| Sorgente | Dati |
|--------|------|
| Pattern Discovery API | Pattern rilevati |
| Cataloghi Unger | Indicatori regime |
| AI (Claude/GPT) | Codice generato |

---

## Panoramica Schema Database

```mermaid
erDiagram
    STRATEGY ||--o{ BACKTEST : has
    STRATEGY ||--o{ TRADE : generates
    SUBACCOUNT ||--o{ TRADE : contains
    SUBACCOUNT ||--o{ POSITION : holds

    STRATEGY {
        uuid id
        string status
        string code
        json metrics
    }

    BACKTEST {
        uuid id
        uuid strategy_id
        float sharpe
        float winrate
    }

    TRADE {
        uuid id
        uuid strategy_id
        string subaccount_id
        float pnl
    }
```

Vedi [Schema Database](../database/schema.md) per dettagli completi.

---

## Principi Chiave

### Hyperliquid e' Source of Truth

- Lo stato exchange e' canonico
- Il database e' solo audit trail
- In caso di conflitto, fidarsi dell'exchange

### WebSocket First

- Tutte le letture via WebSocket
- REST solo per azioni
- Rate limit: 1200 req/min (REST)

### No Lookahead

- I dati fluiscono solo avanti nel tempo
- Dati storici immutabili
- Segnali calcolati solo su dati passati
