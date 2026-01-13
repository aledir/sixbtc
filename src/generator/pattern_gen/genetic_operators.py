"""
Genetic Operators for Pattern Evolution.

Implements selection, crossover, and mutation operators for
evolving trading patterns from the ACTIVE pool.
"""

import random
from dataclasses import dataclass, field
from typing import List, Optional

from src.generator.pattern_gen.building_blocks import (
    BLOCKS_BY_ID,
    get_block,
    get_blocks_by_category,
    get_compatible_blocks,
)


@dataclass
class GeneticIndividual:
    """Represents an individual in the genetic pool."""

    strategy_id: str
    blocks: List[str]           # ['RSI_OVERSOLD', 'VOLUME_SPIKE']
    params: dict                # Block parameters
    fitness: float              # Backtest score (0-100)
    direction: str              # 'long', 'short'
    timeframe: str
    parent_ids: List[str] = field(default_factory=list)  # Lineage tracking


def tournament_selection(
    pool: List[GeneticIndividual],
    tournament_size: int = 3,
    rng: Optional[random.Random] = None,
) -> GeneticIndividual:
    """
    Select individual via tournament selection.

    Picks tournament_size random individuals and returns the one
    with highest fitness. This provides selection pressure while
    maintaining diversity.

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


def roulette_selection(
    pool: List[GeneticIndividual],
    rng: Optional[random.Random] = None,
) -> GeneticIndividual:
    """
    Select individual via fitness-proportional (roulette) selection.

    Probability of selection is proportional to fitness.
    Better for maintaining diversity when fitness variance is high.

    Args:
        pool: List of individuals to select from
        rng: Optional random generator

    Returns:
        Selected individual
    """
    if rng is None:
        rng = random.Random()

    total_fitness = sum(max(0.1, ind.fitness) for ind in pool)
    pick = rng.uniform(0, total_fitness)

    current = 0
    for ind in pool:
        current += max(0.1, ind.fitness)
        if current >= pick:
            return ind

    return pool[-1]


def crossover_blocks(
    parent1: GeneticIndividual,
    parent2: GeneticIndividual,
    rng: Optional[random.Random] = None,
) -> List[str]:
    """
    Crossover: combine blocks from two parents.

    Strategies:
    - Uniform: randomly pick blocks from combined pool
    - Ensures result has 1-3 blocks
    - Filters for direction compatibility

    Args:
        parent1: First parent individual
        parent2: Second parent individual
        rng: Optional random generator

    Returns:
        List of block IDs for child
    """
    if rng is None:
        rng = random.Random()

    # Combine blocks from both parents (unique)
    all_blocks = list(set(parent1.blocks + parent2.blocks))

    if not all_blocks:
        return []

    # Take 1-3 blocks from combined pool
    n_blocks = rng.randint(1, min(3, len(all_blocks)))
    child_blocks = rng.sample(all_blocks, n_blocks)

    return child_blocks


def crossover_single_point(
    parent1: GeneticIndividual,
    parent2: GeneticIndividual,
    rng: Optional[random.Random] = None,
) -> List[str]:
    """
    Single-point crossover for blocks.

    Takes first N blocks from parent1, rest from parent2.

    Example:
        parent1: [A, B, C]
        parent2: [D, E]
        crossover_point = 1
        child: [A, E]

    Args:
        parent1: First parent
        parent2: Second parent
        rng: Optional random generator

    Returns:
        List of block IDs for child
    """
    if rng is None:
        rng = random.Random()

    blocks1 = parent1.blocks
    blocks2 = parent2.blocks

    if not blocks1 or not blocks2:
        return blocks1 or blocks2 or []

    # Crossover point
    max_point = min(len(blocks1), len(blocks2))
    if max_point <= 1:
        # Just pick from one parent
        return rng.choice([blocks1, blocks2])

    point = rng.randint(1, max_point - 1)

    # Take first part from parent1, second from parent2
    child_blocks = blocks1[:point] + blocks2[point:]

    # Limit to 3 blocks
    return child_blocks[:3]


def mutate_blocks(
    blocks: List[str],
    mutation_rate: float = 0.2,
    rng: Optional[random.Random] = None,
) -> List[str]:
    """
    Mutate block composition.

    Mutation operators:
    - Swap: replace block with compatible one from same category
    - Add: add a compatible block (if < 3 blocks)
    - Remove: remove a block (if > 1 block)

    Args:
        blocks: Current block IDs
        mutation_rate: Probability of mutation
        rng: Optional random generator

    Returns:
        Mutated block IDs (may be unchanged)
    """
    if rng is None:
        rng = random.Random()

    if rng.random() > mutation_rate:
        return blocks

    if not blocks:
        return blocks

    mutated = blocks.copy()
    mutation_type = rng.choice(['swap', 'add', 'remove'])

    if mutation_type == 'swap':
        # Replace one block with another from same category
        idx = rng.randint(0, len(mutated) - 1)
        old_block_id = mutated[idx]

        if old_block_id in BLOCKS_BY_ID:
            old_block = BLOCKS_BY_ID[old_block_id]
            compatible = get_blocks_by_category(old_block.category)

            # Filter to same direction
            compatible = [
                b for b in compatible
                if b.id != old_block_id and (
                    b.direction == old_block.direction or
                    b.direction == 'bidi' or
                    old_block.direction == 'bidi'
                )
            ]

            if compatible:
                new_block = rng.choice(compatible)
                mutated[idx] = new_block.id

    elif mutation_type == 'add' and len(mutated) < 3:
        # Add a compatible block
        if mutated[0] in BLOCKS_BY_ID:
            current_block = BLOCKS_BY_ID[mutated[0]]
            compatible = get_compatible_blocks(current_block)

            # Filter out already present blocks
            compatible = [b for b in compatible if b.id not in mutated]

            if compatible:
                new_block = rng.choice(compatible)
                mutated.append(new_block.id)

    elif mutation_type == 'remove' and len(mutated) > 1:
        # Remove a random block
        idx = rng.randint(0, len(mutated) - 1)
        mutated.pop(idx)

    return mutated


def mutate_params(
    params: dict,
    blocks: List[str],
    mutation_rate: float = 0.3,
    rng: Optional[random.Random] = None,
) -> dict:
    """
    Mutate parameter values within allowed ranges.

    For each parameter, with mutation_rate probability:
    - Numeric params: perturb by ±20%
    - Keep within block's allowed range if defined

    Args:
        params: Current parameters dict
        blocks: Block IDs (for getting allowed ranges)
        mutation_rate: Probability of mutating each param
        rng: Optional random generator

    Returns:
        Mutated parameters dict
    """
    if rng is None:
        rng = random.Random()

    mutated = params.copy()

    for key, value in list(mutated.items()):
        if rng.random() >= mutation_rate:
            continue

        if isinstance(value, (int, float)) and value != 0:
            # Perturb by ±20%
            delta = value * 0.2 * rng.choice([-1, 1])
            new_value = value + delta

            # For percentages, clamp to reasonable range
            if 'pct' in key.lower():
                new_value = max(0.01, min(0.50, new_value))
            elif isinstance(value, int):
                new_value = int(round(new_value))

            mutated[key] = new_value

    return mutated


def check_direction_compatibility(
    blocks: List[str],
    target_direction: str,
) -> bool:
    """
    Check if all blocks are compatible with target direction.

    Args:
        blocks: Block IDs to check
        target_direction: 'long', 'short', or 'bidi'

    Returns:
        True if all blocks are compatible
    """
    if target_direction == 'bidi':
        return True

    for block_id in blocks:
        if block_id not in BLOCKS_BY_ID:
            continue

        block = BLOCKS_BY_ID[block_id]
        if block.direction != 'bidi' and block.direction != target_direction:
            return False

    return True


def filter_pool_by_direction(
    pool: List[GeneticIndividual],
    direction: str,
) -> List[GeneticIndividual]:
    """
    Filter genetic pool by direction.

    Args:
        pool: Full genetic pool
        direction: Target direction ('long', 'short', 'bidi')

    Returns:
        Filtered pool with compatible individuals
    """
    if direction == 'bidi':
        return pool

    return [
        ind for ind in pool
        if ind.direction == direction or ind.direction == 'bidi'
    ]


def calculate_diversity(pool: List[GeneticIndividual]) -> float:
    """
    Calculate diversity metric for the pool.

    Higher diversity = more unique block combinations.

    Args:
        pool: Genetic pool

    Returns:
        Diversity score (0-1)
    """
    if len(pool) < 2:
        return 0.0

    # Count unique block combinations
    unique_combos = set()
    for ind in pool:
        combo = tuple(sorted(ind.blocks))
        unique_combos.add(combo)

    return len(unique_combos) / len(pool)
