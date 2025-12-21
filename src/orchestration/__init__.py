"""
SixBTC Orchestration Module

Manages the execution of multiple trading strategies across timeframes.
Includes multi-WebSocket data provider, adaptive scheduler, and main orchestrator.
"""

from src.orchestration.websocket_provider import MultiWebSocketDataProvider
from src.orchestration.adaptive_scheduler import AdaptiveScheduler
from src.orchestration.orchestrator import Orchestrator

__all__ = [
    'MultiWebSocketDataProvider',
    'AdaptiveScheduler',
    'Orchestrator',
]
