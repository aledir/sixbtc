# Decision Trees

Guide passo-passo per risolvere problemi comuni.

---

## Poche Strategie Passano il Backtest

```
PROBLEMA: Tasso di successo backtest molto basso
│
├─ Controlla min_sharpe
│   └─ Se > 0.5 → abbassa a 0.3
│
├─ Controlla min_trades (per il tuo TF)
│   ├─ 15m: se > 120 → abbassa a 100
│   ├─ 30m: se > 80 → abbassa a 60
│   └─ 1h:  se > 50 → abbassa a 40
│
├─ Controlla robustness_threshold
│   └─ Se > 0.85 → abbassa a 0.80
│
├─ Controlla max_degradation
│   └─ Se < 0.40 → alza a 0.50
│
└─ Se ancora niente → il problema e' la qualita' del generator
    └─ Controlla logs/generator.log per errori
```

**Config da modificare**: `backtesting.thresholds.*` e `backtesting.robustness.*`

---

## Strategie Buone in Backtest ma Perdono nel Live

```
PROBLEMA: Performance live << backtest
│
├─ Controlla OOS degradation delle strategie LIVE
│   curl localhost:8080/api/strategies?status=LIVE
│   └─ Se degradation media > 40% → stringe max_degradation a 0.35
│
├─ Controlla shuffle test abilitato
│   └─ shuffle.enabled deve essere true in config
│
├─ Controlla se funding rates sono nel backtest
│   └─ funding.enabled deve essere true
│
├─ Controlla slippage reale vs stimato
│   └─ Se slippage reale > 0.05% → aumenta hyperliquid.slippage
│
└─ Se ancora niente → problema regime di mercato
    └─ Il mercato e' cambiato. Le strategie storiche non funzionano.
    └─ Attendi che il pool si rinnovi con strategie piu' recenti.
```

---

## Pool ACTIVE Vuoto o Troppo Piccolo

```
PROBLEMA: pool ACTIVE < 30 strategie
│
├─ Controlla generator sta girando
│   supervisorctl status sixbtc:generator
│   └─ Se non RUNNING → supervisorctl restart sixbtc:generator
│
├─ Controlla backpressure
│   curl localhost:8080/api/pipeline/status
│   └─ Se queue VALIDATED > 50 → generator e' in pausa (normale)
│   └─ Se queue GENERATED > 80 → validator lento, controlla logs
│
├─ Controlla threshold troppo stretti
│   └─ Vedi sezione "Poche strategie passano il backtest"
│
└─ Controlla backtester sta girando
    supervisorctl status sixbtc:backtester
    └─ Se non RUNNING → supervisorctl restart sixbtc:backtester
```

---

## Nessuna Strategia LIVE

```
PROBLEMA: 0 strategie LIVE nonostante pool ACTIVE
│
├─ Controlla pool size >= min_pool_size (30)
│   curl localhost:8080/api/strategies?status=ACTIVE
│   └─ Se < 30 → aspetta che pool cresca
│
├─ Controlla rotator sta girando
│   supervisorctl status sixbtc:rotator
│   └─ Se non RUNNING → supervisorctl restart sixbtc:rotator
│
├─ Controlla subaccount hanno fondi
│   └─ Verifica su Hyperliquid che ogni subaccount abbia >= min_tradeable_usd
│
├─ Controlla dry_run
│   └─ Se true → le strategie entrano in LIVE ma non tradano
│
└─ Controlla emergency stops
    curl localhost:8080/api/risk/status
    └─ Se emergency stop attivo → aspetta cooldown o reset manuale
```

---

## Ordini Non Eseguiti

```
PROBLEMA: Segnali generati ma nessun ordine su exchange
│
├─ Controlla dry_run = true
│   └─ Se true → gli ordini vengono loggati, non inviati (comportamento corretto)
│
├─ Controlla executor sta girando
│   supervisorctl status sixbtc:executor
│   └─ Se non RUNNING → supervisorctl restart sixbtc:executor
│
├─ Controlla WebSocket connesso
│   cat logs/executor.log | grep -i "websocket\|connected"
│   └─ Se disconnesso → controlla internet, Hyperliquid status
│
├─ Controlla margine disponibile
│   └─ Se margin < margin_needed → ordine skippato (controlla log)
│
└─ Controlla min_notional
    └─ Se notional < 10 USDC → ordine skippato
```

---

## Emergency Stop Scattato

```
PROBLEMA: Trading bloccato da emergency stop
│
├─ Identifica quale stop e' scattato
│   curl localhost:8080/api/risk/status
│   │
│   ├─ max_portfolio_drawdown (20%)
│   │   └─ GRAVE: perdita totale > 20%
│   │   └─ Azione: Aspetta 48h + rotation. Review strategie.
│   │
│   ├─ max_daily_loss (10%)
│   │   └─ Giornata molto negativa
│   │   └─ Azione: Reset automatico a mezzanotte UTC
│   │
│   └─ max_consecutive_losses (10)
│       └─ Strategia in serie negativa
│       └─ Azione: Aspetta 24h. Considera retirement manuale.
│
└─ DOPO il cooldown
    └─ Analizza cosa e' successo
    └─ Verifica se parametri risk sono adeguati
    └─ Riprendi con cautela
```

---

## Strategia Ritirata Inaspettatamente

```
PROBLEMA: Strategia passata da LIVE a RETIRED
│
├─ Controlla motivo retirement
│   curl localhost:8080/api/strategies/{uuid}
│   │
│   ├─ score < 35
│   │   └─ Performance live scadente
│   │   └─ Normale comportamento, la strategia non funzionava
│   │
│   ├─ drawdown > 25%
│   │   └─ Strategia ha perso troppo
│   │   └─ Normale, il sistema si e' protetto
│   │
│   ├─ consecutive_losses >= 10
│   │   └─ Serie negativa lunga
│   │   └─ Regime di mercato cambiato per questa strategia
│   │
│   └─ degradation > 40%
│       └─ Live molto peggio di backtest
│       └─ Possibile overfitting o cambio mercato
│
└─ Nessuna azione necessaria
    └─ Il rotator mettera' una nuova strategia ACTIVE al suo posto
```

---

## Subaccount Senza Fondi

```
PROBLEMA: Subaccount ha balance < min_operational_usd
│
├─ Controlla scheduler topup
│   └─ check_subaccount_funds gira ogni 24h alle 02:00 UTC
│   └─ Se urgente, trigger manuale via API
│
├─ Controlla master ha fondi
│   └─ Se master < master_reserve_usd (100) → no topup possibile
│   └─ Deposita fondi su master wallet
│
└─ Controlla topup_target
    └─ Se subaccount riceve topup ma e' ancora basso
    └─ Aumenta topup_target_usd in config
```

---

## Database Lento o Pieno

```
PROBLEMA: Query lente, errori disco
│
├─ Controlla spazio disco
│   df -h
│   └─ Se < 10% libero → pulisci logs, vacuum DB
│
├─ Controlla log size
│   du -sh logs/*
│   └─ Se troppo grandi → rotazione manuale o attendi scheduler
│
├─ Vacuum database
│   psql -d sixbtc -c "VACUUM ANALYZE;"
│   └─ Libera spazio da deleted rows
│
└─ Cleanup strategie vecchie
    └─ scheduler fa cleanup FAILED e RETIRED > 7 giorni
    └─ Se urgente, DELETE manuale (con cautela)
```

---

## Quick Reference: Cosa Toccare

| Problema | Config da modificare |
|----------|---------------------|
| Troppe strategie falliscono backtest | `backtesting.thresholds.*` |
| Serve piu' robustezza | `backtesting.robustness.min_threshold` |
| Pool cresce troppo lento | `pipeline.queue_limits.*`, threshold |
| Troppi retirement | `monitor.retirement.*` |
| Margine insufficiente | `hyperliquid.funds.*` |
| Troppo rischio | `risk.fixed_fractional.risk_per_trade_pct` |
| Emergency stop troppo sensibile | `risk.emergency.*` |

Dettagli completi: [Config Reference](../config/reference.md)
