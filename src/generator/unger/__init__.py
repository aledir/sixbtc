"""
Unger Generator v2 - Diversified Strategy Factory

Generates millions of unique trading strategies using:
- 68 Entry Conditions (7 categories)
- 32 Entry Filters (5 categories with compatibility rules)
- 15 Exit Conditions
- 5 SL Types + 5 TP Types + 6 Trailing Configs
- 11 Exit Mechanisms (TP/EC/TS with AND/OR logic)
- 4 Timeframes x 3 Directions

Total: ~15-30 million base strategies
"""

from .generator import UngerGenerator, UngerGeneratedStrategy
from .composer import StrategyBlueprint, StrategyComposer

__all__ = [
    "UngerGenerator",
    "UngerGeneratedStrategy",
    "StrategyBlueprint",
    "StrategyComposer",
]
