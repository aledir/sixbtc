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

Genetic evolution: Evolves ACTIVE unger strategies via crossover/mutation
Output: UggStrat_{type}_{hash}, generation_mode="unger_genetic"
"""

from .generator import UngerGenerator, UngerGeneratedStrategy
from .composer import StrategyBlueprint, StrategyComposer
from .genetic_generator import GeneticUngerGenerator, UngerGeneticResult
from .genetic_operators import UngerGeneticIndividual

__all__ = [
    "UngerGenerator",
    "UngerGeneratedStrategy",
    "StrategyBlueprint",
    "StrategyComposer",
    "GeneticUngerGenerator",
    "UngerGeneticResult",
    "UngerGeneticIndividual",
]
