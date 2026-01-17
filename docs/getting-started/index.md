# Getting Started

Setup e configurazione iniziale per SixBTC.

---

## Panoramica

| Guida | Descrizione |
|-------|-------------|
| [Installazione](installation.md) | Requisiti sistema, dipendenze, setup iniziale |
| [Quickstart](quickstart.md) | Sistema funzionante in 10 minuti |
| [Configurazione](configuration.md) | Impostazioni essenziali config.yaml |

---

## Prerequisiti

- Python 3.11+
- PostgreSQL 14+
- Node.js 18+ (per frontend)
- Account Hyperliquid con API keys

---

## Setup Rapido

```bash
# Clone e setup
cd /home/bitwolf/sixbtc
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copia e modifica config
cp config/config.example.yaml config/config.yaml
# Modifica config/config.yaml con le tue impostazioni

# Avvia tutti i servizi
supervisorctl start sixbtc:*
```

Vedi [Quickstart](quickstart.md) per i passi dettagliati.
