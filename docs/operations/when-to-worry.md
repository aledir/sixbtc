# When to Worry

Guida per capire quando qualcosa e' normale e quando e' un problema.

---

## Segnali di Allarme

### Gravita' ALTA - Agisci Subito

| Segnale | Perche' e' grave | Cosa fare |
|---------|-----------------|-----------|
| Emergency stop scattato | Trading bloccato, possibili perdite significative | Controlla `/api/risk/status`, attendi cooldown, analizza causa |
| Executor crashato | Posizioni aperte senza gestione | `supervisorctl restart sixbtc:executor`, verifica posizioni su Hyperliquid |
| Database non raggiungibile | Tutto il sistema bloccato | `sudo systemctl status postgresql`, riavvia se necessario |
| WebSocket disconnesso > 5 min | Dati non aggiornati, ordini non eseguiti | Controlla internet, stato Hyperliquid, restart executor |
| Subaccount a zero | Strategia non puo' tradare | Verifica se c'e' stata liquidazione, deposita fondi |

### Gravita' MEDIA - Controlla Entro 24h

| Segnale | Perche' e' un problema | Cosa fare |
|---------|----------------------|-----------|
| Pool ACTIVE < 30 | Rotator non puo' mettere strategie LIVE | Vedi [Decision Trees](decision-trees.md#pool-active-vuoto) |
| Nessun trade da 24h | Sistema potrebbe essere bloccato | Controlla executor log, verifica segnali generati |
| Win rate pool < 40% | Strategie potrebbero non funzionare | Analizza metriche, considera stringere threshold |
| Queue GENERATED > 80 | Backpressure, validator/backtester lento | Controlla log, potrebbe essere solo carico |
| Errori ripetuti nei log | Qualcosa non funziona | Identifica pattern, cerca in troubleshooting |

### Gravita' BASSA - Monitora

| Segnale | E' normale? | Quando preoccuparsi |
|---------|------------|---------------------|
| Score medio pool in calo | Si', il mercato cambia | Se scende sotto 45 per settimane |
| Strategia ritirata | Si', e' il sistema che funziona | Se retiri > 50% delle LIVE in una settimana |
| Backtest failure rate alto | Dipende, puo' essere normale | Se > 95% falliscono per settimane |
| Topup frequenti | Dipende da performance | Se serve topup ogni giorno = perdite continue |

---

## Cosa e' NORMALE

Non preoccuparti se vedi:

| Situazione | Perche' e' normale |
|------------|-------------------|
| 80-90% strategie falliscono backtest | I filtri sono pensati per essere stretti |
| Strategia LIVE con score in calo | Il mercato cambia, la strategia si adatta |
| Giorni senza trade | Dipende dalle strategie, alcune tradano poco |
| Piccole perdite giornaliere | Fa parte del trading, importante e' il trend |
| Generator in pausa | Backpressure system funziona correttamente |
| Queue VALIDATED oscillante | Normale flusso della pipeline |
| Retirement dopo pochi giorni | Strategia non adatta al mercato attuale |

---

## Metriche Chiave e Range Normali

### Pool Health

| Metrica | Range Normale | Preoccupati se |
|---------|--------------|----------------|
| Pool ACTIVE size | 30-100 | < 20 o costantemente al max |
| Score medio pool | 45-65 | < 40 per > 1 settimana |
| LIVE count | 5-8 (subaccount) | 0 per > 24h |
| Daily retirement | 0-2 | > 4 consecutivamente |

### Performance

| Metrica | Range Normale | Preoccupati se |
|---------|--------------|----------------|
| Daily P&L | -5% a +5% | > -10% in un giorno |
| Weekly P&L | -10% a +15% | > -20% in una settimana |
| Win rate (7 giorni) | 40-60% | < 30% per > 1 settimana |
| Trade frequency | Dipende da TF | Zero trade per > 48h |

### Pipeline

| Metrica | Range Normale | Preoccupati se |
|---------|--------------|----------------|
| Queue GENERATED | 0-100 | Costantemente 0 o > 100 |
| Queue VALIDATED | 0-50 | Costantemente > 70 |
| Backtest success rate | 5-20% | < 1% per > 1 settimana |
| Generation rate | 10-50/ora | 0 per > 1 ora |

---

## Checklist Settimanale

```bash
# 1. Pool sano?
echo "Pool ACTIVE:"
curl -s localhost:8080/api/strategies?status=ACTIVE | jq '.count'

echo "Score medio:"
curl -s localhost:8080/api/pool/stats | jq '.avg_score'

# 2. Performance ultima settimana?
echo "P&L 7 giorni:"
curl -s localhost:8080/api/performance/summary?days=7 | jq '.total_pnl'

# 3. Emergency stops attivati?
echo "Emergency stops:"
curl -s localhost:8080/api/risk/history?days=7 | jq '.events'

# 4. Errori frequenti?
echo "Errori ultimi 7 giorni:"
grep -c "ERROR" logs/*.log
```

---

## Escalation Path

Se qualcosa va male:

1. **Prima**: Controlla [Troubleshooting](troubleshooting.md)
2. **Poi**: Segui [Decision Trees](decision-trees.md)
3. **Se urgente**: Ferma tutto con `supervisorctl stop sixbtc:*`
4. **Mai**: Modificare direttamente il database senza backup

---

## Red Flags Critiche

Se vedi QUALSIASI di questi, FERMA TUTTO e investiga:

- [ ] Portfolio drawdown > 15% in un giorno
- [ ] Tutte le strategie LIVE ritirate contemporaneamente
- [ ] Executor log pieno di "rejected" o "insufficient margin"
- [ ] WebSocket connection errors continui
- [ ] Database corruption errors
- [ ] Discrepanza tra posizioni DB e Hyperliquid

```bash
# Emergency stop manuale
supervisorctl stop sixbtc:executor
# Le posizioni rimangono su Hyperliquid - gestisci manualmente se necessario
```
