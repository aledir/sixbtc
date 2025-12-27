"""
Tests for generator module

Validates:
- AI provider rotation
- Pattern fetching from pattern-discovery
- Strategy code generation
- Template rendering
- Code validation
"""

import pytest
import ast
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.generator.ai_manager import AIManager
from src.generator.pattern_fetcher import PatternFetcher
from src.generator.strategy_builder import StrategyBuilder
from src.strategies.base import StrategyCore, Signal


@pytest.fixture
def mock_config():
    """Mock configuration for new AIClient structure"""
    return {
        'ai': {
            'mode': 'cli',
            'cli': {
                'model': 'claude',
                'timeout': 300
            }
        },
        'generation': {
            'strategies_per_cycle': 20,
            'min_code_quality_score': 0.7,
            'pattern_discovery_url': 'http://localhost:8001'
        }
    }


@pytest.fixture
def sample_patterns():
    """Sample patterns from pattern-discovery"""
    return [
        {
            'pattern_id': 'RSI_OVERSOLD_001',
            'type': 'REV',
            'description': 'RSI oversold with volume confirmation',
            'conditions': {
                'rsi_period': 14,
                'rsi_threshold': 30,
                'volume_multiplier': 1.5
            },
            'performance': {
                'win_rate': 0.62,
                'sharpe': 1.8,
                'edge': 0.045
            }
        },
        {
            'pattern_id': 'BREAKOUT_002',
            'type': 'MOM',
            'description': 'Price breakout above resistance',
            'conditions': {
                'lookback_period': 20,
                'breakout_threshold': 1.02
            },
            'performance': {
                'win_rate': 0.58,
                'sharpe': 1.5,
                'edge': 0.038
            }
        }
    ]


class TestAIManager:
    """Test AI provider management"""

    def test_initialization(self, mock_config):
        """Test AI manager initialization with CLI provider"""
        with patch('src.ai.cli_provider.CLIProvider.is_available_sync') as mock_avail:
            mock_avail.return_value = True
            manager = AIManager(mock_config)

            # New AIManager wraps AIClient with CLI provider
            assert manager._provider_name == 'cli:claude'
            assert manager.client is not None

    def test_generate_with_cli(self, mock_config):
        """Test strategy generation with CLI provider"""
        with patch('src.ai.cli_provider.CLIProvider.is_available_sync') as mock_avail:
            mock_avail.return_value = True
            with patch('src.ai.cli_provider.CLIProvider.generate_response') as mock_gen:
                # Mock CLI response
                import asyncio
                future = asyncio.Future()
                future.set_result("class Strategy_TEST:\n    pass")
                mock_gen.return_value = future

                manager = AIManager(mock_config)

                with patch.object(manager.client, 'generate_response_sync') as mock_sync:
                    mock_sync.return_value = "class Strategy_TEST:\n    pass"

                    result = manager.generate(
                        prompt="Generate a momentum strategy"
                    )

                    assert "class Strategy_TEST" in result
                    mock_sync.assert_called_once()

    def test_get_provider_name(self, mock_config):
        """Test getting provider name"""
        with patch('src.ai.cli_provider.CLIProvider.is_available_sync') as mock_avail:
            mock_avail.return_value = True
            manager = AIManager(mock_config)

            provider_name = manager.get_provider_name()
            assert provider_name == 'cli:claude'

    def test_retry_on_failure(self, mock_config):
        """Test retry logic on failure"""
        with patch('src.ai.cli_provider.CLIProvider.is_available_sync') as mock_avail:
            mock_avail.return_value = True
            manager = AIManager(mock_config)

            with patch.object(manager.client, 'generate_response_sync') as mock_sync:
                mock_sync.return_value = "Success"

                result = manager.generate_with_retry(
                    prompt="Test",
                    max_retries=3
                )

                assert result == "Success"
                mock_sync.assert_called_once()


class TestPatternFetcher:
    """Test pattern fetching from pattern-discovery API"""

    @patch('requests.get')
    def test_fetch_production_patterns(self, mock_get, mock_config, sample_patterns):
        """Test fetching production patterns"""
        # Mock health check and API response
        health_response = Mock()
        health_response.status_code = 200

        patterns_response = Mock()
        patterns_response.status_code = 200
        patterns_response.json.return_value = {
            'patterns': sample_patterns
        }

        mock_get.side_effect = [health_response, patterns_response]

        fetcher = PatternFetcher(mock_config['generation']['pattern_discovery_url'])
        patterns = fetcher.fetch_production_patterns(tier=1, limit=10)

        assert len(patterns) == 2
        assert patterns[0]['pattern_id'] == 'RSI_OVERSOLD_001'

    @patch('requests.get')
    def test_get_tier_1_patterns(self, mock_get, mock_config):
        """Test fetching Tier 1 patterns"""
        # Mock health check and API response
        health_response = Mock()
        health_response.status_code = 200

        patterns_response = Mock()
        patterns_response.status_code = 200
        patterns_response.json.return_value = {
            'patterns': [
                {
                    'id': 'test-123',
                    'name': 'Test Pattern',
                    'formula': 'RSI < 30',
                    'tier': 1,
                    'target_name': 'target_up_24h',
                    'target_direction': 'bullish',
                    'test_edge': 0.05,
                    'test_win_rate': 0.62,
                    'test_n_signals': 100,
                    'quality_score': 0.8
                }
            ]
        }

        mock_get.side_effect = [health_response, patterns_response]

        fetcher = PatternFetcher(mock_config['generation']['pattern_discovery_url'])
        patterns = fetcher.get_tier_1_patterns(limit=10, min_quality_score=0.75)

        assert len(patterns) == 1
        assert patterns[0].name == 'Test Pattern'
        assert patterns[0].tier == 1

    @patch('requests.get')
    def test_handle_api_error(self, mock_get, mock_config):
        """Test handling API errors"""
        # Mock health check failure
        mock_get.side_effect = Exception("Connection error")

        # PatternFetcher handles connection errors gracefully
        fetcher = PatternFetcher(mock_config['generation']['pattern_discovery_url'])
        assert fetcher.is_available() is False

        # Methods return empty when unavailable
        patterns = fetcher.fetch_production_patterns()
        assert patterns == []


class TestStrategyBuilder:
    """Test strategy code building"""

    def test_build_from_template(self):
        """Test building strategy from Jinja2 template"""
        builder = StrategyBuilder()

        template_vars = {
            'strategy_name': 'Strategy_TEST_123',
            'indicator': 'RSI',
            'period': 14,
            'threshold': 30,
            'timeframe': '15m'
        }

        code = builder.build_from_template(
            template_name='simple_indicator.j2',
            variables=template_vars
        )

        assert "Strategy_TEST_123" in code
        assert "RSI" in code


    def test_validate_generated_code(self):
        """Test code validation"""
        builder = StrategyBuilder()

        valid_code = '''
from src.strategies.base import StrategyCore, Signal

class Strategy_TEST(StrategyCore):
    def generate_signal(self, df):
        return Signal(direction='long')
'''

        invalid_code = '''
class Strategy_TEST:
    # Missing StrategyCore inheritance
    def wrong_method(self):
        pass
'''

        assert builder.validate_code(valid_code) is True
        assert builder.validate_code(invalid_code) is False

    
    def test_extract_strategy_metadata(self):
        """Test metadata extraction from code"""
        builder = StrategyBuilder()

        code = '''
class Strategy_MOM_abc123(StrategyCore):
    """
    Momentum strategy using moving averages

    Timeframe: 15m
    Type: MOM
    """
    def __init__(self):
        self.timeframe = '15m'
        self.symbol = 'BTC/USDT'
'''

        metadata = builder.extract_metadata(code)

        assert metadata['name'] == 'Strategy_MOM_abc123'
        assert metadata['type'] == 'MOM'
        assert metadata['timeframe'] == '15m'

    
    def test_generate_strategy_id(self):
        """Test unique strategy ID generation"""
        builder = StrategyBuilder()

        id1 = builder.generate_strategy_id('MOM')
        id2 = builder.generate_strategy_id('MOM')

        # IDs should be unique
        assert id1 != id2
        assert id1.startswith('Strategy_MOM_')
        assert len(id1.split('_')[-1]) == 8  # 8-char hash


class TestStrategyCodeQuality:
    """Test generated code quality"""

    
    def test_no_lookahead_bias(self):
        """Test that generated code has no lookahead bias"""
        builder = StrategyBuilder()

        # Generate code
        code = builder.build_from_template(
            template_name='momentum_basic.j2',
            variables={
                'strategy_name': 'Strategy_TEST',
                'fast_period': 10,
                'slow_period': 20
            }
        )

        # Check for forbidden patterns
        forbidden = ['center=True', 'shift(-', 'future']
        for pattern in forbidden:
            assert pattern not in code

class TestGeneratorIntegration:
    """Integration tests for complete generation workflow"""

    @patch('requests.get')
    def test_pattern_fetching_workflow(
        self,
        mock_get,
        mock_config,
        sample_patterns
    ):
        """Test pattern fetching workflow"""
        # Mock health check and pattern API
        health_response = Mock()
        health_response.status_code = 200

        patterns_response = Mock()
        patterns_response.status_code = 200
        patterns_response.json.return_value = {'patterns': sample_patterns}

        mock_get.side_effect = [health_response, patterns_response]

        # Fetch patterns
        fetcher = PatternFetcher(mock_config['generation']['pattern_discovery_url'])
        patterns = fetcher.fetch_production_patterns(tier=1, limit=5)

        # Validate patterns fetched correctly
        assert len(patterns) > 0
        first = patterns[0]
        # Check pattern_id field (dict format from sample_patterns fixture)
        assert first['pattern_id'] == 'RSI_OVERSOLD_001'
        assert first['type'] == 'REV'

    def test_strategy_validation(self):
        """Test strategy code validation (without AI generation)"""
        builder = StrategyBuilder()

        valid_code = '''import pandas as pd
import talib as ta
from src.strategies.base import StrategyCore, Signal

class Strategy_MOM_test123(StrategyCore):
    leverage = 5

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        if len(df) < 50:
            return None
        rsi = ta.RSI(df['close'], timeperiod=14)
        if rsi.iloc[-1] < 30:
            return Signal(direction='long', atr_stop_multiplier=2.0, atr_take_multiplier=3.0, reason="RSI oversold")
        return None
'''
        assert builder.validate_code(valid_code) is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
