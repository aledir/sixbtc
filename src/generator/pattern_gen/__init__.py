"""
Pattern Generator Module (pattern_gen)

Internal pattern-based strategy generator inspired by pattern-discovery.

Phase 1 - Smart Generation:
- 50% Parametric: RSI thresholds, EMA periods, etc.
- 30% Template: Combine 2-3 building blocks
- 20% Innovative: Sequential, statistical, volatility patterns
- Output: PGnStrat_{type}_{hash}

Phase 2 - Genetic Evolution:
- Pool: ACTIVE strategies with score >= min_pool_score
- Fitness: Backtest score (deferred)
- Operators: Tournament selection, crossover, mutation
- Output: PGgStrat_{type}_{hash}

Database field: generation_mode = "pattern_gen"
"""

from src.generator.pattern_gen.generator import PatternGenGenerator, PatternGenResult
from src.generator.pattern_gen.genetic_generator import GeneticPatternGenerator, GeneticResult

__all__ = [
    'PatternGenGenerator',
    'PatternGenResult',
    'GeneticPatternGenerator',
    'GeneticResult',
]
