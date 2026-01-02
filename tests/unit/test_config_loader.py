"""
Unit Tests for Configuration Loader

Tests the config loader module with focus on:
- Environment variable interpolation
- YAML parsing
- Validation logic
- Fast-fail behavior
- Error handling
"""

import os
import tempfile
from pathlib import Path
import pytest
import yaml

import src.config.loader as config_loader
from src.config.loader import (
    load_config,
    _interpolate_env_vars,
    _validate_config,
    Config
)


@pytest.fixture(autouse=True)
def clear_config_cache():
    """Clear config cache before each test to ensure isolation"""
    config_loader._cached_config = None
    yield
    config_loader._cached_config = None


class TestConfigModel:
    """Test Config model functionality"""

    def test_get_nested_value(self):
        """Test getting nested config values with dot notation"""
        config_data = {
            'risk': {
                'atr': {
                    'stop_multiplier': 2.0
                }
            }
        }
        config = Config(**config_data)

        assert config.get('risk.atr.stop_multiplier') == 2.0

    def test_get_missing_value_returns_default(self):
        """Test getting missing value returns default"""
        config = Config(**{})

        assert config.get('nonexistent.key', 'default') == 'default'

    def test_get_required_success(self):
        """Test get_required returns value if exists"""
        config_data = {'key': 'value'}
        config = Config(**config_data)

        assert config.get_required('key') == 'value'

    def test_get_required_raises_on_missing(self):
        """Test get_required raises ValueError if key missing"""
        config = Config(**{})

        with pytest.raises(ValueError, match="Required config key not found"):
            config.get_required('missing.key')

    def test_get_nested_list(self):
        """Test getting nested list values"""
        config_data = {
            'trading': {
                'timeframes': {
                    'available': ['15m', '30m', '1h']
                }
            }
        }
        config = Config(**config_data)

        result = config.get('trading.timeframes.available')
        assert result == ['15m', '30m', '1h']
        assert isinstance(result, list)


class TestEnvInterpolation:
    """Test environment variable interpolation"""

    def test_interpolate_single_var(self):
        """Test interpolating single environment variable"""
        os.environ['TEST_VAR'] = 'test_value'

        config_str = "key: ${TEST_VAR}"
        result = _interpolate_env_vars(config_str)

        assert result == "key: test_value"

        # Cleanup
        del os.environ['TEST_VAR']

    def test_interpolate_multiple_vars(self):
        """Test interpolating multiple environment variables"""
        os.environ['VAR1'] = 'value1'
        os.environ['VAR2'] = 'value2'

        config_str = "key1: ${VAR1}\nkey2: ${VAR2}"
        result = _interpolate_env_vars(config_str)

        assert 'value1' in result
        assert 'value2' in result

        # Cleanup
        del os.environ['VAR1']
        del os.environ['VAR2']

    def test_missing_env_var_raises_error(self):
        """Test that missing env var raises ValueError"""
        config_str = "key: ${NONEXISTENT_VAR}"

        with pytest.raises(ValueError, match="Environment variable 'NONEXISTENT_VAR' is required"):
            _interpolate_env_vars(config_str)

    def test_no_interpolation_if_no_vars(self):
        """Test config without env vars is unchanged"""
        config_str = "key: plain_value"
        result = _interpolate_env_vars(config_str)

        assert result == config_str


class TestConfigValidation:
    """Test configuration validation logic"""

    def test_validate_valid_config(self):
        """Test validation passes for valid config"""
        config_data = {
            'timeframes': ['15m', '30m', '1h'],  # Global timeframes at root level
            'risk': {
                'sizing_mode': 'atr'
            },
            'database': {
                'host': 'localhost',
                'port': 5432,
                'database': 'sixbtc'
            },
            'system': {
                'execution_mode': 'sync'
            }
        }
        config = Config(**config_data)

        # Should not raise
        _validate_config(config)

    def test_validate_invalid_timeframe_raises(self):
        """Test validation fails for invalid timeframe"""
        config_data = {
            'timeframes': ['15m', '99m'],  # Invalid timeframe
            'risk': {'sizing_mode': 'atr'},
            'database': {'host': 'localhost', 'port': 5432, 'database': 'sixbtc'},
            'system': {'execution_mode': 'sync'}
        }
        config = Config(**config_data)

        with pytest.raises(ValueError, match="Invalid timeframe '99m'"):
            _validate_config(config)

    def test_validate_empty_timeframes_raises(self):
        """Test validation fails for empty timeframes"""
        config_data = {
            'timeframes': [],  # Empty list
            'risk': {'sizing_mode': 'atr'},
            'database': {'host': 'localhost', 'port': 5432, 'database': 'sixbtc'},
            'system': {'execution_mode': 'sync'}
        }
        config = Config(**config_data)

        with pytest.raises(ValueError, match="must be a non-empty list"):
            _validate_config(config)

    def test_validate_invalid_sizing_mode_raises(self):
        """Test validation fails for invalid sizing mode"""
        config_data = {
            'timeframes': ['15m'],
            'risk': {'sizing_mode': 'invalid'},  # Invalid mode
            'database': {'host': 'localhost', 'port': 5432, 'database': 'sixbtc'},
            'system': {'execution_mode': 'sync'}
        }
        config = Config(**config_data)

        with pytest.raises(ValueError, match="risk.sizing_mode must be 'fixed' or 'atr'"):
            _validate_config(config)

    def test_validate_incomplete_database_raises(self):
        """Test validation fails for incomplete database config"""
        config_data = {
            'timeframes': ['15m'],
            'risk': {'sizing_mode': 'atr'},
            'database': {'host': 'localhost'},  # Missing port and database
            'system': {'execution_mode': 'sync'}
        }
        config = Config(**config_data)

        with pytest.raises(ValueError, match="Database configuration incomplete"):
            _validate_config(config)

    def test_validate_invalid_execution_mode_raises(self):
        """Test validation fails for invalid execution mode"""
        config_data = {
            'timeframes': ['15m'],
            'risk': {'sizing_mode': 'atr'},
            'database': {'host': 'localhost', 'port': 5432, 'database': 'sixbtc'},
            'system': {
                'execution_mode': 'invalid'  # Invalid mode
            }
        }
        config = Config(**config_data)

        with pytest.raises(ValueError, match="execution_mode must be one of"):
            _validate_config(config)


class TestLoadConfig:
    """Test full config loading workflow"""

    def test_load_config_success(self, tmp_path):
        """Test loading valid config file"""
        # Create temporary config file
        config_data = {
            'system': {
                'name': 'SixBTC',
                'version': '1.0.0',
                'execution_mode': 'sync'
            },
            'timeframes': ['15m', '30m', '1h'],  # Global timeframes at root
            'risk': {
                'sizing_mode': 'atr'
            },
            'database': {
                'host': 'localhost',
                'port': 5432,
                'database': 'sixbtc_test'
            }
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        # Load config
        config = load_config(config_file)

        assert config.get('system.name') == 'SixBTC'
        assert config.get('timeframes') == ['15m', '30m', '1h']
        assert config.get('risk.sizing_mode') == 'atr'

    def test_load_config_with_env_vars(self, tmp_path):
        """Test loading config with environment variable interpolation"""
        os.environ['TEST_DB_HOST'] = 'testhost'
        os.environ['TEST_DB_PORT'] = '5555'

        config_str = """
system:
  name: SixBTC
  version: 1.0.0
  execution_mode: sync
timeframes: [15m, 30m]
risk:
  sizing_mode: atr
database:
  host: ${TEST_DB_HOST}
  port: ${TEST_DB_PORT}
  database: sixbtc
"""

        config_file = tmp_path / "config.yaml"
        with open(config_file, 'w') as f:
            f.write(config_str)

        # Load config
        config = load_config(config_file)

        assert config.get('database.host') == 'testhost'
        assert config.get('database.port') == 5555  # YAML converts to int

        # Cleanup
        del os.environ['TEST_DB_HOST']
        del os.environ['TEST_DB_PORT']

    def test_load_config_missing_file_raises(self):
        """Test loading missing config file raises FileNotFoundError"""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config("nonexistent_config.yaml")

    def test_load_config_invalid_yaml_raises(self, tmp_path):
        """Test loading invalid YAML raises error"""
        config_file = tmp_path / "invalid.yaml"
        with open(config_file, 'w') as f:
            f.write("invalid: yaml: syntax: here")

        with pytest.raises(yaml.YAMLError):
            load_config(config_file)

    def test_load_config_missing_env_var_raises(self, tmp_path):
        """Test loading config with missing env var raises error"""
        config_str = """
system:
  name: SixBTC
  version: 1.0.0
  execution_mode: sync
timeframes: [15m]
risk:
  sizing_mode: atr
database:
  host: ${MISSING_ENV_VAR}
  port: 5432
  database: sixbtc
"""

        config_file = tmp_path / "config.yaml"
        with open(config_file, 'w') as f:
            f.write(config_str)

        with pytest.raises(ValueError, match="Environment variable 'MISSING_ENV_VAR' is required"):
            load_config(config_file)


class TestConfigEdgeCases:
    """Test edge cases and error handling"""

    def test_get_deeply_nested_value(self):
        """Test getting deeply nested config value"""
        config_data = {
            'level1': {
                'level2': {
                    'level3': {
                        'level4': 'deep_value'
                    }
                }
            }
        }
        config = Config(**config_data)

        assert config.get('level1.level2.level3.level4') == 'deep_value'

    def test_get_with_none_value(self):
        """Test get returns None value correctly"""
        config_data = {'key': None}
        config = Config(**config_data)

        # Should return None, not default
        assert config.get('key', 'default') is None

    def test_get_list_element_returns_list(self):
        """Test get returns list as-is, not individual elements"""
        config_data = {
            'strategies': ['MOM', 'REV', 'TRN']
        }
        config = Config(**config_data)

        result = config.get('strategies')
        assert result == ['MOM', 'REV', 'TRN']
        assert isinstance(result, list)

    def test_empty_config(self):
        """Test empty config doesn't crash"""
        config = Config(**{})

        assert config.get('any.key', 'default') == 'default'
