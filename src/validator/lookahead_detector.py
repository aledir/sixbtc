"""
Lookahead Detector - Phase 2 of validation pipeline

AST-based static code analysis to detect lookahead bias patterns:
- rolling(center=True)
- shift(-N) with negative values
- expanding(center=True)
- Future data access patterns
"""

import ast
from dataclasses import dataclass
from typing import List, Tuple

from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class LookaheadValidationResult:
    """Result of lookahead detection"""
    passed: bool
    violations: List[str]
    patterns_checked: int


class LookaheadDetector:
    """
    Phase 2: Static AST analysis for lookahead bias

    Detects code patterns that use future data, which would cause
    unrealistic backtest results that don't translate to live trading.
    """

    # Pattern descriptions for logging
    PATTERN_DESCRIPTIONS = {
        'rolling_center': "rolling(center=True) uses future data in window calculation",
        'shift_negative': "shift(-N) accesses future data points",
        'expanding_center': "expanding(center=True) uses future data",
        'iloc_negative': "iloc[-N] with N > 1 may access future data in loops",
    }

    def validate(self, code: str) -> LookaheadValidationResult:
        """
        Detect lookahead bias patterns in strategy code.

        Args:
            code: Python source code string

        Returns:
            LookaheadValidationResult with violations list
        """
        violations = []
        patterns_checked = 0

        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Should have been caught by SyntaxValidator
            return LookaheadValidationResult(
                passed=False,
                violations=["Code has syntax errors"],
                patterns_checked=0
            )

        # Check all forbidden patterns
        for node in ast.walk(tree):
            patterns_checked += 1

            # Pattern 1: rolling(center=True)
            violation = self._check_rolling_center(node)
            if violation:
                violations.append(violation)

            # Pattern 2: shift(-N)
            violation = self._check_shift_negative(node)
            if violation:
                violations.append(violation)

            # Pattern 3: expanding(center=True)
            violation = self._check_expanding_center(node)
            if violation:
                violations.append(violation)

        # Additional pattern checks
        extra_violations = self._check_advanced_patterns(tree, code)
        violations.extend(extra_violations)

        passed = len(violations) == 0

        if passed:
            logger.debug(f"Lookahead detection PASSED ({patterns_checked} nodes checked)")
        else:
            logger.warning(f"Lookahead detection FAILED: {len(violations)} violations")
            for v in violations:
                logger.warning(f"  - {v}")

        return LookaheadValidationResult(
            passed=passed,
            violations=violations,
            patterns_checked=patterns_checked
        )

    def _check_rolling_center(self, node: ast.AST) -> str | None:
        """Check for rolling(center=True) pattern"""
        if not isinstance(node, ast.Call):
            return None

        if not hasattr(node.func, 'attr') or node.func.attr != 'rolling':
            return None

        for kw in node.keywords:
            if kw.arg == 'center':
                if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    return "rolling(center=True) detected - uses future data for window calculation"

        return None

    def _check_shift_negative(self, node: ast.AST) -> str | None:
        """Check for shift(-N) with negative values"""
        if not isinstance(node, ast.Call):
            return None

        if not hasattr(node.func, 'attr') or node.func.attr != 'shift':
            return None

        if not node.args:
            return None

        arg = node.args[0]

        # Check for UnaryOp with negative
        if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
            if isinstance(arg.operand, ast.Constant):
                return f"shift(-{arg.operand.value}) detected - accesses future data"

        # Check for negative constant directly
        if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)):
            if arg.value < 0:
                return f"shift({arg.value}) detected - accesses future data"

        return None

    def _check_expanding_center(self, node: ast.AST) -> str | None:
        """Check for expanding(center=True) pattern"""
        if not isinstance(node, ast.Call):
            return None

        if not hasattr(node.func, 'attr') or node.func.attr != 'expanding':
            return None

        for kw in node.keywords:
            if kw.arg == 'center':
                if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    return "expanding(center=True) detected - uses future data"

        return None

    def _check_advanced_patterns(self, tree: ast.AST, code: str) -> List[str]:
        """Check for more advanced lookahead patterns"""
        violations = []

        # Pattern: df.iloc[i+N] where N > 0 inside a loop iterating backwards
        # This is complex to detect statically, so we use heuristics

        # Pattern: Future max/min in rolling operations
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func

                # Check for chained calls like df['close'].rolling(N).max()
                if hasattr(func, 'attr') and func.attr in ['max', 'min', 'mean', 'sum']:
                    if hasattr(func, 'value') and isinstance(func.value, ast.Call):
                        inner_call = func.value
                        if hasattr(inner_call.func, 'attr'):
                            inner_func = inner_call.func.attr
                            if inner_func == 'rolling':
                                # Check for center=True in the rolling call
                                for kw in inner_call.keywords:
                                    if kw.arg == 'center' and isinstance(kw.value, ast.Constant):
                                        if kw.value.value is True:
                                            violations.append(
                                                f"rolling().{func.attr}() with center=True detected"
                                            )

        # Pattern: Accessing df.iloc[future_index] patterns
        # Check for patterns like df.iloc[i + offset] where offset could be positive
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript):
                if hasattr(node.value, 'attr') and node.value.attr == 'iloc':
                    # Check if index is a BinOp with positive constant
                    if isinstance(node.slice, ast.BinOp):
                        if isinstance(node.slice.op, ast.Add):
                            if isinstance(node.slice.right, ast.Constant):
                                if isinstance(node.slice.right.value, int) and node.slice.right.value > 0:
                                    violations.append(
                                        f"df.iloc[i + {node.slice.right.value}] detected - "
                                        "may access future data in loops"
                                    )

        return violations

    def quick_check(self, code: str) -> Tuple[bool, List[str]]:
        """
        Quick check without full result object.

        Args:
            code: Python source code

        Returns:
            (passed, violations) tuple
        """
        result = self.validate(code)
        return (result.passed, result.violations)
