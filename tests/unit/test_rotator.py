"""
Tests for the Rotator module.

Covers:
1. StrategySelector - strategy selection with diversification
2. detect_direction - direction detection from code
"""
import pytest
from unittest.mock import MagicMock, patch

from src.rotator.selector import StrategySelector, detect_direction


# =============================================================================
# DETECT DIRECTION TESTS
# =============================================================================

class TestDetectDirection:
    """Tests for detect_direction function."""

    def test_long_only(self):
        """Code with only long signals should return LONG."""
        code = '''
class PtaStrat_TRD_abc123(StrategyCore):
    def generate_signal(self, df):
        return Signal(direction='long')
'''
        assert detect_direction(code) == "LONG"

    def test_short_only(self):
        """Code with only short signals should return SHORT."""
        code = '''
class PtaStrat_TRD_abc123(StrategyCore):
    def generate_signal(self, df):
        return Signal(direction='short')
'''
        assert detect_direction(code) == "SHORT"

    def test_bidir_explicit(self):
        """Code with explicit bidi should return BIDIR."""
        code = '''
class PtaStrat_TRD_abc123(StrategyCore):
    direction = 'bidi'
    def generate_signal(self, df):
        pass
'''
        assert detect_direction(code) == "BIDIR"

    def test_bidir_both_directions(self):
        """Code with both long and short should return BIDIR."""
        code = '''
class PtaStrat_TRD_abc123(StrategyCore):
    def generate_signal(self, df):
        if condition:
            return Signal(direction='long')
        else:
            return Signal(direction='short')
'''
        assert detect_direction(code) == "BIDIR"

    def test_empty_code_default(self):
        """Empty code should default to LONG."""
        assert detect_direction("") == "LONG"
        assert detect_direction(None) == "LONG"


# =============================================================================
# STRATEGY SELECTOR TESTS
# =============================================================================

class TestStrategySelector:
    """Tests for StrategySelector."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config for selector."""
        return {
            'rotator': {
                'max_live_strategies': 5,
                'min_pool_size': 100,
                'selection': {
                    'max_per_type': 3,
                    'max_per_timeframe': 3,
                    'max_per_direction': 5,
                }
            },
            'active_pool': {
                'min_score': 40,
            }
        }

    def test_selector_initialization(self, mock_config):
        """Selector should initialize with config."""
        selector = StrategySelector(mock_config)

        assert selector.min_score == 40
        assert selector.max_live_strategies == 5
        assert selector.min_pool_size == 100
        assert selector.max_per_type == 3
        assert selector.max_per_timeframe == 3

    def test_selector_missing_config_fails(self):
        """Missing config sections should raise KeyError (Fast Fail)."""
        with pytest.raises(KeyError):
            StrategySelector({})

        with pytest.raises(KeyError):
            StrategySelector({'rotator': {}})

    def test_diversification_limits(self, mock_config):
        """Test that diversification limits are respected."""
        selector = StrategySelector(mock_config)

        # Verify limits are loaded correctly
        assert selector.max_per_type == 3
        assert selector.max_per_timeframe == 3
        assert selector.max_per_direction == 5
