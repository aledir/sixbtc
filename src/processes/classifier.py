#!/usr/bin/env python3
"""
Classifier Process Entry Point

Scores and selects top strategies for live trading.
Supervisor-managed continuous process.
"""

import os
import sys
import signal

# Path setup BEFORE any other imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Signal handlers BEFORE heavy imports
_shutdown_requested = False


def _early_signal_handler(signum, frame):
    """Handle signals immediately during import phase"""
    global _shutdown_requested
    _shutdown_requested = True
    print(f"\nReceived signal {signum}, stopping...", flush=True)
    os._exit(0)


signal.signal(signal.SIGINT, _early_signal_handler)
signal.signal(signal.SIGTERM, _early_signal_handler)


def main():
    """Main entry point"""
    if _shutdown_requested:
        return

    from src.classifier.main_continuous import ContinuousClassifierProcess

    process = ContinuousClassifierProcess()
    process.run()


if __name__ == "__main__":
    main()
