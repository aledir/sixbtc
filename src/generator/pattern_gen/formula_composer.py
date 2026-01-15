"""
Formula Composer - Combines building blocks into complete trading formulas.

Composition methods:
- 50% Parametric: Single block with varied parameter combinations
- 30% Template: Combine 2-3 compatible blocks with AND logic
- 20% Innovative: Sequential, statistical, volatility patterns

Handles deduplication via formula hash (SHA256 of normalized formula).
"""

import hashlib
import itertools
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from src.generator.pattern_gen.building_blocks import (
    ALL_BLOCKS,
    BLOCKS_BY_CATEGORY,
    BLOCKS_BY_ID,
    PatternBlock,
    get_block,
    get_blocks_by_direction,
    get_compatible_blocks,
)
from src.generator.strategy_types import migrate_old_type


@dataclass
class ComposedFormula:
    """Result of composing building blocks into a formula."""

    formula_id: str                     # Unique identifier (hash)
    name: str                           # Human-readable name
    composition_type: str               # 'parametric', 'template', 'innovative'
    indicator_code: str                 # Code to calculate indicators
    entry_signal_code: str              # Code to compute entry_signal boolean
    blocks_used: List[str]              # Block IDs used
    params: Dict[str, Any]              # Parameter values used
    direction: str                      # 'long', 'short', 'bidi'
    lookback: int                       # Maximum lookback required
    indicators: List[str] = field(default_factory=list)  # Indicators needed
    strategy_type: str = "THR"          # Strategy type code

    # BIDI support: separate LONG/SHORT code (only used when direction='bidi' and is_bidi=True)
    is_bidi: bool = False               # True if using separate LONG/SHORT entry conditions
    indicator_code_long: str = ""       # Code for LONG indicator calculations
    indicator_code_short: str = ""      # Code for SHORT indicator calculations
    entry_signal_code_long: str = ""    # Code for LONG entry signal
    entry_signal_code_short: str = ""   # Code for SHORT entry signal
    blocks_used_long: List[str] = field(default_factory=list)   # Block IDs for LONG
    blocks_used_short: List[str] = field(default_factory=list)  # Block IDs for SHORT


class FormulaComposer:
    """
    Composes building blocks into trading formulas.

    Maintains deduplication cache to avoid generating duplicate formulas.
    """

    def __init__(self, seed: Optional[int] = None):
        """Initialize composer with optional random seed."""
        self.generated_hashes: Set[str] = set()
        self.rng = random.Random(seed)

    def compose_all(
        self,
        parametric_count: int,
        template_count: int,
        innovative_count: int,
        direction: str = "bidi",
    ) -> List[ComposedFormula]:
        """
        Compose formulas using all three methods.

        Args:
            parametric_count: Number of parametric formulas
            template_count: Number of template formulas
            innovative_count: Number of innovative formulas
            direction: Filter by direction ('long', 'short', 'bidi')

        Returns:
            List of composed formulas (deduplicated)
        """
        formulas = []
        formulas.extend(self.compose_parametric(parametric_count, direction))
        formulas.extend(self.compose_template(template_count, direction))
        formulas.extend(self.compose_innovative(innovative_count, direction))
        return formulas

    def compose_bidi(self, count: int = 1) -> List[ComposedFormula]:
        """
        Compose BIDI formulas with separate LONG and SHORT entry conditions.

        BIDI strategies have two independent entry logics:
        - LONG block (e.g., RSI oversold, breakout high)
        - SHORT block (e.g., RSI overbought, breakout low)

        The strategy generates long_signal and short_signal separately,
        and entry_signal = long_signal | short_signal.

        Args:
            count: Number of formulas to generate

        Returns:
            List of ComposedFormula with is_bidi=True and separate codes
        """
        formulas = []

        # Get blocks that work for LONG direction
        long_blocks = get_blocks_by_direction('long')
        self.rng.shuffle(long_blocks)

        # Get blocks that work for SHORT direction
        short_blocks = get_blocks_by_direction('short')
        self.rng.shuffle(short_blocks)

        if not long_blocks or not short_blocks:
            return formulas

        for i in range(min(count, len(long_blocks))):
            long_block = long_blocks[i % len(long_blocks)]

            # Try to find a SHORT block from the same category for coherence
            same_category_short = [
                b for b in short_blocks if b.category == long_block.category
            ]
            if same_category_short:
                short_block = self.rng.choice(same_category_short)
            else:
                short_block = short_blocks[i % len(short_blocks)]

            formula = self._compose_bidi_pair(long_block, short_block)
            if formula and self._is_unique(formula):
                formulas.append(formula)
                self.generated_hashes.add(formula.formula_id)

            if len(formulas) >= count:
                break

        return formulas

    def _compose_bidi_pair(
        self,
        long_block: PatternBlock,
        short_block: PatternBlock,
    ) -> Optional[ComposedFormula]:
        """
        Compose a BIDI formula from separate LONG and SHORT blocks.

        Args:
            long_block: Block for LONG entry
            short_block: Block for SHORT entry

        Returns:
            ComposedFormula with is_bidi=True
        """
        params_long = self._get_random_params(long_block)
        params_short = self._get_random_params(short_block)

        try:
            code_long = long_block.formula_template.format(**params_long)
            code_short = short_block.formula_template.format(**params_short)

            # Parse both codes
            ind_long, sig_long = self._split_indicator_signal(code_long)
            ind_short, sig_short = self._split_indicator_signal(code_short)

            # Rename entry_signal to long_entry in LONG code
            ind_long = ind_long.replace("df['entry_signal']", "df['long_entry']")
            sig_long = sig_long.replace("df['entry_signal']", "df['long_entry']")

            # Rename entry_signal to short_entry in SHORT code
            ind_short = ind_short.replace("df['entry_signal']", "df['short_entry']")
            sig_short = sig_short.replace("df['entry_signal']", "df['short_entry']")

            # Combined indicator code (both LONG and SHORT)
            combined_indicator = f"# === LONG Indicators ({long_block.name}) ===\n{ind_long}\n\n# === SHORT Indicators ({short_block.name}) ===\n{ind_short}"

            # Combined signal code
            combined_signal = f"""{sig_long}
{sig_short}
df['long_signal'] = df['long_entry'].fillna(False).astype(bool)
df['short_signal'] = df['short_entry'].fillna(False).astype(bool)
df['entry_signal'] = df['long_signal'] | df['short_signal']"""

            # Build name
            name = f"BIDI: {long_block.name} / {short_block.name}"

            full_code = f"{combined_indicator}\n{combined_signal}"

            return ComposedFormula(
                formula_id=self._compute_hash(full_code),
                name=name,
                composition_type="bidi",
                indicator_code=combined_indicator,
                entry_signal_code=combined_signal,
                blocks_used=[long_block.id, short_block.id],
                params={**params_long, **params_short},
                direction="bidi",
                lookback=max(long_block.lookback, short_block.lookback),
                indicators=list(set(long_block.indicators + short_block.indicators)),
                strategy_type=migrate_old_type(long_block.strategy_type).value,
                # BIDI-specific fields
                is_bidi=True,
                indicator_code_long=ind_long,
                indicator_code_short=ind_short,
                entry_signal_code_long=sig_long,
                entry_signal_code_short=sig_short,
                blocks_used_long=[long_block.id],
                blocks_used_short=[short_block.id],
            )
        except (KeyError, ValueError):
            return None

    def compose_parametric(
        self,
        count: int,
        direction: str = "bidi",
    ) -> List[ComposedFormula]:
        """
        Compose parametric formulas (single block with varied parameters).

        This generates many formulas from each block by varying its parameters.

        Args:
            count: Maximum number of formulas to generate
            direction: Filter blocks by direction

        Returns:
            List of unique composed formulas
        """
        formulas = []
        blocks = get_blocks_by_direction(direction)
        self.rng.shuffle(blocks)

        for block in blocks:
            if len(formulas) >= count:
                break

            # Generate all parameter combinations for this block
            param_combos = self._get_param_combinations(block)
            self.rng.shuffle(param_combos)

            for params in param_combos:
                if len(formulas) >= count:
                    break

                formula = self._compose_single_block(block, params)
                if formula and self._is_unique(formula):
                    formulas.append(formula)
                    self.generated_hashes.add(formula.formula_id)

        return formulas

    def compose_template(
        self,
        count: int,
        direction: str = "bidi",
    ) -> List[ComposedFormula]:
        """
        Compose template formulas (2-3 compatible blocks combined with AND).

        Args:
            count: Maximum number of formulas to generate
            direction: Filter by direction

        Returns:
            List of unique composed formulas
        """
        formulas = []
        blocks = get_blocks_by_direction(direction)
        self.rng.shuffle(blocks)

        for primary_block in blocks:
            if len(formulas) >= count:
                break

            compatible = get_compatible_blocks(primary_block)
            if not compatible:
                continue

            # Try 2-block combinations
            for secondary_block in self.rng.sample(
                compatible, min(5, len(compatible))
            ):
                if len(formulas) >= count:
                    break

                formula = self._compose_two_blocks(
                    primary_block, secondary_block
                )
                if formula and self._is_unique(formula):
                    formulas.append(formula)
                    self.generated_hashes.add(formula.formula_id)

            # Try 3-block combinations (less frequently)
            if len(compatible) >= 2 and self.rng.random() < 0.3:
                tertiary_candidates = [
                    b for b in compatible
                    if b.id != primary_block.id
                ]
                if len(tertiary_candidates) >= 2:
                    pair = self.rng.sample(tertiary_candidates, 2)
                    formula = self._compose_three_blocks(
                        primary_block, pair[0], pair[1]
                    )
                    if formula and self._is_unique(formula):
                        formulas.append(formula)
                        self.generated_hashes.add(formula.formula_id)

        return formulas

    def compose_innovative(
        self,
        count: int,
        direction: str = "bidi",
    ) -> List[ComposedFormula]:
        """
        Compose innovative formulas (sequential, statistical, volatility).

        These are more complex patterns that don't fit parametric/template.

        Args:
            count: Maximum number of formulas to generate
            direction: Filter by direction

        Returns:
            List of unique composed formulas
        """
        formulas = []

        # Sequential patterns (condition followed by another)
        seq_count = count // 3
        formulas.extend(self._compose_sequential(seq_count, direction))

        # Multi-timeframe inspired (different lookbacks)
        mtf_count = count // 3
        formulas.extend(self._compose_multi_lookback(mtf_count, direction))

        # Volatility regime filters
        vol_count = count - len(formulas)
        formulas.extend(self._compose_volatility_regime(vol_count, direction))

        return formulas[:count]

    def _compose_single_block(
        self,
        block: PatternBlock,
        params: Dict[str, Any],
    ) -> Optional[ComposedFormula]:
        """Compose a formula from a single block with given parameters."""
        try:
            # Format the formula template with parameters
            formula_code = block.formula_template.format(**params)

            # Split into indicator calculation and entry signal
            lines = formula_code.strip().split('\n')
            indicator_lines = []
            signal_lines = []

            for line in lines:
                if 'entry_signal' in line:
                    signal_lines.append(line)
                else:
                    indicator_lines.append(line)

            indicator_code = '\n'.join(indicator_lines)
            entry_signal_code = '\n'.join(signal_lines)

            # Determine direction (keep bidi as-is for template to handle)
            formula_direction = block.direction

            # Build param string for name
            param_str = "_".join(f"{k}{v}" for k, v in sorted(params.items()))

            return ComposedFormula(
                formula_id=self._compute_hash(formula_code),
                name=f"{block.name} ({param_str})",
                composition_type="parametric",
                indicator_code=indicator_code,
                entry_signal_code=entry_signal_code,
                blocks_used=[block.id],
                params=params,
                direction=formula_direction,
                lookback=block.lookback,
                indicators=block.indicators.copy(),
                strategy_type=migrate_old_type(block.strategy_type).value,
            )
        except (KeyError, ValueError):
            return None

    def _compose_two_blocks(
        self,
        block1: PatternBlock,
        block2: PatternBlock,
    ) -> Optional[ComposedFormula]:
        """Compose a formula from two blocks with AND logic."""
        # Pick random params for each block
        params1 = self._get_random_params(block1)
        params2 = self._get_random_params(block2)

        try:
            code1 = block1.formula_template.format(**params1)
            code2 = block2.formula_template.format(**params2)

            # Parse both codes
            ind1, sig1 = self._split_indicator_signal(code1)
            ind2, sig2 = self._split_indicator_signal(code2)

            # Rename entry_signal in first block to entry_cond1
            ind1 = ind1.replace("df['entry_signal']", "df['entry_cond1']")
            sig1 = sig1.replace("df['entry_signal']", "df['entry_cond1']")

            # Rename entry_signal in second block to entry_cond2
            ind2 = ind2.replace("df['entry_signal']", "df['entry_cond2']")
            sig2 = sig2.replace("df['entry_signal']", "df['entry_cond2']")

            # Combine indicators
            indicator_code = f"{ind1}\n{ind2}"

            # Combine signals with AND
            entry_signal_code = f"""{sig1}
{sig2}
df['entry_signal'] = df['entry_cond1'] & df['entry_cond2']"""

            # Determine direction (keep bidi as-is for template to handle)
            if block1.direction == block2.direction:
                direction = block1.direction
            elif block1.direction == "bidi":
                direction = block2.direction
            elif block2.direction == "bidi":
                direction = block1.direction
            else:
                return None  # Incompatible directions
            # Note: bidi is preserved for template to split into long/short

            # Determine strategy type (use primary block's type, migrated to unified 5 types)
            strategy_type = migrate_old_type(block1.strategy_type).value

            # Build name
            name = f"{block1.name} + {block2.name}"

            full_code = f"{indicator_code}\n{entry_signal_code}"

            return ComposedFormula(
                formula_id=self._compute_hash(full_code),
                name=name,
                composition_type="template",
                indicator_code=indicator_code,
                entry_signal_code=entry_signal_code,
                blocks_used=[block1.id, block2.id],
                params={**params1, **params2},
                direction=direction,
                lookback=max(block1.lookback, block2.lookback),
                indicators=list(set(block1.indicators + block2.indicators)),
                strategy_type=strategy_type,
            )
        except (KeyError, ValueError):
            return None

    def _compose_three_blocks(
        self,
        block1: PatternBlock,
        block2: PatternBlock,
        block3: PatternBlock,
    ) -> Optional[ComposedFormula]:
        """Compose a formula from three blocks with AND logic."""
        params1 = self._get_random_params(block1)
        params2 = self._get_random_params(block2)
        params3 = self._get_random_params(block3)

        try:
            code1 = block1.formula_template.format(**params1)
            code2 = block2.formula_template.format(**params2)
            code3 = block3.formula_template.format(**params3)

            ind1, sig1 = self._split_indicator_signal(code1)
            ind2, sig2 = self._split_indicator_signal(code2)
            ind3, sig3 = self._split_indicator_signal(code3)

            # Rename signals
            ind1 = ind1.replace("df['entry_signal']", "df['entry_cond1']")
            sig1 = sig1.replace("df['entry_signal']", "df['entry_cond1']")
            ind2 = ind2.replace("df['entry_signal']", "df['entry_cond2']")
            sig2 = sig2.replace("df['entry_signal']", "df['entry_cond2']")
            ind3 = ind3.replace("df['entry_signal']", "df['entry_cond3']")
            sig3 = sig3.replace("df['entry_signal']", "df['entry_cond3']")

            indicator_code = f"{ind1}\n{ind2}\n{ind3}"
            entry_signal_code = f"""{sig1}
{sig2}
{sig3}
df['entry_signal'] = df['entry_cond1'] & df['entry_cond2'] & df['entry_cond3']"""

            # Determine direction (keep bidi as-is for template to handle)
            directions = [block1.direction, block2.direction, block3.direction]
            non_bidi = [d for d in directions if d != "bidi"]
            if non_bidi:
                if len(set(non_bidi)) > 1:
                    return None  # Conflicting directions
                direction = non_bidi[0]
            else:
                direction = "bidi"  # All blocks are bidi

            name = f"{block1.name} + {block2.name} + {block3.name}"
            full_code = f"{indicator_code}\n{entry_signal_code}"

            return ComposedFormula(
                formula_id=self._compute_hash(full_code),
                name=name,
                composition_type="template",
                indicator_code=indicator_code,
                entry_signal_code=entry_signal_code,
                blocks_used=[block1.id, block2.id, block3.id],
                params={**params1, **params2, **params3},
                direction=direction,
                lookback=max(block1.lookback, block2.lookback, block3.lookback),
                indicators=list(set(
                    block1.indicators + block2.indicators + block3.indicators
                )),
                strategy_type=migrate_old_type(block1.strategy_type).value,
            )
        except (KeyError, ValueError):
            return None

    def _compose_sequential(
        self,
        count: int,
        direction: str,
    ) -> List[ComposedFormula]:
        """
        Compose sequential patterns (condition must occur within N bars).

        Example: RSI oversold that was preceded by a volume spike.
        """
        formulas = []
        blocks = get_blocks_by_direction(direction)
        self.rng.shuffle(blocks)

        lookback_windows = [3, 5, 10]

        for block in blocks:
            if len(formulas) >= count:
                break

            compatible = get_compatible_blocks(block)
            if not compatible:
                continue

            for secondary in self.rng.sample(compatible, min(3, len(compatible))):
                if len(formulas) >= count:
                    break

                for window in lookback_windows:
                    formula = self._compose_sequential_pair(
                        block, secondary, window
                    )
                    if formula and self._is_unique(formula):
                        formulas.append(formula)
                        self.generated_hashes.add(formula.formula_id)
                        break

        return formulas

    def _compose_sequential_pair(
        self,
        primary: PatternBlock,
        secondary: PatternBlock,
        window: int,
    ) -> Optional[ComposedFormula]:
        """Create a sequential pattern: secondary occurred within window bars before primary."""
        params1 = self._get_random_params(primary)
        params2 = self._get_random_params(secondary)

        try:
            code1 = primary.formula_template.format(**params1)
            code2 = secondary.formula_template.format(**params2)

            ind1, sig1 = self._split_indicator_signal(code1)
            ind2, sig2 = self._split_indicator_signal(code2)

            # Rename
            ind1 = ind1.replace("df['entry_signal']", "df['primary_cond']")
            sig1 = sig1.replace("df['entry_signal']", "df['primary_cond']")
            ind2 = ind2.replace("df['entry_signal']", "df['secondary_cond']")
            sig2 = sig2.replace("df['entry_signal']", "df['secondary_cond']")

            indicator_code = f"{ind1}\n{ind2}"

            # Sequential logic: secondary occurred in last N bars
            entry_signal_code = f"""{sig1}
{sig2}
df['secondary_recent'] = df['secondary_cond'].rolling({window}).max().fillna(0).astype(bool)
df['entry_signal'] = df['primary_cond'] & df['secondary_recent']"""

            # Direction logic (keep bidi as-is for template to handle)
            if primary.direction == secondary.direction:
                direction = primary.direction
            elif primary.direction == "bidi":
                direction = secondary.direction
            elif secondary.direction == "bidi":
                direction = primary.direction
            else:
                return None
            # Note: bidi is preserved for template to split into long/short

            name = f"{primary.name} after {secondary.name} ({window}bar)"
            full_code = f"{indicator_code}\n{entry_signal_code}"

            return ComposedFormula(
                formula_id=self._compute_hash(full_code),
                name=name,
                composition_type="innovative",
                indicator_code=indicator_code,
                entry_signal_code=entry_signal_code,
                blocks_used=[primary.id, secondary.id],
                params={**params1, **params2, "window": window},
                direction=direction,
                lookback=max(primary.lookback, secondary.lookback) + window,
                indicators=list(set(primary.indicators + secondary.indicators)),
                strategy_type=migrate_old_type(primary.strategy_type).value,
            )
        except (KeyError, ValueError):
            return None

    def _compose_multi_lookback(
        self,
        count: int,
        direction: str,
    ) -> List[ComposedFormula]:
        """
        Compose patterns with multiple lookback periods (pseudo multi-timeframe).

        Example: RSI oversold on both short and long period.
        """
        formulas = []

        # Focus on threshold blocks that have period parameter
        threshold_blocks = [
            b for b in BLOCKS_BY_CATEGORY.get("threshold", [])
            if "period" in b.params and (
                direction == "bidi" or b.direction == direction or b.direction == "bidi"
            )
        ]

        for block in threshold_blocks:
            if len(formulas) >= count:
                break

            periods = block.params.get("period", [])
            if len(periods) < 2:
                continue

            # Create short/long period combinations
            for short_p in periods[:2]:
                for long_p in periods[-2:]:
                    if short_p >= long_p:
                        continue

                    formula = self._compose_dual_period(block, short_p, long_p)
                    if formula and self._is_unique(formula):
                        formulas.append(formula)
                        self.generated_hashes.add(formula.formula_id)

                    if len(formulas) >= count:
                        break

        return formulas

    def _compose_dual_period(
        self,
        block: PatternBlock,
        short_period: int,
        long_period: int,
    ) -> Optional[ComposedFormula]:
        """Create a dual-period variant of a threshold block."""
        try:
            # Get threshold params
            thresholds = block.params.get("threshold", [30])
            threshold = self.rng.choice(thresholds)

            # Create params for both periods
            base_params = {k: v[0] if isinstance(v, list) else v
                         for k, v in block.params.items() if k not in ("period", "threshold")}

            params_short = {**base_params, "period": short_period, "threshold": threshold}
            params_long = {**base_params, "period": long_period, "threshold": threshold}

            code_short = block.formula_template.format(**params_short)
            code_long = block.formula_template.format(**params_long)

            # Rename columns to avoid collision
            code_short = code_short.replace(
                "df['entry_signal']", "df['short_cond']"
            ).replace(
                f"df['{block.indicators[0] if block.indicators else 'ind'}']",
                f"df['{block.indicators[0] if block.indicators else 'ind'}_short']"
            )
            code_long = code_long.replace(
                "df['entry_signal']", "df['long_cond']"
            ).replace(
                f"df['{block.indicators[0] if block.indicators else 'ind'}']",
                f"df['{block.indicators[0] if block.indicators else 'ind'}_long']"
            )

            ind_short, sig_short = self._split_indicator_signal(code_short)
            ind_long, sig_long = self._split_indicator_signal(code_long)

            indicator_code = f"# Short period ({short_period})\n{ind_short}\n# Long period ({long_period})\n{ind_long}"
            entry_signal_code = f"""{sig_short}
{sig_long}
df['entry_signal'] = df['short_cond'] & df['long_cond']"""

            # Keep bidi as-is for template to handle
            direction = block.direction
            name = f"{block.name} dual ({short_period}/{long_period})"
            full_code = f"{indicator_code}\n{entry_signal_code}"

            return ComposedFormula(
                formula_id=self._compute_hash(full_code),
                name=name,
                composition_type="innovative",
                indicator_code=indicator_code,
                entry_signal_code=entry_signal_code,
                blocks_used=[block.id],
                params={"short_period": short_period, "long_period": long_period, "threshold": threshold},
                direction=direction,
                lookback=long_period + 20,
                indicators=block.indicators.copy(),
                strategy_type=migrate_old_type(block.strategy_type).value,
            )
        except (KeyError, ValueError):
            return None

    def _compose_volatility_regime(
        self,
        count: int,
        direction: str,
    ) -> List[ComposedFormula]:
        """
        Compose patterns with volatility regime filter.

        Add ATR squeeze/expansion as filter to other patterns.
        """
        formulas = []

        # Get ATR blocks
        atr_blocks = [b for b in ALL_BLOCKS if b.id in ("ATR_SQUEEZE", "ATR_EXPANSION")]
        if not atr_blocks:
            return formulas

        # Get entry blocks
        entry_blocks = get_blocks_by_direction(direction)
        entry_blocks = [b for b in entry_blocks if b.category in ("threshold", "crossover")]
        self.rng.shuffle(entry_blocks)

        for entry_block in entry_blocks:
            if len(formulas) >= count:
                break

            for atr_block in atr_blocks:
                formula = self._compose_two_blocks(entry_block, atr_block)
                if formula and self._is_unique(formula):
                    formula.name = f"{entry_block.name} in {atr_block.name}"
                    formula.composition_type = "innovative"
                    formulas.append(formula)
                    self.generated_hashes.add(formula.formula_id)

                if len(formulas) >= count:
                    break

        return formulas

    def _get_param_combinations(self, block: PatternBlock) -> List[Dict[str, Any]]:
        """Get all parameter combinations for a block."""
        if not block.params:
            return [{}]

        keys = list(block.params.keys())
        values = [block.params[k] for k in keys]

        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))

        return combinations

    def _get_random_params(self, block: PatternBlock) -> Dict[str, Any]:
        """Get random parameter values for a block."""
        return {
            k: self.rng.choice(v) if isinstance(v, list) else v
            for k, v in block.params.items()
        }

    def _split_indicator_signal(self, code: str) -> Tuple[str, str]:
        """Split code into indicator calculation and signal assignment."""
        lines = code.strip().split('\n')
        indicator_lines = []
        signal_lines = []

        for line in lines:
            # Check if this line assigns to entry_signal or a condition column
            if any(x in line for x in ['entry_signal', 'entry_cond', 'short_cond', 'long_cond', 'primary_cond', 'secondary_cond']):
                signal_lines.append(line)
            else:
                indicator_lines.append(line)

        return '\n'.join(indicator_lines), '\n'.join(signal_lines)

    def _compute_hash(self, formula: str) -> str:
        """Compute SHA256 hash of normalized formula."""
        # Normalize: remove extra whitespace, sort lines
        normalized = '\n'.join(
            line.strip() for line in formula.strip().split('\n')
            if line.strip()
        )
        return hashlib.sha256(normalized.encode()).hexdigest()[:12]

    def _is_unique(self, formula: ComposedFormula) -> bool:
        """Check if formula hash is unique (not seen before)."""
        return formula.formula_id not in self.generated_hashes

    def clear_cache(self) -> None:
        """Clear the deduplication cache."""
        self.generated_hashes.clear()

    def compose_from_blocks(
        self,
        block_ids: List[str],
        direction: str = 'long',
    ) -> Optional[ComposedFormula]:
        """
        Compose formula from specific block IDs.

        Used by genetic generator to create formulas from evolved blocks.
        Does NOT check deduplication (caller's responsibility).

        Args:
            block_ids: List of block IDs to compose
            direction: Target direction ('long', 'short')

        Returns:
            ComposedFormula or None if composition fails
        """
        # Validate and get blocks
        blocks = []
        for block_id in block_ids:
            if block_id in BLOCKS_BY_ID:
                blocks.append(BLOCKS_BY_ID[block_id])

        if not blocks:
            return None

        # Compose based on number of blocks
        if len(blocks) == 1:
            params = self._get_random_params(blocks[0])
            formula = self._compose_single_block(blocks[0], params)
            if formula:
                # Override direction if needed
                if direction != 'bidi' and blocks[0].direction == 'bidi':
                    formula.direction = direction
            return formula

        elif len(blocks) == 2:
            formula = self._compose_two_blocks(blocks[0], blocks[1])
            if formula and direction != 'bidi':
                formula.direction = direction
            return formula

        elif len(blocks) >= 3:
            formula = self._compose_three_blocks(blocks[0], blocks[1], blocks[2])
            if formula and direction != 'bidi':
                formula.direction = direction
            return formula

        return None

    def get_cache_size(self) -> int:
        """Get number of hashes in cache."""
        return len(self.generated_hashes)
