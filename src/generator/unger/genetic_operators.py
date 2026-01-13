"""
Genetic Operators for Unger Strategy Evolution.

Implements selection, crossover, and mutation operators for
evolving Unger strategies from the ACTIVE pool.

Key differences from Pattern Genetics:
- Genes are component IDs (entry, filters, mechanism, configs)
- Compatibility rules between components must be respected
- Parameters are per-component, not per-formula
"""

import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from src.generator.unger.catalogs import (
    ALL_ENTRIES,
    ALL_FILTERS,
    EXIT_MECHANISMS,
    SL_CONFIGS,
    TP_CONFIGS,
    TRAILING_CONFIGS,
    EXIT_CONDITIONS,
    get_entry_by_id,
    get_filter_by_id,
    get_mechanism_by_id,
    get_sl_config_by_id,
    get_tp_config_by_id,
    get_trailing_config_by_id,
    get_exit_by_id,
    get_entries_by_direction,
    get_compatible_filters,
)


@dataclass
class UngerGeneticIndividual:
    """Represents an Unger strategy individual in the genetic pool."""

    strategy_id: str

    # Component IDs (the "genes")
    entry_id: str
    filter_ids: List[str]
    exit_mechanism_id: int
    sl_config_id: str
    tp_config_id: Optional[str]
    exit_condition_id: Optional[str]
    trailing_config_id: Optional[str]

    # Component parameters
    entry_params: dict
    filter_params: List[dict]
    sl_params: dict
    tp_params: Optional[dict]
    exit_params: Optional[dict]
    trailing_params: Optional[dict]

    # Metadata
    fitness: float              # Backtest score (0-100)
    direction: str              # 'LONG', 'SHORT', 'BIDI'
    timeframe: str
    entry_category: str = ""
    parent_ids: List[str] = field(default_factory=list)


def tournament_selection(
    pool: List[UngerGeneticIndividual],
    tournament_size: int = 3,
    rng: Optional[random.Random] = None,
) -> UngerGeneticIndividual:
    """
    Select individual via tournament selection.

    Picks tournament_size random individuals and returns the one
    with highest fitness.

    Args:
        pool: List of individuals to select from
        tournament_size: Number of individuals in tournament
        rng: Optional random generator for reproducibility

    Returns:
        Selected individual with highest fitness in tournament
    """
    if rng is None:
        rng = random.Random()

    tournament = rng.sample(pool, min(tournament_size, len(pool)))
    return max(tournament, key=lambda x: x.fitness)


def filter_pool_by_direction(
    pool: List[UngerGeneticIndividual],
    direction: str,
) -> List[UngerGeneticIndividual]:
    """
    Filter genetic pool by direction.

    Args:
        pool: Full genetic pool
        direction: Target direction ('LONG', 'SHORT', 'BIDI')

    Returns:
        Filtered pool with compatible individuals
    """
    if direction == 'BIDI':
        return pool

    return [
        ind for ind in pool
        if ind.direction == direction or ind.direction == 'BIDI'
    ]


def crossover_components(
    parent1: UngerGeneticIndividual,
    parent2: UngerGeneticIndividual,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """
    Crossover: combine components from two parents.

    Strategy:
    - Randomly pick entry from parent1 or parent2
    - Combine filters from both parents (max 2), validating compatibility
    - Randomly pick exit mechanism
    - Randomly pick SL/TP/TS configs

    Args:
        parent1: First parent individual
        parent2: Second parent individual
        rng: Optional random generator

    Returns:
        Dict with component IDs for child
    """
    if rng is None:
        rng = random.Random()

    # Entry: pick from one parent
    entry_parent = rng.choice([parent1, parent2])
    entry_id = entry_parent.entry_id
    entry_params = entry_parent.entry_params.copy()
    entry_category = entry_parent.entry_category

    # Get the entry object for compatibility check
    entry = get_entry_by_id(entry_id)

    # Filters: combine from both parents, max 2, but validate compatibility
    all_filter_ids = list(set(parent1.filter_ids + parent2.filter_ids))
    compatible_filter_ids = []

    if entry and all_filter_ids:
        # Get direction from entry
        direction = parent1.direction  # Both parents should have same direction
        # Validate each filter is compatible with selected entry
        for fid in all_filter_ids:
            f = get_filter_by_id(fid)
            if f:
                # Check indicator overlap
                if any(ind in entry.indicators_used for ind in f.indicators_used):
                    continue
                # Check direction compatibility
                if direction not in f.compatible_directions:
                    continue
                compatible_filter_ids.append(fid)

    # Select from compatible filters only
    if compatible_filter_ids:
        n_filters = rng.randint(0, min(2, len(compatible_filter_ids)))
        filter_ids = rng.sample(compatible_filter_ids, n_filters) if n_filters > 0 else []
    else:
        filter_ids = []

    # Get filter params from appropriate parent
    filter_params = []
    for fid in filter_ids:
        if fid in parent1.filter_ids:
            idx = parent1.filter_ids.index(fid)
            if idx < len(parent1.filter_params):
                filter_params.append(parent1.filter_params[idx].copy())
            else:
                filter_params.append({})
        elif fid in parent2.filter_ids:
            idx = parent2.filter_ids.index(fid)
            if idx < len(parent2.filter_params):
                filter_params.append(parent2.filter_params[idx].copy())
            else:
                filter_params.append({})
        else:
            filter_params.append({})

    # Exit mechanism: pick from one parent
    mechanism_parent = rng.choice([parent1, parent2])
    exit_mechanism_id = mechanism_parent.exit_mechanism_id

    # SL config: pick from one parent
    sl_parent = rng.choice([parent1, parent2])
    sl_config_id = sl_parent.sl_config_id
    sl_params = sl_parent.sl_params.copy()

    # TP config: pick from parent with TP or None
    tp_parents = [p for p in [parent1, parent2] if p.tp_config_id]
    if tp_parents:
        tp_parent = rng.choice(tp_parents)
        tp_config_id = tp_parent.tp_config_id
        tp_params = tp_parent.tp_params.copy() if tp_parent.tp_params else {}
    else:
        tp_config_id = None
        tp_params = None

    # Exit condition: pick from parent with EC or None
    ec_parents = [p for p in [parent1, parent2] if p.exit_condition_id]
    if ec_parents:
        ec_parent = rng.choice(ec_parents)
        exit_condition_id = ec_parent.exit_condition_id
        exit_params = ec_parent.exit_params.copy() if ec_parent.exit_params else {}
    else:
        exit_condition_id = None
        exit_params = None

    # Trailing config: pick from parent with TS or None
    ts_parents = [p for p in [parent1, parent2] if p.trailing_config_id]
    if ts_parents:
        ts_parent = rng.choice(ts_parents)
        trailing_config_id = ts_parent.trailing_config_id
        trailing_params = ts_parent.trailing_params.copy() if ts_parent.trailing_params else {}
    else:
        trailing_config_id = None
        trailing_params = None

    return {
        'entry_id': entry_id,
        'entry_params': entry_params,
        'entry_category': entry_category,
        'filter_ids': filter_ids,
        'filter_params': filter_params,
        'exit_mechanism_id': exit_mechanism_id,
        'sl_config_id': sl_config_id,
        'sl_params': sl_params,
        'tp_config_id': tp_config_id,
        'tp_params': tp_params,
        'exit_condition_id': exit_condition_id,
        'exit_params': exit_params,
        'trailing_config_id': trailing_config_id,
        'trailing_params': trailing_params,
    }


def mutate_entry(
    components: Dict[str, Any],
    direction: str,
    mutation_rate: float = 0.2,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """
    Mutate entry condition.

    Swaps entry with another compatible one from same category or direction.

    Args:
        components: Current component dict
        direction: Target direction
        mutation_rate: Probability of mutation
        rng: Optional random generator

    Returns:
        Mutated components dict
    """
    if rng is None:
        rng = random.Random()

    if rng.random() > mutation_rate:
        return components

    current_entry = get_entry_by_id(components['entry_id'])
    if not current_entry:
        return components

    # Get compatible entries (same direction or BIDI)
    compatible = get_entries_by_direction(direction)

    # Filter out current entry
    compatible = [e for e in compatible if e.id != components['entry_id']]

    if not compatible:
        return components

    # Pick random entry
    new_entry = rng.choice(compatible)

    # Update components
    mutated = components.copy()
    mutated['entry_id'] = new_entry.id
    mutated['entry_category'] = new_entry.category
    # Reset entry params to defaults (or empty)
    mutated['entry_params'] = {}

    return mutated


def mutate_filters(
    components: Dict[str, Any],
    direction: str,
    mutation_rate: float = 0.2,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """
    Mutate entry filters.

    Operations:
    - Add: add a compatible filter (if < 2)
    - Remove: remove a filter (if > 0)
    - Swap: replace filter with another compatible one

    Args:
        components: Current component dict
        direction: Target direction
        mutation_rate: Probability of mutation
        rng: Optional random generator

    Returns:
        Mutated components dict
    """
    if rng is None:
        rng = random.Random()

    if rng.random() > mutation_rate:
        return components

    mutated = components.copy()
    filter_ids = mutated['filter_ids'].copy()
    filter_params = mutated['filter_params'].copy()

    # Get current entry for compatibility
    entry = get_entry_by_id(mutated['entry_id'])
    if not entry:
        return components

    mutation_type = rng.choice(['add', 'remove', 'swap'])

    if mutation_type == 'add' and len(filter_ids) < 2:
        # Get compatible filters for this entry
        compatible = get_compatible_filters(entry, direction)
        # Filter out already used filters
        compatible = [f for f in compatible if f.id not in filter_ids]

        if compatible:
            new_filter = rng.choice(compatible)
            filter_ids.append(new_filter.id)
            filter_params.append({})

    elif mutation_type == 'remove' and len(filter_ids) > 0:
        idx = rng.randint(0, len(filter_ids) - 1)
        filter_ids.pop(idx)
        if idx < len(filter_params):
            filter_params.pop(idx)

    elif mutation_type == 'swap' and len(filter_ids) > 0:
        idx = rng.randint(0, len(filter_ids) - 1)
        # Get compatible filters
        compatible = get_compatible_filters(entry, direction)
        # Filter out current filter
        compatible = [f for f in compatible if f.id != filter_ids[idx]]

        if compatible:
            new_filter = rng.choice(compatible)
            filter_ids[idx] = new_filter.id
            filter_params[idx] = {}

    mutated['filter_ids'] = filter_ids
    mutated['filter_params'] = filter_params

    return mutated


def mutate_exit_mechanism(
    components: Dict[str, Any],
    mutation_rate: float = 0.2,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """
    Mutate exit mechanism.

    Swaps to another exit mechanism.

    Args:
        components: Current component dict
        mutation_rate: Probability of mutation
        rng: Optional random generator

    Returns:
        Mutated components dict
    """
    if rng is None:
        rng = random.Random()

    if rng.random() > mutation_rate:
        return components

    mutated = components.copy()

    # Pick different mechanism
    available = [m for m in EXIT_MECHANISMS if m.id != components['exit_mechanism_id']]
    if available:
        new_mechanism = rng.choice(available)
        mutated['exit_mechanism_id'] = new_mechanism.id

        # Adjust TP/EC/TS based on new mechanism
        if not new_mechanism.uses_tp:
            mutated['tp_config_id'] = None
            mutated['tp_params'] = None
        if not new_mechanism.uses_ec:
            mutated['exit_condition_id'] = None
            mutated['exit_params'] = None
        if not new_mechanism.uses_ts:
            mutated['trailing_config_id'] = None
            mutated['trailing_params'] = None

    return mutated


def mutate_configs(
    components: Dict[str, Any],
    mutation_rate: float = 0.2,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """
    Mutate SL/TP/TS configs.

    Swaps config type with another.

    Args:
        components: Current component dict
        mutation_rate: Probability of mutation
        rng: Optional random generator

    Returns:
        Mutated components dict
    """
    if rng is None:
        rng = random.Random()

    mutated = components.copy()

    # SL config mutation
    if rng.random() < mutation_rate:
        available = [c for c in SL_CONFIGS if c.id != components['sl_config_id']]
        if available:
            new_sl = rng.choice(available)
            mutated['sl_config_id'] = new_sl.id
            mutated['sl_params'] = {}

    # TP config mutation (if used)
    if components['tp_config_id'] and rng.random() < mutation_rate:
        available = [c for c in TP_CONFIGS if c.id != components['tp_config_id']]
        if available:
            new_tp = rng.choice(available)
            mutated['tp_config_id'] = new_tp.id
            mutated['tp_params'] = {}

    # Trailing config mutation (if used)
    if components['trailing_config_id'] and rng.random() < mutation_rate:
        available = [c for c in TRAILING_CONFIGS if c.id != components['trailing_config_id']]
        if available:
            new_ts = rng.choice(available)
            mutated['trailing_config_id'] = new_ts.id
            mutated['trailing_params'] = {}

    return mutated


def mutate_params(
    params: dict,
    mutation_rate: float = 0.3,
    rng: Optional[random.Random] = None,
) -> dict:
    """
    Mutate parameter values within reasonable ranges.

    For each parameter, with mutation_rate probability:
    - Numeric params: perturb by ±20%
    - Clamp percentages to [0.01, 0.50]

    Args:
        params: Current parameters dict
        mutation_rate: Probability of mutating each param
        rng: Optional random generator

    Returns:
        Mutated parameters dict
    """
    if rng is None:
        rng = random.Random()

    if not params:
        return params

    mutated = params.copy()

    for key, value in list(mutated.items()):
        if rng.random() >= mutation_rate:
            continue

        if isinstance(value, (int, float)) and value != 0:
            # Perturb by ±20%
            delta = value * 0.2 * rng.choice([-1, 1])
            new_value = value + delta

            # For percentages, clamp to reasonable range
            if 'pct' in key.lower() or 'mult' in key.lower():
                new_value = max(0.01, min(0.50, new_value))
            elif isinstance(value, int):
                new_value = max(1, int(round(new_value)))

            mutated[key] = new_value

    return mutated


def calculate_diversity(pool: List[UngerGeneticIndividual]) -> float:
    """
    Calculate diversity metric for the pool.

    Higher diversity = more unique component combinations.

    Args:
        pool: Genetic pool

    Returns:
        Diversity score (0-1)
    """
    if len(pool) < 2:
        return 0.0

    # Count unique component combinations
    unique_combos = set()
    for ind in pool:
        combo = (
            ind.entry_id,
            tuple(sorted(ind.filter_ids)),
            ind.exit_mechanism_id,
            ind.sl_config_id,
            ind.tp_config_id or '',
            ind.trailing_config_id or '',
        )
        unique_combos.add(combo)

    return len(unique_combos) / len(pool)
