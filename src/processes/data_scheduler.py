#!/usr/bin/env python3
"""
Data Scheduler Process Entry Point

Scheduled updates for trading pairs and historical data.
Runs at 02:00 and 14:00 UTC.

Uses APScheduler for cron-like scheduling.
"""

import os
import sys
import signal

# Path setup BEFORE imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Signal handlers BEFORE heavy imports
_shutdown_requested = False


def _early_signal_handler(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    print(f"\nReceived signal {signum}, stopping...", flush=True)
    os._exit(0)


signal.signal(signal.SIGINT, _early_signal_handler)
signal.signal(signal.SIGTERM, _early_signal_handler)


if __name__ == "__main__":
    from src.data.data_scheduler import DataScheduler

    scheduler = DataScheduler()
    scheduler.run()
