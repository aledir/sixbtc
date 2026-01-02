"""
Direct Pattern Generator (Mode A)

Generates StrategyCore classes by directly embedding pattern formula_source.
No AI cost - deterministic code generation.

Pattern formula_source is embedded directly, with:
1. bars_*() functions replaced with precomputed values
2. Helper functions included inline
3. Wrapped in StrategyCore class structure
"""

import ast
import uuid
import logging
from typing import Optional
from dataclasses import dataclass

from src.generator.pattern_fetcher import Pattern
from src.generator.helper_fetcher import HelperFetcher

logger = logging.getLogger(__name__)


@dataclass
class DirectGeneratedStrategy:
    """Result of direct pattern generation"""
    code: str
    strategy_id: str
    strategy_type: str
    timeframe: str
    patterns_used: list[str]
    validation_passed: bool
    validation_errors: list[str]
    leverage: int = 1
    pattern_id: Optional[str] = None
    generation_mode: str = "direct"


class DirectPatternGenerator:
    """
    Generates strategies by directly embedding pattern source code

    No AI calls - pure code transformation.

    Strategy Structure:
    1. Imports (standard)
    2. Helper functions (from API)
    3. bars_*() functions (precomputed for timeframe)
    4. Pattern function (formula_source)
    5. StrategyCore class wrapper
    """

    STRATEGY_TEMPLATE = '''import pandas as pd
import numpy as np
import talib as ta
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType

# =============================================================================
# TIMEFRAME BAR MAPPINGS (precomputed for {timeframe})
# =============================================================================
{bars_functions}

# =============================================================================
# HELPER FUNCTIONS (from pattern-discovery)
# =============================================================================
{helper_functions}

# =============================================================================
# PATTERN FUNCTION: {pattern_name}
# {pattern_readable}
# =============================================================================
{pattern_function}


class Strategy_{strategy_type}_{strategy_id}(StrategyCore):
    """
    Pattern-based strategy: {pattern_name}

    Direction: {direction} only
    Timeframe: {timeframe}
    Holding Period: {holding_period}

    Pattern Edge: {edge:.2f}%
    Pattern Win Rate: {win_rate:.1f}%

    Generated via Direct Embedding (Mode A) - No AI translation.
    """

    leverage = {leverage}

    # Indicator columns added by calculate_indicators()
    indicator_columns = ['atr', 'pattern_signal']

    def __init__(self, params: dict = None):
        super().__init__(params)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate ATR and pattern signal.

        The pattern function is called here ONCE on the full dataframe.
        """
        df = df.copy()

        # ATR for stops
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)

        # Call pattern function ONCE on full dataframe
        try:
            pattern_result = {pattern_func_name}(df)
            if isinstance(pattern_result, pd.Series):
                df['pattern_signal'] = pattern_result
            else:
                # Scalar result - apply to last bar only
                df['pattern_signal'] = False
                df.loc[df.index[-1], 'pattern_signal'] = pattern_result
        except Exception:
            df['pattern_signal'] = False

        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        """Generate {direction} signal from pre-calculated pattern."""
        min_bars = 100
        if len(df) < min_bars:
            return None

        # Read pre-calculated values
        current_atr = df['atr'].iloc[-1]
        entry_condition = bool(df['pattern_signal'].iloc[-1])

        if pd.isna(current_atr) or current_atr <= 0:
            return None

        if entry_condition:
            return Signal(
                direction='{direction}',
                leverage=self.leverage,
                sl_type=StopLossType.{sl_type},
                atr_stop_multiplier={sl_multiplier},
                tp_type=TakeProfitType.RR_RATIO,
                rr_ratio={rr_ratio},
                reason="Pattern {pattern_name}: {pattern_readable}"
            )

        return None
'''

    def __init__(self, config: dict):
        """
        Initialize Direct Pattern Generator

        Args:
            config: Full configuration dict
        """
        self.config = config
        api_url = config['pattern_discovery']['api_url']
        cache_ttl = config.get('pattern_discovery', {}).get('helpers', {}).get(
            'cache_ttl_seconds', 3600
        )
        self.helper_fetcher = HelperFetcher(api_url, cache_ttl_seconds=cache_ttl)

    def generate(
        self,
        pattern: Pattern,
        leverage: int = 1
    ) -> Optional[DirectGeneratedStrategy]:
        """
        Generate strategy from pattern using direct embedding

        Args:
            pattern: Pattern with formula_source
            leverage: Leverage to use

        Returns:
            DirectGeneratedStrategy or None if generation failed
        """
        # Validate pattern has source code
        if not pattern.formula_source:
            logger.warning(
                f"Pattern {pattern.name} has no formula_source, "
                "cannot use direct generation"
            )
            return None

        strategy_id = str(uuid.uuid4())[:8]
        strategy_type = pattern.strategy_type or "GEN"

        logger.info(
            f"Generating strategy via Direct Embedding: "
            f"{pattern.name} -> Strategy_{strategy_type}_{strategy_id}"
        )

        try:
            # Get helpers for this timeframe
            helpers_context = self.helper_fetcher.get_helpers(pattern.timeframe)

            # Generate helper functions code
            helper_functions = self._generate_helper_code(helpers_context)

            # Generate bars_*() functions
            bars_functions = self._generate_bars_code(helpers_context)

            # Extract pattern function name from source
            pattern_func_name = self._extract_function_name(pattern.formula_source)

            # Clean pattern readable description
            pattern_readable = (
                pattern.formula_readable or
                pattern.name.replace('_', ' ')
            )

            # Build complete strategy code
            code = self.STRATEGY_TEMPLATE.format(
                helper_functions=helper_functions,
                timeframe=pattern.timeframe,
                bars_functions=bars_functions,
                pattern_name=pattern.name,
                pattern_readable=pattern_readable,
                pattern_function=pattern.formula_source,
                strategy_type=strategy_type,
                strategy_id=strategy_id,
                direction=pattern.target_direction,
                holding_period=pattern.holding_period or "4h",
                edge=pattern.test_edge * 100,
                win_rate=pattern.test_win_rate * 100,
                leverage=leverage,
                pattern_func_name=pattern_func_name,
                sl_type=pattern.suggested_sl_type or "ATR",
                sl_multiplier=pattern.suggested_sl_multiplier or 2.0,
                rr_ratio=pattern.suggested_rr_ratio or 2.0,
            )

            # Validate generated code
            validation_passed, errors = self._validate_code(code)

            if not validation_passed:
                logger.warning(
                    f"Direct generation validation failed for {pattern.name}: {errors}"
                )

            return DirectGeneratedStrategy(
                code=code,
                strategy_id=strategy_id,
                strategy_type=strategy_type,
                timeframe=pattern.timeframe,
                patterns_used=[pattern.id],
                validation_passed=validation_passed,
                validation_errors=errors,
                leverage=leverage,
                pattern_id=pattern.id,
                generation_mode="direct"
            )

        except Exception as e:
            logger.error(f"Direct generation failed for {pattern.name}: {e}")
            return None

    def _generate_helper_code(self, context) -> str:
        """Generate helper functions code from context"""
        if context is None or not context.helper_functions:
            return "# No helper functions required"

        lines = []
        for func_name, func_code in context.helper_functions.items():
            lines.append(func_code)
            lines.append("")  # Blank line between functions

        return "\n".join(lines).strip() if lines else "# No helper functions"

    def _generate_bars_code(self, context) -> str:
        """Generate bars_*() functions from context"""
        if context is None or not context.timeframe_bars:
            # Fallback to common 15m defaults
            return """def bars_1h(): return 4
def bars_4h(): return 16
def bars_24h(): return 96"""

        lines = []
        for period, bars in sorted(context.timeframe_bars.items()):
            func_name = f"bars_{period}"
            lines.append(f"def {func_name}(): return {bars}")

        return "\n".join(lines) if lines else "def bars_24h(): return 96"

    def _extract_function_name(self, source: str) -> str:
        """Extract function name from source code"""
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return node.name
        except SyntaxError as e:
            logger.warning(f"Failed to parse pattern source: {e}")

        # Fallback: try to extract from "def xxx(" pattern
        import re
        match = re.search(r'def\s+(\w+)\s*\(', source)
        if match:
            return match.group(1)

        return "pattern_signal"

    def _validate_code(self, code: str) -> tuple[bool, list[str]]:
        """Validate generated code"""
        errors = []

        # AST parsing (syntax check)
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
            return False, errors

        # Required elements
        if 'class Strategy_' not in code:
            errors.append("Missing Strategy class definition")
        if 'def generate_signal' not in code:
            errors.append("Missing generate_signal method")
        if 'StrategyCore' not in code:
            errors.append("Missing StrategyCore inheritance")

        # Lookahead bias patterns (forbidden)
        if 'center=True' in code:
            errors.append("Lookahead bias: rolling(center=True) detected")
        if '.shift(-' in code:
            errors.append("Lookahead bias: negative shift detected")

        # Check for common issues
        if "return Signal(" not in code:
            errors.append("Missing Signal return statement")

        return len(errors) == 0, errors

    def can_generate(self, pattern: Pattern) -> bool:
        """Check if pattern can be generated directly"""
        return bool(pattern.formula_source)
