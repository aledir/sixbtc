"""
SixBTC Process Entry Points

Thin wrappers for Supervisor-managed processes.
Each module sets up signal handlers BEFORE heavy imports.

Usage with Supervisor:
    command=/path/to/python -u /path/to/src/processes/generator.py

Direct usage:
    python -m src.processes.generator
"""
