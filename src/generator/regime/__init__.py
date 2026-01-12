"""
Regime Detection Module (Unger Method)

Analyzes market regime using simple breakout vs reversal tests.
Used by the Unger Generator to create regime-coherent strategies.

Components:
- RegimeDetector: Calculates regime for each coin
- RegimeResult: Dataclass with regime analysis results
- UngerPatterns: 60 price action patterns for entry filtering

Models:
- MarketRegime: Database model for persisting regime data
"""

from src.generator.regime.detector import RegimeDetector, RegimeResult
from src.generator.regime.unger_patterns import UngerPatterns

__all__ = ['RegimeDetector', 'RegimeResult', 'UngerPatterns']
