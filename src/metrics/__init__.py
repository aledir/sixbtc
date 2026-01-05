"""
Metrics Collection Module

Collects and stores pipeline metrics snapshots for historical analysis.
"""

# Lazy import to avoid RuntimeWarning when running with python -m
def __getattr__(name):
    if name == 'MetricsCollector':
        from .collector import MetricsCollector
        return MetricsCollector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ['MetricsCollector']
