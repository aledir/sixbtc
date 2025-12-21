"""
Configuration module for SixBTC

Provides unified configuration loading from:
1. config/config.yaml (master configuration)
2. .env file (sensitive credentials)
3. Environment variables (override)
"""

from .loader import load_config, Config

__all__ = ["load_config", "Config"]
