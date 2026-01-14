"""
Validator Module for SixBTC

Pre-backtest validation (3 phases):
1. SyntaxValidator - Python syntax check
2. LookaheadDetector - AST analysis for lookahead bias
3. ExecutionValidator - Runtime execution test

Post-backtest validation (run by backtester for high-scoring strategies):
4. ShuffleTester - Empirical shuffle test for lookahead detection

Usage:
    from src.validator import SyntaxValidator, LookaheadDetector, ExecutionValidator

    # Pre-backtest validation
    syntax_result = SyntaxValidator().validate(code)
    lookahead_result = LookaheadDetector().detect(code)
    exec_result = ExecutionValidator().validate(strategy_instance, test_data)
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
