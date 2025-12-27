"""
Parametric Generator - Generate Strategy Variations from Templates

Takes a StrategyTemplate with Jinja2 placeholders and generates
multiple concrete strategies by applying parameter combinations.

Leverage is assigned randomly from the database coins table:
- min = MIN(coins.max_leverage) from active coins
- max = MAX(coins.max_leverage) from active coins
At execution time: actual_leverage = min(strategy.leverage, coin.max_leverage)
"""

import ast
import hashlib
import itertools
import logging
import random
from typing import Optional, Tuple
from dataclasses import dataclass
from jinja2 import Environment

from sqlalchemy import func
from src.database.models import StrategyTemplate, Coin
from src.database import get_session

logger = logging.getLogger(__name__)


def get_leverage_range_from_db() -> Tuple[int, int]:
    """
    Get min/max leverage from active coins in database

    Returns:
        (min_leverage, max_leverage) tuple

    Raises:
        ValueError: If no active coins in database
    """
    with get_session() as session:
        result = session.query(
            func.min(Coin.max_leverage).label('min_lev'),
            func.max(Coin.max_leverage).label('max_lev')
        ).filter(Coin.is_active == True).first()

        if result is None or result.min_lev is None or result.max_lev is None:
            raise ValueError(
                "No active coins found in database. "
                "Run pairs_updater.py to populate coins table."
            )

        return (result.min_lev, result.max_lev)


@dataclass
class GeneratedStrategy:
    """Result of parametric strategy generation"""
    code: str
    strategy_id: str
    strategy_type: str
    timeframe: str
    template_id: str  # UUID of parent template
    template_name: str
    parameters: dict  # Specific parameters used
    parameter_hash: str  # Hash for deduplication
    generation_mode: str = "template"
    validation_passed: bool = True
    validation_errors: list = None

    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []


class ParametricGenerator:
    """
    Generates concrete strategies from parameterized templates

    No AI calls - just Jinja2 template rendering with
    different parameter combinations.

    Leverage is assigned randomly based on database coins table:
    - min = MIN(coins.max_leverage) from active coins
    - max = MAX(coins.max_leverage) from active coins
    At execution: actual_leverage = min(strategy.leverage, coin.max_leverage)
    """

    def __init__(self, config: dict = None):
        """
        Initialize Parametric Generator

        Reads leverage range from database (coins.max_leverage)
        """
        # Jinja2 environment for rendering templates
        self.jinja_env = Environment(
            variable_start_string='{{',
            variable_end_string='}}',
            block_start_string='{%',
            block_end_string='%}'
        )

        # Load leverage range from database
        self.leverage_min, self.leverage_max = get_leverage_range_from_db()

        logger.info(
            f"ParametricGenerator initialized with leverage range: "
            f"{self.leverage_min}x - {self.leverage_max}x (from coins table)"
        )

    def generate_variations(
        self,
        template: StrategyTemplate,
        max_variations: Optional[int] = None
    ) -> list[GeneratedStrategy]:
        """
        Generate all parameter variations for a template

        Args:
            template: StrategyTemplate with Jinja2 placeholders
            max_variations: Optional limit on number of variations

        Returns:
            List of GeneratedStrategy objects
        """
        strategies = []

        # Generate all parameter combinations
        combinations = self._generate_combinations(template.parameters_schema)

        if max_variations and len(combinations) > max_variations:
            logger.info(
                f"Limiting {len(combinations)} combinations to {max_variations}"
            )
            combinations = combinations[:max_variations]

        logger.info(
            f"Generating {len(combinations)} variations for template {template.name}"
        )

        for i, params in enumerate(combinations):
            try:
                strategy = self._generate_single(template, params)
                if strategy:
                    strategies.append(strategy)
            except Exception as e:
                logger.error(
                    f"Error generating variation {i + 1} for {template.name}: {e}"
                )

        valid_count = sum(1 for s in strategies if s.validation_passed)
        logger.info(
            f"Generated {len(strategies)} strategies from {template.name}, "
            f"{valid_count} passed validation"
        )

        return strategies

    def _generate_single(
        self,
        template: StrategyTemplate,
        params: dict
    ) -> Optional[GeneratedStrategy]:
        """
        Generate a single strategy from template + parameters

        Args:
            template: Parent template
            params: Specific parameter values

        Returns:
            GeneratedStrategy or None if failed
        """
        # Render template with parameters
        try:
            jinja_template = self.jinja_env.from_string(template.code_template)
            code = jinja_template.render(**params)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            return None

        # Assign random leverage (NOT from AI)
        leverage = random.randint(self.leverage_min, self.leverage_max)
        code = self._assign_leverage(code, leverage)

        # Add leverage to params for tracking
        params_with_leverage = {**params, 'leverage': leverage}

        # Generate unique ID based on template + params (including leverage)
        strategy_id = self._generate_id(template.name, params_with_leverage)
        parameter_hash = self._hash_parameters(params_with_leverage)

        # Update class name in code to match strategy_id
        code = self._update_class_name(code, template.strategy_type, strategy_id)

        # Validate generated code
        validation_passed, errors = self._validate_code(code)

        return GeneratedStrategy(
            code=code,
            strategy_id=strategy_id,
            strategy_type=template.strategy_type,
            timeframe=template.timeframe,
            template_id=str(template.id) if template.id else "",
            template_name=template.name,
            parameters=params_with_leverage,
            parameter_hash=parameter_hash,
            generation_mode="template",
            validation_passed=validation_passed,
            validation_errors=errors
        )

    def _assign_leverage(self, code: str, leverage: int) -> str:
        """
        Replace __LEVERAGE__ placeholder with actual leverage value

        Args:
            code: Strategy code with placeholder
            leverage: Leverage value to assign

        Returns:
            Code with leverage assigned
        """
        # Replace the placeholder
        if '__LEVERAGE__' in code:
            code = code.replace('__LEVERAGE__', str(leverage))
        else:
            # Fallback: try to find and update existing leverage attribute
            import re
            pattern = r'leverage\s*=\s*\d+'
            replacement = f'leverage = {leverage}'
            code = re.sub(pattern, replacement, code)

        return code

    def _generate_combinations(self, schema: dict) -> list[dict]:
        """
        Generate all parameter combinations from schema

        Args:
            schema: Parameters schema with values lists

        Returns:
            List of parameter dicts
        """
        if not schema:
            return [{}]

        param_names = list(schema.keys())
        param_values = [schema[p]['values'] for p in param_names]

        combinations = []
        for combo in itertools.product(*param_values):
            combinations.append(dict(zip(param_names, combo)))

        return combinations

    def _generate_id(self, template_name: str, params: dict) -> str:
        """
        Generate unique strategy ID from template + params

        Format: {template_short}_{param_hash_short}
        """
        # Extract template short ID
        template_short = template_name.split('_')[-1] if '_' in template_name else template_name[:8]

        # Hash parameters
        param_str = '_'.join(f"{k}{v}" for k, v in sorted(params.items()))
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:6]

        return f"{template_short}_{param_hash}"

    def _hash_parameters(self, params: dict) -> str:
        """Generate hash of parameters for deduplication"""
        param_str = '_'.join(f"{k}:{v}" for k, v in sorted(params.items()))
        return hashlib.sha256(param_str.encode()).hexdigest()[:16]

    def _update_class_name(
        self,
        code: str,
        strategy_type: str,
        strategy_id: str
    ) -> str:
        """Update class name in code to match strategy ID"""
        import re

        # Find existing class name pattern
        pattern = r'class Strategy_\w+_\w+\(StrategyCore\)'
        new_class = f'class Strategy_{strategy_type}_{strategy_id}(StrategyCore)'

        updated = re.sub(pattern, new_class, code)

        if updated == code:
            # Pattern didn't match, try simpler pattern
            pattern = r'class Strategy_\w+\(StrategyCore\)'
            updated = re.sub(pattern, new_class, code)

        return updated

    def _validate_code(self, code: str) -> tuple[bool, list[str]]:
        """
        Validate generated strategy code

        Returns:
            (validation_passed, list_of_errors)
        """
        errors = []

        # 1. AST parsing
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error: {e}")
            return False, errors

        # 2. Check for required elements
        if 'class Strategy_' not in code:
            errors.append("Missing Strategy class definition")

        if 'def generate_signal' not in code:
            errors.append("Missing generate_signal method")

        if 'StrategyCore' not in code:
            errors.append("Missing StrategyCore inheritance")

        # 3. Check for unrendered placeholders
        if '{{' in code or '}}' in code:
            errors.append("Unrendered Jinja2 placeholders in code")

        # 4. Check for lookahead bias patterns
        if 'center=True' in code:
            errors.append("Lookahead bias: rolling(center=True) detected")

        if '.shift(-' in code:
            errors.append("Lookahead bias: negative shift detected")

        return (len(errors) == 0, errors)

    def count_variations(self, template: StrategyTemplate) -> int:
        """Count total possible variations for a template"""
        total = 1
        for param_def in template.parameters_schema.values():
            total *= len(param_def.get('values', [1]))
        return total

    def estimate_batch_size(
        self,
        templates: list[StrategyTemplate]
    ) -> int:
        """Estimate total strategies from a batch of templates"""
        return sum(self.count_variations(t) for t in templates)
