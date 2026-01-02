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


# Map service names to log files
SERVICE_LOG_FILES = {
    "generator": "logs/generator.log",
    "backtester": "logs/backtester.log",
    "validator": "logs/validator.log",
    "executor": "logs/executor.log",
    "monitor": "logs/monitor.log",
    "scheduler": "logs/scheduler.log",
    "data": "logs/data.log",
    "api": "logs/api.log",
}

# Log level order for filtering
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def parse_log_line(line: str) -> Optional[LogLine]:
    """
    Parse a log line into structured format.

    Expected format: "2025-01-02 14:32:15 INFO     src.generator.main: Message here"

    Returns None if line doesn't match expected format.
    """
    # Pattern: timestamp level logger: message
    pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\w+)\s+(\S+):\s*(.*)$'
    match = re.match(pattern, line)

    if not match:
        return None

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
