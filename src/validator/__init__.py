"""
Validator Module for SixBTC

4-phase validation pipeline:
1. SyntaxValidator - Python syntax check
2. LookaheadDetector - AST analysis for lookahead bias
3. ShuffleTester - Empirical shuffle test
4. ExecutionValidator - Runtime execution test

Usage:
    from src.validator import FullValidator

    validator = FullValidator()
    result = validator.validate(strategy_code, test_data)

    if result.passed:
        # Strategy is valid
    else:
        # Strategy failed validation
"""

from .syntax_validator import SyntaxValidator
from .lookahead_detector import LookaheadDetector
from .shuffle_test import ShuffleTester
from .execution_validator import ExecutionValidator

__all__ = [
    "SyntaxValidator",
    "LookaheadDetector",
    "ShuffleTester",
    "ExecutionValidator",
]
