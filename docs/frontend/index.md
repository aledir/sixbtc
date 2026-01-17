# Frontend

Principi design dashboard React.

---

## Obiettivo

Rispondere a "Sto facendo soldi?" - l'utente NON dovrebbe mai dover aprire Hyperliquid.

---

## Gerarchia Pagine

1. **Overview** - P&L, equity curve, stato sistema
2. **Trading** - Subaccount, posizioni, storico trade
3. **Strategies** - Ranking, dettagli
4. **Pipeline** - Funnel 10 step, qualita' backtest
5. **System** - Log, task, impostazioni

---

## Stack Tecnologico

| Componente | Tecnologia |
|-----------|------------|
| Framework | React 19 |
| Build | Vite 7 |
| Styling | TailwindCSS 4 |
| Charts | Recharts |
| Data | React Query |
| Routing | React Router 7 |

---

## Principi Design

### Mobile-First

- Tab bar bottom su mobile
- Sidebar su desktop
- Breakpoint responsive

### Data-Driven

- Tutti i dati da API
- React Query per caching
- Update real-time via polling

### Minimale

- Niente feature non necessarie
- Focus su cio' che conta (P&L)
- UI pulita e leggibile

---

## Componenti Chiave

| Componente | Scopo |
|-----------|---------|
| `Layout.tsx` | Shell app, navigazione |
| `Overview.tsx` | Riepilogo P&L |
| `Trading.tsx` | Posizioni, trade |
| `Strategies.tsx` | Lista strategie |
| `Pipeline.tsx` | Metriche funnel |
| `System.tsx` | Log, config |

---

## Styling

Variabili CSS per theming:

```css
:root {
  --color-profit: #4caf50;
  --color-loss: #f44336;
  --color-accent: #2196f3;
}
```

Toggle dark/light mode nell'header.

---

## Sviluppo

```bash
cd web
npm run dev    # Avvia dev server
npm run build  # Build produzione
```
