"""
Configuration Loader for SixBTC

Loads configuration from YAML file with environment variable interpolation.
Follows Fast Fail principle - crashes immediately if config is invalid.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator


class Config(BaseModel):
    """
    Master configuration model for SixBTC

    All values are REQUIRED - no fallback defaults!
    Missing or invalid config will cause system to crash at startup (Fast Fail)
    """

    # Raw config data (loaded from YAML)
    _raw_config: Dict[str, Any] = {}

    class Config:
        """Pydantic config"""
        arbitrary_types_allowed = True
        extra = "allow"  # Allow extra fields from YAML

    def __init__(self, **data):
        """Initialize with raw config data"""
        super().__init__(**data)
        self._raw_config = data

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get nested config value using dot notation

        Example:
            config.get('risk.atr.stop_multiplier')  # Returns 2.0
            config.get('timeframes')  # Returns ['15m', '30m', ...]

        Args:
            key_path: Dot-separated path to config key
            default: Default value if key not found

        Returns:
            Config value or default
        """
        keys = key_path.split('.')
        value = self._raw_config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_required(self, key_path: str) -> Any:
        """
        Get required config value - raises error if missing

        Args:
            key_path: Dot-separated path to config key

        Returns:
            Config value

        Raises:
            ValueError: If key not found
        """
        value = self.get(key_path)
        if value is None:
            raise ValueError(f"Required config key not found: {key_path}")
        return value


def _interpolate_env_vars(config_str: str) -> str:
    """
    Replace ${VAR_NAME} placeholders with environment variables

    Supports:
    - ${VAR_NAME} - Required, crashes if missing
    - ${VAR_NAME:-} - Optional, empty string if missing
    - ${VAR_NAME:-default} - Optional, uses default if missing

    Args:
        config_str: YAML config as string

    Returns:
        Config string with env vars interpolated

    Raises:
        ValueError: If required env var is missing
    """
    # Pattern matches: ${VAR} or ${VAR:-} or ${VAR:-default}
    pattern = re.compile(r'\$\{(\w+)(:-([^}]*))?\}')

    def replacer(match):
        var_name = match.group(1)
        has_default = match.group(2) is not None
        default_value = match.group(3) if match.group(3) else ""

        value = os.getenv(var_name)

        if value is None:
            if has_default:
                return default_value
            else:
                raise ValueError(
                    f"Environment variable '{var_name}' is required but not set. "
                    f"Check your .env file or environment."
                )

        return value

    return pattern.sub(replacer, config_str)


def get_master_address() -> str:
    """
    Get Hyperliquid master wallet address from environment.

    Returns:
        Master wallet address (e.g., 0x4dA0047...)

    Raises:
        ValueError: If HL_MASTER_ADDRESS not set (Fast Fail)
    """
    address = os.getenv('HL_MASTER_ADDRESS')
    if not address:
        raise ValueError(
            "HL_MASTER_ADDRESS environment variable not set. "
            "Add your master wallet address to .env"
        )
    return address


def get_master_private_key() -> str:
    """
    Get Hyperliquid master wallet private key from environment.

    WARNING: This returns a sensitive value. Handle with care!

    Returns:
        Master wallet private key (64 hex chars after 0x)

    Raises:
        ValueError: If HL_MASTER_PRIVATE_KEY not set (Fast Fail)
    """
    private_key = os.getenv('HL_MASTER_PRIVATE_KEY')
    if not private_key:
        raise ValueError(
            "HL_MASTER_PRIVATE_KEY environment variable not set. "
            "Add your master wallet private key to .env"
        )
    return private_key


# Global config cache to avoid duplicate loads and prints
_cached_config: Config | None = None


def load_config(config_path: str | Path = "config/config.yaml") -> Config:
    """
    Load SixBTC configuration from YAML file (cached)

    Process:
    1. Return cached config if available
    2. Load .env file (if exists)
    3. Read YAML config
    4. Interpolate environment variables (${VAR})
    5. Parse and validate YAML
    6. Cache and return Config object

    Args:
        config_path: Path to YAML config file

    Returns:
        Config object with loaded configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid or env vars missing
        yaml.YAMLError: If YAML parsing fails

    Example:
        >>> from src.config import load_config
        >>> config = load_config()
        >>> config.get('risk.atr.stop_multiplier')
        2.0
        >>> config.get('timeframes')
        ['15m', '30m', '1h', '4h', '1d']
    """
    global _cached_config

    # Return cached config if available
    if _cached_config is not None:
        return _cached_config

    # 1. Load .env file (if exists)
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)

    # 2. Read YAML config
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Expected location: {config_path.absolute()}"
        )

    with open(config_path, 'r') as f:
        config_str = f.read()

    # 3. Interpolate environment variables
    try:
        config_str = _interpolate_env_vars(config_str)
    except ValueError as e:
        raise ValueError(
            f"Failed to interpolate environment variables in {config_path}: {e}"
        ) from e

    # 4. Parse YAML
    try:
        config_dict = yaml.safe_load(config_str)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(
            f"Failed to parse YAML config {config_path}: {e}"
        ) from e

    if not isinstance(config_dict, dict):
        raise ValueError(
            f"Config file {config_path} must contain a YAML dictionary, "
            f"got {type(config_dict)}"
        )

    # 5. Create Config object
    config = Config(**config_dict)

    # 6. Validate critical settings (Fast Fail)
    _validate_config(config)

    # 7. Cache for future calls
    _cached_config = config

    return config


def _validate_config(config: Config) -> None:
    """
    Validate critical configuration settings

    Raises ValueError if any critical settings are invalid.
    This ensures Fast Fail principle - crash early if config is broken.

    Args:
        config: Loaded configuration

    Raises:
        ValueError: If validation fails
    """
    # Validate global timeframes
    timeframes = config.get('timeframes')
    if not timeframes or not isinstance(timeframes, list):
        raise ValueError(
            "timeframes must be a non-empty list at root level"
        )

    valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '8h', '12h', '1d']
    for tf in timeframes:
        if tf not in valid_timeframes:
            raise ValueError(
                f"Invalid timeframe '{tf}' in timeframes. "
                f"Valid options: {valid_timeframes}"
            )

    # Validate database config
    db_host = config.get('database.host')
    db_port = config.get('database.port')
    db_name = config.get('database.database')

    if not all([db_host, db_port, db_name]):
        raise ValueError(
            "Database configuration incomplete. Required: host, port, database"
        )

    # Validate execution mode
    exec_mode = config.get('system.execution_mode')
    if exec_mode not in ['sync', 'async', 'multiprocess', 'hybrid']:
        raise ValueError(
            f"system.execution_mode must be one of "
            f"['sync', 'async', 'multiprocess', 'hybrid'], got '{exec_mode}'"
        )

    # Validation passed - logging handled by caller


# Convenience function for quick testing
if __name__ == "__main__":
    """Quick test of config loader"""
    try:
        config = load_config()
        print("\n" + "="*60)
        print("CONFIGURATION LOADED SUCCESSFULLY")
        print("="*60)
        print(f"\nSystem: {config.get('system.name')} v{config.get('system.version')}")
        print(f"Timeframes: {config.get('timeframes')}")
        print(f"Risk per trade: {config.get('risk.fixed_fractional.risk_per_trade_pct')}")
        print(f"Execution mode: {config.get('system.execution_mode')}")
        print(f"\nDatabase: {config.get('database.host')}:{config.get('database.port')}")
        print(f"Database name: {config.get('database.database')}")
        print("\n" + "="*60)
    except Exception as e:
        print(f"\n[ERROR] Configuration loading failed:")
        print(f"   {e}")
        raise
