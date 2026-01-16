"""
Config API routes

GET /api/config - Get current configuration (sanitized, no secrets)
GET /api/config/thresholds - Get key thresholds
GET /api/config/yaml - Get raw YAML config with comments (for editing)
PUT /api/config/yaml - Update config from YAML (preserves comments)
GET /api/config/sections - Get list of config sections
"""
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.config import load_config
from src.api.schemas import ConfigResponse
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Config file path
CONFIG_PATH = Path("config/config.yaml")


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


# ==============================================================================
# YAML CONFIG ENDPOINTS (with comment preservation)
# ==============================================================================

class ConfigYamlResponse(BaseModel):
    """Response for YAML config endpoint"""
    yaml_content: str
    sections: List[str]
    line_count: int


class ConfigYamlUpdateRequest(BaseModel):
    """Request for updating YAML config"""
    yaml_content: str


class ConfigYamlUpdateResponse(BaseModel):
    """Response after updating YAML config"""
    success: bool
    message: str
    line_count: int


def extract_sections_from_yaml(content: str) -> List[str]:
    """
    Extract top-level section names from YAML content.

    Looks for patterns like:
    # ==============================================================================
    # SECTION NAME (optional description)
    # ==============================================================================
    """
    import re
    sections = []

    # Pattern: ===+ line, then section header starting with uppercase,
    # then another ===+ line
    # Allow any characters in the section name except newline
    pattern = r'^# ={5,}\n# ([A-Z][^\n]+)\n# ={5,}'
    matches = re.findall(pattern, content, re.MULTILINE)

    for match in matches:
        # Clean up section name
        section = match.strip()
        if section and section not in sections:
            sections.append(section)

    return sections


def redact_sensitive_yaml(content: str) -> str:
    """
    Redact sensitive values in YAML content while preserving structure.

    Replaces values for keys containing sensitive terms.
    """
    import re

    lines = content.split('\n')
    redacted_lines = []

    for line in lines:
        # Check if line contains a sensitive key
        for key in REDACTED_KEYS:
            # Match patterns like "  api_key: value" or "  password: value"
            pattern = rf'^(\s*{key}\s*:\s*)(.+)$'
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                # Replace value with [REDACTED] while keeping comments
                prefix = match.group(1)
                value = match.group(2)
                # Preserve inline comments
                if '#' in value:
                    comment_idx = value.index('#')
                    comment = value[comment_idx:]
                    line = f"{prefix}[REDACTED] {comment}"
                else:
                    line = f"{prefix}[REDACTED]"
                break

        # Also redact ${VAR} style environment references
        line = re.sub(r'\$\{[A-Z_]+\}', '[ENV_VAR]', line)

        redacted_lines.append(line)

    return '\n'.join(redacted_lines)


@router.get("/config/yaml", response_model=ConfigYamlResponse)
async def get_config_yaml():
    """
    Get raw YAML config file content with comments preserved.

    Sensitive values are redacted for security.
    Returns the full YAML with structure and comments intact.
    """
    try:
        if not CONFIG_PATH.exists():
            raise HTTPException(status_code=404, detail="Config file not found")

        # Read raw YAML content
        content = CONFIG_PATH.read_text(encoding='utf-8')

        # Redact sensitive values
        redacted_content = redact_sensitive_yaml(content)

        # Extract sections
        sections = extract_sections_from_yaml(content)

        return ConfigYamlResponse(
            yaml_content=redacted_content,
            sections=sections,
            line_count=len(content.split('\n'))
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading config YAML: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/yaml", response_model=ConfigYamlUpdateResponse)
async def update_config_yaml(request: ConfigYamlUpdateRequest):
    """
    Update config YAML file with new content.

    Uses ruamel.yaml to validate YAML syntax before saving.
    Preserves comments in the new content.

    WARNING: This modifies the live configuration file!
    """
    try:
        from ruamel.yaml import YAML

        yaml = YAML()
        yaml.preserve_quotes = True

        # Validate YAML syntax by parsing
        try:
            from io import StringIO
            parsed = yaml.load(StringIO(request.yaml_content))
            if parsed is None:
                raise HTTPException(status_code=400, detail="YAML content is empty")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML syntax: {e}")

        # Check for [REDACTED] values - don't allow saving with redacted content
        if '[REDACTED]' in request.yaml_content or '[ENV_VAR]' in request.yaml_content:
            raise HTTPException(
                status_code=400,
                detail="Cannot save config with [REDACTED] or [ENV_VAR] placeholders. "
                       "Please restore original values or use ${ENV_VAR} syntax."
            )

        # Backup current config
        backup_path = CONFIG_PATH.with_suffix('.yaml.bak')
        if CONFIG_PATH.exists():
            import shutil
            shutil.copy(CONFIG_PATH, backup_path)
            logger.info(f"Created backup at {backup_path}")

        # Write new content
        CONFIG_PATH.write_text(request.yaml_content, encoding='utf-8')

        # Clear config cache to reload on next access
        from src.config.loader import _cached_config
        import src.config.loader
        src.config.loader._cached_config = None

        logger.info("Config file updated successfully")

        return ConfigYamlUpdateResponse(
            success=True,
            message="Configuration updated successfully. Restart services to apply changes.",
            line_count=len(request.yaml_content.split('\n'))
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating config YAML: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/sections")
async def get_config_sections() -> List[str]:
    """
    Get list of configuration sections.

    Returns section names extracted from YAML comments.
    """
    try:
        if not CONFIG_PATH.exists():
            raise HTTPException(status_code=404, detail="Config file not found")

        content = CONFIG_PATH.read_text(encoding='utf-8')
        sections = extract_sections_from_yaml(content)

        return sections

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting config sections: {e}")
        raise HTTPException(status_code=500, detail=str(e))
