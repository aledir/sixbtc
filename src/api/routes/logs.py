"""
Logs API routes

GET /api/logs/{service} - Get log lines for a service
"""
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import LogLine, LogsResponse
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Project root directory (for absolute paths)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Map service names to log files (absolute paths)
SERVICE_LOG_FILES = {
    "executor": str(PROJECT_ROOT / "logs/executor.log"),
    "generator": str(PROJECT_ROOT / "logs/generator.log"),
    "backtester": str(PROJECT_ROOT / "logs/backtester.log"),
    "validator": str(PROJECT_ROOT / "logs/validator.log"),
    "rotator": str(PROJECT_ROOT / "logs/rotator.log"),
    "monitor": str(PROJECT_ROOT / "logs/monitor.log"),
    "metrics": str(PROJECT_ROOT / "logs/metrics.log"),
    "scheduler": str(PROJECT_ROOT / "logs/scheduler.log"),
    "api": str(PROJECT_ROOT / "logs/api.log"),
    "frontend": str(PROJECT_ROOT / "logs/frontend.log"),
    "subaccount": str(PROJECT_ROOT / "logs/subaccount.log"),
}

# Log level order for filtering
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def parse_log_line(line: str) -> Optional[LogLine]:
    """
    Parse a log line into structured format.

    Supports multiple log formats:
    1. Standard: "2025-01-02 14:32:15 INFO     src.generator.main: Message"
    2. Metrics: "2025-01-02 14:32:15,123 - __main__ - INFO - Message"
    3. API: "2025-01-02 14:32:15 - src.api.routes - INFO - Message"
    4. Uvicorn: "INFO:     127.0.0.1:1234 - \"GET /api/...\" 200 OK"

    Returns None if line doesn't match expected format.
    """
    # Try multiple patterns with named groups for clarity
    # Pattern 1: Standard format - timestamp level logger: message
    match = re.match(
        r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\w+)\s+(\S+):\s*(.*)$',
        line
    )
    if match:
        try:
            timestamp_str, level, logger_name, message = match.groups()
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return LogLine(
                timestamp=timestamp,
                level=level.upper(),
                logger=logger_name,
                message=message,
            )
        except (ValueError, AttributeError):
            pass

    # Pattern 2: Metrics/API format - timestamp - logger - level - message
    match = re.match(
        r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),?\d*\s+-\s+(\S+)\s+-\s+(\w+)\s+-\s*(.*)$',
        line
    )
    if match:
        try:
            timestamp_str, logger_name, level, message = match.groups()
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return LogLine(
                timestamp=timestamp,
                level=level.upper(),
                logger=logger_name,
                message=message,
            )
        except (ValueError, AttributeError):
            pass

    # Pattern 3: Uvicorn format - LEVEL:     message
    match = re.match(r'^(\w+):\s+(.*)$', line)
    if match:
        level, message = match.groups()
        level_upper = level.upper()
        return LogLine(
            timestamp=datetime.now(),
            level=level_upper if level_upper in LOG_LEVELS else "INFO",
            logger="uvicorn",
            message=message,
        )

    return None


def read_log_file(
    filepath: str,
    lines: int = 500,
    level: Optional[str] = None,
    search: Optional[str] = None,
) -> List[LogLine]:
    """
    Read and parse log file.

    Args:
        filepath: Path to log file
        lines: Max lines to return
        level: Minimum log level to include
        search: Search string to filter

    Returns:
        List of LogLine objects (newest first)
    """
    path = Path(filepath)
    if not path.exists():
        return []

    # Determine minimum level index
    min_level_idx = 0
    if level:
        level = level.upper()
        if level in LOG_LEVELS:
            min_level_idx = LOG_LEVELS.index(level)

    parsed_lines = []

    try:
        # Read file from end (tail behavior)
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            # Read all lines and take last N
            all_lines = f.readlines()
            # Process in reverse order (newest first)
            for line in reversed(all_lines):
                line = line.strip()
                if not line:
                    continue

                parsed = parse_log_line(line)
                if not parsed:
                    continue

                # Filter by level
                if parsed.level in LOG_LEVELS:
                    line_level_idx = LOG_LEVELS.index(parsed.level)
                    if line_level_idx < min_level_idx:
                        continue

                # Filter by search term
                if search:
                    search_lower = search.lower()
                    if search_lower not in parsed.message.lower() and search_lower not in parsed.logger.lower():
                        continue

                parsed_lines.append(parsed)

                if len(parsed_lines) >= lines:
                    break

    except Exception as e:
        logger.error(f"Error reading log file {filepath}: {e}")

    return parsed_lines


@router.get("/logs/{service}", response_model=LogsResponse)
async def get_service_logs(
    service: str,
    lines: int = Query(500, ge=1, le=5000, description="Number of lines to return"),
    level: Optional[str] = Query(None, description="Minimum log level (DEBUG, INFO, WARNING, ERROR)"),
    search: Optional[str] = Query(None, description="Search filter"),
):
    """
    Get log lines for a specific service.

    Returns newest lines first.
    """
    if service not in SERVICE_LOG_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service. Valid services: {', '.join(SERVICE_LOG_FILES.keys())}"
        )

    # Validate level
    if level and level.upper() not in LOG_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level. Valid levels: {', '.join(LOG_LEVELS)}"
        )

    log_file = SERVICE_LOG_FILES[service]
    log_lines = read_log_file(log_file, lines=lines, level=level, search=search)

    return LogsResponse(
        service=service,
        lines=log_lines,
        total_lines=len(log_lines),
    )


@router.get("/logs")
async def list_available_logs():
    """
    List available log services and their file status.
    """
    result = {}
    for service, filepath in SERVICE_LOG_FILES.items():
        path = Path(filepath)
        if path.exists():
            stat = path.stat()
            result[service] = {
                "file": filepath,
                "exists": True,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        else:
            result[service] = {
                "file": filepath,
                "exists": False,
                "size_bytes": 0,
                "modified": None,
            }

    return result
