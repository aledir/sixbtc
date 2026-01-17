# Schema Database

Definizioni complete tabelle.

---

## strategies

Tabella principale strategie.

| Colonna | Tipo | Descrizione |
|--------|------|-------------|
| id | UUID | Primary key |
| name | VARCHAR | Nome classe strategia |
| code | TEXT | Codice sorgente Python |
| status | ENUM | GENERATED, VALIDATED, ACTIVE, LIVE, RETIRED, FAILED |
| generation_mode | VARCHAR | Sorgente (pattern, unger, ai_free, etc.) |
| base_code_hash | VARCHAR | Hash per cache shuffle |
| metrics | JSONB | Metriche performance |
| created_at | TIMESTAMP | Data creazione |
| updated_at | TIMESTAMP | Ultimo aggiornamento |

---

## backtests

Risultati backtest.

| Colonna | Tipo | Descrizione |
|--------|------|-------------|
| id | UUID | Primary key |
| strategy_id | UUID | FK a strategies |
| test_type | ENUM | IS, OOS, SHUFFLE |
| sharpe | FLOAT | Sharpe ratio |
| winrate | FLOAT | Win rate |
| max_dd | FLOAT | Max drawdown |
| trade_count | INT | Numero trade |
| start_date | DATE | Inizio test |
| end_date | DATE | Fine test |
| created_at | TIMESTAMP | Data esecuzione |

---

## trades

Storico trade.

| Colonna | Tipo | Descrizione |
|--------|------|-------------|
| id | UUID | Primary key |
| strategy_id | UUID | FK a strategies |
| subaccount_id | VARCHAR | Subaccount Hyperliquid |
| symbol | VARCHAR | Coppia trading |
| side | ENUM | LONG, SHORT |
| entry_price | DECIMAL | Prezzo entrata |
| exit_price | DECIMAL | Prezzo uscita |
| quantity | DECIMAL | Size posizione |
| pnl | DECIMAL | P&L realizzato |
| pnl_pct | DECIMAL | P&L percentuale |
| entry_time | TIMESTAMP | Ora entrata |
| exit_time | TIMESTAMP | Ora uscita |
| exit_reason | VARCHAR | TP, SL, SIGNAL, MANUAL |

---

## positions

Posizioni aperte correnti.

| Colonna | Tipo | Descrizione |
|--------|------|-------------|
| id | UUID | Primary key |
| strategy_id | UUID | FK a strategies |
| subaccount_id | VARCHAR | Subaccount Hyperliquid |
| symbol | VARCHAR | Coppia trading |
| side | ENUM | LONG, SHORT |
| entry_price | DECIMAL | Prezzo entrata |
| quantity | DECIMAL | Size posizione |
| stop_loss | DECIMAL | Prezzo stop loss |
| take_profit | DECIMAL | Prezzo take profit |
| unrealized_pnl | DECIMAL | P&L non realizzato |
| status | ENUM | PENDING, OPEN, CLOSING |
| opened_at | TIMESTAMP | Ora apertura |

---

## subaccounts

Subaccount Hyperliquid.

| Colonna | Tipo | Descrizione |
|--------|------|-------------|
| id | VARCHAR | Indirizzo subaccount (PK) |
| name | VARCHAR | Nome display |
| allocated_balance | DECIMAL | Capitale allocato |
| current_equity | DECIMAL | Equity corrente |
| strategy_id | UUID | FK a strategies (se LIVE) |
| status | ENUM | AVAILABLE, ALLOCATED, PAUSED |
| created_at | TIMESTAMP | Data creazione |

---

## emergency_stops

Record emergency stop.

| Colonna | Tipo | Descrizione |
|--------|------|-------------|
| id | UUID | Primary key |
| scope | ENUM | PORTFOLIO, SUBACCOUNT, STRATEGY |
| scope_id | VARCHAR | ID entita' interessata |
| stop_reason | TEXT | Motivo stop |
| triggered_at | TIMESTAMP | Quando triggerato |
| resolved_at | TIMESTAMP | Quando risolto |
