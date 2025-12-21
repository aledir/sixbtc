# SixBTC - Piano di Test Completo

**Progetto**: AI-Powered Multi-Strategy Trading System  
**Obiettivo**: Testare TUTTI i componenti in modalità dry-run/mock PRIMA del deployment live  
**Regola d'oro**: MAI eseguire ordini reali durante i test

---

## 🎯 PRINCIPI DI TEST

1. **Dry-Run First**: Ogni componente che interagisce con exchange deve avere `dry_run=True`
2. **Mock External APIs**: Usare mock per Hyperliquid, Binance, AI providers
3. **Isolated Tests**: Ogni test deve essere indipendente
4. **Reproducible**: Usare seed fissi per random/AI generation
5. **Fast Feedback**: Unit test < 1s, Integration < 10s, E2E < 60s

---

## 📁 STRUTTURA TEST

```
tests/
├── unit/                      # Test unitari per singole funzioni
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_strategy_base.py
│   ├── test_scorer.py
│   └── test_risk_manager.py
│
├── integration/               # Test integrazione tra moduli
│   ├── test_data_pipeline.py
│   ├── test_backtest_pipeline.py
│   ├── test_strategy_generation.py
│   └── test_deployment_pipeline.py
│
├── e2e/                       # Test end-to-end (dry-run)
│   ├── test_full_cycle.py
│   └── test_orchestrator.py
│
├── mocks/                     # Mock objects
│   ├── mock_hyperliquid.py
│   ├── mock_binance.py
│   ├── mock_ai_provider.py
│   └── mock_websocket.py
│
├── fixtures/                  # Test data
│   ├── sample_ohlcv.parquet
│   ├── sample_strategies.json
│   └── sample_signals.json
│
└── conftest.py               # Pytest fixtures globali
```

---

## 🧪 FASE 1: FOUNDATION TESTS

### 1.1 Config Loader Tests (`tests/unit/test_config.py`)

```python
"""Test configuration loading and validation"""

class TestConfigLoader:
    
    def test_load_valid_config(self):
        """Carica config.yaml valido"""
        config = load_config('config/config.yaml')
        assert config is not None
        assert 'system' in config
        assert 'database' in config
        
    def test_env_variable_interpolation(self):
        """Verifica che ${VAR} venga sostituito"""
        os.environ['TEST_VAR'] = 'test_value'
        config = load_config('config/test_config.yaml')
        assert config['test_key'] == 'test_value'
        
    def test_missing_required_key_raises(self):
        """Config incompleto deve fallire fast"""
        with pytest.raises(ConfigValidationError):
            load_config('config/invalid_config.yaml')
            
    def test_default_values_applied(self):
        """Valori di default applicati se mancanti"""
        config = load_config('config/minimal_config.yaml')
        assert config['trading']['max_positions'] == 10  # default
```

### 1.2 Database Tests (`tests/unit/test_database.py`)

```python
"""Test database models and connections"""

class TestDatabaseModels:
    
    @pytest.fixture
    def db_session(self):
        """In-memory SQLite per test"""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        yield Session()
        
    def test_create_strategy(self, db_session):
        """Crea e recupera una strategia"""
        strategy = Strategy(
            name='Test_MOM_001',
            type='MOM',
            code='class Test(StrategyCore): pass',
            timeframe='15m',
            status='PENDING'
        )
        db_session.add(strategy)
        db_session.commit()
        
        result = db_session.query(Strategy).first()
        assert result.name == 'Test_MOM_001'
        
    def test_strategy_status_transitions(self, db_session):
        """Verifica transizioni di stato valide"""
        strategy = create_test_strategy(db_session)
        
        # PENDING -> TESTED
        strategy.status = 'TESTED'
        db_session.commit()
        assert strategy.status == 'TESTED'
        
        # TESTED -> SELECTED
        strategy.status = 'SELECTED'
        db_session.commit()
        assert strategy.status == 'SELECTED'
        
    def test_backtest_result_relationship(self, db_session):
        """Backtest results linked to strategy"""
        strategy = create_test_strategy(db_session)
        result = BacktestResult(
            strategy_id=strategy.id,
            sharpe_ratio=1.5,
            total_trades=100
        )
        db_session.add(result)
        db_session.commit()
        
        assert len(strategy.backtest_results) == 1
```

### 1.3 Logger Tests (`tests/unit/test_logger.py`)

```python
"""Test logging system"""

class TestLogger:
    
    def test_logger_creates_file(self, tmp_path):
        """Logger crea file di log"""
        log_file = tmp_path / 'test.log'
        logger = setup_logger(log_file=str(log_file))
        logger.info("Test message")
        
        assert log_file.exists()
        assert "Test message" in log_file.read_text()
        
    def test_log_rotation(self, tmp_path):
        """Log rotation a 10MB"""
        # Simula file grande e verifica rotation
        pass
```

---

## 🧪 FASE 2: DATA LAYER TESTS

### 2.1 Binance Downloader Tests (`tests/unit/test_binance_downloader.py`)

```python
"""Test Binance data downloader"""

class TestBinanceDownloader:
    
    @pytest.fixture
    def mock_ccxt(self, mocker):
        """Mock CCXT exchange"""
        mock = mocker.patch('ccxt.binance')
        mock.return_value.fetch_ohlcv.return_value = [
            [1704067200000, 42000, 42500, 41800, 42300, 1000],
            [1704067260000, 42300, 42600, 42200, 42500, 1200],
        ]
        return mock
    
    def test_download_ohlcv(self, mock_ccxt):
        """Download OHLCV per simbolo"""
        downloader = BinanceDataDownloader()
        df = downloader.download_ohlcv('BTC/USDT', '15m', days=1)
        
        assert len(df) > 0
        assert all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume'])
        
    def test_get_common_symbols(self, mock_ccxt):
        """Intersezione Binance-Hyperliquid"""
        downloader = BinanceDataDownloader()
        symbols = downloader.get_common_symbols()
        
        assert 'BTC' in symbols
        assert 'ETH' in symbols
        
    def test_incremental_download(self, mock_ccxt, tmp_path):
        """Download incrementale (solo candles mancanti)"""
        downloader = BinanceDataDownloader(cache_dir=tmp_path)
        
        # Prima download
        df1 = downloader.download_ohlcv('BTC/USDT', '15m', days=1)
        
        # Secondo download - dovrebbe usare cache
        df2 = downloader.download_ohlcv('BTC/USDT', '15m', days=1)
        
        # Verifica che non ha ri-scaricato tutto
        assert mock_ccxt.return_value.fetch_ohlcv.call_count < 10
```

### 2.2 Hyperliquid WebSocket Tests (`tests/unit/test_hyperliquid_websocket.py`)

```python
"""Test Hyperliquid WebSocket data provider"""

class TestHyperliquidDataProvider:
    
    @pytest.fixture
    def mock_websocket(self, mocker):
        """Mock WebSocket connection"""
        mock_ws = mocker.patch('websockets.connect')
        mock_ws.return_value.__aenter__.return_value.recv = AsyncMock(
            return_value=json.dumps({
                'channel': 'candle',
                'data': {
                    'coin': 'BTC',
                    'interval': '15m',
                    'open': '42000',
                    'high': '42500',
                    'low': '41800',
                    'close': '42300',
                    'volume': '1000',
                    'timestamp': 1704067200000
                }
            })
        )
        return mock_ws
    
    def test_singleton_pattern(self):
        """Solo UNA istanza del provider"""
        provider1 = HyperliquidDataProvider()
        provider2 = HyperliquidDataProvider()
        assert provider1 is provider2
        
    async def test_subscribe_candles(self, mock_websocket):
        """Subscribe a candle stream"""
        provider = HyperliquidDataProvider()
        await provider.start()
        await provider.subscribe(['BTC', 'ETH'], ['15m', '1h'])
        
        # Verifica subscriptions inviate
        assert mock_websocket.return_value.send.called
        
    async def test_get_candles_thread_safe(self, mock_websocket):
        """Accesso concorrente ai candles"""
        provider = HyperliquidDataProvider()
        await provider.start()
        
        # Simula accesso concorrente
        tasks = [
            provider.get_candles('BTC', '15m'),
            provider.get_candles('BTC', '15m'),
            provider.get_candles('BTC', '15m'),
        ]
        results = await asyncio.gather(*tasks)
        
        # Tutti devono avere gli stessi dati
        assert all(r == results[0] for r in results)
        
    async def test_auto_reconnect(self, mock_websocket, mocker):
        """Reconnect automatico su disconnessione"""
        provider = HyperliquidDataProvider()
        await provider.start()
        
        # Simula disconnessione
        mock_websocket.return_value.__aenter__.return_value.recv.side_effect = \
            websockets.exceptions.ConnectionClosed(None, None)
        
        # Aspetta reconnect
        await asyncio.sleep(2)
        
        # Verifica che ha tentato reconnect
        assert mock_websocket.call_count > 1
```

### 2.3 Data Pipeline Integration (`tests/integration/test_data_pipeline.py`)

```python
"""Integration test for data pipeline"""

class TestDataPipeline:
    
    async def test_binance_to_backtest_pipeline(self, tmp_path):
        """Dati Binance -> Backtest"""
        # 1. Download dati (mock)
        downloader = BinanceDataDownloader(cache_dir=tmp_path)
        df = downloader.download_ohlcv('BTC/USDT', '15m', days=30)
        
        # 2. Verifica formato per VectorBT
        assert df.index.name == 'timestamp'
        assert df.index.is_monotonic_increasing
        assert not df.isnull().any().any()
        
    async def test_websocket_to_strategy_pipeline(self, mock_websocket):
        """WebSocket -> Strategy signal generation"""
        provider = HyperliquidDataProvider()
        await provider.start()
        
        # Simula 100 candles
        for _ in range(100):
            await provider._process_message(sample_candle_message())
        
        # Get data per strategy
        df = await provider.get_candles_as_dataframe('BTC', '15m')
        
        # Verifica formato per StrategyCore
        assert len(df) >= 50  # Minimo per indicatori
        assert all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume'])
```

---

## 🧪 FASE 3: STRATEGY SYSTEM TESTS

### 3.1 StrategyCore Base Tests (`tests/unit/test_strategy_base.py`)

```python
"""Test StrategyCore base class"""

class TestStrategyCore:
    
    def test_abstract_class_not_instantiable(self):
        """StrategyCore è astratta"""
        with pytest.raises(TypeError):
            StrategyCore()
            
    def test_concrete_strategy_works(self):
        """Strategia concreta funziona"""
        class TestStrategy(StrategyCore):
            def generate_signal(self, df):
                if df['close'].iloc[-1] > df['close'].iloc[-2]:
                    return Signal('long', 0.1, 0.02, 0.04, 'test')
                return None
        
        strategy = TestStrategy()
        df = create_sample_ohlcv(100)
        signal = strategy.generate_signal(df)
        
        assert signal is None or isinstance(signal, Signal)
        
    def test_signal_dataclass(self):
        """Signal contiene tutti i campi"""
        signal = Signal(
            direction='long',
            size=0.1,
            stop_loss=0.02,
            take_profit=0.04,
            reason='Test signal'
        )
        
        assert signal.direction in ['long', 'short', 'close']
        assert 0 < signal.size <= 1
        assert signal.stop_loss > 0
        assert signal.take_profit > 0
```

### 3.2 AI Strategy Generator Tests (`tests/unit/test_strategy_generator.py`)

```python
"""Test AI strategy generation"""

class TestStrategyGenerator:
    
    @pytest.fixture
    def mock_ai_provider(self, mocker):
        """Mock AI provider response"""
        mock = mocker.patch.object(AIManager, 'generate')
        mock.return_value = '''
class Strategy_MOM_test123(StrategyCore):
    """Momentum strategy"""
    
    def generate_signal(self, df):
        if len(df) < 20:
            return None
        
        sma_fast = df['close'].rolling(10).mean().iloc[-1]
        sma_slow = df['close'].rolling(20).mean().iloc[-1]
        
        if sma_fast > sma_slow:
            return Signal('long', 0.1, 0.02, 0.04, 'SMA crossover')
        return None
'''
        return mock
    
    def test_generate_valid_strategy(self, mock_ai_provider):
        """Genera strategia valida"""
        generator = StrategyBuilder()
        code = generator.generate_strategy('MOM', '15m')
        
        # Verifica struttura
        assert 'class Strategy_' in code
        assert 'StrategyCore' in code
        assert 'generate_signal' in code
        
    def test_generated_strategy_executable(self, mock_ai_provider):
        """Strategia generata è eseguibile"""
        generator = StrategyBuilder()
        code = generator.generate_strategy('MOM', '15m')
        
        # Compila ed esegui
        strategy = compile_and_instantiate(code)
        df = create_sample_ohlcv(100)
        signal = strategy.generate_signal(df)
        
        assert signal is None or isinstance(signal, Signal)
        
    def test_ast_validation_catches_lookahead(self, mocker):
        """AST rileva lookahead bias"""
        bad_code = '''
class BadStrategy(StrategyCore):
    def generate_signal(self, df):
        future = df['close'].shift(-1)  # LOOKAHEAD!
        return None
'''
        generator = StrategyBuilder()
        is_valid, errors = generator._validate_structure(bad_code)
        
        assert not is_valid
        assert 'shift(-1)' in str(errors) or 'lookahead' in str(errors).lower()
        
    def test_ast_validation_catches_center_true(self):
        """AST rileva rolling(center=True)"""
        bad_code = '''
class BadStrategy(StrategyCore):
    def generate_signal(self, df):
        ma = df['close'].rolling(10, center=True).mean()  # LOOKAHEAD!
        return None
'''
        generator = StrategyBuilder()
        is_valid, errors = generator._validate_structure(bad_code)
        
        assert not is_valid
```

### 3.3 Strategy Generation Integration (`tests/integration/test_strategy_generation.py`)

```python
"""Integration test for strategy generation pipeline"""

class TestStrategyGenerationPipeline:
    
    def test_generate_and_backtest_cycle(self, mock_ai_provider, tmp_path):
        """Genera -> Valida -> Backtest"""
        # 1. Genera strategia
        generator = StrategyBuilder()
        code = generator.generate_strategy('MOM', '15m')
        
        # 2. Valida (AST + shuffle)
        validator = LookaheadValidator()
        validation = validator.validate(code, create_sample_ohlcv(1000))
        assert validation['ast_check_passed']
        
        # 3. Backtest
        strategy = compile_and_instantiate(code)
        backtester = VectorBTBacktester()
        results = backtester.backtest(strategy, create_sample_ohlcv(1000))
        
        assert 'sharpe_ratio' in results
        assert 'total_trades' in results
```

---

## 🧪 FASE 4: BACKTESTING ENGINE TESTS

### 4.1 VectorBT Wrapper Tests (`tests/unit/test_vectorbt_engine.py`)

```python
"""Test VectorBT backtesting engine"""

class TestVectorBTBacktester:
    
    @pytest.fixture
    def sample_strategy(self):
        """Simple test strategy"""
        class SimpleMA(StrategyCore):
            def generate_signal(self, df):
                if len(df) < 20:
                    return None
                if df['close'].iloc[-1] > df['close'].rolling(20).mean().iloc[-1]:
                    return Signal('long', 0.1, 0.02, 0.04, 'Above MA')
                return None
        return SimpleMA()
    
    def test_backtest_returns_metrics(self, sample_strategy):
        """Backtest ritorna metriche richieste"""
        backtester = VectorBTBacktester()
        data = create_sample_ohlcv(500)
        
        results = backtester.backtest(sample_strategy, data)
        
        required_metrics = [
            'total_return', 'sharpe_ratio', 'sortino_ratio',
            'max_drawdown', 'win_rate', 'expectancy',
            'total_trades', 'profit_factor'
        ]
        for metric in required_metrics:
            assert metric in results
            
    def test_backtest_with_fees(self, sample_strategy):
        """Backtest include fee"""
        backtester = VectorBTBacktester(fee_rate=0.001)
        data = create_sample_ohlcv(500)
        
        results_with_fees = backtester.backtest(sample_strategy, data)
        
        backtester_no_fees = VectorBTBacktester(fee_rate=0)
        results_no_fees = backtester_no_fees.backtest(sample_strategy, data)
        
        # Con fee, return dovrebbe essere minore
        assert results_with_fees['total_return'] <= results_no_fees['total_return']
        
    def test_no_trades_handled(self):
        """Strategia senza trade non crasha"""
        class NoTradeStrategy(StrategyCore):
            def generate_signal(self, df):
                return None  # Mai trade
        
        backtester = VectorBTBacktester()
        results = backtester.backtest(NoTradeStrategy(), create_sample_ohlcv(500))
        
        assert results['total_trades'] == 0
        assert results['total_return'] == 0
```

### 4.2 Lookahead Validator Tests (`tests/unit/test_lookahead_validator.py`)

```python
"""Test lookahead bias detection"""

class TestLookaheadValidator:
    
    def test_clean_strategy_passes(self):
        """Strategia pulita passa validazione"""
        clean_code = '''
class CleanStrategy(StrategyCore):
    def generate_signal(self, df):
        ma = df['close'].rolling(20).mean()
        if df['close'].iloc[-1] > ma.iloc[-1]:
            return Signal('long', 0.1, 0.02, 0.04, 'Clean')
        return None
'''
        validator = LookaheadValidator()
        result = validator.validate(clean_code, create_sample_ohlcv(500))
        
        assert result['ast_check_passed']
        
    def test_negative_shift_detected(self):
        """Rileva shift(-N)"""
        bad_code = '''
class BadStrategy(StrategyCore):
    def generate_signal(self, df):
        future = df['close'].shift(-1)
        return None
'''
        validator = LookaheadValidator()
        result = validator.validate(bad_code, create_sample_ohlcv(500))
        
        assert not result['ast_check_passed']
        assert 'shift' in str(result['violations']).lower()
        
    def test_center_true_detected(self):
        """Rileva rolling(center=True)"""
        bad_code = '''
class BadStrategy(StrategyCore):
    def generate_signal(self, df):
        ma = df['close'].rolling(10, center=True).mean()
        return None
'''
        validator = LookaheadValidator()
        result = validator.validate(bad_code, create_sample_ohlcv(500))
        
        assert not result['ast_check_passed']
        
    def test_shuffle_test_statistical(self):
        """Shuffle test rileva edge statistico"""
        # Strategia con vero edge (o fake per test)
        validator = LookaheadValidator()
        data = create_sample_ohlcv(1000)
        
        p_value = validator._shuffle_test(sample_strategy, data, n_iterations=100)
        
        # p_value < 0.05 = edge statisticamente significativo
        assert 0 <= p_value <= 1
```

### 4.3 Walk-Forward Optimizer Tests (`tests/unit/test_walk_forward.py`)

```python
"""Test walk-forward optimization"""

class TestWalkForwardOptimizer:
    
    def test_creates_correct_windows(self):
        """Crea N windows corretti"""
        optimizer = WalkForwardOptimizer()
        data = create_sample_ohlcv(1000)
        
        windows = optimizer._create_windows(data, n_windows=4)
        
        assert len(windows) == 4
        for train, test in windows:
            assert len(train) > len(test)  # Train > Test
            assert train.index.max() < test.index.min()  # No overlap
            
    def test_unstable_params_rejected(self):
        """Parametri instabili = overfitting"""
        optimizer = WalkForwardOptimizer()
        
        # Parametri molto diversi tra windows = instabile
        params_list = [
            {'sma_period': 10},
            {'sma_period': 50},
            {'sma_period': 5},
            {'sma_period': 100},
        ]
        
        assert not optimizer._are_params_stable(params_list)
        
    def test_stable_params_accepted(self):
        """Parametri stabili accettati"""
        optimizer = WalkForwardOptimizer()
        
        params_list = [
            {'sma_period': 20},
            {'sma_period': 22},
            {'sma_period': 19},
            {'sma_period': 21},
        ]
        
        assert optimizer._are_params_stable(params_list)
```

---

## 🧪 FASE 5: CLASSIFIER & DEPLOYMENT TESTS

### 5.1 Strategy Scorer Tests (`tests/unit/test_scorer.py`)

```python
"""Test strategy scoring system"""

class TestStrategyScorer:
    
    def test_score_calculation(self):
        """Score calcolato correttamente"""
        scorer = StrategyScorer()
        
        metrics = {
            'expectancy': 0.05,       # 5% edge
            'sharpe_ratio': 2.0,
            'consistency': 0.8,
            'wf_stability': 0.1       # Lower = better
        }
        
        score = scorer.score(metrics)
        
        assert 0 <= score <= 100
        
    def test_better_metrics_higher_score(self):
        """Metriche migliori = score più alto"""
        scorer = StrategyScorer()
        
        good_metrics = {'expectancy': 0.08, 'sharpe_ratio': 2.5, 'consistency': 0.9, 'wf_stability': 0.05}
        bad_metrics = {'expectancy': 0.01, 'sharpe_ratio': 0.5, 'consistency': 0.4, 'wf_stability': 0.5}
        
        assert scorer.score(good_metrics) > scorer.score(bad_metrics)
```

### 5.2 Portfolio Builder Tests (`tests/unit/test_portfolio_builder.py`)

```python
"""Test portfolio construction"""

class TestPortfolioBuilder:
    
    def test_selects_top_10(self):
        """Seleziona esattamente 10 strategie"""
        builder = PortfolioBuilder()
        strategies = create_test_strategies(50)  # 50 strategie
        
        selected = builder.select_top_10(strategies)
        
        assert len(selected) == 10
        
    def test_diversification_by_type(self):
        """Max 3 dello stesso tipo"""
        builder = PortfolioBuilder()
        
        # Crea strategie - tutte MOM ma score diversi
        strategies = [create_strategy(type='MOM', score=100-i) for i in range(20)]
        
        selected = builder.select_top_10(strategies)
        
        mom_count = sum(1 for s in selected if s.type == 'MOM')
        assert mom_count <= 3
        
    def test_diversification_by_timeframe(self):
        """Max 3 dello stesso timeframe"""
        builder = PortfolioBuilder()
        
        strategies = [create_strategy(timeframe='15m', score=100-i) for i in range(20)]
        
        selected = builder.select_top_10(strategies)
        
        tf_count = sum(1 for s in selected if s.timeframe == '15m')
        assert tf_count <= 3
        
    def test_minimum_thresholds(self):
        """Filtra strategie sotto soglia"""
        builder = PortfolioBuilder()
        
        strategies = [
            create_strategy(score=60, sharpe=1.5, win_rate=0.6),  # OK
            create_strategy(score=40, sharpe=1.5, win_rate=0.6),  # Score basso
            create_strategy(score=60, sharpe=0.5, win_rate=0.6),  # Sharpe basso
            create_strategy(score=60, sharpe=1.5, win_rate=0.4),  # Win rate basso
        ]
        
        selected = builder.select_top_10(strategies)
        
        assert len(selected) == 1  # Solo la prima passa
```

### 5.3 Subaccount Manager Tests (`tests/unit/test_subaccount_manager.py`)

```python
"""Test subaccount management - DRY RUN ONLY"""

class TestSubaccountManager:
    
    @pytest.fixture
    def mock_client(self, mocker):
        """Mock Hyperliquid client - NO REAL ORDERS"""
        mock = mocker.patch('src.executor.HyperliquidClient')
        mock.return_value.dry_run = True  # IMPORTANTE!
        return mock
    
    def test_deploy_strategy_dry_run(self, mock_client):
        """Deploy strategia (dry run)"""
        manager = SubaccountManager(mock_client.return_value)
        strategy = create_test_strategy()
        
        manager.deploy_strategy(strategy, subaccount_id=1)
        
        assert manager.assignments[1]['strategy_id'] == strategy.id
        # Verifica che NON ha fatto ordini reali
        mock_client.return_value.place_order.assert_not_called()
        
    def test_stop_strategy_closes_positions(self, mock_client):
        """Stop strategia chiude posizioni (dry run)"""
        manager = SubaccountManager(mock_client.return_value)
        strategy = create_test_strategy()
        
        manager.deploy_strategy(strategy, subaccount_id=1)
        manager.stop_strategy(subaccount_id=1)
        
        assert 1 not in manager.assignments
        mock_client.return_value.close_all_positions.assert_called_once()
```

---

## 🧪 FASE 6: ORCHESTRATION TESTS (DRY-RUN ONLY!)

### 6.1 Orchestrator Tests (`tests/unit/test_orchestrator.py`)

```python
"""Test strategy orchestrator - DRY RUN MODE ONLY"""

class TestStrategyOrchestrator:
    
    @pytest.fixture
    def dry_run_orchestrator(self, mocker):
        """Orchestrator in dry-run mode"""
        mocker.patch('src.executor.HyperliquidClient')
        mocker.patch('src.data.HyperliquidDataProvider')
        
        orchestrator = StrategyOrchestrator(dry_run=True)
        assert orchestrator.dry_run == True  # MUST be True
        return orchestrator
    
    def test_orchestrator_starts_in_dry_run(self, dry_run_orchestrator):
        """Orchestrator parte in dry-run"""
        assert dry_run_orchestrator.dry_run == True
        
    def test_schedules_created_per_timeframe(self, dry_run_orchestrator):
        """Schedule creati per timeframe"""
        dry_run_orchestrator._setup_schedules()
        
        jobs = dry_run_orchestrator.scheduler.get_jobs()
        job_ids = [j.id for j in jobs]
        
        assert 'iteration_15m' in job_ids
        assert 'iteration_1h' in job_ids
        
    def test_strategy_execution_dry_run(self, dry_run_orchestrator, mocker):
        """Esecuzione strategia in dry-run"""
        mock_signal = Signal('long', 0.1, 0.02, 0.04, 'Test')
        mock_strategy = mocker.Mock()
        mock_strategy.generate_signal.return_value = mock_signal
        
        dry_run_orchestrator._execute_strategy(
            subaccount_id=1,
            strategy=mock_strategy,
            meta={'symbol': 'BTC', 'timeframe': '15m', 'strategy_id': 'test'}
        )
        
        # Signal generato ma NON eseguito (dry-run)
        mock_strategy.generate_signal.assert_called_once()
        # Verifica log del signal
        assert dry_run_orchestrator.signal_log[-1] == mock_signal
        
    def test_graceful_shutdown(self, dry_run_orchestrator):
        """Shutdown graceful"""
        dry_run_orchestrator.start()
        dry_run_orchestrator.shutdown()
        
        assert dry_run_orchestrator.running == False
```

### 6.2 Signal Execution Tests (`tests/unit/test_signal_execution.py`)

```python
"""Test signal execution - DRY RUN ONLY"""

class TestSignalExecution:
    
    @pytest.fixture
    def mock_client(self, mocker):
        """Mock client - verifica dry_run"""
        mock = mocker.patch('src.executor.HyperliquidClient')
        mock.return_value.dry_run = True
        return mock.return_value
    
    def test_open_position_dry_run(self, mock_client):
        """Open position non esegue ordini reali"""
        executor = SignalExecutor(mock_client, dry_run=True)
        signal = Signal('long', 0.1, 42000, 44000, 'Test')
        
        result = executor.execute(signal, symbol='BTC', subaccount_id=1)
        
        assert result['executed'] == False  # Dry run
        assert result['would_execute'] == True
        mock_client.place_order.assert_not_called()
        
    def test_risk_limits_enforced(self, mock_client):
        """Limiti di rischio rispettati"""
        executor = SignalExecutor(mock_client, dry_run=True)
        
        # Signal con size troppo grande
        signal = Signal('long', 0.5, 42000, 44000, 'Too big')  # 50%!
        
        result = executor.execute(signal, symbol='BTC', subaccount_id=1)
        
        assert result['rejected'] == True
        assert 'risk limit' in result['reason'].lower()
```

### 6.3 E2E Orchestration Test (`tests/e2e/test_full_cycle.py`)

```python
"""End-to-end test - FULL DRY RUN"""

class TestFullCycleDryRun:
    """
    Test completo del ciclo:
    1. Genera strategia
    2. Backtest
    3. Valida
    4. Deploy (dry-run)
    5. Simula esecuzione
    6. Verifica risultati
    """
    
    @pytest.fixture
    def full_system_dry_run(self, mocker):
        """Sistema completo in dry-run"""
        # Mock tutti i componenti esterni
        mocker.patch('src.data.HyperliquidDataProvider')
        mocker.patch('src.executor.HyperliquidClient')
        mocker.patch('src.generator.AIManager')
        
        return {
            'generator': StrategyBuilder(),
            'backtester': VectorBTBacktester(),
            'validator': LookaheadValidator(),
            'scorer': StrategyScorer(),
            'portfolio': PortfolioBuilder(),
            'orchestrator': StrategyOrchestrator(dry_run=True)
        }
    
    async def test_generate_to_deploy_cycle(self, full_system_dry_run):
        """Ciclo completo genera -> deploy"""
        sys = full_system_dry_run
        
        # 1. Genera 20 strategie
        strategies = []
        for i in range(20):
            code = sys['generator'].generate_strategy('MOM', '15m')
            strategies.append(code)
        
        assert len(strategies) == 20
        
        # 2. Backtest tutte
        results = []
        data = create_sample_ohlcv(1000)
        for code in strategies:
            strategy = compile_and_instantiate(code)
            result = sys['backtester'].backtest(strategy, data)
            results.append(result)
        
        # 3. Valida (no lookahead)
        valid_strategies = []
        for code, result in zip(strategies, results):
            validation = sys['validator'].validate(code, data)
            if validation['ast_check_passed']:
                valid_strategies.append((code, result))
        
        # 4. Score e seleziona top 10
        scored = []
        for code, result in valid_strategies:
            score = sys['scorer'].score(result)
            scored.append({'code': code, 'score': score, **result})
        
        top_10 = sys['portfolio'].select_top_10(scored)
        assert len(top_10) <= 10
        
        # 5. Deploy (dry-run)
        for i, strategy in enumerate(top_10):
            sys['orchestrator'].deploy_strategy(strategy, subaccount_id=i+1)
        
        # 6. Simula 100 iterazioni
        for _ in range(100):
            await sys['orchestrator']._run_iteration_dry_run()
        
        # 7. Verifica log signals
        assert len(sys['orchestrator'].signal_log) > 0
        
    async def test_no_real_orders_ever(self, full_system_dry_run, mocker):
        """VERIFICA: nessun ordine reale MAI"""
        spy = mocker.spy(full_system_dry_run['orchestrator'].client, 'place_order')
        
        # Esegui ciclo completo
        await self.test_generate_to_deploy_cycle(full_system_dry_run)
        
        # place_order NON deve essere mai chiamato
        spy.assert_not_called()
```

---

## 🧪 FASE 7: MONITORING TESTS

### 7.1 Dashboard Tests (`tests/unit/test_dashboard.py`)

```python
"""Test monitoring dashboard"""

class TestDashboard:
    
    def test_dashboard_renders(self, mocker):
        """Dashboard si renderizza"""
        mocker.patch('src.database.DatabaseConnection')
        
        dashboard = MonitorDashboard()
        display = dashboard._generate_display()
        
        assert display is not None
        
    def test_metrics_displayed(self, mocker):
        """Metriche visualizzate correttamente"""
        mock_db = mocker.patch('src.database.DatabaseConnection')
        mock_db.return_value.get_live_strategies.return_value = [
            {'name': 'Test', 'pnl': 100, 'win_rate': 0.6}
        ]
        
        dashboard = MonitorDashboard()
        display = dashboard._generate_display()
        
        # Verifica contenuto
        assert 'Test' in str(display)
```

### 7.2 Health Check Tests (`tests/unit/test_health_check.py`)

```python
"""Test health check system"""

class TestHealthCheck:
    
    def test_all_systems_healthy(self, mocker):
        """Tutti i sistemi OK"""
        mocker.patch('src.data.HyperliquidDataProvider.is_connected', return_value=True)
        mocker.patch('src.database.DatabaseConnection.is_connected', return_value=True)
        
        health = HealthChecker()
        status = health.check_all()
        
        assert status['healthy'] == True
        assert status['websocket'] == 'OK'
        assert status['database'] == 'OK'
        
    def test_websocket_down_detected(self, mocker):
        """Rileva WebSocket down"""
        mocker.patch('src.data.HyperliquidDataProvider.is_connected', return_value=False)
        
        health = HealthChecker()
        status = health.check_all()
        
        assert status['healthy'] == False
        assert status['websocket'] == 'ERROR'
```

---

## 🔧 TEST FIXTURES (`tests/conftest.py`)

```python
"""Global test fixtures"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data"""
    def _create(n_candles=500, seed=42):
        np.random.seed(seed)
        
        dates = pd.date_range(
            end=datetime.now(),
            periods=n_candles,
            freq='15min'
        )
        
        # Random walk price
        returns = np.random.randn(n_candles) * 0.001
        close = 42000 * np.cumprod(1 + returns)
        
        df = pd.DataFrame({
            'open': close * (1 + np.random.randn(n_candles) * 0.001),
            'high': close * (1 + np.abs(np.random.randn(n_candles)) * 0.002),
            'low': close * (1 - np.abs(np.random.randn(n_candles)) * 0.002),
            'close': close,
            'volume': np.random.randint(100, 1000, n_candles)
        }, index=dates)
        
        # Ensure high >= open, close, low
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)
        
        return df
    
    return _create


@pytest.fixture
def mock_strategy():
    """Simple test strategy"""
    class MockStrategy(StrategyCore):
        def generate_signal(self, df):
            if len(df) < 20:
                return None
            if df['close'].iloc[-1] > df['close'].rolling(20).mean().iloc[-1]:
                return Signal('long', 0.1, 0.02, 0.04, 'Test')
            return None
    return MockStrategy()


@pytest.fixture
def db_session():
    """In-memory database session"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.database.models import Base
    
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()


@pytest.fixture
def dry_run_config():
    """Configuration with dry_run=True"""
    return {
        'system': {'name': 'SixBTC-Test'},
        'trading': {
            'dry_run': True,  # IMPORTANT!
            'max_positions': 10
        },
        'hyperliquid': {
            'dry_run': True  # IMPORTANT!
        }
    }
```

---

## 🏃 ESECUZIONE TEST

### Comandi

```bash
# Tutti i test
pytest tests/ -v

# Solo unit test (veloci)
pytest tests/unit/ -v

# Solo integration test
pytest tests/integration/ -v

# Solo E2E (lenti)
pytest tests/e2e/ -v

# Con coverage
pytest tests/ --cov=src --cov-report=html

# Test specifico
pytest tests/unit/test_strategy_base.py -v

# Test con keyword
pytest tests/ -k "dry_run" -v

# Test paralleli (più veloci)
pytest tests/ -n auto
```

### CI/CD Pipeline (`.github/workflows/test.yml`)

```yaml
name: SixBTC Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: sixbtc_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio
          
      - name: Run tests
        run: |
          pytest tests/ -v --cov=src --cov-report=xml
        env:
          DRY_RUN: true
          
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## ✅ CHECKLIST PRE-DEPLOYMENT

Prima di andare in produzione, TUTTI questi test devono passare:

### Unit Tests
- [ ] `test_config.py` - Tutti passano
- [ ] `test_database.py` - Tutti passano
- [ ] `test_strategy_base.py` - Tutti passano
- [ ] `test_binance_downloader.py` - Tutti passano
- [ ] `test_hyperliquid_websocket.py` - Tutti passano
- [ ] `test_vectorbt_engine.py` - Tutti passano
- [ ] `test_lookahead_validator.py` - Tutti passano
- [ ] `test_scorer.py` - Tutti passano
- [ ] `test_portfolio_builder.py` - Tutti passano
- [ ] `test_orchestrator.py` - Tutti passano (DRY-RUN)

### Integration Tests
- [ ] `test_data_pipeline.py` - Tutti passano
- [ ] `test_strategy_generation.py` - Tutti passano
- [ ] `test_backtest_pipeline.py` - Tutti passano

### E2E Tests
- [ ] `test_full_cycle.py` - Passa in DRY-RUN
- [ ] `test_no_real_orders_ever` - DEVE passare!

### Coverage
- [ ] Coverage totale > 80%
- [ ] Nessun path critico senza test

### Manual Verification
- [ ] Revisionato codice Phase 6 (trading live)
- [ ] Verificato `dry_run=True` default ovunque
- [ ] API keys NON presenti nel repo
- [ ] `.env` nel `.gitignore`

---

## ⚠️ REGOLE FINALI

1. **MAI** eseguire test con `dry_run=False` prima di review manuale
2. **MAI** committare API keys
3. **SEMPRE** mockare chiamate a exchange esterni nei test
4. **SEMPRE** verificare che `place_order` non sia chiamato nei test
5. **PRIMA** di andare live: esegui TUTTI i test E fai review manuale del codice trading

---

**Last Updated**: 2025-12-20  
**Version**: 1.0.0  
**Status**: Ready for Claude Code Implementation