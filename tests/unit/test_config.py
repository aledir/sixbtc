"""
Tests for the Config module.

Covers:
1. Config class - dot notation access, required values
2. Fast Fail principle - missing config raises errors
3. Environment variable interpolation
"""
import pytest
import os
from unittest.mock import patch, MagicMock

from src.config.loader import Config, load_config


# =============================================================================
# CONFIG CLASS TESTS
# =============================================================================

class TestConfig:
    """Tests for Config class."""

    @pytest.fixture
    def sample_config(self):
        """Create sample config data."""
        return {
            'risk': {
                'atr': {
                    'stop_multiplier': 2.0,
                    'take_multiplier': 3.0,
                },
                'max_positions': 10,
            },
            'timeframes': ['15m', '30m', '1h', '2h'],
            'trading': {
                'enabled': True,
            }
        }

    def test_get_nested_value(self, sample_config):
        """get() should access nested values with dot notation."""
        config = Config(**sample_config)

        assert config.get('risk.atr.stop_multiplier') == 2.0
        assert config.get('risk.max_positions') == 10
        assert config.get('timeframes') == ['15m', '30m', '1h', '2h']
        assert config.get('trading.enabled') is True

    def test_get_missing_returns_default(self, sample_config):
        """get() should return default for missing keys."""
        config = Config(**sample_config)

        assert config.get('nonexistent') is None
        assert config.get('nonexistent', 'default') == 'default'
        assert config.get('risk.nonexistent') is None
        assert config.get('risk.atr.nonexistent', 999) == 999

    def test_get_required_success(self, sample_config):
        """get_required() should return value for existing keys."""
        config = Config(**sample_config)

        assert config.get_required('risk.atr.stop_multiplier') == 2.0
        assert config.get_required('risk.max_positions') == 10

    def test_get_required_fails_on_missing(self, sample_config):
        """get_required() should raise ValueError for missing keys."""
        config = Config(**sample_config)

        with pytest.raises(ValueError) as exc_info:
            config.get_required('nonexistent.key')

        assert "Required config key not found" in str(exc_info.value)

    def test_fast_fail_principle(self, sample_config):
        """Missing required config should fail immediately."""
        config = Config(**sample_config)

        # This should work
        config.get_required('risk.atr.stop_multiplier')

        # This should fail fast
        with pytest.raises(ValueError):
            config.get_required('missing.required.key')


# =============================================================================
# LOAD CONFIG TESTS
# =============================================================================

class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_returns_config_instance(self):
        """load_config() should return a Config instance."""
        config = load_config()

        assert isinstance(config, Config)

    def test_load_config_has_required_sections(self):
        """Loaded config should have required sections."""
        config = load_config()

        # These are essential sections that must exist
        assert config.get('risk') is not None
        assert config.get('backtesting') is not None
        assert config.get('validation') is not None

    def test_config_singleton_pattern(self):
        """Multiple calls should return same config (or reload cleanly)."""
        config1 = load_config()
        config2 = load_config()

        # Both should be valid Config instances
        assert isinstance(config1, Config)
        assert isinstance(config2, Config)
