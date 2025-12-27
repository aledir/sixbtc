"""
Strategy Builder - AI-Powered Strategy Generation

Generates StrategyCore classes using AI with pattern integration and validation.

Two generation modes:
1. Pattern-based: Translates validated patterns from pattern-discovery API
   - One pattern = one strategy (no combinations)
   - Direction forced from pattern's target_direction
   - Uses pattern's suggested SL/TP parameters

2. Template-based: AI generates parameterized templates, system generates variations
   - AI creates ~20 templates/day with Jinja2 placeholders
   - 21 valid template structures (entry/exit combinations)
   - ParametricGenerator creates parameter combinations (no AI cost)
   - Walk-forward validation filters overfitting

Logic: Patterns first, templates as fallback when no patterns available.
"""

import ast
import re
import uuid
import random
from typing import Optional, Literal
from dataclasses import dataclass
import logging
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

from src.generator.ai_manager import AIManager
from src.generator.pattern_fetcher import PatternFetcher, Pattern
from src.generator.template_generator import TemplateGenerator
from src.generator.parametric_generator import (
    ParametricGenerator,
    GeneratedStrategy as ParametricStrategy
)
from src.database.models import StrategyTemplate

logger = logging.getLogger(__name__)

StrategyType = Literal['MOM', 'REV', 'TRN', 'BRE', 'VOL', 'SCA']


@dataclass
class GeneratedStrategy:
    """Result of strategy generation"""
    code: str
    strategy_id: str
    strategy_type: StrategyType
    timeframe: str
    patterns_used: list[str]
    ai_provider: str
    validation_passed: bool
    validation_errors: list[str]
    leverage: int = 1
    pattern_id: Optional[str] = None  # Pattern UUID if pattern-based
    generation_mode: str = "custom"  # "pattern", "custom", or "template"
    template_id: Optional[str] = None  # Template UUID if template-based
    parameters: Optional[dict] = None  # Parameters used if template-based
    parameter_hash: Optional[str] = None  # Hash for deduplication


class StrategyBuilder:
    """
    Generates StrategyCore classes using AI

    Features:
    - Pattern-based generation (using pattern-discovery)
    - Template-based generation (AI templates + parametric variations)
    - 21 valid template structures for maximum diversification
    - AST-based validation (lookahead bias detection)
    - Automatic code fixing
    """

    def __init__(self, config: Optional[dict] = None, init_ai: bool = True):
        """
        Initialize Strategy Builder

        Args:
            config: Configuration dict (uses defaults if None)
            init_ai: Initialize AI manager (False for validation-only mode)
        """
        self.config = config or self._default_config()

        # Initialize components
        if init_ai:
            try:
                # Try to create AI manager if config provided
                if config and 'ai' in config:
                    self.ai_manager = AIManager(config)  # Pass full config
                else:
                    self.ai_manager = None
                    logger.warning("No AI config provided, AI generation disabled")
            except RuntimeError as e:
                logger.warning(f"AI Manager not available: {e}")
                self.ai_manager = None
        else:
            self.ai_manager = None

        # Get pattern discovery API URL from config (NO default)
        pattern_api_url = self.config['generation']['pattern_discovery']['api_url']
        self.pattern_fetcher = PatternFetcher(api_url=pattern_api_url)

        # Setup Jinja2 templates
        template_dir = Path(__file__).parent / 'templates'
        template_dir.mkdir(exist_ok=True)  # Create if not exists
        self.template_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )

        # Initialize template-based generators
        if init_ai and config and 'ai' in config:
            self.template_generator = TemplateGenerator(config)
        else:
            self.template_generator = None

        self.parametric_generator = ParametricGenerator()

    def _default_config(self) -> dict:
        """Default configuration (for tests only - production must provide full config)"""
        return {
            'generation': {
                'pattern_discovery': {
                    'api_url': 'http://localhost:8001'
                },
                'pattern_tier_filter': 1,
                'min_quality_score': 0.75,
                'max_fix_attempts': 3,
                'leverage': {
                    'min': 3,
                    'max': 20
                }
            }
        }

    def _get_random_leverage(self) -> int:
        """Get random leverage within configured range"""
        lev_config = self.config.get('generation', {}).get('leverage', {})
        min_lev = lev_config.get('min', 3)
        max_lev = lev_config.get('max', 20)
        return random.randint(min_lev, max_lev)

    def generate_from_pattern(self, pattern: Pattern) -> Optional[GeneratedStrategy]:
        """
        Generate strategy from a single validated pattern

        One pattern = one strategy. Direction is forced from pattern.

        Args:
            pattern: Validated pattern from pattern-discovery API

        Returns:
            GeneratedStrategy object or None if generation failed
        """
        strategy_id = self._generate_id()
        leverage = self._get_random_leverage()

        # Use pattern's strategy_type if available, otherwise derive from name
        strategy_type = pattern.strategy_type or self._derive_strategy_type(pattern)

        logger.info(
            f"Generating pattern-based {strategy_type} strategy for {pattern.timeframe} "
            f"(ID: {strategy_id}, pattern: {pattern.name})"
        )

        # Build prompt using pattern template
        template = self.template_env.get_template('generate_from_pattern.j2')
        prompt = template.render(
            pattern=pattern,
            strategy_id=strategy_id,
            leverage=leverage
        )

        # Generate code with AI
        try:
            response = self.ai_manager.generate(prompt, max_tokens=4000, temperature=0.5)
            code = self._extract_code_block(response)

            # Validate
            validation_passed, errors = self._validate_code(code)

            # Try to fix if validation failed
            if not validation_passed:
                logger.warning(f"Initial validation failed: {errors}")
                code = self._fix_code(code, errors)
                if code is None:
                    logger.error(f"Failed to fix code for pattern {pattern.name}")
                    return None
                validation_passed, errors = self._validate_code(code)

            return GeneratedStrategy(
                code=code,
                strategy_id=strategy_id,
                strategy_type=strategy_type,
                timeframe=pattern.timeframe,
                patterns_used=[pattern.id],
                ai_provider=self.ai_manager.get_provider_name(),
                validation_passed=validation_passed,
                validation_errors=errors,
                leverage=leverage,
                pattern_id=pattern.id,
                generation_mode="pattern"
            )

        except Exception as e:
            logger.error(f"Pattern-based generation failed for {pattern.name}: {e}")
            return None

    def generate_strategy(
        self,
        strategy_type: StrategyType,
        timeframe: str,
        use_patterns: bool = True,
        patterns: Optional[list] = None
    ) -> Optional[GeneratedStrategy]:
        """
        Generate a complete StrategyCore class

        Priority:
        1. Use provided patterns
        2. Fetch patterns from pattern-discovery
        3. Fallback to template-based generation

        Args:
            strategy_type: Type of strategy (MOM, REV, TRN, etc.)
            timeframe: Target timeframe ('5m', '15m', '1h', etc.)
            use_patterns: Whether to use pattern-discovery patterns
            patterns: Pre-selected patterns (if provided, uses first one)

        Returns:
            GeneratedStrategy object or None if generation failed
        """
        # If patterns provided, use first one (one pattern = one strategy)
        if patterns and len(patterns) > 0:
            return self.generate_from_pattern(patterns[0])

        # If use_patterns, try to fetch one
        if use_patterns:
            fetched_patterns = self._fetch_patterns(timeframe)
            if fetched_patterns:
                return self.generate_from_pattern(fetched_patterns[0])

        # Fallback to template-based generation
        logger.info(f"No patterns available, using template-based generation")
        if self.template_generator:
            template = self.template_generator.generate_template(strategy_type, timeframe)
            if template:
                variations = self.parametric_generator.generate_variations(template, max_variations=1)
                if variations:
                    return self._convert_parametric_strategy(variations[0], template)

        logger.error("No generation method available (no patterns, no template generator)")
        return None

    def _derive_strategy_type(self, pattern: Pattern) -> StrategyType:
        """Derive strategy type from pattern characteristics"""
        # Use pattern's strategy_type if available
        if pattern.strategy_type:
            return pattern.strategy_type

        # Derive from target_name if strategy_type not set
        target = pattern.target_name.lower()
        if 'despite' in target or 'reversal' in target:
            return 'REV'
        elif 'continues' in target or 'trend' in target:
            return 'TRN'
        elif 'breakout' in target or 'break' in target:
            return 'BRE'
        elif 'volatility' in target or 'squeeze' in target:
            return 'VOL'
        else:
            return 'MOM'  # Default to momentum

    def generate_batch(
        self,
        count: int,
        timeframes: Optional[list[str]] = None,
        strategy_types: Optional[list[StrategyType]] = None,
        existing_templates: Optional[list[StrategyTemplate]] = None
    ) -> list[GeneratedStrategy]:
        """
        Generate multiple strategies using patterns first, then templates

        Strategy:
        1. Use all available patterns first (one pattern = one strategy)
        2. Fall back to template-based generation when patterns are exhausted

        Args:
            count: Number of strategies to generate
            timeframes: List of timeframes for template strategies
            strategy_types: List of strategy types for template strategies
            existing_templates: Existing templates to use (optional)

        Returns:
            List of GeneratedStrategy objects (valid only, None excluded)
        """
        timeframes = timeframes or ['15m', '30m', '1h', '4h', '1d']
        strategy_types = strategy_types or ['MOM', 'REV', 'TRN', 'BRE', 'VOL']

        strategies = []
        generated_count = 0

        # Step 1: Fetch all available patterns
        all_patterns = self._fetch_all_patterns()
        logger.info(f"Found {len(all_patterns)} patterns available for generation")

        # Step 2: Generate from patterns first
        for pattern in all_patterns:
            if generated_count >= count:
                break

            strategy = self.generate_from_pattern(pattern)
            if strategy is not None:
                strategies.append(strategy)
                generated_count += 1
                logger.info(
                    f"Generated {generated_count}/{count}: {strategy.strategy_id} "
                    f"(pattern: {pattern.name}, validated: {strategy.validation_passed})"
                )

        # Step 3: Fill remaining with template-based generation
        templates_needed = count - generated_count
        if templates_needed > 0:
            logger.info(f"Patterns exhausted, generating {templates_needed} template-based strategies")

            if self.template_generator:
                # Generate new templates if needed
                templates_to_generate = (templates_needed // 50) + 1  # ~50 variations per template
                new_templates = self.template_generator.generate_batch(count=templates_to_generate)

                # Combine with existing templates
                all_templates = list(existing_templates or []) + new_templates

                # Generate variations until we have enough
                for template in all_templates:
                    if generated_count >= count:
                        break

                    remaining = count - generated_count
                    variations = self.parametric_generator.generate_variations(
                        template,
                        max_variations=remaining
                    )

                    for ps in variations:
                        if generated_count >= count:
                            break
                        strategy = self._convert_parametric_strategy(ps, template)
                        strategies.append(strategy)
                        generated_count += 1
                        logger.info(
                            f"Generated {generated_count}/{count}: {strategy.strategy_id} "
                            f"(template: {template.name}, validated: {strategy.validation_passed})"
                        )
            else:
                logger.warning("Template generator not available, cannot fill remaining count")

        # Summary
        pattern_count = sum(1 for s in strategies if s.generation_mode == "pattern")
        template_count = sum(1 for s in strategies if s.generation_mode == "template")
        validated_count = sum(1 for s in strategies if s.validation_passed)

        logger.info(
            f"Batch generation complete: {len(strategies)} strategies "
            f"({pattern_count} pattern-based, {template_count} template-based), "
            f"{validated_count} validated"
        )

        return strategies

    # ========== TEMPLATE-BASED GENERATION ==========

    def generate_template_batch(
        self,
        count: int = 20
    ) -> list[StrategyTemplate]:
        """
        Generate new AI templates (daily cycle)

        Creates parameterized templates with Jinja2 placeholders
        that can generate thousands of parameter variations.

        Args:
            count: Number of templates to generate (default 20)

        Returns:
            List of generated StrategyTemplate objects
        """
        if not self.template_generator:
            logger.error("Template generator not initialized - AI config required")
            return []

        logger.info(f"Generating {count} new AI templates")
        return self.template_generator.generate_batch(count=count)

    def generate_from_templates(
        self,
        templates: list[StrategyTemplate],
        max_variations_per_template: Optional[int] = None
    ) -> list[GeneratedStrategy]:
        """
        Generate strategies from templates using parametric variations

        No AI cost - just Jinja2 rendering with different parameters.

        Args:
            templates: List of StrategyTemplate objects
            max_variations_per_template: Limit variations per template (None = all)

        Returns:
            List of GeneratedStrategy objects
        """
        all_strategies = []

        for template in templates:
            try:
                # Generate parametric variations
                parametric_strategies = self.parametric_generator.generate_variations(
                    template,
                    max_variations=max_variations_per_template
                )

                # Convert to GeneratedStrategy format
                for ps in parametric_strategies:
                    strategy = self._convert_parametric_strategy(ps, template)
                    all_strategies.append(strategy)

                logger.info(
                    f"Generated {len(parametric_strategies)} variations from "
                    f"template {template.name}"
                )

            except Exception as e:
                logger.error(f"Failed to generate from template {template.name}: {e}")

        valid_count = sum(1 for s in all_strategies if s.validation_passed)
        logger.info(
            f"Template generation complete: {len(all_strategies)} strategies, "
            f"{valid_count} validated"
        )

        return all_strategies

    def _convert_parametric_strategy(
        self,
        ps: ParametricStrategy,
        template: StrategyTemplate
    ) -> GeneratedStrategy:
        """Convert ParametricStrategy to GeneratedStrategy format"""
        return GeneratedStrategy(
            code=ps.code,
            strategy_id=ps.strategy_id,
            strategy_type=ps.strategy_type,
            timeframe=ps.timeframe,
            patterns_used=[],
            ai_provider=template.ai_provider or "template",
            validation_passed=ps.validation_passed,
            validation_errors=ps.validation_errors,
            leverage=1,  # Set from parameters if available
            pattern_id=None,
            generation_mode="template",
            template_id=ps.template_id,
            parameters=ps.parameters,
            parameter_hash=ps.parameter_hash
        )

    def generate_daily_batch(
        self,
        new_templates_count: int = 20,
        existing_templates: Optional[list[StrategyTemplate]] = None,
        max_variations_per_template: Optional[int] = None
    ) -> tuple[list[StrategyTemplate], list[GeneratedStrategy]]:
        """
        Daily generation cycle: new templates + parametric variations

        This is the main entry point for the template-based pipeline:
        1. Generate new AI templates (~20/day)
        2. Generate parametric variations from ALL templates
        3. Walk-forward validation filters overfitting (done by backtester)

        Args:
            new_templates_count: Number of new templates to generate
            existing_templates: Existing templates from database
            max_variations_per_template: Limit variations (None = all)

        Returns:
            Tuple of (new_templates, all_strategies)
        """
        # Step 1: Generate new AI templates
        new_templates = []
        if new_templates_count > 0 and self.template_generator:
            new_templates = self.generate_template_batch(count=new_templates_count)
            logger.info(f"Generated {len(new_templates)} new AI templates")

        # Step 2: Combine with existing templates
        all_templates = list(existing_templates or []) + new_templates
        logger.info(f"Total templates for variation generation: {len(all_templates)}")

        # Step 3: Generate parametric variations from ALL templates
        all_strategies = self.generate_from_templates(
            templates=all_templates,
            max_variations_per_template=max_variations_per_template
        )

        # Summary
        logger.info(
            f"Daily batch complete: "
            f"{len(new_templates)} new templates, "
            f"{len(all_templates)} total templates, "
            f"{len(all_strategies)} strategies generated"
        )

        return new_templates, all_strategies

    def estimate_variations(
        self,
        templates: list[StrategyTemplate]
    ) -> int:
        """Estimate total strategies from a batch of templates"""
        return self.parametric_generator.estimate_batch_size(templates)

    def _fetch_all_patterns(self) -> list[Pattern]:
        """Fetch all available patterns from pattern-discovery"""
        try:
            min_quality = self.config.get('generation', {}).get('min_quality_score', 0.75)
            return self.pattern_fetcher.get_tier_1_patterns(
                limit=100,  # Fetch up to 100 patterns
                min_quality_score=min_quality
            )
        except Exception as e:
            logger.warning(f"Failed to fetch patterns: {e}")
            return []

    def _fetch_patterns(self, timeframe: str) -> list[Pattern]:
        """Fetch patterns from pattern-discovery"""
        try:
            min_quality = self.config.get('generation', {}).get('min_quality_score', 0.75)
            return self.pattern_fetcher.get_tier_1_patterns(
                timeframe=timeframe,
                limit=10,
                min_quality_score=min_quality
            )
        except Exception as e:
            logger.warning(f"Failed to fetch patterns: {e}")
            return []

    def _generate_id(self) -> str:
        """Generate unique strategy ID (8 chars)"""
        return str(uuid.uuid4())[:8]

    def generate_strategy_id(self, strategy_type: str) -> str:
        """
        Generate unique strategy ID with type prefix

        Args:
            strategy_type: Strategy type (MOM, REV, etc.)

        Returns:
            Strategy ID in format Strategy_TYPE_12345678
        """
        unique_id = str(uuid.uuid4())[:8]
        return f"Strategy_{strategy_type}_{unique_id}"

    def build_from_template(
        self,
        template_name: str,
        variables: dict
    ) -> str:
        """
        Build strategy code from Jinja2 template

        Args:
            template_name: Template file name
            variables: Variables to render in template

        Returns:
            Generated strategy code
        """
        try:
            template = self.template_env.get_template(template_name)
            code = template.render(**variables)
            return code
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            # Fallback: generate basic code
            return self._generate_fallback_code(variables)

    def _generate_fallback_code(self, variables: dict) -> str:
        """Generate basic strategy code when template is missing"""
        strategy_name = variables.get('strategy_name', 'Strategy_GEN_fallback')
        indicator = variables.get('indicator', 'RSI')
        period = variables.get('period', 14)
        threshold = variables.get('threshold', 30)

        code = f'''import pandas as pd
import talib as ta
from src.strategies.base import StrategyCore, Signal

class {strategy_name}(StrategyCore):
    """
    {indicator}-based strategy
    """
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < {period}:
            return None

        {indicator.lower()} = ta.{indicator}(df['close'], timeperiod={period})

        if {indicator.lower()}.iloc[-1] < {threshold}:
            return Signal(direction='long', reason="{indicator} oversold")

        return None
'''
        return code

    def validate_code(self, code: str) -> bool:
        """
        Validate strategy code

        Args:
            code: Strategy code to validate

        Returns:
            True if valid, False otherwise
        """
        validation_passed, _ = self._validate_code(code)
        return validation_passed

    def extract_metadata(self, code: str) -> dict:
        """
        Extract metadata from strategy code

        Args:
            code: Strategy code

        Returns:
            Dict with metadata (name, type, timeframe, etc.)
        """
        metadata = {
            'name': None,
            'type': None,
            'timeframe': None
        }

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # Extract class name
                if isinstance(node, ast.ClassDef):
                    metadata['name'] = node.name

                    # Check docstring for type and timeframe
                    if node.body and isinstance(node.body[0], ast.Expr):
                        docstring = ast.get_docstring(node)
                        if docstring:
                            # Extract type
                            type_match = re.search(r'Type:\s*(\w+)', docstring)
                            if type_match:
                                metadata['type'] = type_match.group(1)

                            # Extract timeframe
                            tf_match = re.search(r'Timeframe:\s*(\w+)', docstring)
                            if tf_match:
                                metadata['timeframe'] = tf_match.group(1)

                # Check __init__ for attributes
                if isinstance(node, ast.FunctionDef) and node.name == '__init__':
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Attribute):
                                    if target.attr == 'timeframe' and isinstance(item.value, ast.Constant):
                                        metadata['timeframe'] = item.value.value

        except Exception as e:
            logger.warning(f"Failed to extract metadata: {e}")

        return metadata

    def _extract_code_block(self, content: str) -> str:
        """Extract Python code from AI response"""
        # Look for ```python ... ``` blocks
        match = re.search(r'```python\s+(.*?)\s+```', content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Fallback: assume entire content is code
        return content.strip()

    def _validate_code(self, code: str) -> tuple[bool, list[str]]:
        """
        Validate strategy code

        Returns:
            (validation_passed, list_of_errors)
        """
        errors = []

        # 1. AST parsing
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error: {e}")
            return False, errors

        # 2. Check for StrategyCore class
        has_strategy_class = False
        has_generate_signal = False

        for node in ast.walk(tree):
            # Check class inheritance
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == 'StrategyCore':
                        has_strategy_class = True

                # Check for generate_signal method
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == 'generate_signal':
                        has_generate_signal = True

        if not has_strategy_class:
            errors.append("No class inheriting from StrategyCore found")

        if not has_generate_signal:
            errors.append("No generate_signal method found")

        # 3. Check for lookahead bias patterns
        lookahead_errors = self._check_lookahead_bias(tree)
        errors.extend(lookahead_errors)

        # 4. Check imports
        if 'from src.strategies.base import' not in code:
            errors.append("Missing import: from src.strategies.base import StrategyCore, Signal")

        return (len(errors) == 0, errors)

    def _check_lookahead_bias(self, tree: ast.AST) -> list[str]:
        """
        Check for lookahead bias patterns in AST

        Forbidden patterns:
        - rolling(center=True)
        - shift(-N) where N > 0
        """
        errors = []

        for node in ast.walk(tree):
            # Check rolling(center=True)
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr') and node.func.attr == 'rolling':
                    for kw in node.keywords:
                        if kw.arg == 'center':
                            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                errors.append(
                                    "Lookahead bias: rolling(center=True) detected"
                                )

                # Check shift with negative value
                if hasattr(node.func, 'attr') and node.func.attr == 'shift':
                    if node.args:
                        arg = node.args[0]
                        # Check for negative number
                        if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
                            errors.append(
                                "Lookahead bias: negative shift detected"
                            )
                        # Check for negative constant
                        elif isinstance(arg, ast.Constant) and arg.value < 0:
                            errors.append(
                                "Lookahead bias: negative shift detected"
                            )

        return errors

    def _fix_code(self, code: str, errors: list[str]) -> Optional[str]:
        """
        Attempt to fix code using AI

        Args:
            code: Original code with errors
            errors: List of validation errors

        Returns:
            Fixed code if successful, None if all attempts failed
        """
        # Get max attempts from config - if missing, use reasonable default (not critical)
        max_attempts = self.config.get('generation', {}).get('max_fix_attempts', 3)

        for attempt in range(max_attempts):
            logger.info(f"Attempting code fix (attempt {attempt + 1}/{max_attempts})")

            template = self.template_env.get_template('fix_code.j2')
            prompt = template.render(original_code=code, errors=errors)

            try:
                response = self.ai_manager.generate(prompt, max_tokens=4000, temperature=0.3)
                fixed_code = self._extract_code_block(response)

                # Validate fixed code
                validation_passed, new_errors = self._validate_code(fixed_code)

                if validation_passed:
                    logger.info(f"Code fixed successfully on attempt {attempt + 1}")
                    return fixed_code

                # Update code and errors for next attempt
                code = fixed_code
                errors = new_errors

            except Exception as e:
                logger.error(f"Code fix attempt {attempt + 1} failed: {e}")

        logger.warning(f"Failed to fix code after {max_attempts} attempts - returning None")
        return None  # Return None if fixing failed (do NOT save invalid code)
