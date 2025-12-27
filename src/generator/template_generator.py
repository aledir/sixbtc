"""
Template Generator - AI-Powered Strategy Template Generation

Generates parameterized StrategyCore templates using AI.
Templates contain Jinja2 placeholders for variable parameters.

Structure-based diversification:
- 18 safe template structures (3 risky EXIT-only excluded)
- 6 strategy types (MOM, REV, TRN, BRE, VOL, SCA)
- 4 timeframes (15m, 30m, 1h, 4h)
- Parametric variations for each template

Excluded risky structures (2, 9, 16):
- EXIT-only without TP backup = guaranteed loss if indicator fails
"""

import re
import json
import uuid
import logging
from typing import Optional
from dataclasses import dataclass
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from src.generator.ai_manager import AIManager
from src.database.models import StrategyTemplate

logger = logging.getLogger(__name__)


@dataclass
class TemplateStructure:
    """
    Defines what components a template must have.

    Rules:
    - At least one entry (long or short) required
    - Stop loss always required (not in structure, implicit)
    - At least one exit mechanism required (TP, exit_indicator, or time_exit)
    """
    id: int
    entry_long: bool
    entry_short: bool
    take_profit: bool
    exit_indicator: bool  # Indicator-based exit (RSI reversal, MA cross, etc.)
    time_exit: bool  # Exit after N bars

    @property
    def name(self) -> str:
        """Human-readable structure name"""
        parts = []
        if self.entry_long and self.entry_short:
            parts.append("BIDIR")
        elif self.entry_long:
            parts.append("LONG")
        else:
            parts.append("SHORT")

        exits = []
        if self.take_profit:
            exits.append("TP")
        if self.exit_indicator:
            exits.append("EXIT")
        if self.time_exit:
            exits.append("TIME")

        parts.append("+".join(exits))
        return "_".join(parts)

    def is_valid(self) -> bool:
        """Check if structure is valid"""
        has_entry = self.entry_long or self.entry_short
        has_exit = self.take_profit or self.exit_indicator or self.time_exit
        return has_entry and has_exit


# All 21 valid template structures (for reference)
# Entry (3 options) × Exit combinations (7 valid) = 21
ALL_STRUCTURES = [
    # Long only structures (7)
    TemplateStructure(1,  True, False, True,  False, False),  # LONG_TP
    TemplateStructure(2,  True, False, False, True,  False),  # LONG_EXIT (RISKY)
    TemplateStructure(3,  True, False, False, False, True),   # LONG_TIME
    TemplateStructure(4,  True, False, True,  True,  False),  # LONG_TP+EXIT
    TemplateStructure(5,  True, False, True,  False, True),   # LONG_TP+TIME
    TemplateStructure(6,  True, False, False, True,  True),   # LONG_EXIT+TIME
    TemplateStructure(7,  True, False, True,  True,  True),   # LONG_TP+EXIT+TIME

    # Short only structures (7)
    TemplateStructure(8,  False, True, True,  False, False),  # SHORT_TP
    TemplateStructure(9,  False, True, False, True,  False),  # SHORT_EXIT (RISKY)
    TemplateStructure(10, False, True, False, False, True),   # SHORT_TIME
    TemplateStructure(11, False, True, True,  True,  False),  # SHORT_TP+EXIT
    TemplateStructure(12, False, True, True,  False, True),   # SHORT_TP+TIME
    TemplateStructure(13, False, True, False, True,  True),   # SHORT_EXIT+TIME
    TemplateStructure(14, False, True, True,  True,  True),   # SHORT_TP+EXIT+TIME

    # Bidirectional structures (7)
    TemplateStructure(15, True, True, True,  False, False),   # BIDIR_TP
    TemplateStructure(16, True, True, False, True,  False),   # BIDIR_EXIT (RISKY)
    TemplateStructure(17, True, True, False, False, True),    # BIDIR_TIME
    TemplateStructure(18, True, True, True,  True,  False),   # BIDIR_TP+EXIT
    TemplateStructure(19, True, True, True,  False, True),    # BIDIR_TP+TIME
    TemplateStructure(20, True, True, False, True,  True),    # BIDIR_EXIT+TIME
    TemplateStructure(21, True, True, True,  True,  True),    # BIDIR_TP+EXIT+TIME
]

# Risky structures excluded from generation:
# - 2 (LONG_EXIT): If exit indicator never triggers, only SL protects = guaranteed loss
# - 9 (SHORT_EXIT): Same issue for short positions
# - 16 (BIDIR_EXIT): Same issue for bidirectional
# These structures rely ONLY on indicator-based exit without TP backup.
# If the indicator fails to generate exit signal, position runs until SL hit.
EXCLUDED_STRUCTURE_IDS = {2, 9, 16}

# Structures used for generation (18 safe structures)
VALID_STRUCTURES = [s for s in ALL_STRUCTURES if s.id not in EXCLUDED_STRUCTURE_IDS]


class TemplateGenerator:
    """
    Generates parameterized strategy templates using AI

    Templates have Jinja2 placeholders that ParametricGenerator
    fills with different parameter combinations.

    Diversification through:
    1. Template structure (18 safe combinations, 3 risky excluded)
    2. Strategy type (6 types)
    3. Timeframe (4 timeframes)
    4. Parametric variations (50-200 per template)
    """

    STRATEGY_TYPES = ['MOM', 'REV', 'TRN', 'BRE', 'VOL', 'SCA']
    TIMEFRAMES = ['15m', '30m', '1h', '4h']

    def __init__(self, config: dict):
        """
        Initialize Template Generator

        Args:
            config: Full configuration dict (must contain 'ai' section)
        """
        self.config = config
        self.ai_manager = AIManager(config)

        # Track which structures have been used (for rotation)
        self._structure_index = 0

        # Setup Jinja2 for prompts
        template_dir = Path(__file__).parent / 'templates'
        self.template_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )

        logger.info(
            f"TemplateGenerator initialized with {self.ai_manager.get_provider_name()}, "
            f"{len(VALID_STRUCTURES)} valid structures"
        )

    def get_next_structure(self) -> TemplateStructure:
        """Get next structure in rotation"""
        structure = VALID_STRUCTURES[self._structure_index % len(VALID_STRUCTURES)]
        self._structure_index += 1
        return structure

    def generate_template(
        self,
        strategy_type: str,
        timeframe: str,
        structure: Optional[TemplateStructure] = None
    ) -> Optional[StrategyTemplate]:
        """
        Generate a new parameterized template using AI

        Args:
            strategy_type: Type of strategy (MOM, REV, TRN, etc.)
            timeframe: Target timeframe ('15m', '1h', etc.)
            structure: Template structure (uses next in rotation if None)

        Returns:
            StrategyTemplate object or None if generation failed
        """
        if structure is None:
            structure = self.get_next_structure()

        template_id = str(uuid.uuid4())[:8]

        logger.info(
            f"Generating {strategy_type} template for {timeframe} "
            f"(ID: {template_id}, structure: {structure.name})"
        )

        # Render prompt with structure
        try:
            prompt_template = self.template_env.get_template('generate_template.j2')
            prompt = prompt_template.render(
                strategy_type=strategy_type,
                timeframe=timeframe,
                template_id=template_id,
                structure=structure
            )
        except Exception as e:
            logger.error(f"Failed to render prompt template: {e}")
            return None

        # Call AI
        try:
            response = self.ai_manager.generate(prompt, max_tokens=4000, temperature=0.7)
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            return None

        # Parse response
        code_template = self._extract_code(response)
        parameters_schema = self._extract_schema(response)

        if not code_template:
            logger.error("Failed to extract code template from AI response")
            return None

        if not parameters_schema:
            logger.error("Failed to extract parameters schema from AI response")
            return None

        # Validate template
        validation_errors = self._validate_template(code_template, parameters_schema, structure)
        if validation_errors:
            logger.warning(f"Template validation warnings: {validation_errors}")

        template_name = f"TPL_{strategy_type}_{template_id}"

        logger.info(
            f"Generated template {template_name} with "
            f"{len(parameters_schema)} parameters, structure {structure.name}"
        )

        return StrategyTemplate(
            name=template_name,
            strategy_type=strategy_type,
            timeframe=timeframe,
            code_template=code_template,
            parameters_schema=parameters_schema,
            ai_provider=self.ai_manager.get_provider_name(),
            generation_prompt=prompt,
            structure_id=structure.id
        )

    def generate_batch(self, count: int = 20) -> list[StrategyTemplate]:
        """
        Generate batch of templates (daily cycle)

        Distributes across:
        - Template structures (21 valid)
        - Strategy types (6)
        - Timeframes (4)

        Args:
            count: Number of templates to generate (default 20)

        Returns:
            List of generated StrategyTemplate objects
        """
        templates = []

        for i in range(count):
            # Rotate through types, timeframes, and structures
            st = self.STRATEGY_TYPES[i % len(self.STRATEGY_TYPES)]
            tf = self.TIMEFRAMES[i % len(self.TIMEFRAMES)]
            structure = self.get_next_structure()

            try:
                template = self.generate_template(st, tf, structure)
                if template:
                    templates.append(template)
                    logger.info(
                        f"Generated template {i + 1}/{count}: {template.name} "
                        f"(structure: {structure.name})"
                    )
                else:
                    logger.warning(
                        f"Failed to generate template {i + 1}/{count} "
                        f"({st}, {tf}, {structure.name})"
                    )
            except Exception as e:
                logger.error(f"Error generating template {i + 1}/{count}: {e}")

        logger.info(f"Batch complete: {len(templates)}/{count} templates generated")
        return templates

    def _extract_code(self, response: str) -> Optional[str]:
        """Extract Python code block from AI response"""
        match = re.search(r'```python\s+(.*?)\s+```', response, re.DOTALL)
        if match:
            code = match.group(1).strip()

            if '{{' not in code:
                logger.warning("Code does not contain Jinja2 placeholders")

            return code

        logger.error("No Python code block found in response")
        return None

    def _extract_schema(self, response: str) -> Optional[dict]:
        """Extract parameters schema JSON from AI response"""
        match = re.search(r'```json\s+(.*?)\s+```', response, re.DOTALL)
        if match:
            try:
                schema = json.loads(match.group(1).strip())

                if not isinstance(schema, dict):
                    logger.error("Schema is not a dict")
                    return None

                for param_name, param_def in schema.items():
                    if 'values' not in param_def:
                        logger.error(f"Parameter {param_name} missing 'values'")
                        return None
                    if not isinstance(param_def['values'], list):
                        logger.error(f"Parameter {param_name} values is not a list")
                        return None

                return schema

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse schema JSON: {e}")
                return None

        logger.error("No JSON schema block found in response")
        return None

    def _validate_template(
        self,
        code_template: str,
        parameters_schema: dict,
        structure: TemplateStructure
    ) -> list[str]:
        """
        Validate template code and schema against structure

        Returns list of validation warnings/errors (empty if valid)
        """
        warnings = []

        # Check that all schema parameters appear in code
        for param_name in parameters_schema.keys():
            placeholder = f"{{{{ {param_name} }}}}"
            placeholder_nospace = f"{{{{{param_name}}}}}"

            if placeholder not in code_template and placeholder_nospace not in code_template:
                warnings.append(
                    f"Parameter '{param_name}' defined in schema but not used in code"
                )

        # Check for required elements
        if 'class Strategy_' not in code_template:
            warnings.append("Missing Strategy class definition")

        if 'def generate_signal' not in code_template:
            warnings.append("Missing generate_signal method")

        if 'StrategyCore' not in code_template:
            warnings.append("Missing StrategyCore inheritance")

        if 'Signal(' not in code_template:
            warnings.append("No Signal object returned")

        # Validate structure compliance
        if structure.entry_long and "direction='long'" not in code_template:
            warnings.append("Structure requires entry_long but not found in code")

        if structure.entry_short and "direction='short'" not in code_template:
            warnings.append("Structure requires entry_short but not found in code")

        if structure.exit_indicator and "direction='close'" not in code_template:
            warnings.append("Structure requires exit_indicator but no close signal found")

        if structure.time_exit and 'exit_after_bars' not in code_template:
            warnings.append("Structure requires time_exit but exit_after_bars not found")

        # Check parameter count
        if len(parameters_schema) < 2:
            warnings.append("Too few parameters (minimum 2)")
        if len(parameters_schema) > 8:
            warnings.append("Too many parameters (maximum 8)")

        # Estimate total combinations
        total_combinations = 1
        for param_def in parameters_schema.values():
            total_combinations *= len(param_def.get('values', [1]))

        if total_combinations < 20:
            warnings.append(f"Too few combinations ({total_combinations}), aim for 50+")
        if total_combinations > 500:
            warnings.append(f"Too many combinations ({total_combinations}), aim for <200")

        return warnings

    def count_combinations(self, parameters_schema: dict) -> int:
        """Calculate total number of parameter combinations"""
        total = 1
        for param_def in parameters_schema.values():
            total *= len(param_def.get('values', [1]))
        return total

    def get_structure_by_id(self, structure_id: int) -> Optional[TemplateStructure]:
        """Get structure by ID (searches all structures including excluded)"""
        for s in ALL_STRUCTURES:
            if s.id == structure_id:
                return s
        return None

    def list_structures(self, include_excluded: bool = False) -> list[dict]:
        """
        List template structures as dicts

        Args:
            include_excluded: If True, includes risky structures (2, 9, 16)
        """
        structures = ALL_STRUCTURES if include_excluded else VALID_STRUCTURES
        return [
            {
                "id": s.id,
                "name": s.name,
                "entry_long": s.entry_long,
                "entry_short": s.entry_short,
                "take_profit": s.take_profit,
                "exit_indicator": s.exit_indicator,
                "time_exit": s.time_exit,
                "excluded": s.id in EXCLUDED_STRUCTURE_IDS
            }
            for s in structures
        ]
