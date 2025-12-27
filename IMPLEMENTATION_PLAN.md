# Piano di Implementazione: Architettura Multi-Processo SixBTC

## Obiettivo
Trasformare SixBTC da single-process (AutoPilot) a multi-processo (Supervisor-managed) seguendo il pattern di fivebtc, con validazione completa delle strategie.

---

## Architettura Finale

```
                         SIXBTC SUPERVISOR ARCHITECTURE
═══════════════════════════════════════════════════════════════════════════════

  [group:sixbtc-pipeline]              [group:sixbtc-trading]
  ┌─────────────────────────────────┐  ┌─────────────────────────────┐
  │ sixbtc-generator    (pri: 100)  │  │ sixbtc-executor   (pri: 500)│
  │ sixbtc-validator    (pri: 200)  │  │ sixbtc-monitor    (pri: 999)│
  │ sixbtc-backtester   (pri: 300)  │  └─────────────────────────────┘
  │ sixbtc-classifier   (pri: 400)  │
  └─────────────────────────────────┘  [group:sixbtc-orchestration]
                                       ┌─────────────────────────────┐
  [eventlistener]                      │ sixbtc-scheduler  (pri: 999)│
  ┌─────────────────────────────────┐  │ sixbtc-subaccount (pri: 600)│
  │ sixbtc-crashmail                │  └─────────────────────────────┘
  └─────────────────────────────────┘
                    │
                    ▼
            ┌───────────────┐
            │  PostgreSQL   │  ← Coordinazione via status + processing_by
            └───────────────┘
```

---

## File da Creare

### 1. Process Entry Points (thin wrappers)
```
src/processes/
├── __init__.py
├── generator.py           # → ContinuousGeneratorProcess
├── validator.py           # → ContinuousValidatorProcess
├── backtester.py          # → ContinuousBacktesterProcess
├── classifier.py          # → ContinuousClassifierProcess
├── executor.py            # → ContinuousExecutorProcess
├── subaccount_manager.py  # → SubaccountManagerProcess
├── monitor.py             # → SystemMonitor
└── scheduler.py           # → SixBTCScheduler
```

### 2. Main Continuous Implementations
```
src/generator/main_continuous.py      # ~500 lines
src/validator/main_continuous.py      # ~400 lines (NUOVO)
src/backtester/main_continuous.py     # ~500 lines
src/classifier/main_continuous.py     # ~300 lines
src/executor/main_continuous.py       # ~600 lines
src/subaccount/main_continuous.py     # ~500 lines (NUOVO)
```

### 3. Validazione Completa
```
src/validator/                        # NUOVO MODULO
├── __init__.py
├── main_continuous.py                # Process loop
├── syntax_validator.py               # Fase 1: Python syntax
├── lookahead_detector.py             # Fase 2: AST + patterns
├── shuffle_test.py                   # Fase 3: Empirical test
└── execution_validator.py            # Fase 4: Runtime test
```

### 4. Supervisor Setup
```
setup/
├── configure_supervisor.sh           # Genera config dinamicamente
└── supervisor.conf.template          # Template opzionale
```

### 5. Database Lock/Coordination
```
src/database/
└── strategy_processor.py             # Claim/release pattern per processi
```

---

## Pattern Multithreading (come fivebtc)

Ogni processo CPU-intensive usa internamente `ThreadPoolExecutor` per parallelizzare il lavoro:

### Pattern Base (applicato a Generator, Validator, Backtester)

```python
class ContinuousProcess:
    def __init__(self):
        self.config = load_config()._raw_config
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # ThreadPoolExecutor per parallelismo interno
        self.parallel_threads = self.config['processes']['generator']['parallel_threads']
        self.executor = ThreadPoolExecutor(
            max_workers=self.parallel_threads,
            thread_name_prefix="Worker"
        )

        # Tracking futures attivi
        self.active_futures: Dict[Future, str] = {}  # future -> strategy_id

        # Daily limits
        self.daily_count = 0
        self.daily_limit = self.config['processes']['generator']['daily_limit']
        self.daily_count_lock = threading.Lock()
        self.last_reset_date = datetime.now().date()

        # Process tracking per cleanup
        self.active_processes: List[subprocess.Popen] = []
        self.processes_lock = threading.Lock()

    def _reset_daily_count_if_needed(self):
        """Reset contatore giornaliero a mezzanotte"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_count = 0
            self.last_reset_date = today

    def reserve_slot(self) -> bool:
        """
        Atomic slot reservation - MUST call BEFORE starting work.
        Previene overrun del daily limit.
        """
        with self.daily_count_lock:
            self._reset_daily_count_if_needed()
            if self.daily_count >= self.daily_limit:
                return False
            self.daily_count += 1
            return True

    def release_slot(self):
        """Release slot se il lavoro fallisce prima di completare"""
        with self.daily_count_lock:
            self.daily_count = max(0, self.daily_count - 1)

    async def run_continuous(self):
        """Main loop con ThreadPoolExecutor"""

        # 1. Initial population - avvia N workers
        for i in range(self.parallel_threads):
            if self.shutdown_event.is_set():
                break

            if not self.reserve_slot():
                logger.info("Daily limit reached")
                break

            future = self.executor.submit(self._do_work, slot_reserved=True)
            self.active_futures[future] = f"task_{i}"

        # 2. Main loop - mantiene N workers attivi
        while not self.shutdown_event.is_set() and not self.force_exit:

            # Se nessun task attivo e limit raggiunto, aspetta midnight
            if not self.active_futures:
                if not self.reserve_slot():
                    await self._wait_until_midnight()
                    continue
                else:
                    self.release_slot()  # Era solo un check

            # Wait for ANY task to complete
            if self.active_futures:
                try:
                    done_futures = []
                    for future in as_completed(self.active_futures.keys(), timeout=1):
                        done_futures.append(future)
                        break  # Process one at a time
                except TimeoutError:
                    await asyncio.sleep(0.1)
                    continue

                # Process completed futures
                for future in done_futures:
                    if future not in self.active_futures:
                        continue

                    task_id = self.active_futures.pop(future)

                    try:
                        success, result = future.result()
                        if success:
                            logger.info(f"Task {task_id} completed")
                        else:
                            logger.warning(f"Task {task_id} failed")
                    except Exception as e:
                        logger.error(f"Task {task_id} error: {e}")

                    # Start new task to replace completed one
                    if self.reserve_slot():
                        new_future = self.executor.submit(self._do_work, slot_reserved=True)
                        self.active_futures[new_future] = f"task_{len(self.active_futures)}"

            await asyncio.sleep(0.1)  # Prevent CPU spinning

    def _do_work(self, slot_reserved: bool = False) -> Tuple[bool, Any]:
        """
        Worker method - eseguito nel thread pool.
        DEVE essere thread-safe!
        """
        try:
            # ... actual work here ...
            return (True, result)
        except Exception as e:
            if slot_reserved:
                self.release_slot()
            return (False, str(e))

    def handle_shutdown(self, signum, frame):
        """Shutdown handler con cleanup immediato"""
        logger.info("Shutdown requested...")
        self.shutdown_event.set()
        self.force_exit = True

        # Cancel active futures
        for future in list(self.active_futures.keys()):
            future.cancel()

        # Kill tracked subprocesses
        with self.processes_lock:
            for proc in self.active_processes:
                try:
                    proc.terminate()
                    proc.wait(timeout=0.5)
                except:
                    proc.kill()

        # Shutdown executor (don't wait)
        if self.executor:
            self.executor.shutdown(wait=False)

        os._exit(0)

    def run(self):
        """Entry point"""
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        try:
            asyncio.run(self.run_continuous())
        except KeyboardInterrupt:
            pass
        finally:
            logger.info("Process terminated")
```

### Configurazione Threads per Processo

```yaml
# config/config.yaml
processes:
  generator:
    parallel_threads: 3      # 3 generazioni AI in parallelo
    daily_limit: 300         # Max 300 strategie/giorno

  validator:
    parallel_threads: 5      # 5 validazioni in parallelo
    # No daily limit (processa tutto pending)

  backtester:
    parallel_threads: 10     # 10 backtest in parallelo
    # No daily limit (processa tutto validated)

  classifier:
    parallel_threads: 1      # Single thread (batch operation)
    interval_hours: 1
```

### Database Pool Sizing

**IMPORTANTE**: Il pool DB deve supportare tutti i threads:

```
Total threads = generator(3) + validator(5) + backtester(10) + classifier(1)
              + executor(1) + subaccount(1) + monitor(1) + scheduler(1)
              = 23 threads

database.pool_size = 25      # Base connections
database.max_overflow = 25   # Extra durante picchi
# Total: 50 connections disponibili
```

### Thread Safety Notes

1. **Database sessions**: Ogni thread crea la propria session (NO shared sessions)
2. **Strategy claiming**: Usa `FOR UPDATE SKIP LOCKED` per evitare race conditions
3. **Daily count**: Protetto da `threading.Lock()`
4. **Futures dict**: Modificato solo nel main loop (single-threaded)
5. **Logging**: Thread-safe by default in Python logging

---

## Fasi di Implementazione

### FASE 1: Database Coordination Layer
**Files da creare/modificare:**
- `src/database/strategy_processor.py` (NUOVO)

**Funzionalità:**
```python
class StrategyProcessor:
    def claim_strategy(self, status: str, process_id: str) -> Optional[Strategy]:
        """
        Atomic claim di una strategia per processing.
        SELECT ... WHERE status = ? AND processing_by IS NULL
        FOR UPDATE SKIP LOCKED
        """

    def release_strategy(self, strategy_id: str, new_status: str):
        """Rilascia strategia dopo processing."""

    def mark_failed(self, strategy_id: str, error: str):
        """Marca strategia come fallita."""
```

**Modifica a `src/database/models.py`:**
- Aggiungere campo `processing_by: Optional[str]` a Strategy model
- Aggiungere campo `processing_started_at: Optional[datetime]`

---

### FASE 2: Validazione Completa
**Files da creare:**
- `src/validator/__init__.py`
- `src/validator/main_continuous.py`
- `src/validator/syntax_validator.py`
- `src/validator/lookahead_detector.py`
- `src/validator/shuffle_test.py`
- `src/validator/execution_validator.py`

**Pipeline di validazione:**
```
GENERATED → [Syntax] → [Lookahead AST] → [Shuffle Test] → [Execution] → VALIDATED
                ↓              ↓               ↓              ↓
             DELETE         DELETE          DELETE         DELETE
```

**Riutilizzo codice esistente:**
- `src/backtester/validator.py` contiene già `LookaheadValidator` con AST e shuffle test
- Spostare/refactorare in `src/validator/` con separazione più chiara

---

### FASE 3: Process Entry Points
**Pattern da seguire (da fivebtc):**

```python
#!/usr/bin/env python3
"""Process Entry Point - Thin wrapper"""

import os
import sys
import signal

# Path setup BEFORE imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Signal handlers BEFORE imports
_shutdown_requested = False

def _early_signal_handler(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    print(f"\nReceived signal {signum}, stopping...", flush=True)
    os._exit(0)

signal.signal(signal.SIGINT, _early_signal_handler)
signal.signal(signal.SIGTERM, _early_signal_handler)

if __name__ == "__main__":
    from src.generator.main_continuous import ContinuousGeneratorProcess
    process = ContinuousGeneratorProcess()
    process.run()
```

**Files da creare:**
- `src/processes/generator.py` (~40 lines)
- `src/processes/validator.py` (~40 lines)
- `src/processes/backtester.py` (~40 lines)
- `src/processes/classifier.py` (~40 lines)
- `src/processes/executor.py` (~40 lines)
- `src/processes/subaccount_manager.py` (~40 lines)
- `src/processes/monitor.py` (~200 lines - più logica)
- `src/processes/scheduler.py` (~100 lines)

---

### FASE 4: Main Continuous Implementations

#### 4.1 Generator (`src/generator/main_continuous.py`)
```python
class ContinuousGeneratorProcess:
    def __init__(self):
        self.config = load_config()._raw_config
        self.shutdown_event = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.daily_count = 0
        self.daily_limit = self.config['generation']['batch_size'] * 6  # ~300/day

    async def run_continuous(self):
        while not self.shutdown_event.is_set():
            if self.daily_count >= self.daily_limit:
                await self._wait_until_midnight()
                continue

            # Submit generation tasks to thread pool
            future = self.executor.submit(self._generate_one)
            # ... track futures, handle completion

    def _generate_one(self) -> Tuple[bool, str]:
        # Use StrategyBuilder to generate
        # Save to pending/ with status=GENERATED
        # Return (success, strategy_id)
```

#### 4.2 Validator (`src/validator/main_continuous.py`)
```python
class ContinuousValidatorProcess:
    def __init__(self):
        self.processor = StrategyProcessor()
        self.syntax_validator = SyntaxValidator()
        self.lookahead_detector = LookaheadDetector()
        self.shuffle_tester = ShuffleTester()
        self.execution_validator = ExecutionValidator()

    async def run_continuous(self):
        while not self.shutdown_event.is_set():
            # Claim strategy with status=GENERATED
            strategy = self.processor.claim_strategy('GENERATED', self.process_id)
            if not strategy:
                await asyncio.sleep(5)
                continue

            try:
                # Run 4-phase validation
                if not self.syntax_validator.validate(strategy.code):
                    self._delete_strategy(strategy)
                    continue

                if not self.lookahead_detector.validate(strategy.code):
                    self._delete_strategy(strategy)
                    continue

                if not self.shuffle_tester.validate(strategy.code):
                    self._delete_strategy(strategy)
                    continue

                if not self.execution_validator.validate(strategy.code):
                    self._delete_strategy(strategy)
                    continue

                # All passed!
                self.processor.release_strategy(strategy.id, 'VALIDATED')

            except Exception as e:
                self.processor.mark_failed(strategy.id, str(e))
```

#### 4.3 Backtester (`src/backtester/main_continuous.py`)
```python
class ContinuousBacktesterProcess:
    def __init__(self):
        self.processor = StrategyProcessor()
        self.engine = VectorBTEngine(self.config)
        self.data_loader = BacktestDataLoader()

    async def run_continuous(self):
        while not self.shutdown_event.is_set():
            strategy = self.processor.claim_strategy('VALIDATED', self.process_id)
            if not strategy:
                await asyncio.sleep(5)
                continue

            try:
                # Load data
                data = self.data_loader.load_single_symbol('BTC', '15m', 180)

                # Run backtest
                metrics = self.engine.run_backtest(strategy_instance, data)

                # Check thresholds
                if self._passes_thresholds(metrics):
                    self._save_metrics(strategy.id, metrics)
                    self.processor.release_strategy(strategy.id, 'TESTED')
                else:
                    self._delete_strategy(strategy)

            except Exception as e:
                self.processor.mark_failed(strategy.id, str(e))
```

#### 4.4 Classifier (`src/classifier/main_continuous.py`)
```python
class ContinuousClassifierProcess:
    def __init__(self):
        self.scorer = StrategyScorer(self.config)
        self.portfolio_builder = PortfolioBuilder(self.config)
        self.interval_hours = 1

    async def run_continuous(self):
        while not self.shutdown_event.is_set():
            # Run classification cycle
            tested_strategies = self._get_tested_strategies()

            if tested_strategies:
                ranked = self.scorer.rank_strategies(tested_strategies)
                selected = self.portfolio_builder.select_top_10(ranked)

                for s in selected:
                    self._update_status(s['id'], 'SELECTED')

            # Sleep until next cycle
            await asyncio.sleep(self.interval_hours * 3600)
```

#### 4.5 SubaccountManager (`src/subaccount/main_continuous.py`)
```python
class SubaccountManagerProcess:
    def __init__(self):
        self.client = HyperliquidClient(self.config, dry_run=True)
        self.rotation_interval_hours = 24

    async def run_continuous(self):
        while not self.shutdown_event.is_set():
            # 1. Evaluate live performance
            live_strategies = self._get_live_strategies()
            for s in live_strategies:
                degradation = self._calculate_degradation(s)
                if degradation > 0.50 or s['drawdown'] > 0.25:
                    await self._retire_strategy(s)

            # 2. Deploy replacements
            selected = self._get_selected_strategies()
            free_slots = self._get_free_subaccounts()

            for slot, strategy in zip(free_slots, selected):
                await self._deploy_to_subaccount(slot, strategy)

            # 3. Rebalance capital (if enabled)
            if self.config['risk']['rebalance_enabled']:
                await self._rebalance_capital()

            await asyncio.sleep(self.rotation_interval_hours * 3600)
```

#### 4.6 Executor (`src/executor/main_continuous.py`)
```python
class ContinuousExecutorProcess:
    def __init__(self):
        self.client = HyperliquidClient(self.config, dry_run=True)
        self.position_tracker = PositionTracker()
        self.risk_manager = RiskManager(self.config)

    async def run_continuous(self):
        # Connect to WebSocket for market data
        await self._connect_websocket()

        while not self.shutdown_event.is_set():
            # On each candle close
            for subaccount in self._get_active_subaccounts():
                strategy = self._load_strategy(subaccount.strategy_id)

                # Generate signal
                signal = strategy.generate_signal(self._get_ohlcv(subaccount.symbol))

                if signal:
                    # Calculate position size
                    size, sl, tp = self.risk_manager.calculate(signal, ...)

                    # Execute order
                    await self.client.place_order(...)

                    # Track position
                    self.position_tracker.add_position(...)
```

---

### FASE 5: Supervisor Setup Script

**File: `setup/configure_supervisor.sh`**

```bash
#!/bin/bash
# SixBTC Supervisor Configuration Generator

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment
if [ -f "$BASE_DIR/.env" ]; then
    source "$BASE_DIR/.env"
fi

# Detect user
SIXBTC_USER=$(stat -c '%U' "$BASE_DIR")
VENV_PATH="$BASE_DIR/.venv"
PYTHON_BIN="$VENV_PATH/bin/python"

# Validate
[ -d "$VENV_PATH" ] || { echo "Error: venv not found"; exit 1; }
[ -f "$PYTHON_BIN" ] || { echo "Error: Python not found"; exit 1; }

# Generate config
cat > "$BASE_DIR/supervisor/sixbtc.conf" <<EOF
; SixBTC Supervisor Configuration
; Generated: $(date)

; ============================================================================
; PIPELINE GROUP - Strategy lifecycle
; ============================================================================

[program:sixbtc-generator]
command=$PYTHON_BIN -u $BASE_DIR/src/processes/generator.py
directory=$BASE_DIR
user=$SIXBTC_USER
autostart=true
autorestart=unexpected
startsecs=5
stopwaitsecs=30
stopsignal=TERM
stdout_logfile=NONE
stderr_logfile=NONE
environment=PYTHONPATH="$BASE_DIR"
priority=100

[program:sixbtc-validator]
command=$PYTHON_BIN -u $BASE_DIR/src/processes/validator.py
directory=$BASE_DIR
user=$SIXBTC_USER
autostart=true
autorestart=unexpected
startsecs=5
stopwaitsecs=10
stopsignal=TERM
stdout_logfile=NONE
stderr_logfile=NONE
environment=PYTHONPATH="$BASE_DIR"
priority=200

[program:sixbtc-backtester]
command=$PYTHON_BIN -u $BASE_DIR/src/processes/backtester.py
directory=$BASE_DIR
user=$SIXBTC_USER
autostart=true
autorestart=unexpected
startsecs=5
stopwaitsecs=10
stopsignal=TERM
stdout_logfile=NONE
stderr_logfile=NONE
environment=PYTHONPATH="$BASE_DIR"
priority=300

[program:sixbtc-classifier]
command=$PYTHON_BIN -u $BASE_DIR/src/processes/classifier.py
directory=$BASE_DIR
user=$SIXBTC_USER
autostart=true
autorestart=unexpected
startsecs=5
stopwaitsecs=10
stopsignal=TERM
stdout_logfile=NONE
stderr_logfile=NONE
environment=PYTHONPATH="$BASE_DIR"
priority=400

; ============================================================================
; TRADING GROUP - Live execution
; ============================================================================

[program:sixbtc-executor]
command=$PYTHON_BIN -u $BASE_DIR/src/processes/executor.py
directory=$BASE_DIR
user=$SIXBTC_USER
autostart=true
autorestart=true
startsecs=5
stopwaitsecs=30
stopsignal=TERM
stdout_logfile=NONE
stderr_logfile=NONE
environment=PYTHONPATH="$BASE_DIR"
priority=500

[program:sixbtc-subaccount]
command=$PYTHON_BIN -u $BASE_DIR/src/processes/subaccount_manager.py
directory=$BASE_DIR
user=$SIXBTC_USER
autostart=true
autorestart=unexpected
startsecs=5
stopwaitsecs=30
stopsignal=TERM
stdout_logfile=NONE
stderr_logfile=NONE
environment=PYTHONPATH="$BASE_DIR"
priority=600

[program:sixbtc-monitor]
command=$PYTHON_BIN -u $BASE_DIR/src/processes/monitor.py
directory=$BASE_DIR
user=$SIXBTC_USER
autostart=true
autorestart=true
startsecs=2
startretries=999999
stopwaitsecs=5
stopsignal=TERM
stdout_logfile=NONE
stderr_logfile=NONE
environment=PYTHONPATH="$BASE_DIR"
priority=999

[program:sixbtc-scheduler]
command=$PYTHON_BIN -u $BASE_DIR/src/processes/scheduler.py
directory=$BASE_DIR
user=$SIXBTC_USER
autostart=true
autorestart=unexpected
startsecs=5
stopwaitsecs=10
stopsignal=TERM
stdout_logfile=NONE
stderr_logfile=NONE
environment=PYTHONPATH="$BASE_DIR"
priority=999

; ============================================================================
; GROUPS
; ============================================================================

[group:sixbtc-pipeline]
programs=sixbtc-generator,sixbtc-validator,sixbtc-backtester,sixbtc-classifier
priority=999

[group:sixbtc-trading]
programs=sixbtc-executor,sixbtc-subaccount,sixbtc-monitor
priority=998

[group:sixbtc-orchestration]
programs=sixbtc-scheduler
priority=997

; ============================================================================
; EVENT LISTENER - Crash notifications
; ============================================================================

[eventlistener:sixbtc-crashmail]
command=$PYTHON_BIN -u $BASE_DIR/src/monitor/crash_notifier.py
events=PROCESS_STATE
user=$SIXBTC_USER
buffer_size=10
autorestart=true
environment=PYTHONPATH="$BASE_DIR"

EOF

echo "Configuration generated: $BASE_DIR/supervisor/sixbtc.conf"
echo ""
echo "To install system-wide:"
echo "  sudo cp $BASE_DIR/supervisor/sixbtc.conf /etc/supervisor/conf.d/"
echo "  sudo supervisorctl reread"
echo "  sudo supervisorctl update"
```

---

### FASE 6: Config Updates

**Aggiornare `config/config.yaml`:**

```yaml
# Nuova sezione processes
processes:
  generator:
    enabled: true
    parallel_threads: 3
    daily_limit: 300

  validator:
    enabled: true
    parallel_threads: 5

  backtester:
    enabled: true
    parallel_threads: 10

  classifier:
    enabled: true
    interval_hours: 1

  executor:
    enabled: true
    dry_run: true  # IMPORTANTE: default sicuro

  subaccount_manager:
    enabled: true
    rotation_interval_hours: 24
    rebalance_enabled: true

  monitor:
    enabled: true
    check_interval_seconds: 30

  scheduler:
    enabled: true
```

---

## Ordine di Implementazione

| # | Task | Files | Effort | Dipendenze |
|---|------|-------|--------|------------|
| 1 | Database coordination | `strategy_processor.py`, models.py update | 2h | - |
| 2 | Validator module | `src/validator/*` (5 files) | 4h | #1 |
| 3 | Process entry points | `src/processes/*` (8 files) | 2h | - |
| 4 | Generator continuous | `main_continuous.py` | 3h | #1, #3 |
| 5 | Validator continuous | `main_continuous.py` | 3h | #1, #2, #3 |
| 6 | Backtester continuous | `main_continuous.py` | 3h | #1, #3 |
| 7 | Classifier continuous | `main_continuous.py` | 2h | #1, #3 |
| 8 | SubaccountManager continuous | `main_continuous.py` | 4h | #1, #3 |
| 9 | Executor continuous | `main_continuous.py` | 4h | #1, #3, #8 |
| 10 | Monitor process | `monitor.py` | 3h | #3 |
| 11 | Scheduler process | `scheduler.py` | 2h | #3 |
| 12 | Supervisor setup script | `configure_supervisor.sh` | 1h | - |
| 13 | Config updates | `config.yaml` | 1h | - |
| 14 | Tests | Unit + integration | 4h | All |

**Totale stimato: ~38 ore di sviluppo**

---

## Compatibilità con CLI Manuale

La CLI esistente (`main.py`) continua a funzionare per operazioni manuali:

```bash
# Operazioni manuali (bypassano supervisor)
python main.py generate --count 10
python main.py backtest --strategy Strategy_MOM_xxx
python main.py classify
python main.py deploy --dry-run
python main.py status

# Supervisor per produzione
sudo supervisorctl start sixbtc-pipeline:*
sudo supervisorctl start sixbtc-trading:*
```

---

## Decisioni Confermate

1. **EXECUTOR e SUBACCOUNT_MANAGER separati**: Crash isolation migliore. Executor fa solo trading signals, SubaccountManager gestisce deployment/rotation/rebalance.

2. **Dry-run segue config**: Legge `development.testing.dry_run` dal config.yaml. Più flessibile per ambienti diversi (dev vs prod).

3. **Crash notifier incluso**: Implementare event listener per crash notifications via email/log come in fivebtc.

---

## Note Importanti

1. **Graceful shutdown**: Tutti i processi rispettano SIGTERM con cleanup ordinato.

2. **Database pool**: Verificare che `pool_size + max_overflow >= total_threads` di tutti i processi.

3. **Logging**: Ogni processo scrive in `logs/sixbtc-{process}.log` con rotazione.

4. **Recovery**: Se un processo crasha, supervisor lo riavvia. La strategia in processing viene rilasciata dopo timeout.

---

## Files Aggiuntivi (crash_notifier)

```
src/monitor/
├── crash_notifier.py      # Event listener per supervisor
└── alert_manager.py       # Gestione centralizzata alerts (email, log)
```
