"""
Config API routes

GET /api/config - Get current configuration (sanitized, no secrets)
GET /api/config/thresholds - Get key thresholds
"""
from typing import Any, Dict

from fastapi import APIRouter

from src.config import load_config
from src.api.schemas import ConfigResponse
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Keys to redact from config (contain sensitive data)
REDACTED_KEYS = {
    "api_key",
    "api_secret",
    "secret",
    "password",
    "private_key",
    "wallet_key",
    "token",
}


def sanitize_config(config: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
    """
    Remove sensitive keys from config.

    Recursively walks config dict and redacts sensitive values.
    """
    if depth > 10:  # Prevent infinite recursion
        return config

    sanitized = {}

    for key, value in config.items():
        key_lower = str(key).lower()

        # Check if key contains sensitive words
        is_sensitive = any(redacted in key_lower for redacted in REDACTED_KEYS)

        if is_sensitive:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_config(value, depth + 1)
        elif isinstance(value, list):
            # Handle lists that might contain dicts
            sanitized[key] = [
                sanitize_config(item, depth + 1) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """
    Get current system configuration.

    Sensitive values (API keys, secrets) are redacted.
    """
    try:
        config = load_config()._raw_config
        sanitized = sanitize_config(config)
        return ConfigResponse(config=sanitized)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return ConfigResponse(config={"error": str(e)})


@router.get("/config/thresholds")
async def get_thresholds():
    """
    Get key threshold values from config.

    Returns a simplified view of important thresholds
    for display in the dashboard.
    """
    try:
        config = load_config()._raw_config

        # Extract key thresholds from correct paths
        backtesting = config.get("backtesting", {})
        backtest_thresholds = backtesting.get("thresholds", {})
        risk = config.get("risk", {})
        trading = config.get("trading", {})

        return {
            "backtest": {
                "min_sharpe": backtest_thresholds.get("min_sharpe"),
                "min_win_rate": backtest_thresholds.get("min_win_rate"),
                "max_drawdown": backtest_thresholds.get("max_drawdown"),
                "min_trades": backtest_thresholds.get("min_total_trades"),
                "lookback_days": backtesting.get("is_days"),  # In-sample days
            },
            "risk": {
                "risk_per_trade_pct": risk.get("fixed_fractional", {}).get("risk_per_trade_pct"),
                "max_position_size_pct": risk.get("fixed_fractional", {}).get("max_position_size_pct"),
                "max_open_positions": risk.get("limits", {}).get("max_open_positions_per_subaccount"),
                "max_leverage": None,  # Not configured in config.yaml
            },
            "emergency": {
                "max_portfolio_drawdown": risk.get("emergency", {}).get("max_portfolio_drawdown"),
                "max_subaccount_drawdown": risk.get("emergency", {}).get("max_subaccount_drawdown"),
                "max_daily_loss": risk.get("emergency", {}).get("max_daily_loss"),
            },
            "trading": {
                "timeframes": config.get("timeframes"),  # Top-level, not under trading
                "strategy_types": trading.get("strategy_types"),
            },
        }
    except Exception as e:
        logger.error(f"Error getting thresholds: {e}")
        return {"error": str(e)}
