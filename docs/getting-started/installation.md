# Installazione

Requisiti sistema e setup dipendenze.

---

## Requisiti Sistema

| Componente | Minimo | Raccomandato |
|-----------|---------|-------------|
| CPU | 4 core | 8+ core |
| RAM | 8 GB | 16+ GB |
| Storage | 50 GB SSD | 100+ GB SSD |
| Python | 3.11 | 3.13 |
| PostgreSQL | 14 | 16 |

---

## Dipendenze

```bash
# Pacchetti sistema (Debian/Ubuntu)
sudo apt update
sudo apt install -y python3.11 python3.11-venv postgresql nodejs npm supervisor

# Ambiente Python
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Pacchetti Node (frontend)
cd web && npm install
```

---

## Setup Database

```bash
# Crea database
sudo -u postgres createdb sixbtc
sudo -u postgres createuser bitwolf

# Assegna permessi
sudo -u postgres psql -c "GRANT ALL ON DATABASE sixbtc TO bitwolf;"

# Esegui migrazioni
alembic upgrade head
```

---

## Installazione Supervisor

```bash
# Copia config
sudo cp config/supervisor.conf /etc/supervisor/conf.d/sixbtc.conf

# Ricarica supervisor
sudo supervisorctl reread
sudo supervisorctl update
```

---

## Configurazione

Copia il config di esempio e modifica:

```bash
cp config/config.example.yaml config/config.yaml
```

Impostazioni richieste:

- `hyperliquid.wallet_address`
- `hyperliquid.private_key`
- `database.url`

Vedi [Configurazione](configuration.md) per tutte le opzioni.
