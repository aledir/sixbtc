"""
Pandas-TA Generator - Strategy Factory using pandas_ta indicators.

Generates diversified trading strategies using:
- 50+ pandas_ta indicators (5 categories)
- Compatibility matrices for sensible combinations
- 1-3 indicators per strategy (max to avoid overfitting)
- Reused exit mechanisms from Unger (11 logics)
- Market regime awareness (TREND/REVERSAL)

Total: ~158 million possible strategies.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from src.database import get_session, MarketRegime, Coin
from src.utils import get_logger

from .composer import PtaBlueprint, PtaComposer, PtaEntryCondition

logger = get_logger(__name__)


@dataclass
class PtaGeneratedStrategy:
    """Result of Pandas-TA strategy generation."""

    code: str
    strategy_id: str
    strategy_type: str  # 'MOM', 'TRN', 'CRS', 'VOL', 'VLM'
    timeframe: str
    pattern_coins: list[str]
    entry_indicators: list[str]  # List of indicator IDs used
    exit_mechanism_name: str
    base_code_hash: str
    generation_mode: str = "pandas_ta"
    ai_provider: str = "pandas_ta"
    validation_passed: bool = True
    validation_errors: list[str] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    regime_type: str = ""
    # Compatibility with old interface
    pattern_num: int = 0
    pattern_name: str = ""

    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []
        if self.parameters is None:
            self.parameters = {}


class PandasTaGenerator:
    """
    Pandas-TA Generator - Produces diversified strategies using pandas_ta indicators.

    Key features:
    - 50+ indicators across 5 categories (momentum, trend, crossover, volatility, volume)
    - 1-3 indicators per entry (avoid overfitting)
    - Compatibility matrices prevent redundant combinations
    - Reuses exit mechanisms (11 logics) from Unger
    - ~158 million possible base strategies
    """

    # Default timeframes if not in config
    DEFAULT_TIMEFRAMES = ['15m', '30m', '1h', '2h']
    DEFAULT_DIRECTIONS = ['LONG', 'SHORT', 'BIDI']

    def __init__(self, config: dict):
        """
        Initialize generator with config.

        Args:
            config: Application config dict (from config.yaml)
        """
        self.config = config
        self.composer = PtaComposer(config)

        # Setup Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.template = self.jinja_env.get_template("pandas_ta.j2")

        # Get configured timeframes
        trading_config = config.get('trading', {})
        timeframes_config = trading_config.get('timeframes', {})
        self.timeframes = list(timeframes_config.values()) if timeframes_config else self.DEFAULT_TIMEFRAMES

        # Get pandas_ta specific config
        pta_config = config.get('strategy_sources', {}).get('pandas_ta', {})
        self.indicator_ratios = pta_config.get('indicator_ratios', {
            'single': 0.30,
            'double': 0.50,
            'triple': 0.20,
        })

        logger.info(
            f"PandasTaGenerator initialized: {len(self.timeframes)} timeframes, "
            f"~158M possible strategies"
        )

    def get_regime_coins(self, regime_type: str) -> list[str]:
        """
        Query coins for a market regime.

        Args:
            regime_type: 'TREND' or 'REVERSAL'

        Returns:
            List of coin symbols in this regime
        """
        regime_config = self.config.get('regime', {})
        min_strength = regime_config.get('min_strength', 0.5)

        try:
            with get_session() as session:
                regimes = session.query(MarketRegime).filter(
                    MarketRegime.regime_type == regime_type,
                    MarketRegime.strength >= min_strength,
                ).all()
                return [r.symbol for r in regimes]
        except Exception as e:
            logger.warning(f"Failed to query regime coins: {e}")
            return []

    def get_all_tradeable_coins(self) -> list[str]:
        """Get all tradeable coins from coin registry."""
        try:
            with get_session() as session:
                coins = session.query(Coin).filter(
                    Coin.is_active == True,
                    Coin.max_leverage > 0,
                ).all()
                return [c.symbol for c in coins]
        except Exception as e:
            logger.warning(f"Failed to query tradeable coins: {e}")
            return []

    def generate(
        self,
        timeframe: Optional[str] = None,
        direction: Optional[str] = None,
        regime_type: Optional[str] = None,
        count: int = 1,
        seed: Optional[int] = None,
    ) -> list[PtaGeneratedStrategy]:
        """
        Generate N diversified strategies.

        Args:
            timeframe: Target timeframe (None = random from config)
            direction: 'LONG', 'SHORT', 'BIDI' (None = random)
            regime_type: 'TREND' or 'REVERSAL' for coin selection (None = all coins)
            count: Number of strategies to generate
            seed: Random seed for reproducibility

        Returns:
            List of PtaGeneratedStrategy objects
        """
        if seed is not None:
            self.composer.set_seed(seed)
            random.seed(seed)

        results = []
        seen_hashes = set()

        for _ in range(count):
            # Select timeframe
            tf = timeframe or random.choice(self.timeframes)

            # Select direction (bias toward LONG/SHORT over BIDI)
            if direction:
                dir_ = direction
            else:
                dir_ = random.choice(['LONG', 'LONG', 'SHORT', 'SHORT', 'BIDI'])

            # Select number of indicators based on ratios
            num_indicators = random.choices(
                [1, 2, 3],
                weights=[
                    self.indicator_ratios.get('single', 0.30),
                    self.indicator_ratios.get('double', 0.50),
                    self.indicator_ratios.get('triple', 0.20),
                ]
            )[0]

            # Get coins based on regime or all
            if regime_type:
                coins = self.get_regime_coins(regime_type)
                if not coins:
                    # Fallback to opposite regime
                    fallback = 'REVERSAL' if regime_type == 'TREND' else 'TREND'
                    coins = self.get_regime_coins(fallback)
            else:
                # Mix from both regimes
                trend_coins = self.get_regime_coins('TREND')
                reversal_coins = self.get_regime_coins('REVERSAL')
                coins = list(set(trend_coins + reversal_coins))

            # Fallback to all tradeable coins
            if not coins:
                coins = self.get_all_tradeable_coins()

            if not coins:
                logger.warning("No coins available for strategy generation")
                continue

            # Compose strategy blueprint
            try:
                blueprint = self.composer.compose(
                    timeframe=tf,
                    direction=dir_,
                    regime_type=regime_type or 'MIXED',
                    coins=coins,
                    num_indicators=num_indicators,
                )
            except Exception as e:
                logger.error(f"Failed to compose blueprint: {e}")
                continue

            # Check for duplicate
            bp_hash = blueprint.compute_hash()
            if bp_hash in seen_hashes:
                logger.debug(f"Duplicate strategy hash, skipping: {bp_hash[:8]}")
                continue
            seen_hashes.add(bp_hash)

            # Render to code
            try:
                code = self._render_strategy(blueprint)
            except Exception as e:
                logger.error(f"Failed to render strategy: {e}")
                continue

            # Build result
            result = PtaGeneratedStrategy(
                code=code,
                strategy_id=blueprint.strategy_id,
                strategy_type=blueprint.get_strategy_type(),
                timeframe=tf,
                pattern_coins=blueprint.pattern_coins,
                entry_indicators=[ec.indicator.id for ec in blueprint.entry_conditions],
                exit_mechanism_name=blueprint.exit_mechanism.name,
                base_code_hash=bp_hash,
                parameters=self._extract_parameters(blueprint),
                regime_type=regime_type or 'MIXED',
                pattern_name="+".join([ec.indicator.id for ec in blueprint.entry_conditions]),
            )
            results.append(result)

            logger.debug(
                f"Generated {blueprint.get_class_name()}: "
                f"{blueprint.describe()}"
            )

        return results

    def _extract_parameters(self, bp: PtaBlueprint) -> dict:
        """Extract parameters from blueprint for storage."""
        entry_params = []
        for ec in bp.entry_conditions:
            entry_params.append({
                'indicator_id': ec.indicator.id,
                'condition_type': ec.condition_type.value,
                'indicator_params': ec.indicator_params,
                'threshold': ec.threshold,
                'threshold_high': ec.threshold_high,
            })

        return {
            'entry_conditions': entry_params,
            'sl_params': bp.sl_params,
            'tp_params': bp.tp_params,
            'exit_params': bp.exit_params,
            'trailing_params': bp.trailing_params,
        }

    def _render_strategy(self, bp: PtaBlueprint) -> str:
        """
        Render blueprint to Python strategy code.

        Args:
            bp: PtaBlueprint with all components

        Returns:
            Python source code string
        """
        # Prepare entry names for docstring
        entry_names = " + ".join([
            ec.indicator.name for ec in bp.entry_conditions
        ])

        # Calculate max lookback
        max_lookback = max(
            ec.indicator.lookback for ec in bp.entry_conditions
        ) if bp.entry_conditions else 50

        # Check if ATR is needed
        needs_atr = (
            bp.sl_config.sl_type == 'atr' or
            (bp.tp_config and bp.tp_config.tp_type == 'atr')
        )

        # Build entry reason
        entry_reason = " + ".join([
            f"{ec.indicator.id}({ec.condition_type.value})"
            for ec in bp.entry_conditions
        ])

        # Pre-process exit condition logic
        exit_logic = None
        if bp.exit_condition and bp.exit_params:
            exit_logic = bp.exit_condition.logic_template
            for key, value in bp.exit_params.items():
                exit_logic = exit_logic.replace(f'{{{key}}}', str(value))

        return self.template.render(
            # Meta
            strategy_id=bp.strategy_id,
            class_name=bp.get_class_name(),
            strategy_type=bp.get_strategy_type(),
            timeframe=bp.timeframe,
            direction=bp.direction,
            regime_type=bp.regime_type,
            generated_at=datetime.now(timezone.utc).isoformat(),
            # Entry
            entry_names=entry_names,
            entry_count=len(bp.entry_conditions),
            entry_conditions=bp.entry_conditions,
            entry_reason=entry_reason,
            max_lookback=max_lookback,
            needs_atr=needs_atr,
            # Exit
            exit_mechanism=bp.exit_mechanism,
            sl_config=bp.sl_config,
            sl_params=bp.sl_params,
            tp_config=bp.tp_config,
            tp_params=bp.tp_params,
            exit_condition=bp.exit_condition,
            exit_params=bp.exit_params,
            exit_logic=exit_logic,
            trailing=bp.trailing_config,
            trailing_params=bp.trailing_params,
            # Coins
            pattern_coins=bp.pattern_coins,
        )

    def generate_batch(
        self,
        count: int,
        diverse: bool = True,
    ) -> list[PtaGeneratedStrategy]:
        """
        Generate a batch of strategies with optional diversity.

        When diverse=True, distributes across timeframes, directions, and regimes.

        Args:
            count: Total number of strategies
            diverse: Whether to enforce diversity

        Returns:
            List of generated strategies
        """
        if not diverse:
            return self.generate(count=count)

        results = []
        directions = ['LONG', 'SHORT']  # Skip BIDI for diversity
        regimes = ['TREND', 'REVERSAL']

        # Distribute across timeframes, directions, and regimes
        per_combo = max(1, count // (len(self.timeframes) * len(directions) * len(regimes)))

        for tf in self.timeframes:
            for dir_ in directions:
                for regime in regimes:
                    batch = self.generate(
                        timeframe=tf,
                        direction=dir_,
                        regime_type=regime,
                        count=per_combo,
                    )
                    results.extend(batch)

                    if len(results) >= count:
                        return results[:count]

        return results

    def generate_with_recommended_combos(
        self,
        count: int,
        timeframe: Optional[str] = None,
    ) -> list[PtaGeneratedStrategy]:
        """
        Generate strategies using recommended indicator combinations.

        These are proven market-logic combinations from RECOMMENDED_COMBOS.

        Args:
            count: Number of strategies to generate
            timeframe: Target timeframe (None = random)

        Returns:
            List of generated strategies
        """
        results = []
        seen_hashes = set()

        for _ in range(count):
            tf = timeframe or random.choice(self.timeframes)
            coins = self.get_all_tradeable_coins()

            if not coins:
                logger.warning("No coins available")
                continue

            try:
                blueprint = self.composer.compose_with_recommended_combo(
                    timeframe=tf,
                    coins=coins,
                )
                if blueprint is None:
                    continue

                # Check for duplicate
                bp_hash = blueprint.compute_hash()
                if bp_hash in seen_hashes:
                    continue
                seen_hashes.add(bp_hash)

                code = self._render_strategy(blueprint)

                result = PtaGeneratedStrategy(
                    code=code,
                    strategy_id=blueprint.strategy_id,
                    strategy_type=blueprint.get_strategy_type(),
                    timeframe=tf,
                    pattern_coins=blueprint.pattern_coins,
                    entry_indicators=[ec.indicator.id for ec in blueprint.entry_conditions],
                    exit_mechanism_name=blueprint.exit_mechanism.name,
                    base_code_hash=bp_hash,
                    parameters=self._extract_parameters(blueprint),
                    regime_type=blueprint.regime_type,
                    pattern_name="+".join([ec.indicator.id for ec in blueprint.entry_conditions]),
                )
                results.append(result)

            except Exception as e:
                logger.error(f"Failed to generate recommended combo strategy: {e}")
                continue

        return results
