"""
Syntax Validator - Phase 1 of validation pipeline

Validates:
1. Python syntax correctness
2. Required imports present
3. StrategyCore class inheritance
4. generate_signal method exists
"""

import ast
import re
from dataclasses import dataclass
from typing import List, Tuple

from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class SyntaxValidationResult:
    """Result of syntax validation"""
    passed: bool
    errors: List[str]
    warnings: List[str]
    class_name: str = ""


class SyntaxValidator:
    """
    Phase 1: Python syntax and structure validation

    Fast validation that catches basic errors before more expensive tests.
    """

    REQUIRED_IMPORTS = [
        "pandas",
        "src.strategies.base",
    ]

    REQUIRED_METHODS = [
        "generate_signal",
    ]

    def validate(self, code: str) -> SyntaxValidationResult:
        """
        Validate strategy code syntax and structure.

        Args:
            code: Python source code string

        Returns:
            SyntaxValidationResult with pass/fail and details
        """
        errors = []
        warnings = []
        class_name = ""

        # Phase 1a: Parse syntax
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
            return SyntaxValidationResult(
                passed=False,
                errors=errors,
                warnings=warnings,
                class_name=""
            )

        # Phase 1b: Check required imports
        import_errors = self._check_imports(code, tree)
        errors.extend(import_errors)

        # Phase 1c: Check StrategyCore inheritance
        class_name, inheritance_errors = self._check_class_structure(tree)
        errors.extend(inheritance_errors)

        # Phase 1d: Check required methods
        if class_name:
            method_errors = self._check_methods(tree, class_name)
            errors.extend(method_errors)

        # Phase 1e: Check for common issues (warnings only)
        issue_warnings = self._check_common_issues(tree, code)
        warnings.extend(issue_warnings)

        passed = len(errors) == 0

        if passed:
            logger.debug(f"Syntax validation PASSED for {class_name}")
        else:
            logger.warning(f"Syntax validation FAILED: {errors}")

        return SyntaxValidationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            class_name=class_name
        )

    def _check_imports(self, code: str, tree: ast.AST) -> List[str]:
        """Check for required imports"""
        errors = []

        # Check for pandas import
        if 'pandas' not in code and 'pd' not in code:
            errors.append("Missing required import: pandas")

        # Check for StrategyCore import
        if 'StrategyCore' not in code:
            errors.append("Missing required import: StrategyCore from src.strategies.base")

        # Check for Signal import
        if 'Signal' not in code:
            errors.append("Missing required import: Signal from src.strategies.base")

        return errors

    def _check_class_structure(self, tree: ast.AST) -> Tuple[str, List[str]]:
        """Check for StrategyCore subclass"""
        errors = []
        class_name = ""

        strategy_classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it inherits from StrategyCore
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == 'StrategyCore':
                        strategy_classes.append(node.name)

        if len(strategy_classes) == 0:
            errors.append("No class inheriting from StrategyCore found")
        elif len(strategy_classes) > 1:
            errors.append(f"Multiple StrategyCore subclasses found: {strategy_classes}")
        else:
            class_name = strategy_classes[0]

            # Validate class name format:
            # - PatStrat_TYPE_hash (e.g., PatStrat_MOM_abc123) - pattern-based
            # - UngStrat_TYPE_hash (e.g., UngStrat_CRS_abc123) - Unger regime-based
            # - AIFStrat_TYPE_hash (e.g., AIFStrat_MOM_abc123) - AI free
            # - AIAStrat_TYPE_hash (e.g., AIAStrat_REV_abc123) - AI assigned
            # - PGnStrat_TYPE_hash (e.g., PGnStrat_THR_abc123) - Pattern-gen smart
            # - PGgStrat_TYPE_hash (e.g., PGgStrat_CRS_abc123) - Pattern-gen genetic
            # - PtaStrat_TYPE_hash (e.g., PtaStrat_VOL_abc123) - Pandas-TA based
            # - Strategy_TYPE_hash (legacy/fallback)
            valid_formats = [
                r'^PatStrat_[A-Z]+_[a-f0-9]+$',           # Pattern: PatStrat_MOM_abc123
                r'^UngStrat_[A-Z]+_[a-f0-9]+$',           # Unger: UngStrat_CRS_abc123
                r'^AIFStrat_[A-Z]+_[a-f0-9]+$',           # AI Free: AIFStrat_MOM_abc123
                r'^AIAStrat_[A-Z]+_[a-f0-9]+$',           # AI Assigned: AIAStrat_REV_abc123
                r'^PGnStrat_[A-Z]+_[a-f0-9]+$',           # Pattern-gen smart: PGnStrat_THR_abc123
                r'^PGgStrat_[A-Z]+_[a-f0-9]+$',           # Pattern-gen genetic: PGgStrat_CRS_abc123
                r'^PtaStrat_[A-Z]+_[a-f0-9]+$',           # Pandas-TA: PtaStrat_VOL_abc123
                r'^Strategy_[A-Z]+_[a-f0-9]+$',           # Legacy: Strategy_MOM_abc123
                r'^Strategy_[A-Z]+_[a-f0-9]+_[a-f0-9]+$', # Template: Strategy_MOM_tpl_param
                r'^Strategy_[A-Z]+_[a-zA-Z0-9]+$',        # Alphanumeric (for tests)
            ]
            if not any(re.match(pattern, class_name) for pattern in valid_formats):
                errors.append(
                    f"Invalid class name format: {class_name}. "
                    "Expected: PatStrat_, UngStrat_, AIFStrat_, AIAStrat_, PGnStrat_, PGgStrat_, or PtaStrat_"
                )

        return class_name, errors

    def _check_methods(self, tree: ast.AST, class_name: str) -> List[str]:
        """Check for required methods in strategy class"""
        errors = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                # Get method names
                method_names = [
                    item.name for item in node.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]

                for required in self.REQUIRED_METHODS:
                    if required not in method_names:
                        errors.append(f"Missing required method: {required}")

                # Check generate_signal signature
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == 'generate_signal':
                        # Check it takes df parameter
                        arg_names = [arg.arg for arg in item.args.args]
                        if 'df' not in arg_names:
                            errors.append(
                                "generate_signal must accept 'df' (DataFrame) parameter"
                            )

        return errors

    def _check_common_issues(self, tree: ast.AST, code: str) -> List[str]:
        """Check for common issues (warnings, not errors)"""
        warnings = []

        # Warning: No return statement in generate_signal
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'generate_signal':
                has_return = any(
                    isinstance(n, ast.Return) and n.value is not None
                    for n in ast.walk(node)
                )
                if not has_return:
                    warnings.append("generate_signal may not return any Signal")

        # Warning: Very short function body
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'generate_signal':
                if len(node.body) < 3:
                    warnings.append("generate_signal has very few statements")

        # Warning: Hardcoded timeframe
        if "'5m'" in code or "'15m'" in code or "'1h'" in code:
            warnings.append("Strategy may have hardcoded timeframe references")

        return warnings
