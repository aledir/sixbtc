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
    generation_mode: str = "pattern"  # From pattern-discovery API (direct embedding)


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
from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType

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


class PatStrat_{strategy_type}_{strategy_id}(StrategyCore):
    """
    Pattern-based strategy: {pattern_name}
    Target: {target_name}

    Direction: {direction} only
    Timeframe: {timeframe}
    Holding Period: {holding_period} ({holding_bars} bars)
    Target Magnitude: {magnitude}%

    Pattern Edge: {edge:.2f}%
    Pattern Win Rate: {win_rate:.1f}%

    EXIT STRATEGY:
    - Take Profit at target magnitude ({magnitude}%)
    - Stop Loss at 3× magnitude ({sl_pct_display}%) - Asymmetric R:R 1:3
    - Time limit at {holding_bars} bars (backstop if TP not hit)

    RISK MANAGEMENT:
    Pattern-discovery validated this pattern has {edge:.1f}% edge.
    Asymmetric SL (3×TP) lets winners run while cutting only catastrophic losses.
    Expected profit per trade = magnitude × edge = {magnitude}% × {edge:.1f}% ≈ {expected_profit:.2f}%

    Generated via Direct Embedding (Mode A) - No AI translation.
    """

    # =========================================================================
    # STRATEGY PARAMETERS (read by backtester for vectorized execution)
    # =========================================================================
    direction = '{direction}'
    sl_pct = {sl_pct}
    tp_pct = {tp_pct}
    leverage = {leverage}
    exit_after_bars = {holding_bars}
    signal_column = 'entry_signal'

    # Indicator columns added by calculate_indicators()
    indicator_columns = ['atr', 'entry_signal']

    def __init__(self, params: dict = None):
        super().__init__(params)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate indicators and entry signal.

        The pattern function is called here ONCE on the full dataframe.
        Populates 'entry_signal' column for backtester vectorized execution.
        """
        df = df.copy()

        # ATR (may be used by pattern function)
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)

        # Call pattern function ONCE on full dataframe
        try:
            pattern_result = {pattern_func_name}(df)
            if isinstance(pattern_result, pd.Series):
                df['entry_signal'] = pattern_result.astype(bool)
            else:
                # Scalar result - apply to last bar only
                df['entry_signal'] = False
                df.loc[df.index[-1], 'entry_signal'] = bool(pattern_result)
        except Exception:
            df['entry_signal'] = False

        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        """
        Generate {direction} signal from pre-calculated pattern.

        For LIVE execution: reads entry_signal and returns Signal object.
        For BACKTEST: backtester reads entry_signal array directly (no loop).
        """
        min_bars = 100
        if len(df) < min_bars:
            return None

        # Read pre-calculated entry signal
        entry_condition = bool(df['entry_signal'].iloc[-1])

        if entry_condition:
            return Signal(
                direction=self.direction,
                leverage=self.leverage,
                sl_type=StopLossType.PERCENTAGE,
                sl_pct=self.sl_pct,
                tp_type=TakeProfitType.PERCENTAGE,
                tp_pct=self.tp_pct,
                exit_type=ExitType.TIME_BASED,
                exit_after_bars=self.exit_after_bars,
                reason="Pattern {pattern_name} [{target_name}]: {pattern_readable}"
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
            f"{pattern.name} -> PatStrat_{strategy_type}_{strategy_id}"
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

            # Calculate holding_bars from holding_period and timeframe
            holding_bars = self._calculate_holding_bars(
                pattern.holding_period or "24h",
                pattern.timeframe
            )

            # Get target magnitude from API (REQUIRED - no fallback)
            target_name = pattern.target_name or "unknown"
            magnitude = pattern.target_magnitude
            if magnitude is None or magnitude <= 0:
                raise ValueError(
                    f"Pattern {pattern.name} missing target_magnitude from API. "
                    f"Target: {target_name}. API must provide this field."
                )

            # Convert magnitude to decimal for tp_pct (5% -> 0.05)
            tp_pct = magnitude / 100.0
            # SL = 3× TP (asymmetric, lets winners run, cuts big losses)
            # Pattern-discovery validates that the pattern has positive edge
            # so we want to stay in trades longer and only exit on big moves
            sl_pct = tp_pct * 3.0

            # For docstring display
            edge_pct = pattern.test_edge * 100
            sl_pct_display = magnitude * 3.0
            expected_profit = magnitude * edge_pct / 100  # magnitude × edge

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
                holding_period=pattern.holding_period or "24h",
                holding_bars=holding_bars,
                target_name=target_name,
                edge=edge_pct,
                win_rate=pattern.test_win_rate * 100,
                leverage=leverage,
                pattern_func_name=pattern_func_name,
                magnitude=magnitude,
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                sl_pct_display=sl_pct_display,
                expected_profit=expected_profit,
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
                generation_mode="pattern"  # From pattern-discovery API
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
        if 'class PatStrat_' not in code:
            errors.append("Missing PatStrat class definition")
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

    def _calculate_holding_bars(self, holding_period: str, timeframe: str) -> int:
        """
        Calculate holding period in bars based on timeframe.

        Args:
            holding_period: Period string like "4h", "24h"
            timeframe: Strategy timeframe like "15m", "1h", "4h"

        Returns:
            Number of bars for the holding period
        """
        # Parse holding period to hours
        period_lower = holding_period.lower()
        if period_lower.endswith('h'):
            hours = int(period_lower[:-1])
        elif period_lower.endswith('d'):
            hours = int(period_lower[:-1]) * 24
        else:
            hours = 24  # Default to 24h

        # Parse timeframe to minutes per bar
        tf_lower = timeframe.lower()
        if tf_lower.endswith('m'):
            minutes_per_bar = int(tf_lower[:-1])
        elif tf_lower.endswith('h'):
            minutes_per_bar = int(tf_lower[:-1]) * 60
        elif tf_lower.endswith('d'):
            minutes_per_bar = int(tf_lower[:-1]) * 24 * 60
        else:
            minutes_per_bar = 15  # Default to 15m

        # Calculate bars
        total_minutes = hours * 60
        bars = total_minutes // minutes_per_bar

        return max(1, bars)  # At least 1 bar
