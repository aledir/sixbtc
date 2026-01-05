"""
DEPRECATED: This module has been replaced by:
- SCORER module (src/scorer/) - scoring logic
- ROTATOR module (src/rotator/) - selection and deployment

Do NOT use this module for new code. It exists only for reference.
"""

import warnings

warnings.warn(
    "classifier module is deprecated. Use scorer and rotator modules instead.",
    DeprecationWarning,
    stacklevel=2
)

# Legacy imports for backwards compatibility only
from src.classifier.scorer import StrategyScorer
from src.classifier.portfolio_builder import PortfolioBuilder
from src.classifier.live_scorer import LiveScorer
from src.classifier.dual_ranker import DualRanker

__all__ = [
    'StrategyScorer',
    'PortfolioBuilder',
    'LiveScorer',
    'DualRanker',
]
