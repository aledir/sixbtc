"""
Risk Calculator - Liquidation and Safe Leverage Calculations

Implements Hyperliquid liquidation formulas to prevent positions from being
liquidated before stop loss triggers.

Formulas from Hyperliquid docs:
- maintenance_margin_rate = 1 / (2 * max_leverage)
- LONG liq_price = entry * (1 - 1/leverage + maintenance_margin_rate)
- SHORT liq_price = entry * (1 + 1/leverage - maintenance_margin_rate)
"""

from typing import Tuple


def calculate_liquidation_price(
    entry_price: float,
    leverage: int,
    side: str,
    max_leverage: int,
) -> float:
    """
    Calculate estimated liquidation price for a leveraged position.

    Uses Hyperliquid formula for isolated margin, tier 0.
    Maintenance margin rate = 1 / (2 * max_leverage) per Hyperliquid docs.

    Args:
        entry_price: Entry price of position
        leverage: Leverage used for position (1-max_leverage)
        side: "long" or "short"
        max_leverage: Maximum leverage for the asset (determines maintenance margin)

    Returns:
        Estimated liquidation price

    Example:
        >>> calculate_liquidation_price(100.0, 10, "long", 40)
        90.125  # 10x long with 40x max → liq at ~90.125 (9.875% below entry)
    """
    if leverage <= 0:
        return 0.0
    if max_leverage <= 0:
        max_leverage = 20  # Conservative default

    # Maintenance margin rate depends on asset's max_leverage (tier 0)
    # Per Hyperliquid docs: maintenance_margin = initial_margin / 2
    # initial_margin = 1 / max_leverage
    # maintenance_margin_rate = 1 / (2 * max_leverage)
    maintenance_margin_rate = 1.0 / (2.0 * max_leverage)

    if side.lower() == "long":
        # Long positions liquidate when price drops
        liq_price = entry_price * (1.0 - 1.0 / leverage + maintenance_margin_rate)
    else:  # short
        # Short positions liquidate when price rises
        liq_price = entry_price * (1.0 + 1.0 / leverage - maintenance_margin_rate)

    return liq_price


def calculate_liquidation_distance_pct(
    leverage: int,
    max_leverage: int,
) -> float:
    """
    Calculate liquidation distance as percentage from entry.

    This is how far price can move against you before liquidation.

    Args:
        leverage: Leverage used
        max_leverage: Maximum leverage for the asset

    Returns:
        Liquidation distance as decimal (e.g., 0.10 = 10%)

    Example:
        >>> calculate_liquidation_distance_pct(10, 40)
        0.0875  # 10x with 40x max → liquidation at 8.75% move
    """
    if leverage <= 0:
        return 1.0  # No leverage = no liquidation risk
    if max_leverage <= 0:
        max_leverage = 20

    maintenance_margin_rate = 1.0 / (2.0 * max_leverage)
    liq_distance = 1.0 / leverage - maintenance_margin_rate

    return max(0.0, liq_distance)


def calculate_safe_leverage(
    sl_pct: float,
    max_leverage: int,
    buffer_pct: float = 10.0,
) -> int:
    """
    Calculate maximum safe leverage given a stop loss percentage.

    Ensures liquidation price is at least buffer_pct further from entry
    than the stop loss. This protects against liquidation before SL triggers.

    Args:
        sl_pct: Stop loss distance as decimal (e.g., 0.05 for 5%)
        max_leverage: Maximum leverage for the asset
        buffer_pct: Minimum buffer between SL and liquidation (default: 10%)

    Returns:
        Maximum safe leverage (integer, clamped between 1 and max_leverage)

    Example:
        >>> calculate_safe_leverage(0.12, 40, 10.0)
        6  # With 12% SL and 10% buffer, max safe leverage is 6x
    """
    if sl_pct <= 0:
        return 1  # Zero SL distance = use minimum leverage

    if max_leverage <= 0:
        max_leverage = 20

    # Required liquidation distance must be greater than SL distance + buffer
    # For 10% buffer: if SL is at 12%, liq must be at least at 13.33%
    required_liq_distance = sl_pct / (1.0 - buffer_pct / 100.0)

    # Maintenance margin rate for this asset
    maintenance_margin_rate = 1.0 / (2.0 * max_leverage)

    # Inverse formula to find leverage:
    # liq_distance = 1/leverage - maintenance_margin_rate
    # Therefore: leverage = 1 / (liq_distance + maintenance_margin_rate)
    denominator = required_liq_distance + maintenance_margin_rate

    if denominator <= 0:
        return 1  # Edge case protection

    safe_leverage = int(1.0 / denominator)

    # Clamp between 1 and max_leverage
    return max(1, min(safe_leverage, max_leverage))


def is_leverage_safe(
    sl_pct: float,
    leverage: int,
    max_leverage: int,
    buffer_pct: float = 10.0,
) -> Tuple[bool, int]:
    """
    Check if a leverage/SL combination is safe from liquidation.

    Args:
        sl_pct: Stop loss distance as decimal (e.g., 0.05 for 5%)
        leverage: Desired leverage
        max_leverage: Maximum leverage for the asset
        buffer_pct: Minimum buffer between SL and liquidation (default: 10%)

    Returns:
        Tuple of (is_safe, max_safe_leverage)

    Example:
        >>> is_leverage_safe(0.12, 20, 40, 10.0)
        (False, 6)  # 20x with 12% SL is NOT safe, max is 6x
    """
    safe_lev = calculate_safe_leverage(sl_pct, max_leverage, buffer_pct)
    return (leverage <= safe_lev, safe_lev)
