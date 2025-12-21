"""
Logging system for SixBTC

Provides unified logging across all modules with:
- File rotation
- Per-module log levels
- Structured output (no emojis - ASCII only)
- Console + file output
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


def setup_logging(
    log_file: str = "logs/sixbtc.log",
    log_level: str = "INFO",
    max_bytes: int = 10_485_760,  # 10MB
    backup_count: int = 5,
    module_levels: Optional[dict] = None
) -> logging.Logger:
    """
    Setup SixBTC logging system

    Args:
        log_file: Path to log file
        log_level: Default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Max size per log file before rotation
        backup_count: Number of backup files to keep
        module_levels: Per-module log levels (e.g. {'orchestrator': 'DEBUG'})

    Returns:
        Root logger instance

    Example:
        >>> from src.utils import setup_logging, get_logger
        >>> setup_logging(log_level='INFO')
        >>> logger = get_logger(__name__)
        >>> logger.info("System started")
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything, filter in handlers

    # Remove existing handlers (if any)
    root_logger.handlers.clear()

    # =========================================================================
    # FILE HANDLER (All logs → file)
    # =========================================================================
    file_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # =========================================================================
    # CONSOLE HANDLER (Rich output for terminal)
    # =========================================================================
    console = Console()
    console_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        show_time=False,  # Time already in file logs
        show_path=False   # Clean console output
    )
    console_handler.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(console_handler)

    # =========================================================================
    # PER-MODULE LOG LEVELS
    # =========================================================================
    if module_levels:
        for module_name, level in module_levels.items():
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(getattr(logging, level.upper()))

    # =========================================================================
    # SILENCE NOISY LIBRARIES
    # =========================================================================
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('websockets').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)

    # Log successful setup
    logger = get_logger("sixbtc.setup")
    logger.info(f"Logging system initialized - Log file: {log_file}")
    logger.info(f"Log level: {log_level} | File rotation: {max_bytes} bytes | Backups: {backup_count}")

    if module_levels:
        logger.debug(f"Per-module log levels: {module_levels}")

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance for a module

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
        >>> logger.error("Failed to connect", exc_info=True)
    """
    return logging.getLogger(name)


# Convenience function for testing
if __name__ == "__main__":
    """Test logging system"""
    from src.config import load_config

    # Load config
    config = load_config()

    # Setup logging from config
    setup_logging(
        log_file=config.get('logging.file', 'logs/sixbtc.log'),
        log_level=config.get('logging.level', 'INFO'),
        max_bytes=config.get('logging.max_bytes', 10485760),
        backup_count=config.get('logging.backup_count', 5),
        module_levels=config.get('logging.modules')
    )

    # Test logging
    logger = get_logger("sixbtc.test")
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")

    # Test per-module logger
    orchestrator_logger = get_logger("orchestrator")
    orchestrator_logger.info("Orchestrator log message")

    data_provider_logger = get_logger("data_provider")
    data_provider_logger.warning("Data provider warning (should be visible)")
    data_provider_logger.debug("Data provider debug (may be filtered)")

    print("\n" + "="*60)
    print("Logging test complete - check logs/sixbtc.log")
    print("="*60)
