"""
Target Selection for Execution-Aligned Trading

Selects the best target from pattern.target_results based on:
1. Edge quality (higher is better)
2. Execution type alignment (prefer touch_based for TP strategies)

The key insight is that pattern-discovery validates patterns against targets
that have different execution semantics:

- TOUCH-BASED targets (target_max_*): Check if price TOUCHES a level
  → Aligned with TP-based execution

- CLOSE-BASED targets (all others): Check price at CLOSE of period
  → Aligned with time-based execution

Using the correct execution style ensures the strategy captures
the validated edge of the pattern.
"""

from typing import Optional
from dataclasses import dataclass
import logging

from src.generator.pattern_fetcher import Pattern, TargetResult

logger = logging.getLogger(__name__)


@dataclass
class TargetSelection:
    """Result of target selection with derived execution parameters."""
    target: TargetResult
    execution_type: str
    tp_pct: float
    sl_pct: float
    exit_bars: int
    use_tp: bool


def select_best_target(
    pattern: Pattern,
    holding_bars: int,
    min_edge: float = 0.05,
    max_tier: int = 2,
    touch_preference_ratio: float = 0.80
) -> Optional[TargetSelection]:
    """
    Select best target for trading with smart preference for touch-based.

    Priority logic:
    1. Touch-based if edge >= 80% of best close-based (execution aligned)
    2. Close-based otherwise (significantly better edge justifies mismatch)

    This ensures we prefer execution-aligned targets unless there's a
    significant edge advantage in using a close-based target.

    Args:
        pattern: Pattern with target_results
        holding_bars: Holding period in bars
        min_edge: Minimum edge threshold (default 5%)
        max_tier: Maximum tier to consider (default 2 = tier 1 and 2)
        touch_preference_ratio: Prefer touch if edge >= this ratio of close (default 80%)

    Returns:
        TargetSelection with derived parameters, or None if no valid target
    """
    if not pattern.target_results:
        # Use pattern's main target as fallback
        return _create_selection_from_pattern(pattern, holding_bars)

    # Filter valid targets
    valid_targets = [
        t for t in pattern.target_results
        if (t.tier is not None and t.tier <= max_tier and t.edge >= min_edge)
    ]

    if not valid_targets:
        return _create_selection_from_pattern(pattern, holding_bars)

    # Separate by execution type
    touch_targets = [t for t in valid_targets if t.execution_type == 'touch_based']
    close_targets = [t for t in valid_targets if t.execution_type == 'close_based']

    best_touch = max(touch_targets, key=lambda t: t.edge) if touch_targets else None
    best_close = max(close_targets, key=lambda t: t.edge) if close_targets else None

    # Selection logic
    selected_target = None

    if best_touch and best_close:
        # Prefer touch_based if edge is at least 80% of close_based
        if best_touch.edge >= best_close.edge * touch_preference_ratio:
            selected_target = best_touch
            logger.info(
                f"Selected touch_based target {best_touch.target_name} "
                f"(edge={best_touch.edge:.1%}) over close_based "
                f"(edge={best_close.edge:.1%})"
            )
        else:
            selected_target = best_close
            logger.info(
                f"Selected close_based target {best_close.target_name} "
                f"(edge={best_close.edge:.1%}) - touch_based edge too low "
                f"({best_touch.edge:.1%})"
            )
    elif best_touch:
        selected_target = best_touch
        logger.info(f"Selected touch_based target {best_touch.target_name} (only type available)")
    elif best_close:
        selected_target = best_close
        logger.info(f"Selected close_based target {best_close.target_name} (only type available)")

    if not selected_target:
        return _create_selection_from_pattern(pattern, holding_bars)

    return _derive_parameters(selected_target, holding_bars)


def _derive_parameters(target: TargetResult, holding_bars: int) -> TargetSelection:
    """
    Derive execution parameters from target.

    Touch-based targets:
    - Use TP at target magnitude (pattern predicts price will TOUCH level)
    - SL at 2× TP for 2:1 risk/reward
    - Exit bars as backstop

    Close-based targets:
    - No TP (pattern predicts price at CLOSE of period)
    - Wider SL for price breathing room during holding period
    - Exit bars as primary exit mechanism
    """
    magnitude = target.magnitude or 2.0  # Default 2% if missing
    execution_type = target.execution_type

    if execution_type == 'touch_based':
        # TP-BASED EXECUTION
        # Pattern predicts price will TOUCH level within window
        tp_pct = magnitude / 100.0
        sl_pct = tp_pct * 2.0  # 2:1 SL:TP ratio
        exit_bars = holding_bars  # Backstop if TP not hit
        use_tp = True
    else:
        # TIME-BASED EXECUTION
        # Pattern predicts price will CLOSE at level at end of window
        tp_pct = 0.0  # No TP - let time exit do the work
        sl_pct = (magnitude / 100.0) * 3.0  # Wider SL for breathing room
        exit_bars = holding_bars  # Primary exit mechanism
        use_tp = False

    return TargetSelection(
        target=target,
        execution_type=execution_type,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        exit_bars=exit_bars,
        use_tp=use_tp,
    )


def _create_selection_from_pattern(pattern: Pattern, holding_bars: int) -> TargetSelection:
    """
    Fallback: create selection from pattern's main target.

    Used when pattern has no target_results or no valid targets pass filters.
    """
    # Create a synthetic TargetResult from pattern
    target = TargetResult(
        target_name=pattern.target_name,
        tier=pattern.tier,
        edge=pattern.test_edge,
        win_rate=pattern.test_win_rate,
        n_signals=pattern.test_n_signals,
        direction=pattern.target_direction,
        hold_hours=int(holding_bars * 15 / 60),  # Assuming 15m timeframe
        magnitude=pattern.target_magnitude,
        execution_type=pattern.execution_type,
    )
    return _derive_parameters(target, holding_bars)
