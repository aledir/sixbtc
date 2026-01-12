"""
11 Exit Mechanisms - combinations of TP/EC/TS with AND/OR logic.

Each mechanism defines which exit components are used and how they combine.
SL is always required and not part of the mechanism logic.
"""

from dataclasses import dataclass


@dataclass
class ExitMechanism:
    """Definition of an exit mechanism (combination of exit components)."""

    id: int                     # 1-11
    name: str                   # e.g., "TP Only"
    uses_tp: bool               # Whether Take Profit is used
    uses_ec: bool               # Whether Exit Condition is used
    uses_ts: bool               # Whether Trailing Stop is used
    logic: str                  # Logic operator: "-", "OR", "AND", "(TP^EC)vTS", etc.
    description: str            # Human-readable description


# =============================================================================
# EXIT MECHANISMS (11)
# =============================================================================

EXIT_MECHANISMS = [
    # Single component mechanisms (3)
    ExitMechanism(
        id=1,
        name="TP Only",
        uses_tp=True,
        uses_ec=False,
        uses_ts=False,
        logic="-",
        description="Exit only at fixed target",
    ),
    ExitMechanism(
        id=2,
        name="EC Only",
        uses_tp=False,
        uses_ec=True,
        uses_ts=False,
        logic="-",
        description="Exit only on dynamic conditions",
    ),
    ExitMechanism(
        id=3,
        name="TS Only",
        uses_tp=False,
        uses_ec=False,
        uses_ts=True,
        logic="-",
        description="Exit only via trailing stop",
    ),

    # Two component mechanisms (5)
    ExitMechanism(
        id=4,
        name="TP or EC",
        uses_tp=True,
        uses_ec=True,
        uses_ts=False,
        logic="OR",
        description="Exit at target or on condition (first hit)",
    ),
    ExitMechanism(
        id=5,
        name="TP and EC",
        uses_tp=True,
        uses_ec=True,
        uses_ts=False,
        logic="AND",
        description="Exit at target only if condition is true",
    ),
    ExitMechanism(
        id=6,
        name="TP or TS",
        uses_tp=True,
        uses_ec=False,
        uses_ts=True,
        logic="OR",
        description="Exit at target or via trailing (first hit)",
    ),
    ExitMechanism(
        id=7,
        name="EC or TS",
        uses_tp=False,
        uses_ec=True,
        uses_ts=True,
        logic="OR",
        description="Exit on condition or via trailing (first hit)",
    ),
    ExitMechanism(
        id=8,
        name="EC and TS",
        uses_tp=False,
        uses_ec=True,
        uses_ts=True,
        logic="AND",
        description="Trailing exits only if condition is true",
    ),

    # Three component mechanisms (3)
    ExitMechanism(
        id=9,
        name="All OR",
        uses_tp=True,
        uses_ec=True,
        uses_ts=True,
        logic="OR OR",
        description="Exit on any of the three (first hit)",
    ),
    ExitMechanism(
        id=10,
        name="(TP and EC) or TS",
        uses_tp=True,
        uses_ec=True,
        uses_ts=True,
        logic="(TP^EC)vTS",
        description="TP requires EC true, or trailing exits",
    ),
    ExitMechanism(
        id=11,
        name="(EC and TS) or TP",
        uses_tp=True,
        uses_ec=True,
        uses_ts=True,
        logic="(EC^TS)vTP",
        description="Trailing requires EC true, or TP exits",
    ),
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_mechanism_by_id(mech_id: int) -> ExitMechanism | None:
    """Get a specific mechanism by ID."""
    for m in EXIT_MECHANISMS:
        if m.id == mech_id:
            return m
    return None


def get_mechanisms_with_tp() -> list[ExitMechanism]:
    """Get all mechanisms that use Take Profit."""
    return [m for m in EXIT_MECHANISMS if m.uses_tp]


def get_mechanisms_with_ec() -> list[ExitMechanism]:
    """Get all mechanisms that use Exit Conditions."""
    return [m for m in EXIT_MECHANISMS if m.uses_ec]


def get_mechanisms_with_ts() -> list[ExitMechanism]:
    """Get all mechanisms that use Trailing Stop."""
    return [m for m in EXIT_MECHANISMS if m.uses_ts]


def get_simple_mechanisms() -> list[ExitMechanism]:
    """Get single-component mechanisms (simpler to implement/test)."""
    return [m for m in EXIT_MECHANISMS if m.id <= 3]


def get_or_mechanisms() -> list[ExitMechanism]:
    """Get mechanisms with OR logic (first hit wins)."""
    return [m for m in EXIT_MECHANISMS if "OR" in m.logic or m.logic == "-"]
