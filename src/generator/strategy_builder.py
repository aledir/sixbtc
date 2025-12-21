"""
Strategy Builder - AI-Powered Strategy Generation

Generates StrategyCore classes using AI with pattern integration and validation.
"""

import ast
import re
import uuid
from typing import Optional, Literal
from dataclasses import dataclass
import logging
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

from src.generator.ai_manager import AIManager
from src.generator.pattern_fetcher import PatternFetcher, Pattern

logger = logging.getLogger(__name__)

StrategyType = Literal['MOM', 'REV', 'TRN', 'BRE', 'VOL', 'ARB']


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


class StrategyBuilder:
    """
    Generates StrategyCore classes using AI

    Features:
    - Pattern-based generation (using pattern-discovery)
    - Custom AI logic generation
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
                    self.ai_manager = AIManager(config['ai'])
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

    def _default_config(self) -> dict:
        """Default configuration (for tests only - production must provide full config)"""
        return {
            'generation': {
                'pattern_discovery': {
                    'api_url': 'http://localhost:8001'
                },
                'pattern_tier_filter': 1,
                'min_quality_score': 0.75,
                'pattern_based_pct': 0.30,
                'max_fix_attempts': 3
            }
        }

    def generate_strategy(
        self,
        strategy_type: StrategyType,
        timeframe: str,
        use_patterns: bool = True
    ) -> GeneratedStrategy:
        """
        Generate a complete StrategyCore class

        Args:
            strategy_type: Type of strategy (MOM, REV, TRN, etc.)
            timeframe: Target timeframe ('5m', '15m', '1h', etc.)
            use_patterns: Whether to use pattern-discovery patterns

        Returns:
            GeneratedStrategy object with code and metadata
        """
        strategy_id = self._generate_id()

        logger.info(
            f"Generating {strategy_type} strategy for {timeframe} (ID: {strategy_id})"
        )

        # Fetch patterns if requested
        patterns = []
        if use_patterns:
            patterns = self._fetch_patterns(timeframe)
            if patterns:
                logger.info(f"Using {len(patterns)} patterns from pattern-discovery")
            else:
                logger.info("No patterns available, using custom AI logic")

        # Build prompt
        template = self.template_env.get_template('generate_strategy.j2')
        prompt = template.render(
            strategy_type=strategy_type,
            timeframe=timeframe,
            strategy_id=strategy_id,
            patterns=patterns
        )

        # Generate code with AI
        try:
            response = self.ai_manager.generate(prompt, max_tokens=4000, temperature=0.7)
            code = self._extract_code_block(response.content)

            # Validate
            validation_passed, errors = self._validate_code(code)

            # Try to fix if validation failed
            if not validation_passed:
                logger.warning(f"Initial validation failed: {errors}")
                code = self._fix_code(code, errors)
                validation_passed, errors = self._validate_code(code)

            pattern_ids = [p.id for p in patterns]

            return GeneratedStrategy(
                code=code,
                strategy_id=strategy_id,
                strategy_type=strategy_type,
                timeframe=timeframe,
                patterns_used=pattern_ids,
                ai_provider=response.provider,
                validation_passed=validation_passed,
                validation_errors=errors
            )

        except Exception as e:
            logger.error(f"Strategy generation failed: {e}")
            raise

    def generate_batch(
        self,
        count: int,
        timeframes: Optional[list[str]] = None,
        strategy_types: Optional[list[StrategyType]] = None,
        pattern_based_pct: float = 0.30
    ) -> list[GeneratedStrategy]:
        """
        Generate multiple strategies

        Args:
            count: Number of strategies to generate
            timeframes: List of timeframes to distribute across
            strategy_types: List of strategy types to use
            pattern_based_pct: Percentage of pattern-based strategies

        Returns:
            List of GeneratedStrategy objects
        """
        timeframes = timeframes or ['5m', '15m', '30m', '1h', '4h', '1d']
        strategy_types = strategy_types or ['MOM', 'REV', 'TRN', 'BRE']

        strategies = []
        pattern_count = int(count * pattern_based_pct)

        for i in range(count):
            # Round-robin distribution
            tf = timeframes[i % len(timeframes)]
            st = strategy_types[i % len(strategy_types)]
            use_patterns = i < pattern_count

            try:
                strategy = self.generate_strategy(st, tf, use_patterns)
                strategies.append(strategy)
                logger.info(
                    f"Generated {i+1}/{count}: {strategy.strategy_id} "
                    f"(validated: {strategy.validation_passed})"
                )
            except Exception as e:
                logger.error(f"Failed to generate strategy {i+1}/{count}: {e}")

        success_count = sum(1 for s in strategies if s.validation_passed)
        logger.info(
            f"Batch generation complete: {success_count}/{len(strategies)} validated"
        )

        return strategies

    def _fetch_patterns(self, timeframe: str) -> list[Pattern]:
        """Fetch patterns from pattern-discovery"""
        try:
            return self.pattern_fetcher.get_tier_1_patterns(
                timeframe=timeframe,
                limit=10,
                min_quality_score=self.config['min_quality_score']
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

    def build_from_pattern(self, pattern: dict) -> str:
        """
        Build strategy code from a pattern

        Args:
            pattern: Pattern dictionary from pattern-discovery

        Returns:
            Generated strategy code
        """
        # Generate unique ID
        pattern_type = pattern.get('type', 'GEN')
        strategy_id = self.generate_strategy_id(pattern_type)

        # Extract pattern conditions
        conditions = pattern.get('conditions', {})

        # Build basic strategy code
        code_parts = [
            "import pandas as pd",
            "import talib as ta",
            "from src.strategies.base import StrategyCore, Signal",
            "",
            f"class {strategy_id}(StrategyCore):",
            '    """',
            f"    Generated from pattern: {pattern.get('pattern_id', 'UNKNOWN')}",
            f"    Type: {pattern_type}",
            f"    Description: {pattern.get('description', 'No description')}",
            '    """',
            "",
            "    def generate_signal(self, df: pd.DataFrame) -> Signal | None:",
            "        # Minimum data check",
            "        if len(df) < 50:",
            "            return None",
            "",
        ]

        # Add indicator calculations based on conditions
        for key, value in conditions.items():
            if 'period' in key.lower():
                code_parts.append(f"        {key} = {value}")

        code_parts.extend([
            "",
            "        # Calculate indicators",
        ])

        # Add RSI if mentioned
        if 'rsi' in str(conditions).lower():
            rsi_period = conditions.get('rsi_period', 14)
            code_parts.append(f"        rsi = ta.RSI(df['close'], timeperiod={rsi_period})")

        # Add entry logic
        code_parts.extend([
            "",
            "        # Entry conditions",
            "        # TODO: Implement pattern logic",
            "        return None",
        ])

        return "\n".join(code_parts)

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

    def _fix_code(self, code: str, errors: list[str]) -> str:
        """
        Attempt to fix code using AI

        Args:
            code: Original code with errors
            errors: List of validation errors

        Returns:
            Fixed code
        """
        # Get max attempts from config - if missing, use reasonable default (not critical)
        max_attempts = self.config.get('generation', {}).get('max_fix_attempts', 3)

        for attempt in range(max_attempts):
            logger.info(f"Attempting code fix (attempt {attempt + 1}/{max_attempts})")

            template = self.template_env.get_template('fix_code.j2')
            prompt = template.render(original_code=code, errors=errors)

            try:
                response = self.ai_manager.generate(prompt, max_tokens=4000, temperature=0.3)
                fixed_code = self._extract_code_block(response.content)

                # Validate fixed code
                validation_passed, new_errors = self._validate_code(fixed_code)

                if validation_passed:
                    logger.info(f"Code fixed successfully on attempt {attempt + 1}")
                    return fixed_code

                errors = new_errors

            except Exception as e:
                logger.error(f"Code fix attempt {attempt + 1} failed: {e}")

        logger.warning(f"Failed to fix code after {max_attempts} attempts")
        return code  # Return original if fixing failed
