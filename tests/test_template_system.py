"""
Test Template-Based Strategy Generation System

Tests:
1. ParametricGenerator - variations from templates
2. TemplateGenerator - AI template creation (mocked)
3. StrategyBuilder integration
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4

from src.generator.parametric_generator import ParametricGenerator, GeneratedStrategy
from src.generator.template_generator import TemplateGenerator
from src.generator.strategy_builder import StrategyBuilder
from src.database.models import StrategyTemplate


# ============ FIXTURES ============

@pytest.fixture
def sample_template():
    """Create a sample StrategyTemplate for testing"""
    return StrategyTemplate(
        id=uuid4(),
        name="TPL_MOM_test123",
        strategy_type="MOM",
        timeframe="1h",
        code_template='''import pandas as pd
import numpy as np
import talib as ta
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType


class Strategy_MOM_test123(StrategyCore):
    """
    Momentum strategy template for 1h timeframe

    Parameters:
    - indicator_period: RSI calculation period
    - threshold_low: Oversold threshold
    - threshold_high: Overbought threshold
    - atr_multiplier: ATR multiplier for stop loss
    """

    leverage = {{ leverage }}

    def __init__(self, params: dict = None):
        super().__init__(params)

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        min_bars = 100
        if len(df) < min_bars:
            return None

        # Calculate RSI with parameterized period
        rsi = ta.RSI(df['close'], timeperiod={{ indicator_period }})
        current_rsi = rsi.iloc[-1]

        current_price = df['close'].iloc[-1]
        atr = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        current_atr = atr.iloc[-1]

        if pd.isna(current_atr) or current_atr <= 0:
            return None

        # Entry conditions with parameterized thresholds
        entry_long = current_rsi < {{ threshold_low }}
        entry_short = current_rsi > {{ threshold_high }}

        if entry_long:
            return Signal(
                direction='long',
                leverage=self.leverage,
                sl_type=StopLossType.ATR,
                atr_stop_multiplier={{ atr_multiplier }},
                tp_type=TakeProfitType.RR_RATIO,
                rr_ratio=2.0,
                reason="RSI oversold entry"
            )

        if entry_short:
            return Signal(
                direction='short',
                leverage=self.leverage,
                sl_type=StopLossType.ATR,
                atr_stop_multiplier={{ atr_multiplier }},
                tp_type=TakeProfitType.RR_RATIO,
                rr_ratio=2.0,
                reason="RSI overbought entry"
            )

        return None
''',
        parameters_schema={
            "indicator_period": {"type": "int", "values": [7, 14, 21]},
            "threshold_low": {"type": "int", "values": [25, 30]},
            "threshold_high": {"type": "int", "values": [70, 75]},
            "atr_multiplier": {"type": "float", "values": [1.5, 2.0]},
            "leverage": {"type": "int", "values": [5, 10]}
        },
        ai_provider="test",
        generation_prompt="Test prompt"
    )


@pytest.fixture
def parametric_generator():
    """Create ParametricGenerator instance"""
    return ParametricGenerator()


# ============ PARAMETRIC GENERATOR TESTS ============

class TestParametricGenerator:
    """Test ParametricGenerator class"""

    def test_generate_variations_count(self, parametric_generator, sample_template):
        """Test that correct number of variations are generated"""
        # Expected: 3 * 2 * 2 * 2 * 2 = 48 combinations
        strategies = parametric_generator.generate_variations(sample_template)

        assert len(strategies) == 48
        assert all(isinstance(s, GeneratedStrategy) for s in strategies)

    def test_generate_variations_with_limit(self, parametric_generator, sample_template):
        """Test limiting number of variations"""
        strategies = parametric_generator.generate_variations(
            sample_template,
            max_variations=10
        )

        assert len(strategies) == 10

    def test_generated_code_has_no_placeholders(self, parametric_generator, sample_template):
        """Test that generated code has no Jinja2 placeholders"""
        strategies = parametric_generator.generate_variations(sample_template)

        for s in strategies:
            assert '{{' not in s.code
            assert '}}' not in s.code

    def test_generated_code_has_actual_values(self, parametric_generator, sample_template):
        """Test that parameters are actually substituted in code"""
        strategies = parametric_generator.generate_variations(
            sample_template,
            max_variations=1
        )

        s = strategies[0]
        # Check that one of the parameter values is in the code
        assert any(
            f"timeperiod={p}" in s.code
            for p in [7, 14, 21]
        )

    def test_validation_passes_for_generated_code(self, parametric_generator, sample_template):
        """Test that generated code passes validation"""
        strategies = parametric_generator.generate_variations(sample_template)

        # All strategies should pass validation
        valid_count = sum(1 for s in strategies if s.validation_passed)
        assert valid_count == len(strategies)

    def test_unique_strategy_ids(self, parametric_generator, sample_template):
        """Test that all strategy IDs are unique"""
        strategies = parametric_generator.generate_variations(sample_template)

        ids = [s.strategy_id for s in strategies]
        assert len(ids) == len(set(ids))

    def test_unique_parameter_hashes(self, parametric_generator, sample_template):
        """Test that all parameter hashes are unique"""
        strategies = parametric_generator.generate_variations(sample_template)

        hashes = [s.parameter_hash for s in strategies]
        assert len(hashes) == len(set(hashes))

    def test_parameters_stored_correctly(self, parametric_generator, sample_template):
        """Test that parameters are stored in generated strategy"""
        strategies = parametric_generator.generate_variations(
            sample_template,
            max_variations=1
        )

        s = strategies[0]
        assert 'indicator_period' in s.parameters
        assert 'threshold_low' in s.parameters
        assert 'threshold_high' in s.parameters
        assert 'atr_multiplier' in s.parameters
        assert 'leverage' in s.parameters

    def test_template_id_stored(self, parametric_generator, sample_template):
        """Test that template ID is stored in generated strategy"""
        strategies = parametric_generator.generate_variations(sample_template)

        for s in strategies:
            assert s.template_id == str(sample_template.id)

    def test_count_variations(self, parametric_generator, sample_template):
        """Test counting variations without generating"""
        count = parametric_generator.count_variations(sample_template)
        assert count == 48  # 3 * 2 * 2 * 2 * 2

    def test_estimate_batch_size(self, parametric_generator, sample_template):
        """Test estimating batch size for multiple templates"""
        templates = [sample_template, sample_template]
        estimate = parametric_generator.estimate_batch_size(templates)
        assert estimate == 96  # 48 * 2


# ============ TEMPLATE GENERATOR TESTS ============

class TestTemplateGenerator:
    """Test TemplateGenerator class (with mocked AI)"""

    @pytest.fixture
    def mock_config(self):
        """Config for template generator"""
        return {
            'ai': {
                'providers': [
                    {
                        'name': 'test',
                        'model': 'test-model',
                        'api_key': 'test-key',
                        'enabled': True
                    }
                ],
                'rotation_strategy': 'round_robin'
            }
        }

    @patch('src.generator.template_generator.AIManager')
    def test_generate_template_parses_response(self, mock_ai_class, mock_config):
        """Test that template generator parses AI response correctly"""
        # Mock AI response
        mock_ai = Mock()
        mock_ai.generate.return_value = '''
Here is the template:

```python
import pandas as pd
import talib as ta
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType

class Strategy_MOM_abc123(StrategyCore):
    leverage = {{ leverage }}

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        if len(df) < 100:
            return None

        rsi = ta.RSI(df['close'], timeperiod={{ indicator_period }})
        if rsi.iloc[-1] < {{ threshold }}:
            return Signal(direction='long', leverage=self.leverage, reason="RSI oversold")
        return None
```

```json
{
  "indicator_period": {"type": "int", "values": [7, 14, 21]},
  "threshold": {"type": "int", "values": [25, 30, 35]},
  "leverage": {"type": "int", "values": [5, 10]}
}
```
'''
        mock_ai.get_provider_name.return_value = "test_provider"
        mock_ai_class.return_value = mock_ai

        generator = TemplateGenerator(mock_config)
        template = generator.generate_template("MOM", "1h")

        assert template is not None
        assert template.strategy_type == "MOM"
        assert template.timeframe == "1h"
        assert "indicator_period" in template.parameters_schema
        assert "threshold" in template.parameters_schema
        assert "leverage" in template.parameters_schema
        assert "{{" in template.code_template  # Has Jinja2 placeholders


# ============ STRATEGY BUILDER INTEGRATION TESTS ============

class TestStrategyBuilderTemplateIntegration:
    """Test StrategyBuilder template-based generation"""

    @pytest.fixture
    def mock_config(self):
        """Config for strategy builder"""
        return {
            'generation': {
                'pattern_discovery': {
                    'api_url': 'http://localhost:8001'
                },
                'pattern_tier_filter': 1,
                'min_quality_score': 0.75,
                'max_fix_attempts': 3,
                'leverage': {
                    'min': 3,
                    'max': 20
                }
            },
            'ai': {
                'providers': [
                    {
                        'name': 'test',
                        'model': 'test-model',
                        'api_key': 'test-key',
                        'enabled': True
                    }
                ],
                'rotation_strategy': 'round_robin'
            }
        }

    def test_generate_from_templates(self, mock_config, sample_template):
        """Test generating strategies from templates"""
        # Create builder without AI (parametric only)
        builder = StrategyBuilder(config=mock_config, init_ai=False)

        strategies = builder.generate_from_templates(
            templates=[sample_template],
            max_variations_per_template=5
        )

        assert len(strategies) == 5
        assert all(s.generation_mode == "template" for s in strategies)
        assert all(s.template_id == str(sample_template.id) for s in strategies)

    def test_estimate_variations(self, mock_config, sample_template):
        """Test estimating variations"""
        builder = StrategyBuilder(config=mock_config, init_ai=False)

        estimate = builder.estimate_variations([sample_template])
        assert estimate == 48

    @patch('src.generator.strategy_builder.TemplateGenerator')
    def test_generate_daily_batch(self, mock_tg_class, mock_config, sample_template):
        """Test daily batch generation flow"""
        # Mock template generator
        mock_tg = Mock()
        mock_tg.generate_batch.return_value = [sample_template]
        mock_tg_class.return_value = mock_tg

        builder = StrategyBuilder(config=mock_config, init_ai=True)
        builder.template_generator = mock_tg

        new_templates, strategies = builder.generate_daily_batch(
            new_templates_count=1,
            existing_templates=[],
            max_variations_per_template=10
        )

        assert len(new_templates) == 1
        assert len(strategies) == 10

    def test_converted_strategy_has_all_fields(self, mock_config, sample_template):
        """Test that converted strategy has all required fields"""
        builder = StrategyBuilder(config=mock_config, init_ai=False)

        strategies = builder.generate_from_templates(
            templates=[sample_template],
            max_variations_per_template=1
        )

        s = strategies[0]
        assert s.code is not None
        assert s.strategy_id is not None
        assert s.strategy_type == "MOM"
        assert s.timeframe == "1h"
        assert s.generation_mode == "template"
        assert s.template_id == str(sample_template.id)
        assert s.parameters is not None
        assert s.parameter_hash is not None
        assert s.validation_passed is True


# ============ LOOKAHEAD BIAS DETECTION TESTS ============

class TestLookaheadBiasDetection:
    """Test that lookahead bias is detected in generated code"""

    @pytest.fixture
    def bad_template_center(self):
        """Template with center=True (lookahead bias)"""
        return StrategyTemplate(
            id=uuid4(),
            name="TPL_BAD_center",
            strategy_type="MOM",
            timeframe="1h",
            code_template='''import pandas as pd
from src.strategies.base import StrategyCore, Signal

class Strategy_BAD_center(StrategyCore):
    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        # This is lookahead bias!
        swing_high = df['high'].rolling({{ period }}, center=True).max()
        return None
''',
            parameters_schema={
                "period": {"type": "int", "values": [10, 20]}
            }
        )

    @pytest.fixture
    def bad_template_shift(self):
        """Template with negative shift (lookahead bias)"""
        return StrategyTemplate(
            id=uuid4(),
            name="TPL_BAD_shift",
            strategy_type="MOM",
            timeframe="1h",
            code_template='''import pandas as pd
from src.strategies.base import StrategyCore, Signal

class Strategy_BAD_shift(StrategyCore):
    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        # This is lookahead bias!
        future_price = df['close'].shift(-{{ shift }})
        return None
''',
            parameters_schema={
                "shift": {"type": "int", "values": [1, 2]}
            }
        )

    def test_detects_center_bias(self, bad_template_center):
        """Test that center=True bias is detected"""
        generator = ParametricGenerator()
        strategies = generator.generate_variations(bad_template_center)

        # All strategies should fail validation
        for s in strategies:
            assert s.validation_passed is False
            assert any("center=True" in e for e in s.validation_errors)

    def test_detects_negative_shift_bias(self, bad_template_shift):
        """Test that negative shift bias is detected"""
        generator = ParametricGenerator()
        strategies = generator.generate_variations(bad_template_shift)

        # All strategies should fail validation
        for s in strategies:
            assert s.validation_passed is False
            assert any("negative shift" in e for e in s.validation_errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
