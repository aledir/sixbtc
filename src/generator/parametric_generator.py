"""
Parametric Generator - Generate Multiple Strategies from Templates

Takes a StrategyTemplate with Jinja2 placeholders and generates
multiple concrete strategies by varying parameters across different sets.

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

from src.database.models import StrategyTemplate
from src.database import get_session
from src.data.coin_registry import get_registry

logger = logging.getLogger(__name__)


def get_leverage_range_from_db() -> Tuple[int, int]:
    """
    Get min/max leverage from active coins via CoinRegistry.

    Returns:
        (min_leverage, max_leverage) tuple

    Raises:
        ValueError: If no active coins in registry
    """
    min_lev, max_lev = get_registry().get_leverage_range()

    if min_lev == 1 and max_lev == 10:
        # Registry returned default fallback, check if actually empty
        coins = get_registry().get_all_active_coins()
        if not coins:
            raise ValueError(
                "No active coins found in database. "
                "Run pairs_updater.py to populate coins table."
            )

    return (min_lev, max_lev)


@dataclass
class GeneratedStrategy:
    """Result of parametric strategy generation"""
    code: str
    strategy_id: str
    strategy_type: str
    timeframe: str
    template_id: str  # UUID of parent template/source
    template_name: str
    parameters: dict  # Specific parameters used
    parameter_hash: str  # Hash for deduplication
    generation_mode: str = "ai_free"  # Will be set by caller based on source
    validation_passed: bool = True
    validation_errors: list = None
    base_code_hash: str = ""  # SHA256 of base code BEFORE parameter embedding
    trading_coins: list = None  # Coins for pattern-based strategies

    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []
        if self.trading_coins is None:
            self.trading_coins = []


class ParametricGenerator:
    """
    Generates concrete strategies from parameterized templates or base code

    No AI calls - just Jinja2 template rendering or regex parameter embedding
    with different parameter sets to create multiple strategies.

    Leverage is assigned randomly based on database coins table:
    - min = MIN(coins.max_leverage) from active coins
    - max = MAX(coins.max_leverage) from active coins
    At execution: actual_leverage = min(strategy.leverage, coin.max_leverage)
    """

    def __init__(self, config: dict):
        """
        Initialize Parametric Generator

        Args:
            config: Full config dict with generation.parametric.parameter_space
        """
        # Jinja2 environment for rendering templates
        self.jinja_env = Environment(
            variable_start_string='{{',
            variable_end_string='}}',
            block_start_string='{%',
            block_end_string='%}'
        )

        # Store config for parameter space
        # Default space used for single base strategy generation
        # (Backtester does actual 375-combo optimization via parametric_constants.py)
        self.config = config
        self.parameter_space = config.get('generation', {}).get('parametric', {}).get('parameter_space', {
            'sl_pct': [0.02],
            'tp_pct': [0.04],
            'leverage': [2],
            'exit_bars': [0]
        })

        # Load leverage range from database
        self.leverage_min, self.leverage_max = get_leverage_range_from_db()

        logger.info(
            f"ParametricGenerator initialized with leverage range: "
            f"{self.leverage_min}x - {self.leverage_max}x (from coins table)"
        )

    def generate_strategies(
        self,
        template: StrategyTemplate,
        max_strategies: Optional[int] = None
    ) -> list[GeneratedStrategy]:
        """
        Generate all parametric strategies for a template

        Args:
            template: StrategyTemplate with Jinja2 placeholders
            max_strategies: Optional limit on number of strategies

        Returns:
            List of GeneratedStrategy objects
        """
        strategies = []

        # Generate all parameter sets
        param_sets = self._generate_parameter_sets(template.parameters_schema)

        if max_strategies and len(param_sets) > max_strategies:
            logger.info(
                f"Limiting to {max_strategies} parameter sets (from {len(param_sets)})"
            )
            param_sets = param_sets[:max_strategies]

        logger.info(
            f"Generating {len(param_sets)} strategies from template {template.name}"
        )

        for i, params in enumerate(param_sets):
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

    def generate_from_base_code(
        self,
        base_code: str,
        strategy_type: str,
        timeframe: str,
        source_id: str,
        source_type: str,
        trading_coins: Optional[list] = None,
        max_strategies: Optional[int] = None
    ) -> list[GeneratedStrategy]:
        """
        Generate N strategies from base code with parametric variations.

        This is the unified method for both AI-based and Pattern-based strategies.
        Parameters are embedded directly into the code using regex substitution.

        Args:
            base_code: Strategy code (no Jinja2 placeholders, just Python)
            strategy_type: Type like "MOM", "REV", etc.
            timeframe: Timeframe like "15m", "1h"
            source_id: UUID of source (pattern ID or template ID)
            source_type: "pattern" or "template"
            trading_coins: Optional list of coins for pattern-based strategies
            max_strategies: Optional limit on strategies to generate

        Returns:
            List of GeneratedStrategy objects with parameters embedded
        """
        import re

        # Calculate base_code_hash BEFORE any parameter modification
        base_code_hash = hashlib.sha256(base_code.encode()).hexdigest()

        # Generate parameter combinations from config space
        param_combos = self._generate_param_combinations()

        if max_strategies and len(param_combos) > max_strategies:
            logger.info(
                f"Limiting to {max_strategies} combinations (from {len(param_combos)})"
            )
            param_combos = param_combos[:max_strategies]

        logger.info(
            f"Generating {len(param_combos)} strategies from {source_type} "
            f"{source_id[:8]}... (hash: {base_code_hash[:8]})"
        )

        strategies = []
        for i, params in enumerate(param_combos):
            try:
                # Embed parameters into code
                code = self._embed_parameters(base_code, params)

                # Generate unique ID from source + params
                strategy_id = self._generate_id(
                    f"{source_type}_{source_id}", params
                )

                # Update class name to match new ID
                code = self._update_class_name(code, strategy_type, strategy_id)

                # Validate generated code
                validation_passed, errors = self._validate_code(code)

                strategy = GeneratedStrategy(
                    code=code,
                    strategy_id=strategy_id,
                    strategy_type=strategy_type,
                    timeframe=timeframe,
                    template_id=source_id,
                    template_name=f"{source_type}_{source_id[:8]}",
                    parameters=params,
                    parameter_hash=self._hash_parameters(params),
                    generation_mode=source_type,
                    validation_passed=validation_passed,
                    validation_errors=errors,
                    base_code_hash=base_code_hash,
                    trading_coins=trading_coins or []
                )
                strategies.append(strategy)

            except Exception as e:
                logger.error(
                    f"Error generating strategy {i + 1} from {source_type}: {e}"
                )

        valid_count = sum(1 for s in strategies if s.validation_passed)
        logger.info(
            f"Generated {len(strategies)} strategies, {valid_count} passed validation"
        )

        return strategies

    def _generate_param_combinations(self) -> list[dict]:
        """
        Generate all parameter combinations from config space.

        Uses config['generation']['parametric']['parameter_space']

        Returns:
            List of parameter dicts
        """
        param_names = list(self.parameter_space.keys())
        param_values = [self.parameter_space[p] for p in param_names]

        combos = []
        for combo in itertools.product(*param_values):
            combos.append(dict(zip(param_names, combo)))

        return combos

    def _embed_parameters(self, code: str, params: dict) -> str:
        """
        Embed parameters directly into strategy code using regex.

        Handles multiple formats:
        - sl_pct = 0.02   -> sl_pct = {new_value}
        - self.sl_pct = 0.02
        - "sl_pct": 0.02

        Args:
            code: Base strategy code
            params: Parameter dict {sl_pct: 0.03, tp_pct: 0.05, ...}

        Returns:
            Code with parameters embedded
        """
        import re

        for param_name, value in params.items():
            # Pattern 1: attribute assignment (sl_pct = 0.02 or self.sl_pct = 0.02)
            pattern1 = rf'(\b(?:self\.)?{param_name}\s*=\s*)[\d.]+(\b)'
            code = re.sub(pattern1, rf'\g<1>{value}\2', code)

            # Pattern 2: dict key ("sl_pct": 0.02)
            pattern2 = rf'(["\']){param_name}\1\s*:\s*[\d.]+'
            code = re.sub(pattern2, rf'"\g<1>": {value}', code)

        return code

    def _fix_template_syntax(self, code_template: str) -> str:
        """
        Fix common AI-generated template syntax issues

        Common issues:
        1. Triple braces in f-strings: {{{ var }}} should be {{ var }}
        2. Escaped braces in f-strings where placeholder should be literal

        Args:
            code_template: Raw template code from AI

        Returns:
            Fixed template code
        """
        import re

        # Fix triple braces {{{ var }}} -> {{ var }}
        # This happens when AI puts Jinja2 placeholder inside f-string
        code_template = re.sub(r'\{\{\{(\s*\w+\s*)\}\}\}', r'{{ \1 }}', code_template)

        # Fix f-string with Jinja2 placeholder in reason strings
        # Pattern: f"...{{{ var }}}..." -> f"...{var}..." after rendering
        # We need to replace the placeholder with the rendered value AND escape for f-string
        # Actually, the issue is that f-string needs {{ }} to produce { }
        # So f"...{{{ entry_threshold }}}..." is trying to produce {value}
        # But Jinja2 sees {{{ as {{ + { which is invalid

        # Better approach: convert f"...{{{ var }}}..." to f"...{value}..."
        # by making it a proper Jinja2 expression that outputs the f-string literal
        # For now, just fix the triple brace to double brace
        code_template = re.sub(r'\{\{\{\s*(\w+)\s*\}\}\}', r'{{ \1 }}', code_template)

        # Fix lookahead bias: remove center=True from rolling()
        # AI sometimes generates this despite explicit instructions
        original = code_template
        # Handle various formats: .rolling(N, center=True), .rolling(window=N, center=True)
        code_template = re.sub(r'center\s*=\s*True', '', code_template)
        # Clean up resulting double commas or trailing commas
        code_template = re.sub(r',\s*,', ',', code_template)
        code_template = re.sub(r',\s*\)', ')', code_template)
        code_template = re.sub(r'\(\s*,', '(', code_template)

        if original != code_template:
            logger.info("Fixed lookahead bias: removed center=True from code")

        return code_template

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
        # Fix common template syntax issues
        fixed_template = self._fix_template_syntax(template.code_template)

        # Calculate base_code_hash BEFORE parameter rendering (for metrics tracking)
        base_code_hash = hashlib.sha256(fixed_template.encode()).hexdigest()

        # Render template with parameters
        try:
            jinja_template = self.jinja_env.from_string(fixed_template)
            code = jinja_template.render(**params)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            return None

        # Assign leverage: use from params if present, otherwise random
        if 'leverage' in params:
            leverage = params['leverage']
            params_with_leverage = params
        else:
            leverage = random.randint(self.leverage_min, self.leverage_max)
            params_with_leverage = {**params, 'leverage': leverage}

        code = self._assign_leverage(code, leverage)

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
            base_code_hash=base_code_hash,
            # generation_mode defaults to "ai_free", can be overridden by caller
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

    def _generate_parameter_sets(self, schema: dict) -> list[dict]:
        """
        Generate all parameter sets from schema (each becomes a strategy)

        Args:
            schema: Parameters schema with values lists

        Returns:
            List of parameter dicts (each will create an independent strategy)
        """
        if not schema:
            return [{}]

        param_names = list(schema.keys())
        param_values = [schema[p]['values'] for p in param_names]

        param_sets = []
        for combo in itertools.product(*param_values):
            param_sets.append(dict(zip(param_names, combo)))

        return param_sets

    def _generate_id(self, template_name: str, params: dict) -> str:
        """
        Generate unique strategy ID from template + params

        Format: {param_hash} (single UUID per CLAUDE.md naming convention)
        """
        # Hash template + parameters together for unique ID
        # Include template name to ensure uniqueness across templates
        combined = f"{template_name}:" + '_'.join(f"{k}:{v}" for k, v in sorted(params.items()))
        return hashlib.sha256(combined.encode()).hexdigest()[:8]

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

        # Find existing class name pattern (supports all prefixes)
        pattern = r'class (?:Strategy|PatStrat|UngStrat|UggStrat|AIFStrat|AIAStrat|PGnStrat|PGgStrat|PtaStrat)_\w+_\w+\(StrategyCore\)'
        new_class = f'class Strategy_{strategy_type}_{strategy_id}(StrategyCore)'

        updated = re.sub(pattern, new_class, code)

        if updated == code:
            # Pattern didn't match, try simpler pattern
            pattern = r'class (?:Strategy|PatStrat|UngStrat|UggStrat|AIFStrat|AIAStrat|PGnStrat|PGgStrat|PtaStrat)_\w+\(StrategyCore\)'
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

        if errors:
            logger.warning(f"Strategy validation failed: {errors}")

        return (len(errors) == 0, errors)

    def count_strategies(self, template: StrategyTemplate) -> int:
        """Count total possible strategies for a template"""
        total = 1
        for param_def in template.parameters_schema.values():
            total *= len(param_def.get('values', [1]))
        return total

    def estimate_batch_size(
        self,
        templates: list[StrategyTemplate]
    ) -> int:
        """Estimate total strategies from a batch of templates"""
        return sum(self.count_strategies(t) for t in templates)
