#!/usr/bin/env python3
"""
Generator Process Entry Point

Generates new trading strategies using AI.
Supervisor-managed continuous process.
"""

import os
import sys
import signal

# Path setup BEFORE any other imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Signal handlers BEFORE heavy imports (prevents hanging on SIGTERM during import)
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

    # Now safe to do heavy imports
    from src.generator.main_continuous import ContinuousGeneratorProcess

    process = ContinuousGeneratorProcess()
    process.run()


if __name__ == "__main__":
    main()
