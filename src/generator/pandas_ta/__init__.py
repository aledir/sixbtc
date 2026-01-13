"""
Pandas-TA Strategy Generator

Generates diversified trading strategies using pandas_ta indicators.

Features:
- 50+ indicators across 5 categories
- Compatibility matrices for sensible combinations
- 1-3 indicators per strategy (max to avoid overfitting)
- Reused exit mechanisms from Unger (11 logics)
- Market regime awareness (TREND/REVERSAL)
- ~158 million possible unique strategies

Usage:
    from src.generator.pandas_ta import PandasTaGenerator, PtaGeneratedStrategy

    generator = PandasTaGenerator(config)
    strategies = generator.generate(
        timeframe='15m',
        direction='LONG',
        regime_type='TREND',
        count=10,
    )
"""

from .generator import PandasTaGenerator, PtaGeneratedStrategy
from .composer import PtaBlueprint, PtaComposer, PtaEntryCondition

__all__ = [
    # Main classes
    "PandasTaGenerator",
    "PtaGeneratedStrategy",
    # Composer
    "PtaBlueprint",
    "PtaComposer",
    "PtaEntryCondition",
]
