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
    """Mock configuration"""
    return {
        'ai': {
            'providers': [
                {
                    'name': 'openai',
                    'model': 'gpt-4',
                    'api_key': 'test_key_openai',
                    'enabled': True
                },
                {
                    'name': 'anthropic',
                    'model': 'claude-3-5-sonnet',
                    'api_key': 'test_key_anthropic',
                    'enabled': True
                }
            ],
            'rotation_strategy': 'round_robin',
            'max_retries': 3,
            'timeout': 30
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
        """Test AI manager initialization"""
        manager = AIManager(mock_config['ai'])

        assert len(manager.providers) == 2
        assert manager.current_provider_idx == 0
        assert manager.rotation_strategy == 'round_robin'

    def test_generate_with_openai(self, mock_config):
        """Test strategy generation with OpenAI"""
        # Create manager
        manager = AIManager(mock_config['ai'])

        # Mock OpenAI client directly in the manager's clients dict
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="class Strategy_TEST:\n    pass"))
        ]
        mock_response.usage = Mock(total_tokens=100)
        mock_client.chat.completions.create.return_value = mock_response

        # Replace the openai client with our mock
        manager.clients['openai'] = mock_client

        result = manager.generate(
            prompt="Generate a momentum strategy",
            provider='openai'
        )

        assert "class Strategy_TEST" in result
        mock_client.chat.completions.create.assert_called_once()

    def test_provider_rotation_round_robin(self, mock_config):
        """Test round-robin provider rotation"""
        manager = AIManager(mock_config['ai'])

        # First call should use provider 0
        assert manager.current_provider_idx == 0

        # Rotate
        manager._rotate_provider()
        assert manager.current_provider_idx == 1

        # Rotate again (should wrap)
        manager._rotate_provider()
        assert manager.current_provider_idx == 0

    def test_retry_on_failure(self, mock_config):
        """Test retry logic on provider failure"""
        # Create manager
        manager = AIManager(mock_config['ai'])

        # Mock first call fails, second succeeds
        mock_client_openai = Mock()
        mock_success_response = Mock()
        mock_success_response.choices = [Mock(message=Mock(content="Success"))]
        mock_success_response.usage = Mock(total_tokens=50)

        # First provider (openai) fails
        mock_client_openai.chat.completions.create.side_effect = Exception("API Error")

        # Second provider (anthropic) succeeds
        mock_client_anthropic = Mock()
        mock_anthropic_response = Mock()
        mock_anthropic_response.content = [Mock(text="Success")]
        mock_anthropic_response.usage = Mock(input_tokens=25, output_tokens=25)
        mock_client_anthropic.messages.create.return_value = mock_anthropic_response

        # Replace the clients with our mocks
        manager.clients['openai'] = mock_client_openai
        manager.clients['anthropic'] = mock_client_anthropic

        result = manager.generate_with_retry(
            prompt="Test",
            max_retries=2
        )

        assert result == "Success"
        # First provider should be called once and fail
        assert mock_client_openai.chat.completions.create.call_count == 1
        # Second provider should be called once and succeed
        assert mock_client_anthropic.messages.create.call_count == 1


class TestPatternFetcher:
    """Test pattern fetching from pattern-discovery API"""

    @patch('requests.get')
    
    def test_fetch_top_patterns(self, mock_get, mock_config, sample_patterns):
        """Test fetching top patterns"""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'patterns': sample_patterns,
            'total': len(sample_patterns)
        }
        mock_get.return_value = mock_response

        fetcher = PatternFetcher(mock_config['generation']['pattern_discovery_url'])
        patterns = fetcher.fetch_top_patterns(
            tier=1,
            limit=10,
            min_edge=0.03
        )

        assert len(patterns) == 2
        assert patterns[0]['pattern_id'] == 'RSI_OVERSOLD_001'
        assert patterns[0]['performance']['edge'] >= 0.03

    @patch('requests.get')
    
    def test_fetch_patterns_by_type(self, mock_get, mock_config, sample_patterns):
        """Test fetching patterns by type"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'patterns': [p for p in sample_patterns if p['type'] == 'REV']
        }
        mock_get.return_value = mock_response

        fetcher = PatternFetcher(mock_config['generation']['pattern_discovery_url'])
        patterns = fetcher.fetch_by_type(pattern_type='REV')

        assert len(patterns) == 1
        assert patterns[0]['type'] == 'REV'

    @patch('requests.get')
    
    def test_handle_api_error(self, mock_get, mock_config):
        """Test handling API errors"""
        mock_get.side_effect = Exception("Connection error")

        fetcher = PatternFetcher(mock_config['generation']['pattern_discovery_url'])

        with pytest.raises(Exception):
            fetcher.fetch_top_patterns()


class TestStrategyBuilder:
    """Test strategy code building"""

    
    def test_build_from_pattern(self, sample_patterns):
        """Test building strategy from pattern"""
        builder = StrategyBuilder()

        code = builder.build_from_pattern(sample_patterns[0])

        # Validate generated code
        assert "class Strategy_" in code
        assert "StrategyCore" in code
        assert "generate_signal" in code
        assert "rsi_period = 14" in code

        # Should be valid Python
        try:
            ast.parse(code)
            is_valid = True
        except SyntaxError:
            is_valid = False

        assert is_valid is True

    
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

    
    def test_imports_present(self):
        """Test that necessary imports are included"""
        builder = StrategyBuilder()

        code = builder.build_from_pattern({
            'pattern_id': 'TEST',
            'type': 'MOM',
            'conditions': {'rsi_period': 14}
        })

        # Should have necessary imports
        assert 'import pandas as pd' in code or 'from pandas' in code
        assert 'StrategyCore' in code
        assert 'Signal' in code

    
    def test_type_hints(self):
        """Test that type hints are present"""
        builder = StrategyBuilder()

        code = builder.build_from_pattern({
            'pattern_id': 'TEST',
            'type': 'MOM',
            'conditions': {}
        })

        # Should have type hints
        assert 'pd.DataFrame' in code
        assert 'Signal | None' in code or 'Optional[Signal]' in code


class TestGeneratorIntegration:
    """Integration tests for complete generation workflow"""

    @patch('requests.get')
    def test_full_generation_workflow(
        self,
        mock_get,
        mock_config,
        sample_patterns
    ):
        """Test complete strategy generation workflow"""
        # Mock pattern API
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'patterns': sample_patterns}
        mock_get.return_value = mock_response

        # 1. Fetch patterns
        fetcher = PatternFetcher(mock_config['generation']['pattern_discovery_url'])
        patterns = fetcher.fetch_top_patterns(tier=1, limit=5)

        # 2. Build strategy
        builder = StrategyBuilder()
        code = builder.build_from_pattern(patterns[0])

        # 3. Validate
        assert builder.validate_code(code) is True

        # Complete workflow validation
        assert len(patterns) > 0
        assert "class Strategy_" in code
        assert "generate_signal" in code


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
