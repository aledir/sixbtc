 # Piano: Ristrutturazione Pipeline SixBTC

 Obiettivo

 Ristrutturare la pipeline per seguire il principio Single Responsibility e introdurre il pool ACTIVE con ri-backtest periodico e logica leaderboard.

 ---
 Stato Attuale vs Proposta

 OGGI

 GENERATED → VALIDATED → TESTED → SELECTED → LIVE → RETIRED
                           ↓
                     (si accumula, si blocca)

 Problemi:
 - CLASSIFIER fa 7 cose diverse (viola Single Responsibility)
 - Nessun ri-backtest delle strategie vecchie
 - Subaccount manager gira ogni 24h (troppo lento)
 - TESTED si intasa → patch archival poco elegante

 PROPOSTA

 GENERATED → VALIDATED → ACTIVE (pool max 300) → LIVE → RETIRED
                           ↑↓
                     ri-backtest ogni 3 giorni

 Benefici:
 - Ogni modulo fa UNA cosa
 - Pool ACTIVE auto-gestito (leaderboard)
 - Ri-backtest mantiene score freschi
 - Deployment reattivo (ogni 15-30 min)

 ---
 Pool ACTIVE: Logica Leaderboard

 Regole di ingresso:

 Nuova strategia con score = X

 1. Se score < 15 → RETIRED (non entra mai)
 2. Se pool non pieno (< 300) e score ≥ 15 → ENTRA
 3. Se pool pieno (= 300):
    - Se X > min(pool) → espelli peggiore, ENTRA
    - Se X ≤ min(pool) → RETIRED (non entra)

 Configurazione:

 active_pool:
   max_size: 300              # Dimensione massima pool
   min_score_entry: 15        # Score minimo per entrare

 ---
 Soglie Score Unificate

 | Contesto        | Soglia              | Azione                   |
 |-----------------|---------------------|--------------------------|
 | Ingresso ACTIVE | score ≥ 15          | Può entrare nel pool     |
 | Selezione LIVE  | score ≥ 50 + top 10 | Candidato per deployment |
 | Retirement LIVE | score < 30          | Esce da LIVE → RETIRED   |

 ---
 Cambiamenti di Stato DB

 | Vecchio   | Nuovo     | Note                         |
 |-----------|-----------|------------------------------|
 | GENERATED | GENERATED | invariato                    |
 | VALIDATED | VALIDATED | invariato                    |
 | TESTED    | ACTIVE    | rinominato, pool con max 300 |
 | SELECTED  | rimosso   | non serve più                |
 | LIVE      | LIVE      | invariato                    |
 | RETIRED   | RETIRED   | invariato                    |

 ---
 Nuova Architettura Moduli

 1. SCORER (nuovo modulo)

 Responsabilità UNICA: Calcolare score da metriche

 src/scorer/
 ├── __init__.py
 ├── main_continuous.py      # Processo continuo
 ├── backtest_scorer.py      # Score da backtest (esiste già, spostare)
 └── live_scorer.py          # Score da trade live (esiste già, spostare)

 Flusso:
 - Dopo backtest → SCORER calcola score → salva in Strategy.score_backtest
 - Periodicamente → SCORER ricalcola score per strategie LIVE → salva in Strategy.score_live

 2. BACKTESTER (modificare)

 Responsabilità UNICA: Eseguire backtest

 Modifiche:
 - Aggiungere logica ri-backtest per ACTIVE vecchie
 - Nuovo campo: Strategy.last_backtested_at
 - Config: backtester.retest_interval_days: 3
 - Thread elastico: 4+1

 Thread elastico (5 totali):
 Thread 1-4: Solo VALIDATED (nuove strategie)
 Thread 5:   Prima ri-backtest ACTIVE, se vuoto → aiuta VALIDATED

 Definizione RI-BACKTEST:

 | Aspetto       | Backtest iniziale | Ri-backtest           |
 |---------------|-------------------|-----------------------|
 | Timeframe     | Tutti 6 TF        | Solo TF ottimale      |
 | Training      | 365 giorni        | 365 giorni            |
 | Holdout       | 30 giorni         | 30 giorni             |
 | Coins         | 30                | 30                    |
 | Parametric    | Sì (300 combo)    | No (stessi parametri) |
 | Tempo stimato | ~5 min            | ~1 min                |

 Dopo ri-backtest:
 1. Calcola nuovo score
 2. Aggiorna last_backtested_at = now
 3. Se nuovo score < 15 → RETIRED immediato
 4. Se nuovo score < min(pool) e pool pieno → RETIRED
 5. Altrimenti resta in ACTIVE con score aggiornato

 3. ROTATOR (nuovo modulo, sostituisce classifier + subaccount)

 Responsabilità UNICA: Ruotare strategie da ACTIVE a LIVE

 src/rotator/
 ├── __init__.py
 ├── main_continuous.py      # Processo continuo (ogni 15-30 min)
 ├── selector.py             # Logica selezione top N (da PortfolioBuilder)
 └── deployer.py             # Logica deployment a subaccount

 Flusso:
 - Ogni 15-30 min controlla:
   - Posti liberi in LIVE?
   - Strategie in ACTIVE con score alto?
   - Se sì → deploya

 4. MONITOR (nuovo modulo)

 Responsabilità UNICA: Monitorare LIVE e decidere retirement

 src/monitor/
 ├── __init__.py
 ├── main_continuous.py      # Processo continuo (ogni 15-30 min)
 ├── performance_tracker.py  # Calcola metriche live
 └── retirement_policy.py    # Decide chi ritirare

 Flusso:
 - Ogni 15-30 min:
   - Aggiorna metriche live per ogni LIVE strategy
   - Controlla criteri retirement (score < 30, degradation > 50%, drawdown > 30%)
   - Se triggered → LIVE → RETIRED

 5. CLASSIFIER (rimuovere)

 Il modulo classifier viene eliminato. Le sue responsabilità sono distribuite:

 | Responsabilità  | Va in                             |
 |-----------------|-----------------------------------|
 | Scoring         | SCORER                            |
 | Selection       | ROTATOR                           |
 | Deployment      | ROTATOR                           |
 | Live monitoring | MONITOR                           |
 | Retirement      | MONITOR                           |
 | Archival        | rimosso (ri-backtest lo gestisce) |

 ---
 File da Modificare/Creare

 Database

 - src/database/models.py - Rinominare stato TESTED → ACTIVE, rimuovere SELECTED, aggiungere last_backtested_at
 - alembic/versions/xxx_rename_tested_to_active.py - Migration

 Nuovi Moduli

 - src/scorer/ - Nuovo modulo (spostare da classifier)
 - src/rotator/ - Nuovo modulo (nuovo codice)
 - src/monitor/ - Estendere modulo esistente

 Modifiche

 - src/backtester/main_continuous.py - Aggiungere ri-backtest logic
 - src/backtester/strategy_selector.py - Nuovo file per selezione strategie da testare/ri-testare
 - config/config.yaml - Nuovi parametri
 - config/supervisor.conf - Nuovi processi, rimuovere classifier

 Rimozioni

 - src/classifier/ - Rimuovere intero modulo
 - src/subaccount/ - Sostituito da ROTATOR

 ---
 Config Proposta

 # Pool ACTIVE (nuovo)
 active_pool:
   max_size: 300                  # Max strategie nel pool
   min_score_entry: 15            # Score minimo per entrare

 # Backtester
 backtester:
   retest_interval_days: 3        # Ri-testa ACTIVE ogni 3 giorni
   threads:
     validated: 4                 # Thread dedicati a nuove strategie
     retest: 1                    # Thread elastico (ri-backtest, poi VALIDATED)

 # Rotator (nuovo)
 rotator:
   check_interval_minutes: 15     # Controlla ogni 15 min
   max_live_strategies: 10        # Max strategie in LIVE
   min_score_live: 50             # Score minimo per andare LIVE
   selection:
     max_per_type: 3              # Max per tipo (MOM, REV, etc.)
     max_per_timeframe: 3         # Max per timeframe

 # Monitor
 monitor:
   check_interval_minutes: 15     # Controlla ogni 15 min
   retirement:
     min_score: 30                # Score < 30 → retire
     max_degradation: 0.50        # 50% peggio di backtest → retire
     max_drawdown: 0.30           # 30% drawdown → retire
     min_trades: 10               # Min trade prima di valutare

 # Pipeline (aggiornato)
 pipeline:
   queue_limits:
     generated: 500
     validated: 50
     # active non ha più queue_limit, usa active_pool.max_size

 ---
 Flusso Completo Proposto

 1. GENERATOR genera strategia
    └→ status = GENERATED

 2. VALIDATOR valida (syntax, lookahead, shuffle)
    └→ status = VALIDATED

 3. BACKTESTER testa su tutti i TF
    └→ SCORER calcola score
    └→ status = ACTIVE, score_backtest = X, last_backtested_at = now

 4. [Ogni 3 giorni] BACKTESTER ri-testa ACTIVE vecchie
    └→ SCORER ricalcola score
    └→ Se score < threshold → status = RETIRED
    └→ Altrimenti → last_backtested_at = now

 5. [Ogni 15 min] ROTATOR controlla
    └→ Posti liberi in LIVE? Prende top da ACTIVE
    └→ status = LIVE

 6. EXECUTOR esegue trade per LIVE strategies

 7. [Ogni 15 min] MONITOR controlla LIVE
    └→ Aggiorna score_live
    └→ Se underperforming → status = RETIRED
    └→ ROTATOR riempie il posto libero

 ---
 Ordine di Implementazione

 Fase 1: Preparazione DB

 1. Creare migration per rinominare TESTED → ACTIVE
 2. Rimuovere stato SELECTED
 3. Aggiungere campo last_backtested_at

 Fase 2: SCORER

 1. Creare modulo src/scorer/
 2. Spostare scorer.py e live_scorer.py da classifier
 3. Creare main_continuous.py per SCORER
 4. Aggiungere a supervisor

 Fase 3: BACKTESTER ri-backtest

 1. Modificare main_continuous.py per gestire ri-backtest
 2. Aggiungere logica priorità (VALIDATED prima, poi ACTIVE vecchie)
 3. Aggiungere config retest_interval_days

 Fase 4: ROTATOR

 1. Creare modulo src/rotator/
 2. Implementare selector.py (da PortfolioBuilder)
 3. Implementare deployer.py (da subaccount manager)
 4. Creare main_continuous.py
 5. Aggiungere a supervisor

 Fase 5: MONITOR

 1. Estendere src/monitor/ esistente
 2. Aggiungere performance_tracker.py
 3. Aggiungere retirement_policy.py
 4. Modificare main_continuous.py

 Fase 6: Cleanup

 1. Rimuovere src/classifier/
 2. Rimuovere src/subaccount/
 3. Aggiornare supervisor.conf
 4. Rimuovere patch archival aggiunta oggi
 5. Test end-to-end

 ---
 Rischi e Mitigazioni

 | Rischio                        | Mitigazione                                             |
 |--------------------------------|---------------------------------------------------------|
 | Migration DB fallisce          | Backup prima, test su staging                           |
 | Processi non si sincronizzano  | Usare stesso pattern atomico (FOR UPDATE SKIP LOCKED)   |
 | ACTIVE troppo grande           | Ri-backtest riduce naturalmente (score scende → retire) |
 | Perdita dati durante migration | TESTED → ACTIVE è solo rename, nessun dato perso        |

 ---
 Stima Effort

 | Fase            | Complessità | File coinvolti     |
 |-----------------|-------------|--------------------|
 | 1. DB Migration | Bassa       | 2 file             |
 | 2. SCORER       | Media       | 4 file nuovi       |
 | 3. BACKTESTER   | Media       | 2 file modificati  |
 | 4. ROTATOR      | Alta        | 4 file nuovi       |
 | 5. MONITOR      | Media       | 3 file modificati  |
 | 6. Cleanup      | Bassa       | Rimozioni + config |

 ---
 Decisioni Confermate

 1. Stato ACTIVE: Rinominato da TESTED, pool con max 300 strategie
 2. Stato SELECTED: Rimosso - flusso semplificato ACTIVE → LIVE diretto
 3. Logica pool: Leaderboard - solo le top 300 per score restano
 4. Soglia ingresso ACTIVE: Score ≥ 15
 5. Soglia selezione LIVE: Score ≥ 50 (top 10)
 6. Soglia retirement LIVE: Score < 30
 7. Priorità ri-backtest: FIFO (più vecchie prima)
 8. Thread allocation: 4 thread VALIDATED + 1 thread elastico (ri-backtest, poi VALIDATED)
 9. Ri-backtest definition: Solo TF ottimale, 365+30 giorni, stessi parametri (no parametric)
 10. Frequenza ri-backtest: Ogni 3 giorni
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
