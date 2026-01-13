"""
Pattern Building Blocks - Atomic conditions for pattern generation.

Each block represents a single trading condition that can be combined
with others to create complete patterns.

Categories:
- threshold: RSI, CCI, Stochastic extremes
- crossover: MA crosses, MACD crosses
- volume: Volume spikes, dry-ups
- price_action: Higher highs, inside bars, gaps
- statistical: Returns, drawdowns, z-scores
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class PatternBlock:
    """Single pattern condition/building block."""

    id: str                         # Unique identifier e.g., "RSI_OVERSOLD"
    name: str                       # Human-readable name
    category: str                   # 'threshold', 'crossover', 'volume', 'price_action', 'statistical'
    formula_template: str           # Python code with {params} placeholders
    params: Dict[str, List[Any]]    # Parameter options e.g., {"threshold": [20, 25, 30]}
    direction: str                  # 'long', 'short', 'bidi'
    lookback: int                   # Minimum bars needed
    indicators: List[str] = field(default_factory=list)  # Required indicators
    combinable_with: List[str] = field(default_factory=list)  # Compatible categories
    strategy_type: str = "THR"      # Default strategy type


# =============================================================================
# THRESHOLD BLOCKS (Oversold/Overbought conditions)
# =============================================================================

THRESHOLD_BLOCKS = [
    # RSI Oversold/Overbought
    PatternBlock(
        id="RSI_OVERSOLD",
        name="RSI Oversold",
        category="threshold",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['entry_signal'] = df['rsi'] < {threshold}""",
        params={"period": [7, 14, 21], "threshold": [20, 25, 30, 35]},
        direction="long",
        lookback=30,
        indicators=["rsi"],
        combinable_with=["volume", "price_action", "crossover"],
        strategy_type="THR",
    ),
    PatternBlock(
        id="RSI_OVERBOUGHT",
        name="RSI Overbought",
        category="threshold",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['entry_signal'] = df['rsi'] > {threshold}""",
        params={"period": [7, 14, 21], "threshold": [65, 70, 75, 80]},
        direction="short",
        lookback=30,
        indicators=["rsi"],
        combinable_with=["volume", "price_action", "crossover"],
        strategy_type="THR",
    ),
    # Stochastic
    PatternBlock(
        id="STOCH_OVERSOLD",
        name="Stochastic Oversold",
        category="threshold",
        formula_template="""df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'],
    fastk_period={fastk}, slowk_period={slowk}, slowd_period={slowd})
df['entry_signal'] = df['slowk'] < {threshold}""",
        params={
            "fastk": [5, 14],
            "slowk": [3, 5],
            "slowd": [3, 5],
            "threshold": [15, 20, 25],
        },
        direction="long",
        lookback=30,
        indicators=["stoch"],
        combinable_with=["volume", "price_action"],
        strategy_type="THR",
    ),
    PatternBlock(
        id="STOCH_OVERBOUGHT",
        name="Stochastic Overbought",
        category="threshold",
        formula_template="""df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'],
    fastk_period={fastk}, slowk_period={slowk}, slowd_period={slowd})
df['entry_signal'] = df['slowk'] > {threshold}""",
        params={
            "fastk": [5, 14],
            "slowk": [3, 5],
            "slowd": [3, 5],
            "threshold": [75, 80, 85],
        },
        direction="short",
        lookback=30,
        indicators=["stoch"],
        combinable_with=["volume", "price_action"],
        strategy_type="THR",
    ),
    # CCI
    PatternBlock(
        id="CCI_OVERSOLD",
        name="CCI Oversold",
        category="threshold",
        formula_template="""df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod={period})
df['entry_signal'] = df['cci'] < {threshold}""",
        params={"period": [14, 20], "threshold": [-150, -100, -80]},
        direction="long",
        lookback=30,
        indicators=["cci"],
        combinable_with=["volume", "price_action"],
        strategy_type="THR",
    ),
    PatternBlock(
        id="CCI_OVERBOUGHT",
        name="CCI Overbought",
        category="threshold",
        formula_template="""df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod={period})
df['entry_signal'] = df['cci'] > {threshold}""",
        params={"period": [14, 20], "threshold": [80, 100, 150]},
        direction="short",
        lookback=30,
        indicators=["cci"],
        combinable_with=["volume", "price_action"],
        strategy_type="THR",
    ),
    # Williams %R
    PatternBlock(
        id="WILLR_OVERSOLD",
        name="Williams %R Oversold",
        category="threshold",
        formula_template="""df['willr'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod={period})
df['entry_signal'] = df['willr'] < {threshold}""",
        params={"period": [14, 21], "threshold": [-90, -85, -80]},
        direction="long",
        lookback=30,
        indicators=["willr"],
        combinable_with=["volume", "price_action"],
        strategy_type="THR",
    ),
    PatternBlock(
        id="WILLR_OVERBOUGHT",
        name="Williams %R Overbought",
        category="threshold",
        formula_template="""df['willr'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod={period})
df['entry_signal'] = df['willr'] > {threshold}""",
        params={"period": [14, 21], "threshold": [-20, -15, -10]},
        direction="short",
        lookback=30,
        indicators=["willr"],
        combinable_with=["volume", "price_action"],
        strategy_type="THR",
    ),
    # MFI (Money Flow Index)
    PatternBlock(
        id="MFI_OVERSOLD",
        name="MFI Oversold",
        category="threshold",
        formula_template="""df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod={period})
df['entry_signal'] = df['mfi'] < {threshold}""",
        params={"period": [14, 21], "threshold": [15, 20, 25]},
        direction="long",
        lookback=30,
        indicators=["mfi"],
        combinable_with=["price_action"],
        strategy_type="THR",
    ),
    PatternBlock(
        id="MFI_OVERBOUGHT",
        name="MFI Overbought",
        category="threshold",
        formula_template="""df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod={period})
df['entry_signal'] = df['mfi'] > {threshold}""",
        params={"period": [14, 21], "threshold": [75, 80, 85]},
        direction="short",
        lookback=30,
        indicators=["mfi"],
        combinable_with=["price_action"],
        strategy_type="THR",
    ),
]


# =============================================================================
# CROSSOVER BLOCKS (Moving average and indicator crosses)
# =============================================================================

CROSSOVER_BLOCKS = [
    # EMA Crossovers
    PatternBlock(
        id="EMA_CROSS_UP",
        name="EMA Fast Cross Up",
        category="crossover",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast_period})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow_period})
df['entry_signal'] = (df['ema_fast'] > df['ema_slow']) & (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))""",
        params={
            "fast_period": [5, 8, 12, 20],
            "slow_period": [20, 26, 50, 100],
        },
        direction="long",
        lookback=100,
        indicators=["ema"],
        combinable_with=["threshold", "volume"],
        strategy_type="CRS",
    ),
    PatternBlock(
        id="EMA_CROSS_DOWN",
        name="EMA Fast Cross Down",
        category="crossover",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast_period})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow_period})
df['entry_signal'] = (df['ema_fast'] < df['ema_slow']) & (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1))""",
        params={
            "fast_period": [5, 8, 12, 20],
            "slow_period": [20, 26, 50, 100],
        },
        direction="short",
        lookback=100,
        indicators=["ema"],
        combinable_with=["threshold", "volume"],
        strategy_type="CRS",
    ),
    # Price crosses EMA
    PatternBlock(
        id="PRICE_CROSS_EMA_UP",
        name="Price Cross EMA Up",
        category="crossover",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['entry_signal'] = (df['close'] > df['ema']) & (df['close'].shift(1) <= df['ema'].shift(1))""",
        params={"period": [10, 20, 50, 100, 200]},
        direction="long",
        lookback=200,
        indicators=["ema"],
        combinable_with=["threshold", "volume"],
        strategy_type="CRS",
    ),
    PatternBlock(
        id="PRICE_CROSS_EMA_DOWN",
        name="Price Cross EMA Down",
        category="crossover",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['entry_signal'] = (df['close'] < df['ema']) & (df['close'].shift(1) >= df['ema'].shift(1))""",
        params={"period": [10, 20, 50, 100, 200]},
        direction="short",
        lookback=200,
        indicators=["ema"],
        combinable_with=["threshold", "volume"],
        strategy_type="CRS",
    ),
    # MACD Crossover
    PatternBlock(
        id="MACD_CROSS_UP",
        name="MACD Cross Up",
        category="crossover",
        formula_template="""df['macd'], df['macd_signal'], df['macd_hist'] = ta.MACD(df['close'],
    fastperiod={fast}, slowperiod={slow}, signalperiod={signal})
df['entry_signal'] = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))""",
        params={
            "fast": [8, 12],
            "slow": [21, 26],
            "signal": [7, 9],
        },
        direction="long",
        lookback=50,
        indicators=["macd"],
        combinable_with=["threshold", "volume"],
        strategy_type="CRS",
    ),
    PatternBlock(
        id="MACD_CROSS_DOWN",
        name="MACD Cross Down",
        category="crossover",
        formula_template="""df['macd'], df['macd_signal'], df['macd_hist'] = ta.MACD(df['close'],
    fastperiod={fast}, slowperiod={slow}, signalperiod={signal})
df['entry_signal'] = (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1))""",
        params={
            "fast": [8, 12],
            "slow": [21, 26],
            "signal": [7, 9],
        },
        direction="short",
        lookback=50,
        indicators=["macd"],
        combinable_with=["threshold", "volume"],
        strategy_type="CRS",
    ),
]


# =============================================================================
# VOLUME BLOCKS
# =============================================================================

VOLUME_BLOCKS = [
    PatternBlock(
        id="VOLUME_SPIKE",
        name="Volume Spike",
        category="volume",
        formula_template="""df['vol_avg'] = df['volume'].rolling({period}).mean()
df['entry_signal'] = df['volume'] > df['vol_avg'] * {multiplier}""",
        params={
            "period": [10, 20, 50],
            "multiplier": [1.5, 2.0, 2.5, 3.0],
        },
        direction="bidi",
        lookback=50,
        indicators=["volume"],
        combinable_with=["threshold", "crossover", "price_action"],
        strategy_type="VOL",
    ),
    PatternBlock(
        id="VOLUME_DRY",
        name="Volume Dry Up",
        category="volume",
        formula_template="""df['vol_avg'] = df['volume'].rolling({period}).mean()
df['entry_signal'] = df['volume'] < df['vol_avg'] * {multiplier}""",
        params={
            "period": [10, 20],
            "multiplier": [0.3, 0.5, 0.7],
        },
        direction="bidi",
        lookback=30,
        indicators=["volume"],
        combinable_with=["threshold", "price_action"],
        strategy_type="VOL",
    ),
    PatternBlock(
        id="VOLUME_BREAKOUT_UP",
        name="Volume Breakout Up",
        category="volume",
        formula_template="""df['vol_avg'] = df['volume'].rolling({period}).mean()
df['close_chg'] = df['close'].pct_change()
df['entry_signal'] = (df['volume'] > df['vol_avg'] * {multiplier}) & (df['close_chg'] > 0)""",
        params={
            "period": [20],
            "multiplier": [2.0, 2.5, 3.0],
        },
        direction="long",
        lookback=30,
        indicators=["volume"],
        combinable_with=["threshold", "crossover"],
        strategy_type="VOL",
    ),
    PatternBlock(
        id="VOLUME_BREAKOUT_DOWN",
        name="Volume Breakout Down",
        category="volume",
        formula_template="""df['vol_avg'] = df['volume'].rolling({period}).mean()
df['close_chg'] = df['close'].pct_change()
df['entry_signal'] = (df['volume'] > df['vol_avg'] * {multiplier}) & (df['close_chg'] < 0)""",
        params={
            "period": [20],
            "multiplier": [2.0, 2.5, 3.0],
        },
        direction="short",
        lookback=30,
        indicators=["volume"],
        combinable_with=["threshold", "crossover"],
        strategy_type="VOL",
    ),
]


# =============================================================================
# PRICE ACTION BLOCKS
# =============================================================================

PRICE_ACTION_BLOCKS = [
    PatternBlock(
        id="HIGHER_HIGH",
        name="Higher High",
        category="price_action",
        formula_template="""df['high_prev'] = df['high'].shift(1)
df['high_prev2'] = df['high'].shift(2)
df['entry_signal'] = (df['high'] > df['high_prev']) & (df['high_prev'] > df['high_prev2'])""",
        params={},
        direction="long",
        lookback=5,
        indicators=[],
        combinable_with=["threshold", "volume"],
        strategy_type="PRC",
    ),
    PatternBlock(
        id="LOWER_LOW",
        name="Lower Low",
        category="price_action",
        formula_template="""df['low_prev'] = df['low'].shift(1)
df['low_prev2'] = df['low'].shift(2)
df['entry_signal'] = (df['low'] < df['low_prev']) & (df['low_prev'] < df['low_prev2'])""",
        params={},
        direction="short",
        lookback=5,
        indicators=[],
        combinable_with=["threshold", "volume"],
        strategy_type="PRC",
    ),
    PatternBlock(
        id="INSIDE_BAR",
        name="Inside Bar",
        category="price_action",
        formula_template="""df['entry_signal'] = (df['high'] < df['high'].shift(1)) & (df['low'] > df['low'].shift(1))""",
        params={},
        direction="bidi",
        lookback=5,
        indicators=[],
        combinable_with=["threshold", "volume", "crossover"],
        strategy_type="PRC",
    ),
    PatternBlock(
        id="OUTSIDE_BAR",
        name="Outside Bar (Engulfing Range)",
        category="price_action",
        formula_template="""df['entry_signal'] = (df['high'] > df['high'].shift(1)) & (df['low'] < df['low'].shift(1))""",
        params={},
        direction="bidi",
        lookback=5,
        indicators=[],
        combinable_with=["threshold", "volume"],
        strategy_type="PRC",
    ),
    PatternBlock(
        id="GAP_UP",
        name="Gap Up",
        category="price_action",
        formula_template="""df['entry_signal'] = df['open'] > df['high'].shift(1)""",
        params={},
        direction="long",
        lookback=5,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="PRC",
    ),
    PatternBlock(
        id="GAP_DOWN",
        name="Gap Down",
        category="price_action",
        formula_template="""df['entry_signal'] = df['open'] < df['low'].shift(1)""",
        params={},
        direction="short",
        lookback=5,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="PRC",
    ),
    PatternBlock(
        id="BULLISH_ENGULFING",
        name="Bullish Engulfing",
        category="price_action",
        formula_template="""df['prev_bearish'] = df['close'].shift(1) < df['open'].shift(1)
df['curr_bullish'] = df['close'] > df['open']
df['engulf'] = (df['close'] > df['open'].shift(1)) & (df['open'] < df['close'].shift(1))
df['entry_signal'] = df['prev_bearish'] & df['curr_bullish'] & df['engulf']""",
        params={},
        direction="long",
        lookback=5,
        indicators=[],
        combinable_with=["threshold", "volume"],
        strategy_type="PRC",
    ),
    PatternBlock(
        id="BEARISH_ENGULFING",
        name="Bearish Engulfing",
        category="price_action",
        formula_template="""df['prev_bullish'] = df['close'].shift(1) > df['open'].shift(1)
df['curr_bearish'] = df['close'] < df['open']
df['engulf'] = (df['open'] > df['close'].shift(1)) & (df['close'] < df['open'].shift(1))
df['entry_signal'] = df['prev_bullish'] & df['curr_bearish'] & df['engulf']""",
        params={},
        direction="short",
        lookback=5,
        indicators=[],
        combinable_with=["threshold", "volume"],
        strategy_type="PRC",
    ),
]


# =============================================================================
# STATISTICAL BLOCKS
# =============================================================================

STATISTICAL_BLOCKS = [
    PatternBlock(
        id="RETURN_NEGATIVE",
        name="Negative Return",
        category="statistical",
        formula_template="""df['return_{period}'] = df['close'].pct_change({period})
df['entry_signal'] = df['return_{period}'] < {threshold}""",
        params={
            "period": [4, 8, 16, 24, 48, 96],
            "threshold": [-0.03, -0.05, -0.07, -0.10],
        },
        direction="long",
        lookback=100,
        indicators=[],
        combinable_with=["threshold", "volume"],
        strategy_type="STA",
    ),
    PatternBlock(
        id="RETURN_POSITIVE",
        name="Positive Return",
        category="statistical",
        formula_template="""df['return_{period}'] = df['close'].pct_change({period})
df['entry_signal'] = df['return_{period}'] > {threshold}""",
        params={
            "period": [4, 8, 16, 24, 48, 96],
            "threshold": [0.03, 0.05, 0.07, 0.10],
        },
        direction="short",
        lookback=100,
        indicators=[],
        combinable_with=["threshold", "volume"],
        strategy_type="STA",
    ),
    PatternBlock(
        id="DRAWDOWN",
        name="Drawdown from High",
        category="statistical",
        formula_template="""df['high_{period}'] = df['high'].rolling({period}).max()
df['drawdown'] = (df['high_{period}'] - df['close']) / df['high_{period}']
df['entry_signal'] = df['drawdown'] > {threshold}""",
        params={
            "period": [24, 48, 96],
            "threshold": [0.05, 0.08, 0.10, 0.15, 0.20],
        },
        direction="long",
        lookback=100,
        indicators=[],
        combinable_with=["threshold", "volume"],
        strategy_type="STA",
    ),
    PatternBlock(
        id="RALLY_FROM_LOW",
        name="Rally from Low",
        category="statistical",
        formula_template="""df['low_{period}'] = df['low'].rolling({period}).min()
df['rally'] = (df['close'] - df['low_{period}']) / df['low_{period}']
df['entry_signal'] = df['rally'] > {threshold}""",
        params={
            "period": [24, 48, 96],
            "threshold": [0.05, 0.08, 0.10, 0.15],
        },
        direction="short",
        lookback=100,
        indicators=[],
        combinable_with=["threshold", "volume"],
        strategy_type="STA",
    ),
    PatternBlock(
        id="BB_LOWER",
        name="Below Bollinger Lower",
        category="statistical",
        formula_template="""df['bb_upper'], df['bb_middle'], df['bb_lower'] = ta.BBANDS(df['close'],
    timeperiod={period}, nbdevup={std}, nbdevdn={std})
df['entry_signal'] = df['close'] < df['bb_lower']""",
        params={
            "period": [10, 20],
            "std": [1.5, 2.0, 2.5],
        },
        direction="long",
        lookback=30,
        indicators=["bb"],
        combinable_with=["threshold", "volume"],
        strategy_type="STA",
    ),
    PatternBlock(
        id="BB_UPPER",
        name="Above Bollinger Upper",
        category="statistical",
        formula_template="""df['bb_upper'], df['bb_middle'], df['bb_lower'] = ta.BBANDS(df['close'],
    timeperiod={period}, nbdevup={std}, nbdevdn={std})
df['entry_signal'] = df['close'] > df['bb_upper']""",
        params={
            "period": [10, 20],
            "std": [1.5, 2.0, 2.5],
        },
        direction="short",
        lookback=30,
        indicators=["bb"],
        combinable_with=["threshold", "volume"],
        strategy_type="STA",
    ),
    PatternBlock(
        id="ATR_SQUEEZE",
        name="ATR Squeeze (Low Volatility)",
        category="statistical",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['atr_avg'] = df['atr'].rolling({avg_period}).mean()
df['entry_signal'] = df['atr'] < df['atr_avg'] * {threshold}""",
        params={
            "period": [14],
            "avg_period": [20, 50],
            "threshold": [0.5, 0.6, 0.7],
        },
        direction="bidi",
        lookback=60,
        indicators=["atr"],
        combinable_with=["crossover", "price_action"],
        strategy_type="STA",
    ),
    PatternBlock(
        id="ATR_EXPANSION",
        name="ATR Expansion (High Volatility)",
        category="statistical",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['atr_avg'] = df['atr'].rolling({avg_period}).mean()
df['entry_signal'] = df['atr'] > df['atr_avg'] * {threshold}""",
        params={
            "period": [14],
            "avg_period": [20, 50],
            "threshold": [1.5, 2.0, 2.5],
        },
        direction="bidi",
        lookback=60,
        indicators=["atr"],
        combinable_with=["crossover", "threshold"],
        strategy_type="STA",
    ),
]


# =============================================================================
# DIVERGENCE BLOCKS (Momentum exhaustion patterns)
# =============================================================================

DIVERGENCE_BLOCKS = [
    # RSI Bullish Divergence
    PatternBlock(
        id="RSI_BULLISH_DIVERGENCE",
        name="RSI Bullish Divergence",
        category="divergence",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['price_min'] = df['low'].rolling({lookback}).min()
df['is_price_low'] = df['low'] == df['price_min']
df['rsi_at_low'] = df['rsi'].where(df['is_price_low']).ffill()
df['prev_price_min'] = df['price_min'].shift({lookback})
df['prev_rsi_at_low'] = df['rsi_at_low'].shift({lookback})
df['price_lower'] = df['price_min'] < df['prev_price_min']
df['rsi_higher'] = df['rsi_at_low'] > df['prev_rsi_at_low'] + {threshold}
df['entry_signal'] = df['is_price_low'] & df['price_lower'] & df['rsi_higher']""",
        params={
            "period": [14, 21],
            "lookback": [10, 20, 30],
            "threshold": [2, 5, 8],
        },
        direction="long",
        lookback=80,
        indicators=["rsi"],
        combinable_with=["volume", "threshold", "price_action"],
        strategy_type="DIV",
    ),
    # RSI Bearish Divergence
    PatternBlock(
        id="RSI_BEARISH_DIVERGENCE",
        name="RSI Bearish Divergence",
        category="divergence",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['price_max'] = df['high'].rolling({lookback}).max()
df['is_price_high'] = df['high'] == df['price_max']
df['rsi_at_high'] = df['rsi'].where(df['is_price_high']).ffill()
df['prev_price_max'] = df['price_max'].shift({lookback})
df['prev_rsi_at_high'] = df['rsi_at_high'].shift({lookback})
df['price_higher'] = df['price_max'] > df['prev_price_max']
df['rsi_lower'] = df['rsi_at_high'] < df['prev_rsi_at_high'] - {threshold}
df['entry_signal'] = df['is_price_high'] & df['price_higher'] & df['rsi_lower']""",
        params={
            "period": [14, 21],
            "lookback": [10, 20, 30],
            "threshold": [2, 5, 8],
        },
        direction="short",
        lookback=80,
        indicators=["rsi"],
        combinable_with=["volume", "threshold", "price_action"],
        strategy_type="DIV",
    ),
    # MACD Bullish Divergence
    PatternBlock(
        id="MACD_BULLISH_DIVERGENCE",
        name="MACD Bullish Divergence",
        category="divergence",
        formula_template="""df['macd'], df['macd_signal'], df['macd_hist'] = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod={signal})
df['price_min'] = df['low'].rolling({lookback}).min()
df['is_price_low'] = df['low'] == df['price_min']
df['macd_at_low'] = df['macd_hist'].where(df['is_price_low']).ffill()
df['prev_price_min'] = df['price_min'].shift({lookback})
df['prev_macd_at_low'] = df['macd_at_low'].shift({lookback})
df['price_lower'] = df['price_min'] < df['prev_price_min']
df['macd_higher'] = df['macd_at_low'] > df['prev_macd_at_low']
df['entry_signal'] = df['is_price_low'] & df['price_lower'] & df['macd_higher']""",
        params={
            "fast": [8, 12],
            "slow": [21, 26],
            "signal": [7, 9],
            "lookback": [10, 20, 30],
        },
        direction="long",
        lookback=80,
        indicators=["macd"],
        combinable_with=["volume", "threshold", "price_action"],
        strategy_type="DIV",
    ),
    # MACD Bearish Divergence
    PatternBlock(
        id="MACD_BEARISH_DIVERGENCE",
        name="MACD Bearish Divergence",
        category="divergence",
        formula_template="""df['macd'], df['macd_signal'], df['macd_hist'] = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod={signal})
df['price_max'] = df['high'].rolling({lookback}).max()
df['is_price_high'] = df['high'] == df['price_max']
df['macd_at_high'] = df['macd_hist'].where(df['is_price_high']).ffill()
df['prev_price_max'] = df['price_max'].shift({lookback})
df['prev_macd_at_high'] = df['macd_at_high'].shift({lookback})
df['price_higher'] = df['price_max'] > df['prev_price_max']
df['macd_lower'] = df['macd_at_high'] < df['prev_macd_at_high']
df['entry_signal'] = df['is_price_high'] & df['price_higher'] & df['macd_lower']""",
        params={
            "fast": [8, 12],
            "slow": [21, 26],
            "signal": [7, 9],
            "lookback": [10, 20, 30],
        },
        direction="short",
        lookback=80,
        indicators=["macd"],
        combinable_with=["volume", "threshold", "price_action"],
        strategy_type="DIV",
    ),
    # OBV Bullish Divergence (Volume confirms)
    PatternBlock(
        id="OBV_BULLISH_DIVERGENCE",
        name="OBV Bullish Divergence",
        category="divergence",
        formula_template="""df['obv'] = ta.OBV(df['close'], df['volume'])
df['obv_ema'] = ta.EMA(df['obv'], timeperiod={period})
df['price_min'] = df['low'].rolling({lookback}).min()
df['is_price_low'] = df['low'] == df['price_min']
df['obv_at_low'] = df['obv_ema'].where(df['is_price_low']).ffill()
df['prev_price_min'] = df['price_min'].shift({lookback})
df['prev_obv_at_low'] = df['obv_at_low'].shift({lookback})
df['price_lower'] = df['price_min'] < df['prev_price_min']
df['obv_higher'] = df['obv_at_low'] > df['prev_obv_at_low']
df['entry_signal'] = df['is_price_low'] & df['price_lower'] & df['obv_higher']""",
        params={
            "period": [10, 20],
            "lookback": [10, 20, 30],
        },
        direction="long",
        lookback=80,
        indicators=["obv"],
        combinable_with=["threshold", "crossover", "price_action"],
        strategy_type="DIV",
    ),
    # OBV Bearish Divergence
    PatternBlock(
        id="OBV_BEARISH_DIVERGENCE",
        name="OBV Bearish Divergence",
        category="divergence",
        formula_template="""df['obv'] = ta.OBV(df['close'], df['volume'])
df['obv_ema'] = ta.EMA(df['obv'], timeperiod={period})
df['price_max'] = df['high'].rolling({lookback}).max()
df['is_price_high'] = df['high'] == df['price_max']
df['obv_at_high'] = df['obv_ema'].where(df['is_price_high']).ffill()
df['prev_price_max'] = df['price_max'].shift({lookback})
df['prev_obv_at_high'] = df['obv_at_high'].shift({lookback})
df['price_higher'] = df['price_max'] > df['prev_price_max']
df['obv_lower'] = df['obv_at_high'] < df['prev_obv_at_high']
df['entry_signal'] = df['is_price_high'] & df['price_higher'] & df['obv_lower']""",
        params={
            "period": [10, 20],
            "lookback": [10, 20, 30],
        },
        direction="short",
        lookback=80,
        indicators=["obv"],
        combinable_with=["threshold", "crossover", "price_action"],
        strategy_type="DIV",
    ),
]


# =============================================================================
# CONFIRMATION BLOCKS (Filters that combine with other blocks)
# =============================================================================

CONFIRMATION_BLOCKS = [
    # Volume Confirmation
    PatternBlock(
        id="VOLUME_ABOVE_AVERAGE",
        name="Volume Above Average",
        category="confirmation",
        formula_template="""df['vol_ma'] = df['volume'].rolling({period}).mean()
df['entry_signal'] = df['volume'] > df['vol_ma'] * {multiplier}""",
        params={
            "period": [20, 50],
            "multiplier": [1.0, 1.2, 1.5],
        },
        direction="bidi",
        lookback=50,
        indicators=["volume"],
        combinable_with=["threshold", "crossover", "price_action", "statistical", "divergence"],
        strategy_type="CNF",
    ),
    # Trend Aligned (Long)
    PatternBlock(
        id="TREND_UP",
        name="Trend Up (Price > EMA)",
        category="confirmation",
        formula_template="""df['ema_trend'] = ta.EMA(df['close'], timeperiod={period})
df['entry_signal'] = df['close'] > df['ema_trend']""",
        params={"period": [20, 50, 100]},
        direction="long",
        lookback=100,
        indicators=["ema"],
        combinable_with=["threshold", "crossover", "volume", "price_action", "statistical", "divergence"],
        strategy_type="CNF",
    ),
    # Trend Aligned (Short)
    PatternBlock(
        id="TREND_DOWN",
        name="Trend Down (Price < EMA)",
        category="confirmation",
        formula_template="""df['ema_trend'] = ta.EMA(df['close'], timeperiod={period})
df['entry_signal'] = df['close'] < df['ema_trend']""",
        params={"period": [20, 50, 100]},
        direction="short",
        lookback=100,
        indicators=["ema"],
        combinable_with=["threshold", "crossover", "volume", "price_action", "statistical", "divergence"],
        strategy_type="CNF",
    ),
    # Volatility Expanding
    PatternBlock(
        id="VOLATILITY_EXPANDING",
        name="Volatility Expanding",
        category="confirmation",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['atr_ma'] = df['atr'].rolling({ma_period}).mean()
df['entry_signal'] = df['atr'] > df['atr_ma'] * {multiplier}""",
        params={
            "period": [14],
            "ma_period": [20, 50],
            "multiplier": [1.0, 1.2],
        },
        direction="bidi",
        lookback=60,
        indicators=["atr"],
        combinable_with=["threshold", "crossover", "price_action", "statistical", "divergence"],
        strategy_type="CNF",
    ),
    # ADX Trending
    PatternBlock(
        id="ADX_TRENDING",
        name="ADX Trending Market",
        category="confirmation",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod={period})
df['entry_signal'] = df['adx'] > {threshold}""",
        params={
            "period": [14, 20],
            "threshold": [20, 25, 30],
        },
        direction="bidi",
        lookback=40,
        indicators=["adx"],
        combinable_with=["threshold", "crossover", "volume", "price_action", "divergence"],
        strategy_type="CNF",
    ),
    # Not Overbought (for long entries)
    PatternBlock(
        id="NOT_OVERBOUGHT",
        name="Not Overbought (RSI < threshold)",
        category="confirmation",
        formula_template="""df['rsi_filter'] = ta.RSI(df['close'], timeperiod={period})
df['entry_signal'] = df['rsi_filter'] < {threshold}""",
        params={
            "period": [14],
            "threshold": [65, 70, 75],
        },
        direction="long",
        lookback=30,
        indicators=["rsi"],
        combinable_with=["crossover", "volume", "price_action", "statistical", "divergence"],
        strategy_type="CNF",
    ),
    # Not Oversold (for short entries)
    PatternBlock(
        id="NOT_OVERSOLD",
        name="Not Oversold (RSI > threshold)",
        category="confirmation",
        formula_template="""df['rsi_filter'] = ta.RSI(df['close'], timeperiod={period})
df['entry_signal'] = df['rsi_filter'] > {threshold}""",
        params={
            "period": [14],
            "threshold": [25, 30, 35],
        },
        direction="short",
        lookback=30,
        indicators=["rsi"],
        combinable_with=["crossover", "volume", "price_action", "statistical", "divergence"],
        strategy_type="CNF",
    ),
]


# =============================================================================
# ADVANCED PATTERN BLOCKS (Sophisticated price patterns)
# =============================================================================

ADVANCED_PATTERN_BLOCKS = [
    # Higher Low (Reversal setup)
    PatternBlock(
        id="HIGHER_LOW_FORMATION",
        name="Higher Low Formation",
        category="advanced_pattern",
        formula_template="""df['swing_low'] = df['low'].rolling({lookback}).min()
df['prev_swing_low'] = df['swing_low'].shift({lookback})
df['is_at_low'] = df['low'] == df['swing_low']
df['higher_low'] = df['swing_low'] > df['prev_swing_low']
df['entry_signal'] = df['is_at_low'] & df['higher_low']""",
        params={"lookback": [10, 15, 20]},
        direction="long",
        lookback=50,
        indicators=[],
        combinable_with=["threshold", "volume", "confirmation"],
        strategy_type="ADV",
    ),
    # Lower High (Reversal setup)
    PatternBlock(
        id="LOWER_HIGH_FORMATION",
        name="Lower High Formation",
        category="advanced_pattern",
        formula_template="""df['swing_high'] = df['high'].rolling({lookback}).max()
df['prev_swing_high'] = df['swing_high'].shift({lookback})
df['is_at_high'] = df['high'] == df['swing_high']
df['lower_high'] = df['swing_high'] < df['prev_swing_high']
df['entry_signal'] = df['is_at_high'] & df['lower_high']""",
        params={"lookback": [10, 15, 20]},
        direction="short",
        lookback=50,
        indicators=[],
        combinable_with=["threshold", "volume", "confirmation"],
        strategy_type="ADV",
    ),
    # Pullback to EMA (Long)
    PatternBlock(
        id="PULLBACK_TO_EMA_LONG",
        name="Pullback to EMA (Trend Continuation)",
        category="advanced_pattern",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['above_ema'] = df['close'] > df['ema']
df['was_above'] = df['above_ema'].shift(1)
df['touched_ema'] = (df['low'] <= df['ema']) & (df['close'] > df['ema'])
df['trend_up'] = df['ema'] > df['ema'].shift({trend_lookback})
df['entry_signal'] = df['touched_ema'] & df['was_above'] & df['trend_up']""",
        params={
            "period": [20, 50],
            "trend_lookback": [5, 10],
        },
        direction="long",
        lookback=60,
        indicators=["ema"],
        combinable_with=["threshold", "volume", "confirmation"],
        strategy_type="ADV",
    ),
    # Pullback to EMA (Short)
    PatternBlock(
        id="PULLBACK_TO_EMA_SHORT",
        name="Pullback to EMA (Trend Continuation Short)",
        category="advanced_pattern",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['below_ema'] = df['close'] < df['ema']
df['was_below'] = df['below_ema'].shift(1)
df['touched_ema'] = (df['high'] >= df['ema']) & (df['close'] < df['ema'])
df['trend_down'] = df['ema'] < df['ema'].shift({trend_lookback})
df['entry_signal'] = df['touched_ema'] & df['was_below'] & df['trend_down']""",
        params={
            "period": [20, 50],
            "trend_lookback": [5, 10],
        },
        direction="short",
        lookback=60,
        indicators=["ema"],
        combinable_with=["threshold", "volume", "confirmation"],
        strategy_type="ADV",
    ),
    # Breakout with Volume
    PatternBlock(
        id="BREAKOUT_HIGH_VOLUME",
        name="Breakout Above Resistance with Volume",
        category="advanced_pattern",
        formula_template="""df['resistance'] = df['high'].rolling({lookback}).max().shift(1)
df['breakout'] = df['close'] > df['resistance']
df['vol_ma'] = df['volume'].rolling({vol_period}).mean()
df['high_volume'] = df['volume'] > df['vol_ma'] * {vol_mult}
df['entry_signal'] = df['breakout'] & df['high_volume']""",
        params={
            "lookback": [10, 20],
            "vol_period": [20],
            "vol_mult": [1.5, 2.0],
        },
        direction="long",
        lookback=50,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="ADV",
    ),
    # Breakdown with Volume
    PatternBlock(
        id="BREAKDOWN_HIGH_VOLUME",
        name="Breakdown Below Support with Volume",
        category="advanced_pattern",
        formula_template="""df['support'] = df['low'].rolling({lookback}).min().shift(1)
df['breakdown'] = df['close'] < df['support']
df['vol_ma'] = df['volume'].rolling({vol_period}).mean()
df['high_volume'] = df['volume'] > df['vol_ma'] * {vol_mult}
df['entry_signal'] = df['breakdown'] & df['high_volume']""",
        params={
            "lookback": [10, 20],
            "vol_period": [20],
            "vol_mult": [1.5, 2.0],
        },
        direction="short",
        lookback=50,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="ADV",
    ),
    # Failed Breakout (Mean Reversion)
    PatternBlock(
        id="FAILED_BREAKOUT_LONG",
        name="Failed Breakdown (Buy the Dip)",
        category="advanced_pattern",
        formula_template="""df['support'] = df['low'].rolling({lookback}).min().shift(1)
df['broke_support'] = df['low'].shift(1) < df['support'].shift(1)
df['recovered'] = df['close'] > df['support']
df['entry_signal'] = df['broke_support'] & df['recovered']""",
        params={"lookback": [10, 20, 30]},
        direction="long",
        lookback=50,
        indicators=[],
        combinable_with=["threshold", "volume", "confirmation"],
        strategy_type="ADV",
    ),
    # Failed Breakout Short
    PatternBlock(
        id="FAILED_BREAKOUT_SHORT",
        name="Failed Breakout (Sell the Rip)",
        category="advanced_pattern",
        formula_template="""df['resistance'] = df['high'].rolling({lookback}).max().shift(1)
df['broke_resistance'] = df['high'].shift(1) > df['resistance'].shift(1)
df['rejected'] = df['close'] < df['resistance']
df['entry_signal'] = df['broke_resistance'] & df['rejected']""",
        params={"lookback": [10, 20, 30]},
        direction="short",
        lookback=50,
        indicators=[],
        combinable_with=["threshold", "volume", "confirmation"],
        strategy_type="ADV",
    ),
]


# =============================================================================
# MORE DIVERGENCE BLOCKS (Stochastic, CCI)
# =============================================================================

MORE_DIVERGENCE_BLOCKS = [
    # Stochastic Bullish Divergence
    PatternBlock(
        id="STOCH_BULLISH_DIVERGENCE",
        name="Stochastic Bullish Divergence",
        category="divergence",
        formula_template="""df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period={fastk}, slowk_period={slowk}, slowd_period={slowd})
df['price_min'] = df['low'].rolling({lookback}).min()
df['is_price_low'] = df['low'] == df['price_min']
df['stoch_at_low'] = df['slowk'].where(df['is_price_low']).ffill()
df['prev_price_min'] = df['price_min'].shift({lookback})
df['prev_stoch_at_low'] = df['stoch_at_low'].shift({lookback})
df['price_lower'] = df['price_min'] < df['prev_price_min']
df['stoch_higher'] = df['stoch_at_low'] > df['prev_stoch_at_low'] + {threshold}
df['entry_signal'] = df['is_price_low'] & df['price_lower'] & df['stoch_higher']""",
        params={
            "fastk": [5, 14],
            "slowk": [3, 5],
            "slowd": [3, 5],
            "lookback": [10, 20],
            "threshold": [3, 5, 8],
        },
        direction="long",
        lookback=80,
        indicators=["stoch"],
        combinable_with=["volume", "threshold", "price_action", "confirmation"],
        strategy_type="DIV",
    ),
    # Stochastic Bearish Divergence
    PatternBlock(
        id="STOCH_BEARISH_DIVERGENCE",
        name="Stochastic Bearish Divergence",
        category="divergence",
        formula_template="""df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period={fastk}, slowk_period={slowk}, slowd_period={slowd})
df['price_max'] = df['high'].rolling({lookback}).max()
df['is_price_high'] = df['high'] == df['price_max']
df['stoch_at_high'] = df['slowk'].where(df['is_price_high']).ffill()
df['prev_price_max'] = df['price_max'].shift({lookback})
df['prev_stoch_at_high'] = df['stoch_at_high'].shift({lookback})
df['price_higher'] = df['price_max'] > df['prev_price_max']
df['stoch_lower'] = df['stoch_at_high'] < df['prev_stoch_at_high'] - {threshold}
df['entry_signal'] = df['is_price_high'] & df['price_higher'] & df['stoch_lower']""",
        params={
            "fastk": [5, 14],
            "slowk": [3, 5],
            "slowd": [3, 5],
            "lookback": [10, 20],
            "threshold": [3, 5, 8],
        },
        direction="short",
        lookback=80,
        indicators=["stoch"],
        combinable_with=["volume", "threshold", "price_action", "confirmation"],
        strategy_type="DIV",
    ),
    # CCI Bullish Divergence
    PatternBlock(
        id="CCI_BULLISH_DIVERGENCE",
        name="CCI Bullish Divergence",
        category="divergence",
        formula_template="""df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod={period})
df['price_min'] = df['low'].rolling({lookback}).min()
df['is_price_low'] = df['low'] == df['price_min']
df['cci_at_low'] = df['cci'].where(df['is_price_low']).ffill()
df['prev_price_min'] = df['price_min'].shift({lookback})
df['prev_cci_at_low'] = df['cci_at_low'].shift({lookback})
df['price_lower'] = df['price_min'] < df['prev_price_min']
df['cci_higher'] = df['cci_at_low'] > df['prev_cci_at_low'] + {threshold}
df['entry_signal'] = df['is_price_low'] & df['price_lower'] & df['cci_higher']""",
        params={
            "period": [14, 20],
            "lookback": [10, 20],
            "threshold": [10, 20, 30],
        },
        direction="long",
        lookback=80,
        indicators=["cci"],
        combinable_with=["volume", "threshold", "price_action", "confirmation"],
        strategy_type="DIV",
    ),
    # CCI Bearish Divergence
    PatternBlock(
        id="CCI_BEARISH_DIVERGENCE",
        name="CCI Bearish Divergence",
        category="divergence",
        formula_template="""df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod={period})
df['price_max'] = df['high'].rolling({lookback}).max()
df['is_price_high'] = df['high'] == df['price_max']
df['cci_at_high'] = df['cci'].where(df['is_price_high']).ffill()
df['prev_price_max'] = df['price_max'].shift({lookback})
df['prev_cci_at_high'] = df['cci_at_high'].shift({lookback})
df['price_higher'] = df['price_max'] > df['prev_price_max']
df['cci_lower'] = df['cci_at_high'] < df['prev_cci_at_high'] - {threshold}
df['entry_signal'] = df['is_price_high'] & df['price_higher'] & df['cci_lower']""",
        params={
            "period": [14, 20],
            "lookback": [10, 20],
            "threshold": [10, 20, 30],
        },
        direction="short",
        lookback=80,
        indicators=["cci"],
        combinable_with=["volume", "threshold", "price_action", "confirmation"],
        strategy_type="DIV",
    ),
]


# =============================================================================
# CANDLESTICK PATTERN BLOCKS (Classic patterns with filters)
# =============================================================================

CANDLESTICK_BLOCKS = [
    # Hammer (bullish reversal)
    PatternBlock(
        id="HAMMER",
        name="Hammer Pattern",
        category="candlestick",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
df['is_hammer'] = (df['lower_wick'] > df['body'] * {wick_mult}) & (df['upper_wick'] < df['body'] * 0.5)
df['in_downtrend'] = df['close'] < df['close'].rolling({trend_period}).mean()
df['entry_signal'] = df['is_hammer'] & df['in_downtrend']""",
        params={
            "wick_mult": [2.0, 2.5, 3.0],
            "trend_period": [10, 20],
        },
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CDL",
    ),
    # Shooting Star (bearish reversal)
    PatternBlock(
        id="SHOOTING_STAR",
        name="Shooting Star Pattern",
        category="candlestick",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
df['is_star'] = (df['upper_wick'] > df['body'] * {wick_mult}) & (df['lower_wick'] < df['body'] * 0.5)
df['in_uptrend'] = df['close'] > df['close'].rolling({trend_period}).mean()
df['entry_signal'] = df['is_star'] & df['in_uptrend']""",
        params={
            "wick_mult": [2.0, 2.5, 3.0],
            "trend_period": [10, 20],
        },
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CDL",
    ),
    # Doji (indecision, often reversal)
    PatternBlock(
        id="DOJI_REVERSAL_LONG",
        name="Doji at Support",
        category="candlestick",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['range'] = df['high'] - df['low']
df['is_doji'] = df['body'] < df['range'] * {body_ratio}
df['at_low'] = df['low'] == df['low'].rolling({lookback}).min()
df['entry_signal'] = df['is_doji'] & df['at_low']""",
        params={
            "body_ratio": [0.1, 0.15, 0.2],
            "lookback": [10, 20],
        },
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CDL",
    ),
    # Doji at resistance
    PatternBlock(
        id="DOJI_REVERSAL_SHORT",
        name="Doji at Resistance",
        category="candlestick",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['range'] = df['high'] - df['low']
df['is_doji'] = df['body'] < df['range'] * {body_ratio}
df['at_high'] = df['high'] == df['high'].rolling({lookback}).max()
df['entry_signal'] = df['is_doji'] & df['at_high']""",
        params={
            "body_ratio": [0.1, 0.15, 0.2],
            "lookback": [10, 20],
        },
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CDL",
    ),
    # Three White Soldiers (strong bullish continuation)
    PatternBlock(
        id="THREE_WHITE_SOLDIERS",
        name="Three White Soldiers",
        category="candlestick",
        formula_template="""df['bullish'] = df['close'] > df['open']
df['higher_close'] = df['close'] > df['close'].shift(1)
df['soldier1'] = df['bullish'].shift(2) & (df['close'].shift(2) > df['close'].shift(3))
df['soldier2'] = df['bullish'].shift(1) & df['higher_close'].shift(1)
df['soldier3'] = df['bullish'] & df['higher_close']
df['entry_signal'] = df['soldier1'] & df['soldier2'] & df['soldier3']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="CDL",
    ),
    # Three Black Crows (strong bearish continuation)
    PatternBlock(
        id="THREE_BLACK_CROWS",
        name="Three Black Crows",
        category="candlestick",
        formula_template="""df['bearish'] = df['close'] < df['open']
df['lower_close'] = df['close'] < df['close'].shift(1)
df['crow1'] = df['bearish'].shift(2) & (df['close'].shift(2) < df['close'].shift(3))
df['crow2'] = df['bearish'].shift(1) & df['lower_close'].shift(1)
df['crow3'] = df['bearish'] & df['lower_close']
df['entry_signal'] = df['crow1'] & df['crow2'] & df['crow3']""",
        params={},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="CDL",
    ),
]


# =============================================================================
# MOMENTUM EXTREME BLOCKS (ROC, MOM at extremes)
# =============================================================================

MOMENTUM_BLOCKS = [
    # ROC Oversold
    PatternBlock(
        id="ROC_OVERSOLD",
        name="Rate of Change Oversold",
        category="momentum",
        formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
df['entry_signal'] = df['roc'] < {threshold}""",
        params={
            "period": [10, 14, 20],
            "threshold": [-5, -7, -10, -15],
        },
        direction="long",
        lookback=30,
        indicators=["roc"],
        combinable_with=["volume", "threshold", "price_action", "confirmation"],
        strategy_type="MOM",
    ),
    # ROC Overbought
    PatternBlock(
        id="ROC_OVERBOUGHT",
        name="Rate of Change Overbought",
        category="momentum",
        formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
df['entry_signal'] = df['roc'] > {threshold}""",
        params={
            "period": [10, 14, 20],
            "threshold": [5, 7, 10, 15],
        },
        direction="short",
        lookback=30,
        indicators=["roc"],
        combinable_with=["volume", "threshold", "price_action", "confirmation"],
        strategy_type="MOM",
    ),
    # MOM (Momentum) Oversold
    PatternBlock(
        id="MOM_OVERSOLD",
        name="Momentum Oversold",
        category="momentum",
        formula_template="""df['mom'] = ta.MOM(df['close'], timeperiod={period})
df['mom_pct'] = df['mom'] / df['close'].shift({period}) * 100
df['entry_signal'] = df['mom_pct'] < {threshold}""",
        params={
            "period": [10, 14, 20],
            "threshold": [-5, -7, -10],
        },
        direction="long",
        lookback=30,
        indicators=["mom"],
        combinable_with=["volume", "threshold", "price_action", "confirmation"],
        strategy_type="MOM",
    ),
    # MOM Overbought
    PatternBlock(
        id="MOM_OVERBOUGHT",
        name="Momentum Overbought",
        category="momentum",
        formula_template="""df['mom'] = ta.MOM(df['close'], timeperiod={period})
df['mom_pct'] = df['mom'] / df['close'].shift({period}) * 100
df['entry_signal'] = df['mom_pct'] > {threshold}""",
        params={
            "period": [10, 14, 20],
            "threshold": [5, 7, 10],
        },
        direction="short",
        lookback=30,
        indicators=["mom"],
        combinable_with=["volume", "threshold", "price_action", "confirmation"],
        strategy_type="MOM",
    ),
    # ROC Cross Zero (momentum shift)
    PatternBlock(
        id="ROC_CROSS_ZERO_UP",
        name="ROC Cross Zero Up",
        category="momentum",
        formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
df['was_negative'] = df['roc'].shift(1) < 0
df['now_positive'] = df['roc'] >= 0
df['entry_signal'] = df['was_negative'] & df['now_positive']""",
        params={"period": [10, 14, 20]},
        direction="long",
        lookback=30,
        indicators=["roc"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="MOM",
    ),
    # ROC Cross Zero Down
    PatternBlock(
        id="ROC_CROSS_ZERO_DOWN",
        name="ROC Cross Zero Down",
        category="momentum",
        formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
df['was_positive'] = df['roc'].shift(1) > 0
df['now_negative'] = df['roc'] <= 0
df['entry_signal'] = df['was_positive'] & df['now_negative']""",
        params={"period": [10, 14, 20]},
        direction="short",
        lookback=30,
        indicators=["roc"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="MOM",
    ),
]


# =============================================================================
# CHANNEL BLOCKS (Keltner, Donchian)
# =============================================================================

CHANNEL_BLOCKS = [
    # Keltner Channel Lower Touch (long)
    PatternBlock(
        id="KELTNER_LOWER",
        name="Keltner Channel Lower Touch",
        category="channel",
        formula_template="""df['kc_middle'] = ta.EMA(df['close'], timeperiod={period})
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['kc_lower'] = df['kc_middle'] - df['atr'] * {mult}
df['entry_signal'] = df['low'] <= df['kc_lower']""",
        params={
            "period": [20],
            "mult": [1.5, 2.0, 2.5],
        },
        direction="long",
        lookback=40,
        indicators=["ema", "atr"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CHN",
    ),
    # Keltner Channel Upper Touch (short)
    PatternBlock(
        id="KELTNER_UPPER",
        name="Keltner Channel Upper Touch",
        category="channel",
        formula_template="""df['kc_middle'] = ta.EMA(df['close'], timeperiod={period})
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['kc_upper'] = df['kc_middle'] + df['atr'] * {mult}
df['entry_signal'] = df['high'] >= df['kc_upper']""",
        params={
            "period": [20],
            "mult": [1.5, 2.0, 2.5],
        },
        direction="short",
        lookback=40,
        indicators=["ema", "atr"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CHN",
    ),
    # Donchian Channel Breakout Up
    PatternBlock(
        id="DONCHIAN_BREAKOUT_UP",
        name="Donchian Channel Breakout Up",
        category="channel",
        formula_template="""df['dc_high'] = df['high'].rolling({period}).max().shift(1)
df['entry_signal'] = df['high'] > df['dc_high']""",
        params={"period": [10, 20, 55]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CHN",
    ),
    # Donchian Channel Breakout Down
    PatternBlock(
        id="DONCHIAN_BREAKOUT_DOWN",
        name="Donchian Channel Breakout Down",
        category="channel",
        formula_template="""df['dc_low'] = df['low'].rolling({period}).min().shift(1)
df['entry_signal'] = df['low'] < df['dc_low']""",
        params={"period": [10, 20, 55]},
        direction="short",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CHN",
    ),
    # Donchian Middle Reversion (Long - price near lower)
    PatternBlock(
        id="DONCHIAN_REVERSION_LONG",
        name="Donchian Near Lower Band",
        category="channel",
        formula_template="""df['dc_high'] = df['high'].rolling({period}).max()
df['dc_low'] = df['low'].rolling({period}).min()
df['dc_range'] = df['dc_high'] - df['dc_low']
df['dc_position'] = (df['close'] - df['dc_low']) / df['dc_range']
df['entry_signal'] = df['dc_position'] < {threshold}""",
        params={
            "period": [20, 55],
            "threshold": [0.1, 0.15, 0.2],
        },
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CHN",
    ),
    # Donchian Middle Reversion (Short - price near upper)
    PatternBlock(
        id="DONCHIAN_REVERSION_SHORT",
        name="Donchian Near Upper Band",
        category="channel",
        formula_template="""df['dc_high'] = df['high'].rolling({period}).max()
df['dc_low'] = df['low'].rolling({period}).min()
df['dc_range'] = df['dc_high'] - df['dc_low']
df['dc_position'] = (df['close'] - df['dc_low']) / df['dc_range']
df['entry_signal'] = df['dc_position'] > {threshold}""",
        params={
            "period": [20, 55],
            "threshold": [0.8, 0.85, 0.9],
        },
        direction="short",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CHN",
    ),
]


# =============================================================================
# MULTI-INDICATOR BLOCKS (Triple confirmations)
# =============================================================================

MULTI_INDICATOR_BLOCKS = [
    # Triple Oversold (RSI + Stoch + CCI all oversold)
    PatternBlock(
        id="TRIPLE_OVERSOLD",
        name="Triple Oversold (RSI + Stoch + CCI)",
        category="multi_indicator",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={rsi_period})
df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowd_period=3)
df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod={cci_period})
df['rsi_os'] = df['rsi'] < {rsi_threshold}
df['stoch_os'] = df['slowk'] < {stoch_threshold}
df['cci_os'] = df['cci'] < {cci_threshold}
df['entry_signal'] = df['rsi_os'] & df['stoch_os'] & df['cci_os']""",
        params={
            "rsi_period": [14],
            "cci_period": [20],
            "rsi_threshold": [30, 35],
            "stoch_threshold": [20, 25],
            "cci_threshold": [-100, -80],
        },
        direction="long",
        lookback=40,
        indicators=["rsi", "stoch", "cci"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="MLT",
    ),
    # Triple Overbought
    PatternBlock(
        id="TRIPLE_OVERBOUGHT",
        name="Triple Overbought (RSI + Stoch + CCI)",
        category="multi_indicator",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={rsi_period})
df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowd_period=3)
df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod={cci_period})
df['rsi_ob'] = df['rsi'] > {rsi_threshold}
df['stoch_ob'] = df['slowk'] > {stoch_threshold}
df['cci_ob'] = df['cci'] > {cci_threshold}
df['entry_signal'] = df['rsi_ob'] & df['stoch_ob'] & df['cci_ob']""",
        params={
            "rsi_period": [14],
            "cci_period": [20],
            "rsi_threshold": [65, 70],
            "stoch_threshold": [75, 80],
            "cci_threshold": [80, 100],
        },
        direction="short",
        lookback=40,
        indicators=["rsi", "stoch", "cci"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="MLT",
    ),
    # Trend + Momentum + Volume (Long)
    PatternBlock(
        id="TREND_MOM_VOL_LONG",
        name="Trend + Momentum + Volume Long",
        category="multi_indicator",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={ema_period})
df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['vol_ma'] = df['volume'].rolling(20).mean()
df['trend_up'] = df['close'] > df['ema']
df['momentum_ok'] = (df['rsi'] > {rsi_min}) & (df['rsi'] < {rsi_max})
df['volume_ok'] = df['volume'] > df['vol_ma'] * {vol_mult}
df['entry_signal'] = df['trend_up'] & df['momentum_ok'] & df['volume_ok']""",
        params={
            "ema_period": [50, 100],
            "rsi_min": [40, 45],
            "rsi_max": [65, 70],
            "vol_mult": [1.0, 1.2],
        },
        direction="long",
        lookback=120,
        indicators=["ema", "rsi"],
        combinable_with=["crossover", "price_action"],
        strategy_type="MLT",
    ),
    # Trend + Momentum + Volume (Short)
    PatternBlock(
        id="TREND_MOM_VOL_SHORT",
        name="Trend + Momentum + Volume Short",
        category="multi_indicator",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={ema_period})
df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['vol_ma'] = df['volume'].rolling(20).mean()
df['trend_down'] = df['close'] < df['ema']
df['momentum_ok'] = (df['rsi'] < {rsi_max}) & (df['rsi'] > {rsi_min})
df['volume_ok'] = df['volume'] > df['vol_ma'] * {vol_mult}
df['entry_signal'] = df['trend_down'] & df['momentum_ok'] & df['volume_ok']""",
        params={
            "ema_period": [50, 100],
            "rsi_max": [55, 60],
            "rsi_min": [30, 35],
            "vol_mult": [1.0, 1.2],
        },
        direction="short",
        lookback=120,
        indicators=["ema", "rsi"],
        combinable_with=["crossover", "price_action"],
        strategy_type="MLT",
    ),
]


# =============================================================================
# FILTERED BLOCKS (Enhanced versions of existing blocks)
# =============================================================================

FILTERED_BLOCKS = [
    # RSI Oversold with Volume Confirmation
    PatternBlock(
        id="RSI_OVERSOLD_VOLUME",
        name="RSI Oversold + Volume Spike",
        category="filtered",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['vol_ma'] = df['volume'].rolling(20).mean()
df['rsi_oversold'] = df['rsi'] < {threshold}
df['volume_confirm'] = df['volume'] > df['vol_ma'] * {vol_mult}
df['entry_signal'] = df['rsi_oversold'] & df['volume_confirm']""",
        params={
            "period": [14, 21],
            "threshold": [25, 30],
            "vol_mult": [1.2, 1.5],
        },
        direction="long",
        lookback=40,
        indicators=["rsi"],
        combinable_with=["crossover", "price_action", "confirmation"],
        strategy_type="FLT",
    ),
    # RSI Overbought with Volume Confirmation
    PatternBlock(
        id="RSI_OVERBOUGHT_VOLUME",
        name="RSI Overbought + Volume Spike",
        category="filtered",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['vol_ma'] = df['volume'].rolling(20).mean()
df['rsi_overbought'] = df['rsi'] > {threshold}
df['volume_confirm'] = df['volume'] > df['vol_ma'] * {vol_mult}
df['entry_signal'] = df['rsi_overbought'] & df['volume_confirm']""",
        params={
            "period": [14, 21],
            "threshold": [70, 75],
            "vol_mult": [1.2, 1.5],
        },
        direction="short",
        lookback=40,
        indicators=["rsi"],
        combinable_with=["crossover", "price_action", "confirmation"],
        strategy_type="FLT",
    ),
    # RSI Cross (not just level)
    PatternBlock(
        id="RSI_CROSS_UP",
        name="RSI Cross Up from Oversold",
        category="filtered",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['was_oversold'] = df['rsi'].shift(1) < {threshold}
df['now_above'] = df['rsi'] >= {threshold}
df['entry_signal'] = df['was_oversold'] & df['now_above']""",
        params={
            "period": [14, 21],
            "threshold": [30, 35],
        },
        direction="long",
        lookback=40,
        indicators=["rsi"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="FLT",
    ),
    # RSI Cross Down
    PatternBlock(
        id="RSI_CROSS_DOWN",
        name="RSI Cross Down from Overbought",
        category="filtered",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['was_overbought'] = df['rsi'].shift(1) > {threshold}
df['now_below'] = df['rsi'] <= {threshold}
df['entry_signal'] = df['was_overbought'] & df['now_below']""",
        params={
            "period": [14, 21],
            "threshold": [65, 70],
        },
        direction="short",
        lookback=40,
        indicators=["rsi"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="FLT",
    ),
    # EMA Cross with Trend Filter
    PatternBlock(
        id="EMA_CROSS_TREND_LONG",
        name="EMA Cross Up + Trend Aligned",
        category="filtered",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
df['ema_trend'] = ta.EMA(df['close'], timeperiod={trend})
df['cross_up'] = (df['ema_fast'] > df['ema_slow']) & (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))
df['trend_up'] = df['close'] > df['ema_trend']
df['entry_signal'] = df['cross_up'] & df['trend_up']""",
        params={
            "fast": [8, 12],
            "slow": [21, 26],
            "trend": [50, 100],
        },
        direction="long",
        lookback=120,
        indicators=["ema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="FLT",
    ),
    # EMA Cross with Trend Filter (Short)
    PatternBlock(
        id="EMA_CROSS_TREND_SHORT",
        name="EMA Cross Down + Trend Aligned",
        category="filtered",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
df['ema_trend'] = ta.EMA(df['close'], timeperiod={trend})
df['cross_down'] = (df['ema_fast'] < df['ema_slow']) & (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1))
df['trend_down'] = df['close'] < df['ema_trend']
df['entry_signal'] = df['cross_down'] & df['trend_down']""",
        params={
            "fast": [8, 12],
            "slow": [21, 26],
            "trend": [50, 100],
        },
        direction="short",
        lookback=120,
        indicators=["ema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="FLT",
    ),
    # Bollinger Squeeze Breakout
    PatternBlock(
        id="BB_SQUEEZE_BREAKOUT_UP",
        name="Bollinger Squeeze Breakout Up",
        category="filtered",
        formula_template="""df['bb_upper'], df['bb_middle'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod={period}, nbdevup={std}, nbdevdn={std})
df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
df['squeeze'] = df['bb_width'] < df['bb_width'].rolling({squeeze_lookback}).mean() * {squeeze_mult}
df['was_squeeze'] = df['squeeze'].shift(1)
df['breakout_up'] = df['close'] > df['bb_upper']
df['entry_signal'] = df['was_squeeze'] & df['breakout_up']""",
        params={
            "period": [20],
            "std": [2.0],
            "squeeze_lookback": [20, 50],
            "squeeze_mult": [0.5, 0.7],
        },
        direction="long",
        lookback=80,
        indicators=["bb"],
        combinable_with=["volume", "confirmation"],
        strategy_type="FLT",
    ),
    # Bollinger Squeeze Breakout Down
    PatternBlock(
        id="BB_SQUEEZE_BREAKOUT_DOWN",
        name="Bollinger Squeeze Breakout Down",
        category="filtered",
        formula_template="""df['bb_upper'], df['bb_middle'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod={period}, nbdevup={std}, nbdevdn={std})
df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
df['squeeze'] = df['bb_width'] < df['bb_width'].rolling({squeeze_lookback}).mean() * {squeeze_mult}
df['was_squeeze'] = df['squeeze'].shift(1)
df['breakout_down'] = df['close'] < df['bb_lower']
df['entry_signal'] = df['was_squeeze'] & df['breakout_down']""",
        params={
            "period": [20],
            "std": [2.0],
            "squeeze_lookback": [20, 50],
            "squeeze_mult": [0.5, 0.7],
        },
        direction="short",
        lookback=80,
        indicators=["bb"],
        combinable_with=["volume", "confirmation"],
        strategy_type="FLT",
    ),
]


# =============================================================================
# VWAP BLOCKS (Volume Weighted Average Price)
# =============================================================================

VWAP_BLOCKS = [
    # Price crosses above VWAP
    PatternBlock(
        id="VWAP_CROSS_UP",
        name="Price Cross Above VWAP",
        category="vwap",
        formula_template="""df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
df['above_vwap'] = df['close'] > df['vwap']
df['was_below'] = df['close'].shift(1) <= df['vwap'].shift(1)
df['entry_signal'] = df['above_vwap'] & df['was_below']""",
        params={},
        direction="long",
        lookback=20,
        indicators=["vwap"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="VWP",
    ),
    # Price crosses below VWAP
    PatternBlock(
        id="VWAP_CROSS_DOWN",
        name="Price Cross Below VWAP",
        category="vwap",
        formula_template="""df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
df['below_vwap'] = df['close'] < df['vwap']
df['was_above'] = df['close'].shift(1) >= df['vwap'].shift(1)
df['entry_signal'] = df['below_vwap'] & df['was_above']""",
        params={},
        direction="short",
        lookback=20,
        indicators=["vwap"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="VWP",
    ),
    # Price far below VWAP (mean reversion long)
    PatternBlock(
        id="VWAP_DEVIATION_LONG",
        name="Price Far Below VWAP",
        category="vwap",
        formula_template="""df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
df['vwap_dev'] = (df['close'] - df['vwap']) / df['vwap']
df['entry_signal'] = df['vwap_dev'] < -{threshold}""",
        params={"threshold": [0.01, 0.015, 0.02, 0.025]},
        direction="long",
        lookback=20,
        indicators=["vwap"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="VWP",
    ),
    # Price far above VWAP (mean reversion short)
    PatternBlock(
        id="VWAP_DEVIATION_SHORT",
        name="Price Far Above VWAP",
        category="vwap",
        formula_template="""df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
df['vwap_dev'] = (df['close'] - df['vwap']) / df['vwap']
df['entry_signal'] = df['vwap_dev'] > {threshold}""",
        params={"threshold": [0.01, 0.015, 0.02, 0.025]},
        direction="short",
        lookback=20,
        indicators=["vwap"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="VWP",
    ),
]


# =============================================================================
# ICHIMOKU BLOCKS (Ichimoku Cloud components)
# =============================================================================

ICHIMOKU_BLOCKS = [
    # Price above cloud (bullish)
    PatternBlock(
        id="ICHIMOKU_ABOVE_CLOUD",
        name="Price Above Ichimoku Cloud",
        category="ichimoku",
        formula_template="""df['tenkan'] = (df['high'].rolling({tenkan}).max() + df['low'].rolling({tenkan}).min()) / 2
df['kijun'] = (df['high'].rolling({kijun}).max() + df['low'].rolling({kijun}).min()) / 2
df['senkou_a'] = ((df['tenkan'] + df['kijun']) / 2).shift({displacement})
df['senkou_b'] = ((df['high'].rolling({senkou}).max() + df['low'].rolling({senkou}).min()) / 2).shift({displacement})
df['cloud_top'] = df[['senkou_a', 'senkou_b']].max(axis=1)
df['entry_signal'] = df['close'] > df['cloud_top']""",
        params={
            "tenkan": [9],
            "kijun": [26],
            "senkou": [52],
            "displacement": [26],
        },
        direction="long",
        lookback=80,
        indicators=["ichimoku"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ICH",
    ),
    # Price below cloud (bearish)
    PatternBlock(
        id="ICHIMOKU_BELOW_CLOUD",
        name="Price Below Ichimoku Cloud",
        category="ichimoku",
        formula_template="""df['tenkan'] = (df['high'].rolling({tenkan}).max() + df['low'].rolling({tenkan}).min()) / 2
df['kijun'] = (df['high'].rolling({kijun}).max() + df['low'].rolling({kijun}).min()) / 2
df['senkou_a'] = ((df['tenkan'] + df['kijun']) / 2).shift({displacement})
df['senkou_b'] = ((df['high'].rolling({senkou}).max() + df['low'].rolling({senkou}).min()) / 2).shift({displacement})
df['cloud_bottom'] = df[['senkou_a', 'senkou_b']].min(axis=1)
df['entry_signal'] = df['close'] < df['cloud_bottom']""",
        params={
            "tenkan": [9],
            "kijun": [26],
            "senkou": [52],
            "displacement": [26],
        },
        direction="short",
        lookback=80,
        indicators=["ichimoku"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ICH",
    ),
    # Tenkan/Kijun cross up (bullish)
    PatternBlock(
        id="ICHIMOKU_TK_CROSS_UP",
        name="Tenkan Cross Above Kijun",
        category="ichimoku",
        formula_template="""df['tenkan'] = (df['high'].rolling({tenkan}).max() + df['low'].rolling({tenkan}).min()) / 2
df['kijun'] = (df['high'].rolling({kijun}).max() + df['low'].rolling({kijun}).min()) / 2
df['tk_above'] = df['tenkan'] > df['kijun']
df['tk_was_below'] = df['tenkan'].shift(1) <= df['kijun'].shift(1)
df['entry_signal'] = df['tk_above'] & df['tk_was_below']""",
        params={
            "tenkan": [9],
            "kijun": [26],
        },
        direction="long",
        lookback=40,
        indicators=["ichimoku"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ICH",
    ),
    # Tenkan/Kijun cross down (bearish)
    PatternBlock(
        id="ICHIMOKU_TK_CROSS_DOWN",
        name="Tenkan Cross Below Kijun",
        category="ichimoku",
        formula_template="""df['tenkan'] = (df['high'].rolling({tenkan}).max() + df['low'].rolling({tenkan}).min()) / 2
df['kijun'] = (df['high'].rolling({kijun}).max() + df['low'].rolling({kijun}).min()) / 2
df['tk_below'] = df['tenkan'] < df['kijun']
df['tk_was_above'] = df['tenkan'].shift(1) >= df['kijun'].shift(1)
df['entry_signal'] = df['tk_below'] & df['tk_was_above']""",
        params={
            "tenkan": [9],
            "kijun": [26],
        },
        direction="short",
        lookback=40,
        indicators=["ichimoku"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ICH",
    ),
]


# =============================================================================
# ADX DIRECTION BLOCKS (+DI/-DI crosses)
# =============================================================================

ADX_DIRECTION_BLOCKS = [
    # +DI crosses above -DI (bullish)
    PatternBlock(
        id="DI_CROSS_UP",
        name="+DI Cross Above -DI",
        category="adx_direction",
        formula_template="""df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['plus_above'] = df['plus_di'] > df['minus_di']
df['was_below'] = df['plus_di'].shift(1) <= df['minus_di'].shift(1)
df['entry_signal'] = df['plus_above'] & df['was_below']""",
        params={"period": [14, 20]},
        direction="long",
        lookback=30,
        indicators=["adx"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ADX",
    ),
    # -DI crosses above +DI (bearish)
    PatternBlock(
        id="DI_CROSS_DOWN",
        name="-DI Cross Above +DI",
        category="adx_direction",
        formula_template="""df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_above'] = df['minus_di'] > df['plus_di']
df['was_below'] = df['minus_di'].shift(1) <= df['plus_di'].shift(1)
df['entry_signal'] = df['minus_above'] & df['was_below']""",
        params={"period": [14, 20]},
        direction="short",
        lookback=30,
        indicators=["adx"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ADX",
    ),
    # Strong +DI with ADX trending
    PatternBlock(
        id="STRONG_PLUS_DI",
        name="Strong +DI with ADX Trending",
        category="adx_direction",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod={period})
df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['adx_strong'] = df['adx'] > {adx_threshold}
df['plus_dominant'] = df['plus_di'] > df['minus_di'] + {di_diff}
df['entry_signal'] = df['adx_strong'] & df['plus_dominant']""",
        params={
            "period": [14],
            "adx_threshold": [20, 25],
            "di_diff": [5, 10],
        },
        direction="long",
        lookback=30,
        indicators=["adx"],
        combinable_with=["volume", "crossover", "confirmation"],
        strategy_type="ADX",
    ),
    # Strong -DI with ADX trending
    PatternBlock(
        id="STRONG_MINUS_DI",
        name="Strong -DI with ADX Trending",
        category="adx_direction",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod={period})
df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['adx_strong'] = df['adx'] > {adx_threshold}
df['minus_dominant'] = df['minus_di'] > df['plus_di'] + {di_diff}
df['entry_signal'] = df['adx_strong'] & df['minus_dominant']""",
        params={
            "period": [14],
            "adx_threshold": [20, 25],
            "di_diff": [5, 10],
        },
        direction="short",
        lookback=30,
        indicators=["adx"],
        combinable_with=["volume", "crossover", "confirmation"],
        strategy_type="ADX",
    ),
]


# =============================================================================
# PARABOLIC SAR BLOCKS
# =============================================================================

SAR_BLOCKS = [
    # SAR flip to bullish
    PatternBlock(
        id="SAR_FLIP_BULLISH",
        name="Parabolic SAR Flip Bullish",
        category="sar",
        formula_template="""df['sar'] = ta.SAR(df['high'], df['low'], acceleration={accel}, maximum={maximum})
df['sar_below'] = df['sar'] < df['close']
df['sar_was_above'] = df['sar'].shift(1) >= df['close'].shift(1)
df['entry_signal'] = df['sar_below'] & df['sar_was_above']""",
        params={
            "accel": [0.02],
            "maximum": [0.2],
        },
        direction="long",
        lookback=20,
        indicators=["sar"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="SAR",
    ),
    # SAR flip to bearish
    PatternBlock(
        id="SAR_FLIP_BEARISH",
        name="Parabolic SAR Flip Bearish",
        category="sar",
        formula_template="""df['sar'] = ta.SAR(df['high'], df['low'], acceleration={accel}, maximum={maximum})
df['sar_above'] = df['sar'] > df['close']
df['sar_was_below'] = df['sar'].shift(1) <= df['close'].shift(1)
df['entry_signal'] = df['sar_above'] & df['sar_was_below']""",
        params={
            "accel": [0.02],
            "maximum": [0.2],
        },
        direction="short",
        lookback=20,
        indicators=["sar"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="SAR",
    ),
    # SAR below price for N bars (confirmed uptrend)
    PatternBlock(
        id="SAR_CONFIRMED_UP",
        name="SAR Below Price N Bars",
        category="sar",
        formula_template="""df['sar'] = ta.SAR(df['high'], df['low'], acceleration={accel}, maximum={maximum})
df['sar_below'] = df['sar'] < df['close']
df['sar_streak'] = df['sar_below'].rolling({bars}).sum()
df['entry_signal'] = df['sar_streak'] >= {bars}""",
        params={
            "accel": [0.02],
            "maximum": [0.2],
            "bars": [3, 5],
        },
        direction="long",
        lookback=20,
        indicators=["sar"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="SAR",
    ),
    # SAR above price for N bars (confirmed downtrend)
    PatternBlock(
        id="SAR_CONFIRMED_DOWN",
        name="SAR Above Price N Bars",
        category="sar",
        formula_template="""df['sar'] = ta.SAR(df['high'], df['low'], acceleration={accel}, maximum={maximum})
df['sar_above'] = df['sar'] > df['close']
df['sar_streak'] = df['sar_above'].rolling({bars}).sum()
df['entry_signal'] = df['sar_streak'] >= {bars}""",
        params={
            "accel": [0.02],
            "maximum": [0.2],
            "bars": [3, 5],
        },
        direction="short",
        lookback=20,
        indicators=["sar"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="SAR",
    ),
]


# =============================================================================
# CONSECUTIVE CANDLES BLOCKS
# =============================================================================

CONSECUTIVE_BLOCKS = [
    # N consecutive bullish candles
    PatternBlock(
        id="CONSECUTIVE_BULLISH",
        name="N Consecutive Bullish Candles",
        category="consecutive",
        formula_template="""df['bullish'] = (df['close'] > df['open']).astype(int)
df['bull_streak'] = df['bullish'].rolling({n}).sum()
df['entry_signal'] = df['bull_streak'] >= {n}""",
        params={"n": [3, 4, 5]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CNS",
    ),
    # N consecutive bearish candles
    PatternBlock(
        id="CONSECUTIVE_BEARISH",
        name="N Consecutive Bearish Candles",
        category="consecutive",
        formula_template="""df['bearish'] = (df['close'] < df['open']).astype(int)
df['bear_streak'] = df['bearish'].rolling({n}).sum()
df['entry_signal'] = df['bear_streak'] >= {n}""",
        params={"n": [3, 4, 5]},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CNS",
    ),
    # N consecutive higher closes
    PatternBlock(
        id="CONSECUTIVE_HIGHER_CLOSE",
        name="N Consecutive Higher Closes",
        category="consecutive",
        formula_template="""df['higher_close'] = (df['close'] > df['close'].shift(1)).astype(int)
df['hc_streak'] = df['higher_close'].rolling({n}).sum()
df['entry_signal'] = df['hc_streak'] >= {n}""",
        params={"n": [3, 4, 5]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CNS",
    ),
    # N consecutive lower closes
    PatternBlock(
        id="CONSECUTIVE_LOWER_CLOSE",
        name="N Consecutive Lower Closes",
        category="consecutive",
        formula_template="""df['lower_close'] = (df['close'] < df['close'].shift(1)).astype(int)
df['lc_streak'] = df['lower_close'].rolling({n}).sum()
df['entry_signal'] = df['lc_streak'] >= {n}""",
        params={"n": [3, 4, 5]},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CNS",
    ),
]


# =============================================================================
# RANGE CONTRACTION BLOCKS (NR4, NR7)
# =============================================================================

RANGE_CONTRACTION_BLOCKS = [
    # NR4 - Narrowest Range 4 bars (long breakout)
    PatternBlock(
        id="NR4_BREAKOUT_UP",
        name="NR4 Breakout Up",
        category="range_contraction",
        formula_template="""df['range'] = df['high'] - df['low']
df['nr4'] = df['range'] == df['range'].rolling(4).min()
df['breakout_up'] = df['close'] > df['high'].shift(1)
df['entry_signal'] = df['nr4'].shift(1) & df['breakout_up']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="NRX",
    ),
    # NR4 - Narrowest Range 4 bars (short breakout)
    PatternBlock(
        id="NR4_BREAKOUT_DOWN",
        name="NR4 Breakout Down",
        category="range_contraction",
        formula_template="""df['range'] = df['high'] - df['low']
df['nr4'] = df['range'] == df['range'].rolling(4).min()
df['breakout_down'] = df['close'] < df['low'].shift(1)
df['entry_signal'] = df['nr4'].shift(1) & df['breakout_down']""",
        params={},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="NRX",
    ),
    # NR7 - Narrowest Range 7 bars (long breakout)
    PatternBlock(
        id="NR7_BREAKOUT_UP",
        name="NR7 Breakout Up",
        category="range_contraction",
        formula_template="""df['range'] = df['high'] - df['low']
df['nr7'] = df['range'] == df['range'].rolling(7).min()
df['breakout_up'] = df['close'] > df['high'].shift(1)
df['entry_signal'] = df['nr7'].shift(1) & df['breakout_up']""",
        params={},
        direction="long",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="NRX",
    ),
    # NR7 - Narrowest Range 7 bars (short breakout)
    PatternBlock(
        id="NR7_BREAKOUT_DOWN",
        name="NR7 Breakout Down",
        category="range_contraction",
        formula_template="""df['range'] = df['high'] - df['low']
df['nr7'] = df['range'] == df['range'].rolling(7).min()
df['breakout_down'] = df['close'] < df['low'].shift(1)
df['entry_signal'] = df['nr7'].shift(1) & df['breakout_down']""",
        params={},
        direction="short",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="NRX",
    ),
]


# =============================================================================
# GAP FILL BLOCKS
# =============================================================================

GAP_FILL_BLOCKS = [
    # Gap up then fill (mean reversion short)
    PatternBlock(
        id="GAP_UP_FILL",
        name="Gap Up Fill (Short)",
        category="gap_fill",
        formula_template="""df['gap_up'] = df['open'] > df['high'].shift(1)
df['gap_size'] = (df['open'] - df['high'].shift(1)) / df['high'].shift(1)
df['gap_significant'] = df['gap_size'] > {min_gap}
df['filling'] = df['close'] < df['open']
df['entry_signal'] = df['gap_up'] & df['gap_significant'] & df['filling']""",
        params={"min_gap": [0.005, 0.01, 0.015]},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="GAP",
    ),
    # Gap down then fill (mean reversion long)
    PatternBlock(
        id="GAP_DOWN_FILL",
        name="Gap Down Fill (Long)",
        category="gap_fill",
        formula_template="""df['gap_down'] = df['open'] < df['low'].shift(1)
df['gap_size'] = (df['low'].shift(1) - df['open']) / df['low'].shift(1)
df['gap_significant'] = df['gap_size'] > {min_gap}
df['filling'] = df['close'] > df['open']
df['entry_signal'] = df['gap_down'] & df['gap_significant'] & df['filling']""",
        params={"min_gap": [0.005, 0.01, 0.015]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="GAP",
    ),
    # Gap up continuation (momentum)
    PatternBlock(
        id="GAP_UP_CONTINUATION",
        name="Gap Up Continuation",
        category="gap_fill",
        formula_template="""df['gap_up'] = df['open'] > df['high'].shift(1)
df['gap_size'] = (df['open'] - df['high'].shift(1)) / df['high'].shift(1)
df['gap_significant'] = df['gap_size'] > {min_gap}
df['continuing'] = df['close'] > df['open']
df['entry_signal'] = df['gap_up'] & df['gap_significant'] & df['continuing']""",
        params={"min_gap": [0.005, 0.01, 0.015]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="GAP",
    ),
    # Gap down continuation (momentum)
    PatternBlock(
        id="GAP_DOWN_CONTINUATION",
        name="Gap Down Continuation",
        category="gap_fill",
        formula_template="""df['gap_down'] = df['open'] < df['low'].shift(1)
df['gap_size'] = (df['low'].shift(1) - df['open']) / df['low'].shift(1)
df['gap_significant'] = df['gap_size'] > {min_gap}
df['continuing'] = df['close'] < df['open']
df['entry_signal'] = df['gap_down'] & df['gap_significant'] & df['continuing']""",
        params={"min_gap": [0.005, 0.01, 0.015]},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="GAP",
    ),
]


# =============================================================================
# AROON BLOCKS
# =============================================================================

AROON_BLOCKS = [
    # Aroon Up crosses above Aroon Down
    PatternBlock(
        id="AROON_CROSS_UP",
        name="Aroon Up Cross Above Down",
        category="aroon",
        formula_template="""df['aroon_down'], df['aroon_up'] = ta.AROON(df['high'], df['low'], timeperiod={period})
df['up_above'] = df['aroon_up'] > df['aroon_down']
df['was_below'] = df['aroon_up'].shift(1) <= df['aroon_down'].shift(1)
df['entry_signal'] = df['up_above'] & df['was_below']""",
        params={"period": [14, 25]},
        direction="long",
        lookback=30,
        indicators=["aroon"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ARN",
    ),
    # Aroon Down crosses above Aroon Up
    PatternBlock(
        id="AROON_CROSS_DOWN",
        name="Aroon Down Cross Above Up",
        category="aroon",
        formula_template="""df['aroon_down'], df['aroon_up'] = ta.AROON(df['high'], df['low'], timeperiod={period})
df['down_above'] = df['aroon_down'] > df['aroon_up']
df['was_below'] = df['aroon_down'].shift(1) <= df['aroon_up'].shift(1)
df['entry_signal'] = df['down_above'] & df['was_below']""",
        params={"period": [14, 25]},
        direction="short",
        lookback=30,
        indicators=["aroon"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ARN",
    ),
    # Strong Aroon Up (new high recently)
    PatternBlock(
        id="AROON_STRONG_UP",
        name="Strong Aroon Up",
        category="aroon",
        formula_template="""df['aroon_down'], df['aroon_up'] = ta.AROON(df['high'], df['low'], timeperiod={period})
df['entry_signal'] = df['aroon_up'] > {threshold}""",
        params={
            "period": [14, 25],
            "threshold": [70, 80, 90],
        },
        direction="long",
        lookback=30,
        indicators=["aroon"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ARN",
    ),
    # Strong Aroon Down (new low recently)
    PatternBlock(
        id="AROON_STRONG_DOWN",
        name="Strong Aroon Down",
        category="aroon",
        formula_template="""df['aroon_down'], df['aroon_up'] = ta.AROON(df['high'], df['low'], timeperiod={period})
df['entry_signal'] = df['aroon_down'] > {threshold}""",
        params={
            "period": [14, 25],
            "threshold": [70, 80, 90],
        },
        direction="short",
        lookback=30,
        indicators=["aroon"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ARN",
    ),
]


# =============================================================================
# CHAIKIN MONEY FLOW BLOCKS
# =============================================================================

CMF_BLOCKS = [
    # CMF positive (buying pressure)
    PatternBlock(
        id="CMF_POSITIVE",
        name="Chaikin Money Flow Positive",
        category="cmf",
        formula_template="""df['mf_mult'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'] + 1e-10)
df['mf_vol'] = df['mf_mult'] * df['volume']
df['cmf'] = df['mf_vol'].rolling({period}).sum() / df['volume'].rolling({period}).sum()
df['entry_signal'] = df['cmf'] > {threshold}""",
        params={
            "period": [20, 21],
            "threshold": [0.05, 0.10, 0.15],
        },
        direction="long",
        lookback=30,
        indicators=["cmf"],
        combinable_with=["threshold", "crossover", "confirmation"],
        strategy_type="CMF",
    ),
    # CMF negative (selling pressure)
    PatternBlock(
        id="CMF_NEGATIVE",
        name="Chaikin Money Flow Negative",
        category="cmf",
        formula_template="""df['mf_mult'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'] + 1e-10)
df['mf_vol'] = df['mf_mult'] * df['volume']
df['cmf'] = df['mf_vol'].rolling({period}).sum() / df['volume'].rolling({period}).sum()
df['entry_signal'] = df['cmf'] < -{threshold}""",
        params={
            "period": [20, 21],
            "threshold": [0.05, 0.10, 0.15],
        },
        direction="short",
        lookback=30,
        indicators=["cmf"],
        combinable_with=["threshold", "crossover", "confirmation"],
        strategy_type="CMF",
    ),
    # CMF cross zero up
    PatternBlock(
        id="CMF_CROSS_ZERO_UP",
        name="CMF Cross Zero Up",
        category="cmf",
        formula_template="""df['mf_mult'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'] + 1e-10)
df['mf_vol'] = df['mf_mult'] * df['volume']
df['cmf'] = df['mf_vol'].rolling({period}).sum() / df['volume'].rolling({period}).sum()
df['cmf_positive'] = df['cmf'] > 0
df['was_negative'] = df['cmf'].shift(1) <= 0
df['entry_signal'] = df['cmf_positive'] & df['was_negative']""",
        params={"period": [20, 21]},
        direction="long",
        lookback=30,
        indicators=["cmf"],
        combinable_with=["threshold", "crossover", "confirmation"],
        strategy_type="CMF",
    ),
    # CMF cross zero down
    PatternBlock(
        id="CMF_CROSS_ZERO_DOWN",
        name="CMF Cross Zero Down",
        category="cmf",
        formula_template="""df['mf_mult'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'] + 1e-10)
df['mf_vol'] = df['mf_mult'] * df['volume']
df['cmf'] = df['mf_vol'].rolling({period}).sum() / df['volume'].rolling({period}).sum()
df['cmf_negative'] = df['cmf'] < 0
df['was_positive'] = df['cmf'].shift(1) >= 0
df['entry_signal'] = df['cmf_negative'] & df['was_positive']""",
        params={"period": [20, 21]},
        direction="short",
        lookback=30,
        indicators=["cmf"],
        combinable_with=["threshold", "crossover", "confirmation"],
        strategy_type="CMF",
    ),
]


# =============================================================================
# WILLIAMS ACCUMULATION/DISTRIBUTION BLOCKS
# =============================================================================

WAD_BLOCKS = [
    # A/D rising (accumulation)
    PatternBlock(
        id="WAD_RISING",
        name="Williams A/D Rising",
        category="wad",
        formula_template="""df['ad'] = ta.AD(df['high'], df['low'], df['close'], df['volume'])
df['ad_ma'] = df['ad'].rolling({period}).mean()
df['ad_rising'] = df['ad'] > df['ad_ma']
df['ad_slope'] = df['ad'] - df['ad'].shift({lookback})
df['entry_signal'] = df['ad_rising'] & (df['ad_slope'] > 0)""",
        params={
            "period": [10, 20],
            "lookback": [3, 5],
        },
        direction="long",
        lookback=30,
        indicators=["ad"],
        combinable_with=["threshold", "crossover", "confirmation"],
        strategy_type="WAD",
    ),
    # A/D falling (distribution)
    PatternBlock(
        id="WAD_FALLING",
        name="Williams A/D Falling",
        category="wad",
        formula_template="""df['ad'] = ta.AD(df['high'], df['low'], df['close'], df['volume'])
df['ad_ma'] = df['ad'].rolling({period}).mean()
df['ad_falling'] = df['ad'] < df['ad_ma']
df['ad_slope'] = df['ad'] - df['ad'].shift({lookback})
df['entry_signal'] = df['ad_falling'] & (df['ad_slope'] < 0)""",
        params={
            "period": [10, 20],
            "lookback": [3, 5],
        },
        direction="short",
        lookback=30,
        indicators=["ad"],
        combinable_with=["threshold", "crossover", "confirmation"],
        strategy_type="WAD",
    ),
    # A/D bullish divergence
    PatternBlock(
        id="WAD_BULLISH_DIVERGENCE",
        name="A/D Bullish Divergence",
        category="wad",
        formula_template="""df['ad'] = ta.AD(df['high'], df['low'], df['close'], df['volume'])
df['price_min'] = df['low'].rolling({lookback}).min()
df['is_price_low'] = df['low'] == df['price_min']
df['ad_at_low'] = df['ad'].where(df['is_price_low']).ffill()
df['prev_price_min'] = df['price_min'].shift({lookback})
df['prev_ad_at_low'] = df['ad_at_low'].shift({lookback})
df['price_lower'] = df['price_min'] < df['prev_price_min']
df['ad_higher'] = df['ad_at_low'] > df['prev_ad_at_low']
df['entry_signal'] = df['is_price_low'] & df['price_lower'] & df['ad_higher']""",
        params={"lookback": [10, 20]},
        direction="long",
        lookback=60,
        indicators=["ad"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="WAD",
    ),
    # A/D bearish divergence
    PatternBlock(
        id="WAD_BEARISH_DIVERGENCE",
        name="A/D Bearish Divergence",
        category="wad",
        formula_template="""df['ad'] = ta.AD(df['high'], df['low'], df['close'], df['volume'])
df['price_max'] = df['high'].rolling({lookback}).max()
df['is_price_high'] = df['high'] == df['price_max']
df['ad_at_high'] = df['ad'].where(df['is_price_high']).ffill()
df['prev_price_max'] = df['price_max'].shift({lookback})
df['prev_ad_at_high'] = df['ad_at_high'].shift({lookback})
df['price_higher'] = df['price_max'] > df['prev_price_max']
df['ad_lower'] = df['ad_at_high'] < df['prev_ad_at_high']
df['entry_signal'] = df['is_price_high'] & df['price_higher'] & df['ad_lower']""",
        params={"lookback": [10, 20]},
        direction="short",
        lookback=60,
        indicators=["ad"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="WAD",
    ),
]


# =============================================================================
# TRIX BLOCKS (Triple Smoothed EMA)
# =============================================================================

TRIX_BLOCKS = [
    # TRIX cross zero up
    PatternBlock(
        id="TRIX_CROSS_ZERO_UP",
        name="TRIX Cross Zero Up",
        category="trix",
        formula_template="""df['trix'] = ta.TRIX(df['close'], timeperiod={period})
df['trix_positive'] = df['trix'] > 0
df['was_negative'] = df['trix'].shift(1) <= 0
df['entry_signal'] = df['trix_positive'] & df['was_negative']""",
        params={"period": [12, 15, 18]},
        direction="long",
        lookback=50,
        indicators=["trix"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="TRX",
    ),
    # TRIX cross zero down
    PatternBlock(
        id="TRIX_CROSS_ZERO_DOWN",
        name="TRIX Cross Zero Down",
        category="trix",
        formula_template="""df['trix'] = ta.TRIX(df['close'], timeperiod={period})
df['trix_negative'] = df['trix'] < 0
df['was_positive'] = df['trix'].shift(1) >= 0
df['entry_signal'] = df['trix_negative'] & df['was_positive']""",
        params={"period": [12, 15, 18]},
        direction="short",
        lookback=50,
        indicators=["trix"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="TRX",
    ),
    # TRIX signal line cross up
    PatternBlock(
        id="TRIX_SIGNAL_CROSS_UP",
        name="TRIX Cross Above Signal",
        category="trix",
        formula_template="""df['trix'] = ta.TRIX(df['close'], timeperiod={period})
df['trix_signal'] = df['trix'].rolling({signal}).mean()
df['trix_above'] = df['trix'] > df['trix_signal']
df['was_below'] = df['trix'].shift(1) <= df['trix_signal'].shift(1)
df['entry_signal'] = df['trix_above'] & df['was_below']""",
        params={"period": [12, 15], "signal": [9]},
        direction="long",
        lookback=50,
        indicators=["trix"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="TRX",
    ),
    # TRIX signal line cross down
    PatternBlock(
        id="TRIX_SIGNAL_CROSS_DOWN",
        name="TRIX Cross Below Signal",
        category="trix",
        formula_template="""df['trix'] = ta.TRIX(df['close'], timeperiod={period})
df['trix_signal'] = df['trix'].rolling({signal}).mean()
df['trix_below'] = df['trix'] < df['trix_signal']
df['was_above'] = df['trix'].shift(1) >= df['trix_signal'].shift(1)
df['entry_signal'] = df['trix_below'] & df['was_above']""",
        params={"period": [12, 15], "signal": [9]},
        direction="short",
        lookback=50,
        indicators=["trix"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="TRX",
    ),
]


# =============================================================================
# ULTIMATE OSCILLATOR BLOCKS
# =============================================================================

ULTOSC_BLOCKS = [
    # Ultimate Oscillator oversold
    PatternBlock(
        id="ULTOSC_OVERSOLD",
        name="Ultimate Oscillator Oversold",
        category="ultosc",
        formula_template="""df['ultosc'] = ta.ULTOSC(df['high'], df['low'], df['close'], timeperiod1={p1}, timeperiod2={p2}, timeperiod3={p3})
df['entry_signal'] = df['ultosc'] < {threshold}""",
        params={"p1": [7], "p2": [14], "p3": [28], "threshold": [25, 30, 35]},
        direction="long",
        lookback=40,
        indicators=["ultosc"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="ULT",
    ),
    # Ultimate Oscillator overbought
    PatternBlock(
        id="ULTOSC_OVERBOUGHT",
        name="Ultimate Oscillator Overbought",
        category="ultosc",
        formula_template="""df['ultosc'] = ta.ULTOSC(df['high'], df['low'], df['close'], timeperiod1={p1}, timeperiod2={p2}, timeperiod3={p3})
df['entry_signal'] = df['ultosc'] > {threshold}""",
        params={"p1": [7], "p2": [14], "p3": [28], "threshold": [65, 70, 75]},
        direction="short",
        lookback=40,
        indicators=["ultosc"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="ULT",
    ),
    # Ultimate Oscillator cross up from oversold
    PatternBlock(
        id="ULTOSC_CROSS_UP",
        name="Ultimate Oscillator Cross Up",
        category="ultosc",
        formula_template="""df['ultosc'] = ta.ULTOSC(df['high'], df['low'], df['close'], timeperiod1={p1}, timeperiod2={p2}, timeperiod3={p3})
df['was_oversold'] = df['ultosc'].shift(1) < {threshold}
df['now_above'] = df['ultosc'] >= {threshold}
df['entry_signal'] = df['was_oversold'] & df['now_above']""",
        params={"p1": [7], "p2": [14], "p3": [28], "threshold": [30, 35]},
        direction="long",
        lookback=40,
        indicators=["ultosc"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="ULT",
    ),
    # Ultimate Oscillator cross down from overbought
    PatternBlock(
        id="ULTOSC_CROSS_DOWN",
        name="Ultimate Oscillator Cross Down",
        category="ultosc",
        formula_template="""df['ultosc'] = ta.ULTOSC(df['high'], df['low'], df['close'], timeperiod1={p1}, timeperiod2={p2}, timeperiod3={p3})
df['was_overbought'] = df['ultosc'].shift(1) > {threshold}
df['now_below'] = df['ultosc'] <= {threshold}
df['entry_signal'] = df['was_overbought'] & df['now_below']""",
        params={"p1": [7], "p2": [14], "p3": [28], "threshold": [65, 70]},
        direction="short",
        lookback=40,
        indicators=["ultosc"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="ULT",
    ),
]


# =============================================================================
# ELDER RAY BLOCKS (Bull/Bear Power)
# =============================================================================

ELDER_RAY_BLOCKS = [
    # Bull Power positive and rising
    PatternBlock(
        id="BULL_POWER_POSITIVE",
        name="Bull Power Positive",
        category="elder_ray",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['bull_power'] = df['high'] - df['ema']
df['bp_positive'] = df['bull_power'] > 0
df['bp_rising'] = df['bull_power'] > df['bull_power'].shift(1)
df['entry_signal'] = df['bp_positive'] & df['bp_rising']""",
        params={"period": [13, 21]},
        direction="long",
        lookback=30,
        indicators=["ema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ELD",
    ),
    # Bear Power negative and falling
    PatternBlock(
        id="BEAR_POWER_NEGATIVE",
        name="Bear Power Negative",
        category="elder_ray",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['bear_power'] = df['low'] - df['ema']
df['bp_negative'] = df['bear_power'] < 0
df['bp_falling'] = df['bear_power'] < df['bear_power'].shift(1)
df['entry_signal'] = df['bp_negative'] & df['bp_falling']""",
        params={"period": [13, 21]},
        direction="short",
        lookback=30,
        indicators=["ema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ELD",
    ),
    # Bull Power divergence
    PatternBlock(
        id="BULL_POWER_DIVERGENCE",
        name="Bull Power Bullish Divergence",
        category="elder_ray",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['bull_power'] = df['high'] - df['ema']
df['price_low'] = df['low'] == df['low'].rolling({lookback}).min()
df['bp_rising'] = df['bull_power'] > df['bull_power'].shift({lookback})
df['entry_signal'] = df['price_low'] & df['bp_rising']""",
        params={"period": [13], "lookback": [5, 10]},
        direction="long",
        lookback=30,
        indicators=["ema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ELD",
    ),
    # Bear Power divergence
    PatternBlock(
        id="BEAR_POWER_DIVERGENCE",
        name="Bear Power Bearish Divergence",
        category="elder_ray",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['bear_power'] = df['low'] - df['ema']
df['price_high'] = df['high'] == df['high'].rolling({lookback}).max()
df['bp_falling'] = df['bear_power'] < df['bear_power'].shift({lookback})
df['entry_signal'] = df['price_high'] & df['bp_falling']""",
        params={"period": [13], "lookback": [5, 10]},
        direction="short",
        lookback=30,
        indicators=["ema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ELD",
    ),
]


# =============================================================================
# TSI (True Strength Index) BLOCKS
# =============================================================================

TSI_BLOCKS = [
    # TSI cross zero up
    PatternBlock(
        id="TSI_CROSS_ZERO_UP",
        name="TSI Cross Zero Up",
        category="tsi",
        formula_template="""df['pc'] = df['close'] - df['close'].shift(1)
df['pc_ds'] = ta.EMA(ta.EMA(df['pc'], timeperiod={fast}), timeperiod={slow})
df['apc_ds'] = ta.EMA(ta.EMA(df['pc'].abs(), timeperiod={fast}), timeperiod={slow})
df['tsi'] = 100 * df['pc_ds'] / (df['apc_ds'] + 1e-10)
df['tsi_positive'] = df['tsi'] > 0
df['was_negative'] = df['tsi'].shift(1) <= 0
df['entry_signal'] = df['tsi_positive'] & df['was_negative']""",
        params={"fast": [13], "slow": [25]},
        direction="long",
        lookback=50,
        indicators=["tsi"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="TSI",
    ),
    # TSI cross zero down
    PatternBlock(
        id="TSI_CROSS_ZERO_DOWN",
        name="TSI Cross Zero Down",
        category="tsi",
        formula_template="""df['pc'] = df['close'] - df['close'].shift(1)
df['pc_ds'] = ta.EMA(ta.EMA(df['pc'], timeperiod={fast}), timeperiod={slow})
df['apc_ds'] = ta.EMA(ta.EMA(df['pc'].abs(), timeperiod={fast}), timeperiod={slow})
df['tsi'] = 100 * df['pc_ds'] / (df['apc_ds'] + 1e-10)
df['tsi_negative'] = df['tsi'] < 0
df['was_positive'] = df['tsi'].shift(1) >= 0
df['entry_signal'] = df['tsi_negative'] & df['was_positive']""",
        params={"fast": [13], "slow": [25]},
        direction="short",
        lookback=50,
        indicators=["tsi"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="TSI",
    ),
    # TSI oversold
    PatternBlock(
        id="TSI_OVERSOLD",
        name="TSI Oversold",
        category="tsi",
        formula_template="""df['pc'] = df['close'] - df['close'].shift(1)
df['pc_ds'] = ta.EMA(ta.EMA(df['pc'], timeperiod={fast}), timeperiod={slow})
df['apc_ds'] = ta.EMA(ta.EMA(df['pc'].abs(), timeperiod={fast}), timeperiod={slow})
df['tsi'] = 100 * df['pc_ds'] / (df['apc_ds'] + 1e-10)
df['entry_signal'] = df['tsi'] < {threshold}""",
        params={"fast": [13], "slow": [25], "threshold": [-25, -20, -15]},
        direction="long",
        lookback=50,
        indicators=["tsi"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="TSI",
    ),
    # TSI overbought
    PatternBlock(
        id="TSI_OVERBOUGHT",
        name="TSI Overbought",
        category="tsi",
        formula_template="""df['pc'] = df['close'] - df['close'].shift(1)
df['pc_ds'] = ta.EMA(ta.EMA(df['pc'], timeperiod={fast}), timeperiod={slow})
df['apc_ds'] = ta.EMA(ta.EMA(df['pc'].abs(), timeperiod={fast}), timeperiod={slow})
df['tsi'] = 100 * df['pc_ds'] / (df['apc_ds'] + 1e-10)
df['entry_signal'] = df['tsi'] > {threshold}""",
        params={"fast": [13], "slow": [25], "threshold": [15, 20, 25]},
        direction="short",
        lookback=50,
        indicators=["tsi"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="TSI",
    ),
]


# =============================================================================
# AWESOME OSCILLATOR BLOCKS
# =============================================================================

AO_BLOCKS = [
    # AO cross zero up
    PatternBlock(
        id="AO_CROSS_ZERO_UP",
        name="Awesome Oscillator Cross Zero Up",
        category="ao",
        formula_template="""df['median'] = (df['high'] + df['low']) / 2
df['ao'] = df['median'].rolling({fast}).mean() - df['median'].rolling({slow}).mean()
df['ao_positive'] = df['ao'] > 0
df['was_negative'] = df['ao'].shift(1) <= 0
df['entry_signal'] = df['ao_positive'] & df['was_negative']""",
        params={"fast": [5], "slow": [34]},
        direction="long",
        lookback=50,
        indicators=["ao"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="AWE",
    ),
    # AO cross zero down
    PatternBlock(
        id="AO_CROSS_ZERO_DOWN",
        name="Awesome Oscillator Cross Zero Down",
        category="ao",
        formula_template="""df['median'] = (df['high'] + df['low']) / 2
df['ao'] = df['median'].rolling({fast}).mean() - df['median'].rolling({slow}).mean()
df['ao_negative'] = df['ao'] < 0
df['was_positive'] = df['ao'].shift(1) >= 0
df['entry_signal'] = df['ao_negative'] & df['was_positive']""",
        params={"fast": [5], "slow": [34]},
        direction="short",
        lookback=50,
        indicators=["ao"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="AWE",
    ),
    # AO saucer bullish
    PatternBlock(
        id="AO_SAUCER_BULLISH",
        name="AO Saucer Bullish",
        category="ao",
        formula_template="""df['median'] = (df['high'] + df['low']) / 2
df['ao'] = df['median'].rolling({fast}).mean() - df['median'].rolling({slow}).mean()
df['ao_positive'] = df['ao'] > 0
df['ao_rising'] = df['ao'] > df['ao'].shift(1)
df['was_falling'] = df['ao'].shift(1) < df['ao'].shift(2)
df['entry_signal'] = df['ao_positive'] & df['ao_rising'] & df['was_falling']""",
        params={"fast": [5], "slow": [34]},
        direction="long",
        lookback=50,
        indicators=["ao"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="AWE",
    ),
    # AO saucer bearish
    PatternBlock(
        id="AO_SAUCER_BEARISH",
        name="AO Saucer Bearish",
        category="ao",
        formula_template="""df['median'] = (df['high'] + df['low']) / 2
df['ao'] = df['median'].rolling({fast}).mean() - df['median'].rolling({slow}).mean()
df['ao_negative'] = df['ao'] < 0
df['ao_falling'] = df['ao'] < df['ao'].shift(1)
df['was_rising'] = df['ao'].shift(1) > df['ao'].shift(2)
df['entry_signal'] = df['ao_negative'] & df['ao_falling'] & df['was_rising']""",
        params={"fast": [5], "slow": [34]},
        direction="short",
        lookback=50,
        indicators=["ao"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="AWE",
    ),
]


# =============================================================================
# LINEAR REGRESSION BLOCKS
# =============================================================================

LINREG_BLOCKS = [
    # Price below linear regression
    PatternBlock(
        id="LINREG_BELOW",
        name="Price Below Linear Regression",
        category="linreg",
        formula_template="""df['linreg'] = ta.LINEARREG(df['close'], timeperiod={period})
df['deviation'] = (df['close'] - df['linreg']) / df['linreg']
df['entry_signal'] = df['deviation'] < -{threshold}""",
        params={"period": [14, 20], "threshold": [0.01, 0.015, 0.02]},
        direction="long",
        lookback=30,
        indicators=["linreg"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="LNR",
    ),
    # Price above linear regression
    PatternBlock(
        id="LINREG_ABOVE",
        name="Price Above Linear Regression",
        category="linreg",
        formula_template="""df['linreg'] = ta.LINEARREG(df['close'], timeperiod={period})
df['deviation'] = (df['close'] - df['linreg']) / df['linreg']
df['entry_signal'] = df['deviation'] > {threshold}""",
        params={"period": [14, 20], "threshold": [0.01, 0.015, 0.02]},
        direction="short",
        lookback=30,
        indicators=["linreg"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="LNR",
    ),
    # Linear regression slope up
    PatternBlock(
        id="LINREG_SLOPE_UP",
        name="Linear Regression Slope Up",
        category="linreg",
        formula_template="""df['linreg_slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['entry_signal'] = df['linreg_slope'] > {threshold}""",
        params={"period": [14, 20], "threshold": [0.0, 0.001, 0.002]},
        direction="long",
        lookback=30,
        indicators=["linreg"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="LNR",
    ),
    # Linear regression slope down
    PatternBlock(
        id="LINREG_SLOPE_DOWN",
        name="Linear Regression Slope Down",
        category="linreg",
        formula_template="""df['linreg_slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['entry_signal'] = df['linreg_slope'] < -{threshold}""",
        params={"period": [14, 20], "threshold": [0.0, 0.001, 0.002]},
        direction="short",
        lookback=30,
        indicators=["linreg"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="LNR",
    ),
]


# =============================================================================
# PIVOT POINT BLOCKS
# =============================================================================

PIVOT_BLOCKS = [
    # Price at S1 support
    PatternBlock(
        id="PIVOT_S1_LONG",
        name="Price at Pivot S1",
        category="pivot",
        formula_template="""df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
df['s1'] = 2 * df['pivot'] - df['high'].shift(1)
df['near_s1'] = (df['low'] <= df['s1'] * (1 + {tolerance})) & (df['low'] >= df['s1'] * (1 - {tolerance}))
df['bounce'] = df['close'] > df['open']
df['entry_signal'] = df['near_s1'] & df['bounce']""",
        params={"tolerance": [0.001, 0.002, 0.003]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PVT",
    ),
    # Price at R1 resistance
    PatternBlock(
        id="PIVOT_R1_SHORT",
        name="Price at Pivot R1",
        category="pivot",
        formula_template="""df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
df['r1'] = 2 * df['pivot'] - df['low'].shift(1)
df['near_r1'] = (df['high'] >= df['r1'] * (1 - {tolerance})) & (df['high'] <= df['r1'] * (1 + {tolerance}))
df['rejection'] = df['close'] < df['open']
df['entry_signal'] = df['near_r1'] & df['rejection']""",
        params={"tolerance": [0.001, 0.002, 0.003]},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PVT",
    ),
    # Price breaks above pivot
    PatternBlock(
        id="PIVOT_BREAK_UP",
        name="Price Break Above Pivot",
        category="pivot",
        formula_template="""df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
df['above_pivot'] = df['close'] > df['pivot']
df['was_below'] = df['close'].shift(1) <= df['pivot'].shift(1)
df['entry_signal'] = df['above_pivot'] & df['was_below']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PVT",
    ),
    # Price breaks below pivot
    PatternBlock(
        id="PIVOT_BREAK_DOWN",
        name="Price Break Below Pivot",
        category="pivot",
        formula_template="""df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
df['below_pivot'] = df['close'] < df['pivot']
df['was_above'] = df['close'].shift(1) >= df['pivot'].shift(1)
df['entry_signal'] = df['below_pivot'] & df['was_above']""",
        params={},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PVT",
    ),
]


# =============================================================================
# PPO (Percentage Price Oscillator) BLOCKS
# =============================================================================

PPO_BLOCKS = [
    # PPO cross zero up
    PatternBlock(
        id="PPO_CROSS_ZERO_UP",
        name="PPO Cross Zero Up",
        category="ppo",
        formula_template="""df['ppo'] = ta.PPO(df['close'], fastperiod={fast}, slowperiod={slow})
df['ppo_positive'] = df['ppo'] > 0
df['was_negative'] = df['ppo'].shift(1) <= 0
df['entry_signal'] = df['ppo_positive'] & df['was_negative']""",
        params={"fast": [12], "slow": [26]},
        direction="long",
        lookback=40,
        indicators=["ppo"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PPO",
    ),
    # PPO cross zero down
    PatternBlock(
        id="PPO_CROSS_ZERO_DOWN",
        name="PPO Cross Zero Down",
        category="ppo",
        formula_template="""df['ppo'] = ta.PPO(df['close'], fastperiod={fast}, slowperiod={slow})
df['ppo_negative'] = df['ppo'] < 0
df['was_positive'] = df['ppo'].shift(1) >= 0
df['entry_signal'] = df['ppo_negative'] & df['was_positive']""",
        params={"fast": [12], "slow": [26]},
        direction="short",
        lookback=40,
        indicators=["ppo"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PPO",
    ),
    # PPO signal cross up
    PatternBlock(
        id="PPO_SIGNAL_CROSS_UP",
        name="PPO Cross Above Signal",
        category="ppo",
        formula_template="""df['ppo'] = ta.PPO(df['close'], fastperiod={fast}, slowperiod={slow})
df['ppo_signal'] = ta.EMA(df['ppo'], timeperiod={signal})
df['ppo_above'] = df['ppo'] > df['ppo_signal']
df['was_below'] = df['ppo'].shift(1) <= df['ppo_signal'].shift(1)
df['entry_signal'] = df['ppo_above'] & df['was_below']""",
        params={"fast": [12], "slow": [26], "signal": [9]},
        direction="long",
        lookback=40,
        indicators=["ppo"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PPO",
    ),
    # PPO signal cross down
    PatternBlock(
        id="PPO_SIGNAL_CROSS_DOWN",
        name="PPO Cross Below Signal",
        category="ppo",
        formula_template="""df['ppo'] = ta.PPO(df['close'], fastperiod={fast}, slowperiod={slow})
df['ppo_signal'] = ta.EMA(df['ppo'], timeperiod={signal})
df['ppo_below'] = df['ppo'] < df['ppo_signal']
df['was_above'] = df['ppo'].shift(1) >= df['ppo_signal'].shift(1)
df['entry_signal'] = df['ppo_below'] & df['was_above']""",
        params={"fast": [12], "slow": [26], "signal": [9]},
        direction="short",
        lookback=40,
        indicators=["ppo"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PPO",
    ),
]


# =============================================================================
# CMO (Chande Momentum Oscillator) BLOCKS
# =============================================================================

CMO_BLOCKS = [
    # CMO oversold
    PatternBlock(
        id="CMO_OVERSOLD",
        name="CMO Oversold",
        category="cmo",
        formula_template="""df['cmo'] = ta.CMO(df['close'], timeperiod={period})
df['entry_signal'] = df['cmo'] < {threshold}""",
        params={"period": [14, 20], "threshold": [-50, -40, -30]},
        direction="long",
        lookback=30,
        indicators=["cmo"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="CMO",
    ),
    # CMO overbought
    PatternBlock(
        id="CMO_OVERBOUGHT",
        name="CMO Overbought",
        category="cmo",
        formula_template="""df['cmo'] = ta.CMO(df['close'], timeperiod={period})
df['entry_signal'] = df['cmo'] > {threshold}""",
        params={"period": [14, 20], "threshold": [30, 40, 50]},
        direction="short",
        lookback=30,
        indicators=["cmo"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="CMO",
    ),
    # CMO cross zero up
    PatternBlock(
        id="CMO_CROSS_ZERO_UP",
        name="CMO Cross Zero Up",
        category="cmo",
        formula_template="""df['cmo'] = ta.CMO(df['close'], timeperiod={period})
df['cmo_positive'] = df['cmo'] > 0
df['was_negative'] = df['cmo'].shift(1) <= 0
df['entry_signal'] = df['cmo_positive'] & df['was_negative']""",
        params={"period": [14, 20]},
        direction="long",
        lookback=30,
        indicators=["cmo"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="CMO",
    ),
    # CMO cross zero down
    PatternBlock(
        id="CMO_CROSS_ZERO_DOWN",
        name="CMO Cross Zero Down",
        category="cmo",
        formula_template="""df['cmo'] = ta.CMO(df['close'], timeperiod={period})
df['cmo_negative'] = df['cmo'] < 0
df['was_positive'] = df['cmo'].shift(1) >= 0
df['entry_signal'] = df['cmo_negative'] & df['was_positive']""",
        params={"period": [14, 20]},
        direction="short",
        lookback=30,
        indicators=["cmo"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="CMO",
    ),
]


# =============================================================================
# DPO (Detrended Price Oscillator) BLOCKS
# =============================================================================

DPO_BLOCKS = [
    # DPO oversold
    PatternBlock(
        id="DPO_OVERSOLD",
        name="DPO Oversold (Cycle Low)",
        category="dpo",
        formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['dpo'] = df['close'].shift({period} // 2 + 1) - df['sma']
df['dpo_pct'] = df['dpo'] / df['close'] * 100
df['entry_signal'] = df['dpo_pct'] < {threshold}""",
        params={"period": [20, 30], "threshold": [-2, -3, -4]},
        direction="long",
        lookback=50,
        indicators=["sma"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="DPO",
    ),
    # DPO overbought
    PatternBlock(
        id="DPO_OVERBOUGHT",
        name="DPO Overbought (Cycle High)",
        category="dpo",
        formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['dpo'] = df['close'].shift({period} // 2 + 1) - df['sma']
df['dpo_pct'] = df['dpo'] / df['close'] * 100
df['entry_signal'] = df['dpo_pct'] > {threshold}""",
        params={"period": [20, 30], "threshold": [2, 3, 4]},
        direction="short",
        lookback=50,
        indicators=["sma"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="DPO",
    ),
    # DPO cross zero up
    PatternBlock(
        id="DPO_CROSS_ZERO_UP",
        name="DPO Cross Zero Up",
        category="dpo",
        formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['dpo'] = df['close'].shift({period} // 2 + 1) - df['sma']
df['dpo_positive'] = df['dpo'] > 0
df['was_negative'] = df['dpo'].shift(1) <= 0
df['entry_signal'] = df['dpo_positive'] & df['was_negative']""",
        params={"period": [20, 30]},
        direction="long",
        lookback=50,
        indicators=["sma"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="DPO",
    ),
    # DPO cross zero down
    PatternBlock(
        id="DPO_CROSS_ZERO_DOWN",
        name="DPO Cross Zero Down",
        category="dpo",
        formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['dpo'] = df['close'].shift({period} // 2 + 1) - df['sma']
df['dpo_negative'] = df['dpo'] < 0
df['was_positive'] = df['dpo'].shift(1) >= 0
df['entry_signal'] = df['dpo_negative'] & df['was_positive']""",
        params={"period": [20, 30]},
        direction="short",
        lookback=50,
        indicators=["sma"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="DPO",
    ),
]


# =============================================================================
# PRICE EXTREMES BLOCKS (N-period high/low)
# =============================================================================

PRICE_EXTREMES_BLOCKS = [
    # Price at N-period high
    PatternBlock(
        id="PRICE_AT_HIGH",
        name="Price at N-Period High",
        category="price_extremes",
        formula_template="""df['n_high'] = df['high'].rolling({period}).max()
df['entry_signal'] = df['high'] >= df['n_high']""",
        params={"period": [10, 20, 50]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PEX",
    ),
    # Price at N-period low
    PatternBlock(
        id="PRICE_AT_LOW",
        name="Price at N-Period Low",
        category="price_extremes",
        formula_template="""df['n_low'] = df['low'].rolling({period}).min()
df['entry_signal'] = df['low'] <= df['n_low']""",
        params={"period": [10, 20, 50]},
        direction="short",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PEX",
    ),
    # Bounce from N-period low (reversal)
    PatternBlock(
        id="BOUNCE_FROM_LOW",
        name="Bounce from N-Period Low",
        category="price_extremes",
        formula_template="""df['n_low'] = df['low'].rolling({period}).min()
df['at_low'] = df['low'].shift(1) <= df['n_low'].shift(1)
df['bouncing'] = df['close'] > df['open']
df['entry_signal'] = df['at_low'] & df['bouncing']""",
        params={"period": [10, 20, 50]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PEX",
    ),
    # Rejection from N-period high (reversal)
    PatternBlock(
        id="REJECTION_FROM_HIGH",
        name="Rejection from N-Period High",
        category="price_extremes",
        formula_template="""df['n_high'] = df['high'].rolling({period}).max()
df['at_high'] = df['high'].shift(1) >= df['n_high'].shift(1)
df['rejecting'] = df['close'] < df['open']
df['entry_signal'] = df['at_high'] & df['rejecting']""",
        params={"period": [10, 20, 50]},
        direction="short",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PEX",
    ),
]


# =============================================================================
# VOLATILITY RATIO BLOCKS
# =============================================================================

VOLATILITY_RATIO_BLOCKS = [
    # Current volatility low vs historical
    PatternBlock(
        id="VOL_RATIO_LOW",
        name="Low Volatility Ratio",
        category="volatility_ratio",
        formula_template="""df['atr_short'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={short})
df['atr_long'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={long})
df['vol_ratio'] = df['atr_short'] / (df['atr_long'] + 1e-10)
df['entry_signal'] = df['vol_ratio'] < {threshold}""",
        params={"short": [7, 14], "long": [50], "threshold": [0.6, 0.7, 0.8]},
        direction="bidi",
        lookback=60,
        indicators=["atr"],
        combinable_with=["crossover", "threshold", "confirmation"],
        strategy_type="VLR",
    ),
    # Current volatility high vs historical
    PatternBlock(
        id="VOL_RATIO_HIGH",
        name="High Volatility Ratio",
        category="volatility_ratio",
        formula_template="""df['atr_short'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={short})
df['atr_long'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={long})
df['vol_ratio'] = df['atr_short'] / (df['atr_long'] + 1e-10)
df['entry_signal'] = df['vol_ratio'] > {threshold}""",
        params={"short": [7, 14], "long": [50], "threshold": [1.3, 1.5, 1.7]},
        direction="bidi",
        lookback=60,
        indicators=["atr"],
        combinable_with=["crossover", "threshold", "confirmation"],
        strategy_type="VLR",
    ),
    # Volatility expansion starting
    PatternBlock(
        id="VOL_EXPANSION_START",
        name="Volatility Expansion Starting",
        category="volatility_ratio",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['atr_ma'] = df['atr'].rolling({ma_period}).mean()
df['vol_expanding'] = df['atr'] > df['atr_ma']
df['was_contracting'] = df['atr'].shift(1) <= df['atr_ma'].shift(1)
df['entry_signal'] = df['vol_expanding'] & df['was_contracting']""",
        params={"period": [14], "ma_period": [20, 50]},
        direction="bidi",
        lookback=60,
        indicators=["atr"],
        combinable_with=["crossover", "threshold", "confirmation"],
        strategy_type="VLR",
    ),
]


# =============================================================================
# ACCELERATION BLOCKS (ROC of ROC)
# =============================================================================

ACCELERATION_BLOCKS = [
    # Positive acceleration (momentum increasing)
    PatternBlock(
        id="ACCELERATION_POSITIVE",
        name="Positive Acceleration",
        category="acceleration",
        formula_template="""df['roc1'] = ta.ROC(df['close'], timeperiod={period})
df['roc2'] = ta.ROC(df['roc1'], timeperiod={period})
df['entry_signal'] = df['roc2'] > {threshold}""",
        params={"period": [10, 14], "threshold": [0.5, 1.0, 1.5]},
        direction="long",
        lookback=40,
        indicators=["roc"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ACC",
    ),
    # Negative acceleration (momentum decreasing)
    PatternBlock(
        id="ACCELERATION_NEGATIVE",
        name="Negative Acceleration",
        category="acceleration",
        formula_template="""df['roc1'] = ta.ROC(df['close'], timeperiod={period})
df['roc2'] = ta.ROC(df['roc1'], timeperiod={period})
df['entry_signal'] = df['roc2'] < -{threshold}""",
        params={"period": [10, 14], "threshold": [0.5, 1.0, 1.5]},
        direction="short",
        lookback=40,
        indicators=["roc"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ACC",
    ),
    # Acceleration turning positive
    PatternBlock(
        id="ACCELERATION_TURN_UP",
        name="Acceleration Turning Positive",
        category="acceleration",
        formula_template="""df['roc1'] = ta.ROC(df['close'], timeperiod={period})
df['roc2'] = ta.ROC(df['roc1'], timeperiod={period})
df['acc_positive'] = df['roc2'] > 0
df['was_negative'] = df['roc2'].shift(1) <= 0
df['entry_signal'] = df['acc_positive'] & df['was_negative']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=40,
        indicators=["roc"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ACC",
    ),
    # Acceleration turning negative
    PatternBlock(
        id="ACCELERATION_TURN_DOWN",
        name="Acceleration Turning Negative",
        category="acceleration",
        formula_template="""df['roc1'] = ta.ROC(df['close'], timeperiod={period})
df['roc2'] = ta.ROC(df['roc1'], timeperiod={period})
df['acc_negative'] = df['roc2'] < 0
df['was_positive'] = df['roc2'].shift(1) >= 0
df['entry_signal'] = df['acc_negative'] & df['was_positive']""",
        params={"period": [10, 14]},
        direction="short",
        lookback=40,
        indicators=["roc"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ACC",
    ),
]


# =============================================================================
# MA RIBBON BLOCKS (Multiple MA alignment)
# =============================================================================

MA_RIBBON_BLOCKS = [
    # Bullish ribbon (fast > medium > slow)
    PatternBlock(
        id="MA_RIBBON_BULLISH",
        name="MA Ribbon Bullish Alignment",
        category="ma_ribbon",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
df['ema_med'] = ta.EMA(df['close'], timeperiod={medium})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
df['aligned'] = (df['ema_fast'] > df['ema_med']) & (df['ema_med'] > df['ema_slow'])
df['price_above'] = df['close'] > df['ema_fast']
df['entry_signal'] = df['aligned'] & df['price_above']""",
        params={"fast": [10, 20], "medium": [50], "slow": [100, 200]},
        direction="long",
        lookback=200,
        indicators=["ema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="RBN",
    ),
    # Bearish ribbon (fast < medium < slow)
    PatternBlock(
        id="MA_RIBBON_BEARISH",
        name="MA Ribbon Bearish Alignment",
        category="ma_ribbon",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
df['ema_med'] = ta.EMA(df['close'], timeperiod={medium})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
df['aligned'] = (df['ema_fast'] < df['ema_med']) & (df['ema_med'] < df['ema_slow'])
df['price_below'] = df['close'] < df['ema_fast']
df['entry_signal'] = df['aligned'] & df['price_below']""",
        params={"fast": [10, 20], "medium": [50], "slow": [100, 200]},
        direction="short",
        lookback=200,
        indicators=["ema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="RBN",
    ),
    # Ribbon squeeze (MAs converging)
    PatternBlock(
        id="MA_RIBBON_SQUEEZE",
        name="MA Ribbon Squeeze",
        category="ma_ribbon",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
df['ribbon_width'] = (df['ema_fast'] - df['ema_slow']).abs() / df['close']
df['avg_width'] = df['ribbon_width'].rolling({lookback}).mean()
df['entry_signal'] = df['ribbon_width'] < df['avg_width'] * {threshold}""",
        params={"fast": [10], "slow": [50], "lookback": [20], "threshold": [0.3, 0.5]},
        direction="bidi",
        lookback=80,
        indicators=["ema"],
        combinable_with=["volume", "crossover", "confirmation"],
        strategy_type="RBN",
    ),
]


# =============================================================================
# HEIKIN-ASHI BLOCKS
# =============================================================================

HEIKIN_ASHI_BLOCKS = [
    # HA bullish (green candle, no lower wick)
    PatternBlock(
        id="HA_BULLISH_STRONG",
        name="Heikin-Ashi Strong Bullish",
        category="heikin_ashi",
        formula_template="""df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
df['ha_open'] = ((df['open'].shift(1) + df['close'].shift(1)) / 2).fillna(df['open'])
df['ha_high'] = df[['high', 'ha_open', 'ha_close']].max(axis=1)
df['ha_low'] = df[['low', 'ha_open', 'ha_close']].min(axis=1)
df['ha_bullish'] = df['ha_close'] > df['ha_open']
df['no_lower_wick'] = df['ha_low'] >= df[['ha_open', 'ha_close']].min(axis=1) * 0.999
df['entry_signal'] = df['ha_bullish'] & df['no_lower_wick']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="HAK",
    ),
    # HA bearish (red candle, no upper wick)
    PatternBlock(
        id="HA_BEARISH_STRONG",
        name="Heikin-Ashi Strong Bearish",
        category="heikin_ashi",
        formula_template="""df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
df['ha_open'] = ((df['open'].shift(1) + df['close'].shift(1)) / 2).fillna(df['open'])
df['ha_high'] = df[['high', 'ha_open', 'ha_close']].max(axis=1)
df['ha_low'] = df[['low', 'ha_open', 'ha_close']].min(axis=1)
df['ha_bearish'] = df['ha_close'] < df['ha_open']
df['no_upper_wick'] = df['ha_high'] <= df[['ha_open', 'ha_close']].max(axis=1) * 1.001
df['entry_signal'] = df['ha_bearish'] & df['no_upper_wick']""",
        params={},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="HAK",
    ),
    # HA trend reversal to bullish
    PatternBlock(
        id="HA_REVERSAL_BULLISH",
        name="Heikin-Ashi Reversal Bullish",
        category="heikin_ashi",
        formula_template="""df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
df['ha_open'] = ((df['open'].shift(1) + df['close'].shift(1)) / 2).fillna(df['open'])
df['ha_bullish'] = df['ha_close'] > df['ha_open']
df['was_bearish'] = df['ha_close'].shift(1) < df['ha_open'].shift(1)
df['entry_signal'] = df['ha_bullish'] & df['was_bearish']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="HAK",
    ),
    # HA trend reversal to bearish
    PatternBlock(
        id="HA_REVERSAL_BEARISH",
        name="Heikin-Ashi Reversal Bearish",
        category="heikin_ashi",
        formula_template="""df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
df['ha_open'] = ((df['open'].shift(1) + df['close'].shift(1)) / 2).fillna(df['open'])
df['ha_bearish'] = df['ha_close'] < df['ha_open']
df['was_bullish'] = df['ha_close'].shift(1) > df['ha_open'].shift(1)
df['entry_signal'] = df['ha_bearish'] & df['was_bullish']""",
        params={},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="HAK",
    ),
]


# =============================================================================
# FORCE INDEX BLOCKS
# =============================================================================

FORCE_INDEX_BLOCKS = [
    # Force Index positive
    PatternBlock(
        id="FORCE_INDEX_POSITIVE",
        name="Force Index Positive",
        category="force_index",
        formula_template="""df['force'] = df['close'].diff() * df['volume']
df['force_ema'] = ta.EMA(df['force'], timeperiod={period})
df['entry_signal'] = df['force_ema'] > {threshold}""",
        params={"period": [13, 21], "threshold": [0]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="FRC",
    ),
    # Force Index negative
    PatternBlock(
        id="FORCE_INDEX_NEGATIVE",
        name="Force Index Negative",
        category="force_index",
        formula_template="""df['force'] = df['close'].diff() * df['volume']
df['force_ema'] = ta.EMA(df['force'], timeperiod={period})
df['entry_signal'] = df['force_ema'] < -{threshold}""",
        params={"period": [13, 21], "threshold": [0]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="FRC",
    ),
    # Force Index cross zero up
    PatternBlock(
        id="FORCE_INDEX_CROSS_UP",
        name="Force Index Cross Zero Up",
        category="force_index",
        formula_template="""df['force'] = df['close'].diff() * df['volume']
df['force_ema'] = ta.EMA(df['force'], timeperiod={period})
df['force_positive'] = df['force_ema'] > 0
df['was_negative'] = df['force_ema'].shift(1) <= 0
df['entry_signal'] = df['force_positive'] & df['was_negative']""",
        params={"period": [13, 21]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="FRC",
    ),
    # Force Index cross zero down
    PatternBlock(
        id="FORCE_INDEX_CROSS_DOWN",
        name="Force Index Cross Zero Down",
        category="force_index",
        formula_template="""df['force'] = df['close'].diff() * df['volume']
df['force_ema'] = ta.EMA(df['force'], timeperiod={period})
df['force_negative'] = df['force_ema'] < 0
df['was_positive'] = df['force_ema'].shift(1) >= 0
df['entry_signal'] = df['force_negative'] & df['was_positive']""",
        params={"period": [13, 21]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="FRC",
    ),
]


# =============================================================================
# KLINGER OSCILLATOR BLOCKS
# =============================================================================

KLINGER_BLOCKS = [
    # Klinger positive
    PatternBlock(
        id="KLINGER_POSITIVE",
        name="Klinger Oscillator Positive",
        category="klinger",
        formula_template="""df['hlc'] = df['high'] + df['low'] + df['close']
df['trend'] = (df['hlc'] > df['hlc'].shift(1)).astype(int) * 2 - 1
df['dm'] = df['high'] - df['low']
df['cm'] = df['dm'].where(df['trend'] == df['trend'].shift(1), df['dm'] + df['dm'].shift(1))
df['vf'] = df['volume'] * df['trend'] * (2 * df['dm'] / df['cm'] - 1).abs() * 100
df['kvo'] = ta.EMA(df['vf'], timeperiod={fast}) - ta.EMA(df['vf'], timeperiod={slow})
df['entry_signal'] = df['kvo'] > {threshold}""",
        params={"fast": [34], "slow": [55], "threshold": [0]},
        direction="long",
        lookback=70,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="KLG",
    ),
    # Klinger negative
    PatternBlock(
        id="KLINGER_NEGATIVE",
        name="Klinger Oscillator Negative",
        category="klinger",
        formula_template="""df['hlc'] = df['high'] + df['low'] + df['close']
df['trend'] = (df['hlc'] > df['hlc'].shift(1)).astype(int) * 2 - 1
df['dm'] = df['high'] - df['low']
df['cm'] = df['dm'].where(df['trend'] == df['trend'].shift(1), df['dm'] + df['dm'].shift(1))
df['vf'] = df['volume'] * df['trend'] * (2 * df['dm'] / df['cm'] - 1).abs() * 100
df['kvo'] = ta.EMA(df['vf'], timeperiod={fast}) - ta.EMA(df['vf'], timeperiod={slow})
df['entry_signal'] = df['kvo'] < -{threshold}""",
        params={"fast": [34], "slow": [55], "threshold": [0]},
        direction="short",
        lookback=70,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="KLG",
    ),
    # Klinger cross signal line up
    PatternBlock(
        id="KLINGER_SIGNAL_CROSS_UP",
        name="Klinger Cross Signal Up",
        category="klinger",
        formula_template="""df['hlc'] = df['high'] + df['low'] + df['close']
df['trend'] = (df['hlc'] > df['hlc'].shift(1)).astype(int) * 2 - 1
df['dm'] = df['high'] - df['low']
df['cm'] = df['dm'].where(df['trend'] == df['trend'].shift(1), df['dm'] + df['dm'].shift(1))
df['vf'] = df['volume'] * df['trend'] * (2 * df['dm'] / df['cm'] - 1).abs() * 100
df['kvo'] = ta.EMA(df['vf'], timeperiod={fast}) - ta.EMA(df['vf'], timeperiod={slow})
df['kvo_signal'] = ta.EMA(df['kvo'], timeperiod={signal})
df['kvo_above'] = df['kvo'] > df['kvo_signal']
df['was_below'] = df['kvo'].shift(1) <= df['kvo_signal'].shift(1)
df['entry_signal'] = df['kvo_above'] & df['was_below']""",
        params={"fast": [34], "slow": [55], "signal": [13]},
        direction="long",
        lookback=70,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="KLG",
    ),
    # Klinger cross signal line down
    PatternBlock(
        id="KLINGER_SIGNAL_CROSS_DOWN",
        name="Klinger Cross Signal Down",
        category="klinger",
        formula_template="""df['hlc'] = df['high'] + df['low'] + df['close']
df['trend'] = (df['hlc'] > df['hlc'].shift(1)).astype(int) * 2 - 1
df['dm'] = df['high'] - df['low']
df['cm'] = df['dm'].where(df['trend'] == df['trend'].shift(1), df['dm'] + df['dm'].shift(1))
df['vf'] = df['volume'] * df['trend'] * (2 * df['dm'] / df['cm'] - 1).abs() * 100
df['kvo'] = ta.EMA(df['vf'], timeperiod={fast}) - ta.EMA(df['vf'], timeperiod={slow})
df['kvo_signal'] = ta.EMA(df['kvo'], timeperiod={signal})
df['kvo_below'] = df['kvo'] < df['kvo_signal']
df['was_above'] = df['kvo'].shift(1) >= df['kvo_signal'].shift(1)
df['entry_signal'] = df['kvo_below'] & df['was_above']""",
        params={"fast": [34], "slow": [55], "signal": [13]},
        direction="short",
        lookback=70,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="KLG",
    ),
]


# =============================================================================
# EASE OF MOVEMENT BLOCKS
# =============================================================================

EMV_BLOCKS = [
    # EMV positive (easy upward movement)
    PatternBlock(
        id="EMV_POSITIVE",
        name="Ease of Movement Positive",
        category="emv",
        formula_template="""df['dm'] = ((df['high'] + df['low']) / 2) - ((df['high'].shift(1) + df['low'].shift(1)) / 2)
df['br'] = df['volume'] / (df['high'] - df['low'] + 1e-10)
df['emv'] = df['dm'] / (br + 1e-10)
df['emv_ma'] = df['emv'].rolling({period}).mean()
df['entry_signal'] = df['emv_ma'] > {threshold}""",
        params={"period": [14], "threshold": [0]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="EMV",
    ),
    # EMV negative (easy downward movement)
    PatternBlock(
        id="EMV_NEGATIVE",
        name="Ease of Movement Negative",
        category="emv",
        formula_template="""df['dm'] = ((df['high'] + df['low']) / 2) - ((df['high'].shift(1) + df['low'].shift(1)) / 2)
df['br'] = df['volume'] / (df['high'] - df['low'] + 1e-10)
df['emv'] = df['dm'] / (br + 1e-10)
df['emv_ma'] = df['emv'].rolling({period}).mean()
df['entry_signal'] = df['emv_ma'] < -{threshold}""",
        params={"period": [14], "threshold": [0]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="EMV",
    ),
    # EMV cross zero up
    PatternBlock(
        id="EMV_CROSS_ZERO_UP",
        name="EMV Cross Zero Up",
        category="emv",
        formula_template="""df['dm'] = ((df['high'] + df['low']) / 2) - ((df['high'].shift(1) + df['low'].shift(1)) / 2)
df['br'] = df['volume'] / (df['high'] - df['low'] + 1e-10)
df['emv'] = df['dm'] / (br + 1e-10)
df['emv_ma'] = df['emv'].rolling({period}).mean()
df['emv_positive'] = df['emv_ma'] > 0
df['was_negative'] = df['emv_ma'].shift(1) <= 0
df['entry_signal'] = df['emv_positive'] & df['was_negative']""",
        params={"period": [14]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="EMV",
    ),
    # EMV cross zero down
    PatternBlock(
        id="EMV_CROSS_ZERO_DOWN",
        name="EMV Cross Zero Down",
        category="emv",
        formula_template="""df['dm'] = ((df['high'] + df['low']) / 2) - ((df['high'].shift(1) + df['low'].shift(1)) / 2)
df['br'] = df['volume'] / (df['high'] - df['low'] + 1e-10)
df['emv'] = df['dm'] / (br + 1e-10)
df['emv_ma'] = df['emv'].rolling({period}).mean()
df['emv_negative'] = df['emv_ma'] < 0
df['was_positive'] = df['emv_ma'].shift(1) >= 0
df['entry_signal'] = df['emv_negative'] & df['was_positive']""",
        params={"period": [14]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="EMV",
    ),
]


# =============================================================================
# TEMA/DEMA BLOCKS
# =============================================================================

TEMA_DEMA_BLOCKS = [
    # TEMA cross up
    PatternBlock(
        id="TEMA_CROSS_UP",
        name="TEMA Cross Price Up",
        category="tema_dema",
        formula_template="""df['tema'] = ta.TEMA(df['close'], timeperiod={period})
df['price_above'] = df['close'] > df['tema']
df['was_below'] = df['close'].shift(1) <= df['tema'].shift(1)
df['entry_signal'] = df['price_above'] & df['was_below']""",
        params={"period": [10, 20, 30]},
        direction="long",
        lookback=50,
        indicators=["tema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="TDM",
    ),
    # TEMA cross down
    PatternBlock(
        id="TEMA_CROSS_DOWN",
        name="TEMA Cross Price Down",
        category="tema_dema",
        formula_template="""df['tema'] = ta.TEMA(df['close'], timeperiod={period})
df['price_below'] = df['close'] < df['tema']
df['was_above'] = df['close'].shift(1) >= df['tema'].shift(1)
df['entry_signal'] = df['price_below'] & df['was_above']""",
        params={"period": [10, 20, 30]},
        direction="short",
        lookback=50,
        indicators=["tema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="TDM",
    ),
    # DEMA cross up
    PatternBlock(
        id="DEMA_CROSS_UP",
        name="DEMA Cross Price Up",
        category="tema_dema",
        formula_template="""df['dema'] = ta.DEMA(df['close'], timeperiod={period})
df['price_above'] = df['close'] > df['dema']
df['was_below'] = df['close'].shift(1) <= df['dema'].shift(1)
df['entry_signal'] = df['price_above'] & df['was_below']""",
        params={"period": [10, 20, 30]},
        direction="long",
        lookback=50,
        indicators=["dema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="TDM",
    ),
    # DEMA cross down
    PatternBlock(
        id="DEMA_CROSS_DOWN",
        name="DEMA Cross Price Down",
        category="tema_dema",
        formula_template="""df['dema'] = ta.DEMA(df['close'], timeperiod={period})
df['price_below'] = df['close'] < df['dema']
df['was_above'] = df['close'].shift(1) >= df['dema'].shift(1)
df['entry_signal'] = df['price_below'] & df['was_above']""",
        params={"period": [10, 20, 30]},
        direction="short",
        lookback=50,
        indicators=["dema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="TDM",
    ),
]


# =============================================================================
# COPPOCK CURVE BLOCKS
# =============================================================================

COPPOCK_BLOCKS = [
    # Coppock cross zero up (long-term buy signal)
    PatternBlock(
        id="COPPOCK_CROSS_UP",
        name="Coppock Curve Cross Zero Up",
        category="coppock",
        formula_template="""df['roc_long'] = ta.ROC(df['close'], timeperiod={long_roc})
df['roc_short'] = ta.ROC(df['close'], timeperiod={short_roc})
df['coppock'] = ta.WMA(df['roc_long'] + df['roc_short'], timeperiod={wma})
df['coppock_positive'] = df['coppock'] > 0
df['was_negative'] = df['coppock'].shift(1) <= 0
df['entry_signal'] = df['coppock_positive'] & df['was_negative']""",
        params={"long_roc": [14], "short_roc": [11], "wma": [10]},
        direction="long",
        lookback=50,
        indicators=["roc", "wma"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="COP",
    ),
    # Coppock cross zero down
    PatternBlock(
        id="COPPOCK_CROSS_DOWN",
        name="Coppock Curve Cross Zero Down",
        category="coppock",
        formula_template="""df['roc_long'] = ta.ROC(df['close'], timeperiod={long_roc})
df['roc_short'] = ta.ROC(df['close'], timeperiod={short_roc})
df['coppock'] = ta.WMA(df['roc_long'] + df['roc_short'], timeperiod={wma})
df['coppock_negative'] = df['coppock'] < 0
df['was_positive'] = df['coppock'].shift(1) >= 0
df['entry_signal'] = df['coppock_negative'] & df['was_positive']""",
        params={"long_roc": [14], "short_roc": [11], "wma": [10]},
        direction="short",
        lookback=50,
        indicators=["roc", "wma"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="COP",
    ),
    # Coppock rising
    PatternBlock(
        id="COPPOCK_RISING",
        name="Coppock Curve Rising",
        category="coppock",
        formula_template="""df['roc_long'] = ta.ROC(df['close'], timeperiod={long_roc})
df['roc_short'] = ta.ROC(df['close'], timeperiod={short_roc})
df['coppock'] = ta.WMA(df['roc_long'] + df['roc_short'], timeperiod={wma})
df['coppock_rising'] = df['coppock'] > df['coppock'].shift(1)
df['consecutive'] = df['coppock_rising'].rolling({bars}).sum() >= {bars}
df['entry_signal'] = df['consecutive']""",
        params={"long_roc": [14], "short_roc": [11], "wma": [10], "bars": [2, 3]},
        direction="long",
        lookback=50,
        indicators=["roc", "wma"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="COP",
    ),
    # Coppock falling
    PatternBlock(
        id="COPPOCK_FALLING",
        name="Coppock Curve Falling",
        category="coppock",
        formula_template="""df['roc_long'] = ta.ROC(df['close'], timeperiod={long_roc})
df['roc_short'] = ta.ROC(df['close'], timeperiod={short_roc})
df['coppock'] = ta.WMA(df['roc_long'] + df['roc_short'], timeperiod={wma})
df['coppock_falling'] = df['coppock'] < df['coppock'].shift(1)
df['consecutive'] = df['coppock_falling'].rolling({bars}).sum() >= {bars}
df['entry_signal'] = df['consecutive']""",
        params={"long_roc": [14], "short_roc": [11], "wma": [10], "bars": [2, 3]},
        direction="short",
        lookback=50,
        indicators=["roc", "wma"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="COP",
    ),
]


# =============================================================================
# KELTNER CHANNEL BLOCKS
# =============================================================================

KELTNER_BLOCKS = [
    # Price breaks above upper Keltner band
    PatternBlock(
        id="KELTNER_BREAK_UPPER",
        name="Keltner Channel Breakout Up",
        category="keltner",
        formula_template="""df['kelt_mid'] = ta.EMA(df['close'], timeperiod={period})
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['kelt_upper'] = df['kelt_mid'] + {mult} * df['atr']
df['entry_signal'] = df['close'] > df['kelt_upper']""",
        params={"period": [20], "mult": [1.5, 2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=["ema", "atr"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="KLT",
    ),
    # Price breaks below lower Keltner band
    PatternBlock(
        id="KELTNER_BREAK_LOWER",
        name="Keltner Channel Breakout Down",
        category="keltner",
        formula_template="""df['kelt_mid'] = ta.EMA(df['close'], timeperiod={period})
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['kelt_lower'] = df['kelt_mid'] - {mult} * df['atr']
df['entry_signal'] = df['close'] < df['kelt_lower']""",
        params={"period": [20], "mult": [1.5, 2.0, 2.5]},
        direction="short",
        lookback=30,
        indicators=["ema", "atr"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="KLT",
    ),
    # Price returns to mid from upper (mean reversion)
    PatternBlock(
        id="KELTNER_REVERT_FROM_UPPER",
        name="Keltner Mean Reversion from Upper",
        category="keltner",
        formula_template="""df['kelt_mid'] = ta.EMA(df['close'], timeperiod={period})
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['kelt_upper'] = df['kelt_mid'] + {mult} * df['atr']
df['was_above'] = df['close'].shift(1) > df['kelt_upper'].shift(1)
df['now_below'] = df['close'] <= df['kelt_upper']
df['entry_signal'] = df['was_above'] & df['now_below']""",
        params={"period": [20], "mult": [2.0, 2.5]},
        direction="short",
        lookback=30,
        indicators=["ema", "atr"],
        combinable_with=["volume", "threshold"],
        strategy_type="KLT",
    ),
    # Price returns to mid from lower (mean reversion)
    PatternBlock(
        id="KELTNER_REVERT_FROM_LOWER",
        name="Keltner Mean Reversion from Lower",
        category="keltner",
        formula_template="""df['kelt_mid'] = ta.EMA(df['close'], timeperiod={period})
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['kelt_lower'] = df['kelt_mid'] - {mult} * df['atr']
df['was_below'] = df['close'].shift(1) < df['kelt_lower'].shift(1)
df['now_above'] = df['close'] >= df['kelt_lower']
df['entry_signal'] = df['was_below'] & df['now_above']""",
        params={"period": [20], "mult": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=["ema", "atr"],
        combinable_with=["volume", "threshold"],
        strategy_type="KLT",
    ),
]


# =============================================================================
# DONCHIAN CHANNEL BLOCKS
# =============================================================================

DONCHIAN_BLOCKS = [
    # Price breaks above N-period high (Turtle long entry)
    PatternBlock(
        id="DONCHIAN_BREAK_HIGH",
        name="Donchian Breakout High",
        category="donchian",
        formula_template="""df['donch_high'] = df['high'].rolling({period}).max().shift(1)
df['entry_signal'] = df['high'] > df['donch_high']""",
        params={"period": [20, 55]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="DON",
    ),
    # Price breaks below N-period low (Turtle short entry)
    PatternBlock(
        id="DONCHIAN_BREAK_LOW",
        name="Donchian Breakout Low",
        category="donchian",
        formula_template="""df['donch_low'] = df['low'].rolling({period}).min().shift(1)
df['entry_signal'] = df['low'] < df['donch_low']""",
        params={"period": [20, 55]},
        direction="short",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="DON",
    ),
    # Donchian channel width contracting (squeeze)
    PatternBlock(
        id="DONCHIAN_SQUEEZE",
        name="Donchian Channel Squeeze",
        category="donchian",
        formula_template="""df['donch_high'] = df['high'].rolling({period}).max()
df['donch_low'] = df['low'].rolling({period}).min()
df['donch_width'] = (df['donch_high'] - df['donch_low']) / df['close']
df['width_avg'] = df['donch_width'].rolling({period}).mean()
df['entry_signal'] = df['donch_width'] < df['width_avg'] * {squeeze_mult}""",
        params={"period": [20], "squeeze_mult": [0.5, 0.7]},
        direction="bidi",
        lookback=40,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="DON",
    ),
    # Price at middle of Donchian (trend following)
    PatternBlock(
        id="DONCHIAN_MID_CROSS_UP",
        name="Donchian Mid Cross Up",
        category="donchian",
        formula_template="""df['donch_high'] = df['high'].rolling({period}).max()
df['donch_low'] = df['low'].rolling({period}).min()
df['donch_mid'] = (df['donch_high'] + df['donch_low']) / 2
df['above_mid'] = df['close'] > df['donch_mid']
df['was_below'] = df['close'].shift(1) <= df['donch_mid'].shift(1)
df['entry_signal'] = df['above_mid'] & df['was_below']""",
        params={"period": [20, 55]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="DON",
    ),
]


# =============================================================================
# WILLIAMS %R BLOCKS
# =============================================================================

WILLIAMS_R_BLOCKS = [
    # Williams %R oversold
    PatternBlock(
        id="WILLR_OVERSOLD",
        name="Williams %R Oversold",
        category="williams_r",
        formula_template="""df['willr'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod={period})
df['entry_signal'] = df['willr'] < -{threshold}""",
        params={"period": [14, 21], "threshold": [80, 90]},
        direction="long",
        lookback=30,
        indicators=["willr"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="WLR",
    ),
    # Williams %R overbought
    PatternBlock(
        id="WILLR_OVERBOUGHT",
        name="Williams %R Overbought",
        category="williams_r",
        formula_template="""df['willr'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod={period})
df['entry_signal'] = df['willr'] > -{threshold}""",
        params={"period": [14, 21], "threshold": [10, 20]},
        direction="short",
        lookback=30,
        indicators=["willr"],
        combinable_with=["volume", "price_action", "confirmation"],
        strategy_type="WLR",
    ),
    # Williams %R exit oversold zone
    PatternBlock(
        id="WILLR_EXIT_OVERSOLD",
        name="Williams %R Exit Oversold",
        category="williams_r",
        formula_template="""df['willr'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod={period})
df['was_oversold'] = df['willr'].shift(1) < -{threshold}
df['now_above'] = df['willr'] >= -{threshold}
df['entry_signal'] = df['was_oversold'] & df['now_above']""",
        params={"period": [14], "threshold": [80]},
        direction="long",
        lookback=30,
        indicators=["willr"],
        combinable_with=["volume", "threshold"],
        strategy_type="WLR",
    ),
    # Williams %R exit overbought zone
    PatternBlock(
        id="WILLR_EXIT_OVERBOUGHT",
        name="Williams %R Exit Overbought",
        category="williams_r",
        formula_template="""df['willr'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod={period})
df['was_overbought'] = df['willr'].shift(1) > -{threshold}
df['now_below'] = df['willr'] <= -{threshold}
df['entry_signal'] = df['was_overbought'] & df['now_below']""",
        params={"period": [14], "threshold": [20]},
        direction="short",
        lookback=30,
        indicators=["willr"],
        combinable_with=["volume", "threshold"],
        strategy_type="WLR",
    ),
]


# =============================================================================
# MFI (MONEY FLOW INDEX) BLOCKS
# =============================================================================

MFI_BLOCKS = [
    # MFI oversold
    PatternBlock(
        id="MFI_OVERSOLD",
        name="Money Flow Index Oversold",
        category="mfi",
        formula_template="""df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod={period})
df['entry_signal'] = df['mfi'] < {threshold}""",
        params={"period": [14], "threshold": [20, 25, 30]},
        direction="long",
        lookback=30,
        indicators=["mfi"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="MFI",
    ),
    # MFI overbought
    PatternBlock(
        id="MFI_OVERBOUGHT",
        name="Money Flow Index Overbought",
        category="mfi",
        formula_template="""df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod={period})
df['entry_signal'] = df['mfi'] > {threshold}""",
        params={"period": [14], "threshold": [70, 75, 80]},
        direction="short",
        lookback=30,
        indicators=["mfi"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="MFI",
    ),
    # MFI bullish divergence (price lower low, MFI higher low)
    PatternBlock(
        id="MFI_BULLISH_DIV",
        name="MFI Bullish Divergence",
        category="mfi",
        formula_template="""df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod={period})
df['price_ll'] = df['low'] < df['low'].rolling({lookback}).min().shift(1)
df['mfi_hl'] = df['mfi'] > df['mfi'].rolling({lookback}).min().shift(1)
df['entry_signal'] = df['price_ll'] & df['mfi_hl']""",
        params={"period": [14], "lookback": [10, 20]},
        direction="long",
        lookback=40,
        indicators=["mfi"],
        combinable_with=["volume", "threshold"],
        strategy_type="MFI",
    ),
    # MFI bearish divergence (price higher high, MFI lower high)
    PatternBlock(
        id="MFI_BEARISH_DIV",
        name="MFI Bearish Divergence",
        category="mfi",
        formula_template="""df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod={period})
df['price_hh'] = df['high'] > df['high'].rolling({lookback}).max().shift(1)
df['mfi_lh'] = df['mfi'] < df['mfi'].rolling({lookback}).max().shift(1)
df['entry_signal'] = df['price_hh'] & df['mfi_lh']""",
        params={"period": [14], "lookback": [10, 20]},
        direction="short",
        lookback=40,
        indicators=["mfi"],
        combinable_with=["volume", "threshold"],
        strategy_type="MFI",
    ),
]


# =============================================================================
# KAMA (KAUFMAN ADAPTIVE MA) BLOCKS
# =============================================================================

KAMA_BLOCKS = [
    # Price crosses above KAMA
    PatternBlock(
        id="KAMA_CROSS_UP",
        name="KAMA Cross Up",
        category="kama",
        formula_template="""df['kama'] = ta.KAMA(df['close'], timeperiod={period})
df['above'] = df['close'] > df['kama']
df['was_below'] = df['close'].shift(1) <= df['kama'].shift(1)
df['entry_signal'] = df['above'] & df['was_below']""",
        params={"period": [10, 20, 30]},
        direction="long",
        lookback=40,
        indicators=["kama"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="KAM",
    ),
    # Price crosses below KAMA
    PatternBlock(
        id="KAMA_CROSS_DOWN",
        name="KAMA Cross Down",
        category="kama",
        formula_template="""df['kama'] = ta.KAMA(df['close'], timeperiod={period})
df['below'] = df['close'] < df['kama']
df['was_above'] = df['close'].shift(1) >= df['kama'].shift(1)
df['entry_signal'] = df['below'] & df['was_above']""",
        params={"period": [10, 20, 30]},
        direction="short",
        lookback=40,
        indicators=["kama"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="KAM",
    ),
    # KAMA slope positive
    PatternBlock(
        id="KAMA_SLOPE_UP",
        name="KAMA Slope Positive",
        category="kama",
        formula_template="""df['kama'] = ta.KAMA(df['close'], timeperiod={period})
df['kama_slope'] = df['kama'] - df['kama'].shift({slope_period})
df['entry_signal'] = df['kama_slope'] > 0""",
        params={"period": [20], "slope_period": [3, 5]},
        direction="long",
        lookback=40,
        indicators=["kama"],
        combinable_with=["volume", "threshold"],
        strategy_type="KAM",
    ),
    # KAMA slope negative
    PatternBlock(
        id="KAMA_SLOPE_DOWN",
        name="KAMA Slope Negative",
        category="kama",
        formula_template="""df['kama'] = ta.KAMA(df['close'], timeperiod={period})
df['kama_slope'] = df['kama'] - df['kama'].shift({slope_period})
df['entry_signal'] = df['kama_slope'] < 0""",
        params={"period": [20], "slope_period": [3, 5]},
        direction="short",
        lookback=40,
        indicators=["kama"],
        combinable_with=["volume", "threshold"],
        strategy_type="KAM",
    ),
]


# =============================================================================
# NATR (NORMALIZED ATR) BLOCKS
# =============================================================================

NATR_BLOCKS = [
    # Volatility expansion (NATR above threshold)
    PatternBlock(
        id="NATR_HIGH_VOL",
        name="NATR High Volatility",
        category="natr",
        formula_template="""df['natr'] = ta.NATR(df['high'], df['low'], df['close'], timeperiod={period})
df['entry_signal'] = df['natr'] > {threshold}""",
        params={"period": [14], "threshold": [2.0, 3.0, 4.0]},
        direction="bidi",
        lookback=30,
        indicators=["natr"],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="NTR",
    ),
    # Volatility contraction (NATR below average)
    PatternBlock(
        id="NATR_LOW_VOL",
        name="NATR Low Volatility",
        category="natr",
        formula_template="""df['natr'] = ta.NATR(df['high'], df['low'], df['close'], timeperiod={period})
df['natr_avg'] = df['natr'].rolling({avg_period}).mean()
df['entry_signal'] = df['natr'] < df['natr_avg'] * {squeeze_mult}""",
        params={"period": [14], "avg_period": [20], "squeeze_mult": [0.5, 0.7]},
        direction="bidi",
        lookback=40,
        indicators=["natr"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="NTR",
    ),
    # Volatility breakout (NATR increases sharply)
    PatternBlock(
        id="NATR_BREAKOUT",
        name="NATR Volatility Breakout",
        category="natr",
        formula_template="""df['natr'] = ta.NATR(df['high'], df['low'], df['close'], timeperiod={period})
df['natr_prev'] = df['natr'].shift(1)
df['vol_increase'] = df['natr'] / df['natr_prev']
df['entry_signal'] = df['vol_increase'] > {mult}""",
        params={"period": [14], "mult": [1.5, 2.0]},
        direction="bidi",
        lookback=30,
        indicators=["natr"],
        combinable_with=["threshold", "momentum"],
        strategy_type="NTR",
    ),
]


# =============================================================================
# HILBERT TRANSFORM BLOCKS
# =============================================================================

HILBERT_BLOCKS = [
    # Hilbert trendline cross up
    PatternBlock(
        id="HT_TRENDLINE_CROSS_UP",
        name="Hilbert Trendline Cross Up",
        category="hilbert",
        formula_template="""df['ht_trendline'] = ta.HT_TRENDLINE(df['close'])
df['above'] = df['close'] > df['ht_trendline']
df['was_below'] = df['close'].shift(1) <= df['ht_trendline'].shift(1)
df['entry_signal'] = df['above'] & df['was_below']""",
        params={},
        direction="long",
        lookback=60,
        indicators=["ht_trendline"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="HLB",
    ),
    # Hilbert trendline cross down
    PatternBlock(
        id="HT_TRENDLINE_CROSS_DOWN",
        name="Hilbert Trendline Cross Down",
        category="hilbert",
        formula_template="""df['ht_trendline'] = ta.HT_TRENDLINE(df['close'])
df['below'] = df['close'] < df['ht_trendline']
df['was_above'] = df['close'].shift(1) >= df['ht_trendline'].shift(1)
df['entry_signal'] = df['below'] & df['was_above']""",
        params={},
        direction="short",
        lookback=60,
        indicators=["ht_trendline"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="HLB",
    ),
    # Hilbert trend mode (1 = trend, 0 = cycle)
    PatternBlock(
        id="HT_TREND_MODE",
        name="Hilbert Trend Mode",
        category="hilbert",
        formula_template="""df['ht_trend'] = ta.HT_TRENDMODE(df['close'])
df['entry_signal'] = df['ht_trend'] == 1""",
        params={},
        direction="bidi",
        lookback=60,
        indicators=["ht_trendmode"],
        combinable_with=["threshold", "momentum", "confirmation"],
        strategy_type="HLB",
    ),
    # Hilbert cycle mode
    PatternBlock(
        id="HT_CYCLE_MODE",
        name="Hilbert Cycle Mode",
        category="hilbert",
        formula_template="""df['ht_trend'] = ta.HT_TRENDMODE(df['close'])
df['entry_signal'] = df['ht_trend'] == 0""",
        params={},
        direction="bidi",
        lookback=60,
        indicators=["ht_trendmode"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="HLB",
    ),
]


# =============================================================================
# CANDLESTICK PATTERN BLOCKS (TA-LIB)
# =============================================================================

CANDLE_PATTERN_BLOCKS = [
    # Bullish Engulfing
    PatternBlock(
        id="CDL_ENGULFING_BULL",
        name="Bullish Engulfing Pattern",
        category="candle_pattern",
        formula_template="""df['cdl_engulfing'] = ta.CDLENGULFING(df['open'], df['high'], df['low'], df['close'])
df['entry_signal'] = df['cdl_engulfing'] > 0""",
        params={},
        direction="long",
        lookback=10,
        indicators=["cdl_engulfing"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CDL",
    ),
    # Bearish Engulfing
    PatternBlock(
        id="CDL_ENGULFING_BEAR",
        name="Bearish Engulfing Pattern",
        category="candle_pattern",
        formula_template="""df['cdl_engulfing'] = ta.CDLENGULFING(df['open'], df['high'], df['low'], df['close'])
df['entry_signal'] = df['cdl_engulfing'] < 0""",
        params={},
        direction="short",
        lookback=10,
        indicators=["cdl_engulfing"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CDL",
    ),
    # Hammer (bullish reversal)
    PatternBlock(
        id="CDL_HAMMER",
        name="Hammer Pattern",
        category="candle_pattern",
        formula_template="""df['cdl_hammer'] = ta.CDLHAMMER(df['open'], df['high'], df['low'], df['close'])
df['entry_signal'] = df['cdl_hammer'] != 0""",
        params={},
        direction="long",
        lookback=10,
        indicators=["cdl_hammer"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CDL",
    ),
    # Shooting Star (bearish reversal)
    PatternBlock(
        id="CDL_SHOOTINGSTAR",
        name="Shooting Star Pattern",
        category="candle_pattern",
        formula_template="""df['cdl_star'] = ta.CDLSHOOTINGSTAR(df['open'], df['high'], df['low'], df['close'])
df['entry_signal'] = df['cdl_star'] != 0""",
        params={},
        direction="short",
        lookback=10,
        indicators=["cdl_shootingstar"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CDL",
    ),
    # Morning Star (bullish reversal)
    PatternBlock(
        id="CDL_MORNINGSTAR",
        name="Morning Star Pattern",
        category="candle_pattern",
        formula_template="""df['cdl_morning'] = ta.CDLMORNINGSTAR(df['open'], df['high'], df['low'], df['close'])
df['entry_signal'] = df['cdl_morning'] != 0""",
        params={},
        direction="long",
        lookback=10,
        indicators=["cdl_morningstar"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CDL",
    ),
    # Evening Star (bearish reversal)
    PatternBlock(
        id="CDL_EVENINGSTAR",
        name="Evening Star Pattern",
        category="candle_pattern",
        formula_template="""df['cdl_evening'] = ta.CDLEVENINGSTAR(df['open'], df['high'], df['low'], df['close'])
df['entry_signal'] = df['cdl_evening'] != 0""",
        params={},
        direction="short",
        lookback=10,
        indicators=["cdl_eveningstar"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CDL",
    ),
]


# =============================================================================
# STOCHASTIC RSI BLOCKS
# =============================================================================

STOCH_RSI_BLOCKS = [
    # Stoch RSI oversold
    PatternBlock(
        id="STOCHRSI_OVERSOLD",
        name="Stochastic RSI Oversold",
        category="stoch_rsi",
        formula_template="""df['fastk'], df['fastd'] = ta.STOCHRSI(df['close'], timeperiod={period}, fastk_period={fastk}, fastd_period={fastd})
df['entry_signal'] = df['fastk'] < {threshold}""",
        params={"period": [14], "fastk": [5], "fastd": [3], "threshold": [20, 25]},
        direction="long",
        lookback=30,
        indicators=["stochrsi"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="SRI",
    ),
    # Stoch RSI overbought
    PatternBlock(
        id="STOCHRSI_OVERBOUGHT",
        name="Stochastic RSI Overbought",
        category="stoch_rsi",
        formula_template="""df['fastk'], df['fastd'] = ta.STOCHRSI(df['close'], timeperiod={period}, fastk_period={fastk}, fastd_period={fastd})
df['entry_signal'] = df['fastk'] > {threshold}""",
        params={"period": [14], "fastk": [5], "fastd": [3], "threshold": [75, 80]},
        direction="short",
        lookback=30,
        indicators=["stochrsi"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="SRI",
    ),
    # Stoch RSI K crosses above D
    PatternBlock(
        id="STOCHRSI_CROSS_UP",
        name="Stochastic RSI Cross Up",
        category="stoch_rsi",
        formula_template="""df['fastk'], df['fastd'] = ta.STOCHRSI(df['close'], timeperiod={period}, fastk_period={fastk}, fastd_period={fastd})
df['k_above_d'] = df['fastk'] > df['fastd']
df['k_was_below'] = df['fastk'].shift(1) <= df['fastd'].shift(1)
df['entry_signal'] = df['k_above_d'] & df['k_was_below']""",
        params={"period": [14], "fastk": [5], "fastd": [3]},
        direction="long",
        lookback=30,
        indicators=["stochrsi"],
        combinable_with=["volume", "threshold"],
        strategy_type="SRI",
    ),
    # Stoch RSI K crosses below D
    PatternBlock(
        id="STOCHRSI_CROSS_DOWN",
        name="Stochastic RSI Cross Down",
        category="stoch_rsi",
        formula_template="""df['fastk'], df['fastd'] = ta.STOCHRSI(df['close'], timeperiod={period}, fastk_period={fastk}, fastd_period={fastd})
df['k_below_d'] = df['fastk'] < df['fastd']
df['k_was_above'] = df['fastk'].shift(1) >= df['fastd'].shift(1)
df['entry_signal'] = df['k_below_d'] & df['k_was_above']""",
        params={"period": [14], "fastk": [5], "fastd": [3]},
        direction="short",
        lookback=30,
        indicators=["stochrsi"],
        combinable_with=["volume", "threshold"],
        strategy_type="SRI",
    ),
]


# =============================================================================
# VWMA (VOLUME WEIGHTED MOVING AVERAGE) BLOCKS
# =============================================================================

VWMA_BLOCKS = [
    # Price crosses above VWMA
    PatternBlock(
        id="VWMA_CROSS_UP",
        name="VWMA Cross Up",
        category="vwma",
        formula_template="""df['vwma'] = (df['close'] * df['volume']).rolling({period}).sum() / df['volume'].rolling({period}).sum()
df['above'] = df['close'] > df['vwma']
df['was_below'] = df['close'].shift(1) <= df['vwma'].shift(1)
df['entry_signal'] = df['above'] & df['was_below']""",
        params={"period": [10, 20, 50]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="VWM",
    ),
    # Price crosses below VWMA
    PatternBlock(
        id="VWMA_CROSS_DOWN",
        name="VWMA Cross Down",
        category="vwma",
        formula_template="""df['vwma'] = (df['close'] * df['volume']).rolling({period}).sum() / df['volume'].rolling({period}).sum()
df['below'] = df['close'] < df['vwma']
df['was_above'] = df['close'].shift(1) >= df['vwma'].shift(1)
df['entry_signal'] = df['below'] & df['was_above']""",
        params={"period": [10, 20, 50]},
        direction="short",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="VWM",
    ),
    # VWMA diverging from SMA (volume driving price)
    PatternBlock(
        id="VWMA_DIVERGE_UP",
        name="VWMA Above SMA",
        category="vwma",
        formula_template="""df['vwma'] = (df['close'] * df['volume']).rolling({period}).sum() / df['volume'].rolling({period}).sum()
df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['vwma_lead'] = (df['vwma'] - df['sma']) / df['sma'] * 100
df['entry_signal'] = df['vwma_lead'] > {threshold}""",
        params={"period": [20], "threshold": [0.1, 0.2, 0.5]},
        direction="long",
        lookback=40,
        indicators=["sma"],
        combinable_with=["volume", "threshold"],
        strategy_type="VWM",
    ),
]


# =============================================================================
# OBV (ON BALANCE VOLUME) BLOCKS
# =============================================================================

OBV_BLOCKS = [
    # OBV trending up
    PatternBlock(
        id="OBV_TREND_UP",
        name="OBV Trending Up",
        category="obv",
        formula_template="""df['obv'] = ta.OBV(df['close'], df['volume'])
df['obv_sma'] = df['obv'].rolling({period}).mean()
df['entry_signal'] = df['obv'] > df['obv_sma']""",
        params={"period": [10, 20]},
        direction="long",
        lookback=30,
        indicators=["obv"],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="OBV",
    ),
    # OBV trending down
    PatternBlock(
        id="OBV_TREND_DOWN",
        name="OBV Trending Down",
        category="obv",
        formula_template="""df['obv'] = ta.OBV(df['close'], df['volume'])
df['obv_sma'] = df['obv'].rolling({period}).mean()
df['entry_signal'] = df['obv'] < df['obv_sma']""",
        params={"period": [10, 20]},
        direction="short",
        lookback=30,
        indicators=["obv"],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="OBV",
    ),
    # OBV bullish divergence
    PatternBlock(
        id="OBV_BULL_DIV",
        name="OBV Bullish Divergence",
        category="obv",
        formula_template="""df['obv'] = ta.OBV(df['close'], df['volume'])
df['price_ll'] = df['close'] < df['close'].rolling({lookback}).min().shift(1)
df['obv_hl'] = df['obv'] > df['obv'].rolling({lookback}).min().shift(1)
df['entry_signal'] = df['price_ll'] & df['obv_hl']""",
        params={"lookback": [10, 20]},
        direction="long",
        lookback=30,
        indicators=["obv"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="OBV",
    ),
    # OBV bearish divergence
    PatternBlock(
        id="OBV_BEAR_DIV",
        name="OBV Bearish Divergence",
        category="obv",
        formula_template="""df['obv'] = ta.OBV(df['close'], df['volume'])
df['price_hh'] = df['close'] > df['close'].rolling({lookback}).max().shift(1)
df['obv_lh'] = df['obv'] < df['obv'].rolling({lookback}).max().shift(1)
df['entry_signal'] = df['price_hh'] & df['obv_lh']""",
        params={"lookback": [10, 20]},
        direction="short",
        lookback=30,
        indicators=["obv"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="OBV",
    ),
]


# =============================================================================
# ADOSC (CHAIKIN A/D OSCILLATOR) BLOCKS
# =============================================================================

ADOSC_BLOCKS = [
    # ADOSC crosses above zero
    PatternBlock(
        id="ADOSC_CROSS_UP",
        name="Chaikin A/D Oscillator Cross Up",
        category="adosc",
        formula_template="""df['adosc'] = ta.ADOSC(df['high'], df['low'], df['close'], df['volume'], fastperiod={fast}, slowperiod={slow})
df['above_zero'] = df['adosc'] > 0
df['was_below'] = df['adosc'].shift(1) <= 0
df['entry_signal'] = df['above_zero'] & df['was_below']""",
        params={"fast": [3], "slow": [10]},
        direction="long",
        lookback=20,
        indicators=["adosc"],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="ADO",
    ),
    # ADOSC crosses below zero
    PatternBlock(
        id="ADOSC_CROSS_DOWN",
        name="Chaikin A/D Oscillator Cross Down",
        category="adosc",
        formula_template="""df['adosc'] = ta.ADOSC(df['high'], df['low'], df['close'], df['volume'], fastperiod={fast}, slowperiod={slow})
df['below_zero'] = df['adosc'] < 0
df['was_above'] = df['adosc'].shift(1) >= 0
df['entry_signal'] = df['below_zero'] & df['was_above']""",
        params={"fast": [3], "slow": [10]},
        direction="short",
        lookback=20,
        indicators=["adosc"],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="ADO",
    ),
    # ADOSC rising
    PatternBlock(
        id="ADOSC_RISING",
        name="Chaikin A/D Oscillator Rising",
        category="adosc",
        formula_template="""df['adosc'] = ta.ADOSC(df['high'], df['low'], df['close'], df['volume'], fastperiod={fast}, slowperiod={slow})
df['adosc_rising'] = df['adosc'] > df['adosc'].shift(1)
df['consecutive'] = df['adosc_rising'].rolling({bars}).sum() >= {bars}
df['entry_signal'] = df['consecutive']""",
        params={"fast": [3], "slow": [10], "bars": [2, 3]},
        direction="long",
        lookback=20,
        indicators=["adosc"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="ADO",
    ),
    # ADOSC falling
    PatternBlock(
        id="ADOSC_FALLING",
        name="Chaikin A/D Oscillator Falling",
        category="adosc",
        formula_template="""df['adosc'] = ta.ADOSC(df['high'], df['low'], df['close'], df['volume'], fastperiod={fast}, slowperiod={slow})
df['adosc_falling'] = df['adosc'] < df['adosc'].shift(1)
df['consecutive'] = df['adosc_falling'].rolling({bars}).sum() >= {bars}
df['entry_signal'] = df['consecutive']""",
        params={"fast": [3], "slow": [10], "bars": [2, 3]},
        direction="short",
        lookback=20,
        indicators=["adosc"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="ADO",
    ),
]


# =============================================================================
# BOP (BALANCE OF POWER) BLOCKS
# =============================================================================

BOP_BLOCKS = [
    # BOP positive (bulls in control)
    PatternBlock(
        id="BOP_POSITIVE",
        name="Balance of Power Positive",
        category="bop",
        formula_template="""df['bop'] = ta.BOP(df['open'], df['high'], df['low'], df['close'])
df['bop_sma'] = df['bop'].rolling({period}).mean()
df['entry_signal'] = df['bop_sma'] > {threshold}""",
        params={"period": [5, 10], "threshold": [0.1, 0.2]},
        direction="long",
        lookback=20,
        indicators=["bop"],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="BOP",
    ),
    # BOP negative (bears in control)
    PatternBlock(
        id="BOP_NEGATIVE",
        name="Balance of Power Negative",
        category="bop",
        formula_template="""df['bop'] = ta.BOP(df['open'], df['high'], df['low'], df['close'])
df['bop_sma'] = df['bop'].rolling({period}).mean()
df['entry_signal'] = df['bop_sma'] < -{threshold}""",
        params={"period": [5, 10], "threshold": [0.1, 0.2]},
        direction="short",
        lookback=20,
        indicators=["bop"],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="BOP",
    ),
    # BOP reversal (crosses zero)
    PatternBlock(
        id="BOP_CROSS_UP",
        name="Balance of Power Cross Up",
        category="bop",
        formula_template="""df['bop'] = ta.BOP(df['open'], df['high'], df['low'], df['close'])
df['bop_sma'] = df['bop'].rolling({period}).mean()
df['above'] = df['bop_sma'] > 0
df['was_below'] = df['bop_sma'].shift(1) <= 0
df['entry_signal'] = df['above'] & df['was_below']""",
        params={"period": [5, 10]},
        direction="long",
        lookback=20,
        indicators=["bop"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="BOP",
    ),
]


# =============================================================================
# PLUS/MINUS DI BLOCKS
# =============================================================================

PLUS_MINUS_DI_BLOCKS = [
    # +DI crosses above -DI
    PatternBlock(
        id="DI_CROSS_BULL",
        name="DI+ Crosses Above DI-",
        category="plus_minus_di",
        formula_template="""df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['plus_above'] = df['plus_di'] > df['minus_di']
df['was_below'] = df['plus_di'].shift(1) <= df['minus_di'].shift(1)
df['entry_signal'] = df['plus_above'] & df['was_below']""",
        params={"period": [14]},
        direction="long",
        lookback=30,
        indicators=["plus_di", "minus_di"],
        combinable_with=["threshold", "confirmation", "adx_direction"],
        strategy_type="DMI",
    ),
    # -DI crosses above +DI
    PatternBlock(
        id="DI_CROSS_BEAR",
        name="DI- Crosses Above DI+",
        category="plus_minus_di",
        formula_template="""df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_above'] = df['minus_di'] > df['plus_di']
df['was_below'] = df['minus_di'].shift(1) <= df['plus_di'].shift(1)
df['entry_signal'] = df['minus_above'] & df['was_below']""",
        params={"period": [14]},
        direction="short",
        lookback=30,
        indicators=["plus_di", "minus_di"],
        combinable_with=["threshold", "confirmation", "adx_direction"],
        strategy_type="DMI",
    ),
    # DI spread widening (strong trend)
    PatternBlock(
        id="DI_SPREAD_WIDE_BULL",
        name="DI Spread Widening Bullish",
        category="plus_minus_di",
        formula_template="""df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['spread'] = df['plus_di'] - df['minus_di']
df['spread_expanding'] = df['spread'] > df['spread'].shift(1)
df['entry_signal'] = (df['spread'] > {threshold}) & df['spread_expanding']""",
        params={"period": [14], "threshold": [10, 15, 20]},
        direction="long",
        lookback=30,
        indicators=["plus_di", "minus_di"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="DMI",
    ),
    # DI spread widening bearish
    PatternBlock(
        id="DI_SPREAD_WIDE_BEAR",
        name="DI Spread Widening Bearish",
        category="plus_minus_di",
        formula_template="""df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['spread'] = df['minus_di'] - df['plus_di']
df['spread_expanding'] = df['spread'] > df['spread'].shift(1)
df['entry_signal'] = (df['spread'] > {threshold}) & df['spread_expanding']""",
        params={"period": [14], "threshold": [10, 15, 20]},
        direction="short",
        lookback=30,
        indicators=["plus_di", "minus_di"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="DMI",
    ),
]


# =============================================================================
# PERCENT RANK BLOCKS
# =============================================================================

PERCENT_RANK_BLOCKS = [
    # Price at low percentile (oversold)
    PatternBlock(
        id="PCTRANK_LOW",
        name="Price Percent Rank Low",
        category="percent_rank",
        formula_template="""df['pct_rank'] = df['close'].rolling({period}).apply(lambda x: (x.iloc[-1] > x[:-1]).sum() / len(x[:-1]) * 100, raw=False)
df['entry_signal'] = df['pct_rank'] < {threshold}""",
        params={"period": [50, 100], "threshold": [10, 20]},
        direction="long",
        lookback=110,
        indicators=[],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="PCT",
    ),
    # Price at high percentile (overbought)
    PatternBlock(
        id="PCTRANK_HIGH",
        name="Price Percent Rank High",
        category="percent_rank",
        formula_template="""df['pct_rank'] = df['close'].rolling({period}).apply(lambda x: (x.iloc[-1] > x[:-1]).sum() / len(x[:-1]) * 100, raw=False)
df['entry_signal'] = df['pct_rank'] > {threshold}""",
        params={"period": [50, 100], "threshold": [80, 90]},
        direction="short",
        lookback=110,
        indicators=[],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="PCT",
    ),
    # Percent rank mean reversion
    PatternBlock(
        id="PCTRANK_REVERT_UP",
        name="Percent Rank Mean Reversion Up",
        category="percent_rank",
        formula_template="""df['pct_rank'] = df['close'].rolling({period}).apply(lambda x: (x.iloc[-1] > x[:-1]).sum() / len(x[:-1]) * 100, raw=False)
df['was_low'] = df['pct_rank'].shift(1) < {low_thresh}
df['now_rising'] = df['pct_rank'] > df['pct_rank'].shift(1)
df['entry_signal'] = df['was_low'] & df['now_rising']""",
        params={"period": [50], "low_thresh": [15, 20]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="PCT",
    ),
]


# =============================================================================
# MEDIAN PRICE BLOCKS
# =============================================================================

MEDIAN_PRICE_BLOCKS = [
    # Price crosses above median price MA
    PatternBlock(
        id="MEDPRICE_CROSS_UP",
        name="Median Price Cross Up",
        category="median_price",
        formula_template="""df['medprice'] = ta.MEDPRICE(df['high'], df['low'])
df['medprice_ma'] = ta.SMA(df['medprice'], timeperiod={period})
df['above'] = df['close'] > df['medprice_ma']
df['was_below'] = df['close'].shift(1) <= df['medprice_ma'].shift(1)
df['entry_signal'] = df['above'] & df['was_below']""",
        params={"period": [10, 20]},
        direction="long",
        lookback=30,
        indicators=["medprice"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="MED",
    ),
    # Price crosses below median price MA
    PatternBlock(
        id="MEDPRICE_CROSS_DOWN",
        name="Median Price Cross Down",
        category="median_price",
        formula_template="""df['medprice'] = ta.MEDPRICE(df['high'], df['low'])
df['medprice_ma'] = ta.SMA(df['medprice'], timeperiod={period})
df['below'] = df['close'] < df['medprice_ma']
df['was_above'] = df['close'].shift(1) >= df['medprice_ma'].shift(1)
df['entry_signal'] = df['below'] & df['was_above']""",
        params={"period": [10, 20]},
        direction="short",
        lookback=30,
        indicators=["medprice"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="MED",
    ),
    # Price deviation from median price
    PatternBlock(
        id="MEDPRICE_DEVIATION",
        name="Median Price Deviation",
        category="median_price",
        formula_template="""df['medprice'] = ta.MEDPRICE(df['high'], df['low'])
df['deviation'] = (df['close'] - df['medprice']) / df['medprice'] * 100
df['entry_signal'] = df['deviation'] < -{threshold}""",
        params={"threshold": [1.0, 2.0]},
        direction="long",
        lookback=10,
        indicators=["medprice"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="MED",
    ),
]


# =============================================================================
# TYPICAL PRICE BLOCKS
# =============================================================================

TYPPRICE_BLOCKS = [
    # Typical price crosses above MA
    PatternBlock(
        id="TYPPRICE_CROSS_UP",
        name="Typical Price Cross Up",
        category="typprice",
        formula_template="""df['typprice'] = ta.TYPPRICE(df['high'], df['low'], df['close'])
df['typprice_ma'] = ta.SMA(df['typprice'], timeperiod={period})
df['above'] = df['typprice'] > df['typprice_ma']
df['was_below'] = df['typprice'].shift(1) <= df['typprice_ma'].shift(1)
df['entry_signal'] = df['above'] & df['was_below']""",
        params={"period": [10, 20]},
        direction="long",
        lookback=30,
        indicators=["typprice"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="TYP",
    ),
    # Typical price crosses below MA
    PatternBlock(
        id="TYPPRICE_CROSS_DOWN",
        name="Typical Price Cross Down",
        category="typprice",
        formula_template="""df['typprice'] = ta.TYPPRICE(df['high'], df['low'], df['close'])
df['typprice_ma'] = ta.SMA(df['typprice'], timeperiod={period})
df['below'] = df['typprice'] < df['typprice_ma']
df['was_above'] = df['typprice'].shift(1) >= df['typprice_ma'].shift(1)
df['entry_signal'] = df['below'] & df['was_above']""",
        params={"period": [10, 20]},
        direction="short",
        lookback=30,
        indicators=["typprice"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="TYP",
    ),
    # Typical price momentum
    PatternBlock(
        id="TYPPRICE_MOM",
        name="Typical Price Momentum",
        category="typprice",
        formula_template="""df['typprice'] = ta.TYPPRICE(df['high'], df['low'], df['close'])
df['typprice_mom'] = df['typprice'] / df['typprice'].shift({period}) - 1
df['entry_signal'] = df['typprice_mom'] > {threshold}""",
        params={"period": [5, 10], "threshold": [0.01, 0.02]},
        direction="long",
        lookback=20,
        indicators=["typprice"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="TYP",
    ),
]


# =============================================================================
# MOMENTUM DIFF BLOCKS
# =============================================================================

MOMENTUM_DIFF_BLOCKS = [
    # Fast momentum > slow momentum (acceleration)
    PatternBlock(
        id="MOM_DIFF_ACCEL_UP",
        name="Momentum Acceleration Up",
        category="momentum_diff",
        formula_template="""df['mom_fast'] = ta.MOM(df['close'], timeperiod={fast})
df['mom_slow'] = ta.MOM(df['close'], timeperiod={slow})
df['mom_diff'] = df['mom_fast'] - df['mom_slow']
df['entry_signal'] = df['mom_diff'] > 0""",
        params={"fast": [5, 10], "slow": [20, 30]},
        direction="long",
        lookback=40,
        indicators=["mom"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="MDI",
    ),
    # Fast momentum < slow momentum (deceleration)
    PatternBlock(
        id="MOM_DIFF_ACCEL_DOWN",
        name="Momentum Acceleration Down",
        category="momentum_diff",
        formula_template="""df['mom_fast'] = ta.MOM(df['close'], timeperiod={fast})
df['mom_slow'] = ta.MOM(df['close'], timeperiod={slow})
df['mom_diff'] = df['mom_fast'] - df['mom_slow']
df['entry_signal'] = df['mom_diff'] < 0""",
        params={"fast": [5, 10], "slow": [20, 30]},
        direction="short",
        lookback=40,
        indicators=["mom"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="MDI",
    ),
    # Momentum diff crosses zero up
    PatternBlock(
        id="MOM_DIFF_CROSS_UP",
        name="Momentum Diff Cross Up",
        category="momentum_diff",
        formula_template="""df['mom_fast'] = ta.MOM(df['close'], timeperiod={fast})
df['mom_slow'] = ta.MOM(df['close'], timeperiod={slow})
df['mom_diff'] = df['mom_fast'] - df['mom_slow']
df['above'] = df['mom_diff'] > 0
df['was_below'] = df['mom_diff'].shift(1) <= 0
df['entry_signal'] = df['above'] & df['was_below']""",
        params={"fast": [5], "slow": [20]},
        direction="long",
        lookback=30,
        indicators=["mom"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="MDI",
    ),
    # Momentum diff crosses zero down
    PatternBlock(
        id="MOM_DIFF_CROSS_DOWN",
        name="Momentum Diff Cross Down",
        category="momentum_diff",
        formula_template="""df['mom_fast'] = ta.MOM(df['close'], timeperiod={fast})
df['mom_slow'] = ta.MOM(df['close'], timeperiod={slow})
df['mom_diff'] = df['mom_fast'] - df['mom_slow']
df['below'] = df['mom_diff'] < 0
df['was_above'] = df['mom_diff'].shift(1) >= 0
df['entry_signal'] = df['below'] & df['was_above']""",
        params={"fast": [5], "slow": [20]},
        direction="short",
        lookback=30,
        indicators=["mom"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="MDI",
    ),
]


# =============================================================================
# PRICE OSCILLATOR (APO) BLOCKS
# =============================================================================

PRICE_OSC_BLOCKS = [
    # APO crosses above zero
    PatternBlock(
        id="APO_CROSS_UP",
        name="APO Cross Zero Up",
        category="price_osc",
        formula_template="""df['apo'] = ta.APO(df['close'], fastperiod={fast}, slowperiod={slow})
df['above'] = df['apo'] > 0
df['was_below'] = df['apo'].shift(1) <= 0
df['entry_signal'] = df['above'] & df['was_below']""",
        params={"fast": [12], "slow": [26]},
        direction="long",
        lookback=40,
        indicators=["apo"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="APO",
    ),
    # APO crosses below zero
    PatternBlock(
        id="APO_CROSS_DOWN",
        name="APO Cross Zero Down",
        category="price_osc",
        formula_template="""df['apo'] = ta.APO(df['close'], fastperiod={fast}, slowperiod={slow})
df['below'] = df['apo'] < 0
df['was_above'] = df['apo'].shift(1) >= 0
df['entry_signal'] = df['below'] & df['was_above']""",
        params={"fast": [12], "slow": [26]},
        direction="short",
        lookback=40,
        indicators=["apo"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="APO",
    ),
    # APO above threshold
    PatternBlock(
        id="APO_HIGH",
        name="APO High",
        category="price_osc",
        formula_template="""df['apo'] = ta.APO(df['close'], fastperiod={fast}, slowperiod={slow})
df['apo_pct'] = df['apo'] / df['close'] * 100
df['entry_signal'] = df['apo_pct'] > {threshold}""",
        params={"fast": [12], "slow": [26], "threshold": [1.0, 2.0]},
        direction="long",
        lookback=40,
        indicators=["apo"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="APO",
    ),
    # APO below threshold
    PatternBlock(
        id="APO_LOW",
        name="APO Low",
        category="price_osc",
        formula_template="""df['apo'] = ta.APO(df['close'], fastperiod={fast}, slowperiod={slow})
df['apo_pct'] = df['apo'] / df['close'] * 100
df['entry_signal'] = df['apo_pct'] < -{threshold}""",
        params={"fast": [12], "slow": [26], "threshold": [1.0, 2.0]},
        direction="short",
        lookback=40,
        indicators=["apo"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="APO",
    ),
]


# =============================================================================
# RANGE PERCENT BLOCKS
# =============================================================================

RANGE_PERCENT_BLOCKS = [
    # Price near bottom of range (oversold)
    PatternBlock(
        id="RANGE_PCT_LOW",
        name="Price at Range Low",
        category="range_percent",
        formula_template="""df['range_high'] = df['high'].rolling({period}).max()
df['range_low'] = df['low'].rolling({period}).min()
df['range_pct'] = (df['close'] - df['range_low']) / (df['range_high'] - df['range_low']) * 100
df['entry_signal'] = df['range_pct'] < {threshold}""",
        params={"period": [20, 50], "threshold": [10, 20]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="RNG",
    ),
    # Price near top of range (overbought)
    PatternBlock(
        id="RANGE_PCT_HIGH",
        name="Price at Range High",
        category="range_percent",
        formula_template="""df['range_high'] = df['high'].rolling({period}).max()
df['range_low'] = df['low'].rolling({period}).min()
df['range_pct'] = (df['close'] - df['range_low']) / (df['range_high'] - df['range_low']) * 100
df['entry_signal'] = df['range_pct'] > {threshold}""",
        params={"period": [20, 50], "threshold": [80, 90]},
        direction="short",
        lookback=60,
        indicators=[],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="RNG",
    ),
    # Price breaks out of range
    PatternBlock(
        id="RANGE_BREAKOUT_UP",
        name="Range Breakout Up",
        category="range_percent",
        formula_template="""df['range_high'] = df['high'].rolling({period}).max().shift(1)
df['entry_signal'] = df['close'] > df['range_high']""",
        params={"period": [20, 50]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="RNG",
    ),
]


# =============================================================================
# STDDEV (STANDARD DEVIATION) BLOCKS
# =============================================================================

STDDEV_BLOCKS = [
    # Volatility expansion (stddev above average)
    PatternBlock(
        id="STDDEV_HIGH",
        name="StdDev High Volatility",
        category="stddev",
        formula_template="""df['stddev'] = ta.STDDEV(df['close'], timeperiod={period})
df['stddev_avg'] = df['stddev'].rolling({avg_period}).mean()
df['entry_signal'] = df['stddev'] > df['stddev_avg'] * {mult}""",
        params={"period": [20], "avg_period": [50], "mult": [1.5, 2.0]},
        direction="bidi",
        lookback=60,
        indicators=["stddev"],
        combinable_with=["threshold", "momentum", "confirmation"],
        strategy_type="STD",
    ),
    # Volatility contraction (squeeze)
    PatternBlock(
        id="STDDEV_LOW",
        name="StdDev Low Volatility",
        category="stddev",
        formula_template="""df['stddev'] = ta.STDDEV(df['close'], timeperiod={period})
df['stddev_avg'] = df['stddev'].rolling({avg_period}).mean()
df['entry_signal'] = df['stddev'] < df['stddev_avg'] * {mult}""",
        params={"period": [20], "avg_period": [50], "mult": [0.5, 0.7]},
        direction="bidi",
        lookback=60,
        indicators=["stddev"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="STD",
    ),
    # Z-score extreme (price deviation)
    PatternBlock(
        id="ZSCORE_LOW",
        name="Z-Score Extreme Low",
        category="stddev",
        formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['stddev'] = ta.STDDEV(df['close'], timeperiod={period})
df['zscore'] = (df['close'] - df['sma']) / df['stddev']
df['entry_signal'] = df['zscore'] < -{threshold}""",
        params={"period": [20], "threshold": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=["sma", "stddev"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="STD",
    ),
]


# =============================================================================
# ROC MULTI-TIMEFRAME BLOCKS
# =============================================================================

ROC_MULTI_BLOCKS = [
    # Fast ROC > Slow ROC (acceleration)
    PatternBlock(
        id="ROC_MULTI_ACCEL_UP",
        name="ROC Multi Acceleration Up",
        category="roc_multi",
        formula_template="""df['roc_fast'] = ta.ROC(df['close'], timeperiod={fast})
df['roc_slow'] = ta.ROC(df['close'], timeperiod={slow})
df['entry_signal'] = (df['roc_fast'] > df['roc_slow']) & (df['roc_fast'] > 0)""",
        params={"fast": [5, 10], "slow": [20, 30]},
        direction="long",
        lookback=40,
        indicators=["roc"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="RCM",
    ),
    # Fast ROC < Slow ROC (deceleration)
    PatternBlock(
        id="ROC_MULTI_ACCEL_DOWN",
        name="ROC Multi Acceleration Down",
        category="roc_multi",
        formula_template="""df['roc_fast'] = ta.ROC(df['close'], timeperiod={fast})
df['roc_slow'] = ta.ROC(df['close'], timeperiod={slow})
df['entry_signal'] = (df['roc_fast'] < df['roc_slow']) & (df['roc_fast'] < 0)""",
        params={"fast": [5, 10], "slow": [20, 30]},
        direction="short",
        lookback=40,
        indicators=["roc"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="RCM",
    ),
    # Both ROCs positive and rising
    PatternBlock(
        id="ROC_MULTI_BOTH_UP",
        name="ROC Multi Both Rising",
        category="roc_multi",
        formula_template="""df['roc_fast'] = ta.ROC(df['close'], timeperiod={fast})
df['roc_slow'] = ta.ROC(df['close'], timeperiod={slow})
df['fast_rising'] = df['roc_fast'] > df['roc_fast'].shift(1)
df['slow_rising'] = df['roc_slow'] > df['roc_slow'].shift(1)
df['entry_signal'] = df['fast_rising'] & df['slow_rising'] & (df['roc_fast'] > 0)""",
        params={"fast": [5], "slow": [20]},
        direction="long",
        lookback=30,
        indicators=["roc"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="RCM",
    ),
    # ROC divergence (fast vs slow)
    PatternBlock(
        id="ROC_MULTI_DIVERGE",
        name="ROC Multi Divergence",
        category="roc_multi",
        formula_template="""df['roc_fast'] = ta.ROC(df['close'], timeperiod={fast})
df['roc_slow'] = ta.ROC(df['close'], timeperiod={slow})
df['fast_up'] = df['roc_fast'] > df['roc_fast'].shift(1)
df['slow_down'] = df['roc_slow'] < df['roc_slow'].shift(1)
df['entry_signal'] = df['fast_up'] & df['slow_down'] & (df['roc_fast'] > 0)""",
        params={"fast": [5], "slow": [20]},
        direction="long",
        lookback=30,
        indicators=["roc"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="RCM",
    ),
]


# =============================================================================
# BBANDS WIDTH BLOCKS
# =============================================================================

BBANDS_WIDTH_BLOCKS = [
    # BB width squeeze (low volatility)
    PatternBlock(
        id="BBWIDTH_SQUEEZE",
        name="Bollinger Band Squeeze",
        category="bbands_width",
        formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod={period})
df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid'] * 100
df['width_avg'] = df['bb_width'].rolling({avg_period}).mean()
df['entry_signal'] = df['bb_width'] < df['width_avg'] * {mult}""",
        params={"period": [20], "avg_period": [50], "mult": [0.5, 0.7]},
        direction="bidi",
        lookback=60,
        indicators=["bbands"],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="BBW",
    ),
    # BB width expansion
    PatternBlock(
        id="BBWIDTH_EXPAND",
        name="Bollinger Band Expansion",
        category="bbands_width",
        formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod={period})
df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid'] * 100
df['width_prev'] = df['bb_width'].shift(1)
df['expanding'] = df['bb_width'] > df['width_prev'] * {mult}
df['entry_signal'] = df['expanding']""",
        params={"period": [20], "mult": [1.2, 1.5]},
        direction="bidi",
        lookback=30,
        indicators=["bbands"],
        combinable_with=["threshold", "momentum"],
        strategy_type="BBW",
    ),
    # BB width percentile low
    PatternBlock(
        id="BBWIDTH_PERCENTILE_LOW",
        name="BB Width Percentile Low",
        category="bbands_width",
        formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod={period})
df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid'] * 100
df['width_min'] = df['bb_width'].rolling({lookback}).min()
df['width_max'] = df['bb_width'].rolling({lookback}).max()
df['width_pct'] = (df['bb_width'] - df['width_min']) / (df['width_max'] - df['width_min']) * 100
df['entry_signal'] = df['width_pct'] < {threshold}""",
        params={"period": [20], "lookback": [100], "threshold": [10, 20]},
        direction="bidi",
        lookback=120,
        indicators=["bbands"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="BBW",
    ),
    # BB width breakout (from squeeze)
    PatternBlock(
        id="BBWIDTH_BREAKOUT",
        name="BB Width Breakout",
        category="bbands_width",
        formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod={period})
df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid'] * 100
df['width_avg'] = df['bb_width'].rolling({avg_period}).mean()
df['was_squeeze'] = df['bb_width'].shift(1) < df['width_avg'].shift(1) * 0.7
df['now_expand'] = df['bb_width'] > df['width_avg']
df['entry_signal'] = df['was_squeeze'] & df['now_expand']""",
        params={"period": [20], "avg_period": [50]},
        direction="bidi",
        lookback=60,
        indicators=["bbands"],
        combinable_with=["threshold", "momentum"],
        strategy_type="BBW",
    ),
]


# =============================================================================
# MACD HISTOGRAM BLOCKS
# =============================================================================

MACD_HIST_BLOCKS = [
    # MACD histogram positive peak
    PatternBlock(
        id="MACD_HIST_PEAK",
        name="MACD Histogram Peak",
        category="macd_hist",
        formula_template="""df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod={signal})
df['hist_falling'] = df['hist'] < df['hist'].shift(1)
df['was_rising'] = df['hist'].shift(1) > df['hist'].shift(2)
df['entry_signal'] = df['hist_falling'] & df['was_rising'] & (df['hist'] > 0)""",
        params={"fast": [12], "slow": [26], "signal": [9]},
        direction="short",
        lookback=40,
        indicators=["macd"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="MCH",
    ),
    # MACD histogram trough
    PatternBlock(
        id="MACD_HIST_TROUGH",
        name="MACD Histogram Trough",
        category="macd_hist",
        formula_template="""df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod={signal})
df['hist_rising'] = df['hist'] > df['hist'].shift(1)
df['was_falling'] = df['hist'].shift(1) < df['hist'].shift(2)
df['entry_signal'] = df['hist_rising'] & df['was_falling'] & (df['hist'] < 0)""",
        params={"fast": [12], "slow": [26], "signal": [9]},
        direction="long",
        lookback=40,
        indicators=["macd"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="MCH",
    ),
    # MACD histogram cross zero up
    PatternBlock(
        id="MACD_HIST_CROSS_UP",
        name="MACD Histogram Cross Up",
        category="macd_hist",
        formula_template="""df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod={signal})
df['above'] = df['hist'] > 0
df['was_below'] = df['hist'].shift(1) <= 0
df['entry_signal'] = df['above'] & df['was_below']""",
        params={"fast": [12], "slow": [26], "signal": [9]},
        direction="long",
        lookback=40,
        indicators=["macd"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="MCH",
    ),
    # MACD histogram divergence
    PatternBlock(
        id="MACD_HIST_DIV_BULL",
        name="MACD Histogram Bullish Divergence",
        category="macd_hist",
        formula_template="""df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod={signal})
df['price_ll'] = df['close'] < df['close'].rolling({lookback}).min().shift(1)
df['hist_hl'] = df['hist'] > df['hist'].rolling({lookback}).min().shift(1)
df['entry_signal'] = df['price_ll'] & df['hist_hl']""",
        params={"fast": [12], "slow": [26], "signal": [9], "lookback": [10, 20]},
        direction="long",
        lookback=50,
        indicators=["macd"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="MCH",
    ),
]


# =============================================================================
# RSI SLOPE BLOCKS
# =============================================================================

RSI_SLOPE_BLOCKS = [
    # RSI accelerating up
    PatternBlock(
        id="RSI_SLOPE_UP",
        name="RSI Slope Up",
        category="rsi_slope",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['rsi_slope'] = df['rsi'] - df['rsi'].shift({slope_period})
df['entry_signal'] = df['rsi_slope'] > {threshold}""",
        params={"period": [14], "slope_period": [3, 5], "threshold": [5, 10]},
        direction="long",
        lookback=30,
        indicators=["rsi"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="RSL",
    ),
    # RSI accelerating down
    PatternBlock(
        id="RSI_SLOPE_DOWN",
        name="RSI Slope Down",
        category="rsi_slope",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['rsi_slope'] = df['rsi'] - df['rsi'].shift({slope_period})
df['entry_signal'] = df['rsi_slope'] < -{threshold}""",
        params={"period": [14], "slope_period": [3, 5], "threshold": [5, 10]},
        direction="short",
        lookback=30,
        indicators=["rsi"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="RSL",
    ),
    # RSI slope reversal (from falling to rising)
    PatternBlock(
        id="RSI_SLOPE_REVERSAL",
        name="RSI Slope Reversal Up",
        category="rsi_slope",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['rsi_slope'] = df['rsi'] - df['rsi'].shift(1)
df['now_rising'] = df['rsi_slope'] > 0
df['was_falling'] = df['rsi_slope'].shift(1) < 0
df['rsi_low'] = df['rsi'] < {rsi_thresh}
df['entry_signal'] = df['now_rising'] & df['was_falling'] & df['rsi_low']""",
        params={"period": [14], "rsi_thresh": [40, 50]},
        direction="long",
        lookback=30,
        indicators=["rsi"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="RSL",
    ),
]


# =============================================================================
# VOLUME PRICE BLOCKS
# =============================================================================

VOLUME_PRICE_BLOCKS = [
    # Up move with high volume (confirmation)
    PatternBlock(
        id="VOL_PRICE_UP_CONFIRM",
        name="Volume Price Up Confirm",
        category="volume_price",
        formula_template="""df['price_up'] = df['close'] > df['close'].shift(1)
df['vol_avg'] = df['volume'].rolling({period}).mean()
df['vol_high'] = df['volume'] > df['vol_avg'] * {mult}
df['entry_signal'] = df['price_up'] & df['vol_high']""",
        params={"period": [20], "mult": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="VPR",
    ),
    # Down move with high volume
    PatternBlock(
        id="VOL_PRICE_DOWN_CONFIRM",
        name="Volume Price Down Confirm",
        category="volume_price",
        formula_template="""df['price_down'] = df['close'] < df['close'].shift(1)
df['vol_avg'] = df['volume'].rolling({period}).mean()
df['vol_high'] = df['volume'] > df['vol_avg'] * {mult}
df['entry_signal'] = df['price_down'] & df['vol_high']""",
        params={"period": [20], "mult": [1.5, 2.0]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="VPR",
    ),
    # Volume price divergence (price up, volume down)
    PatternBlock(
        id="VOL_PRICE_DIV_BEAR",
        name="Volume Price Divergence Bearish",
        category="volume_price",
        formula_template="""df['price_up'] = df['close'] > df['close'].shift({period})
df['vol_down'] = df['volume'] < df['volume'].rolling({period}).mean()
df['entry_signal'] = df['price_up'] & df['vol_down']""",
        params={"period": [5, 10]},
        direction="short",
        lookback=20,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="VPR",
    ),
    # Volume price divergence (price down, volume down - exhaustion)
    PatternBlock(
        id="VOL_PRICE_DIV_BULL",
        name="Volume Price Divergence Bullish",
        category="volume_price",
        formula_template="""df['price_down'] = df['close'] < df['close'].shift({period})
df['vol_down'] = df['volume'] < df['volume'].rolling({period}).mean()
df['entry_signal'] = df['price_down'] & df['vol_down']""",
        params={"period": [5, 10]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="VPR",
    ),
]


# =============================================================================
# WCLPRICE (WEIGHTED CLOSE PRICE) BLOCKS
# =============================================================================

WCLPRICE_BLOCKS = [
    # WCL price crosses above MA
    PatternBlock(
        id="WCLPRICE_CROSS_UP",
        name="Weighted Close Cross Up",
        category="wclprice",
        formula_template="""df['wclprice'] = ta.WCLPRICE(df['high'], df['low'], df['close'])
df['wclprice_ma'] = ta.SMA(df['wclprice'], timeperiod={period})
df['above'] = df['wclprice'] > df['wclprice_ma']
df['was_below'] = df['wclprice'].shift(1) <= df['wclprice_ma'].shift(1)
df['entry_signal'] = df['above'] & df['was_below']""",
        params={"period": [10, 20]},
        direction="long",
        lookback=30,
        indicators=["wclprice"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="WCL",
    ),
    # WCL price crosses below MA
    PatternBlock(
        id="WCLPRICE_CROSS_DOWN",
        name="Weighted Close Cross Down",
        category="wclprice",
        formula_template="""df['wclprice'] = ta.WCLPRICE(df['high'], df['low'], df['close'])
df['wclprice_ma'] = ta.SMA(df['wclprice'], timeperiod={period})
df['below'] = df['wclprice'] < df['wclprice_ma']
df['was_above'] = df['wclprice'].shift(1) >= df['wclprice_ma'].shift(1)
df['entry_signal'] = df['below'] & df['was_above']""",
        params={"period": [10, 20]},
        direction="short",
        lookback=30,
        indicators=["wclprice"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="WCL",
    ),
    # WCL momentum
    PatternBlock(
        id="WCLPRICE_MOM",
        name="Weighted Close Momentum",
        category="wclprice",
        formula_template="""df['wclprice'] = ta.WCLPRICE(df['high'], df['low'], df['close'])
df['wcl_mom'] = df['wclprice'] / df['wclprice'].shift({period}) - 1
df['entry_signal'] = df['wcl_mom'] > {threshold}""",
        params={"period": [5, 10], "threshold": [0.01, 0.02]},
        direction="long",
        lookback=20,
        indicators=["wclprice"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="WCL",
    ),
]


# =============================================================================
# AVGPRICE BLOCKS
# =============================================================================

AVGPRICE_BLOCKS = [
    # Average price cross above MA
    PatternBlock(
        id="AVGPRICE_CROSS_UP",
        name="Average Price Cross Up",
        category="avgprice",
        formula_template="""df['avgprice'] = ta.AVGPRICE(df['open'], df['high'], df['low'], df['close'])
df['avgprice_ma'] = ta.SMA(df['avgprice'], timeperiod={period})
df['above'] = df['avgprice'] > df['avgprice_ma']
df['was_below'] = df['avgprice'].shift(1) <= df['avgprice_ma'].shift(1)
df['entry_signal'] = df['above'] & df['was_below']""",
        params={"period": [10, 20]},
        direction="long",
        lookback=30,
        indicators=["avgprice"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="AVG",
    ),
    # Average price cross below MA
    PatternBlock(
        id="AVGPRICE_CROSS_DOWN",
        name="Average Price Cross Down",
        category="avgprice",
        formula_template="""df['avgprice'] = ta.AVGPRICE(df['open'], df['high'], df['low'], df['close'])
df['avgprice_ma'] = ta.SMA(df['avgprice'], timeperiod={period})
df['below'] = df['avgprice'] < df['avgprice_ma']
df['was_above'] = df['avgprice'].shift(1) >= df['avgprice_ma'].shift(1)
df['entry_signal'] = df['below'] & df['was_above']""",
        params={"period": [10, 20]},
        direction="short",
        lookback=30,
        indicators=["avgprice"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="AVG",
    ),
    # Average price trend
    PatternBlock(
        id="AVGPRICE_TREND_UP",
        name="Average Price Trend Up",
        category="avgprice",
        formula_template="""df['avgprice'] = ta.AVGPRICE(df['open'], df['high'], df['low'], df['close'])
df['avgprice_rising'] = df['avgprice'] > df['avgprice'].shift(1)
df['consecutive'] = df['avgprice_rising'].rolling({bars}).sum() >= {bars}
df['entry_signal'] = df['consecutive']""",
        params={"bars": [3, 5]},
        direction="long",
        lookback=20,
        indicators=["avgprice"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="AVG",
    ),
]


# =============================================================================
# HIGH LOW DIFF BLOCKS
# =============================================================================

HIGH_LOW_DIFF_BLOCKS = [
    # Wide range bar (high volatility)
    PatternBlock(
        id="HL_WIDE_RANGE",
        name="Wide Range Bar",
        category="high_low_diff",
        formula_template="""df['hl_range'] = (df['high'] - df['low']) / df['close'] * 100
df['range_avg'] = df['hl_range'].rolling({period}).mean()
df['entry_signal'] = df['hl_range'] > df['range_avg'] * {mult}""",
        params={"period": [20], "mult": [1.5, 2.0]},
        direction="bidi",
        lookback=30,
        indicators=[],
        combinable_with=["threshold", "momentum", "volume"],
        strategy_type="HLD",
    ),
    # Narrow range bar (low volatility)
    PatternBlock(
        id="HL_NARROW_RANGE",
        name="Narrow Range Bar",
        category="high_low_diff",
        formula_template="""df['hl_range'] = (df['high'] - df['low']) / df['close'] * 100
df['range_avg'] = df['hl_range'].rolling({period}).mean()
df['entry_signal'] = df['hl_range'] < df['range_avg'] * {mult}""",
        params={"period": [20], "mult": [0.5, 0.7]},
        direction="bidi",
        lookback=30,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="HLD",
    ),
    # Range expansion (breakout signal)
    PatternBlock(
        id="HL_RANGE_EXPAND",
        name="Range Expansion",
        category="high_low_diff",
        formula_template="""df['hl_range'] = df['high'] - df['low']
df['prev_range'] = df['hl_range'].shift(1)
df['range_expand'] = df['hl_range'] > df['prev_range'] * {mult}
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['range_expand'] & df['bullish']""",
        params={"mult": [1.5, 2.0]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="HLD",
    ),
]


# =============================================================================
# CLOSE POSITION BLOCKS
# =============================================================================

CLOSE_POSITION_BLOCKS = [
    # Close near high of bar (bullish)
    PatternBlock(
        id="CLOSE_NEAR_HIGH",
        name="Close Near High",
        category="close_position",
        formula_template="""df['hl_range'] = df['high'] - df['low']
df['close_pos'] = (df['close'] - df['low']) / df['hl_range']
df['entry_signal'] = df['close_pos'] > {threshold}""",
        params={"threshold": [0.8, 0.9]},
        direction="long",
        lookback=5,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="CLP",
    ),
    # Close near low of bar (bearish)
    PatternBlock(
        id="CLOSE_NEAR_LOW",
        name="Close Near Low",
        category="close_position",
        formula_template="""df['hl_range'] = df['high'] - df['low']
df['close_pos'] = (df['close'] - df['low']) / df['hl_range']
df['entry_signal'] = df['close_pos'] < {threshold}""",
        params={"threshold": [0.1, 0.2]},
        direction="short",
        lookback=5,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="CLP",
    ),
    # Close near middle (indecision, potential reversal)
    PatternBlock(
        id="CLOSE_MIDDLE",
        name="Close Near Middle",
        category="close_position",
        formula_template="""df['hl_range'] = df['high'] - df['low']
df['close_pos'] = (df['close'] - df['low']) / df['hl_range']
df['near_middle'] = (df['close_pos'] > 0.4) & (df['close_pos'] < 0.6)
df['prev_trend_down'] = df['close'].shift(1) < df['close'].shift({lookback})
df['entry_signal'] = df['near_middle'] & df['prev_trend_down']""",
        params={"lookback": [5, 10]},
        direction="long",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="CLP",
    ),
]


# =============================================================================
# SWING POINTS BLOCKS
# =============================================================================

SWING_POINTS_BLOCKS = [
    # Breakout above swing high
    PatternBlock(
        id="SWING_HIGH_BREAK",
        name="Swing High Breakout",
        category="swing_points",
        formula_template="""df['swing_high'] = df['high'].rolling({period}).max().shift(1)
df['entry_signal'] = df['high'] > df['swing_high']""",
        params={"period": [10, 20, 50]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="SWG",
    ),
    # Breakout below swing low
    PatternBlock(
        id="SWING_LOW_BREAK",
        name="Swing Low Breakout",
        category="swing_points",
        formula_template="""df['swing_low'] = df['low'].rolling({period}).min().shift(1)
df['entry_signal'] = df['low'] < df['swing_low']""",
        params={"period": [10, 20, 50]},
        direction="short",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="SWG",
    ),
    # Retest of swing high (support becomes resistance)
    PatternBlock(
        id="SWING_HIGH_RETEST",
        name="Swing High Retest",
        category="swing_points",
        formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
df['near_swing'] = abs(df['high'] - df['swing_high'].shift(1)) / df['close'] < 0.01
df['rejected'] = df['close'] < df['open']
df['entry_signal'] = df['near_swing'] & df['rejected']""",
        params={"period": [20]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="SWG",
    ),
    # Retest of swing low (resistance becomes support)
    PatternBlock(
        id="SWING_LOW_RETEST",
        name="Swing Low Retest",
        category="swing_points",
        formula_template="""df['swing_low'] = df['low'].rolling({period}).min()
df['near_swing'] = abs(df['low'] - df['swing_low'].shift(1)) / df['close'] < 0.01
df['bounced'] = df['close'] > df['open']
df['entry_signal'] = df['near_swing'] & df['bounced']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="SWG",
    ),
]


# =============================================================================
# MULTI BAR PATTERN BLOCKS
# =============================================================================

MULTI_BAR_BLOCKS = [
    # Two-bar reversal bullish (down bar followed by up bar)
    PatternBlock(
        id="TWO_BAR_REVERSAL_BULL",
        name="Two Bar Reversal Bullish",
        category="multi_bar",
        formula_template="""df['prev_down'] = df['close'].shift(1) < df['open'].shift(1)
df['curr_up'] = df['close'] > df['open']
df['higher_close'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['prev_down'] & df['curr_up'] & df['higher_close']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="MBR",
    ),
    # Two-bar reversal bearish
    PatternBlock(
        id="TWO_BAR_REVERSAL_BEAR",
        name="Two Bar Reversal Bearish",
        category="multi_bar",
        formula_template="""df['prev_up'] = df['close'].shift(1) > df['open'].shift(1)
df['curr_down'] = df['close'] < df['open']
df['lower_close'] = df['close'] < df['close'].shift(1)
df['entry_signal'] = df['prev_up'] & df['curr_down'] & df['lower_close']""",
        params={},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="MBR",
    ),
    # Three bar continuation bullish
    PatternBlock(
        id="THREE_BAR_CONT_BULL",
        name="Three Bar Continuation Bullish",
        category="multi_bar",
        formula_template="""df['bar1_up'] = df['close'].shift(2) > df['open'].shift(2)
df['bar2_up'] = df['close'].shift(1) > df['open'].shift(1)
df['bar3_up'] = df['close'] > df['open']
df['entry_signal'] = df['bar1_up'] & df['bar2_up'] & df['bar3_up']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="MBR",
    ),
    # Inside bar breakout
    PatternBlock(
        id="INSIDE_BAR_BREAK_UP",
        name="Inside Bar Breakout Up",
        category="multi_bar",
        formula_template="""df['inside_bar'] = (df['high'].shift(1) < df['high'].shift(2)) & (df['low'].shift(1) > df['low'].shift(2))
df['break_up'] = df['high'] > df['high'].shift(1)
df['entry_signal'] = df['inside_bar'] & df['break_up']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="MBR",
    ),
]


# =============================================================================
# PRICE MA DISTANCE BLOCKS
# =============================================================================

PRICE_MA_DISTANCE_BLOCKS = [
    # Price far above MA (overextended)
    PatternBlock(
        id="PRICE_MA_OVER_EXT_UP",
        name="Price Overextended Above MA",
        category="price_ma_distance",
        formula_template="""df['ma'] = ta.SMA(df['close'], timeperiod={period})
df['distance'] = (df['close'] - df['ma']) / df['ma'] * 100
df['entry_signal'] = df['distance'] > {threshold}""",
        params={"period": [20, 50], "threshold": [3, 5, 7]},
        direction="short",
        lookback=60,
        indicators=["sma"],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="PMD",
    ),
    # Price far below MA (overextended)
    PatternBlock(
        id="PRICE_MA_OVER_EXT_DOWN",
        name="Price Overextended Below MA",
        category="price_ma_distance",
        formula_template="""df['ma'] = ta.SMA(df['close'], timeperiod={period})
df['distance'] = (df['close'] - df['ma']) / df['ma'] * 100
df['entry_signal'] = df['distance'] < -{threshold}""",
        params={"period": [20, 50], "threshold": [3, 5, 7]},
        direction="long",
        lookback=60,
        indicators=["sma"],
        combinable_with=["threshold", "confirmation", "momentum"],
        strategy_type="PMD",
    ),
    # Price returning to MA from above
    PatternBlock(
        id="PRICE_MA_RETURN_DOWN",
        name="Price Returning to MA Down",
        category="price_ma_distance",
        formula_template="""df['ma'] = ta.SMA(df['close'], timeperiod={period})
df['distance'] = (df['close'] - df['ma']) / df['ma'] * 100
df['was_extended'] = df['distance'].shift(1) > {threshold}
df['returning'] = df['distance'] < df['distance'].shift(1)
df['entry_signal'] = df['was_extended'] & df['returning']""",
        params={"period": [20], "threshold": [3, 5]},
        direction="short",
        lookback=40,
        indicators=["sma"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="PMD",
    ),
    # Price returning to MA from below
    PatternBlock(
        id="PRICE_MA_RETURN_UP",
        name="Price Returning to MA Up",
        category="price_ma_distance",
        formula_template="""df['ma'] = ta.SMA(df['close'], timeperiod={period})
df['distance'] = (df['close'] - df['ma']) / df['ma'] * 100
df['was_extended'] = df['distance'].shift(1) < -{threshold}
df['returning'] = df['distance'] > df['distance'].shift(1)
df['entry_signal'] = df['was_extended'] & df['returning']""",
        params={"period": [20], "threshold": [3, 5]},
        direction="long",
        lookback=40,
        indicators=["sma"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="PMD",
    ),
]


# =============================================================================
# ATR BREAKOUT BLOCKS
# =============================================================================

ATR_BREAKOUT_BLOCKS = [
    # Price breaks above previous close + ATR
    PatternBlock(
        id="ATR_BREAK_UP",
        name="ATR Breakout Up",
        category="atr_breakout",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['upper_level'] = df['close'].shift(1) + df['atr'].shift(1) * {mult}
df['entry_signal'] = df['close'] > df['upper_level']""",
        params={"period": [14], "mult": [1.0, 1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=["atr"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ATB",
    ),
    # Price breaks below previous close - ATR
    PatternBlock(
        id="ATR_BREAK_DOWN",
        name="ATR Breakout Down",
        category="atr_breakout",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['lower_level'] = df['close'].shift(1) - df['atr'].shift(1) * {mult}
df['entry_signal'] = df['close'] < df['lower_level']""",
        params={"period": [14], "mult": [1.0, 1.5, 2.0]},
        direction="short",
        lookback=30,
        indicators=["atr"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ATB",
    ),
    # ATR channel breakout (from MA)
    PatternBlock(
        id="ATR_CHANNEL_BREAK_UP",
        name="ATR Channel Breakout Up",
        category="atr_breakout",
        formula_template="""df['ma'] = ta.SMA(df['close'], timeperiod={ma_period})
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={atr_period})
df['upper_band'] = df['ma'] + df['atr'] * {mult}
df['entry_signal'] = df['close'] > df['upper_band']""",
        params={"ma_period": [20], "atr_period": [14], "mult": [2.0, 2.5]},
        direction="long",
        lookback=40,
        indicators=["sma", "atr"],
        combinable_with=["volume", "confirmation"],
        strategy_type="ATB",
    ),
]


# =============================================================================
# DUAL MOMENTUM BLOCKS
# =============================================================================

DUAL_MOMENTUM_BLOCKS = [
    # RSI + MOM both bullish
    PatternBlock(
        id="RSI_MOM_BULL",
        name="RSI and MOM Both Bullish",
        category="dual_momentum",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={rsi_period})
df['mom'] = ta.MOM(df['close'], timeperiod={mom_period})
df['rsi_rising'] = df['rsi'] > df['rsi'].shift(1)
df['mom_positive'] = df['mom'] > 0
df['entry_signal'] = df['rsi_rising'] & df['mom_positive']""",
        params={"rsi_period": [14], "mom_period": [10]},
        direction="long",
        lookback=30,
        indicators=["rsi", "mom"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="DUM",
    ),
    # RSI + MOM both bearish
    PatternBlock(
        id="RSI_MOM_BEAR",
        name="RSI and MOM Both Bearish",
        category="dual_momentum",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={rsi_period})
df['mom'] = ta.MOM(df['close'], timeperiod={mom_period})
df['rsi_falling'] = df['rsi'] < df['rsi'].shift(1)
df['mom_negative'] = df['mom'] < 0
df['entry_signal'] = df['rsi_falling'] & df['mom_negative']""",
        params={"rsi_period": [14], "mom_period": [10]},
        direction="short",
        lookback=30,
        indicators=["rsi", "mom"],
        combinable_with=["threshold", "confirmation", "volume"],
        strategy_type="DUM",
    ),
    # CCI + ROC bullish
    PatternBlock(
        id="CCI_ROC_BULL",
        name="CCI and ROC Both Bullish",
        category="dual_momentum",
        formula_template="""df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod={cci_period})
df['roc'] = ta.ROC(df['close'], timeperiod={roc_period})
df['cci_rising'] = df['cci'] > df['cci'].shift(1)
df['roc_positive'] = df['roc'] > 0
df['entry_signal'] = df['cci_rising'] & df['roc_positive']""",
        params={"cci_period": [20], "roc_period": [10]},
        direction="long",
        lookback=30,
        indicators=["cci", "roc"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="DUM",
    ),
    # Stoch + RSI oversold
    PatternBlock(
        id="STOCH_RSI_OVERSOLD",
        name="Stoch and RSI Both Oversold",
        category="dual_momentum",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'])
df['rsi_oversold'] = df['rsi'] < {rsi_thresh}
df['stoch_oversold'] = df['slowk'] < {stoch_thresh}
df['entry_signal'] = df['rsi_oversold'] & df['stoch_oversold']""",
        params={"rsi_thresh": [30, 35], "stoch_thresh": [20, 25]},
        direction="long",
        lookback=30,
        indicators=["rsi", "stoch"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="DUM",
    ),
]


# =============================================================================
# CANDLE SIZE BLOCKS
# =============================================================================

CANDLE_SIZE_BLOCKS = [
    # Large bullish candle (marubozu-like)
    PatternBlock(
        id="LARGE_BULL_CANDLE",
        name="Large Bullish Candle",
        category="candle_size",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['range'] = df['high'] - df['low']
df['body_ratio'] = df['body'] / df['range']
df['avg_range'] = df['range'].rolling({period}).mean()
df['large'] = df['range'] > df['avg_range'] * {mult}
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['large'] & df['bullish'] & (df['body_ratio'] > 0.7)""",
        params={"period": [20], "mult": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CSZ",
    ),
    # Large bearish candle
    PatternBlock(
        id="LARGE_BEAR_CANDLE",
        name="Large Bearish Candle",
        category="candle_size",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['range'] = df['high'] - df['low']
df['body_ratio'] = df['body'] / df['range']
df['avg_range'] = df['range'].rolling({period}).mean()
df['large'] = df['range'] > df['avg_range'] * {mult}
df['bearish'] = df['close'] < df['open']
df['entry_signal'] = df['large'] & df['bearish'] & (df['body_ratio'] > 0.7)""",
        params={"period": [20], "mult": [1.5, 2.0]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CSZ",
    ),
    # Doji (small body)
    PatternBlock(
        id="DOJI_PATTERN",
        name="Doji Pattern",
        category="candle_size",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['range'] = df['high'] - df['low']
df['body_ratio'] = df['body'] / df['range']
df['is_doji'] = df['body_ratio'] < {threshold}
df['prev_trend_down'] = df['close'].shift(1) < df['close'].shift(5)
df['entry_signal'] = df['is_doji'] & df['prev_trend_down']""",
        params={"threshold": [0.1, 0.15]},
        direction="long",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="CSZ",
    ),
]


# =============================================================================
# TREND PERSISTENCE BLOCKS
# =============================================================================

TREND_PERSISTENCE_BLOCKS = [
    # N consecutive up closes
    PatternBlock(
        id="CONSEC_UP_CLOSES",
        name="Consecutive Up Closes",
        category="trend_persistence",
        formula_template="""df['up_close'] = df['close'] > df['close'].shift(1)
df['consec_up'] = df['up_close'].rolling({bars}).sum() >= {bars}
df['entry_signal'] = df['consec_up']""",
        params={"bars": [3, 4, 5]},
        direction="long",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="TRP",
    ),
    # N consecutive down closes
    PatternBlock(
        id="CONSEC_DOWN_CLOSES",
        name="Consecutive Down Closes",
        category="trend_persistence",
        formula_template="""df['down_close'] = df['close'] < df['close'].shift(1)
df['consec_down'] = df['down_close'].rolling({bars}).sum() >= {bars}
df['entry_signal'] = df['consec_down']""",
        params={"bars": [3, 4, 5]},
        direction="short",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="TRP",
    ),
    # Trend exhaustion (many consecutive bars then reversal)
    PatternBlock(
        id="TREND_EXHAUSTION_BULL",
        name="Trend Exhaustion Bullish",
        category="trend_persistence",
        formula_template="""df['down_close'] = df['close'] < df['close'].shift(1)
df['consec_down'] = df['down_close'].rolling({bars}).sum() >= {bars}
df['reversal'] = df['close'] > df['open']
df['entry_signal'] = df['consec_down'].shift(1) & df['reversal']""",
        params={"bars": [4, 5]},
        direction="long",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="TRP",
    ),
]


# =============================================================================
# PRICE VELOCITY BLOCKS
# =============================================================================

PRICE_VELOCITY_BLOCKS = [
    # Price velocity increasing (acceleration)
    PatternBlock(
        id="PRICE_ACCEL_UP",
        name="Price Acceleration Up",
        category="price_velocity",
        formula_template="""df['velocity'] = df['close'] - df['close'].shift({period})
df['accel'] = df['velocity'] - df['velocity'].shift(1)
df['entry_signal'] = (df['velocity'] > 0) & (df['accel'] > 0)""",
        params={"period": [5, 10]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="PVL",
    ),
    # Price velocity decreasing (deceleration)
    PatternBlock(
        id="PRICE_ACCEL_DOWN",
        name="Price Acceleration Down",
        category="price_velocity",
        formula_template="""df['velocity'] = df['close'] - df['close'].shift({period})
df['accel'] = df['velocity'] - df['velocity'].shift(1)
df['entry_signal'] = (df['velocity'] < 0) & (df['accel'] < 0)""",
        params={"period": [5, 10]},
        direction="short",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="PVL",
    ),
    # Velocity reversal
    PatternBlock(
        id="VELOCITY_REVERSAL_UP",
        name="Velocity Reversal Up",
        category="price_velocity",
        formula_template="""df['velocity'] = df['close'] - df['close'].shift({period})
df['vel_positive'] = df['velocity'] > 0
df['vel_was_negative'] = df['velocity'].shift(1) < 0
df['entry_signal'] = df['vel_positive'] & df['vel_was_negative']""",
        params={"period": [5, 10]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PVL",
    ),
]


# =============================================================================
# VOLUME TREND BLOCKS
# =============================================================================

VOLUME_TREND_BLOCKS = [
    # Volume increasing trend
    PatternBlock(
        id="VOL_TREND_UP",
        name="Volume Trend Up",
        category="volume_trend",
        formula_template="""df['vol_ma_short'] = df['volume'].rolling({short}).mean()
df['vol_ma_long'] = df['volume'].rolling({long}).mean()
df['vol_rising'] = df['vol_ma_short'] > df['vol_ma_long']
df['price_up'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['vol_rising'] & df['price_up']""",
        params={"short": [5], "long": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["threshold", "momentum", "confirmation"],
        strategy_type="VTR",
    ),
    # Volume decreasing (exhaustion)
    PatternBlock(
        id="VOL_TREND_DOWN",
        name="Volume Trend Down",
        category="volume_trend",
        formula_template="""df['vol_ma_short'] = df['volume'].rolling({short}).mean()
df['vol_ma_long'] = df['volume'].rolling({long}).mean()
df['vol_falling'] = df['vol_ma_short'] < df['vol_ma_long'] * {mult}
df['entry_signal'] = df['vol_falling']""",
        params={"short": [5], "long": [20], "mult": [0.7, 0.8]},
        direction="bidi",
        lookback=30,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="VTR",
    ),
    # Volume spike
    PatternBlock(
        id="VOL_SPIKE",
        name="Volume Spike",
        category="volume_trend",
        formula_template="""df['vol_avg'] = df['volume'].rolling({period}).mean()
df['vol_spike'] = df['volume'] > df['vol_avg'] * {mult}
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['vol_spike'] & df['bullish']""",
        params={"period": [20], "mult": [2.0, 2.5, 3.0]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["threshold", "momentum"],
        strategy_type="VTR",
    ),
]


# =============================================================================
# SUPPORT RESISTANCE BLOCKS
# =============================================================================

SUPPORT_RESISTANCE_BLOCKS = [
    # Price bounces off support
    PatternBlock(
        id="SUPPORT_BOUNCE",
        name="Support Bounce",
        category="support_resistance",
        formula_template="""df['support'] = df['low'].rolling({period}).min()
df['near_support'] = (df['low'] - df['support']) / df['close'] < {tolerance}
df['bounce'] = df['close'] > df['open']
df['entry_signal'] = df['near_support'] & df['bounce']""",
        params={"period": [20, 50], "tolerance": [0.005, 0.01]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="SNR",
    ),
    # Price rejected at resistance
    PatternBlock(
        id="RESISTANCE_REJECT",
        name="Resistance Rejection",
        category="support_resistance",
        formula_template="""df['resistance'] = df['high'].rolling({period}).max()
df['near_resistance'] = (df['resistance'] - df['high']) / df['close'] < {tolerance}
df['reject'] = df['close'] < df['open']
df['entry_signal'] = df['near_resistance'] & df['reject']""",
        params={"period": [20, 50], "tolerance": [0.005, 0.01]},
        direction="short",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="SNR",
    ),
    # Support break (becomes resistance)
    PatternBlock(
        id="SUPPORT_BREAK",
        name="Support Break",
        category="support_resistance",
        formula_template="""df['support'] = df['low'].rolling({period}).min().shift(1)
df['break_down'] = df['close'] < df['support']
df['entry_signal'] = df['break_down']""",
        params={"period": [20, 50]},
        direction="short",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="SNR",
    ),
]


# =============================================================================
# OPEN CLOSE RELATION BLOCKS
# =============================================================================

OPEN_CLOSE_REL_BLOCKS = [
    # Gap up continuation (open > prev close, continues up)
    PatternBlock(
        id="GAP_UP_CONTINUE",
        name="Gap Up Continuation",
        category="open_close_rel",
        formula_template="""df['gap_up'] = df['open'] > df['close'].shift(1) * (1 + {gap_pct})
df['continues_up'] = df['close'] > df['open']
df['entry_signal'] = df['gap_up'] & df['continues_up']""",
        params={"gap_pct": [0.005, 0.01]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="OCR",
    ),
    # Gap down continuation
    PatternBlock(
        id="GAP_DOWN_CONTINUE",
        name="Gap Down Continuation",
        category="open_close_rel",
        formula_template="""df['gap_down'] = df['open'] < df['close'].shift(1) * (1 - {gap_pct})
df['continues_down'] = df['close'] < df['open']
df['entry_signal'] = df['gap_down'] & df['continues_down']""",
        params={"gap_pct": [0.005, 0.01]},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="OCR",
    ),
    # Gap fill reversal (gap up then fills)
    PatternBlock(
        id="GAP_UP_FILL",
        name="Gap Up Fill Reversal",
        category="open_close_rel",
        formula_template="""df['gap_up'] = df['open'] > df['close'].shift(1) * (1 + {gap_pct})
df['fills_gap'] = df['low'] <= df['close'].shift(1)
df['entry_signal'] = df['gap_up'] & df['fills_gap']""",
        params={"gap_pct": [0.005, 0.01]},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="OCR",
    ),
]


# =============================================================================
# BODY WICK RATIO BLOCKS
# =============================================================================

BODY_WICK_RATIO_BLOCKS = [
    # Long upper wick (selling pressure)
    PatternBlock(
        id="LONG_UPPER_WICK",
        name="Long Upper Wick",
        category="body_wick_ratio",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['upper_wick'] = df['high'] - df[['close', 'open']].max(axis=1)
df['range'] = df['high'] - df['low']
df['upper_ratio'] = df['upper_wick'] / df['range']
df['entry_signal'] = df['upper_ratio'] > {threshold}""",
        params={"threshold": [0.5, 0.6, 0.7]},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="BWR",
    ),
    # Long lower wick (buying pressure)
    PatternBlock(
        id="LONG_LOWER_WICK",
        name="Long Lower Wick",
        category="body_wick_ratio",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['lower_wick'] = df[['close', 'open']].min(axis=1) - df['low']
df['range'] = df['high'] - df['low']
df['lower_ratio'] = df['lower_wick'] / df['range']
df['entry_signal'] = df['lower_ratio'] > {threshold}""",
        params={"threshold": [0.5, 0.6, 0.7]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="BWR",
    ),
    # Small body large wicks (indecision)
    PatternBlock(
        id="SMALL_BODY_LARGE_WICKS",
        name="Small Body Large Wicks",
        category="body_wick_ratio",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['range'] = df['high'] - df['low']
df['body_ratio'] = df['body'] / df['range']
df['small_body'] = df['body_ratio'] < {body_thresh}
df['prev_down'] = df['close'].shift(1) < df['close'].shift(3)
df['entry_signal'] = df['small_body'] & df['prev_down']""",
        params={"body_thresh": [0.2, 0.3]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="BWR",
    ),
]


# =============================================================================
# HIGHER LOWS / LOWER HIGHS BLOCKS
# =============================================================================

HIGHER_LOWS_BLOCKS = [
    # Higher lows pattern (uptrend structure)
    PatternBlock(
        id="HIGHER_LOWS",
        name="Higher Lows Pattern",
        category="higher_lows",
        formula_template="""df['hl1'] = df['low'] > df['low'].shift(1)
df['hl2'] = df['low'].shift(1) > df['low'].shift(2)
df['entry_signal'] = df['hl1'] & df['hl2']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="HLS",
    ),
    # Lower highs pattern (downtrend structure)
    PatternBlock(
        id="LOWER_HIGHS",
        name="Lower Highs Pattern",
        category="higher_lows",
        formula_template="""df['lh1'] = df['high'] < df['high'].shift(1)
df['lh2'] = df['high'].shift(1) < df['high'].shift(2)
df['entry_signal'] = df['lh1'] & df['lh2']""",
        params={},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="HLS",
    ),
    # Higher highs and higher lows (strong uptrend)
    PatternBlock(
        id="HH_HL",
        name="Higher Highs and Higher Lows",
        category="higher_lows",
        formula_template="""df['hh'] = df['high'] > df['high'].shift({period})
df['hl'] = df['low'] > df['low'].shift({period})
df['entry_signal'] = df['hh'] & df['hl']""",
        params={"period": [3, 5]},
        direction="long",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="HLS",
    ),
    # Lower highs and lower lows (strong downtrend)
    PatternBlock(
        id="LH_LL",
        name="Lower Highs and Lower Lows",
        category="higher_lows",
        formula_template="""df['lh'] = df['high'] < df['high'].shift({period})
df['ll'] = df['low'] < df['low'].shift({period})
df['entry_signal'] = df['lh'] & df['ll']""",
        params={"period": [3, 5]},
        direction="short",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="HLS",
    ),
]


# =============================================================================
# CHANNEL POSITION BLOCKS
# =============================================================================

CHANNEL_POSITION_BLOCKS = [
    # Price in lower third of channel
    PatternBlock(
        id="CHANNEL_LOWER_THIRD",
        name="Price in Lower Third",
        category="channel_position",
        formula_template="""df['ch_high'] = df['high'].rolling({period}).max()
df['ch_low'] = df['low'].rolling({period}).min()
df['ch_range'] = df['ch_high'] - df['ch_low']
df['position'] = (df['close'] - df['ch_low']) / df['ch_range']
df['entry_signal'] = df['position'] < 0.33""",
        params={"period": [20, 50]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CHP",
    ),
    # Price in upper third of channel
    PatternBlock(
        id="CHANNEL_UPPER_THIRD",
        name="Price in Upper Third",
        category="channel_position",
        formula_template="""df['ch_high'] = df['high'].rolling({period}).max()
df['ch_low'] = df['low'].rolling({period}).min()
df['ch_range'] = df['ch_high'] - df['ch_low']
df['position'] = (df['close'] - df['ch_low']) / df['ch_range']
df['entry_signal'] = df['position'] > 0.67""",
        params={"period": [20, 50]},
        direction="short",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="CHP",
    ),
    # Price crossing channel midpoint up
    PatternBlock(
        id="CHANNEL_MID_CROSS_UP",
        name="Channel Midpoint Cross Up",
        category="channel_position",
        formula_template="""df['ch_high'] = df['high'].rolling({period}).max()
df['ch_low'] = df['low'].rolling({period}).min()
df['ch_mid'] = (df['ch_high'] + df['ch_low']) / 2
df['above_mid'] = df['close'] > df['ch_mid']
df['was_below'] = df['close'].shift(1) <= df['ch_mid'].shift(1)
df['entry_signal'] = df['above_mid'] & df['was_below']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="CHP",
    ),
]


# =============================================================================
# MOMENTUM EXTREME BLOCKS
# =============================================================================

MOMENTUM_EXTREME_BLOCKS = [
    # RSI + CCI both oversold
    PatternBlock(
        id="RSI_CCI_OVERSOLD",
        name="RSI and CCI Oversold",
        category="momentum_extreme",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod=20)
df['rsi_oversold'] = df['rsi'] < {rsi_thresh}
df['cci_oversold'] = df['cci'] < -{cci_thresh}
df['entry_signal'] = df['rsi_oversold'] & df['cci_oversold']""",
        params={"rsi_thresh": [30, 35], "cci_thresh": [100, 150]},
        direction="long",
        lookback=30,
        indicators=["rsi", "cci"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MEX",
    ),
    # RSI + CCI both overbought
    PatternBlock(
        id="RSI_CCI_OVERBOUGHT",
        name="RSI and CCI Overbought",
        category="momentum_extreme",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod=20)
df['rsi_overbought'] = df['rsi'] > {rsi_thresh}
df['cci_overbought'] = df['cci'] > {cci_thresh}
df['entry_signal'] = df['rsi_overbought'] & df['cci_overbought']""",
        params={"rsi_thresh": [65, 70], "cci_thresh": [100, 150]},
        direction="short",
        lookback=30,
        indicators=["rsi", "cci"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MEX",
    ),
    # Triple momentum oversold
    PatternBlock(
        id="TRIPLE_MOM_OVERSOLD",
        name="Triple Momentum Oversold",
        category="momentum_extreme",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'])
df['willr'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod=14)
df['rsi_low'] = df['rsi'] < 35
df['stoch_low'] = df['slowk'] < 25
df['willr_low'] = df['willr'] < -75
df['entry_signal'] = df['rsi_low'] & df['stoch_low'] & df['willr_low']""",
        params={},
        direction="long",
        lookback=30,
        indicators=["rsi", "stoch", "willr"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MEX",
    ),
]


# =============================================================================
# VOLATILITY REGIME BLOCKS
# =============================================================================

VOLATILITY_REGIME_BLOCKS = [
    # High volatility regime
    PatternBlock(
        id="VOL_REGIME_HIGH",
        name="High Volatility Regime",
        category="volatility_regime",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['atr_pct'] = df['atr'] / df['close'] * 100
df['atr_avg'] = df['atr_pct'].rolling({avg_period}).mean()
df['entry_signal'] = df['atr_pct'] > df['atr_avg'] * {mult}""",
        params={"period": [14], "avg_period": [50], "mult": [1.5, 2.0]},
        direction="bidi",
        lookback=60,
        indicators=["atr"],
        combinable_with=["threshold", "momentum"],
        strategy_type="VRG",
    ),
    # Low volatility regime (squeeze)
    PatternBlock(
        id="VOL_REGIME_LOW",
        name="Low Volatility Regime",
        category="volatility_regime",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['atr_pct'] = df['atr'] / df['close'] * 100
df['atr_avg'] = df['atr_pct'].rolling({avg_period}).mean()
df['entry_signal'] = df['atr_pct'] < df['atr_avg'] * {mult}""",
        params={"period": [14], "avg_period": [50], "mult": [0.5, 0.7]},
        direction="bidi",
        lookback=60,
        indicators=["atr"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="VRG",
    ),
    # Volatility regime transition (from low to high)
    PatternBlock(
        id="VOL_REGIME_TRANSITION",
        name="Volatility Regime Transition",
        category="volatility_regime",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['atr_pct'] = df['atr'] / df['close'] * 100
df['atr_avg'] = df['atr_pct'].rolling({avg_period}).mean()
df['was_low'] = df['atr_pct'].shift(1) < df['atr_avg'].shift(1) * 0.7
df['now_high'] = df['atr_pct'] > df['atr_avg']
df['entry_signal'] = df['was_low'] & df['now_high']""",
        params={"period": [14], "avg_period": [50]},
        direction="bidi",
        lookback=60,
        indicators=["atr"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VRG",
    ),
]


# =============================================================================
# TREND QUALITY BLOCKS
# =============================================================================

TREND_QUALITY_BLOCKS = [
    # Strong uptrend (ADX high + positive slope)
    PatternBlock(
        id="STRONG_UPTREND",
        name="Strong Uptrend",
        category="trend_quality",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod={period})
df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['strong_trend'] = df['adx'] > {adx_thresh}
df['bullish'] = df['plus_di'] > df['minus_di']
df['entry_signal'] = df['strong_trend'] & df['bullish']""",
        params={"period": [14], "adx_thresh": [25, 30]},
        direction="long",
        lookback=30,
        indicators=["adx", "plus_di", "minus_di"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="TQU",
    ),
    # Strong downtrend
    PatternBlock(
        id="STRONG_DOWNTREND",
        name="Strong Downtrend",
        category="trend_quality",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod={period})
df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['strong_trend'] = df['adx'] > {adx_thresh}
df['bearish'] = df['minus_di'] > df['plus_di']
df['entry_signal'] = df['strong_trend'] & df['bearish']""",
        params={"period": [14], "adx_thresh": [25, 30]},
        direction="short",
        lookback=30,
        indicators=["adx", "plus_di", "minus_di"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="TQU",
    ),
    # Weak/ranging market
    PatternBlock(
        id="WEAK_TREND",
        name="Weak Trend / Ranging",
        category="trend_quality",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod={period})
df['weak_trend'] = df['adx'] < {adx_thresh}
df['entry_signal'] = df['weak_trend']""",
        params={"period": [14], "adx_thresh": [20, 25]},
        direction="bidi",
        lookback=30,
        indicators=["adx"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="TQU",
    ),
]


# =============================================================================
# DOUBLE PATTERN BLOCKS
# =============================================================================

DOUBLE_PATTERN_BLOCKS = [
    # Double bottom approximation
    PatternBlock(
        id="DOUBLE_BOTTOM",
        name="Double Bottom Pattern",
        category="double_pattern",
        formula_template="""df['low_min'] = df['low'].rolling({period}).min()
df['near_low'] = (df['low'] - df['low_min']) / df['close'] < {tolerance}
df['bounce'] = df['close'] > df['open']
df['prev_near_low'] = df['near_low'].shift({lookback})
df['entry_signal'] = df['near_low'] & df['bounce'] & df['prev_near_low']""",
        params={"period": [20], "lookback": [5, 10], "tolerance": [0.01, 0.02]},
        direction="long",
        lookback=40,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="DBL",
    ),
    # Double top approximation
    PatternBlock(
        id="DOUBLE_TOP",
        name="Double Top Pattern",
        category="double_pattern",
        formula_template="""df['high_max'] = df['high'].rolling({period}).max()
df['near_high'] = (df['high_max'] - df['high']) / df['close'] < {tolerance}
df['reject'] = df['close'] < df['open']
df['prev_near_high'] = df['near_high'].shift({lookback})
df['entry_signal'] = df['near_high'] & df['reject'] & df['prev_near_high']""",
        params={"period": [20], "lookback": [5, 10], "tolerance": [0.01, 0.02]},
        direction="short",
        lookback=40,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="DBL",
    ),
    # Failed double bottom (breakdown)
    PatternBlock(
        id="FAILED_DOUBLE_BOTTOM",
        name="Failed Double Bottom",
        category="double_pattern",
        formula_template="""df['low_min'] = df['low'].rolling({period}).min()
df['break_below'] = df['close'] < df['low_min'].shift(1)
df['entry_signal'] = df['break_below']""",
        params={"period": [20, 30]},
        direction="short",
        lookback=40,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="DBL",
    ),
    # Failed double top (breakout)
    PatternBlock(
        id="FAILED_DOUBLE_TOP",
        name="Failed Double Top",
        category="double_pattern",
        formula_template="""df['high_max'] = df['high'].rolling({period}).max()
df['break_above'] = df['close'] > df['high_max'].shift(1)
df['entry_signal'] = df['break_above']""",
        params={"period": [20, 30]},
        direction="long",
        lookback=40,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="DBL",
    ),
]


# =============================================================================
# BREAKOUT CONFIRMATION BLOCKS
# =============================================================================

BREAKOUT_CONFIRM_BLOCKS = [
    # Breakout with volume confirmation
    PatternBlock(
        id="BREAKOUT_VOL_CONFIRM",
        name="Breakout with Volume",
        category="breakout_confirm",
        formula_template="""df['resistance'] = df['high'].rolling({period}).max().shift(1)
df['breakout'] = df['close'] > df['resistance']
df['vol_avg'] = df['volume'].rolling({period}).mean()
df['vol_confirm'] = df['volume'] > df['vol_avg'] * {vol_mult}
df['entry_signal'] = df['breakout'] & df['vol_confirm']""",
        params={"period": [20], "vol_mult": [1.5, 2.0]},
        direction="long",
        lookback=40,
        indicators=[],
        combinable_with=["threshold", "momentum"],
        strategy_type="BKC",
    ),
    # Breakdown with volume confirmation
    PatternBlock(
        id="BREAKDOWN_VOL_CONFIRM",
        name="Breakdown with Volume",
        category="breakout_confirm",
        formula_template="""df['support'] = df['low'].rolling({period}).min().shift(1)
df['breakdown'] = df['close'] < df['support']
df['vol_avg'] = df['volume'].rolling({period}).mean()
df['vol_confirm'] = df['volume'] > df['vol_avg'] * {vol_mult}
df['entry_signal'] = df['breakdown'] & df['vol_confirm']""",
        params={"period": [20], "vol_mult": [1.5, 2.0]},
        direction="short",
        lookback=40,
        indicators=[],
        combinable_with=["threshold", "momentum"],
        strategy_type="BKC",
    ),
    # Breakout with momentum confirmation
    PatternBlock(
        id="BREAKOUT_MOM_CONFIRM",
        name="Breakout with Momentum",
        category="breakout_confirm",
        formula_template="""df['resistance'] = df['high'].rolling({period}).max().shift(1)
df['breakout'] = df['close'] > df['resistance']
df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['rsi_strong'] = df['rsi'] > 50
df['entry_signal'] = df['breakout'] & df['rsi_strong']""",
        params={"period": [20]},
        direction="long",
        lookback=40,
        indicators=["rsi"],
        combinable_with=["volume", "confirmation"],
        strategy_type="BKC",
    ),
]


# =============================================================================
# EMA STACK BLOCKS
# =============================================================================

EMA_STACK_BLOCKS = [
    # Bullish EMA stack (fast > medium > slow)
    PatternBlock(
        id="EMA_STACK_BULL",
        name="Bullish EMA Stack",
        category="ema_stack",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
df['ema_med'] = ta.EMA(df['close'], timeperiod={med})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
df['stack_bull'] = (df['ema_fast'] > df['ema_med']) & (df['ema_med'] > df['ema_slow'])
df['entry_signal'] = df['stack_bull']""",
        params={"fast": [8, 10], "med": [21], "slow": [50]},
        direction="long",
        lookback=60,
        indicators=["ema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="EMS",
    ),
    # Bearish EMA stack (fast < medium < slow)
    PatternBlock(
        id="EMA_STACK_BEAR",
        name="Bearish EMA Stack",
        category="ema_stack",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
df['ema_med'] = ta.EMA(df['close'], timeperiod={med})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
df['stack_bear'] = (df['ema_fast'] < df['ema_med']) & (df['ema_med'] < df['ema_slow'])
df['entry_signal'] = df['stack_bear']""",
        params={"fast": [8, 10], "med": [21], "slow": [50]},
        direction="short",
        lookback=60,
        indicators=["ema"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="EMS",
    ),
    # EMA stack alignment change (becomes bullish)
    PatternBlock(
        id="EMA_STACK_ALIGN_BULL",
        name="EMA Stack Becomes Bullish",
        category="ema_stack",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
df['ema_med'] = ta.EMA(df['close'], timeperiod={med})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
df['stack_bull'] = (df['ema_fast'] > df['ema_med']) & (df['ema_med'] > df['ema_slow'])
df['was_not_bull'] = ~((df['ema_fast'].shift(1) > df['ema_med'].shift(1)) & (df['ema_med'].shift(1) > df['ema_slow'].shift(1)))
df['entry_signal'] = df['stack_bull'] & df['was_not_bull']""",
        params={"fast": [10], "med": [21], "slow": [50]},
        direction="long",
        lookback=60,
        indicators=["ema"],
        combinable_with=["volume", "confirmation"],
        strategy_type="EMS",
    ),
]


# =============================================================================
# INTRADAY MOMENTUM BLOCKS
# =============================================================================

INTRADAY_MOM_BLOCKS = [
    # Strong bullish bar (close near high)
    PatternBlock(
        id="INTRADAY_BULL_STRONG",
        name="Strong Intraday Bullish",
        category="intraday_mom",
        formula_template="""df['bar_range'] = df['high'] - df['low']
df['close_strength'] = (df['close'] - df['low']) / df['bar_range']
df['open_strength'] = (df['open'] - df['low']) / df['bar_range']
df['strong_bull'] = (df['close_strength'] > {close_thresh}) & (df['close'] > df['open'])
df['entry_signal'] = df['strong_bull']""",
        params={"close_thresh": [0.7, 0.8]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="IDM",
    ),
    # Strong bearish bar (close near low)
    PatternBlock(
        id="INTRADAY_BEAR_STRONG",
        name="Strong Intraday Bearish",
        category="intraday_mom",
        formula_template="""df['bar_range'] = df['high'] - df['low']
df['close_strength'] = (df['close'] - df['low']) / df['bar_range']
df['strong_bear'] = (df['close_strength'] < {close_thresh}) & (df['close'] < df['open'])
df['entry_signal'] = df['strong_bear']""",
        params={"close_thresh": [0.2, 0.3]},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="IDM",
    ),
    # Intraday reversal (open weak, close strong)
    PatternBlock(
        id="INTRADAY_REVERSAL_UP",
        name="Intraday Reversal Up",
        category="intraday_mom",
        formula_template="""df['bar_range'] = df['high'] - df['low']
df['open_pos'] = (df['open'] - df['low']) / df['bar_range']
df['close_pos'] = (df['close'] - df['low']) / df['bar_range']
df['reversal'] = (df['open_pos'] < 0.3) & (df['close_pos'] > 0.7)
df['entry_signal'] = df['reversal']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="IDM",
    ),
]


# =============================================================================
# PRICE REJECTION BLOCKS
# =============================================================================

PRICE_REJECTION_BLOCKS = [
    # Upper wick rejection (price rejected at highs)
    PatternBlock(
        id="UPPER_WICK_REJECT",
        name="Upper Wick Rejection",
        category="price_rejection",
        formula_template="""df['upper_wick'] = df['high'] - df[['close', 'open']].max(axis=1)
df['bar_range'] = df['high'] - df['low']
df['wick_ratio'] = df['upper_wick'] / df['bar_range']
df['at_resistance'] = df['high'] >= df['high'].rolling({period}).max().shift(1) * 0.99
df['entry_signal'] = (df['wick_ratio'] > {threshold}) & df['at_resistance']""",
        params={"period": [20], "threshold": [0.5, 0.6]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PRJ",
    ),
    # Lower wick rejection (price rejected at lows)
    PatternBlock(
        id="LOWER_WICK_REJECT",
        name="Lower Wick Rejection",
        category="price_rejection",
        formula_template="""df['lower_wick'] = df[['close', 'open']].min(axis=1) - df['low']
df['bar_range'] = df['high'] - df['low']
df['wick_ratio'] = df['lower_wick'] / df['bar_range']
df['at_support'] = df['low'] <= df['low'].rolling({period}).min().shift(1) * 1.01
df['entry_signal'] = (df['wick_ratio'] > {threshold}) & df['at_support']""",
        params={"period": [20], "threshold": [0.5, 0.6]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PRJ",
    ),
    # Failed breakout rejection
    PatternBlock(
        id="FAILED_BREAK_REJECT",
        name="Failed Breakout Rejection",
        category="price_rejection",
        formula_template="""df['prev_high'] = df['high'].rolling({period}).max().shift(1)
df['broke_out'] = df['high'] > df['prev_high']
df['closed_below'] = df['close'] < df['prev_high']
df['entry_signal'] = df['broke_out'] & df['closed_below']""",
        params={"period": [20]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PRJ",
    ),
]


# =============================================================================
# CLIMAX VOLUME BLOCKS
# =============================================================================

CLIMAX_VOLUME_BLOCKS = [
    # Selling climax (high volume + down bar + reversal)
    PatternBlock(
        id="SELLING_CLIMAX",
        name="Selling Climax",
        category="climax_volume",
        formula_template="""df['vol_avg'] = df['volume'].rolling({period}).mean()
df['vol_spike'] = df['volume'] > df['vol_avg'] * {mult}
df['down_bar'] = df['close'] < df['open']
df['lower_wick'] = df[['close', 'open']].min(axis=1) - df['low']
df['bar_range'] = df['high'] - df['low']
df['wick_ratio'] = df['lower_wick'] / df['bar_range']
df['entry_signal'] = df['vol_spike'] & df['down_bar'] & (df['wick_ratio'] > 0.4)""",
        params={"period": [20], "mult": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="CLX",
    ),
    # Buying climax (high volume + up bar + reversal potential)
    PatternBlock(
        id="BUYING_CLIMAX",
        name="Buying Climax",
        category="climax_volume",
        formula_template="""df['vol_avg'] = df['volume'].rolling({period}).mean()
df['vol_spike'] = df['volume'] > df['vol_avg'] * {mult}
df['up_bar'] = df['close'] > df['open']
df['upper_wick'] = df['high'] - df[['close', 'open']].max(axis=1)
df['bar_range'] = df['high'] - df['low']
df['wick_ratio'] = df['upper_wick'] / df['bar_range']
df['entry_signal'] = df['vol_spike'] & df['up_bar'] & (df['wick_ratio'] > 0.4)""",
        params={"period": [20], "mult": [2.0, 2.5]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="CLX",
    ),
    # Exhaustion volume (extreme volume after trend)
    PatternBlock(
        id="EXHAUSTION_VOLUME",
        name="Exhaustion Volume",
        category="climax_volume",
        formula_template="""df['vol_avg'] = df['volume'].rolling({period}).mean()
df['vol_extreme'] = df['volume'] > df['vol_avg'] * {mult}
df['trend_up'] = df['close'] > df['close'].shift({trend_period})
df['entry_signal'] = df['vol_extreme'] & df['trend_up']""",
        params={"period": [20], "mult": [3.0], "trend_period": [10]},
        direction="short",
        lookback=40,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="CLX",
    ),
]


# =============================================================================
# RETRACEMENT BLOCKS
# =============================================================================

RETRACEMENT_BLOCKS = [
    # 38% retracement (shallow pullback)
    PatternBlock(
        id="RETRACE_38",
        name="38% Retracement",
        category="retracement",
        formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
df['swing_low'] = df['low'].rolling({period}).min()
df['swing_range'] = df['swing_high'] - df['swing_low']
df['retrace_level'] = df['swing_high'] - df['swing_range'] * 0.382
df['near_level'] = abs(df['close'] - df['retrace_level']) / df['close'] < {tolerance}
df['bouncing'] = df['close'] > df['open']
df['entry_signal'] = df['near_level'] & df['bouncing']""",
        params={"period": [20, 50], "tolerance": [0.01, 0.02]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="RTR",
    ),
    # 50% retracement
    PatternBlock(
        id="RETRACE_50",
        name="50% Retracement",
        category="retracement",
        formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
df['swing_low'] = df['low'].rolling({period}).min()
df['swing_range'] = df['swing_high'] - df['swing_low']
df['retrace_level'] = df['swing_high'] - df['swing_range'] * 0.5
df['near_level'] = abs(df['close'] - df['retrace_level']) / df['close'] < {tolerance}
df['bouncing'] = df['close'] > df['open']
df['entry_signal'] = df['near_level'] & df['bouncing']""",
        params={"period": [20, 50], "tolerance": [0.01, 0.02]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="RTR",
    ),
    # 62% retracement (deep pullback)
    PatternBlock(
        id="RETRACE_62",
        name="62% Retracement",
        category="retracement",
        formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
df['swing_low'] = df['low'].rolling({period}).min()
df['swing_range'] = df['swing_high'] - df['swing_low']
df['retrace_level'] = df['swing_high'] - df['swing_range'] * 0.618
df['near_level'] = abs(df['close'] - df['retrace_level']) / df['close'] < {tolerance}
df['bouncing'] = df['close'] > df['open']
df['entry_signal'] = df['near_level'] & df['bouncing']""",
        params={"period": [20, 50], "tolerance": [0.01, 0.02]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="RTR",
    ),
    # Retracement complete (price returns to trend)
    PatternBlock(
        id="RETRACE_COMPLETE",
        name="Retracement Complete",
        category="retracement",
        formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
df['swing_low'] = df['low'].rolling({period}).min()
df['mid_point'] = (df['swing_high'] + df['swing_low']) / 2
df['was_below_mid'] = df['close'].shift(1) < df['mid_point'].shift(1)
df['now_above_mid'] = df['close'] > df['mid_point']
df['entry_signal'] = df['was_below_mid'] & df['now_above_mid']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="RTR",
    ),
]


# =============================================================================
# EXPANSION CYCLE BLOCKS
# =============================================================================

EXPANSION_CYCLE_BLOCKS = [
    # Range expansion after contraction
    PatternBlock(
        id="EXPANSION_AFTER_SQUEEZE",
        name="Expansion After Squeeze",
        category="expansion_cycle",
        formula_template="""df['bar_range'] = df['high'] - df['low']
df['range_avg'] = df['bar_range'].rolling({period}).mean()
df['was_contracted'] = df['bar_range'].shift(1) < df['range_avg'].shift(1) * {contract_mult}
df['now_expanded'] = df['bar_range'] > df['range_avg'] * {expand_mult}
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['was_contracted'] & df['now_expanded'] & df['bullish']""",
        params={"period": [20], "contract_mult": [0.5], "expand_mult": [1.5]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="EXC",
    ),
    # Contraction setup (preparing for breakout)
    PatternBlock(
        id="CONTRACTION_SETUP",
        name="Contraction Setup",
        category="expansion_cycle",
        formula_template="""df['bar_range'] = df['high'] - df['low']
df['range_avg'] = df['bar_range'].rolling({period}).mean()
df['contracted'] = df['bar_range'] < df['range_avg'] * {mult}
df['consec_contract'] = df['contracted'].rolling({bars}).sum() >= {bars}
df['entry_signal'] = df['consec_contract']""",
        params={"period": [20], "mult": [0.6, 0.7], "bars": [3, 4]},
        direction="bidi",
        lookback=30,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="EXC",
    ),
    # Volatility cycle low
    PatternBlock(
        id="VOL_CYCLE_LOW",
        name="Volatility Cycle Low",
        category="expansion_cycle",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['atr_min'] = df['atr'].rolling({lookback}).min()
df['at_low'] = df['atr'] <= df['atr_min'] * 1.1
df['entry_signal'] = df['at_low']""",
        params={"period": [14], "lookback": [50, 100]},
        direction="bidi",
        lookback=110,
        indicators=["atr"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="EXC",
    ),
]


# =============================================================================
# PRICE MEMORY BLOCKS
# =============================================================================

PRICE_MEMORY_BLOCKS = [
    # Return to previous high
    PatternBlock(
        id="RETURN_PREV_HIGH",
        name="Return to Previous High",
        category="price_memory",
        formula_template="""df['prev_high'] = df['high'].shift({period})
df['near_prev_high'] = abs(df['close'] - df['prev_high']) / df['close'] < {tolerance}
df['from_below'] = df['close'].shift(1) < df['prev_high'].shift(1)
df['entry_signal'] = df['near_prev_high'] & df['from_below']""",
        params={"period": [10, 20], "tolerance": [0.005, 0.01]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PMM",
    ),
    # Return to previous low
    PatternBlock(
        id="RETURN_PREV_LOW",
        name="Return to Previous Low",
        category="price_memory",
        formula_template="""df['prev_low'] = df['low'].shift({period})
df['near_prev_low'] = abs(df['close'] - df['prev_low']) / df['close'] < {tolerance}
df['from_above'] = df['close'].shift(1) > df['prev_low'].shift(1)
df['entry_signal'] = df['near_prev_low'] & df['from_above']""",
        params={"period": [10, 20], "tolerance": [0.005, 0.01]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PMM",
    ),
    # Return to previous close
    PatternBlock(
        id="RETURN_PREV_CLOSE",
        name="Return to Previous Close",
        category="price_memory",
        formula_template="""df['anchor_close'] = df['close'].shift({period})
df['near_anchor'] = abs(df['close'] - df['anchor_close']) / df['close'] < {tolerance}
df['was_away'] = abs(df['close'].shift(1) - df['anchor_close'].shift(1)) / df['close'].shift(1) > {tolerance} * 2
df['entry_signal'] = df['near_anchor'] & df['was_away']""",
        params={"period": [20], "tolerance": [0.01]},
        direction="bidi",
        lookback=40,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PMM",
    ),
]


# =============================================================================
# MOMENTUM SHIFT BLOCKS
# =============================================================================

MOMENTUM_SHIFT_BLOCKS = [
    # Momentum direction flip (negative to positive)
    PatternBlock(
        id="MOM_FLIP_UP",
        name="Momentum Flip Up",
        category="momentum_shift",
        formula_template="""df['mom'] = ta.MOM(df['close'], timeperiod={period})
df['mom_positive'] = df['mom'] > 0
df['mom_was_negative'] = df['mom'].shift(1) < 0
df['entry_signal'] = df['mom_positive'] & df['mom_was_negative']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=20,
        indicators=["mom"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="MSH",
    ),
    # Momentum direction flip (positive to negative)
    PatternBlock(
        id="MOM_FLIP_DOWN",
        name="Momentum Flip Down",
        category="momentum_shift",
        formula_template="""df['mom'] = ta.MOM(df['close'], timeperiod={period})
df['mom_negative'] = df['mom'] < 0
df['mom_was_positive'] = df['mom'].shift(1) > 0
df['entry_signal'] = df['mom_negative'] & df['mom_was_positive']""",
        params={"period": [10, 14]},
        direction="short",
        lookback=20,
        indicators=["mom"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="MSH",
    ),
    # Momentum acceleration change
    PatternBlock(
        id="MOM_ACCEL_CHANGE",
        name="Momentum Acceleration Change",
        category="momentum_shift",
        formula_template="""df['mom'] = ta.MOM(df['close'], timeperiod={period})
df['mom_accel'] = df['mom'] - df['mom'].shift(1)
df['accel_positive'] = df['mom_accel'] > 0
df['accel_was_negative'] = df['mom_accel'].shift(1) < 0
df['mom_recovering'] = df['mom'] > df['mom'].rolling(5).min()
df['entry_signal'] = df['accel_positive'] & df['accel_was_negative'] & df['mom_recovering']""",
        params={"period": [10]},
        direction="long",
        lookback=20,
        indicators=["mom"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="MSH",
    ),
]


# =============================================================================
# BARS SINCE BLOCKS
# =============================================================================

BARS_SINCE_BLOCKS = [
    # N bars since swing high
    PatternBlock(
        id="BARS_SINCE_HIGH",
        name="Bars Since High",
        category="bars_since",
        formula_template="""df['is_high'] = df['high'] == df['high'].rolling({lookback}).max()
df['bars_since'] = df['is_high'].cumsum()
df['bars_since'] = df.groupby(df['bars_since']).cumcount()
df['entry_signal'] = df['bars_since'] == {trigger_bars}""",
        params={"lookback": [20], "trigger_bars": [5, 10]},
        direction="short",
        lookback=40,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="BSN",
    ),
    # N bars since swing low
    PatternBlock(
        id="BARS_SINCE_LOW",
        name="Bars Since Low",
        category="bars_since",
        formula_template="""df['is_low'] = df['low'] == df['low'].rolling({lookback}).min()
df['bars_since'] = df['is_low'].cumsum()
df['bars_since'] = df.groupby(df['bars_since']).cumcount()
df['entry_signal'] = df['bars_since'] == {trigger_bars}""",
        params={"lookback": [20], "trigger_bars": [5, 10]},
        direction="long",
        lookback=40,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="BSN",
    ),
    # First bar after consolidation
    PatternBlock(
        id="FIRST_BAR_AFTER_CONSOL",
        name="First Bar After Consolidation",
        category="bars_since",
        formula_template="""df['bar_range'] = df['high'] - df['low']
df['range_avg'] = df['bar_range'].rolling({period}).mean()
df['is_narrow'] = df['bar_range'] < df['range_avg'] * 0.5
df['consec_narrow'] = df['is_narrow'].rolling({consol_bars}).sum() >= {consol_bars}
df['now_wide'] = df['bar_range'] > df['range_avg']
df['entry_signal'] = df['consec_narrow'].shift(1) & df['now_wide']""",
        params={"period": [20], "consol_bars": [3, 4]},
        direction="bidi",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="BSN",
    ),
]


# =============================================================================
# RELATIVE POSITION BLOCKS
# =============================================================================

RELATIVE_POSITION_BLOCKS = [
    # Price position relative to MA
    PatternBlock(
        id="REL_POS_MA",
        name="Relative Position to MA",
        category="relative_position",
        formula_template="""df['ma'] = ta.SMA(df['close'], timeperiod={period})
df['rel_pos'] = (df['close'] - df['ma']) / df['ma'] * 100
df['extended_below'] = df['rel_pos'] < -{threshold}
df['turning_up'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['extended_below'] & df['turning_up']""",
        params={"period": [20, 50], "threshold": [2, 3, 5]},
        direction="long",
        lookback=60,
        indicators=["sma"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="RPS",
    ),
    # Price position in daily range
    PatternBlock(
        id="REL_POS_RANGE",
        name="Relative Position in Range",
        category="relative_position",
        formula_template="""df['range_high'] = df['high'].rolling({period}).max()
df['range_low'] = df['low'].rolling({period}).min()
df['range_pos'] = (df['close'] - df['range_low']) / (df['range_high'] - df['range_low'])
df['oversold'] = df['range_pos'] < {threshold}
df['entry_signal'] = df['oversold']""",
        params={"period": [20], "threshold": [0.1, 0.2]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="RPS",
    ),
    # Price vs VWAP position
    PatternBlock(
        id="REL_POS_VWAP",
        name="Relative Position to VWAP",
        category="relative_position",
        formula_template="""df['vwap'] = (df['close'] * df['volume']).rolling({period}).sum() / df['volume'].rolling({period}).sum()
df['below_vwap'] = df['close'] < df['vwap']
df['cross_above'] = (df['close'] > df['vwap']) & (df['close'].shift(1) <= df['vwap'].shift(1))
df['entry_signal'] = df['cross_above']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="RPS",
    ),
]


# =============================================================================
# THRUST BLOCKS
# =============================================================================

THRUST_BLOCKS = [
    # Bullish thrust (strong move after consolidation)
    PatternBlock(
        id="THRUST_BULL",
        name="Bullish Thrust",
        category="thrust",
        formula_template="""df['bar_range'] = df['high'] - df['low']
df['range_avg'] = df['bar_range'].rolling({period}).mean()
df['was_quiet'] = df['bar_range'].shift(1) < df['range_avg'].shift(1) * 0.7
df['big_move'] = df['bar_range'] > df['range_avg'] * {mult}
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['was_quiet'] & df['big_move'] & df['bullish']""",
        params={"period": [20], "mult": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="THT",
    ),
    # Bearish thrust
    PatternBlock(
        id="THRUST_BEAR",
        name="Bearish Thrust",
        category="thrust",
        formula_template="""df['bar_range'] = df['high'] - df['low']
df['range_avg'] = df['bar_range'].rolling({period}).mean()
df['was_quiet'] = df['bar_range'].shift(1) < df['range_avg'].shift(1) * 0.7
df['big_move'] = df['bar_range'] > df['range_avg'] * {mult}
df['bearish'] = df['close'] < df['open']
df['entry_signal'] = df['was_quiet'] & df['big_move'] & df['bearish']""",
        params={"period": [20], "mult": [1.5, 2.0]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="THT",
    ),
    # Thrust continuation
    PatternBlock(
        id="THRUST_CONTINUE",
        name="Thrust Continuation",
        category="thrust",
        formula_template="""df['bar_range'] = df['high'] - df['low']
df['range_avg'] = df['bar_range'].rolling({period}).mean()
df['prev_thrust'] = df['bar_range'].shift(1) > df['range_avg'].shift(1) * 1.5
df['prev_bull'] = df['close'].shift(1) > df['open'].shift(1)
df['continues'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['prev_thrust'] & df['prev_bull'] & df['continues']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="THT",
    ),
]


# =============================================================================
# PIVOT EXTENDED BLOCKS
# =============================================================================

PIVOT_EXT_BLOCKS = [
    # Bounce off S1 support
    PatternBlock(
        id="PIVOT_S1_BOUNCE",
        name="Pivot S1 Bounce",
        category="pivot_ext",
        formula_template="""df['pp'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
df['s1'] = 2 * df['pp'] - df['high'].shift(1)
df['near_s1'] = abs(df['low'] - df['s1']) / df['close'] < {tolerance}
df['bounce'] = df['close'] > df['open']
df['entry_signal'] = df['near_s1'] & df['bounce']""",
        params={"tolerance": [0.005, 0.01]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PVE",
    ),
    # Rejection at R1 resistance
    PatternBlock(
        id="PIVOT_R1_REJECT",
        name="Pivot R1 Rejection",
        category="pivot_ext",
        formula_template="""df['pp'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
df['r1'] = 2 * df['pp'] - df['low'].shift(1)
df['near_r1'] = abs(df['high'] - df['r1']) / df['close'] < {tolerance}
df['reject'] = df['close'] < df['open']
df['entry_signal'] = df['near_r1'] & df['reject']""",
        params={"tolerance": [0.005, 0.01]},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="PVE",
    ),
    # Break above R1
    PatternBlock(
        id="PIVOT_R1_BREAK",
        name="Pivot R1 Breakout",
        category="pivot_ext",
        formula_template="""df['pp'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
df['r1'] = 2 * df['pp'] - df['low'].shift(1)
df['break_r1'] = df['close'] > df['r1']
df['was_below'] = df['close'].shift(1) <= df['r1'].shift(1)
df['entry_signal'] = df['break_r1'] & df['was_below']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="PVE",
    ),
    # Break below S1
    PatternBlock(
        id="PIVOT_S1_BREAK",
        name="Pivot S1 Breakdown",
        category="pivot_ext",
        formula_template="""df['pp'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
df['s1'] = 2 * df['pp'] - df['high'].shift(1)
df['break_s1'] = df['close'] < df['s1']
df['was_above'] = df['close'].shift(1) >= df['s1'].shift(1)
df['entry_signal'] = df['break_s1'] & df['was_above']""",
        params={},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="PVE",
    ),
]


# =============================================================================
# ATR BANDS BLOCKS
# =============================================================================

ATR_BANDS_BLOCKS = [
    # Price touches lower ATR band
    PatternBlock(
        id="ATR_BAND_LOWER_TOUCH",
        name="ATR Lower Band Touch",
        category="atr_bands",
        formula_template="""df['ma'] = ta.SMA(df['close'], timeperiod={ma_period})
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={atr_period})
df['lower_band'] = df['ma'] - df['atr'] * {mult}
df['touch_lower'] = df['low'] <= df['lower_band']
df['bounce'] = df['close'] > df['open']
df['entry_signal'] = df['touch_lower'] & df['bounce']""",
        params={"ma_period": [20], "atr_period": [14], "mult": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=["sma", "atr"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ATB",
    ),
    # Price touches upper ATR band
    PatternBlock(
        id="ATR_BAND_UPPER_TOUCH",
        name="ATR Upper Band Touch",
        category="atr_bands",
        formula_template="""df['ma'] = ta.SMA(df['close'], timeperiod={ma_period})
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={atr_period})
df['upper_band'] = df['ma'] + df['atr'] * {mult}
df['touch_upper'] = df['high'] >= df['upper_band']
df['reject'] = df['close'] < df['open']
df['entry_signal'] = df['touch_upper'] & df['reject']""",
        params={"ma_period": [20], "atr_period": [14], "mult": [2.0, 2.5]},
        direction="short",
        lookback=30,
        indicators=["sma", "atr"],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="ATB",
    ),
    # Price returns to MA from ATR band
    PatternBlock(
        id="ATR_BAND_RETURN",
        name="ATR Band Return to MA",
        category="atr_bands",
        formula_template="""df['ma'] = ta.SMA(df['close'], timeperiod={ma_period})
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={atr_period})
df['lower_band'] = df['ma'] - df['atr'] * {mult}
df['was_at_lower'] = df['low'].shift(1) <= df['lower_band'].shift(1)
df['returning'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['was_at_lower'] & df['returning']""",
        params={"ma_period": [20], "atr_period": [14], "mult": [2.0]},
        direction="long",
        lookback=30,
        indicators=["sma", "atr"],
        combinable_with=["volume", "confirmation"],
        strategy_type="ATB",
    ),
]


# =============================================================================
# PRICE CHANGE RATE BLOCKS
# =============================================================================

PRICE_CHANGE_RATE_BLOCKS = [
    # Fast price change rate positive
    PatternBlock(
        id="PRICE_RATE_FAST_UP",
        name="Fast Price Rate Up",
        category="price_change_rate",
        formula_template="""df['rate_fast'] = (df['close'] - df['close'].shift({fast})) / df['close'].shift({fast}) * 100
df['rate_slow'] = (df['close'] - df['close'].shift({slow})) / df['close'].shift({slow}) * 100
df['fast_positive'] = df['rate_fast'] > {threshold}
df['accelerating'] = df['rate_fast'] > df['rate_slow']
df['entry_signal'] = df['fast_positive'] & df['accelerating']""",
        params={"fast": [3, 5], "slow": [10, 15], "threshold": [1.0, 2.0]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="PCR",
    ),
    # Fast price change rate negative
    PatternBlock(
        id="PRICE_RATE_FAST_DOWN",
        name="Fast Price Rate Down",
        category="price_change_rate",
        formula_template="""df['rate_fast'] = (df['close'] - df['close'].shift({fast})) / df['close'].shift({fast}) * 100
df['rate_slow'] = (df['close'] - df['close'].shift({slow})) / df['close'].shift({slow}) * 100
df['fast_negative'] = df['rate_fast'] < -{threshold}
df['accelerating'] = df['rate_fast'] < df['rate_slow']
df['entry_signal'] = df['fast_negative'] & df['accelerating']""",
        params={"fast": [3, 5], "slow": [10, 15], "threshold": [1.0, 2.0]},
        direction="short",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="PCR",
    ),
    # Price rate reversal
    PatternBlock(
        id="PRICE_RATE_REVERSAL",
        name="Price Rate Reversal",
        category="price_change_rate",
        formula_template="""df['rate'] = (df['close'] - df['close'].shift({period})) / df['close'].shift({period}) * 100
df['rate_positive'] = df['rate'] > 0
df['rate_was_negative'] = df['rate'].shift(1) < 0
df['entry_signal'] = df['rate_positive'] & df['rate_was_negative']""",
        params={"period": [5, 10]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PCR",
    ),
]


# =============================================================================
# VOLUME DISTRIBUTION BLOCKS
# =============================================================================

VOLUME_DISTRIBUTION_BLOCKS = [
    # Consecutive high volume bars
    PatternBlock(
        id="VOL_CONSEC_HIGH",
        name="Consecutive High Volume",
        category="volume_distribution",
        formula_template="""df['vol_avg'] = df['volume'].rolling({period}).mean()
df['high_vol'] = df['volume'] > df['vol_avg'] * {mult}
df['consec_high'] = df['high_vol'].rolling({bars}).sum() >= {bars}
df['bullish'] = df['close'] > df['close'].shift({bars})
df['entry_signal'] = df['consec_high'] & df['bullish']""",
        params={"period": [20], "mult": [1.2, 1.5], "bars": [3, 4]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["threshold", "momentum"],
        strategy_type="VDS",
    ),
    # Volume dry up (low volume streak)
    PatternBlock(
        id="VOL_DRY_UP",
        name="Volume Dry Up",
        category="volume_distribution",
        formula_template="""df['vol_avg'] = df['volume'].rolling({period}).mean()
df['low_vol'] = df['volume'] < df['vol_avg'] * {mult}
df['consec_low'] = df['low_vol'].rolling({bars}).sum() >= {bars}
df['entry_signal'] = df['consec_low']""",
        params={"period": [20], "mult": [0.5, 0.7], "bars": [3, 4]},
        direction="bidi",
        lookback=30,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="VDS",
    ),
    # Volume surge after quiet
    PatternBlock(
        id="VOL_SURGE_AFTER_QUIET",
        name="Volume Surge After Quiet",
        category="volume_distribution",
        formula_template="""df['vol_avg'] = df['volume'].rolling({period}).mean()
df['was_quiet'] = df['volume'].shift(1) < df['vol_avg'].shift(1) * 0.5
df['now_surge'] = df['volume'] > df['vol_avg'] * {mult}
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['was_quiet'] & df['now_surge'] & df['bullish']""",
        params={"period": [20], "mult": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VDS",
    ),
]


# =============================================================================
# TREND EXHAUSTION EXTENDED BLOCKS
# =============================================================================

TREND_EXHAUSTION_EXT_BLOCKS = [
    # Overextended up with momentum divergence
    PatternBlock(
        id="OVEREXT_UP_DIV",
        name="Overextended Up with Divergence",
        category="trend_exhaustion_ext",
        formula_template="""df['ma'] = ta.SMA(df['close'], timeperiod={period})
df['distance'] = (df['close'] - df['ma']) / df['ma'] * 100
df['overext'] = df['distance'] > {dist_thresh}
df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['rsi_div'] = df['rsi'] < df['rsi'].shift(5)
df['entry_signal'] = df['overext'] & df['rsi_div']""",
        params={"period": [20], "dist_thresh": [3, 5]},
        direction="short",
        lookback=30,
        indicators=["sma", "rsi"],
        combinable_with=["volume", "confirmation"],
        strategy_type="TEX",
    ),
    # Overextended down with momentum divergence
    PatternBlock(
        id="OVEREXT_DOWN_DIV",
        name="Overextended Down with Divergence",
        category="trend_exhaustion_ext",
        formula_template="""df['ma'] = ta.SMA(df['close'], timeperiod={period})
df['distance'] = (df['close'] - df['ma']) / df['ma'] * 100
df['overext'] = df['distance'] < -{dist_thresh}
df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['rsi_div'] = df['rsi'] > df['rsi'].shift(5)
df['entry_signal'] = df['overext'] & df['rsi_div']""",
        params={"period": [20], "dist_thresh": [3, 5]},
        direction="long",
        lookback=30,
        indicators=["sma", "rsi"],
        combinable_with=["volume", "confirmation"],
        strategy_type="TEX",
    ),
    # Parabolic exhaustion
    PatternBlock(
        id="PARABOLIC_EXHAUST",
        name="Parabolic Exhaustion",
        category="trend_exhaustion_ext",
        formula_template="""df['ret_5'] = (df['close'] - df['close'].shift(5)) / df['close'].shift(5) * 100
df['ret_10'] = (df['close'] - df['close'].shift(10)) / df['close'].shift(10) * 100
df['parabolic'] = df['ret_5'] > df['ret_10'] * {accel}
df['extended'] = df['ret_5'] > {threshold}
df['entry_signal'] = df['parabolic'] & df['extended']""",
        params={"accel": [0.7, 0.8], "threshold": [5, 7]},
        direction="short",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="TEX",
    ),
]


# =============================================================================
# REVERSAL CANDLESTICK EXTENDED BLOCKS
# =============================================================================

REVERSAL_CANDLE_EXT_BLOCKS = [
    # Pinbar at support
    PatternBlock(
        id="PINBAR_SUPPORT",
        name="Pinbar at Support",
        category="reversal_candle_ext",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['lower_wick'] = df[['close', 'open']].min(axis=1) - df['low']
df['range'] = df['high'] - df['low']
df['pinbar'] = (df['lower_wick'] / df['range'] > {wick_ratio}) & (df['body'] / df['range'] < 0.3)
df['at_support'] = df['low'] <= df['low'].rolling({period}).min().shift(1) * 1.01
df['entry_signal'] = df['pinbar'] & df['at_support']""",
        params={"wick_ratio": [0.6, 0.7], "period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="RCE",
    ),
    # Pinbar at resistance
    PatternBlock(
        id="PINBAR_RESISTANCE",
        name="Pinbar at Resistance",
        category="reversal_candle_ext",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['upper_wick'] = df['high'] - df[['close', 'open']].max(axis=1)
df['range'] = df['high'] - df['low']
df['pinbar'] = (df['upper_wick'] / df['range'] > {wick_ratio}) & (df['body'] / df['range'] < 0.3)
df['at_resistance'] = df['high'] >= df['high'].rolling({period}).max().shift(1) * 0.99
df['entry_signal'] = df['pinbar'] & df['at_resistance']""",
        params={"wick_ratio": [0.6, 0.7], "period": [20]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="RCE",
    ),
    # Engulfing with trend context
    PatternBlock(
        id="ENGULF_TREND_CONTEXT",
        name="Engulfing with Trend Context",
        category="reversal_candle_ext",
        formula_template="""df['body_curr'] = abs(df['close'] - df['open'])
df['body_prev'] = abs(df['close'].shift(1) - df['open'].shift(1))
df['engulf'] = (df['body_curr'] > df['body_prev']) & (df['close'] > df['open']) & (df['close'].shift(1) < df['open'].shift(1))
df['downtrend'] = df['close'].shift(1) < df['close'].shift({period})
df['entry_signal'] = df['engulf'] & df['downtrend']""",
        params={"period": [10, 20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="RCE",
    ),
    # Three bar reversal setup
    PatternBlock(
        id="THREE_BAR_REVERSAL",
        name="Three Bar Reversal",
        category="reversal_candle_ext",
        formula_template="""df['bar1_down'] = df['close'].shift(2) < df['open'].shift(2)
df['bar2_small'] = abs(df['close'].shift(1) - df['open'].shift(1)) < abs(df['close'].shift(2) - df['open'].shift(2)) * 0.5
df['bar3_up'] = (df['close'] > df['open']) & (df['close'] > df['high'].shift(1))
df['entry_signal'] = df['bar1_down'] & df['bar2_small'] & df['bar3_up']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="RCE",
    ),
]


# =============================================================================
# MA CONVERGENCE BLOCKS
# =============================================================================

MA_CONVERGENCE_BLOCKS = [
    # MA squeeze (convergence)
    PatternBlock(
        id="MA_SQUEEZE",
        name="MA Squeeze",
        category="ma_convergence",
        formula_template="""df['ma_fast'] = ta.SMA(df['close'], timeperiod={fast})
df['ma_slow'] = ta.SMA(df['close'], timeperiod={slow})
df['spread'] = abs(df['ma_fast'] - df['ma_slow']) / df['close'] * 100
df['spread_avg'] = df['spread'].rolling({avg_period}).mean()
df['squeeze'] = df['spread'] < df['spread_avg'] * {mult}
df['entry_signal'] = df['squeeze']""",
        params={"fast": [10], "slow": [30], "avg_period": [20], "mult": [0.5, 0.7]},
        direction="bidi",
        lookback=40,
        indicators=["sma"],
        combinable_with=["threshold", "momentum"],
        strategy_type="MAC",
    ),
    # MA expansion (divergence)
    PatternBlock(
        id="MA_EXPANSION",
        name="MA Expansion",
        category="ma_convergence",
        formula_template="""df['ma_fast'] = ta.SMA(df['close'], timeperiod={fast})
df['ma_slow'] = ta.SMA(df['close'], timeperiod={slow})
df['spread'] = (df['ma_fast'] - df['ma_slow']) / df['close'] * 100
df['spread_prev'] = df['spread'].shift(1)
df['expanding'] = df['spread'] > df['spread_prev']
df['bullish'] = df['spread'] > 0
df['entry_signal'] = df['expanding'] & df['bullish']""",
        params={"fast": [10], "slow": [30]},
        direction="long",
        lookback=40,
        indicators=["sma"],
        combinable_with=["volume", "momentum"],
        strategy_type="MAC",
    ),
    # Price touch converged MAs
    PatternBlock(
        id="MA_CONVERGE_TOUCH",
        name="Price Touch Converged MAs",
        category="ma_convergence",
        formula_template="""df['ma_fast'] = ta.SMA(df['close'], timeperiod={fast})
df['ma_slow'] = ta.SMA(df['close'], timeperiod={slow})
df['spread'] = abs(df['ma_fast'] - df['ma_slow']) / df['close'] * 100
df['converged'] = df['spread'] < {spread_thresh}
df['ma_mid'] = (df['ma_fast'] + df['ma_slow']) / 2
df['touch'] = abs(df['close'] - df['ma_mid']) / df['close'] * 100 < {touch_thresh}
df['entry_signal'] = df['converged'] & df['touch']""",
        params={"fast": [10], "slow": [30], "spread_thresh": [0.5], "touch_thresh": [0.3]},
        direction="bidi",
        lookback=40,
        indicators=["sma"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MAC",
    ),
]


# =============================================================================
# PRICE RATIO BLOCKS
# =============================================================================

PRICE_RATIO_BLOCKS = [
    # High/Low ratio extreme (wide range)
    PatternBlock(
        id="HL_RATIO_WIDE",
        name="High Low Ratio Wide",
        category="price_ratio",
        formula_template="""df['hl_ratio'] = df['high'] / df['low']
df['ratio_avg'] = df['hl_ratio'].rolling({period}).mean()
df['wide_range'] = df['hl_ratio'] > df['ratio_avg'] * {mult}
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['wide_range'] & df['bullish']""",
        params={"period": [20], "mult": [1.3, 1.5]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="PRT",
    ),
    # Body/Range ratio (strong conviction)
    PatternBlock(
        id="BODY_RANGE_STRONG",
        name="Strong Body Range Ratio",
        category="price_ratio",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['range'] = df['high'] - df['low']
df['body_ratio'] = df['body'] / df['range']
df['strong_body'] = df['body_ratio'] > {threshold}
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['strong_body'] & df['bullish']""",
        params={"threshold": [0.7, 0.8]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "threshold", "momentum"],
        strategy_type="PRT",
    ),
    # Close/Open ratio (gap fill potential)
    PatternBlock(
        id="CLOSE_OPEN_GAP",
        name="Close Open Gap Ratio",
        category="price_ratio",
        formula_template="""df['gap_ratio'] = df['open'] / df['close'].shift(1)
df['gap_up'] = df['gap_ratio'] > (1 + {gap_thresh})
df['fills'] = df['close'] < df['open']
df['entry_signal'] = df['gap_up'] & df['fills']""",
        params={"gap_thresh": [0.005, 0.01]},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PRT",
    ),
]


# =============================================================================
# STRUCTURE BREAK BLOCKS
# =============================================================================

STRUCTURE_BREAK_BLOCKS = [
    # Break of Structure Up (BOS)
    PatternBlock(
        id="BOS_UP",
        name="Break of Structure Up",
        category="structure_break",
        formula_template="""df['swing_high'] = df['high'].rolling({period}).max().shift(1)
df['break'] = df['close'] > df['swing_high']
df['strong_break'] = df['close'] > df['swing_high'] * (1 + {margin})
df['entry_signal'] = df['strong_break']""",
        params={"period": [10, 20], "margin": [0.001, 0.002]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum", "confirmation"],
        strategy_type="STB",
    ),
    # Break of Structure Down (BOS)
    PatternBlock(
        id="BOS_DOWN",
        name="Break of Structure Down",
        category="structure_break",
        formula_template="""df['swing_low'] = df['low'].rolling({period}).min().shift(1)
df['break'] = df['close'] < df['swing_low']
df['strong_break'] = df['close'] < df['swing_low'] * (1 - {margin})
df['entry_signal'] = df['strong_break']""",
        params={"period": [10, 20], "margin": [0.001, 0.002]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum", "confirmation"],
        strategy_type="STB",
    ),
    # Change of Character (CHoCH)
    PatternBlock(
        id="CHOCH_BULL",
        name="Change of Character Bullish",
        category="structure_break",
        formula_template="""df['prev_low'] = df['low'].rolling({period}).min()
df['made_lower_low'] = df['low'] < df['prev_low'].shift(1)
df['now_higher_high'] = df['high'] > df['high'].shift(1)
df['reversal'] = df['made_lower_low'].shift(1) & df['now_higher_high']
df['entry_signal'] = df['reversal']""",
        params={"period": [10, 20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="STB",
    ),
]


# =============================================================================
# IMPULSE CORRECTION BLOCKS
# =============================================================================

IMPULSE_CORRECTION_BLOCKS = [
    # Impulse move followed by pullback
    PatternBlock(
        id="IMPULSE_PULLBACK_BULL",
        name="Bullish Impulse Pullback",
        category="impulse_correction",
        formula_template="""df['impulse_move'] = df['close'].shift({pullback}) - df['close'].shift({impulse})
df['impulse_pct'] = df['impulse_move'] / df['close'].shift({impulse}) * 100
df['had_impulse'] = df['impulse_pct'] > {imp_thresh}
df['pullback'] = df['close'] < df['close'].shift({pullback})
df['entry_signal'] = df['had_impulse'] & df['pullback']""",
        params={"impulse": [10], "pullback": [3], "imp_thresh": [3, 5]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="IMP",
    ),
    # Impulse continuation
    PatternBlock(
        id="IMPULSE_CONTINUE",
        name="Impulse Continuation",
        category="impulse_correction",
        formula_template="""df['move_5'] = (df['close'] - df['close'].shift(5)) / df['close'].shift(5) * 100
df['move_1'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
df['impulse'] = df['move_5'] > {threshold}
df['continues'] = df['move_1'] > 0
df['entry_signal'] = df['impulse'] & df['continues']""",
        params={"threshold": [3, 5]},
        direction="long",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="IMP",
    ),
    # Correction complete (price resumes)
    PatternBlock(
        id="CORRECTION_COMPLETE",
        name="Correction Complete",
        category="impulse_correction",
        formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
df['swing_low'] = df['low'].rolling({period}).min()
df['retrace'] = (df['swing_high'] - df['close']) / (df['swing_high'] - df['swing_low'])
df['was_retracing'] = df['retrace'].shift(1) > {retrace_level}
df['resuming'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['was_retracing'] & df['resuming']""",
        params={"period": [20], "retrace_level": [0.4, 0.5]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="IMP",
    ),
]


# =============================================================================
# FRACTAL BLOCKS - Williams Fractals
# =============================================================================

FRACTAL_BLOCKS = [
    # Fractal High (bearish fractal)
    PatternBlock(
        id="FRACTAL_HIGH",
        name="Fractal High Formed",
        category="fractal",
        formula_template="""df['mid_high'] = df['high'].shift(2)
df['left1'] = df['high'].shift(3) < df['mid_high']
df['left2'] = df['high'].shift(4) < df['mid_high']
df['right1'] = df['high'].shift(1) < df['mid_high']
df['right2'] = df['high'] < df['mid_high']
df['fractal_high'] = df['left1'] & df['left2'] & df['right1'] & df['right2']
df['entry_signal'] = df['fractal_high']""",
        params={},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation", "momentum"],
        strategy_type="FRC",
    ),
    # Fractal Low (bullish fractal)
    PatternBlock(
        id="FRACTAL_LOW",
        name="Fractal Low Formed",
        category="fractal",
        formula_template="""df['mid_low'] = df['low'].shift(2)
df['left1'] = df['low'].shift(3) > df['mid_low']
df['left2'] = df['low'].shift(4) > df['mid_low']
df['right1'] = df['low'].shift(1) > df['mid_low']
df['right2'] = df['low'] > df['mid_low']
df['fractal_low'] = df['left1'] & df['left2'] & df['right1'] & df['right2']
df['entry_signal'] = df['fractal_low']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation", "momentum"],
        strategy_type="FRC",
    ),
    # Fractal Breakout
    PatternBlock(
        id="FRACTAL_BREAKOUT",
        name="Fractal Breakout",
        category="fractal",
        formula_template="""df['mid_high'] = df['high'].shift(2)
df['fh_left1'] = df['high'].shift(3) < df['mid_high']
df['fh_right1'] = df['high'].shift(1) < df['mid_high']
df['fractal_high'] = df['fh_left1'] & df['fh_right1']
df['last_fractal'] = df['mid_high'].where(df['fractal_high']).ffill()
df['breakout'] = df['close'] > df['last_fractal'] * (1 + {margin})
df['entry_signal'] = df['breakout']""",
        params={"margin": [0.001, 0.002]},
        direction="long",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="FRC",
    ),
]


# =============================================================================
# VOLUME PROFILE BLOCKS
# =============================================================================

VOLUME_PROFILE_BLOCKS = [
    # High Volume Node
    PatternBlock(
        id="HIGH_VOLUME_NODE",
        name="High Volume Node",
        category="volume_profile",
        formula_template="""df['vol_ma'] = df['volume'].rolling({period}).mean()
df['vol_std'] = df['volume'].rolling({period}).std()
df['high_vol'] = df['volume'] > df['vol_ma'] + df['vol_std'] * {mult}
df['price_stable'] = abs(df['close'] - df['close'].shift(1)) / df['close'] < 0.005
df['entry_signal'] = df['high_vol'] & df['price_stable']""",
        params={"period": [20, 50], "mult": [1.5, 2.0]},
        direction="bidi",
        lookback=60,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="VPR",
    ),
    # Volume Climax at Support
    PatternBlock(
        id="VOL_CLIMAX_SUPPORT",
        name="Volume Climax at Support",
        category="volume_profile",
        formula_template="""df['vol_rank'] = df['volume'].rolling({period}).apply(lambda x: (x[-1] - x.min()) / (x.max() - x.min() + 1e-10), raw=True)
df['price_low'] = df['low'] <= df['low'].rolling({period}).min() * 1.01
df['vol_extreme'] = df['vol_rank'] > {vol_thresh}
df['entry_signal'] = df['vol_extreme'] & df['price_low']""",
        params={"period": [20], "vol_thresh": [0.8, 0.9]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["confirmation", "momentum"],
        strategy_type="VPR",
    ),
    # Low Volume Breakout Setup
    PatternBlock(
        id="LOW_VOL_BREAKOUT_SETUP",
        name="Low Volume Breakout Setup",
        category="volume_profile",
        formula_template="""df['vol_ma'] = df['volume'].rolling({period}).mean()
df['low_vol'] = df['volume'] < df['vol_ma'] * {low_mult}
df['low_vol_days'] = df['low_vol'].rolling(3).sum() >= 2
df['range_tight'] = (df['high'].rolling(3).max() - df['low'].rolling(3).min()) / df['close'] < 0.02
df['entry_signal'] = df['low_vol_days'] & df['range_tight']""",
        params={"period": [20], "low_mult": [0.5, 0.7]},
        direction="bidi",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="VPR",
    ),
]


# =============================================================================
# ZIGZAG BLOCKS
# =============================================================================

ZIGZAG_BLOCKS = [
    # ZigZag Swing Low
    PatternBlock(
        id="ZIGZAG_SWING_LOW",
        name="ZigZag Swing Low",
        category="zigzag",
        formula_template="""df['swing_low'] = df['low'].rolling({period}).min()
df['is_swing'] = df['low'] == df['swing_low']
df['swing_confirmed'] = df['is_swing'].shift({confirm}) & (df['close'] > df['low'].shift({confirm}))
df['entry_signal'] = df['swing_confirmed']""",
        params={"period": [10, 20], "confirm": [2, 3]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum", "confirmation"],
        strategy_type="ZZG",
    ),
    # ZigZag Swing High
    PatternBlock(
        id="ZIGZAG_SWING_HIGH",
        name="ZigZag Swing High",
        category="zigzag",
        formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
df['is_swing'] = df['high'] == df['swing_high']
df['swing_confirmed'] = df['is_swing'].shift({confirm}) & (df['close'] < df['high'].shift({confirm}))
df['entry_signal'] = df['swing_confirmed']""",
        params={"period": [10, 20], "confirm": [2, 3]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum", "confirmation"],
        strategy_type="ZZG",
    ),
    # ZigZag Higher Low
    PatternBlock(
        id="ZIGZAG_HIGHER_LOW",
        name="ZigZag Higher Low",
        category="zigzag",
        formula_template="""df['swing_low'] = df['low'].rolling({period}).min()
df['prev_swing'] = df['swing_low'].shift({period})
df['higher_low'] = df['swing_low'] > df['prev_swing']
df['confirmed'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['higher_low'] & df['confirmed']""",
        params={"period": [10, 15]},
        direction="long",
        lookback=40,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="ZZG",
    ),
]


# =============================================================================
# VORTEX BLOCKS
# =============================================================================

VORTEX_BLOCKS = [
    # Vortex Bullish Cross
    PatternBlock(
        id="VORTEX_BULL_CROSS",
        name="Vortex Bullish Cross",
        category="vortex",
        formula_template="""df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
df['vmp'] = abs(df['high'] - df['low'].shift(1))
df['vmm'] = abs(df['low'] - df['high'].shift(1))
df['vmp_sum'] = df['vmp'].rolling({period}).sum()
df['vmm_sum'] = df['vmm'].rolling({period}).sum()
df['tr_sum'] = df['tr'].rolling({period}).sum()
df['vip'] = df['vmp_sum'] / df['tr_sum']
df['vim'] = df['vmm_sum'] / df['tr_sum']
df['cross_up'] = (df['vip'] > df['vim']) & (df['vip'].shift(1) <= df['vim'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [14, 21]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="VTX",
    ),
    # Vortex Bearish Cross
    PatternBlock(
        id="VORTEX_BEAR_CROSS",
        name="Vortex Bearish Cross",
        category="vortex",
        formula_template="""df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
df['vmp'] = abs(df['high'] - df['low'].shift(1))
df['vmm'] = abs(df['low'] - df['high'].shift(1))
df['vmp_sum'] = df['vmp'].rolling({period}).sum()
df['vmm_sum'] = df['vmm'].rolling({period}).sum()
df['tr_sum'] = df['tr'].rolling({period}).sum()
df['vip'] = df['vmp_sum'] / df['tr_sum']
df['vim'] = df['vmm_sum'] / df['tr_sum']
df['cross_down'] = (df['vip'] < df['vim']) & (df['vip'].shift(1) >= df['vim'].shift(1))
df['entry_signal'] = df['cross_down']""",
        params={"period": [14, 21]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold", "confirmation"],
        strategy_type="VTX",
    ),
    # Vortex Strong Trend
    PatternBlock(
        id="VORTEX_STRONG_TREND",
        name="Vortex Strong Trend",
        category="vortex",
        formula_template="""df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
df['vmp'] = abs(df['high'] - df['low'].shift(1))
df['vmm'] = abs(df['low'] - df['high'].shift(1))
df['vmp_sum'] = df['vmp'].rolling({period}).sum()
df['vmm_sum'] = df['vmm'].rolling({period}).sum()
df['tr_sum'] = df['tr'].rolling({period}).sum()
df['vip'] = df['vmp_sum'] / df['tr_sum']
df['vim'] = df['vmm_sum'] / df['tr_sum']
df['strong_bull'] = (df['vip'] - df['vim']) > {threshold}
df['entry_signal'] = df['strong_bull']""",
        params={"period": [14], "threshold": [0.2, 0.3]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VTX",
    ),
]


# =============================================================================
# MASS INDEX BLOCKS
# =============================================================================

MASS_INDEX_BLOCKS = [
    # Mass Index Reversal Bulge
    PatternBlock(
        id="MASS_INDEX_BULGE",
        name="Mass Index Reversal Bulge",
        category="mass_index",
        formula_template="""df['range'] = df['high'] - df['low']
df['ema_range'] = ta.EMA(df['range'], timeperiod=9)
df['double_ema'] = ta.EMA(df['ema_range'], timeperiod=9)
df['ratio'] = df['ema_range'] / (df['double_ema'] + 1e-10)
df['mass'] = df['ratio'].rolling(25).sum()
df['bulge'] = (df['mass'].shift(1) > {upper}) & (df['mass'] < {upper})
df['entry_signal'] = df['bulge']""",
        params={"upper": [26.5, 27.0]},
        direction="bidi",
        lookback=50,
        indicators=["EMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="MAS",
    ),
    # Mass Index Low (trending)
    PatternBlock(
        id="MASS_INDEX_LOW",
        name="Mass Index Low Trend",
        category="mass_index",
        formula_template="""df['range'] = df['high'] - df['low']
df['ema_range'] = ta.EMA(df['range'], timeperiod=9)
df['double_ema'] = ta.EMA(df['ema_range'], timeperiod=9)
df['ratio'] = df['ema_range'] / (df['double_ema'] + 1e-10)
df['mass'] = df['ratio'].rolling(25).sum()
df['low_mass'] = df['mass'] < {lower}
df['uptrend'] = df['close'] > df['close'].shift(5)
df['entry_signal'] = df['low_mass'] & df['uptrend']""",
        params={"lower": [24.0, 24.5]},
        direction="long",
        lookback=50,
        indicators=["EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="MAS",
    ),
    # Mass Index Setup (before reversal)
    PatternBlock(
        id="MASS_INDEX_SETUP",
        name="Mass Index Setup",
        category="mass_index",
        formula_template="""df['range'] = df['high'] - df['low']
df['ema_range'] = ta.EMA(df['range'], timeperiod=9)
df['double_ema'] = ta.EMA(df['ema_range'], timeperiod=9)
df['ratio'] = df['ema_range'] / (df['double_ema'] + 1e-10)
df['mass'] = df['ratio'].rolling(25).sum()
df['rising'] = df['mass'] > df['mass'].shift(1)
df['near_bulge'] = df['mass'] > {trigger}
df['entry_signal'] = df['rising'] & df['near_bulge']""",
        params={"trigger": [25.5, 26.0]},
        direction="bidi",
        lookback=50,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MAS",
    ),
]


# =============================================================================
# CONNORS RSI BLOCKS
# =============================================================================

CONNORS_RSI_BLOCKS = [
    # Connors RSI Oversold
    PatternBlock(
        id="CONNORS_RSI_OVERSOLD",
        name="Connors RSI Oversold",
        category="connors_rsi",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=3)
df['streak'] = (df['close'] > df['close'].shift(1)).astype(int)
df['streak'] = df['streak'].replace(0, -1)
df['streak_count'] = df['streak'].groupby((df['streak'] != df['streak'].shift()).cumsum()).cumcount() + 1
df['streak_count'] = df['streak_count'] * df['streak']
df['roc'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
df['roc_rank'] = df['roc'].rolling({period}).apply(lambda x: (x < x[-1]).sum() / len(x) * 100, raw=True)
df['crsi'] = (df['rsi'] + df['roc_rank'] + 50) / 3
df['oversold'] = df['crsi'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"period": [100], "level": [15, 20]},
        direction="long",
        lookback=120,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="CRS",
    ),
    # Connors RSI Overbought
    PatternBlock(
        id="CONNORS_RSI_OVERBOUGHT",
        name="Connors RSI Overbought",
        category="connors_rsi",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=3)
df['streak'] = (df['close'] > df['close'].shift(1)).astype(int)
df['streak'] = df['streak'].replace(0, -1)
df['streak_count'] = df['streak'].groupby((df['streak'] != df['streak'].shift()).cumsum()).cumcount() + 1
df['streak_count'] = df['streak_count'] * df['streak']
df['roc'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
df['roc_rank'] = df['roc'].rolling({period}).apply(lambda x: (x < x[-1]).sum() / len(x) * 100, raw=True)
df['crsi'] = (df['rsi'] + df['roc_rank'] + 50) / 3
df['overbought'] = df['crsi'] > {level}
df['entry_signal'] = df['overbought']""",
        params={"period": [100], "level": [80, 85]},
        direction="short",
        lookback=120,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="CRS",
    ),
    # Connors RSI Mean Reversion
    PatternBlock(
        id="CONNORS_RSI_MEAN_REV",
        name="Connors RSI Mean Reversion",
        category="connors_rsi",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=3)
df['roc'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
df['roc_rank'] = df['roc'].rolling({period}).apply(lambda x: (x < x[-1]).sum() / len(x) * 100, raw=True)
df['crsi'] = (df['rsi'] + df['roc_rank'] + 50) / 3
df['was_oversold'] = df['crsi'].shift(1) < {low}
df['recovering'] = df['crsi'] > df['crsi'].shift(1)
df['entry_signal'] = df['was_oversold'] & df['recovering']""",
        params={"period": [100], "low": [20, 25]},
        direction="long",
        lookback=120,
        indicators=["RSI"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="CRS",
    ),
]


# =============================================================================
# SQUEEZE BLOCKS - Bollinger inside Keltner
# =============================================================================

SQUEEZE_BLOCKS = [
    # Squeeze On (low volatility)
    PatternBlock(
        id="SQUEEZE_ON",
        name="Squeeze On",
        category="squeeze",
        formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod={period}, nbdevup=2, nbdevdn=2)
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['kc_upper'] = ta.EMA(df['close'], timeperiod={period}) + df['atr'] * 1.5
df['kc_lower'] = ta.EMA(df['close'], timeperiod={period}) - df['atr'] * 1.5
df['squeeze_on'] = (df['bb_lower'] > df['kc_lower']) & (df['bb_upper'] < df['kc_upper'])
df['entry_signal'] = df['squeeze_on'] & ~df['squeeze_on'].shift(1)""",
        params={"period": [20]},
        direction="bidi",
        lookback=30,
        indicators=["BBANDS", "ATR", "EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="SQZ",
    ),
    # Squeeze Fire Long
    PatternBlock(
        id="SQUEEZE_FIRE_LONG",
        name="Squeeze Fire Long",
        category="squeeze",
        formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod={period}, nbdevup=2, nbdevdn=2)
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['kc_upper'] = ta.EMA(df['close'], timeperiod={period}) + df['atr'] * 1.5
df['kc_lower'] = ta.EMA(df['close'], timeperiod={period}) - df['atr'] * 1.5
df['squeeze_on'] = (df['bb_lower'] > df['kc_lower']) & (df['bb_upper'] < df['kc_upper'])
df['squeeze_off'] = ~df['squeeze_on'] & df['squeeze_on'].shift(1)
df['mom'] = df['close'] - ta.SMA(df['close'], timeperiod={period})
df['mom_up'] = df['mom'] > 0
df['entry_signal'] = df['squeeze_off'] & df['mom_up']""",
        params={"period": [20]},
        direction="long",
        lookback=35,
        indicators=["BBANDS", "ATR", "EMA", "SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="SQZ",
    ),
    # Squeeze Fire Short
    PatternBlock(
        id="SQUEEZE_FIRE_SHORT",
        name="Squeeze Fire Short",
        category="squeeze",
        formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod={period}, nbdevup=2, nbdevdn=2)
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['kc_upper'] = ta.EMA(df['close'], timeperiod={period}) + df['atr'] * 1.5
df['kc_lower'] = ta.EMA(df['close'], timeperiod={period}) - df['atr'] * 1.5
df['squeeze_on'] = (df['bb_lower'] > df['kc_lower']) & (df['bb_upper'] < df['kc_upper'])
df['squeeze_off'] = ~df['squeeze_on'] & df['squeeze_on'].shift(1)
df['mom'] = df['close'] - ta.SMA(df['close'], timeperiod={period})
df['mom_down'] = df['mom'] < 0
df['entry_signal'] = df['squeeze_off'] & df['mom_down']""",
        params={"period": [20]},
        direction="short",
        lookback=35,
        indicators=["BBANDS", "ATR", "EMA", "SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="SQZ",
    ),
]


# =============================================================================
# PRICE TRANSFORM BLOCKS
# =============================================================================

PRICE_TRANSFORM_BLOCKS = [
    # Log Return Extreme
    PatternBlock(
        id="LOG_RETURN_EXTREME",
        name="Log Return Extreme",
        category="price_transform",
        formula_template="""df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
df['log_ret_std'] = df['log_ret'].rolling({period}).std()
df['extreme_neg'] = df['log_ret'] < -df['log_ret_std'] * {mult}
df['entry_signal'] = df['extreme_neg']""",
        params={"period": [20], "mult": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PTR",
    ),
    # Normalized Price Level
    PatternBlock(
        id="NORMALIZED_PRICE_LOW",
        name="Normalized Price Low",
        category="price_transform",
        formula_template="""df['price_max'] = df['close'].rolling({period}).max()
df['price_min'] = df['close'].rolling({period}).min()
df['norm_price'] = (df['close'] - df['price_min']) / (df['price_max'] - df['price_min'] + 1e-10)
df['low_norm'] = df['norm_price'] < {level}
df['entry_signal'] = df['low_norm']""",
        params={"period": [50, 100], "level": [0.1, 0.2]},
        direction="long",
        lookback=110,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="PTR",
    ),
    # Price Z-Score Extreme
    PatternBlock(
        id="PRICE_ZSCORE_EXTREME",
        name="Price Z-Score Extreme",
        category="price_transform",
        formula_template="""df['price_ma'] = df['close'].rolling({period}).mean()
df['price_std'] = df['close'].rolling({period}).std()
df['zscore'] = (df['close'] - df['price_ma']) / (df['price_std'] + 1e-10)
df['extreme_low'] = df['zscore'] < -{threshold}
df['entry_signal'] = df['extreme_low']""",
        params={"period": [20, 50], "threshold": [2.0, 2.5]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PTR",
    ),
]


# =============================================================================
# ADAPTIVE CHANNEL BLOCKS
# =============================================================================

ADAPTIVE_CHANNEL_BLOCKS = [
    # Adaptive Channel Breakout
    PatternBlock(
        id="ADAPTIVE_CHANNEL_BREAK_UP",
        name="Adaptive Channel Breakout Up",
        category="adaptive_channel",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['mid'] = ta.EMA(df['close'], timeperiod={period})
df['upper'] = df['mid'] + df['atr'] * {mult}
df['lower'] = df['mid'] - df['atr'] * {mult}
df['breakout'] = (df['close'] > df['upper']) & (df['close'].shift(1) <= df['upper'].shift(1))
df['entry_signal'] = df['breakout']""",
        params={"period": [20], "mult": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=["ATR", "EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="ACH",
    ),
    # Adaptive Channel Bounce
    PatternBlock(
        id="ADAPTIVE_CHANNEL_BOUNCE",
        name="Adaptive Channel Bounce",
        category="adaptive_channel",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['mid'] = ta.EMA(df['close'], timeperiod={period})
df['lower'] = df['mid'] - df['atr'] * {mult}
df['at_lower'] = df['low'] <= df['lower'] * 1.01
df['bounce'] = df['close'] > df['open']
df['entry_signal'] = df['at_lower'] & df['bounce']""",
        params={"period": [20], "mult": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=["ATR", "EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="ACH",
    ),
    # Adaptive Channel Width Expansion
    PatternBlock(
        id="ADAPTIVE_CHANNEL_EXPAND",
        name="Adaptive Channel Expansion",
        category="adaptive_channel",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['atr_ma'] = df['atr'].rolling({period}).mean()
df['expansion'] = df['atr'] > df['atr_ma'] * {mult}
df['uptrend'] = df['close'] > ta.EMA(df['close'], timeperiod={period})
df['entry_signal'] = df['expansion'] & df['uptrend']""",
        params={"period": [14], "mult": [1.3, 1.5]},
        direction="long",
        lookback=30,
        indicators=["ATR", "EMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="ACH",
    ),
]


# =============================================================================
# MOMENTUM QUALITY BLOCKS
# =============================================================================

MOMENTUM_QUALITY_BLOCKS = [
    # Smooth Momentum
    PatternBlock(
        id="SMOOTH_MOMENTUM",
        name="Smooth Momentum",
        category="momentum_quality",
        formula_template="""df['mom'] = df['close'] - df['close'].shift({period})
df['mom_smooth'] = ta.EMA(df['mom'], timeperiod=5)
df['mom_diff'] = abs(df['mom'] - df['mom_smooth'])
df['smooth_ratio'] = df['mom_diff'].rolling(10).mean() / (abs(df['mom']).rolling(10).mean() + 1e-10)
df['is_smooth'] = df['smooth_ratio'] < {threshold}
df['positive_mom'] = df['mom_smooth'] > 0
df['entry_signal'] = df['is_smooth'] & df['positive_mom']""",
        params={"period": [10, 20], "threshold": [0.3, 0.4]},
        direction="long",
        lookback=40,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MQU",
    ),
    # Accelerating Momentum
    PatternBlock(
        id="ACCEL_MOMENTUM",
        name="Accelerating Momentum",
        category="momentum_quality",
        formula_template="""df['mom'] = df['close'] - df['close'].shift({period})
df['mom_accel'] = df['mom'] - df['mom'].shift(3)
df['accel_positive'] = df['mom_accel'] > 0
df['mom_positive'] = df['mom'] > 0
df['increasing'] = df['mom_accel'] > df['mom_accel'].shift(1)
df['entry_signal'] = df['accel_positive'] & df['mom_positive'] & df['increasing']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="MQU",
    ),
    # Momentum Divergence Quality
    PatternBlock(
        id="MOM_DIVERGENCE_QUALITY",
        name="Momentum Divergence Quality",
        category="momentum_quality",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['price_lower'] = df['close'] < df['close'].shift(5)
df['rsi_higher'] = df['rsi'] > df['rsi'].shift(5)
df['divergence'] = df['price_lower'] & df['rsi_higher']
df['rsi_recovering'] = df['rsi'] > df['rsi'].shift(1)
df['entry_signal'] = df['divergence'] & df['rsi_recovering']""",
        params={"period": [14]},
        direction="long",
        lookback=30,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MQU",
    ),
    # Consistent Momentum
    PatternBlock(
        id="CONSISTENT_MOMENTUM",
        name="Consistent Momentum",
        category="momentum_quality",
        formula_template="""df['ret'] = df['close'].pct_change()
df['positive'] = df['ret'] > 0
df['pos_count'] = df['positive'].rolling({period}).sum()
df['consistency'] = df['pos_count'] / {period}
df['high_consistency'] = df['consistency'] > {threshold}
df['still_positive'] = df['ret'] > 0
df['entry_signal'] = df['high_consistency'] & df['still_positive']""",
        params={"period": [10, 20], "threshold": [0.65, 0.7]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="MQU",
    ),
]


# =============================================================================
# PSAR EXTENDED BLOCKS
# =============================================================================

PSAR_EXTENDED_BLOCKS = [
    # PSAR Flip Long
    PatternBlock(
        id="PSAR_FLIP_LONG",
        name="PSAR Flip to Long",
        category="psar_extended",
        formula_template="""df['sar'] = ta.SAR(df['high'], df['low'], acceleration={accel}, maximum={max_accel})
df['sar_below'] = df['sar'] < df['close']
df['sar_was_above'] = df['sar'].shift(1) > df['close'].shift(1)
df['flip_long'] = df['sar_below'] & df['sar_was_above']
df['entry_signal'] = df['flip_long']""",
        params={"accel": [0.02], "max_accel": [0.2]},
        direction="long",
        lookback=20,
        indicators=["SAR"],
        combinable_with=["volume", "momentum", "confirmation"],
        strategy_type="PSE",
    ),
    # PSAR Proximity
    PatternBlock(
        id="PSAR_PROXIMITY",
        name="PSAR Proximity",
        category="psar_extended",
        formula_template="""df['sar'] = ta.SAR(df['high'], df['low'], acceleration={accel}, maximum={max_accel})
df['sar_below'] = df['sar'] < df['close']
df['distance'] = (df['close'] - df['sar']) / df['close']
df['close_to_sar'] = df['distance'] < {proximity}
df['uptrend'] = df['sar_below']
df['entry_signal'] = df['close_to_sar'] & df['uptrend']""",
        params={"accel": [0.02], "max_accel": [0.2], "proximity": [0.01, 0.015]},
        direction="long",
        lookback=20,
        indicators=["SAR"],
        combinable_with=["volume", "confirmation"],
        strategy_type="PSE",
    ),
    # PSAR Acceleration Zone
    PatternBlock(
        id="PSAR_ACCEL_ZONE",
        name="PSAR Acceleration Zone",
        category="psar_extended",
        formula_template="""df['sar'] = ta.SAR(df['high'], df['low'], acceleration={accel}, maximum={max_accel})
df['sar_below'] = df['sar'] < df['close']
df['sar_change'] = df['sar'] - df['sar'].shift(1)
df['accelerating'] = df['sar_change'] > df['sar_change'].shift(1)
df['strong_accel'] = df['accelerating'].rolling(3).sum() >= 2
df['entry_signal'] = df['strong_accel'] & df['sar_below']""",
        params={"accel": [0.02], "max_accel": [0.2]},
        direction="long",
        lookback=25,
        indicators=["SAR"],
        combinable_with=["momentum", "threshold"],
        strategy_type="PSE",
    ),
]


# =============================================================================
# CUMULATIVE DELTA BLOCKS (proxy via volume/price)
# =============================================================================

CUMULATIVE_DELTA_BLOCKS = [
    # Volume Delta Positive
    PatternBlock(
        id="VOL_DELTA_POSITIVE",
        name="Volume Delta Positive",
        category="cumulative_delta",
        formula_template="""df['price_up'] = df['close'] > df['open']
df['delta'] = np.where(df['price_up'], df['volume'], -df['volume'])
df['cum_delta'] = df['delta'].rolling({period}).sum()
df['delta_positive'] = df['cum_delta'] > 0
df['delta_rising'] = df['cum_delta'] > df['cum_delta'].shift(1)
df['entry_signal'] = df['delta_positive'] & df['delta_rising']""",
        params={"period": [10, 20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="CDL",
    ),
    # Volume Delta Divergence
    PatternBlock(
        id="VOL_DELTA_DIVERGENCE",
        name="Volume Delta Divergence",
        category="cumulative_delta",
        formula_template="""df['price_up'] = df['close'] > df['open']
df['delta'] = np.where(df['price_up'], df['volume'], -df['volume'])
df['cum_delta'] = df['delta'].rolling({period}).sum()
df['price_down'] = df['close'] < df['close'].shift(5)
df['delta_up'] = df['cum_delta'] > df['cum_delta'].shift(5)
df['divergence'] = df['price_down'] & df['delta_up']
df['entry_signal'] = df['divergence']""",
        params={"period": [20]},
        direction="long",
        lookback=35,
        indicators=[],
        combinable_with=["confirmation", "volume"],
        strategy_type="CDL",
    ),
    # Volume Delta Extreme
    PatternBlock(
        id="VOL_DELTA_EXTREME",
        name="Volume Delta Extreme",
        category="cumulative_delta",
        formula_template="""df['price_up'] = df['close'] > df['open']
df['delta'] = np.where(df['price_up'], df['volume'], -df['volume'])
df['cum_delta'] = df['delta'].rolling({period}).sum()
df['delta_ma'] = df['cum_delta'].rolling({period}).mean()
df['delta_std'] = df['cum_delta'].rolling({period}).std()
df['extreme_neg'] = df['cum_delta'] < df['delta_ma'] - df['delta_std'] * {mult}
df['entry_signal'] = df['extreme_neg']""",
        params={"period": [20], "mult": [1.5, 2.0]},
        direction="long",
        lookback=40,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="CDL",
    ),
]


# =============================================================================
# EFFICIENCY RATIO BLOCKS (Kaufman)
# =============================================================================

EFFICIENCY_RATIO_BLOCKS = [
    # High Efficiency Ratio
    PatternBlock(
        id="HIGH_EFFICIENCY_RATIO",
        name="High Efficiency Ratio",
        category="efficiency_ratio",
        formula_template="""df['change'] = abs(df['close'] - df['close'].shift({period}))
df['volatility'] = abs(df['close'] - df['close'].shift(1)).rolling({period}).sum()
df['er'] = df['change'] / (df['volatility'] + 1e-10)
df['high_er'] = df['er'] > {threshold}
df['uptrend'] = df['close'] > df['close'].shift({period})
df['entry_signal'] = df['high_er'] & df['uptrend']""",
        params={"period": [10, 20], "threshold": [0.5, 0.6]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "volume"],
        strategy_type="EFR",
    ),
    # Efficiency Ratio Rising
    PatternBlock(
        id="ER_RISING",
        name="Efficiency Ratio Rising",
        category="efficiency_ratio",
        formula_template="""df['change'] = abs(df['close'] - df['close'].shift({period}))
df['volatility'] = abs(df['close'] - df['close'].shift(1)).rolling({period}).sum()
df['er'] = df['change'] / (df['volatility'] + 1e-10)
df['er_rising'] = df['er'] > df['er'].shift(3)
df['er_above_mid'] = df['er'] > 0.3
df['entry_signal'] = df['er_rising'] & df['er_above_mid']""",
        params={"period": [10, 14]},
        direction="bidi",
        lookback=25,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="EFR",
    ),
    # Low Efficiency (Choppy) to High
    PatternBlock(
        id="ER_LOW_TO_HIGH",
        name="Efficiency Low to High",
        category="efficiency_ratio",
        formula_template="""df['change'] = abs(df['close'] - df['close'].shift({period}))
df['volatility'] = abs(df['close'] - df['close'].shift(1)).rolling({period}).sum()
df['er'] = df['change'] / (df['volatility'] + 1e-10)
df['was_low'] = df['er'].shift(3) < {low_thresh}
df['now_high'] = df['er'] > {high_thresh}
df['entry_signal'] = df['was_low'] & df['now_high']""",
        params={"period": [10], "low_thresh": [0.2], "high_thresh": [0.4, 0.5]},
        direction="bidi",
        lookback=25,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="EFR",
    ),
]


# =============================================================================
# CHOPPINESS BLOCKS
# =============================================================================

CHOPPINESS_BLOCKS = [
    # Low Choppiness (Trending)
    PatternBlock(
        id="LOW_CHOPPINESS",
        name="Low Choppiness Trending",
        category="choppiness",
        formula_template="""df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
df['atr_sum'] = df['tr'].rolling({period}).sum()
df['high_low_range'] = df['high'].rolling({period}).max() - df['low'].rolling({period}).min()
df['chop'] = 100 * np.log10(df['atr_sum'] / (df['high_low_range'] + 1e-10)) / np.log10({period})
df['low_chop'] = df['chop'] < {threshold}
df['uptrend'] = df['close'] > df['close'].shift(5)
df['entry_signal'] = df['low_chop'] & df['uptrend']""",
        params={"period": [14], "threshold": [38.2, 40]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="CHP",
    ),
    # High Choppiness Breaking Out
    PatternBlock(
        id="CHOP_BREAKOUT",
        name="Choppiness Breakout",
        category="choppiness",
        formula_template="""df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
df['atr_sum'] = df['tr'].rolling({period}).sum()
df['high_low_range'] = df['high'].rolling({period}).max() - df['low'].rolling({period}).min()
df['chop'] = 100 * np.log10(df['atr_sum'] / (df['high_low_range'] + 1e-10)) / np.log10({period})
df['was_high'] = df['chop'].shift(1) > {high_thresh}
df['now_low'] = df['chop'] < {low_thresh}
df['entry_signal'] = df['was_high'] & df['now_low']""",
        params={"period": [14], "high_thresh": [55, 60], "low_thresh": [45, 50]},
        direction="bidi",
        lookback=25,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="CHP",
    ),
    # Choppiness Extreme
    PatternBlock(
        id="CHOP_EXTREME",
        name="Choppiness Extreme Sideways",
        category="choppiness",
        formula_template="""df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
df['atr_sum'] = df['tr'].rolling({period}).sum()
df['high_low_range'] = df['high'].rolling({period}).max() - df['low'].rolling({period}).min()
df['chop'] = 100 * np.log10(df['atr_sum'] / (df['high_low_range'] + 1e-10)) / np.log10({period})
df['extreme_chop'] = df['chop'] > {threshold}
df['extreme_days'] = df['extreme_chop'].rolling(5).sum() >= 3
df['entry_signal'] = df['extreme_days']""",
        params={"period": [14], "threshold": [61.8, 65]},
        direction="bidi",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="CHP",
    ),
]


# =============================================================================
# DETRENDED PRICE BLOCKS
# =============================================================================

DETRENDED_PRICE_BLOCKS = [
    # DPO Oversold
    PatternBlock(
        id="DPO_OVERSOLD",
        name="DPO Oversold",
        category="detrended_price",
        formula_template="""df['dpo_period'] = {period} // 2 + 1
df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['dpo'] = df['close'].shift(df['dpo_period'].iloc[0]) - df['sma']
df['dpo_std'] = df['dpo'].rolling({period}).std()
df['oversold'] = df['dpo'] < -df['dpo_std'] * {mult}
df['entry_signal'] = df['oversold']""",
        params={"period": [20], "mult": [1.5, 2.0]},
        direction="long",
        lookback=40,
        indicators=["SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="DTP",
    ),
    # DPO Zero Cross Up
    PatternBlock(
        id="DPO_CROSS_UP",
        name="DPO Cross Up",
        category="detrended_price",
        formula_template="""df['dpo_period'] = {period} // 2 + 1
df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['dpo'] = df['close'].shift(df['dpo_period'].iloc[0]) - df['sma']
df['cross_up'] = (df['dpo'] > 0) & (df['dpo'].shift(1) <= 0)
df['entry_signal'] = df['cross_up']""",
        params={"period": [20, 30]},
        direction="long",
        lookback=45,
        indicators=["SMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="DTP",
    ),
    # DPO Positive Momentum
    PatternBlock(
        id="DPO_POSITIVE_MOM",
        name="DPO Positive Momentum",
        category="detrended_price",
        formula_template="""df['dpo_period'] = {period} // 2 + 1
df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['dpo'] = df['close'].shift(df['dpo_period'].iloc[0]) - df['sma']
df['dpo_positive'] = df['dpo'] > 0
df['dpo_rising'] = df['dpo'] > df['dpo'].shift(3)
df['entry_signal'] = df['dpo_positive'] & df['dpo_rising']""",
        params={"period": [20]},
        direction="long",
        lookback=40,
        indicators=["SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="DTP",
    ),
]


# =============================================================================
# TRUE STRENGTH INDEX BLOCKS
# =============================================================================

TRUE_STRENGTH_INDEX_BLOCKS = [
    # TSI Oversold
    PatternBlock(
        id="TSI_OVERSOLD",
        name="TSI Oversold",
        category="true_strength_index",
        formula_template="""df['pc'] = df['close'] - df['close'].shift(1)
df['pc_ds'] = ta.EMA(ta.EMA(df['pc'], timeperiod={long_period}), timeperiod={short_period})
df['apc'] = abs(df['pc'])
df['apc_ds'] = ta.EMA(ta.EMA(df['apc'], timeperiod={long_period}), timeperiod={short_period})
df['tsi'] = 100 * df['pc_ds'] / (df['apc_ds'] + 1e-10)
df['oversold'] = df['tsi'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"long_period": [25], "short_period": [13], "level": [-25, -30]},
        direction="long",
        lookback=50,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="TSX",
    ),
    # TSI Signal Cross
    PatternBlock(
        id="TSI_SIGNAL_CROSS",
        name="TSI Signal Cross Up",
        category="true_strength_index",
        formula_template="""df['pc'] = df['close'] - df['close'].shift(1)
df['pc_ds'] = ta.EMA(ta.EMA(df['pc'], timeperiod={long_period}), timeperiod={short_period})
df['apc'] = abs(df['pc'])
df['apc_ds'] = ta.EMA(ta.EMA(df['apc'], timeperiod={long_period}), timeperiod={short_period})
df['tsi'] = 100 * df['pc_ds'] / (df['apc_ds'] + 1e-10)
df['signal'] = ta.EMA(df['tsi'], timeperiod=7)
df['cross_up'] = (df['tsi'] > df['signal']) & (df['tsi'].shift(1) <= df['signal'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"long_period": [25], "short_period": [13]},
        direction="long",
        lookback=50,
        indicators=["EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="TSX",
    ),
    # TSI Zero Cross
    PatternBlock(
        id="TSI_ZERO_CROSS",
        name="TSI Zero Cross Up",
        category="true_strength_index",
        formula_template="""df['pc'] = df['close'] - df['close'].shift(1)
df['pc_ds'] = ta.EMA(ta.EMA(df['pc'], timeperiod={long_period}), timeperiod={short_period})
df['apc'] = abs(df['pc'])
df['apc_ds'] = ta.EMA(ta.EMA(df['apc'], timeperiod={long_period}), timeperiod={short_period})
df['tsi'] = 100 * df['pc_ds'] / (df['apc_ds'] + 1e-10)
df['cross_zero'] = (df['tsi'] > 0) & (df['tsi'].shift(1) <= 0)
df['entry_signal'] = df['cross_zero']""",
        params={"long_period": [25], "short_period": [13]},
        direction="long",
        lookback=50,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="TSX",
    ),
]


# =============================================================================
# ULTIMATE OSCILLATOR EXTENDED BLOCKS
# =============================================================================

ULTIMATE_OSC_EXT_BLOCKS = [
    # UO Oversold Reversal
    PatternBlock(
        id="UO_OVERSOLD_REV",
        name="UO Oversold Reversal",
        category="ultimate_osc_ext",
        formula_template="""df['uo'] = ta.ULTOSC(df['high'], df['low'], df['close'], timeperiod1=7, timeperiod2=14, timeperiod3=28)
df['oversold'] = df['uo'] < {level}
df['turning'] = df['uo'] > df['uo'].shift(1)
df['entry_signal'] = df['oversold'] & df['turning']""",
        params={"level": [30, 35]},
        direction="long",
        lookback=40,
        indicators=["ULTOSC"],
        combinable_with=["volume", "confirmation"],
        strategy_type="UOE",
    ),
    # UO Bullish Divergence
    PatternBlock(
        id="UO_BULL_DIV",
        name="UO Bullish Divergence",
        category="ultimate_osc_ext",
        formula_template="""df['uo'] = ta.ULTOSC(df['high'], df['low'], df['close'], timeperiod1=7, timeperiod2=14, timeperiod3=28)
df['price_lower'] = df['close'] < df['close'].shift({lookback})
df['uo_higher'] = df['uo'] > df['uo'].shift({lookback})
df['uo_oversold'] = df['uo'] < 50
df['divergence'] = df['price_lower'] & df['uo_higher'] & df['uo_oversold']
df['entry_signal'] = df['divergence']""",
        params={"lookback": [5, 10]},
        direction="long",
        lookback=50,
        indicators=["ULTOSC"],
        combinable_with=["confirmation", "momentum"],
        strategy_type="UOE",
    ),
    # UO Momentum Thrust
    PatternBlock(
        id="UO_THRUST",
        name="UO Momentum Thrust",
        category="ultimate_osc_ext",
        formula_template="""df['uo'] = ta.ULTOSC(df['high'], df['low'], df['close'], timeperiod1=7, timeperiod2=14, timeperiod3=28)
df['uo_rise'] = df['uo'] - df['uo'].shift(3)
df['strong_rise'] = df['uo_rise'] > {threshold}
df['above_mid'] = df['uo'] > 50
df['entry_signal'] = df['strong_rise'] & df['above_mid']""",
        params={"threshold": [10, 15]},
        direction="long",
        lookback=40,
        indicators=["ULTOSC"],
        combinable_with=["volume", "threshold"],
        strategy_type="UOE",
    ),
]


# =============================================================================
# PRICE ACTION ZONES BLOCKS
# =============================================================================

PRICE_ACTION_ZONES_BLOCKS = [
    # Demand Zone Touch
    PatternBlock(
        id="DEMAND_ZONE_TOUCH",
        name="Demand Zone Touch",
        category="price_action_zones",
        formula_template="""df['swing_low'] = df['low'].rolling({period}).min()
df['zone_top'] = df['swing_low'] * (1 + {zone_width})
df['in_zone'] = (df['low'] <= df['zone_top']) & (df['low'] >= df['swing_low'] * 0.99)
df['bounce'] = df['close'] > df['open']
df['entry_signal'] = df['in_zone'] & df['bounce']""",
        params={"period": [20, 30], "zone_width": [0.01, 0.015]},
        direction="long",
        lookback=40,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PAZ",
    ),
    # Supply Zone Touch
    PatternBlock(
        id="SUPPLY_ZONE_TOUCH",
        name="Supply Zone Touch",
        category="price_action_zones",
        formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
df['zone_bottom'] = df['swing_high'] * (1 - {zone_width})
df['in_zone'] = (df['high'] >= df['zone_bottom']) & (df['high'] <= df['swing_high'] * 1.01)
df['rejection'] = df['close'] < df['open']
df['entry_signal'] = df['in_zone'] & df['rejection']""",
        params={"period": [20, 30], "zone_width": [0.01, 0.015]},
        direction="short",
        lookback=40,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PAZ",
    ),
    # Fresh Zone Break
    PatternBlock(
        id="FRESH_ZONE_BREAK",
        name="Fresh Zone Break",
        category="price_action_zones",
        formula_template="""df['prev_high'] = df['high'].rolling({period}).max().shift(1)
df['breakout'] = df['close'] > df['prev_high']
df['strong'] = df['close'] > df['prev_high'] * (1 + {margin})
df['entry_signal'] = df['strong']""",
        params={"period": [20], "margin": [0.002, 0.005]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="PAZ",
    ),
]


# =============================================================================
# TWIN RANGE BLOCKS
# =============================================================================

TWIN_RANGE_BLOCKS = [
    # Twin Range Filter Long
    PatternBlock(
        id="TWIN_RANGE_LONG",
        name="Twin Range Filter Long",
        category="twin_range",
        formula_template="""df['atr_fast'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={fast_period})
df['atr_slow'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={slow_period})
df['range_val'] = (df['atr_fast'] * {fast_mult} + df['atr_slow'] * {slow_mult}) / 2
df['smooth_range'] = ta.EMA(df['range_val'], timeperiod=10)
df['up'] = df['close'] > df['close'].shift(1) + df['smooth_range'].shift(1)
df['entry_signal'] = df['up']""",
        params={"fast_period": [5], "slow_period": [20], "fast_mult": [1.0], "slow_mult": [1.0]},
        direction="long",
        lookback=30,
        indicators=["ATR", "EMA"],
        combinable_with=["momentum", "volume"],
        strategy_type="TWR",
    ),
    # Twin Range Filter Short
    PatternBlock(
        id="TWIN_RANGE_SHORT",
        name="Twin Range Filter Short",
        category="twin_range",
        formula_template="""df['atr_fast'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={fast_period})
df['atr_slow'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={slow_period})
df['range_val'] = (df['atr_fast'] * {fast_mult} + df['atr_slow'] * {slow_mult}) / 2
df['smooth_range'] = ta.EMA(df['range_val'], timeperiod=10)
df['down'] = df['close'] < df['close'].shift(1) - df['smooth_range'].shift(1)
df['entry_signal'] = df['down']""",
        params={"fast_period": [5], "slow_period": [20], "fast_mult": [1.0], "slow_mult": [1.0]},
        direction="short",
        lookback=30,
        indicators=["ATR", "EMA"],
        combinable_with=["momentum", "volume"],
        strategy_type="TWR",
    ),
    # Twin Range Squeeze
    PatternBlock(
        id="TWIN_RANGE_SQUEEZE",
        name="Twin Range Squeeze",
        category="twin_range",
        formula_template="""df['atr_fast'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={fast_period})
df['atr_slow'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={slow_period})
df['ratio'] = df['atr_fast'] / (df['atr_slow'] + 1e-10)
df['squeeze'] = df['ratio'] < {threshold}
df['squeeze_days'] = df['squeeze'].rolling(5).sum() >= 3
df['entry_signal'] = df['squeeze_days']""",
        params={"fast_period": [5], "slow_period": [20], "threshold": [0.6, 0.7]},
        direction="bidi",
        lookback=30,
        indicators=["ATR"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="TWR",
    ),
]


# =============================================================================
# IMPULSE MACD BLOCKS
# =============================================================================

IMPULSE_MACD_BLOCKS = [
    # Impulse MACD Green
    PatternBlock(
        id="IMPULSE_MACD_GREEN",
        name="Impulse MACD Green",
        category="impulse_macd",
        formula_template="""df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod=9)
df['hist_rising'] = df['hist'] > df['hist'].shift(1)
df['macd_rising'] = df['macd'] > df['macd'].shift(1)
df['green_bar'] = df['hist_rising'] & df['macd_rising']
df['entry_signal'] = df['green_bar']""",
        params={"fast": [12], "slow": [26]},
        direction="long",
        lookback=40,
        indicators=["MACD"],
        combinable_with=["volume", "threshold"],
        strategy_type="IMC",
    ),
    # Impulse MACD Red
    PatternBlock(
        id="IMPULSE_MACD_RED",
        name="Impulse MACD Red",
        category="impulse_macd",
        formula_template="""df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod=9)
df['hist_falling'] = df['hist'] < df['hist'].shift(1)
df['macd_falling'] = df['macd'] < df['macd'].shift(1)
df['red_bar'] = df['hist_falling'] & df['macd_falling']
df['entry_signal'] = df['red_bar']""",
        params={"fast": [12], "slow": [26]},
        direction="short",
        lookback=40,
        indicators=["MACD"],
        combinable_with=["volume", "threshold"],
        strategy_type="IMC",
    ),
    # Impulse MACD Color Change
    PatternBlock(
        id="IMPULSE_MACD_CHANGE",
        name="Impulse MACD Color Change",
        category="impulse_macd",
        formula_template="""df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod=9)
df['hist_rising'] = df['hist'] > df['hist'].shift(1)
df['macd_rising'] = df['macd'] > df['macd'].shift(1)
df['green'] = df['hist_rising'] & df['macd_rising']
df['was_not_green'] = ~(df['hist'].shift(1) > df['hist'].shift(2)) | ~(df['macd'].shift(1) > df['macd'].shift(2))
df['color_change'] = df['green'] & df['was_not_green']
df['entry_signal'] = df['color_change']""",
        params={"fast": [12], "slow": [26]},
        direction="long",
        lookback=40,
        indicators=["MACD"],
        combinable_with=["volume", "confirmation"],
        strategy_type="IMC",
    ),
]


# =============================================================================
# WAVETREND BLOCKS
# =============================================================================

WAVETREND_BLOCKS = [
    # WaveTrend Oversold
    PatternBlock(
        id="WAVETREND_OVERSOLD",
        name="WaveTrend Oversold",
        category="wavetrend",
        formula_template="""df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
df['esa'] = ta.EMA(df['hlc3'], timeperiod={period})
df['d'] = ta.EMA(abs(df['hlc3'] - df['esa']), timeperiod={period})
df['ci'] = (df['hlc3'] - df['esa']) / (0.015 * df['d'] + 1e-10)
df['wt1'] = ta.EMA(df['ci'], timeperiod=21)
df['wt2'] = ta.SMA(df['wt1'], timeperiod=4)
df['oversold'] = df['wt1'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"period": [10], "level": [-60, -70]},
        direction="long",
        lookback=40,
        indicators=["EMA", "SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="WVT",
    ),
    # WaveTrend Cross Up
    PatternBlock(
        id="WAVETREND_CROSS_UP",
        name="WaveTrend Cross Up",
        category="wavetrend",
        formula_template="""df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
df['esa'] = ta.EMA(df['hlc3'], timeperiod={period})
df['d'] = ta.EMA(abs(df['hlc3'] - df['esa']), timeperiod={period})
df['ci'] = (df['hlc3'] - df['esa']) / (0.015 * df['d'] + 1e-10)
df['wt1'] = ta.EMA(df['ci'], timeperiod=21)
df['wt2'] = ta.SMA(df['wt1'], timeperiod=4)
df['cross_up'] = (df['wt1'] > df['wt2']) & (df['wt1'].shift(1) <= df['wt2'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [10]},
        direction="long",
        lookback=40,
        indicators=["EMA", "SMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="WVT",
    ),
    # WaveTrend Divergence
    PatternBlock(
        id="WAVETREND_DIVERGENCE",
        name="WaveTrend Divergence",
        category="wavetrend",
        formula_template="""df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
df['esa'] = ta.EMA(df['hlc3'], timeperiod={period})
df['d'] = ta.EMA(abs(df['hlc3'] - df['esa']), timeperiod={period})
df['ci'] = (df['hlc3'] - df['esa']) / (0.015 * df['d'] + 1e-10)
df['wt1'] = ta.EMA(df['ci'], timeperiod=21)
df['price_lower'] = df['close'] < df['close'].shift(5)
df['wt_higher'] = df['wt1'] > df['wt1'].shift(5)
df['divergence'] = df['price_lower'] & df['wt_higher']
df['entry_signal'] = df['divergence']""",
        params={"period": [10]},
        direction="long",
        lookback=40,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="WVT",
    ),
]


# =============================================================================
# QQE BLOCKS (Qualitative Quantitative Estimation)
# =============================================================================

QQE_BLOCKS = [
    # QQE Cross Up
    PatternBlock(
        id="QQE_CROSS_UP",
        name="QQE Cross Up",
        category="qqe",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={rsi_period})
df['rsi_ma'] = ta.EMA(df['rsi'], timeperiod=5)
df['atr_rsi'] = abs(df['rsi_ma'] - df['rsi_ma'].shift(1))
df['atr_rsi_ma'] = ta.EMA(df['atr_rsi'], timeperiod={period}) * {mult}
df['long_band'] = df['rsi_ma'] - df['atr_rsi_ma']
df['cross_up'] = (df['rsi_ma'] > df['long_band']) & (df['rsi_ma'].shift(1) <= df['long_band'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"rsi_period": [14], "period": [5], "mult": [4.236]},
        direction="long",
        lookback=30,
        indicators=["RSI", "EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="QQE",
    ),
    # QQE Trend
    PatternBlock(
        id="QQE_TREND",
        name="QQE Trend Mode",
        category="qqe",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={rsi_period})
df['rsi_ma'] = ta.EMA(df['rsi'], timeperiod=5)
df['atr_rsi'] = abs(df['rsi_ma'] - df['rsi_ma'].shift(1))
df['atr_rsi_ma'] = ta.EMA(df['atr_rsi'], timeperiod={period}) * {mult}
df['trend_up'] = df['rsi_ma'] > 50
df['strong'] = df['rsi_ma'] > (50 + df['atr_rsi_ma'])
df['entry_signal'] = df['trend_up'] & df['strong']""",
        params={"rsi_period": [14], "period": [5], "mult": [4.236]},
        direction="long",
        lookback=30,
        indicators=["RSI", "EMA"],
        combinable_with=["threshold", "confirmation"],
        strategy_type="QQE",
    ),
    # QQE Zero Cross
    PatternBlock(
        id="QQE_ZERO_CROSS",
        name="QQE Zero Cross",
        category="qqe",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={rsi_period})
df['rsi_ma'] = ta.EMA(df['rsi'], timeperiod=5)
df['rsi_centered'] = df['rsi_ma'] - 50
df['cross_zero'] = (df['rsi_centered'] > 0) & (df['rsi_centered'].shift(1) <= 0)
df['entry_signal'] = df['cross_zero']""",
        params={"rsi_period": [14]},
        direction="long",
        lookback=25,
        indicators=["RSI", "EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="QQE",
    ),
]


# =============================================================================
# SCHAFF TREND CYCLE BLOCKS
# =============================================================================

SCHAFF_TREND_BLOCKS = [
    # STC Oversold
    PatternBlock(
        id="STC_OVERSOLD",
        name="STC Oversold",
        category="schaff_trend",
        formula_template="""df['macd'], _, _ = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod=9)
df['macd_min'] = df['macd'].rolling({cycle}).min()
df['macd_max'] = df['macd'].rolling({cycle}).max()
df['stoch_macd'] = (df['macd'] - df['macd_min']) / (df['macd_max'] - df['macd_min'] + 1e-10) * 100
df['stc1'] = ta.EMA(df['stoch_macd'], timeperiod=3)
df['stc1_min'] = df['stc1'].rolling({cycle}).min()
df['stc1_max'] = df['stc1'].rolling({cycle}).max()
df['stc'] = (df['stc1'] - df['stc1_min']) / (df['stc1_max'] - df['stc1_min'] + 1e-10) * 100
df['oversold'] = df['stc'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"fast": [23], "slow": [50], "cycle": [10], "level": [25, 30]},
        direction="long",
        lookback=70,
        indicators=["MACD", "EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="STC",
    ),
    # STC Rising
    PatternBlock(
        id="STC_RISING",
        name="STC Rising from Low",
        category="schaff_trend",
        formula_template="""df['macd'], _, _ = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod=9)
df['macd_min'] = df['macd'].rolling({cycle}).min()
df['macd_max'] = df['macd'].rolling({cycle}).max()
df['stoch_macd'] = (df['macd'] - df['macd_min']) / (df['macd_max'] - df['macd_min'] + 1e-10) * 100
df['stc1'] = ta.EMA(df['stoch_macd'], timeperiod=3)
df['stc1_min'] = df['stc1'].rolling({cycle}).min()
df['stc1_max'] = df['stc1'].rolling({cycle}).max()
df['stc'] = (df['stc1'] - df['stc1_min']) / (df['stc1_max'] - df['stc1_min'] + 1e-10) * 100
df['was_low'] = df['stc'].shift(1) < {low_level}
df['rising'] = df['stc'] > df['stc'].shift(1)
df['entry_signal'] = df['was_low'] & df['rising']""",
        params={"fast": [23], "slow": [50], "cycle": [10], "low_level": [25, 30]},
        direction="long",
        lookback=70,
        indicators=["MACD", "EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="STC",
    ),
    # STC Trend Confirm
    PatternBlock(
        id="STC_TREND_CONFIRM",
        name="STC Trend Confirm",
        category="schaff_trend",
        formula_template="""df['macd'], _, _ = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod=9)
df['macd_min'] = df['macd'].rolling({cycle}).min()
df['macd_max'] = df['macd'].rolling({cycle}).max()
df['stoch_macd'] = (df['macd'] - df['macd_min']) / (df['macd_max'] - df['macd_min'] + 1e-10) * 100
df['stc1'] = ta.EMA(df['stoch_macd'], timeperiod=3)
df['stc1_min'] = df['stc1'].rolling({cycle}).min()
df['stc1_max'] = df['stc1'].rolling({cycle}).max()
df['stc'] = (df['stc1'] - df['stc1_min']) / (df['stc1_max'] - df['stc1_min'] + 1e-10) * 100
df['strong_up'] = df['stc'] > {high_level}
df['price_up'] = df['close'] > df['close'].shift(3)
df['entry_signal'] = df['strong_up'] & df['price_up']""",
        params={"fast": [23], "slow": [50], "cycle": [10], "high_level": [70, 75]},
        direction="long",
        lookback=70,
        indicators=["MACD", "EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="STC",
    ),
]


# =============================================================================
# FISHER TRANSFORM BLOCKS
# =============================================================================

FISHER_TRANSFORM_BLOCKS = [
    # Fisher Oversold
    PatternBlock(
        id="FISHER_OVERSOLD",
        name="Fisher Oversold",
        category="fisher_transform",
        formula_template="""df['hl2'] = (df['high'] + df['low']) / 2
df['max_hl2'] = df['hl2'].rolling({period}).max()
df['min_hl2'] = df['hl2'].rolling({period}).min()
df['raw'] = 2 * ((df['hl2'] - df['min_hl2']) / (df['max_hl2'] - df['min_hl2'] + 1e-10) - 0.5)
df['raw'] = df['raw'].clip(-0.999, 0.999)
df['fisher'] = 0.5 * np.log((1 + df['raw']) / (1 - df['raw'] + 1e-10))
df['fisher'] = ta.EMA(df['fisher'], timeperiod=3)
df['oversold'] = df['fisher'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"period": [10], "level": [-1.5, -2.0]},
        direction="long",
        lookback=25,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="FSH",
    ),
    # Fisher Cross Up
    PatternBlock(
        id="FISHER_CROSS_UP",
        name="Fisher Cross Up",
        category="fisher_transform",
        formula_template="""df['hl2'] = (df['high'] + df['low']) / 2
df['max_hl2'] = df['hl2'].rolling({period}).max()
df['min_hl2'] = df['hl2'].rolling({period}).min()
df['raw'] = 2 * ((df['hl2'] - df['min_hl2']) / (df['max_hl2'] - df['min_hl2'] + 1e-10) - 0.5)
df['raw'] = df['raw'].clip(-0.999, 0.999)
df['fisher'] = 0.5 * np.log((1 + df['raw']) / (1 - df['raw'] + 1e-10))
df['fisher'] = ta.EMA(df['fisher'], timeperiod=3)
df['signal'] = df['fisher'].shift(1)
df['cross_up'] = (df['fisher'] > df['signal']) & (df['fisher'].shift(1) <= df['signal'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [10]},
        direction="long",
        lookback=25,
        indicators=["EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="FSH",
    ),
    # Fisher Zero Cross
    PatternBlock(
        id="FISHER_ZERO_CROSS",
        name="Fisher Zero Cross Up",
        category="fisher_transform",
        formula_template="""df['hl2'] = (df['high'] + df['low']) / 2
df['max_hl2'] = df['hl2'].rolling({period}).max()
df['min_hl2'] = df['hl2'].rolling({period}).min()
df['raw'] = 2 * ((df['hl2'] - df['min_hl2']) / (df['max_hl2'] - df['min_hl2'] + 1e-10) - 0.5)
df['raw'] = df['raw'].clip(-0.999, 0.999)
df['fisher'] = 0.5 * np.log((1 + df['raw']) / (1 - df['raw'] + 1e-10))
df['fisher'] = ta.EMA(df['fisher'], timeperiod=3)
df['cross_zero'] = (df['fisher'] > 0) & (df['fisher'].shift(1) <= 0)
df['entry_signal'] = df['cross_zero']""",
        params={"period": [10]},
        direction="long",
        lookback=25,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="FSH",
    ),
]


# =============================================================================
# EHLERS BLOCKS (Super Smoother, etc.)
# =============================================================================

EHLERS_BLOCKS = [
    # Super Smoother Cross
    PatternBlock(
        id="SUPER_SMOOTHER_CROSS",
        name="Super Smoother Cross Up",
        category="ehlers",
        formula_template="""df['a1'] = np.exp(-1.414 * 3.14159 / {period})
df['b1'] = 2 * df['a1'] * np.cos(1.414 * 3.14159 / {period})
df['c2'] = df['b1']
df['c3'] = -df['a1'] * df['a1']
df['c1'] = 1 - df['c2'] - df['c3']
df['ss'] = df['close'].copy()
for i in range(2, len(df)):
    df.iloc[i, df.columns.get_loc('ss')] = df['c1'].iloc[i] * (df['close'].iloc[i] + df['close'].iloc[i-1]) / 2 + df['c2'].iloc[i] * df['ss'].iloc[i-1] + df['c3'].iloc[i] * df['ss'].iloc[i-2]
df['cross_up'] = (df['close'] > df['ss']) & (df['close'].shift(1) <= df['ss'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [10, 20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="EHL",
    ),
    # Ehlers Trend
    PatternBlock(
        id="EHLERS_TREND",
        name="Ehlers Smoothed Trend",
        category="ehlers",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
df['trend'] = df['ema_fast'] - df['ema_slow']
df['trend_smooth'] = ta.EMA(df['trend'], timeperiod=5)
df['trend_up'] = df['trend_smooth'] > 0
df['trend_rising'] = df['trend_smooth'] > df['trend_smooth'].shift(1)
df['entry_signal'] = df['trend_up'] & df['trend_rising']""",
        params={"fast": [8, 10], "slow": [21, 25]},
        direction="long",
        lookback=35,
        indicators=["EMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="EHL",
    ),
    # Ehlers Instantaneous Trend
    PatternBlock(
        id="EHLERS_INST_TREND",
        name="Ehlers Instantaneous Trend",
        category="ehlers",
        formula_template="""df['ema1'] = ta.EMA(df['close'], timeperiod={period})
df['ema2'] = ta.EMA(df['ema1'], timeperiod={period})
df['inst_trend'] = 2 * df['ema1'] - df['ema2']
df['trigger'] = ta.EMA(df['inst_trend'], timeperiod=3)
df['cross_up'] = (df['inst_trend'] > df['trigger']) & (df['inst_trend'].shift(1) <= df['trigger'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=30,
        indicators=["EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="EHL",
    ),
]


# =============================================================================
# CENTER OF GRAVITY BLOCKS
# =============================================================================

CENTER_OF_GRAVITY_BLOCKS = [
    # COG Oversold
    PatternBlock(
        id="COG_OVERSOLD",
        name="COG Oversold",
        category="center_of_gravity",
        formula_template="""weights = np.arange(1, {period} + 1)
df['cog'] = -df['close'].rolling({period}).apply(lambda x: np.sum(weights * x) / np.sum(x), raw=True)
df['cog_norm'] = (df['cog'] - df['cog'].rolling(50).mean()) / (df['cog'].rolling(50).std() + 1e-10)
df['oversold'] = df['cog_norm'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"period": [10], "level": [-1.5, -2.0]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="COG",
    ),
    # COG Zero Cross
    PatternBlock(
        id="COG_ZERO_CROSS",
        name="COG Zero Cross Up",
        category="center_of_gravity",
        formula_template="""weights = np.arange(1, {period} + 1)
df['cog'] = -df['close'].rolling({period}).apply(lambda x: np.sum(weights * x) / np.sum(x), raw=True)
df['cog_ma'] = df['cog'].rolling(10).mean()
df['cross_up'] = (df['cog'] > df['cog_ma']) & (df['cog'].shift(1) <= df['cog_ma'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [10]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="COG",
    ),
    # COG Momentum
    PatternBlock(
        id="COG_MOMENTUM",
        name="COG Momentum",
        category="center_of_gravity",
        formula_template="""weights = np.arange(1, {period} + 1)
df['cog'] = -df['close'].rolling({period}).apply(lambda x: np.sum(weights * x) / np.sum(x), raw=True)
df['cog_change'] = df['cog'] - df['cog'].shift(3)
df['positive_mom'] = df['cog_change'] > 0
df['accelerating'] = df['cog_change'] > df['cog_change'].shift(1)
df['entry_signal'] = df['positive_mom'] & df['accelerating']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="COG",
    ),
]


# =============================================================================
# RELATIVE VIGOR INDEX BLOCKS
# =============================================================================

RELATIVE_VIGOR_BLOCKS = [
    # RVI Cross Up
    PatternBlock(
        id="RVI_CROSS_UP",
        name="RVI Cross Up",
        category="relative_vigor",
        formula_template="""df['co'] = df['close'] - df['open']
df['hl'] = df['high'] - df['low']
df['rvi_num'] = (df['co'] + 2*df['co'].shift(1) + 2*df['co'].shift(2) + df['co'].shift(3)) / 6
df['rvi_den'] = (df['hl'] + 2*df['hl'].shift(1) + 2*df['hl'].shift(2) + df['hl'].shift(3)) / 6
df['rvi'] = df['rvi_num'].rolling({period}).sum() / (df['rvi_den'].rolling({period}).sum() + 1e-10)
df['signal'] = (df['rvi'] + 2*df['rvi'].shift(1) + 2*df['rvi'].shift(2) + df['rvi'].shift(3)) / 6
df['cross_up'] = (df['rvi'] > df['signal']) & (df['rvi'].shift(1) <= df['signal'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="RVI",
    ),
    # RVI Positive
    PatternBlock(
        id="RVI_POSITIVE",
        name="RVI Positive Zone",
        category="relative_vigor",
        formula_template="""df['co'] = df['close'] - df['open']
df['hl'] = df['high'] - df['low']
df['rvi_num'] = (df['co'] + 2*df['co'].shift(1) + 2*df['co'].shift(2) + df['co'].shift(3)) / 6
df['rvi_den'] = (df['hl'] + 2*df['hl'].shift(1) + 2*df['hl'].shift(2) + df['hl'].shift(3)) / 6
df['rvi'] = df['rvi_num'].rolling({period}).sum() / (df['rvi_den'].rolling({period}).sum() + 1e-10)
df['positive'] = df['rvi'] > 0
df['rising'] = df['rvi'] > df['rvi'].shift(1)
df['entry_signal'] = df['positive'] & df['rising']""",
        params={"period": [10]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["threshold", "confirmation"],
        strategy_type="RVI",
    ),
    # RVI Divergence
    PatternBlock(
        id="RVI_DIVERGENCE",
        name="RVI Divergence",
        category="relative_vigor",
        formula_template="""df['co'] = df['close'] - df['open']
df['hl'] = df['high'] - df['low']
df['rvi_num'] = (df['co'] + 2*df['co'].shift(1) + 2*df['co'].shift(2) + df['co'].shift(3)) / 6
df['rvi_den'] = (df['hl'] + 2*df['hl'].shift(1) + 2*df['hl'].shift(2) + df['hl'].shift(3)) / 6
df['rvi'] = df['rvi_num'].rolling({period}).sum() / (df['rvi_den'].rolling({period}).sum() + 1e-10)
df['price_lower'] = df['close'] < df['close'].shift(5)
df['rvi_higher'] = df['rvi'] > df['rvi'].shift(5)
df['divergence'] = df['price_lower'] & df['rvi_higher']
df['entry_signal'] = df['divergence']""",
        params={"period": [10]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="RVI",
    ),
]


# =============================================================================
# RAINBOW MA BLOCKS
# =============================================================================

RAINBOW_MA_BLOCKS = [
    # Rainbow Bull Alignment
    PatternBlock(
        id="RAINBOW_BULL_ALIGN",
        name="Rainbow Bull Alignment",
        category="rainbow_ma",
        formula_template="""df['ma1'] = ta.SMA(df['close'], timeperiod={base})
df['ma2'] = ta.SMA(df['ma1'], timeperiod={base})
df['ma3'] = ta.SMA(df['ma2'], timeperiod={base})
df['ma4'] = ta.SMA(df['ma3'], timeperiod={base})
df['aligned'] = (df['close'] > df['ma1']) & (df['ma1'] > df['ma2']) & (df['ma2'] > df['ma3']) & (df['ma3'] > df['ma4'])
df['entry_signal'] = df['aligned']""",
        params={"base": [2, 3]},
        direction="long",
        lookback=30,
        indicators=["SMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="RBW",
    ),
    # Rainbow Cross
    PatternBlock(
        id="RAINBOW_CROSS",
        name="Rainbow Cross Up",
        category="rainbow_ma",
        formula_template="""df['ma1'] = ta.SMA(df['close'], timeperiod={base})
df['ma2'] = ta.SMA(df['ma1'], timeperiod={base})
df['ma3'] = ta.SMA(df['ma2'], timeperiod={base})
df['price_cross'] = (df['close'] > df['ma1']) & (df['close'].shift(1) <= df['ma1'].shift(1))
df['ma_positive'] = df['ma1'] > df['ma2']
df['entry_signal'] = df['price_cross'] & df['ma_positive']""",
        params={"base": [2, 3]},
        direction="long",
        lookback=25,
        indicators=["SMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="RBW",
    ),
    # Rainbow Width
    PatternBlock(
        id="RAINBOW_WIDTH",
        name="Rainbow Width Expanding",
        category="rainbow_ma",
        formula_template="""df['ma1'] = ta.SMA(df['close'], timeperiod={base})
df['ma2'] = ta.SMA(df['ma1'], timeperiod={base})
df['ma3'] = ta.SMA(df['ma2'], timeperiod={base})
df['width'] = (df['ma1'] - df['ma3']) / df['close']
df['expanding'] = df['width'] > df['width'].shift(3)
df['positive'] = df['width'] > 0
df['entry_signal'] = df['expanding'] & df['positive']""",
        params={"base": [2, 3]},
        direction="long",
        lookback=30,
        indicators=["SMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="RBW",
    ),
]


# =============================================================================
# TREND INTENSITY BLOCKS
# =============================================================================

TREND_INTENSITY_BLOCKS = [
    # Trend Intensity High
    PatternBlock(
        id="TREND_INTENSITY_HIGH",
        name="Trend Intensity High",
        category="trend_intensity",
        formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['dev'] = abs(df['close'] - df['sma'])
df['avg_dev'] = df['dev'].rolling({period}).mean()
df['ti'] = df['dev'] / (df['avg_dev'] + 1e-10)
df['high_ti'] = df['ti'] > {threshold}
df['uptrend'] = df['close'] > df['sma']
df['entry_signal'] = df['high_ti'] & df['uptrend']""",
        params={"period": [20, 30], "threshold": [1.2, 1.5]},
        direction="long",
        lookback=40,
        indicators=["SMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="TIN",
    ),
    # Trend Intensity Rising
    PatternBlock(
        id="TREND_INTENSITY_RISING",
        name="Trend Intensity Rising",
        category="trend_intensity",
        formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['dev'] = abs(df['close'] - df['sma'])
df['avg_dev'] = df['dev'].rolling({period}).mean()
df['ti'] = df['dev'] / (df['avg_dev'] + 1e-10)
df['ti_rising'] = df['ti'] > df['ti'].shift(3)
df['uptrend'] = df['close'] > df['sma']
df['entry_signal'] = df['ti_rising'] & df['uptrend']""",
        params={"period": [20]},
        direction="long",
        lookback=35,
        indicators=["SMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="TIN",
    ),
    # Trend Intensity Breakout
    PatternBlock(
        id="TREND_INTENSITY_BREAK",
        name="Trend Intensity Breakout",
        category="trend_intensity",
        formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['dev'] = abs(df['close'] - df['sma'])
df['avg_dev'] = df['dev'].rolling({period}).mean()
df['ti'] = df['dev'] / (df['avg_dev'] + 1e-10)
df['was_low'] = df['ti'].shift(3) < 0.8
df['now_high'] = df['ti'] > {threshold}
df['uptrend'] = df['close'] > df['sma']
df['entry_signal'] = df['was_low'] & df['now_high'] & df['uptrend']""",
        params={"period": [20], "threshold": [1.2, 1.3]},
        direction="long",
        lookback=40,
        indicators=["SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="TIN",
    ),
]


# =============================================================================
# PRICE ZONE OSCILLATOR BLOCKS
# =============================================================================

PRICE_ZONE_OSC_BLOCKS = [
    # PZO Oversold
    PatternBlock(
        id="PZO_OVERSOLD",
        name="PZO Oversold",
        category="price_zone_osc",
        formula_template="""df['cp'] = np.where(df['close'] > df['close'].shift(1), df['close'], -df['close'])
df['tc'] = ta.EMA(df['cp'], timeperiod={period})
df['vc'] = ta.EMA(df['close'], timeperiod={period})
df['pzo'] = 100 * df['tc'] / (df['vc'] + 1e-10)
df['oversold'] = df['pzo'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"period": [14], "level": [-40, -50]},
        direction="long",
        lookback=25,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="PZO",
    ),
    # PZO Cross Up
    PatternBlock(
        id="PZO_CROSS_UP",
        name="PZO Cross Up Zero",
        category="price_zone_osc",
        formula_template="""df['cp'] = np.where(df['close'] > df['close'].shift(1), df['close'], -df['close'])
df['tc'] = ta.EMA(df['cp'], timeperiod={period})
df['vc'] = ta.EMA(df['close'], timeperiod={period})
df['pzo'] = 100 * df['tc'] / (df['vc'] + 1e-10)
df['cross_up'] = (df['pzo'] > 0) & (df['pzo'].shift(1) <= 0)
df['entry_signal'] = df['cross_up']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="PZO",
    ),
    # PZO Strong Positive
    PatternBlock(
        id="PZO_STRONG_POS",
        name="PZO Strong Positive",
        category="price_zone_osc",
        formula_template="""df['cp'] = np.where(df['close'] > df['close'].shift(1), df['close'], -df['close'])
df['tc'] = ta.EMA(df['cp'], timeperiod={period})
df['vc'] = ta.EMA(df['close'], timeperiod={period})
df['pzo'] = 100 * df['tc'] / (df['vc'] + 1e-10)
df['strong_pos'] = df['pzo'] > {level}
df['rising'] = df['pzo'] > df['pzo'].shift(1)
df['entry_signal'] = df['strong_pos'] & df['rising']""",
        params={"period": [14], "level": [40, 50]},
        direction="long",
        lookback=25,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="PZO",
    ),
]


# =============================================================================
# SUPERTREND BLOCKS
# =============================================================================

SUPERTREND_BLOCKS = [
    # Supertrend Buy Signal
    PatternBlock(
        id="SUPERTREND_BUY",
        name="Supertrend Buy",
        category="supertrend",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['hl2'] = (df['high'] + df['low']) / 2
df['upper'] = df['hl2'] + df['atr'] * {mult}
df['lower'] = df['hl2'] - df['atr'] * {mult}
df['trend'] = 1
df['st'] = df['lower'].copy()
for i in range(1, len(df)):
    if df['close'].iloc[i-1] > df['st'].iloc[i-1]:
        df.iloc[i, df.columns.get_loc('st')] = max(df['lower'].iloc[i], df['st'].iloc[i-1])
    else:
        df.iloc[i, df.columns.get_loc('st')] = df['upper'].iloc[i]
df['buy'] = (df['close'] > df['st']) & (df['close'].shift(1) <= df['st'].shift(1))
df['entry_signal'] = df['buy']""",
        params={"period": [10], "mult": [2.0, 3.0]},
        direction="long",
        lookback=30,
        indicators=["ATR"],
        combinable_with=["volume", "momentum"],
        strategy_type="SPT",
    ),
    # Supertrend Trend Up
    PatternBlock(
        id="SUPERTREND_UP",
        name="Supertrend Trend Up",
        category="supertrend",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['hl2'] = (df['high'] + df['low']) / 2
df['basic_upper'] = df['hl2'] + df['atr'] * {mult}
df['basic_lower'] = df['hl2'] - df['atr'] * {mult}
df['in_uptrend'] = df['close'] > df['basic_lower']
df['uptrend_confirm'] = df['in_uptrend'].rolling(3).sum() >= 3
df['entry_signal'] = df['uptrend_confirm']""",
        params={"period": [10], "mult": [2.0, 3.0]},
        direction="long",
        lookback=25,
        indicators=["ATR"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="SPT",
    ),
    # Supertrend Proximity
    PatternBlock(
        id="SUPERTREND_PROXIMITY",
        name="Supertrend Proximity",
        category="supertrend",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['hl2'] = (df['high'] + df['low']) / 2
df['lower_band'] = df['hl2'] - df['atr'] * {mult}
df['dist'] = (df['close'] - df['lower_band']) / df['close']
df['close_to_band'] = df['dist'] < {proximity}
df['above'] = df['close'] > df['lower_band']
df['entry_signal'] = df['close_to_band'] & df['above']""",
        params={"period": [10], "mult": [2.0], "proximity": [0.01, 0.015]},
        direction="long",
        lookback=25,
        indicators=["ATR"],
        combinable_with=["volume", "confirmation"],
        strategy_type="SPT",
    ),
]


# =============================================================================
# HURST EXPONENT BLOCKS (simplified)
# =============================================================================

HURST_EXPONENT_BLOCKS = [
    # Hurst Trending
    PatternBlock(
        id="HURST_TRENDING",
        name="Hurst Trending",
        category="hurst_exponent",
        formula_template="""df['returns'] = df['close'].pct_change()
df['std_n'] = df['returns'].rolling({period}).std()
df['std_2n'] = df['returns'].rolling({period} * 2).std()
df['hurst_proxy'] = np.log(df['std_2n'] / (df['std_n'] + 1e-10)) / np.log(2)
df['trending'] = df['hurst_proxy'] > {threshold}
df['uptrend'] = df['close'] > df['close'].shift({period})
df['entry_signal'] = df['trending'] & df['uptrend']""",
        params={"period": [20], "threshold": [0.55, 0.6]},
        direction="long",
        lookback=50,
        indicators=[],
        combinable_with=["momentum", "volume"],
        strategy_type="HRS",
    ),
    # Hurst Mean Reverting
    PatternBlock(
        id="HURST_MEAN_REV",
        name="Hurst Mean Reverting",
        category="hurst_exponent",
        formula_template="""df['returns'] = df['close'].pct_change()
df['std_n'] = df['returns'].rolling({period}).std()
df['std_2n'] = df['returns'].rolling({period} * 2).std()
df['hurst_proxy'] = np.log(df['std_2n'] / (df['std_n'] + 1e-10)) / np.log(2)
df['mean_rev'] = df['hurst_proxy'] < {threshold}
df['oversold'] = df['close'] < df['close'].rolling({period}).mean()
df['entry_signal'] = df['mean_rev'] & df['oversold']""",
        params={"period": [20], "threshold": [0.4, 0.45]},
        direction="long",
        lookback=50,
        indicators=[],
        combinable_with=["confirmation", "threshold"],
        strategy_type="HRS",
    ),
    # Hurst Regime Change
    PatternBlock(
        id="HURST_REGIME_CHANGE",
        name="Hurst Regime Change",
        category="hurst_exponent",
        formula_template="""df['returns'] = df['close'].pct_change()
df['std_n'] = df['returns'].rolling({period}).std()
df['std_2n'] = df['returns'].rolling({period} * 2).std()
df['hurst_proxy'] = np.log(df['std_2n'] / (df['std_n'] + 1e-10)) / np.log(2)
df['was_mean_rev'] = df['hurst_proxy'].shift(5) < 0.45
df['now_trending'] = df['hurst_proxy'] > 0.55
df['entry_signal'] = df['was_mean_rev'] & df['now_trending']""",
        params={"period": [20]},
        direction="bidi",
        lookback=50,
        indicators=[],
        combinable_with=["momentum", "volume"],
        strategy_type="HRS",
    ),
]


# =============================================================================
# CHANDELIER EXIT BLOCKS
# =============================================================================

CHANDELIER_EXIT_BLOCKS = [
    # Chandelier Long Entry
    PatternBlock(
        id="CHANDELIER_LONG_ENTRY",
        name="Chandelier Long Entry",
        category="chandelier_exit",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['highest'] = df['high'].rolling({period}).max()
df['chandelier_long'] = df['highest'] - df['atr'] * {mult}
df['above'] = df['close'] > df['chandelier_long']
df['cross_above'] = df['above'] & ~df['above'].shift(1)
df['entry_signal'] = df['cross_above']""",
        params={"period": [22], "mult": [3.0]},
        direction="long",
        lookback=35,
        indicators=["ATR"],
        combinable_with=["volume", "momentum"],
        strategy_type="CHN",
    ),
    # Chandelier Trend Confirm
    PatternBlock(
        id="CHANDELIER_TREND",
        name="Chandelier Trend Confirm",
        category="chandelier_exit",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['highest'] = df['high'].rolling({period}).max()
df['chandelier_long'] = df['highest'] - df['atr'] * {mult}
df['above'] = df['close'] > df['chandelier_long']
df['trend_days'] = df['above'].rolling(5).sum() >= 4
df['entry_signal'] = df['trend_days']""",
        params={"period": [22], "mult": [3.0]},
        direction="long",
        lookback=35,
        indicators=["ATR"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="CHN",
    ),
    # Chandelier Proximity
    PatternBlock(
        id="CHANDELIER_PROXIMITY",
        name="Chandelier Proximity",
        category="chandelier_exit",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['highest'] = df['high'].rolling({period}).max()
df['chandelier_long'] = df['highest'] - df['atr'] * {mult}
df['dist'] = (df['close'] - df['chandelier_long']) / df['close']
df['close_to_stop'] = df['dist'] < {proximity}
df['above'] = df['close'] > df['chandelier_long']
df['entry_signal'] = df['close_to_stop'] & df['above']""",
        params={"period": [22], "mult": [3.0], "proximity": [0.02, 0.03]},
        direction="long",
        lookback=35,
        indicators=["ATR"],
        combinable_with=["volume", "confirmation"],
        strategy_type="CHN",
    ),
]


# =============================================================================
# ELDER IMPULSE BLOCKS
# =============================================================================

ELDER_IMPULSE_BLOCKS = [
    # Elder Impulse Green
    PatternBlock(
        id="ELDER_IMPULSE_GREEN",
        name="Elder Impulse Green",
        category="elder_impulse",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
df['ema_rising'] = df['ema'] > df['ema'].shift(1)
df['hist_rising'] = df['hist'] > df['hist'].shift(1)
df['green'] = df['ema_rising'] & df['hist_rising']
df['entry_signal'] = df['green']""",
        params={"period": [13]},
        direction="long",
        lookback=40,
        indicators=["EMA", "MACD"],
        combinable_with=["volume", "threshold"],
        strategy_type="EIM",
    ),
    # Elder Impulse Green Start
    PatternBlock(
        id="ELDER_IMPULSE_GREEN_START",
        name="Elder Impulse Green Start",
        category="elder_impulse",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
df['ema_rising'] = df['ema'] > df['ema'].shift(1)
df['hist_rising'] = df['hist'] > df['hist'].shift(1)
df['green'] = df['ema_rising'] & df['hist_rising']
df['green_start'] = df['green'] & ~df['green'].shift(1)
df['entry_signal'] = df['green_start']""",
        params={"period": [13]},
        direction="long",
        lookback=40,
        indicators=["EMA", "MACD"],
        combinable_with=["volume", "confirmation"],
        strategy_type="EIM",
    ),
    # Elder Impulse Blue to Green
    PatternBlock(
        id="ELDER_IMPULSE_BLUE_GREEN",
        name="Elder Impulse Blue to Green",
        category="elder_impulse",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
df['ema_rising'] = df['ema'] > df['ema'].shift(1)
df['hist_rising'] = df['hist'] > df['hist'].shift(1)
df['green'] = df['ema_rising'] & df['hist_rising']
df['blue'] = ~df['ema_rising'] & ~df['hist_rising'].shift(1).fillna(False) | ~df['hist_rising'] & df['ema_rising'].shift(1).fillna(False)
df['was_blue'] = ~df['green'].shift(1)
df['now_green'] = df['green']
df['entry_signal'] = df['was_blue'] & df['now_green']""",
        params={"period": [13]},
        direction="long",
        lookback=40,
        indicators=["EMA", "MACD"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="EIM",
    ),
]


# =============================================================================
# DMI ADX EXTENDED BLOCKS
# =============================================================================

DMI_ADX_EXT_BLOCKS = [
    # DMI Cross with ADX Filter
    PatternBlock(
        id="DMI_CROSS_ADX_FILTER",
        name="DMI Cross ADX Filter",
        category="dmi_adx_ext",
        formula_template="""df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod={period})
df['cross_up'] = (df['plus_di'] > df['minus_di']) & (df['plus_di'].shift(1) <= df['minus_di'].shift(1))
df['adx_strong'] = df['adx'] > {adx_thresh}
df['entry_signal'] = df['cross_up'] & df['adx_strong']""",
        params={"period": [14], "adx_thresh": [20, 25]},
        direction="long",
        lookback=30,
        indicators=["PLUS_DI", "MINUS_DI", "ADX"],
        combinable_with=["volume", "confirmation"],
        strategy_type="DMX",
    ),
    # ADX Rising with DI+
    PatternBlock(
        id="ADX_RISING_DI_PLUS",
        name="ADX Rising with DI+",
        category="dmi_adx_ext",
        formula_template="""df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod={period})
df['adx_rising'] = df['adx'] > df['adx'].shift(3)
df['di_positive'] = df['plus_di'] > df['minus_di']
df['entry_signal'] = df['adx_rising'] & df['di_positive']""",
        params={"period": [14]},
        direction="long",
        lookback=30,
        indicators=["PLUS_DI", "MINUS_DI", "ADX"],
        combinable_with=["momentum", "threshold"],
        strategy_type="DMX",
    ),
    # DMI Spread Expanding
    PatternBlock(
        id="DMI_SPREAD_EXPAND",
        name="DMI Spread Expanding",
        category="dmi_adx_ext",
        formula_template="""df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
df['spread'] = df['plus_di'] - df['minus_di']
df['spread_expand'] = df['spread'] > df['spread'].shift(3)
df['positive_spread'] = df['spread'] > {threshold}
df['entry_signal'] = df['spread_expand'] & df['positive_spread']""",
        params={"period": [14], "threshold": [5, 10]},
        direction="long",
        lookback=30,
        indicators=["PLUS_DI", "MINUS_DI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="DMX",
    ),
]


# =============================================================================
# ALMA BLOCKS (Arnaud Legoux MA)
# =============================================================================

ALMA_BLOCKS = [
    # ALMA Cross Up
    PatternBlock(
        id="ALMA_CROSS_UP",
        name="ALMA Cross Up",
        category="alma",
        formula_template="""m = {offset} * ({period} - 1)
s = {period} / {sigma}
weights = np.exp(-((np.arange({period}) - m) ** 2) / (2 * s * s))
weights = weights / weights.sum()
df['alma'] = df['close'].rolling({period}).apply(lambda x: np.sum(weights * x), raw=True)
df['cross_up'] = (df['close'] > df['alma']) & (df['close'].shift(1) <= df['alma'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [9, 14], "offset": [0.85], "sigma": [6]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="ALM",
    ),
    # ALMA Trend
    PatternBlock(
        id="ALMA_TREND",
        name="ALMA Trend Up",
        category="alma",
        formula_template="""m = {offset} * ({period} - 1)
s = {period} / {sigma}
weights = np.exp(-((np.arange({period}) - m) ** 2) / (2 * s * s))
weights = weights / weights.sum()
df['alma'] = df['close'].rolling({period}).apply(lambda x: np.sum(weights * x), raw=True)
df['above'] = df['close'] > df['alma']
df['alma_rising'] = df['alma'] > df['alma'].shift(3)
df['entry_signal'] = df['above'] & df['alma_rising']""",
        params={"period": [9], "offset": [0.85], "sigma": [6]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["confirmation", "threshold"],
        strategy_type="ALM",
    ),
    # ALMA Distance
    PatternBlock(
        id="ALMA_DISTANCE",
        name="ALMA Distance Extreme",
        category="alma",
        formula_template="""m = {offset} * ({period} - 1)
s = {period} / {sigma}
weights = np.exp(-((np.arange({period}) - m) ** 2) / (2 * s * s))
weights = weights / weights.sum()
df['alma'] = df['close'].rolling({period}).apply(lambda x: np.sum(weights * x), raw=True)
df['dist'] = (df['close'] - df['alma']) / df['alma']
df['extreme_low'] = df['dist'] < -{threshold}
df['entry_signal'] = df['extreme_low']""",
        params={"period": [14], "offset": [0.85], "sigma": [6], "threshold": [0.02, 0.03]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="ALM",
    ),
]


# =============================================================================
# VIDYA BLOCKS (Variable Index Dynamic Average)
# =============================================================================

VIDYA_BLOCKS = [
    # VIDYA Cross Up
    PatternBlock(
        id="VIDYA_CROSS_UP",
        name="VIDYA Cross Up",
        category="vidya",
        formula_template="""df['cmo'] = ta.CMO(df['close'], timeperiod={cmo_period})
df['abs_cmo'] = abs(df['cmo']) / 100
df['sc'] = 2 / ({period} + 1)
df['vidya'] = df['close'].copy()
for i in range(1, len(df)):
    df.iloc[i, df.columns.get_loc('vidya')] = df['sc'].iloc[i] * df['abs_cmo'].iloc[i] * df['close'].iloc[i] + (1 - df['sc'].iloc[i] * df['abs_cmo'].iloc[i]) * df['vidya'].iloc[i-1]
df['cross_up'] = (df['close'] > df['vidya']) & (df['close'].shift(1) <= df['vidya'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [14], "cmo_period": [9]},
        direction="long",
        lookback=30,
        indicators=["CMO"],
        combinable_with=["volume", "momentum"],
        strategy_type="VDY",
    ),
    # VIDYA Trend
    PatternBlock(
        id="VIDYA_TREND",
        name="VIDYA Trend Up",
        category="vidya",
        formula_template="""df['cmo'] = ta.CMO(df['close'], timeperiod={cmo_period})
df['abs_cmo'] = abs(df['cmo']) / 100
df['sc'] = 2 / ({period} + 1)
df['vidya'] = df['close'].copy()
for i in range(1, len(df)):
    df.iloc[i, df.columns.get_loc('vidya')] = df['sc'].iloc[i] * df['abs_cmo'].iloc[i] * df['close'].iloc[i] + (1 - df['sc'].iloc[i] * df['abs_cmo'].iloc[i]) * df['vidya'].iloc[i-1]
df['above'] = df['close'] > df['vidya']
df['rising'] = df['vidya'] > df['vidya'].shift(3)
df['entry_signal'] = df['above'] & df['rising']""",
        params={"period": [14], "cmo_period": [9]},
        direction="long",
        lookback=30,
        indicators=["CMO"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="VDY",
    ),
    # VIDYA Momentum Strong
    PatternBlock(
        id="VIDYA_MOMENTUM",
        name="VIDYA Momentum Strong",
        category="vidya",
        formula_template="""df['cmo'] = ta.CMO(df['close'], timeperiod={cmo_period})
df['abs_cmo'] = abs(df['cmo']) / 100
df['strong_cmo'] = df['abs_cmo'] > {threshold}
df['cmo_positive'] = df['cmo'] > 0
df['entry_signal'] = df['strong_cmo'] & df['cmo_positive']""",
        params={"cmo_period": [9], "threshold": [0.4, 0.5]},
        direction="long",
        lookback=20,
        indicators=["CMO"],
        combinable_with=["volume", "confirmation"],
        strategy_type="VDY",
    ),
]


# =============================================================================
# MCGINLEY DYNAMIC BLOCKS
# =============================================================================

MCGINLEY_BLOCKS = [
    # McGinley Cross Up
    PatternBlock(
        id="MCGINLEY_CROSS_UP",
        name="McGinley Cross Up",
        category="mcginley",
        formula_template="""df['md'] = df['close'].copy()
k = 0.6
n = {period}
for i in range(1, len(df)):
    prev_md = df['md'].iloc[i-1]
    curr_close = df['close'].iloc[i]
    ratio = curr_close / (prev_md + 1e-10)
    df.iloc[i, df.columns.get_loc('md')] = prev_md + (curr_close - prev_md) / (n * (ratio ** 4) + 1e-10)
df['cross_up'] = (df['close'] > df['md']) & (df['close'].shift(1) <= df['md'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="MCG",
    ),
    # McGinley Trend
    PatternBlock(
        id="MCGINLEY_TREND",
        name="McGinley Trend Up",
        category="mcginley",
        formula_template="""df['md'] = df['close'].copy()
n = {period}
for i in range(1, len(df)):
    prev_md = df['md'].iloc[i-1]
    curr_close = df['close'].iloc[i]
    ratio = curr_close / (prev_md + 1e-10)
    df.iloc[i, df.columns.get_loc('md')] = prev_md + (curr_close - prev_md) / (n * (ratio ** 4) + 1e-10)
df['above'] = df['close'] > df['md']
df['md_rising'] = df['md'] > df['md'].shift(3)
df['entry_signal'] = df['above'] & df['md_rising']""",
        params={"period": [10]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["confirmation", "threshold"],
        strategy_type="MCG",
    ),
    # McGinley Proximity
    PatternBlock(
        id="MCGINLEY_PROXIMITY",
        name="McGinley Proximity",
        category="mcginley",
        formula_template="""df['md'] = df['close'].copy()
n = {period}
for i in range(1, len(df)):
    prev_md = df['md'].iloc[i-1]
    curr_close = df['close'].iloc[i]
    ratio = curr_close / (prev_md + 1e-10)
    df.iloc[i, df.columns.get_loc('md')] = prev_md + (curr_close - prev_md) / (n * (ratio ** 4) + 1e-10)
df['dist'] = abs(df['close'] - df['md']) / df['close']
df['close_to_md'] = df['dist'] < {threshold}
df['above'] = df['close'] > df['md']
df['entry_signal'] = df['close_to_md'] & df['above']""",
        params={"period": [10], "threshold": [0.005, 0.01]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="MCG",
    ),
]


# =============================================================================
# T3 MA BLOCKS (Tillson)
# =============================================================================

T3_MA_BLOCKS = [
    # T3 Cross Up
    PatternBlock(
        id="T3_CROSS_UP",
        name="T3 Cross Up",
        category="t3_ma",
        formula_template="""vf = {vfactor}
df['ema1'] = ta.EMA(df['close'], timeperiod={period})
df['ema2'] = ta.EMA(df['ema1'], timeperiod={period})
df['ema3'] = ta.EMA(df['ema2'], timeperiod={period})
df['ema4'] = ta.EMA(df['ema3'], timeperiod={period})
df['ema5'] = ta.EMA(df['ema4'], timeperiod={period})
df['ema6'] = ta.EMA(df['ema5'], timeperiod={period})
c1 = -vf**3
c2 = 3*vf**2 + 3*vf**3
c3 = -6*vf**2 - 3*vf - 3*vf**3
c4 = 1 + 3*vf + vf**3 + 3*vf**2
df['t3'] = c1*df['ema6'] + c2*df['ema5'] + c3*df['ema4'] + c4*df['ema3']
df['cross_up'] = (df['close'] > df['t3']) & (df['close'].shift(1) <= df['t3'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [5], "vfactor": [0.7]},
        direction="long",
        lookback=40,
        indicators=["EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="T3M",
    ),
    # T3 Trend
    PatternBlock(
        id="T3_TREND",
        name="T3 Trend Up",
        category="t3_ma",
        formula_template="""vf = {vfactor}
df['ema1'] = ta.EMA(df['close'], timeperiod={period})
df['ema2'] = ta.EMA(df['ema1'], timeperiod={period})
df['ema3'] = ta.EMA(df['ema2'], timeperiod={period})
df['ema4'] = ta.EMA(df['ema3'], timeperiod={period})
df['ema5'] = ta.EMA(df['ema4'], timeperiod={period})
df['ema6'] = ta.EMA(df['ema5'], timeperiod={period})
c1 = -vf**3
c2 = 3*vf**2 + 3*vf**3
c3 = -6*vf**2 - 3*vf - 3*vf**3
c4 = 1 + 3*vf + vf**3 + 3*vf**2
df['t3'] = c1*df['ema6'] + c2*df['ema5'] + c3*df['ema4'] + c4*df['ema3']
df['above'] = df['close'] > df['t3']
df['rising'] = df['t3'] > df['t3'].shift(3)
df['entry_signal'] = df['above'] & df['rising']""",
        params={"period": [5], "vfactor": [0.7]},
        direction="long",
        lookback=40,
        indicators=["EMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="T3M",
    ),
    # T3 Slope Strong
    PatternBlock(
        id="T3_SLOPE",
        name="T3 Slope Strong",
        category="t3_ma",
        formula_template="""vf = {vfactor}
df['ema1'] = ta.EMA(df['close'], timeperiod={period})
df['ema2'] = ta.EMA(df['ema1'], timeperiod={period})
df['ema3'] = ta.EMA(df['ema2'], timeperiod={period})
df['ema4'] = ta.EMA(df['ema3'], timeperiod={period})
df['ema5'] = ta.EMA(df['ema4'], timeperiod={period})
df['ema6'] = ta.EMA(df['ema5'], timeperiod={period})
c1 = -vf**3
c2 = 3*vf**2 + 3*vf**3
c3 = -6*vf**2 - 3*vf - 3*vf**3
c4 = 1 + 3*vf + vf**3 + 3*vf**2
df['t3'] = c1*df['ema6'] + c2*df['ema5'] + c3*df['ema4'] + c4*df['ema3']
df['slope'] = (df['t3'] - df['t3'].shift(3)) / df['t3'].shift(3)
df['strong_up'] = df['slope'] > {threshold}
df['entry_signal'] = df['strong_up']""",
        params={"period": [5], "vfactor": [0.7], "threshold": [0.01, 0.015]},
        direction="long",
        lookback=40,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="T3M",
    ),
]


# =============================================================================
# JURIK MA BLOCKS (simplified adaptive)
# =============================================================================

JURIK_MA_BLOCKS = [
    # Jurik Cross Up
    PatternBlock(
        id="JURIK_CROSS_UP",
        name="Jurik Cross Up",
        category="jurik_ma",
        formula_template="""df['vol'] = df['close'].rolling({period}).std()
df['vol_ratio'] = df['vol'] / df['vol'].rolling({period} * 2).mean()
df['alpha'] = df['vol_ratio'].clip(0.1, 1.0)
df['jma'] = df['close'].copy()
for i in range(1, len(df)):
    a = df['alpha'].iloc[i] * {phase}
    df.iloc[i, df.columns.get_loc('jma')] = a * df['close'].iloc[i] + (1 - a) * df['jma'].iloc[i-1]
df['cross_up'] = (df['close'] > df['jma']) & (df['close'].shift(1) <= df['jma'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [10], "phase": [0.5]},
        direction="long",
        lookback=35,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="JMA",
    ),
    # Jurik Trend
    PatternBlock(
        id="JURIK_TREND",
        name="Jurik Trend Up",
        category="jurik_ma",
        formula_template="""df['vol'] = df['close'].rolling({period}).std()
df['vol_ratio'] = df['vol'] / df['vol'].rolling({period} * 2).mean()
df['alpha'] = df['vol_ratio'].clip(0.1, 1.0)
df['jma'] = df['close'].copy()
for i in range(1, len(df)):
    a = df['alpha'].iloc[i] * {phase}
    df.iloc[i, df.columns.get_loc('jma')] = a * df['close'].iloc[i] + (1 - a) * df['jma'].iloc[i-1]
df['above'] = df['close'] > df['jma']
df['jma_rising'] = df['jma'] > df['jma'].shift(3)
df['entry_signal'] = df['above'] & df['jma_rising']""",
        params={"period": [10], "phase": [0.5]},
        direction="long",
        lookback=35,
        indicators=[],
        combinable_with=["confirmation", "threshold"],
        strategy_type="JMA",
    ),
    # Jurik Adaptive
    PatternBlock(
        id="JURIK_ADAPTIVE",
        name="Jurik Adaptive Entry",
        category="jurik_ma",
        formula_template="""df['vol'] = df['close'].rolling({period}).std()
df['vol_ratio'] = df['vol'] / df['vol'].rolling({period} * 2).mean()
df['high_adapt'] = df['vol_ratio'] > 1.0
df['trend_up'] = df['close'] > df['close'].shift(5)
df['entry_signal'] = df['high_adapt'] & df['trend_up']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=35,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="JMA",
    ),
]


# =============================================================================
# ZERO LAG MA BLOCKS
# =============================================================================

ZERO_LAG_MA_BLOCKS = [
    # Zero Lag EMA Cross Up
    PatternBlock(
        id="ZLEMA_CROSS_UP",
        name="Zero Lag EMA Cross Up",
        category="zero_lag_ma",
        formula_template="""lag = ({period} - 1) // 2
df['zlema_data'] = 2 * df['close'] - df['close'].shift(lag)
df['zlema'] = ta.EMA(df['zlema_data'], timeperiod={period})
df['cross_up'] = (df['close'] > df['zlema']) & (df['close'].shift(1) <= df['zlema'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [10, 20]},
        direction="long",
        lookback=30,
        indicators=["EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="ZLM",
    ),
    # Zero Lag EMA Trend
    PatternBlock(
        id="ZLEMA_TREND",
        name="Zero Lag EMA Trend",
        category="zero_lag_ma",
        formula_template="""lag = ({period} - 1) // 2
df['zlema_data'] = 2 * df['close'] - df['close'].shift(lag)
df['zlema'] = ta.EMA(df['zlema_data'], timeperiod={period})
df['above'] = df['close'] > df['zlema']
df['rising'] = df['zlema'] > df['zlema'].shift(3)
df['entry_signal'] = df['above'] & df['rising']""",
        params={"period": [12, 20]},
        direction="long",
        lookback=35,
        indicators=["EMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="ZLM",
    ),
    # Zero Lag Dual Cross
    PatternBlock(
        id="ZLEMA_DUAL_CROSS",
        name="Zero Lag Dual Cross",
        category="zero_lag_ma",
        formula_template="""lag_fast = ({fast} - 1) // 2
lag_slow = ({slow} - 1) // 2
df['zl_fast_data'] = 2 * df['close'] - df['close'].shift(lag_fast)
df['zl_slow_data'] = 2 * df['close'] - df['close'].shift(lag_slow)
df['zlema_fast'] = ta.EMA(df['zl_fast_data'], timeperiod={fast})
df['zlema_slow'] = ta.EMA(df['zl_slow_data'], timeperiod={slow})
df['cross_up'] = (df['zlema_fast'] > df['zlema_slow']) & (df['zlema_fast'].shift(1) <= df['zlema_slow'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"fast": [8], "slow": [21]},
        direction="long",
        lookback=35,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="ZLM",
    ),
]


# =============================================================================
# HULL MA BLOCKS
# =============================================================================

HULL_MA_BLOCKS = [
    # Hull MA Cross Up
    PatternBlock(
        id="HMA_CROSS_UP",
        name="Hull MA Cross Up",
        category="hull_ma",
        formula_template="""half_period = {period} // 2
sqrt_period = int(np.sqrt({period}))
df['wma_half'] = ta.WMA(df['close'], timeperiod=half_period)
df['wma_full'] = ta.WMA(df['close'], timeperiod={period})
df['hma_raw'] = 2 * df['wma_half'] - df['wma_full']
df['hma'] = ta.WMA(df['hma_raw'], timeperiod=sqrt_period)
df['cross_up'] = (df['close'] > df['hma']) & (df['close'].shift(1) <= df['hma'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [9, 16]},
        direction="long",
        lookback=30,
        indicators=["WMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="HMA",
    ),
    # Hull MA Trend
    PatternBlock(
        id="HMA_TREND",
        name="Hull MA Trend",
        category="hull_ma",
        formula_template="""half_period = {period} // 2
sqrt_period = int(np.sqrt({period}))
df['wma_half'] = ta.WMA(df['close'], timeperiod=half_period)
df['wma_full'] = ta.WMA(df['close'], timeperiod={period})
df['hma_raw'] = 2 * df['wma_half'] - df['wma_full']
df['hma'] = ta.WMA(df['hma_raw'], timeperiod=sqrt_period)
df['above'] = df['close'] > df['hma']
df['rising'] = df['hma'] > df['hma'].shift(2)
df['entry_signal'] = df['above'] & df['rising']""",
        params={"period": [9, 14]},
        direction="long",
        lookback=30,
        indicators=["WMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="HMA",
    ),
    # Hull MA Color Change
    PatternBlock(
        id="HMA_COLOR_CHANGE",
        name="Hull MA Color Change",
        category="hull_ma",
        formula_template="""half_period = {period} // 2
sqrt_period = int(np.sqrt({period}))
df['wma_half'] = ta.WMA(df['close'], timeperiod=half_period)
df['wma_full'] = ta.WMA(df['close'], timeperiod={period})
df['hma_raw'] = 2 * df['wma_half'] - df['wma_full']
df['hma'] = ta.WMA(df['hma_raw'], timeperiod=sqrt_period)
df['hma_rising'] = df['hma'] > df['hma'].shift(1)
df['was_falling'] = df['hma'].shift(1) < df['hma'].shift(2)
df['color_change'] = df['hma_rising'] & df['was_falling']
df['entry_signal'] = df['color_change']""",
        params={"period": [9, 16]},
        direction="long",
        lookback=30,
        indicators=["WMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="HMA",
    ),
]


# =============================================================================
# LAGUERRE BLOCKS
# =============================================================================

LAGUERRE_BLOCKS = [
    # Laguerre RSI Oversold
    PatternBlock(
        id="LAGUERRE_RSI_OVERSOLD",
        name="Laguerre RSI Oversold",
        category="laguerre",
        formula_template="""gamma = {gamma}
df['L0'] = (1 - gamma) * df['close'] + gamma * df['close'].shift(1).fillna(df['close'])
df['L1'] = -gamma * df['L0'] + df['L0'].shift(1).fillna(df['L0']) + gamma * df['L0'].shift(1).fillna(df['L0'])
df['L2'] = -gamma * df['L1'] + df['L1'].shift(1).fillna(df['L1']) + gamma * df['L1'].shift(1).fillna(df['L1'])
df['L3'] = -gamma * df['L2'] + df['L2'].shift(1).fillna(df['L2']) + gamma * df['L2'].shift(1).fillna(df['L2'])
df['cu'] = np.where(df['L0'] >= df['L1'], df['L0'] - df['L1'], 0) + np.where(df['L1'] >= df['L2'], df['L1'] - df['L2'], 0) + np.where(df['L2'] >= df['L3'], df['L2'] - df['L3'], 0)
df['cd'] = np.where(df['L0'] < df['L1'], df['L1'] - df['L0'], 0) + np.where(df['L1'] < df['L2'], df['L2'] - df['L1'], 0) + np.where(df['L2'] < df['L3'], df['L3'] - df['L2'], 0)
df['lrsi'] = df['cu'] / (df['cu'] + df['cd'] + 1e-10)
df['oversold'] = df['lrsi'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"gamma": [0.7, 0.8], "level": [0.2, 0.25]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="LAG",
    ),
    # Laguerre RSI Cross Up
    PatternBlock(
        id="LAGUERRE_RSI_CROSS",
        name="Laguerre RSI Cross Up",
        category="laguerre",
        formula_template="""gamma = {gamma}
df['L0'] = (1 - gamma) * df['close'] + gamma * df['close'].shift(1).fillna(df['close'])
df['L1'] = -gamma * df['L0'] + df['L0'].shift(1).fillna(df['L0']) + gamma * df['L0'].shift(1).fillna(df['L0'])
df['L2'] = -gamma * df['L1'] + df['L1'].shift(1).fillna(df['L1']) + gamma * df['L1'].shift(1).fillna(df['L1'])
df['L3'] = -gamma * df['L2'] + df['L2'].shift(1).fillna(df['L2']) + gamma * df['L2'].shift(1).fillna(df['L2'])
df['cu'] = np.where(df['L0'] >= df['L1'], df['L0'] - df['L1'], 0) + np.where(df['L1'] >= df['L2'], df['L1'] - df['L2'], 0) + np.where(df['L2'] >= df['L3'], df['L2'] - df['L3'], 0)
df['cd'] = np.where(df['L0'] < df['L1'], df['L1'] - df['L0'], 0) + np.where(df['L1'] < df['L2'], df['L2'] - df['L1'], 0) + np.where(df['L2'] < df['L3'], df['L3'] - df['L2'], 0)
df['lrsi'] = df['cu'] / (df['cu'] + df['cd'] + 1e-10)
df['cross_up'] = (df['lrsi'] > {level}) & (df['lrsi'].shift(1) <= {level})
df['entry_signal'] = df['cross_up']""",
        params={"gamma": [0.7], "level": [0.2, 0.3]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="LAG",
    ),
    # Laguerre RSI Rising
    PatternBlock(
        id="LAGUERRE_RSI_RISING",
        name="Laguerre RSI Rising",
        category="laguerre",
        formula_template="""gamma = {gamma}
df['L0'] = (1 - gamma) * df['close'] + gamma * df['close'].shift(1).fillna(df['close'])
df['L1'] = -gamma * df['L0'] + df['L0'].shift(1).fillna(df['L0']) + gamma * df['L0'].shift(1).fillna(df['L0'])
df['L2'] = -gamma * df['L1'] + df['L1'].shift(1).fillna(df['L1']) + gamma * df['L1'].shift(1).fillna(df['L1'])
df['L3'] = -gamma * df['L2'] + df['L2'].shift(1).fillna(df['L2']) + gamma * df['L2'].shift(1).fillna(df['L2'])
df['cu'] = np.where(df['L0'] >= df['L1'], df['L0'] - df['L1'], 0) + np.where(df['L1'] >= df['L2'], df['L1'] - df['L2'], 0) + np.where(df['L2'] >= df['L3'], df['L2'] - df['L3'], 0)
df['cd'] = np.where(df['L0'] < df['L1'], df['L1'] - df['L0'], 0) + np.where(df['L1'] < df['L2'], df['L2'] - df['L1'], 0) + np.where(df['L2'] < df['L3'], df['L3'] - df['L2'], 0)
df['lrsi'] = df['cu'] / (df['cu'] + df['cd'] + 1e-10)
df['rising'] = df['lrsi'] > df['lrsi'].shift(1)
df['above_mid'] = df['lrsi'] > 0.5
df['entry_signal'] = df['rising'] & df['above_mid']""",
        params={"gamma": [0.7, 0.8]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="LAG",
    ),
]


# =============================================================================
# STOCHASTIC EXTENDED BLOCKS
# =============================================================================

STOCHASTIC_EXT_BLOCKS = [
    # Stochastic Pop
    PatternBlock(
        id="STOCH_POP",
        name="Stochastic Pop",
        category="stochastic_ext",
        formula_template="""df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period={period}, slowk_period=3, slowd_period=3)
df['was_oversold'] = df['slowk'].shift(3) < {oversold}
df['now_above'] = df['slowk'] > {pop_level}
df['pop'] = df['was_oversold'] & df['now_above']
df['entry_signal'] = df['pop']""",
        params={"period": [14], "oversold": [20, 25], "pop_level": [50, 60]},
        direction="long",
        lookback=30,
        indicators=["STOCH"],
        combinable_with=["volume", "momentum"],
        strategy_type="STE",
    ),
    # Stochastic Hook
    PatternBlock(
        id="STOCH_HOOK",
        name="Stochastic Hook",
        category="stochastic_ext",
        formula_template="""df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period={period}, slowk_period=3, slowd_period=3)
df['oversold'] = df['slowk'] < {level}
df['k_turning'] = (df['slowk'] > df['slowk'].shift(1)) & (df['slowk'].shift(1) < df['slowk'].shift(2))
df['hook'] = df['oversold'] & df['k_turning']
df['entry_signal'] = df['hook']""",
        params={"period": [14], "level": [20, 30]},
        direction="long",
        lookback=25,
        indicators=["STOCH"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="STE",
    ),
    # Stochastic Momentum
    PatternBlock(
        id="STOCH_MOMENTUM",
        name="Stochastic Momentum",
        category="stochastic_ext",
        formula_template="""df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period={period}, slowk_period=3, slowd_period=3)
df['k_momentum'] = df['slowk'] - df['slowk'].shift(5)
df['strong_momentum'] = df['k_momentum'] > {threshold}
df['k_above_d'] = df['slowk'] > df['slowd']
df['entry_signal'] = df['strong_momentum'] & df['k_above_d']""",
        params={"period": [14], "threshold": [20, 30]},
        direction="long",
        lookback=30,
        indicators=["STOCH"],
        combinable_with=["volume", "confirmation"],
        strategy_type="STE",
    ),
]


# =============================================================================
# WILLIAMS AD BLOCKS
# =============================================================================

WILLIAMS_AD_BLOCKS = [
    # Williams AD Rising
    PatternBlock(
        id="WAD_RISING",
        name="Williams AD Rising",
        category="williams_ad",
        formula_template="""df['trh'] = np.maximum(df['high'], df['close'].shift(1))
df['trl'] = np.minimum(df['low'], df['close'].shift(1))
df['ad'] = np.where(df['close'] > df['close'].shift(1), df['close'] - df['trl'], np.where(df['close'] < df['close'].shift(1), df['close'] - df['trh'], 0))
df['wad'] = df['ad'].cumsum()
df['wad_ma'] = df['wad'].rolling({period}).mean()
df['rising'] = df['wad'] > df['wad_ma']
df['wad_up'] = df['wad'] > df['wad'].shift(3)
df['entry_signal'] = df['rising'] & df['wad_up']""",
        params={"period": [14, 20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="WAX",
    ),
    # Williams AD Divergence
    PatternBlock(
        id="WAD_DIVERGENCE",
        name="Williams AD Divergence",
        category="williams_ad",
        formula_template="""df['trh'] = np.maximum(df['high'], df['close'].shift(1))
df['trl'] = np.minimum(df['low'], df['close'].shift(1))
df['ad'] = np.where(df['close'] > df['close'].shift(1), df['close'] - df['trl'], np.where(df['close'] < df['close'].shift(1), df['close'] - df['trh'], 0))
df['wad'] = df['ad'].cumsum()
df['price_lower'] = df['close'] < df['close'].shift({lookback})
df['wad_higher'] = df['wad'] > df['wad'].shift({lookback})
df['divergence'] = df['price_lower'] & df['wad_higher']
df['entry_signal'] = df['divergence']""",
        params={"lookback": [5, 10]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["confirmation", "threshold"],
        strategy_type="WAX",
    ),
    # Williams AD Breakout
    PatternBlock(
        id="WAD_BREAKOUT",
        name="Williams AD Breakout",
        category="williams_ad",
        formula_template="""df['trh'] = np.maximum(df['high'], df['close'].shift(1))
df['trl'] = np.minimum(df['low'], df['close'].shift(1))
df['ad'] = np.where(df['close'] > df['close'].shift(1), df['close'] - df['trl'], np.where(df['close'] < df['close'].shift(1), df['close'] - df['trh'], 0))
df['wad'] = df['ad'].cumsum()
df['wad_high'] = df['wad'].rolling({period}).max()
df['breakout'] = df['wad'] > df['wad_high'].shift(1)
df['entry_signal'] = df['breakout']""",
        params={"period": [20, 30]},
        direction="long",
        lookback=40,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="WAX",
    ),
]


# =============================================================================
# POSITIVE VOLUME INDEX BLOCKS
# =============================================================================

POSITIVE_VOLUME_BLOCKS = [
    # PVI Cross Up
    PatternBlock(
        id="PVI_CROSS_UP",
        name="PVI Cross Up",
        category="positive_volume",
        formula_template="""df['vol_up'] = df['volume'] > df['volume'].shift(1)
df['ret'] = df['close'].pct_change()
df['pvi_change'] = np.where(df['vol_up'], df['ret'], 0)
df['pvi'] = (1 + df['pvi_change']).cumprod() * 1000
df['pvi_ma'] = ta.EMA(df['pvi'], timeperiod={period})
df['cross_up'] = (df['pvi'] > df['pvi_ma']) & (df['pvi'].shift(1) <= df['pvi_ma'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [255]},
        direction="long",
        lookback=270,
        indicators=["EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="PVI",
    ),
    # PVI Above MA
    PatternBlock(
        id="PVI_ABOVE_MA",
        name="PVI Above MA",
        category="positive_volume",
        formula_template="""df['vol_up'] = df['volume'] > df['volume'].shift(1)
df['ret'] = df['close'].pct_change()
df['pvi_change'] = np.where(df['vol_up'], df['ret'], 0)
df['pvi'] = (1 + df['pvi_change']).cumprod() * 1000
df['pvi_ma'] = ta.SMA(df['pvi'], timeperiod={period})
df['above'] = df['pvi'] > df['pvi_ma']
df['rising'] = df['pvi'] > df['pvi'].shift(5)
df['entry_signal'] = df['above'] & df['rising']""",
        params={"period": [100, 200]},
        direction="long",
        lookback=220,
        indicators=["SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="PVI",
    ),
    # PVI Rising Fast
    PatternBlock(
        id="PVI_RISING_FAST",
        name="PVI Rising Fast",
        category="positive_volume",
        formula_template="""df['vol_up'] = df['volume'] > df['volume'].shift(1)
df['ret'] = df['close'].pct_change()
df['pvi_change'] = np.where(df['vol_up'], df['ret'], 0)
df['pvi'] = (1 + df['pvi_change']).cumprod() * 1000
df['pvi_roc'] = (df['pvi'] - df['pvi'].shift({period})) / df['pvi'].shift({period}) * 100
df['fast_rise'] = df['pvi_roc'] > {threshold}
df['entry_signal'] = df['fast_rise']""",
        params={"period": [20], "threshold": [1, 2]},
        direction="long",
        lookback=50,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="PVI",
    ),
]


# =============================================================================
# NEGATIVE VOLUME INDEX BLOCKS
# =============================================================================

NEGATIVE_VOLUME_BLOCKS = [
    # NVI Cross Up
    PatternBlock(
        id="NVI_CROSS_UP",
        name="NVI Cross Up",
        category="negative_volume",
        formula_template="""df['vol_down'] = df['volume'] < df['volume'].shift(1)
df['ret'] = df['close'].pct_change()
df['nvi_change'] = np.where(df['vol_down'], df['ret'], 0)
df['nvi'] = (1 + df['nvi_change']).cumprod() * 1000
df['nvi_ma'] = ta.EMA(df['nvi'], timeperiod={period})
df['cross_up'] = (df['nvi'] > df['nvi_ma']) & (df['nvi'].shift(1) <= df['nvi_ma'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [255]},
        direction="long",
        lookback=270,
        indicators=["EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="NVI",
    ),
    # NVI Above MA
    PatternBlock(
        id="NVI_ABOVE_MA",
        name="NVI Above MA",
        category="negative_volume",
        formula_template="""df['vol_down'] = df['volume'] < df['volume'].shift(1)
df['ret'] = df['close'].pct_change()
df['nvi_change'] = np.where(df['vol_down'], df['ret'], 0)
df['nvi'] = (1 + df['nvi_change']).cumprod() * 1000
df['nvi_ma'] = ta.SMA(df['nvi'], timeperiod={period})
df['above'] = df['nvi'] > df['nvi_ma']
df['rising'] = df['nvi'] > df['nvi'].shift(5)
df['entry_signal'] = df['above'] & df['rising']""",
        params={"period": [100, 200]},
        direction="long",
        lookback=220,
        indicators=["SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="NVI",
    ),
    # NVI Smart Money
    PatternBlock(
        id="NVI_SMART_MONEY",
        name="NVI Smart Money Signal",
        category="negative_volume",
        formula_template="""df['vol_down'] = df['volume'] < df['volume'].shift(1)
df['ret'] = df['close'].pct_change()
df['nvi_change'] = np.where(df['vol_down'], df['ret'], 0)
df['nvi'] = (1 + df['nvi_change']).cumprod() * 1000
df['nvi_trend'] = df['nvi'] > df['nvi'].shift({period})
df['price_trend'] = df['close'] > df['close'].shift({period})
df['smart'] = df['nvi_trend'] & df['price_trend']
df['entry_signal'] = df['smart']""",
        params={"period": [20, 50]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["confirmation", "threshold"],
        strategy_type="NVI",
    ),
]


# =============================================================================
# INERTIA BLOCKS
# =============================================================================

INERTIA_BLOCKS = [
    # Inertia Rising
    PatternBlock(
        id="INERTIA_RISING",
        name="Inertia Rising",
        category="inertia",
        formula_template="""df['rvi_num'] = (df['close'] - df['open']) + 2 * (df['close'].shift(1) - df['open'].shift(1)) + 2 * (df['close'].shift(2) - df['open'].shift(2)) + (df['close'].shift(3) - df['open'].shift(3))
df['rvi_den'] = (df['high'] - df['low']) + 2 * (df['high'].shift(1) - df['low'].shift(1)) + 2 * (df['high'].shift(2) - df['low'].shift(2)) + (df['high'].shift(3) - df['low'].shift(3))
df['rvi'] = df['rvi_num'].rolling({period}).sum() / (df['rvi_den'].rolling({period}).sum() + 1e-10)
df['inertia'] = ta.LINEARREG(df['rvi'], timeperiod={period})
df['rising'] = df['inertia'] > df['inertia'].shift(1)
df['positive'] = df['inertia'] > 0
df['entry_signal'] = df['rising'] & df['positive']""",
        params={"period": [14, 20]},
        direction="long",
        lookback=35,
        indicators=["LINEARREG"],
        combinable_with=["volume", "momentum"],
        strategy_type="INR",
    ),
    # Inertia Cross Zero
    PatternBlock(
        id="INERTIA_CROSS_ZERO",
        name="Inertia Cross Zero",
        category="inertia",
        formula_template="""df['rvi_num'] = (df['close'] - df['open']) + 2 * (df['close'].shift(1) - df['open'].shift(1)) + 2 * (df['close'].shift(2) - df['open'].shift(2)) + (df['close'].shift(3) - df['open'].shift(3))
df['rvi_den'] = (df['high'] - df['low']) + 2 * (df['high'].shift(1) - df['low'].shift(1)) + 2 * (df['high'].shift(2) - df['low'].shift(2)) + (df['high'].shift(3) - df['low'].shift(3))
df['rvi'] = df['rvi_num'].rolling({period}).sum() / (df['rvi_den'].rolling({period}).sum() + 1e-10)
df['inertia'] = ta.LINEARREG(df['rvi'], timeperiod={period})
df['cross_up'] = (df['inertia'] > 0) & (df['inertia'].shift(1) <= 0)
df['entry_signal'] = df['cross_up']""",
        params={"period": [14, 20]},
        direction="long",
        lookback=35,
        indicators=["LINEARREG"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="INR",
    ),
    # Inertia Strong
    PatternBlock(
        id="INERTIA_STRONG",
        name="Inertia Strong",
        category="inertia",
        formula_template="""df['rvi_num'] = (df['close'] - df['open']) + 2 * (df['close'].shift(1) - df['open'].shift(1)) + 2 * (df['close'].shift(2) - df['open'].shift(2)) + (df['close'].shift(3) - df['open'].shift(3))
df['rvi_den'] = (df['high'] - df['low']) + 2 * (df['high'].shift(1) - df['low'].shift(1)) + 2 * (df['high'].shift(2) - df['low'].shift(2)) + (df['high'].shift(3) - df['low'].shift(3))
df['rvi'] = df['rvi_num'].rolling({period}).sum() / (df['rvi_den'].rolling({period}).sum() + 1e-10)
df['inertia'] = ta.LINEARREG(df['rvi'], timeperiod={period})
df['strong'] = df['inertia'] > {threshold}
df['entry_signal'] = df['strong']""",
        params={"period": [14], "threshold": [0.3, 0.4]},
        direction="long",
        lookback=30,
        indicators=["LINEARREG"],
        combinable_with=["volume", "confirmation"],
        strategy_type="INR",
    ),
]


# =============================================================================
# KNOW SURE THING (KST) BLOCKS
# =============================================================================

KNOW_SURE_THING_BLOCKS = [
    # KST Cross Up
    PatternBlock(
        id="KST_CROSS_UP",
        name="KST Cross Up",
        category="know_sure_thing",
        formula_template="""df['roc1'] = ta.ROC(df['close'], timeperiod=10)
df['roc2'] = ta.ROC(df['close'], timeperiod=15)
df['roc3'] = ta.ROC(df['close'], timeperiod=20)
df['roc4'] = ta.ROC(df['close'], timeperiod=30)
df['kst'] = ta.SMA(df['roc1'], timeperiod=10) * 1 + ta.SMA(df['roc2'], timeperiod=10) * 2 + ta.SMA(df['roc3'], timeperiod=10) * 3 + ta.SMA(df['roc4'], timeperiod=15) * 4
df['signal'] = ta.SMA(df['kst'], timeperiod=9)
df['cross_up'] = (df['kst'] > df['signal']) & (df['kst'].shift(1) <= df['signal'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={},
        direction="long",
        lookback=50,
        indicators=["ROC", "SMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="KST",
    ),
    # KST Positive
    PatternBlock(
        id="KST_POSITIVE",
        name="KST Positive Zone",
        category="know_sure_thing",
        formula_template="""df['roc1'] = ta.ROC(df['close'], timeperiod=10)
df['roc2'] = ta.ROC(df['close'], timeperiod=15)
df['roc3'] = ta.ROC(df['close'], timeperiod=20)
df['roc4'] = ta.ROC(df['close'], timeperiod=30)
df['kst'] = ta.SMA(df['roc1'], timeperiod=10) * 1 + ta.SMA(df['roc2'], timeperiod=10) * 2 + ta.SMA(df['roc3'], timeperiod=10) * 3 + ta.SMA(df['roc4'], timeperiod=15) * 4
df['positive'] = df['kst'] > 0
df['rising'] = df['kst'] > df['kst'].shift(3)
df['entry_signal'] = df['positive'] & df['rising']""",
        params={},
        direction="long",
        lookback=50,
        indicators=["ROC", "SMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="KST",
    ),
    # KST Zero Cross
    PatternBlock(
        id="KST_ZERO_CROSS",
        name="KST Zero Cross",
        category="know_sure_thing",
        formula_template="""df['roc1'] = ta.ROC(df['close'], timeperiod=10)
df['roc2'] = ta.ROC(df['close'], timeperiod=15)
df['roc3'] = ta.ROC(df['close'], timeperiod=20)
df['roc4'] = ta.ROC(df['close'], timeperiod=30)
df['kst'] = ta.SMA(df['roc1'], timeperiod=10) * 1 + ta.SMA(df['roc2'], timeperiod=10) * 2 + ta.SMA(df['roc3'], timeperiod=10) * 3 + ta.SMA(df['roc4'], timeperiod=15) * 4
df['cross_zero'] = (df['kst'] > 0) & (df['kst'].shift(1) <= 0)
df['entry_signal'] = df['cross_zero']""",
        params={},
        direction="long",
        lookback=50,
        indicators=["ROC", "SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="KST",
    ),
]


# =============================================================================
# SPECIAL K BLOCKS
# =============================================================================

SPECIAL_K_BLOCKS = [
    # Special K Rising
    PatternBlock(
        id="SPECIAL_K_RISING",
        name="Special K Rising",
        category="special_k",
        formula_template="""df['roc10'] = ta.ROC(df['close'], timeperiod=10)
df['roc15'] = ta.ROC(df['close'], timeperiod=15)
df['roc20'] = ta.ROC(df['close'], timeperiod=20)
df['roc30'] = ta.ROC(df['close'], timeperiod=30)
df['roc40'] = ta.ROC(df['close'], timeperiod=40)
df['roc65'] = ta.ROC(df['close'], timeperiod=65)
df['spk'] = ta.SMA(df['roc10'], timeperiod=10) + ta.SMA(df['roc15'], timeperiod=10) * 2 + ta.SMA(df['roc20'], timeperiod=10) * 3 + ta.SMA(df['roc30'], timeperiod=15) * 4 + ta.SMA(df['roc40'], timeperiod=50) + ta.SMA(df['roc65'], timeperiod=65) * 2
df['rising'] = df['spk'] > df['spk'].shift(3)
df['positive'] = df['spk'] > 0
df['entry_signal'] = df['rising'] & df['positive']""",
        params={},
        direction="long",
        lookback=150,
        indicators=["ROC", "SMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="SPK",
    ),
    # Special K Cross Zero
    PatternBlock(
        id="SPECIAL_K_ZERO_CROSS",
        name="Special K Zero Cross",
        category="special_k",
        formula_template="""df['roc10'] = ta.ROC(df['close'], timeperiod=10)
df['roc15'] = ta.ROC(df['close'], timeperiod=15)
df['roc20'] = ta.ROC(df['close'], timeperiod=20)
df['roc30'] = ta.ROC(df['close'], timeperiod=30)
df['roc40'] = ta.ROC(df['close'], timeperiod=40)
df['roc65'] = ta.ROC(df['close'], timeperiod=65)
df['spk'] = ta.SMA(df['roc10'], timeperiod=10) + ta.SMA(df['roc15'], timeperiod=10) * 2 + ta.SMA(df['roc20'], timeperiod=10) * 3 + ta.SMA(df['roc30'], timeperiod=15) * 4 + ta.SMA(df['roc40'], timeperiod=50) + ta.SMA(df['roc65'], timeperiod=65) * 2
df['cross_zero'] = (df['spk'] > 0) & (df['spk'].shift(1) <= 0)
df['entry_signal'] = df['cross_zero']""",
        params={},
        direction="long",
        lookback=150,
        indicators=["ROC", "SMA"],
        combinable_with=["volume", "threshold"],
        strategy_type="SPK",
    ),
    # Special K Momentum
    PatternBlock(
        id="SPECIAL_K_MOMENTUM",
        name="Special K Momentum",
        category="special_k",
        formula_template="""df['roc10'] = ta.ROC(df['close'], timeperiod=10)
df['roc15'] = ta.ROC(df['close'], timeperiod=15)
df['roc20'] = ta.ROC(df['close'], timeperiod=20)
df['roc30'] = ta.ROC(df['close'], timeperiod=30)
df['roc40'] = ta.ROC(df['close'], timeperiod=40)
df['roc65'] = ta.ROC(df['close'], timeperiod=65)
df['spk'] = ta.SMA(df['roc10'], timeperiod=10) + ta.SMA(df['roc15'], timeperiod=10) * 2 + ta.SMA(df['roc20'], timeperiod=10) * 3 + ta.SMA(df['roc30'], timeperiod=15) * 4 + ta.SMA(df['roc40'], timeperiod=50) + ta.SMA(df['roc65'], timeperiod=65) * 2
df['spk_mom'] = df['spk'] - df['spk'].shift(5)
df['strong_mom'] = df['spk_mom'] > df['spk_mom'].rolling(20).std()
df['entry_signal'] = df['strong_mom']""",
        params={},
        direction="long",
        lookback=150,
        indicators=["ROC", "SMA"],
        combinable_with=["confirmation", "volume"],
        strategy_type="SPK",
    ),
]


# =============================================================================
# PERCENTAGE PRICE OSCILLATOR EXTENDED BLOCKS
# =============================================================================

PERCENTAGE_PRICE_OSC_BLOCKS = [
    # PPO Cross Up
    PatternBlock(
        id="PPO_CROSS_UP_EXT",
        name="PPO Cross Up Extended",
        category="percentage_price_osc",
        formula_template="""df['ppo'] = ta.PPO(df['close'], fastperiod={fast}, slowperiod={slow}, matype=1)
df['ppo_signal'] = ta.EMA(df['ppo'], timeperiod=9)
df['cross_up'] = (df['ppo'] > df['ppo_signal']) & (df['ppo'].shift(1) <= df['ppo_signal'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"fast": [12], "slow": [26]},
        direction="long",
        lookback=40,
        indicators=["PPO", "EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="PPX",
    ),
    # PPO Histogram Rising
    PatternBlock(
        id="PPO_HIST_RISING",
        name="PPO Histogram Rising",
        category="percentage_price_osc",
        formula_template="""df['ppo'] = ta.PPO(df['close'], fastperiod={fast}, slowperiod={slow}, matype=1)
df['ppo_signal'] = ta.EMA(df['ppo'], timeperiod=9)
df['ppo_hist'] = df['ppo'] - df['ppo_signal']
df['hist_rising'] = df['ppo_hist'] > df['ppo_hist'].shift(1)
df['hist_rising_count'] = df['hist_rising'].rolling(3).sum() >= 2
df['entry_signal'] = df['hist_rising_count']""",
        params={"fast": [12], "slow": [26]},
        direction="long",
        lookback=40,
        indicators=["PPO", "EMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="PPX",
    ),
    # PPO Zero Cross
    PatternBlock(
        id="PPO_ZERO_CROSS_EXT",
        name="PPO Zero Cross Extended",
        category="percentage_price_osc",
        formula_template="""df['ppo'] = ta.PPO(df['close'], fastperiod={fast}, slowperiod={slow}, matype=1)
df['cross_zero'] = (df['ppo'] > 0) & (df['ppo'].shift(1) <= 0)
df['ppo_rising'] = df['ppo'] > df['ppo'].shift(3)
df['entry_signal'] = df['cross_zero'] & df['ppo_rising']""",
        params={"fast": [12], "slow": [26]},
        direction="long",
        lookback=40,
        indicators=["PPO"],
        combinable_with=["volume", "confirmation"],
        strategy_type="PPX",
    ),
]


# =============================================================================
# ABSOLUTE PRICE OSCILLATOR BLOCKS
# =============================================================================

ABSOLUTE_PRICE_OSC_BLOCKS = [
    # APO Cross Up
    PatternBlock(
        id="APO_CROSS_UP",
        name="APO Cross Up",
        category="absolute_price_osc",
        formula_template="""df['apo'] = ta.APO(df['close'], fastperiod={fast}, slowperiod={slow}, matype=1)
df['apo_signal'] = ta.EMA(df['apo'], timeperiod=9)
df['cross_up'] = (df['apo'] > df['apo_signal']) & (df['apo'].shift(1) <= df['apo_signal'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"fast": [12], "slow": [26]},
        direction="long",
        lookback=40,
        indicators=["APO", "EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="APO",
    ),
    # APO Zero Cross
    PatternBlock(
        id="APO_ZERO_CROSS",
        name="APO Zero Cross",
        category="absolute_price_osc",
        formula_template="""df['apo'] = ta.APO(df['close'], fastperiod={fast}, slowperiod={slow}, matype=1)
df['cross_zero'] = (df['apo'] > 0) & (df['apo'].shift(1) <= 0)
df['entry_signal'] = df['cross_zero']""",
        params={"fast": [12], "slow": [26]},
        direction="long",
        lookback=40,
        indicators=["APO"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="APO",
    ),
    # APO Positive Rising
    PatternBlock(
        id="APO_POSITIVE_RISING",
        name="APO Positive Rising",
        category="absolute_price_osc",
        formula_template="""df['apo'] = ta.APO(df['close'], fastperiod={fast}, slowperiod={slow}, matype=1)
df['positive'] = df['apo'] > 0
df['rising'] = df['apo'] > df['apo'].shift(3)
df['entry_signal'] = df['positive'] & df['rising']""",
        params={"fast": [12], "slow": [26]},
        direction="long",
        lookback=40,
        indicators=["APO"],
        combinable_with=["volume", "confirmation"],
        strategy_type="APO",
    ),
]


# =============================================================================
# DETRENDED VOLUME BLOCKS
# =============================================================================

DETRENDED_VOLUME_BLOCKS = [
    # Volume Above Trend
    PatternBlock(
        id="VOL_ABOVE_TREND",
        name="Volume Above Trend",
        category="detrended_volume",
        formula_template="""df['vol_ma'] = ta.SMA(df['volume'], timeperiod={period})
df['vol_trend'] = ta.LINEARREG(df['volume'], timeperiod={period})
df['above_trend'] = df['volume'] > df['vol_trend'] * {mult}
df['price_up'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['above_trend'] & df['price_up']""",
        params={"period": [20], "mult": [1.2, 1.5]},
        direction="long",
        lookback=30,
        indicators=["SMA", "LINEARREG"],
        combinable_with=["momentum", "threshold"],
        strategy_type="DTV",
    ),
    # Volume Breakout
    PatternBlock(
        id="VOL_BREAKOUT_DT",
        name="Volume Detrended Breakout",
        category="detrended_volume",
        formula_template="""df['vol_ma'] = ta.SMA(df['volume'], timeperiod={period})
df['vol_detrend'] = df['volume'] - df['vol_ma']
df['vol_std'] = df['vol_detrend'].rolling({period}).std()
df['breakout'] = df['vol_detrend'] > df['vol_std'] * {mult}
df['entry_signal'] = df['breakout']""",
        params={"period": [20], "mult": [2.0, 2.5]},
        direction="bidi",
        lookback=30,
        indicators=["SMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="DTV",
    ),
    # Volume Mean Reversion
    PatternBlock(
        id="VOL_MEAN_REV",
        name="Volume Mean Reversion",
        category="detrended_volume",
        formula_template="""df['vol_ma'] = ta.SMA(df['volume'], timeperiod={period})
df['vol_detrend'] = df['volume'] - df['vol_ma']
df['was_low'] = df['vol_detrend'].shift(1) < 0
df['now_rising'] = df['vol_detrend'] > df['vol_detrend'].shift(1)
df['price_up'] = df['close'] > df['open']
df['entry_signal'] = df['was_low'] & df['now_rising'] & df['price_up']""",
        params={"period": [20, 30]},
        direction="long",
        lookback=35,
        indicators=["SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="DTV",
    ),
]


# =============================================================================
# RELATIVE MOMENTUM INDEX BLOCKS
# =============================================================================

RELATIVE_MOMENTUM_BLOCKS = [
    # RMI Oversold
    PatternBlock(
        id="RMI_OVERSOLD",
        name="RMI Oversold",
        category="relative_momentum",
        formula_template="""df['delta'] = df['close'] - df['close'].shift({momentum})
df['up'] = np.where(df['delta'] > 0, df['delta'], 0)
df['down'] = np.where(df['delta'] < 0, -df['delta'], 0)
df['up_avg'] = ta.EMA(df['up'], timeperiod={period})
df['down_avg'] = ta.EMA(df['down'], timeperiod={period})
df['rmi'] = 100 * df['up_avg'] / (df['up_avg'] + df['down_avg'] + 1e-10)
df['oversold'] = df['rmi'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"period": [14], "momentum": [4], "level": [30, 35]},
        direction="long",
        lookback=30,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="RMI",
    ),
    # RMI Cross Up
    PatternBlock(
        id="RMI_CROSS_UP",
        name="RMI Cross Up",
        category="relative_momentum",
        formula_template="""df['delta'] = df['close'] - df['close'].shift({momentum})
df['up'] = np.where(df['delta'] > 0, df['delta'], 0)
df['down'] = np.where(df['delta'] < 0, -df['delta'], 0)
df['up_avg'] = ta.EMA(df['up'], timeperiod={period})
df['down_avg'] = ta.EMA(df['down'], timeperiod={period})
df['rmi'] = 100 * df['up_avg'] / (df['up_avg'] + df['down_avg'] + 1e-10)
df['cross_up'] = (df['rmi'] > 50) & (df['rmi'].shift(1) <= 50)
df['entry_signal'] = df['cross_up']""",
        params={"period": [14], "momentum": [4]},
        direction="long",
        lookback=30,
        indicators=["EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="RMI",
    ),
    # RMI Strong
    PatternBlock(
        id="RMI_STRONG",
        name="RMI Strong",
        category="relative_momentum",
        formula_template="""df['delta'] = df['close'] - df['close'].shift({momentum})
df['up'] = np.where(df['delta'] > 0, df['delta'], 0)
df['down'] = np.where(df['delta'] < 0, -df['delta'], 0)
df['up_avg'] = ta.EMA(df['up'], timeperiod={period})
df['down_avg'] = ta.EMA(df['down'], timeperiod={period})
df['rmi'] = 100 * df['up_avg'] / (df['up_avg'] + df['down_avg'] + 1e-10)
df['strong'] = df['rmi'] > {level}
df['rising'] = df['rmi'] > df['rmi'].shift(3)
df['entry_signal'] = df['strong'] & df['rising']""",
        params={"period": [14], "momentum": [4], "level": [60, 65]},
        direction="long",
        lookback=30,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="RMI",
    ),
]


# =============================================================================
# STOCHASTIC MOMENTUM INDEX BLOCKS
# =============================================================================

STOCHASTIC_MOMENTUM_BLOCKS = [
    # SMI Oversold
    PatternBlock(
        id="SMI_OVERSOLD",
        name="SMI Oversold",
        category="stochastic_momentum",
        formula_template="""df['hh'] = df['high'].rolling({period}).max()
df['ll'] = df['low'].rolling({period}).min()
df['mid'] = (df['hh'] + df['ll']) / 2
df['d'] = df['close'] - df['mid']
df['hl'] = df['hh'] - df['ll']
df['d_smooth'] = ta.EMA(ta.EMA(df['d'], timeperiod={smooth}), timeperiod={smooth})
df['hl_smooth'] = ta.EMA(ta.EMA(df['hl'], timeperiod={smooth}), timeperiod={smooth})
df['smi'] = 100 * df['d_smooth'] / (df['hl_smooth'] / 2 + 1e-10)
df['oversold'] = df['smi'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"period": [13], "smooth": [5], "level": [-40, -45]},
        direction="long",
        lookback=35,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="SMI",
    ),
    # SMI Cross Up
    PatternBlock(
        id="SMI_CROSS_UP",
        name="SMI Cross Up",
        category="stochastic_momentum",
        formula_template="""df['hh'] = df['high'].rolling({period}).max()
df['ll'] = df['low'].rolling({period}).min()
df['mid'] = (df['hh'] + df['ll']) / 2
df['d'] = df['close'] - df['mid']
df['hl'] = df['hh'] - df['ll']
df['d_smooth'] = ta.EMA(ta.EMA(df['d'], timeperiod={smooth}), timeperiod={smooth})
df['hl_smooth'] = ta.EMA(ta.EMA(df['hl'], timeperiod={smooth}), timeperiod={smooth})
df['smi'] = 100 * df['d_smooth'] / (df['hl_smooth'] / 2 + 1e-10)
df['signal'] = ta.EMA(df['smi'], timeperiod=3)
df['cross_up'] = (df['smi'] > df['signal']) & (df['smi'].shift(1) <= df['signal'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [13], "smooth": [5]},
        direction="long",
        lookback=35,
        indicators=["EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="SMI",
    ),
    # SMI Zero Cross
    PatternBlock(
        id="SMI_ZERO_CROSS",
        name="SMI Zero Cross",
        category="stochastic_momentum",
        formula_template="""df['hh'] = df['high'].rolling({period}).max()
df['ll'] = df['low'].rolling({period}).min()
df['mid'] = (df['hh'] + df['ll']) / 2
df['d'] = df['close'] - df['mid']
df['hl'] = df['hh'] - df['ll']
df['d_smooth'] = ta.EMA(ta.EMA(df['d'], timeperiod={smooth}), timeperiod={smooth})
df['hl_smooth'] = ta.EMA(ta.EMA(df['hl'], timeperiod={smooth}), timeperiod={smooth})
df['smi'] = 100 * df['d_smooth'] / (df['hl_smooth'] / 2 + 1e-10)
df['cross_zero'] = (df['smi'] > 0) & (df['smi'].shift(1) <= 0)
df['entry_signal'] = df['cross_zero']""",
        params={"period": [13], "smooth": [5]},
        direction="long",
        lookback=35,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="SMI",
    ),
]


# =============================================================================
# PROJECTION OSCILLATOR BLOCKS
# =============================================================================

PROJECTION_OSC_BLOCKS = [
    # Projection Oscillator Oversold
    PatternBlock(
        id="PROJ_OSC_OVERSOLD",
        name="Projection Oscillator Oversold",
        category="projection_osc",
        formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['upper'] = ta.LINEARREG(df['high'], timeperiod={period}) + df['slope'] * {period}
df['lower'] = ta.LINEARREG(df['low'], timeperiod={period}) + df['slope'] * {period}
df['proj_osc'] = 100 * (df['close'] - df['lower']) / (df['upper'] - df['lower'] + 1e-10)
df['oversold'] = df['proj_osc'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"period": [14], "level": [20, 25]},
        direction="long",
        lookback=25,
        indicators=["LINEARREG_SLOPE", "LINEARREG"],
        combinable_with=["volume", "confirmation"],
        strategy_type="PRO",
    ),
    # Projection Oscillator Rising
    PatternBlock(
        id="PROJ_OSC_RISING",
        name="Projection Oscillator Rising",
        category="projection_osc",
        formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['upper'] = ta.LINEARREG(df['high'], timeperiod={period}) + df['slope'] * {period}
df['lower'] = ta.LINEARREG(df['low'], timeperiod={period}) + df['slope'] * {period}
df['proj_osc'] = 100 * (df['close'] - df['lower']) / (df['upper'] - df['lower'] + 1e-10)
df['rising'] = df['proj_osc'] > df['proj_osc'].shift(3)
df['above_mid'] = df['proj_osc'] > 50
df['entry_signal'] = df['rising'] & df['above_mid']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["LINEARREG_SLOPE", "LINEARREG"],
        combinable_with=["momentum", "threshold"],
        strategy_type="PRO",
    ),
    # Projection Oscillator Cross
    PatternBlock(
        id="PROJ_OSC_CROSS",
        name="Projection Oscillator Cross",
        category="projection_osc",
        formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['upper'] = ta.LINEARREG(df['high'], timeperiod={period}) + df['slope'] * {period}
df['lower'] = ta.LINEARREG(df['low'], timeperiod={period}) + df['slope'] * {period}
df['proj_osc'] = 100 * (df['close'] - df['lower']) / (df['upper'] - df['lower'] + 1e-10)
df['cross_up'] = (df['proj_osc'] > 50) & (df['proj_osc'].shift(1) <= 50)
df['entry_signal'] = df['cross_up']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["LINEARREG_SLOPE", "LINEARREG"],
        combinable_with=["volume", "confirmation"],
        strategy_type="PRO",
    ),
]


# =============================================================================
# PROJECTION BANDS BLOCKS
# =============================================================================

PROJECTION_BANDS_BLOCKS = [
    # Projection Bands Lower Touch
    PatternBlock(
        id="PROJ_BANDS_LOWER",
        name="Projection Bands Lower Touch",
        category="projection_bands",
        formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['reg'] = ta.LINEARREG(df['close'], timeperiod={period})
df['upper'] = ta.MAX(df['high'] - df['reg'], timeperiod={period}) + df['reg']
df['lower'] = df['reg'] - ta.MAX(df['reg'] - df['low'], timeperiod={period})
df['at_lower'] = df['low'] <= df['lower'] * 1.01
df['bounce'] = df['close'] > df['open']
df['entry_signal'] = df['at_lower'] & df['bounce']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["LINEARREG_SLOPE", "LINEARREG", "MAX"],
        combinable_with=["volume", "confirmation"],
        strategy_type="PRB",
    ),
    # Projection Bands Breakout
    PatternBlock(
        id="PROJ_BANDS_BREAKOUT",
        name="Projection Bands Breakout",
        category="projection_bands",
        formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['reg'] = ta.LINEARREG(df['close'], timeperiod={period})
df['upper'] = ta.MAX(df['high'] - df['reg'], timeperiod={period}) + df['reg']
df['breakout'] = (df['close'] > df['upper']) & (df['close'].shift(1) <= df['upper'].shift(1))
df['entry_signal'] = df['breakout']""",
        params={"period": [14, 20]},
        direction="long",
        lookback=30,
        indicators=["LINEARREG_SLOPE", "LINEARREG", "MAX"],
        combinable_with=["momentum", "threshold"],
        strategy_type="PRB",
    ),
    # Projection Bands Mid Cross
    PatternBlock(
        id="PROJ_BANDS_MID",
        name="Projection Bands Mid Cross",
        category="projection_bands",
        formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['reg'] = ta.LINEARREG(df['close'], timeperiod={period})
df['cross_up'] = (df['close'] > df['reg']) & (df['close'].shift(1) <= df['reg'].shift(1))
df['slope_pos'] = df['slope'] > 0
df['entry_signal'] = df['cross_up'] & df['slope_pos']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["LINEARREG_SLOPE", "LINEARREG"],
        combinable_with=["volume", "confirmation"],
        strategy_type="PRB",
    ),
]


# =============================================================================
# PRICE MOMENTUM OSCILLATOR BLOCKS
# =============================================================================

PRICE_MOMENTUM_OSC_BLOCKS = [
    # PMO Cross Up
    PatternBlock(
        id="PMO_CROSS_UP",
        name="PMO Cross Up",
        category="price_momentum_osc",
        formula_template="""df['roc'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
df['roc_ema1'] = ta.EMA(df['roc'], timeperiod={smooth1})
df['pmo'] = ta.EMA(df['roc_ema1'] * 10, timeperiod={smooth2})
df['signal'] = ta.EMA(df['pmo'], timeperiod=10)
df['cross_up'] = (df['pmo'] > df['signal']) & (df['pmo'].shift(1) <= df['signal'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"smooth1": [35], "smooth2": [20]},
        direction="long",
        lookback=60,
        indicators=["EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="PMO",
    ),
    # PMO Zero Cross
    PatternBlock(
        id="PMO_ZERO_CROSS",
        name="PMO Zero Cross",
        category="price_momentum_osc",
        formula_template="""df['roc'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
df['roc_ema1'] = ta.EMA(df['roc'], timeperiod={smooth1})
df['pmo'] = ta.EMA(df['roc_ema1'] * 10, timeperiod={smooth2})
df['cross_zero'] = (df['pmo'] > 0) & (df['pmo'].shift(1) <= 0)
df['entry_signal'] = df['cross_zero']""",
        params={"smooth1": [35], "smooth2": [20]},
        direction="long",
        lookback=60,
        indicators=["EMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="PMO",
    ),
    # PMO Rising Strong
    PatternBlock(
        id="PMO_RISING_STRONG",
        name="PMO Rising Strong",
        category="price_momentum_osc",
        formula_template="""df['roc'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
df['roc_ema1'] = ta.EMA(df['roc'], timeperiod={smooth1})
df['pmo'] = ta.EMA(df['roc_ema1'] * 10, timeperiod={smooth2})
df['signal'] = ta.EMA(df['pmo'], timeperiod=10)
df['rising'] = df['pmo'] > df['pmo'].shift(3)
df['above_signal'] = df['pmo'] > df['signal']
df['entry_signal'] = df['rising'] & df['above_signal']""",
        params={"smooth1": [35], "smooth2": [20]},
        direction="long",
        lookback=60,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="PMO",
    ),
]


# =============================================================================
# DECISION POINT BLOCKS
# =============================================================================

DECISION_POINT_BLOCKS = [
    # Decision Point Breadth
    PatternBlock(
        id="DP_BREADTH",
        name="Decision Point Breadth Proxy",
        category="decision_point",
        formula_template="""df['up_day'] = df['close'] > df['close'].shift(1)
df['breadth'] = df['up_day'].rolling({period}).sum() / {period} * 100
df['breadth_ma'] = ta.EMA(df['breadth'], timeperiod={ma_period})
df['cross_up'] = (df['breadth'] > df['breadth_ma']) & (df['breadth'].shift(1) <= df['breadth_ma'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [20], "ma_period": [10]},
        direction="long",
        lookback=40,
        indicators=["EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="DPT",
    ),
    # Decision Point Thrust
    PatternBlock(
        id="DP_THRUST",
        name="Decision Point Thrust",
        category="decision_point",
        formula_template="""df['up_day'] = df['close'] > df['close'].shift(1)
df['breadth'] = df['up_day'].rolling({period}).sum() / {period} * 100
df['thrust'] = df['breadth'] > {threshold}
df['entry_signal'] = df['thrust']""",
        params={"period": [10], "threshold": [70, 80]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["confirmation", "threshold"],
        strategy_type="DPT",
    ),
    # Decision Point Rising
    PatternBlock(
        id="DP_RISING",
        name="Decision Point Rising",
        category="decision_point",
        formula_template="""df['up_day'] = df['close'] > df['close'].shift(1)
df['breadth'] = df['up_day'].rolling({period}).sum() / {period} * 100
df['rising'] = df['breadth'] > df['breadth'].shift(5)
df['above_50'] = df['breadth'] > 50
df['entry_signal'] = df['rising'] & df['above_50']""",
        params={"period": [20, 30]},
        direction="long",
        lookback=40,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="DPT",
    ),
]


# =============================================================================
# VOLUME WEIGHTED RSI BLOCKS
# =============================================================================

VOLUME_WEIGHTED_RSI_BLOCKS = [
    # VW-RSI Oversold
    PatternBlock(
        id="VWRSI_OVERSOLD",
        name="Volume Weighted RSI Oversold",
        category="volume_weighted_rsi",
        formula_template="""df['delta'] = df['close'] - df['close'].shift(1)
df['up'] = np.where(df['delta'] > 0, df['delta'] * df['volume'], 0)
df['down'] = np.where(df['delta'] < 0, -df['delta'] * df['volume'], 0)
df['up_avg'] = df['up'].rolling({period}).sum()
df['down_avg'] = df['down'].rolling({period}).sum()
df['vwrsi'] = 100 * df['up_avg'] / (df['up_avg'] + df['down_avg'] + 1e-10)
df['oversold'] = df['vwrsi'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"period": [14], "level": [30, 35]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VWR",
    ),
    # VW-RSI Cross Up
    PatternBlock(
        id="VWRSI_CROSS_UP",
        name="Volume Weighted RSI Cross Up",
        category="volume_weighted_rsi",
        formula_template="""df['delta'] = df['close'] - df['close'].shift(1)
df['up'] = np.where(df['delta'] > 0, df['delta'] * df['volume'], 0)
df['down'] = np.where(df['delta'] < 0, -df['delta'] * df['volume'], 0)
df['up_avg'] = df['up'].rolling({period}).sum()
df['down_avg'] = df['down'].rolling({period}).sum()
df['vwrsi'] = 100 * df['up_avg'] / (df['up_avg'] + df['down_avg'] + 1e-10)
df['cross_up'] = (df['vwrsi'] > 50) & (df['vwrsi'].shift(1) <= 50)
df['entry_signal'] = df['cross_up']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="VWR",
    ),
    # VW-RSI Strong
    PatternBlock(
        id="VWRSI_STRONG",
        name="Volume Weighted RSI Strong",
        category="volume_weighted_rsi",
        formula_template="""df['delta'] = df['close'] - df['close'].shift(1)
df['up'] = np.where(df['delta'] > 0, df['delta'] * df['volume'], 0)
df['down'] = np.where(df['delta'] < 0, -df['delta'] * df['volume'], 0)
df['up_avg'] = df['up'].rolling({period}).sum()
df['down_avg'] = df['down'].rolling({period}).sum()
df['vwrsi'] = 100 * df['up_avg'] / (df['up_avg'] + df['down_avg'] + 1e-10)
df['strong'] = df['vwrsi'] > {level}
df['rising'] = df['vwrsi'] > df['vwrsi'].shift(3)
df['entry_signal'] = df['strong'] & df['rising']""",
        params={"period": [14], "level": [60, 65]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["confirmation", "volume"],
        strategy_type="VWR",
    ),
]


# =============================================================================
# EASE OF MOVEMENT EXTENDED BLOCKS
# =============================================================================

EASE_OF_MOVEMENT_EXT_BLOCKS = [
    # EMV Cross Up
    PatternBlock(
        id="EMV_CROSS_UP_EXT",
        name="EMV Cross Up Extended",
        category="ease_of_movement_ext",
        formula_template="""df['distance'] = ((df['high'] + df['low']) / 2) - ((df['high'].shift(1) + df['low'].shift(1)) / 2)
df['box_ratio'] = (df['volume'] / 1e8) / (df['high'] - df['low'] + 1e-10)
df['emv'] = df['distance'] / df['box_ratio']
df['emv_ma'] = ta.SMA(df['emv'], timeperiod={period})
df['cross_up'] = (df['emv'] > df['emv_ma']) & (df['emv'].shift(1) <= df['emv_ma'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["SMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="EMX",
    ),
    # EMV Positive Strong
    PatternBlock(
        id="EMV_POSITIVE_STRONG",
        name="EMV Positive Strong",
        category="ease_of_movement_ext",
        formula_template="""df['distance'] = ((df['high'] + df['low']) / 2) - ((df['high'].shift(1) + df['low'].shift(1)) / 2)
df['box_ratio'] = (df['volume'] / 1e8) / (df['high'] - df['low'] + 1e-10)
df['emv'] = df['distance'] / df['box_ratio']
df['emv_ma'] = ta.SMA(df['emv'], timeperiod={period})
df['positive'] = df['emv_ma'] > 0
df['rising'] = df['emv_ma'] > df['emv_ma'].shift(3)
df['entry_signal'] = df['positive'] & df['rising']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["SMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="EMX",
    ),
    # EMV Zero Cross
    PatternBlock(
        id="EMV_ZERO_CROSS_EXT",
        name="EMV Zero Cross Extended",
        category="ease_of_movement_ext",
        formula_template="""df['distance'] = ((df['high'] + df['low']) / 2) - ((df['high'].shift(1) + df['low'].shift(1)) / 2)
df['box_ratio'] = (df['volume'] / 1e8) / (df['high'] - df['low'] + 1e-10)
df['emv'] = df['distance'] / df['box_ratio']
df['emv_ma'] = ta.SMA(df['emv'], timeperiod={period})
df['cross_zero'] = (df['emv_ma'] > 0) & (df['emv_ma'].shift(1) <= 0)
df['entry_signal'] = df['cross_zero']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="EMX",
    ),
]


# =============================================================================
# ACCUMULATION SWING INDEX BLOCKS
# =============================================================================

ACCUMULATION_SWING_BLOCKS = [
    # ASI Rising
    PatternBlock(
        id="ASI_RISING",
        name="Accumulation Swing Rising",
        category="accumulation_swing",
        formula_template="""df['k'] = np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1)))
df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
df['si'] = 50 * (df['close'] - df['close'].shift(1) + 0.5 * (df['close'] - df['open']) + 0.25 * (df['close'].shift(1) - df['open'].shift(1))) / df['tr'] * df['k'] / df['tr']
df['asi'] = df['si'].cumsum()
df['asi_ma'] = ta.SMA(df['asi'], timeperiod={period})
df['rising'] = df['asi'] > df['asi_ma']
df['asi_up'] = df['asi'] > df['asi'].shift(3)
df['entry_signal'] = df['rising'] & df['asi_up']""",
        params={"period": [14]},
        direction="long",
        lookback=30,
        indicators=["SMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="ASI",
    ),
    # ASI Breakout
    PatternBlock(
        id="ASI_BREAKOUT",
        name="Accumulation Swing Breakout",
        category="accumulation_swing",
        formula_template="""df['k'] = np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1)))
df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
df['si'] = 50 * (df['close'] - df['close'].shift(1) + 0.5 * (df['close'] - df['open']) + 0.25 * (df['close'].shift(1) - df['open'].shift(1))) / df['tr'] * df['k'] / df['tr']
df['asi'] = df['si'].cumsum()
df['asi_high'] = df['asi'].rolling({period}).max()
df['breakout'] = df['asi'] > df['asi_high'].shift(1)
df['entry_signal'] = df['breakout']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["confirmation", "threshold"],
        strategy_type="ASI",
    ),
    # ASI Divergence
    PatternBlock(
        id="ASI_DIVERGENCE",
        name="Accumulation Swing Divergence",
        category="accumulation_swing",
        formula_template="""df['k'] = np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1)))
df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
df['si'] = 50 * (df['close'] - df['close'].shift(1) + 0.5 * (df['close'] - df['open']) + 0.25 * (df['close'].shift(1) - df['open'].shift(1))) / df['tr'] * df['k'] / df['tr']
df['asi'] = df['si'].cumsum()
df['price_lower'] = df['close'] < df['close'].shift({lookback})
df['asi_higher'] = df['asi'] > df['asi'].shift({lookback})
df['divergence'] = df['price_lower'] & df['asi_higher']
df['entry_signal'] = df['divergence']""",
        params={"lookback": [5, 10]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="ASI",
    ),
]


# =============================================================================
# DEMAND INDEX BLOCKS
# =============================================================================

DEMAND_INDEX_BLOCKS = [
    # Demand Index Positive
    PatternBlock(
        id="DI_POSITIVE",
        name="Demand Index Positive",
        category="demand_index",
        formula_template="""df['bp'] = df['close'] - df['low']
df['sp'] = df['high'] - df['close']
df['bp_vol'] = df['bp'] * df['volume']
df['sp_vol'] = df['sp'] * df['volume']
df['di'] = df['bp_vol'].rolling({period}).sum() / (df['sp_vol'].rolling({period}).sum() + 1e-10)
df['positive'] = df['di'] > 1.0
df['rising'] = df['di'] > df['di'].shift(3)
df['entry_signal'] = df['positive'] & df['rising']""",
        params={"period": [14, 20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="DMI",
    ),
    # Demand Index Cross
    PatternBlock(
        id="DI_CROSS",
        name="Demand Index Cross",
        category="demand_index",
        formula_template="""df['bp'] = df['close'] - df['low']
df['sp'] = df['high'] - df['close']
df['bp_vol'] = df['bp'] * df['volume']
df['sp_vol'] = df['sp'] * df['volume']
df['di'] = df['bp_vol'].rolling({period}).sum() / (df['sp_vol'].rolling({period}).sum() + 1e-10)
df['cross_up'] = (df['di'] > 1.0) & (df['di'].shift(1) <= 1.0)
df['entry_signal'] = df['cross_up']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["confirmation", "threshold"],
        strategy_type="DMI",
    ),
    # Demand Index Strong
    PatternBlock(
        id="DI_STRONG",
        name="Demand Index Strong",
        category="demand_index",
        formula_template="""df['bp'] = df['close'] - df['low']
df['sp'] = df['high'] - df['close']
df['bp_vol'] = df['bp'] * df['volume']
df['sp_vol'] = df['sp'] * df['volume']
df['di'] = df['bp_vol'].rolling({period}).sum() / (df['sp_vol'].rolling({period}).sum() + 1e-10)
df['strong'] = df['di'] > {threshold}
df['entry_signal'] = df['strong']""",
        params={"period": [14], "threshold": [1.5, 2.0]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="DMI",
    ),
]


# =============================================================================
# HERRICK PAYOFF INDEX BLOCKS (proxy)
# =============================================================================

HERRICK_PAYOFF_BLOCKS = [
    # HPI Rising
    PatternBlock(
        id="HPI_RISING",
        name="Herrick Payoff Rising",
        category="herrick_payoff",
        formula_template="""df['mean_price'] = (df['high'] + df['low']) / 2
df['mean_change'] = df['mean_price'] - df['mean_price'].shift(1)
df['vol_factor'] = df['volume'] / df['volume'].rolling({period}).mean()
df['hpi'] = df['mean_change'] * df['vol_factor']
df['hpi_cum'] = df['hpi'].rolling({period}).sum()
df['rising'] = df['hpi_cum'] > df['hpi_cum'].shift(3)
df['positive'] = df['hpi_cum'] > 0
df['entry_signal'] = df['rising'] & df['positive']""",
        params={"period": [14, 20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="HPI",
    ),
    # HPI Cross Zero
    PatternBlock(
        id="HPI_CROSS_ZERO",
        name="Herrick Payoff Cross Zero",
        category="herrick_payoff",
        formula_template="""df['mean_price'] = (df['high'] + df['low']) / 2
df['mean_change'] = df['mean_price'] - df['mean_price'].shift(1)
df['vol_factor'] = df['volume'] / df['volume'].rolling({period}).mean()
df['hpi'] = df['mean_change'] * df['vol_factor']
df['hpi_cum'] = df['hpi'].rolling({period}).sum()
df['cross_zero'] = (df['hpi_cum'] > 0) & (df['hpi_cum'].shift(1) <= 0)
df['entry_signal'] = df['cross_zero']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["confirmation", "threshold"],
        strategy_type="HPI",
    ),
    # HPI Divergence
    PatternBlock(
        id="HPI_DIVERGENCE",
        name="Herrick Payoff Divergence",
        category="herrick_payoff",
        formula_template="""df['mean_price'] = (df['high'] + df['low']) / 2
df['mean_change'] = df['mean_price'] - df['mean_price'].shift(1)
df['vol_factor'] = df['volume'] / df['volume'].rolling({period}).mean()
df['hpi'] = df['mean_change'] * df['vol_factor']
df['hpi_cum'] = df['hpi'].rolling({period}).sum()
df['price_lower'] = df['close'] < df['close'].shift(5)
df['hpi_higher'] = df['hpi_cum'] > df['hpi_cum'].shift(5)
df['divergence'] = df['price_lower'] & df['hpi_higher']
df['entry_signal'] = df['divergence']""",
        params={"period": [14]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="HPI",
    ),
]


# =============================================================================
# TRADE VOLUME INDEX BLOCKS
# =============================================================================

TRADE_VOLUME_INDEX_BLOCKS = [
    # TVI Rising
    PatternBlock(
        id="TVI_RISING",
        name="Trade Volume Index Rising",
        category="trade_volume_index",
        formula_template="""df['direction'] = np.sign(df['close'] - df['close'].shift(1))
df['tvi'] = (df['direction'] * df['volume']).cumsum()
df['tvi_ma'] = ta.SMA(df['tvi'], timeperiod={period})
df['rising'] = df['tvi'] > df['tvi_ma']
df['tvi_up'] = df['tvi'] > df['tvi'].shift(3)
df['entry_signal'] = df['rising'] & df['tvi_up']""",
        params={"period": [14, 20]},
        direction="long",
        lookback=30,
        indicators=["SMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="TVI",
    ),
    # TVI Cross Up
    PatternBlock(
        id="TVI_CROSS_UP",
        name="Trade Volume Index Cross Up",
        category="trade_volume_index",
        formula_template="""df['direction'] = np.sign(df['close'] - df['close'].shift(1))
df['tvi'] = (df['direction'] * df['volume']).cumsum()
df['tvi_ma'] = ta.SMA(df['tvi'], timeperiod={period})
df['cross_up'] = (df['tvi'] > df['tvi_ma']) & (df['tvi'].shift(1) <= df['tvi_ma'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="TVI",
    ),
    # TVI Breakout
    PatternBlock(
        id="TVI_BREAKOUT",
        name="Trade Volume Index Breakout",
        category="trade_volume_index",
        formula_template="""df['direction'] = np.sign(df['close'] - df['close'].shift(1))
df['tvi'] = (df['direction'] * df['volume']).cumsum()
df['tvi_high'] = df['tvi'].rolling({period}).max()
df['breakout'] = df['tvi'] > df['tvi_high'].shift(1)
df['entry_signal'] = df['breakout']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["confirmation", "momentum"],
        strategy_type="TVI",
    ),
]


# =============================================================================
# SWING INDEX BLOCKS
# =============================================================================

SWING_INDEX_BLOCKS = [
    # Swing Index Positive
    PatternBlock(
        id="SI_POSITIVE",
        name="Swing Index Positive",
        category="swing_index",
        formula_template="""df['k'] = np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1)))
df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
df['si'] = 50 * (df['close'] - df['close'].shift(1) + 0.5 * (df['close'] - df['open'])) / (df['tr'] + 1e-10)
df['si_ma'] = ta.SMA(df['si'], timeperiod={period})
df['positive'] = df['si_ma'] > 0
df['rising'] = df['si_ma'] > df['si_ma'].shift(3)
df['entry_signal'] = df['positive'] & df['rising']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["SMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="SWI",
    ),
    # Swing Index Cross
    PatternBlock(
        id="SI_CROSS",
        name="Swing Index Cross",
        category="swing_index",
        formula_template="""df['k'] = np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1)))
df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
df['si'] = 50 * (df['close'] - df['close'].shift(1) + 0.5 * (df['close'] - df['open'])) / (df['tr'] + 1e-10)
df['si_ma'] = ta.SMA(df['si'], timeperiod={period})
df['cross_up'] = (df['si_ma'] > 0) & (df['si_ma'].shift(1) <= 0)
df['entry_signal'] = df['cross_up']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["SMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="SWI",
    ),
    # Swing Index Strong
    PatternBlock(
        id="SI_STRONG",
        name="Swing Index Strong",
        category="swing_index",
        formula_template="""df['k'] = np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1)))
df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
df['si'] = 50 * (df['close'] - df['close'].shift(1) + 0.5 * (df['close'] - df['open'])) / (df['tr'] + 1e-10)
df['si_sum'] = df['si'].rolling({period}).sum()
df['strong'] = df['si_sum'] > df['si_sum'].rolling({period}).std() * {mult}
df['entry_signal'] = df['strong']""",
        params={"period": [14], "mult": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="SWI",
    ),
]


# =============================================================================
# DYNAMIC MOMENTUM INDEX BLOCKS
# =============================================================================

DYNAMIC_MOMENTUM_BLOCKS = [
    # DMI Oversold
    PatternBlock(
        id="DYMI_OVERSOLD",
        name="Dynamic Momentum Oversold",
        category="dynamic_momentum",
        formula_template="""df['vol'] = df['close'].rolling(5).std()
df['vol_avg'] = df['vol'].rolling(10).mean()
df['dyn_period'] = np.clip(14 * df['vol_avg'] / (df['vol'] + 1e-10), 5, 30).astype(int)
df['dymi'] = ta.RSI(df['close'], timeperiod=14)
df['oversold'] = df['dymi'] < {level}
df['entry_signal'] = df['oversold']""",
        params={"level": [30, 35]},
        direction="long",
        lookback=35,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="DYM",
    ),
    # DMI Cross Up
    PatternBlock(
        id="DYMI_CROSS_UP",
        name="Dynamic Momentum Cross Up",
        category="dynamic_momentum",
        formula_template="""df['dymi'] = ta.RSI(df['close'], timeperiod=14)
df['dymi_ma'] = ta.SMA(df['dymi'], timeperiod=9)
df['cross_up'] = (df['dymi'] > df['dymi_ma']) & (df['dymi'].shift(1) <= df['dymi_ma'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={},
        direction="long",
        lookback=30,
        indicators=["RSI", "SMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="DYM",
    ),
    # DMI Strong
    PatternBlock(
        id="DYMI_STRONG",
        name="Dynamic Momentum Strong",
        category="dynamic_momentum",
        formula_template="""df['dymi'] = ta.RSI(df['close'], timeperiod=14)
df['strong'] = df['dymi'] > {level}
df['rising'] = df['dymi'] > df['dymi'].shift(3)
df['entry_signal'] = df['strong'] & df['rising']""",
        params={"level": [60, 65]},
        direction="long",
        lookback=25,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="DYM",
    ),
]


# =============================================================================
# MARKET FACILITATION INDEX BLOCKS (Bill Williams)
# =============================================================================

MARKET_FACILITATION_BLOCKS = [
    # MFI Green (price up, volume up)
    PatternBlock(
        id="MFI_GREEN",
        name="Market Facilitation Green",
        category="market_facilitation",
        formula_template="""df['mfi'] = (df['high'] - df['low']) / (df['volume'] + 1e-10) * 1e8
df['mfi_up'] = df['mfi'] > df['mfi'].shift(1)
df['vol_up'] = df['volume'] > df['volume'].shift(1)
df['green'] = df['mfi_up'] & df['vol_up']
df['entry_signal'] = df['green']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="MFB",
    ),
    # MFI Squat (MFI down, volume up)
    PatternBlock(
        id="MFI_SQUAT",
        name="Market Facilitation Squat",
        category="market_facilitation",
        formula_template="""df['mfi'] = (df['high'] - df['low']) / (df['volume'] + 1e-10) * 1e8
df['mfi_down'] = df['mfi'] < df['mfi'].shift(1)
df['vol_up'] = df['volume'] > df['volume'].shift(1)
df['squat'] = df['mfi_down'] & df['vol_up']
df['squat_count'] = df['squat'].rolling(3).sum() >= 2
df['price_up'] = df['close'] > df['close'].shift(3)
df['entry_signal'] = df['squat_count'] & df['price_up']""",
        params={},
        direction="long",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="MFB",
    ),
    # MFI Fade Recovery
    PatternBlock(
        id="MFI_FADE_RECOVERY",
        name="Market Facilitation Fade Recovery",
        category="market_facilitation",
        formula_template="""df['mfi'] = (df['high'] - df['low']) / (df['volume'] + 1e-10) * 1e8
df['mfi_down'] = df['mfi'] < df['mfi'].shift(1)
df['vol_down'] = df['volume'] < df['volume'].shift(1)
df['fade'] = df['mfi_down'] & df['vol_down']
df['was_fade'] = df['fade'].shift(1)
df['mfi_rising'] = df['mfi'] > df['mfi'].shift(1)
df['recovery'] = df['was_fade'] & df['mfi_rising']
df['entry_signal'] = df['recovery']""",
        params={},
        direction="bidi",
        lookback=15,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="MFB",
    ),
]


# =============================================================================
# VOLATILITY SYSTEM BLOCKS
# =============================================================================

VOLATILITY_SYSTEM_BLOCKS = [
    # Volatility Breakout Up
    PatternBlock(
        id="VOL_SYS_BREAKOUT_UP",
        name="Volatility System Breakout Up",
        category="volatility_system",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['upper'] = df['close'].shift(1) + df['atr'].shift(1) * {mult}
df['breakout'] = df['close'] > df['upper']
df['entry_signal'] = df['breakout']""",
        params={"period": [14], "mult": [1.5, 2.0]},
        direction="long",
        lookback=25,
        indicators=["ATR"],
        combinable_with=["volume", "momentum"],
        strategy_type="VSY",
    ),
    # Volatility Contraction Breakout
    PatternBlock(
        id="VOL_SYS_CONTRACT_BREAK",
        name="Volatility Contraction Breakout",
        category="volatility_system",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['atr_ma'] = df['atr'].rolling({period}).mean()
df['contracted'] = df['atr'] < df['atr_ma'] * {contract}
df['contracted_days'] = df['contracted'].rolling(5).sum() >= 3
df['breakout'] = df['close'] > df['high'].shift(1)
df['entry_signal'] = df['contracted_days'] & df['breakout']""",
        params={"period": [14], "contract": [0.7, 0.8]},
        direction="long",
        lookback=30,
        indicators=["ATR"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="VSY",
    ),
    # Volatility Expansion Entry
    PatternBlock(
        id="VOL_SYS_EXPANSION",
        name="Volatility System Expansion",
        category="volatility_system",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
df['atr_ma'] = df['atr'].rolling({period}).mean()
df['expansion'] = df['atr'] > df['atr_ma'] * {expand}
df['price_up'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['expansion'] & df['price_up']""",
        params={"period": [14], "expand": [1.2, 1.5]},
        direction="long",
        lookback=25,
        indicators=["ATR"],
        combinable_with=["volume", "confirmation"],
        strategy_type="VSY",
    ),
]


# =============================================================================
# PRICE CHANNEL EXTENDED BLOCKS
# =============================================================================

PRICE_CHANNEL_EXT_BLOCKS = [
    # Price Channel Breakout Up
    PatternBlock(
        id="PCH_BREAKOUT_UP",
        name="Price Channel Breakout Up",
        category="price_channel_ext",
        formula_template="""df['upper'] = df['high'].rolling({period}).max().shift(1)
df['lower'] = df['low'].rolling({period}).min().shift(1)
df['breakout'] = df['close'] > df['upper']
df['entry_signal'] = df['breakout']""",
        params={"period": [20, 30]},
        direction="long",
        lookback=35,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="PCE",
    ),
    # Price Channel Mid Cross
    PatternBlock(
        id="PCH_MID_CROSS",
        name="Price Channel Mid Cross",
        category="price_channel_ext",
        formula_template="""df['upper'] = df['high'].rolling({period}).max()
df['lower'] = df['low'].rolling({period}).min()
df['mid'] = (df['upper'] + df['lower']) / 2
df['cross_up'] = (df['close'] > df['mid']) & (df['close'].shift(1) <= df['mid'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["confirmation", "threshold"],
        strategy_type="PCE",
    ),
    # Price Channel Width
    PatternBlock(
        id="PCH_WIDTH_EXPAND",
        name="Price Channel Width Expanding",
        category="price_channel_ext",
        formula_template="""df['upper'] = df['high'].rolling({period}).max()
df['lower'] = df['low'].rolling({period}).min()
df['width'] = (df['upper'] - df['lower']) / df['close']
df['width_ma'] = df['width'].rolling({period}).mean()
df['expanding'] = df['width'] > df['width_ma'] * {mult}
df['uptrend'] = df['close'] > (df['upper'] + df['lower']) / 2
df['entry_signal'] = df['expanding'] & df['uptrend']""",
        params={"period": [20], "mult": [1.2, 1.3]},
        direction="long",
        lookback=35,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PCE",
    ),
]


# =============================================================================
# BALANCE OF POWER EXTENDED BLOCKS
# =============================================================================

BALANCE_OF_POWER_EXT_BLOCKS = [
    # BOP Cross Up
    PatternBlock(
        id="BOP_CROSS_UP_EXT",
        name="BOP Cross Up Extended",
        category="balance_of_power_ext",
        formula_template="""df['bop'] = ta.BOP(df['open'], df['high'], df['low'], df['close'])
df['bop_ma'] = ta.SMA(df['bop'], timeperiod={period})
df['cross_up'] = (df['bop'] > df['bop_ma']) & (df['bop'].shift(1) <= df['bop_ma'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["BOP", "SMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="BPX",
    ),
    # BOP Strong Positive
    PatternBlock(
        id="BOP_STRONG_POS",
        name="BOP Strong Positive",
        category="balance_of_power_ext",
        formula_template="""df['bop'] = ta.BOP(df['open'], df['high'], df['low'], df['close'])
df['bop_ma'] = ta.SMA(df['bop'], timeperiod={period})
df['strong'] = df['bop_ma'] > {threshold}
df['rising'] = df['bop_ma'] > df['bop_ma'].shift(3)
df['entry_signal'] = df['strong'] & df['rising']""",
        params={"period": [14], "threshold": [0.3, 0.4]},
        direction="long",
        lookback=25,
        indicators=["BOP", "SMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="BPX",
    ),
    # BOP Zero Cross
    PatternBlock(
        id="BOP_ZERO_CROSS_EXT",
        name="BOP Zero Cross Extended",
        category="balance_of_power_ext",
        formula_template="""df['bop'] = ta.BOP(df['open'], df['high'], df['low'], df['close'])
df['bop_ma'] = ta.SMA(df['bop'], timeperiod={period})
df['cross_zero'] = (df['bop_ma'] > 0) & (df['bop_ma'].shift(1) <= 0)
df['entry_signal'] = df['cross_zero']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["BOP", "SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="BPX",
    ),
]


# =============================================================================
# CHAIKIN VOLATILITY BLOCKS
# =============================================================================

CHAIKIN_VOLATILITY_BLOCKS = [
    # Chaikin Vol Rising
    PatternBlock(
        id="CHAIKIN_VOL_RISING",
        name="Chaikin Volatility Rising",
        category="chaikin_volatility",
        formula_template="""df['hl'] = df['high'] - df['low']
df['hl_ema'] = ta.EMA(df['hl'], timeperiod={period})
df['chv'] = (df['hl_ema'] - df['hl_ema'].shift({period})) / (df['hl_ema'].shift({period}) + 1e-10) * 100
df['rising'] = df['chv'] > df['chv'].shift(1)
df['positive'] = df['chv'] > 0
df['entry_signal'] = df['rising'] & df['positive']""",
        params={"period": [10]},
        direction="bidi",
        lookback=25,
        indicators=["EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="CHV",
    ),
    # Chaikin Vol Extreme Low
    PatternBlock(
        id="CHAIKIN_VOL_LOW",
        name="Chaikin Volatility Extreme Low",
        category="chaikin_volatility",
        formula_template="""df['hl'] = df['high'] - df['low']
df['hl_ema'] = ta.EMA(df['hl'], timeperiod={period})
df['chv'] = (df['hl_ema'] - df['hl_ema'].shift({period})) / (df['hl_ema'].shift({period}) + 1e-10) * 100
df['low_vol'] = df['chv'] < {threshold}
df['entry_signal'] = df['low_vol']""",
        params={"period": [10], "threshold": [-20, -30]},
        direction="bidi",
        lookback=25,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="CHV",
    ),
    # Chaikin Vol Expansion
    PatternBlock(
        id="CHAIKIN_VOL_EXPAND",
        name="Chaikin Volatility Expansion",
        category="chaikin_volatility",
        formula_template="""df['hl'] = df['high'] - df['low']
df['hl_ema'] = ta.EMA(df['hl'], timeperiod={period})
df['chv'] = (df['hl_ema'] - df['hl_ema'].shift({period})) / (df['hl_ema'].shift({period}) + 1e-10) * 100
df['was_low'] = df['chv'].shift(3) < 0
df['now_high'] = df['chv'] > {threshold}
df['expansion'] = df['was_low'] & df['now_high']
df['entry_signal'] = df['expansion']""",
        params={"period": [10], "threshold": [10, 20]},
        direction="bidi",
        lookback=30,
        indicators=["EMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="CHV",
    ),
]


# =============================================================================
# HISTORICAL VOLATILITY BLOCKS
# =============================================================================

HISTORICAL_VOLATILITY_BLOCKS = [
    # HV Low (consolidation)
    PatternBlock(
        id="HV_LOW",
        name="Historical Volatility Low",
        category="historical_volatility",
        formula_template="""df['returns'] = np.log(df['close'] / df['close'].shift(1))
df['hv'] = df['returns'].rolling({period}).std() * np.sqrt(252) * 100
df['hv_ma'] = df['hv'].rolling({period}).mean()
df['low_hv'] = df['hv'] < df['hv_ma'] * {mult}
df['entry_signal'] = df['low_hv']""",
        params={"period": [20], "mult": [0.7, 0.8]},
        direction="bidi",
        lookback=40,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="HVO",
    ),
    # HV Breakout
    PatternBlock(
        id="HV_BREAKOUT",
        name="Historical Volatility Breakout",
        category="historical_volatility",
        formula_template="""df['returns'] = np.log(df['close'] / df['close'].shift(1))
df['hv'] = df['returns'].rolling({period}).std() * np.sqrt(252) * 100
df['hv_ma'] = df['hv'].rolling({period}).mean()
df['was_low'] = df['hv'].shift(3) < df['hv_ma'].shift(3)
df['now_high'] = df['hv'] > df['hv_ma']
df['breakout'] = df['was_low'] & df['now_high']
df['price_up'] = df['close'] > df['close'].shift(3)
df['entry_signal'] = df['breakout'] & df['price_up']""",
        params={"period": [20]},
        direction="long",
        lookback=40,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="HVO",
    ),
    # HV Rising
    PatternBlock(
        id="HV_RISING",
        name="Historical Volatility Rising",
        category="historical_volatility",
        formula_template="""df['returns'] = np.log(df['close'] / df['close'].shift(1))
df['hv'] = df['returns'].rolling({period}).std() * np.sqrt(252) * 100
df['rising'] = df['hv'] > df['hv'].shift(5)
df['price_trend'] = df['close'] > df['close'].shift(5)
df['entry_signal'] = df['rising'] & df['price_trend']""",
        params={"period": [20]},
        direction="long",
        lookback=35,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="HVO",
    ),
]


# =============================================================================
# STANDARD ERROR BLOCKS
# =============================================================================

STANDARD_ERROR_BLOCKS = [
    # Standard Error Band Touch
    PatternBlock(
        id="SE_BAND_TOUCH",
        name="Standard Error Band Touch",
        category="standard_error",
        formula_template="""df['reg'] = ta.LINEARREG(df['close'], timeperiod={period})
df['se'] = ta.STDDEV(df['close'], timeperiod={period}) / np.sqrt({period})
df['upper'] = df['reg'] + df['se'] * {mult}
df['lower'] = df['reg'] - df['se'] * {mult}
df['at_lower'] = df['low'] <= df['lower']
df['bounce'] = df['close'] > df['open']
df['entry_signal'] = df['at_lower'] & df['bounce']""",
        params={"period": [20], "mult": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=["LINEARREG", "STDDEV"],
        combinable_with=["volume", "confirmation"],
        strategy_type="SER",
    ),
    # Standard Error Cross Up
    PatternBlock(
        id="SE_CROSS_UP",
        name="Standard Error Cross Up",
        category="standard_error",
        formula_template="""df['reg'] = ta.LINEARREG(df['close'], timeperiod={period})
df['cross_up'] = (df['close'] > df['reg']) & (df['close'].shift(1) <= df['reg'].shift(1))
df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['slope_pos'] = df['slope'] > 0
df['entry_signal'] = df['cross_up'] & df['slope_pos']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=["LINEARREG", "LINEARREG_SLOPE"],
        combinable_with=["momentum", "threshold"],
        strategy_type="SER",
    ),
    # Standard Error Narrow
    PatternBlock(
        id="SE_NARROW",
        name="Standard Error Narrow",
        category="standard_error",
        formula_template="""df['se'] = ta.STDDEV(df['close'], timeperiod={period}) / np.sqrt({period})
df['se_ma'] = df['se'].rolling({period}).mean()
df['narrow'] = df['se'] < df['se_ma'] * {mult}
df['narrow_days'] = df['narrow'].rolling(5).sum() >= 3
df['entry_signal'] = df['narrow_days']""",
        params={"period": [20], "mult": [0.7, 0.8]},
        direction="bidi",
        lookback=35,
        indicators=["STDDEV"],
        combinable_with=["volume", "confirmation"],
        strategy_type="SER",
    ),
]


# =============================================================================
# REGRESSION SLOPE BLOCKS
# =============================================================================

REGRESSION_SLOPE_BLOCKS = [
    # Slope Positive Strong
    PatternBlock(
        id="REG_SLOPE_STRONG",
        name="Regression Slope Strong",
        category="regression_slope",
        formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['slope_norm'] = df['slope'] / df['close'] * 100
df['strong'] = df['slope_norm'] > {threshold}
df['entry_signal'] = df['strong']""",
        params={"period": [14, 20], "threshold": [0.5, 1.0]},
        direction="long",
        lookback=30,
        indicators=["LINEARREG_SLOPE"],
        combinable_with=["volume", "momentum"],
        strategy_type="RSL",
    ),
    # Slope Turn Up
    PatternBlock(
        id="REG_SLOPE_TURN_UP",
        name="Regression Slope Turn Up",
        category="regression_slope",
        formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['was_neg'] = df['slope'].shift(1) < 0
df['now_pos'] = df['slope'] > 0
df['turn_up'] = df['was_neg'] & df['now_pos']
df['entry_signal'] = df['turn_up']""",
        params={"period": [14, 20]},
        direction="long",
        lookback=30,
        indicators=["LINEARREG_SLOPE"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="RSL",
    ),
    # Slope Accelerating
    PatternBlock(
        id="REG_SLOPE_ACCEL",
        name="Regression Slope Accelerating",
        category="regression_slope",
        formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['slope_change'] = df['slope'] - df['slope'].shift(3)
df['accelerating'] = df['slope_change'] > 0
df['positive'] = df['slope'] > 0
df['entry_signal'] = df['accelerating'] & df['positive']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["LINEARREG_SLOPE"],
        combinable_with=["volume", "confirmation"],
        strategy_type="RSL",
    ),
]


# =============================================================================
# PRICE OSCILLATOR EXTENDED BLOCKS
# =============================================================================

PRICE_OSCILLATOR_EXT_BLOCKS = [
    # Price Oscillator Cross
    PatternBlock(
        id="PRICE_OSC_CROSS_EXT",
        name="Price Oscillator Cross Extended",
        category="price_oscillator_ext",
        formula_template="""df['fast_ma'] = ta.EMA(df['close'], timeperiod={fast})
df['slow_ma'] = ta.EMA(df['close'], timeperiod={slow})
df['po'] = (df['fast_ma'] - df['slow_ma']) / df['slow_ma'] * 100
df['po_signal'] = ta.SMA(df['po'], timeperiod=9)
df['cross_up'] = (df['po'] > df['po_signal']) & (df['po'].shift(1) <= df['po_signal'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"fast": [10], "slow": [21]},
        direction="long",
        lookback=35,
        indicators=["EMA", "SMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="POX",
    ),
    # Price Oscillator Zero Cross
    PatternBlock(
        id="PRICE_OSC_ZERO_EXT",
        name="Price Oscillator Zero Cross",
        category="price_oscillator_ext",
        formula_template="""df['fast_ma'] = ta.EMA(df['close'], timeperiod={fast})
df['slow_ma'] = ta.EMA(df['close'], timeperiod={slow})
df['po'] = (df['fast_ma'] - df['slow_ma']) / df['slow_ma'] * 100
df['cross_zero'] = (df['po'] > 0) & (df['po'].shift(1) <= 0)
df['entry_signal'] = df['cross_zero']""",
        params={"fast": [10], "slow": [21]},
        direction="long",
        lookback=35,
        indicators=["EMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="POX",
    ),
    # Price Oscillator Strong
    PatternBlock(
        id="PRICE_OSC_STRONG_EXT",
        name="Price Oscillator Strong",
        category="price_oscillator_ext",
        formula_template="""df['fast_ma'] = ta.EMA(df['close'], timeperiod={fast})
df['slow_ma'] = ta.EMA(df['close'], timeperiod={slow})
df['po'] = (df['fast_ma'] - df['slow_ma']) / df['slow_ma'] * 100
df['strong'] = df['po'] > {threshold}
df['rising'] = df['po'] > df['po'].shift(3)
df['entry_signal'] = df['strong'] & df['rising']""",
        params={"fast": [10], "slow": [21], "threshold": [1.0, 2.0]},
        direction="long",
        lookback=35,
        indicators=["EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="POX",
    ),
]


# =============================================================================
# VOLUME OSCILLATOR BLOCKS
# =============================================================================

VOLUME_OSCILLATOR_BLOCKS = [
    # Volume Oscillator Positive
    PatternBlock(
        id="VOL_OSC_POSITIVE",
        name="Volume Oscillator Positive",
        category="volume_oscillator",
        formula_template="""df['fast_vol'] = ta.SMA(df['volume'], timeperiod={fast})
df['slow_vol'] = ta.SMA(df['volume'], timeperiod={slow})
df['vo'] = (df['fast_vol'] - df['slow_vol']) / df['slow_vol'] * 100
df['positive'] = df['vo'] > 0
df['rising'] = df['vo'] > df['vo'].shift(1)
df['price_up'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['positive'] & df['rising'] & df['price_up']""",
        params={"fast": [5], "slow": [20]},
        direction="long",
        lookback=30,
        indicators=["SMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="VOO",
    ),
    # Volume Oscillator Cross
    PatternBlock(
        id="VOL_OSC_CROSS",
        name="Volume Oscillator Cross",
        category="volume_oscillator",
        formula_template="""df['fast_vol'] = ta.SMA(df['volume'], timeperiod={fast})
df['slow_vol'] = ta.SMA(df['volume'], timeperiod={slow})
df['vo'] = (df['fast_vol'] - df['slow_vol']) / df['slow_vol'] * 100
df['cross_up'] = (df['vo'] > 0) & (df['vo'].shift(1) <= 0)
df['price_up'] = df['close'] > df['open']
df['entry_signal'] = df['cross_up'] & df['price_up']""",
        params={"fast": [5], "slow": [20]},
        direction="long",
        lookback=30,
        indicators=["SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="VOO",
    ),
    # Volume Oscillator Strong
    PatternBlock(
        id="VOL_OSC_STRONG",
        name="Volume Oscillator Strong",
        category="volume_oscillator",
        formula_template="""df['fast_vol'] = ta.SMA(df['volume'], timeperiod={fast})
df['slow_vol'] = ta.SMA(df['volume'], timeperiod={slow})
df['vo'] = (df['fast_vol'] - df['slow_vol']) / df['slow_vol'] * 100
df['strong'] = df['vo'] > {threshold}
df['entry_signal'] = df['strong']""",
        params={"fast": [5], "slow": [20], "threshold": [30, 50]},
        direction="bidi",
        lookback=30,
        indicators=["SMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VOO",
    ),
]


# =============================================================================
# MOMENTUM PERCENTILE BLOCKS
# =============================================================================

MOMENTUM_PERCENTILE_BLOCKS = [
    # Momentum Percentile Low
    PatternBlock(
        id="MOM_PERCENTILE_LOW",
        name="Momentum Percentile Low",
        category="momentum_percentile",
        formula_template="""df['mom'] = df['close'] - df['close'].shift({mom_period})
df['percentile'] = df['mom'].rolling({lookback}).apply(lambda x: (x < x.iloc[-1]).sum() / len(x) * 100, raw=False)
df['low_pct'] = df['percentile'] < {level}
df['entry_signal'] = df['low_pct']""",
        params={"mom_period": [10], "lookback": [100], "level": [20, 25]},
        direction="long",
        lookback=120,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="MPT",
    ),
    # Momentum Percentile Rising
    PatternBlock(
        id="MOM_PERCENTILE_RISING",
        name="Momentum Percentile Rising",
        category="momentum_percentile",
        formula_template="""df['mom'] = df['close'] - df['close'].shift({mom_period})
df['percentile'] = df['mom'].rolling({lookback}).apply(lambda x: (x < x.iloc[-1]).sum() / len(x) * 100, raw=False)
df['rising'] = df['percentile'] > df['percentile'].shift(5)
df['above_mid'] = df['percentile'] > 50
df['entry_signal'] = df['rising'] & df['above_mid']""",
        params={"mom_period": [10], "lookback": [100]},
        direction="long",
        lookback=120,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="MPT",
    ),
    # Momentum Percentile Extreme High
    PatternBlock(
        id="MOM_PERCENTILE_HIGH",
        name="Momentum Percentile High",
        category="momentum_percentile",
        formula_template="""df['mom'] = df['close'] - df['close'].shift({mom_period})
df['percentile'] = df['mom'].rolling({lookback}).apply(lambda x: (x < x.iloc[-1]).sum() / len(x) * 100, raw=False)
df['high_pct'] = df['percentile'] > {level}
df['entry_signal'] = df['high_pct']""",
        params={"mom_period": [10], "lookback": [100], "level": [75, 80]},
        direction="long",
        lookback=120,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="MPT",
    ),
]


# =============================================================================
# TREND SCORE BLOCKS
# =============================================================================

TREND_SCORE_BLOCKS = [
    # Trend Score Bullish
    PatternBlock(
        id="TREND_SCORE_BULL",
        name="Trend Score Bullish",
        category="trend_score",
        formula_template="""df['ma5'] = ta.SMA(df['close'], timeperiod=5)
df['ma10'] = ta.SMA(df['close'], timeperiod=10)
df['ma20'] = ta.SMA(df['close'], timeperiod=20)
df['score'] = (df['close'] > df['ma5']).astype(int) + (df['ma5'] > df['ma10']).astype(int) + (df['ma10'] > df['ma20']).astype(int) + (df['close'] > df['ma20']).astype(int)
df['bullish'] = df['score'] >= {threshold}
df['entry_signal'] = df['bullish']""",
        params={"threshold": [3, 4]},
        direction="long",
        lookback=30,
        indicators=["SMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="TSC",
    ),
    # Trend Score Improving
    PatternBlock(
        id="TREND_SCORE_IMPROVE",
        name="Trend Score Improving",
        category="trend_score",
        formula_template="""df['ma5'] = ta.SMA(df['close'], timeperiod=5)
df['ma10'] = ta.SMA(df['close'], timeperiod=10)
df['ma20'] = ta.SMA(df['close'], timeperiod=20)
df['score'] = (df['close'] > df['ma5']).astype(int) + (df['ma5'] > df['ma10']).astype(int) + (df['ma10'] > df['ma20']).astype(int) + (df['close'] > df['ma20']).astype(int)
df['improving'] = df['score'] > df['score'].shift(3)
df['above_mid'] = df['score'] >= 2
df['entry_signal'] = df['improving'] & df['above_mid']""",
        params={},
        direction="long",
        lookback=30,
        indicators=["SMA"],
        combinable_with=["confirmation", "threshold"],
        strategy_type="TSC",
    ),
    # Trend Score Flip
    PatternBlock(
        id="TREND_SCORE_FLIP",
        name="Trend Score Flip Bullish",
        category="trend_score",
        formula_template="""df['ma5'] = ta.SMA(df['close'], timeperiod=5)
df['ma10'] = ta.SMA(df['close'], timeperiod=10)
df['ma20'] = ta.SMA(df['close'], timeperiod=20)
df['score'] = (df['close'] > df['ma5']).astype(int) + (df['ma5'] > df['ma10']).astype(int) + (df['ma10'] > df['ma20']).astype(int) + (df['close'] > df['ma20']).astype(int)
df['was_bearish'] = df['score'].shift(1) <= 1
df['now_bullish'] = df['score'] >= 3
df['flip'] = df['was_bearish'] & df['now_bullish']
df['entry_signal'] = df['flip']""",
        params={},
        direction="long",
        lookback=30,
        indicators=["SMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="TSC",
    ),
]


# =============================================================================
# ADAPTIVE RSI BLOCKS
# =============================================================================

ADAPTIVE_RSI_BLOCKS = [
    # Adaptive RSI Oversold
    PatternBlock(
        id="ARSI_OVERSOLD",
        name="Adaptive RSI Oversold",
        category="adaptive_rsi",
        formula_template="""df['vol'] = df['close'].rolling(10).std()
df['vol_ratio'] = df['vol'] / df['vol'].rolling(50).mean()
df['dyn_period'] = np.clip(14 / df['vol_ratio'], 7, 28).fillna(14).astype(int)
df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['dyn_oversold'] = {base_level} - (df['vol_ratio'] - 1) * 10
df['dyn_oversold'] = df['dyn_oversold'].clip(20, 40)
df['oversold'] = df['rsi'] < df['dyn_oversold']
df['entry_signal'] = df['oversold']""",
        params={"base_level": [30, 35]},
        direction="long",
        lookback=60,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="ARS",
    ),
    # Adaptive RSI Cross
    PatternBlock(
        id="ARSI_CROSS",
        name="Adaptive RSI Cross",
        category="adaptive_rsi",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['rsi_ma'] = ta.EMA(df['rsi'], timeperiod=9)
df['vol'] = df['close'].rolling(10).std()
df['vol_high'] = df['vol'] > df['vol'].rolling(20).mean()
df['cross_up'] = (df['rsi'] > df['rsi_ma']) & (df['rsi'].shift(1) <= df['rsi_ma'].shift(1))
df['entry_signal'] = df['cross_up'] & df['vol_high']""",
        params={},
        direction="long",
        lookback=40,
        indicators=["RSI", "EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="ARS",
    ),
    # Adaptive RSI Strong
    PatternBlock(
        id="ARSI_STRONG",
        name="Adaptive RSI Strong",
        category="adaptive_rsi",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['vol'] = df['close'].rolling(10).std()
df['vol_ratio'] = df['vol'] / df['vol'].rolling(50).mean()
df['dyn_strong'] = {base_level} + (df['vol_ratio'] - 1) * 10
df['dyn_strong'] = df['dyn_strong'].clip(55, 75)
df['strong'] = df['rsi'] > df['dyn_strong']
df['rising'] = df['rsi'] > df['rsi'].shift(3)
df['entry_signal'] = df['strong'] & df['rising']""",
        params={"base_level": [60, 65]},
        direction="long",
        lookback=60,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="ARS",
    ),
]


# =============================================================================
# RATE OF CHANGE EXTENDED BLOCKS
# =============================================================================

RATE_OF_CHANGE_EXT_BLOCKS = [
    # ROC Smoothed Cross
    PatternBlock(
        id="ROC_SMOOTHED_CROSS",
        name="ROC Smoothed Cross",
        category="rate_of_change_ext",
        formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
df['roc_smooth'] = ta.EMA(df['roc'], timeperiod=5)
df['roc_signal'] = ta.EMA(df['roc_smooth'], timeperiod=9)
df['cross_up'] = (df['roc_smooth'] > df['roc_signal']) & (df['roc_smooth'].shift(1) <= df['roc_signal'].shift(1))
df['entry_signal'] = df['cross_up']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=30,
        indicators=["ROC", "EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="RCX",
    ),
    # ROC Percentile Extreme
    PatternBlock(
        id="ROC_PERCENTILE",
        name="ROC Percentile Extreme",
        category="rate_of_change_ext",
        formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
df['roc_pct'] = df['roc'].rolling(100).apply(lambda x: (x.iloc[-1] > x).sum() / len(x) * 100, raw=False)
df['extreme_low'] = df['roc_pct'] < {threshold}
df['turning'] = df['roc'] > df['roc'].shift(1)
df['entry_signal'] = df['extreme_low'] & df['turning']""",
        params={"period": [10], "threshold": [10, 20]},
        direction="long",
        lookback=120,
        indicators=["ROC"],
        combinable_with=["volume", "threshold"],
        strategy_type="RCX",
    ),
    # ROC Acceleration
    PatternBlock(
        id="ROC_ACCELERATION",
        name="ROC Acceleration",
        category="rate_of_change_ext",
        formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
df['roc_change'] = df['roc'] - df['roc'].shift(3)
df['accelerating'] = df['roc_change'] > 0
df['positive'] = df['roc'] > 0
df['entry_signal'] = df['accelerating'] & df['positive']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=25,
        indicators=["ROC"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="RCX",
    ),
]


# =============================================================================
# VOLATILITY BREAKOUT BLOCKS
# =============================================================================

VOLATILITY_BREAKOUT_BLOCKS = [
    # ATR Expansion Trigger
    PatternBlock(
        id="ATR_EXPANSION_TRIGGER",
        name="ATR Expansion Trigger",
        category="volatility_breakout",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['atr_ma'] = df['atr'].rolling(20).mean()
df['was_low'] = df['atr'].shift(3) < df['atr_ma'].shift(3) * {contract_mult}
df['now_high'] = df['atr'] > df['atr_ma'] * {expand_mult}
df['expansion'] = df['was_low'] & df['now_high']
df['price_up'] = df['close'] > df['close'].shift(3)
df['entry_signal'] = df['expansion'] & df['price_up']""",
        params={"contract_mult": [0.8], "expand_mult": [1.2, 1.5]},
        direction="long",
        lookback=35,
        indicators=["ATR"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VBK",
    ),
    # Volatility Squeeze Break
    PatternBlock(
        id="VOL_SQUEEZE_BREAK",
        name="Volatility Squeeze Break",
        category="volatility_breakout",
        formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
df['bb_narrow'] = df['bb_width'] < df['bb_width'].rolling(50).quantile(0.2)
df['squeeze_days'] = df['bb_narrow'].rolling(5).sum() >= 3
df['break_up'] = df['close'] > df['bb_upper']
df['entry_signal'] = df['squeeze_days'].shift(1) & df['break_up']""",
        params={},
        direction="long",
        lookback=60,
        indicators=["BBANDS"],
        combinable_with=["volume", "momentum"],
        strategy_type="VBK",
    ),
    # Range Breakout
    PatternBlock(
        id="RANGE_BREAKOUT",
        name="Range Breakout",
        category="volatility_breakout",
        formula_template="""df['range'] = df['high'] - df['low']
df['avg_range'] = df['range'].rolling({period}).mean()
df['narrow_range'] = df['range'] < df['avg_range'] * {mult}
df['nr_days'] = df['narrow_range'].rolling(5).sum() >= 3
df['high_break'] = df['close'] > df['high'].shift(1).rolling(5).max()
df['entry_signal'] = df['nr_days'].shift(1) & df['high_break']""",
        params={"period": [20], "mult": [0.6, 0.7]},
        direction="long",
        lookback=35,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="VBK",
    ),
]


# =============================================================================
# PRICE DENSITY BLOCKS
# =============================================================================

PRICE_DENSITY_BLOCKS = [
    # Price Clustering
    PatternBlock(
        id="PRICE_CLUSTERING",
        name="Price Clustering",
        category="price_density",
        formula_template="""df['range'] = df['high'].rolling({period}).max() - df['low'].rolling({period}).min()
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['density'] = df['range'] / (df['atr'] * {period})
df['tight'] = df['density'] < {threshold}
df['break_up'] = df['close'] > df['high'].shift(1).rolling(5).max()
df['entry_signal'] = df['tight'].shift(1) & df['break_up']""",
        params={"period": [10], "threshold": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=["ATR"],
        combinable_with=["volume", "momentum"],
        strategy_type="PDN",
    ),
    # Consolidation Density
    PatternBlock(
        id="CONSOLIDATION_DENSITY",
        name="Consolidation Density",
        category="price_density",
        formula_template="""df['hl_range'] = df['high'] - df['low']
df['avg_range'] = df['hl_range'].rolling(20).mean()
df['small_range'] = df['hl_range'] < df['avg_range'] * {mult}
df['consol_days'] = df['small_range'].rolling({period}).sum()
df['tight_consol'] = df['consol_days'] >= {period} * 0.7
df['breakout'] = df['close'] > df['close'].shift(1).rolling(5).max()
df['entry_signal'] = df['tight_consol'].shift(1) & df['breakout']""",
        params={"period": [10], "mult": [0.7, 0.8]},
        direction="long",
        lookback=35,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PDN",
    ),
    # Distribution Width
    PatternBlock(
        id="DISTRIBUTION_WIDTH",
        name="Distribution Width",
        category="price_density",
        formula_template="""df['std'] = df['close'].rolling({period}).std()
df['std_norm'] = df['std'] / df['close'] * 100
df['narrow'] = df['std_norm'] < df['std_norm'].rolling(50).quantile(0.25)
df['expanding'] = df['std_norm'] > df['std_norm'].shift(3)
df['entry_signal'] = df['narrow'].shift(3) & df['expanding']""",
        params={"period": [20]},
        direction="bidi",
        lookback=60,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="PDN",
    ),
]


# =============================================================================
# MOMENTUM DIVERGENCE EXTENDED BLOCKS
# =============================================================================

MOMENTUM_DIVERGENCE_EXT_BLOCKS = [
    # Multi-Indicator Divergence
    PatternBlock(
        id="MULTI_IND_DIV",
        name="Multi-Indicator Divergence",
        category="momentum_divergence_ext",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['macd'], df['macd_signal'], df['macd_hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
df['price_lower'] = df['close'] < df['close'].shift({period})
df['rsi_higher'] = df['rsi'] > df['rsi'].shift({period})
df['macd_higher'] = df['macd_hist'] > df['macd_hist'].shift({period})
df['bullish_div'] = df['price_lower'] & df['rsi_higher'] & df['macd_higher']
df['entry_signal'] = df['bullish_div']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=30,
        indicators=["RSI", "MACD"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MDV",
    ),
    # Hidden Divergence
    PatternBlock(
        id="HIDDEN_DIV",
        name="Hidden Divergence",
        category="momentum_divergence_ext",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['price_higher'] = df['low'] > df['low'].shift({period})
df['rsi_lower'] = df['rsi'] < df['rsi'].shift({period})
df['uptrend'] = df['close'] > ta.EMA(df['close'], timeperiod=50)
df['hidden_bull'] = df['price_higher'] & df['rsi_lower'] & df['uptrend']
df['entry_signal'] = df['hidden_bull']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=60,
        indicators=["RSI", "EMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="MDV",
    ),
    # Triple Divergence
    PatternBlock(
        id="TRIPLE_DIV",
        name="Triple Divergence",
        category="momentum_divergence_ext",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['stoch_k'], df['stoch_d'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowd_period=3)
df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod=14)
df['price_low'] = df['close'] < df['close'].shift(10)
df['rsi_up'] = df['rsi'] > df['rsi'].shift(10)
df['stoch_up'] = df['stoch_k'] > df['stoch_k'].shift(10)
df['cci_up'] = df['cci'] > df['cci'].shift(10)
df['triple'] = df['price_low'] & df['rsi_up'] & df['stoch_up'] & df['cci_up']
df['entry_signal'] = df['triple']""",
        params={},
        direction="long",
        lookback=30,
        indicators=["RSI", "STOCH", "CCI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MDV",
    ),
]


# =============================================================================
# TREND CONFIRMATION BLOCKS
# =============================================================================

TREND_CONFIRMATION_BLOCKS = [
    # Multi-MA Alignment
    PatternBlock(
        id="MULTI_MA_ALIGN",
        name="Multi-MA Alignment",
        category="trend_confirmation",
        formula_template="""df['ema10'] = ta.EMA(df['close'], timeperiod=10)
df['ema20'] = ta.EMA(df['close'], timeperiod=20)
df['ema50'] = ta.EMA(df['close'], timeperiod=50)
df['aligned'] = (df['ema10'] > df['ema20']) & (df['ema20'] > df['ema50'])
df['price_above'] = df['close'] > df['ema10']
df['entry_signal'] = df['aligned'] & df['price_above']""",
        params={},
        direction="long",
        lookback=60,
        indicators=["EMA"],
        combinable_with=["momentum", "volume"],
        strategy_type="TCF",
    ),
    # ADX + DI Confirm
    PatternBlock(
        id="ADX_DI_CONFIRM",
        name="ADX + DI Confirm",
        category="trend_confirmation",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
df['strong_trend'] = df['adx'] > {adx_thresh}
df['bullish'] = df['plus_di'] > df['minus_di']
df['di_strong'] = df['plus_di'] > {di_thresh}
df['entry_signal'] = df['strong_trend'] & df['bullish'] & df['di_strong']""",
        params={"adx_thresh": [25, 30], "di_thresh": [20, 25]},
        direction="long",
        lookback=25,
        indicators=["ADX", "PLUS_DI", "MINUS_DI"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="TCF",
    ),
    # Trend Unanimity
    PatternBlock(
        id="TREND_UNANIMITY",
        name="Trend Unanimity",
        category="trend_confirmation",
        formula_template="""df['above_sma20'] = df['close'] > ta.SMA(df['close'], timeperiod=20)
df['above_sma50'] = df['close'] > ta.SMA(df['close'], timeperiod=50)
df['rsi_bullish'] = ta.RSI(df['close'], timeperiod=14) > 50
df['macd'], _, _ = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
df['macd_pos'] = df['macd'] > 0
df['unanimity'] = df['above_sma20'] & df['above_sma50'] & df['rsi_bullish'] & df['macd_pos']
df['entry_signal'] = df['unanimity']""",
        params={},
        direction="long",
        lookback=60,
        indicators=["SMA", "RSI", "MACD"],
        combinable_with=["volume", "threshold"],
        strategy_type="TCF",
    ),
]


# =============================================================================
# OSCILLATOR EXTREME BLOCKS
# =============================================================================

OSCILLATOR_EXTREME_BLOCKS = [
    # RSI + Stoch Extreme
    PatternBlock(
        id="RSI_STOCH_EXTREME",
        name="RSI + Stoch Extreme",
        category="oscillator_extreme",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['stoch_k'], _ = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowd_period=3)
df['rsi_oversold'] = df['rsi'] < {rsi_level}
df['stoch_oversold'] = df['stoch_k'] < {stoch_level}
df['both_oversold'] = df['rsi_oversold'] & df['stoch_oversold']
df['turning'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['both_oversold'] & df['turning']""",
        params={"rsi_level": [30, 35], "stoch_level": [20, 25]},
        direction="long",
        lookback=25,
        indicators=["RSI", "STOCH"],
        combinable_with=["volume", "confirmation"],
        strategy_type="OEX",
    ),
    # Multi-Osc Oversold
    PatternBlock(
        id="MULTI_OSC_OVERSOLD",
        name="Multi-Oscillator Oversold",
        category="oscillator_extreme",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod=14)
df['willr'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod=14)
df['rsi_os'] = df['rsi'] < 35
df['cci_os'] = df['cci'] < -100
df['willr_os'] = df['willr'] < -80
df['multi_os'] = df['rsi_os'] & df['cci_os'] & df['willr_os']
df['entry_signal'] = df['multi_os']""",
        params={},
        direction="long",
        lookback=25,
        indicators=["RSI", "CCI", "WILLR"],
        combinable_with=["volume", "confirmation"],
        strategy_type="OEX",
    ),
    # Oscillator Unanimity
    PatternBlock(
        id="OSC_UNANIMITY",
        name="Oscillator Unanimity",
        category="oscillator_extreme",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['stoch_k'], _ = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowd_period=3)
df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)
df['rsi_turn'] = (df['rsi'] > df['rsi'].shift(1)) & (df['rsi'].shift(1) < 40)
df['stoch_turn'] = (df['stoch_k'] > df['stoch_k'].shift(1)) & (df['stoch_k'].shift(1) < 30)
df['mfi_turn'] = (df['mfi'] > df['mfi'].shift(1)) & (df['mfi'].shift(1) < 30)
df['unanimity'] = df['rsi_turn'] & df['stoch_turn'] & df['mfi_turn']
df['entry_signal'] = df['unanimity']""",
        params={},
        direction="long",
        lookback=25,
        indicators=["RSI", "STOCH", "MFI"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="OEX",
    ),
]


# =============================================================================
# VOLUME MOMENTUM BLOCKS
# =============================================================================

VOLUME_MOMENTUM_BLOCKS = [
    # Volume ROC
    PatternBlock(
        id="VOL_ROC",
        name="Volume ROC",
        category="volume_momentum",
        formula_template="""df['vol_roc'] = (df['volume'] - df['volume'].shift({period})) / df['volume'].shift({period}) * 100
df['vol_surge'] = df['vol_roc'] > {threshold}
df['price_up'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['vol_surge'] & df['price_up']""",
        params={"period": [5, 10], "threshold": [50, 100]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="VMM",
    ),
    # Volume Acceleration
    PatternBlock(
        id="VOL_ACCEL",
        name="Volume Acceleration",
        category="volume_momentum",
        formula_template="""df['vol_ma'] = df['volume'].rolling({period}).mean()
df['vol_ratio'] = df['volume'] / df['vol_ma']
df['vol_accel'] = df['vol_ratio'] - df['vol_ratio'].shift(3)
df['accelerating'] = df['vol_accel'] > 0
df['high_vol'] = df['vol_ratio'] > 1.5
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['accelerating'] & df['high_vol'] & df['bullish']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VMM",
    ),
    # Volume Momentum Divergence
    PatternBlock(
        id="VOL_MOM_DIV",
        name="Volume Momentum Divergence",
        category="volume_momentum",
        formula_template="""df['price_lower'] = df['close'] < df['close'].shift(10)
df['vol_higher'] = df['volume'] > df['volume'].shift(10)
df['obv'] = ta.OBV(df['close'], df['volume'])
df['obv_higher'] = df['obv'] > df['obv'].shift(10)
df['vol_div'] = df['price_lower'] & df['vol_higher'] & df['obv_higher']
df['entry_signal'] = df['vol_div']""",
        params={},
        direction="long",
        lookback=20,
        indicators=["OBV"],
        combinable_with=["momentum", "threshold"],
        strategy_type="VMM",
    ),
]


# =============================================================================
# CANDLE MOMENTUM BLOCKS
# =============================================================================

CANDLE_MOMENTUM_BLOCKS = [
    # Body Momentum
    PatternBlock(
        id="BODY_MOMENTUM",
        name="Body Momentum",
        category="candle_momentum",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['body_ma'] = df['body'].rolling({period}).mean()
df['body_ratio'] = df['body'] / df['body_ma']
df['strong_body'] = df['body_ratio'] > {threshold}
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['strong_body'] & df['bullish']""",
        params={"period": [10], "threshold": [1.5, 2.0]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="CDM",
    ),
    # Candle Acceleration
    PatternBlock(
        id="CANDLE_ACCEL",
        name="Candle Acceleration",
        category="candle_momentum",
        formula_template="""df['body'] = df['close'] - df['open']
df['body_1'] = df['body'].shift(1)
df['body_2'] = df['body'].shift(2)
df['accelerating'] = (df['body'] > df['body_1']) & (df['body_1'] > df['body_2'])
df['all_bullish'] = (df['body'] > 0) & (df['body_1'] > 0) & (df['body_2'] > 0)
df['entry_signal'] = df['accelerating'] & df['all_bullish']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="CDM",
    ),
    # Consecutive Body Growth
    PatternBlock(
        id="CONSEC_BODY_GROWTH",
        name="Consecutive Body Growth",
        category="candle_momentum",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['growing'] = df['body'] > df['body'].shift(1) * {mult}
df['bullish'] = df['close'] > df['open']
df['consec'] = df['growing'] & df['bullish']
df['consec_count'] = df['consec'].rolling({count}).sum()
df['entry_signal'] = df['consec_count'] >= {count}""",
        params={"mult": [1.1, 1.2], "count": [3]},
        direction="long",
        lookback=15,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="CDM",
    ),
]


# =============================================================================
# SUPPORT BOUNCE BLOCKS
# =============================================================================

SUPPORT_BOUNCE_BLOCKS = [
    # Dynamic Support Test
    PatternBlock(
        id="DYN_SUPPORT_TEST",
        name="Dynamic Support Test",
        category="support_bounce",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['at_ema'] = df['low'] <= df['ema'] * 1.01
df['above_ema'] = df['close'] > df['ema']
df['bounce'] = df['at_ema'] & df['above_ema']
df['uptrend'] = df['ema'] > df['ema'].shift(5)
df['entry_signal'] = df['bounce'] & df['uptrend']""",
        params={"period": [20, 50]},
        direction="long",
        lookback=60,
        indicators=["EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="SBN",
    ),
    # Pivot Bounce
    PatternBlock(
        id="PIVOT_BOUNCE",
        name="Pivot Bounce",
        category="support_bounce",
        formula_template="""df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
df['s1'] = 2 * df['pivot'] - df['high'].shift(1)
df['at_support'] = df['low'] <= df['s1'] * 1.005
df['bounce'] = df['close'] > df['open']
df['above_s1'] = df['close'] > df['s1']
df['entry_signal'] = df['at_support'] & df['bounce'] & df['above_s1']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="SBN",
    ),
    # MA Support Touch
    PatternBlock(
        id="MA_SUPPORT_TOUCH",
        name="MA Support Touch",
        category="support_bounce",
        formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['touches'] = (df['low'] <= df['sma'] * 1.005) & (df['close'] > df['sma'])
df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean()
df['entry_signal'] = df['touches'] & df['vol_confirm']""",
        params={"period": [20, 50]},
        direction="long",
        lookback=60,
        indicators=["SMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="SBN",
    ),
]


# =============================================================================
# BREAKOUT STRENGTH BLOCKS
# =============================================================================

BREAKOUT_STRENGTH_BLOCKS = [
    # Volume-Confirmed Break
    PatternBlock(
        id="VOL_CONFIRM_BREAK",
        name="Volume-Confirmed Break",
        category="breakout_strength",
        formula_template="""df['high_20'] = df['high'].rolling(20).max()
df['break_high'] = df['close'] > df['high_20'].shift(1)
df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
df['entry_signal'] = df['break_high'] & df['vol_surge']""",
        params={"mult": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="BKS",
    ),
    # ATR Break Magnitude
    PatternBlock(
        id="ATR_BREAK_MAG",
        name="ATR Break Magnitude",
        category="breakout_strength",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['prev_high'] = df['high'].shift(1).rolling(10).max()
df['break_size'] = df['close'] - df['prev_high']
df['strong_break'] = df['break_size'] > df['atr'] * {mult}
df['entry_signal'] = df['strong_break']""",
        params={"mult": [1.0, 1.5]},
        direction="long",
        lookback=25,
        indicators=["ATR"],
        combinable_with=["volume", "confirmation"],
        strategy_type="BKS",
    ),
    # Multi-Bar Break
    PatternBlock(
        id="MULTI_BAR_BREAK",
        name="Multi-Bar Break",
        category="breakout_strength",
        formula_template="""df['high_10'] = df['high'].rolling(10).max()
df['break'] = df['close'] > df['high_10'].shift(1)
df['consec_break'] = df['break'].rolling({bars}).sum() >= {bars}
df['vol_up'] = df['volume'] > df['volume'].shift(1)
df['entry_signal'] = df['consec_break'] & df['vol_up']""",
        params={"bars": [2, 3]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="BKS",
    ),
]


# =============================================================================
# RESISTANCE REJECTION BLOCKS
# =============================================================================

RESISTANCE_REJECTION_BLOCKS = [
    # Dynamic Resistance Test
    PatternBlock(
        id="DYN_RESISTANCE_TEST",
        name="Dynamic Resistance Test",
        category="resistance_rejection",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['at_ema'] = df['high'] >= df['ema'] * 0.99
df['below_ema'] = df['close'] < df['ema']
df['rejection'] = df['at_ema'] & df['below_ema']
df['downtrend'] = df['ema'] < df['ema'].shift(5)
df['entry_signal'] = df['rejection'] & df['downtrend']""",
        params={"period": [20, 50]},
        direction="short",
        lookback=60,
        indicators=["EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="RRJ",
    ),
    # Pivot Rejection
    PatternBlock(
        id="PIVOT_REJECTION",
        name="Pivot Rejection",
        category="resistance_rejection",
        formula_template="""df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
df['r1'] = 2 * df['pivot'] - df['low'].shift(1)
df['at_resistance'] = df['high'] >= df['r1'] * 0.995
df['rejection'] = df['close'] < df['open']
df['below_r1'] = df['close'] < df['r1']
df['entry_signal'] = df['at_resistance'] & df['rejection'] & df['below_r1']""",
        params={},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="RRJ",
    ),
    # MA Resistance Touch
    PatternBlock(
        id="MA_RESISTANCE_TOUCH",
        name="MA Resistance Touch",
        category="resistance_rejection",
        formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['touches'] = (df['high'] >= df['sma'] * 0.995) & (df['close'] < df['sma'])
df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean()
df['entry_signal'] = df['touches'] & df['vol_confirm']""",
        params={"period": [20, 50]},
        direction="short",
        lookback=60,
        indicators=["SMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="RRJ",
    ),
]


# =============================================================================
# PULLBACK ENTRY BLOCKS
# =============================================================================

PULLBACK_ENTRY_BLOCKS = [
    # Trend Pullback
    PatternBlock(
        id="TREND_PULLBACK",
        name="Trend Pullback",
        category="pullback_entry",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod=20)
df['ema_slow'] = ta.EMA(df['close'], timeperiod=50)
df['uptrend'] = df['ema_fast'] > df['ema_slow']
df['pullback'] = df['low'] <= df['ema_fast'] * 1.01
df['bounce'] = df['close'] > df['ema_fast']
df['entry_signal'] = df['uptrend'] & df['pullback'] & df['bounce']""",
        params={},
        direction="long",
        lookback=60,
        indicators=["EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="PBE",
    ),
    # EMA Pullback
    PatternBlock(
        id="EMA_PULLBACK",
        name="EMA Pullback",
        category="pullback_entry",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['above_ema'] = df['close'].shift(5) > df['ema'].shift(5)
df['touched'] = df['low'] <= df['ema'] * 1.005
df['recovered'] = df['close'] > df['ema']
df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['not_overbought'] = df['rsi'] < 70
df['entry_signal'] = df['above_ema'] & df['touched'] & df['recovered'] & df['not_overbought']""",
        params={"period": [20, 50]},
        direction="long",
        lookback=60,
        indicators=["EMA", "RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="PBE",
    ),
    # Fibonacci Retracement Zone
    PatternBlock(
        id="FIB_RETRACE_ZONE",
        name="Fibonacci Retracement Zone",
        category="pullback_entry",
        formula_template="""df['high_20'] = df['high'].rolling(20).max()
df['low_20'] = df['low'].rolling(20).min()
df['range'] = df['high_20'] - df['low_20']
df['fib_382'] = df['high_20'] - df['range'] * 0.382
df['fib_618'] = df['high_20'] - df['range'] * 0.618
df['in_zone'] = (df['low'] <= df['fib_382']) & (df['low'] >= df['fib_618'])
df['bounce'] = df['close'] > df['open']
df['entry_signal'] = df['in_zone'] & df['bounce']""",
        params={},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="PBE",
    ),
]


# =============================================================================
# MOMENTUM EXHAUSTION BLOCKS (MEX2)
# =============================================================================

MOMENTUM_EXHAUSTION_EXT_BLOCKS = [
    # RSI Exhaustion
    PatternBlock(
        id="RSI_EXHAUSTION",
        name="RSI Exhaustion",
        category="momentum_exhaustion_ext",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['was_extreme'] = df['rsi'].shift(3) > {level}
df['falling'] = df['rsi'] < df['rsi'].shift(1)
df['still_high'] = df['rsi'] > 50
df['exhaustion'] = df['was_extreme'] & df['falling'] & df['still_high']
df['entry_signal'] = df['exhaustion']""",
        params={"level": [75, 80]},
        direction="short",
        lookback=25,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MEX",
    ),
    # Momentum Deceleration
    PatternBlock(
        id="MOM_DECELERATION",
        name="Momentum Deceleration",
        category="momentum_exhaustion_ext",
        formula_template="""df['mom'] = ta.MOM(df['close'], timeperiod=10)
df['mom_accel'] = df['mom'] - df['mom'].shift(3)
df['decelerating'] = df['mom_accel'] < 0
df['still_positive'] = df['mom'] > 0
df['high_price'] = df['close'] > df['close'].rolling(20).mean()
df['entry_signal'] = df['decelerating'] & df['still_positive'] & df['high_price']""",
        params={},
        direction="short",
        lookback=30,
        indicators=["MOM"],
        combinable_with=["volume", "threshold"],
        strategy_type="MEX",
    ),
    # Climax Reversal
    PatternBlock(
        id="CLIMAX_REVERSAL",
        name="Climax Reversal",
        category="momentum_exhaustion_ext",
        formula_template="""df['range'] = df['high'] - df['low']
df['avg_range'] = df['range'].rolling(20).mean()
df['climax_bar'] = df['range'] > df['avg_range'] * {mult}
df['vol_climax'] = df['volume'] > df['volume'].rolling(20).mean() * 2
df['reversal'] = df['close'] < df['open']
df['entry_signal'] = df['climax_bar'] & df['vol_climax'] & df['reversal']""",
        params={"mult": [2.0, 2.5]},
        direction="short",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="MEX",
    ),
]


# =============================================================================
# VOLUME PROFILE EXTENDED BLOCKS
# =============================================================================

VOLUME_PROFILE_EXT_BLOCKS = [
    # High Volume Node
    PatternBlock(
        id="HIGH_VOL_NODE",
        name="High Volume Node",
        category="volume_profile_ext",
        formula_template="""df['vol_ma'] = df['volume'].rolling({period}).mean()
df['high_vol'] = df['volume'] > df['vol_ma'] * {mult}
df['price_level'] = df['close'].rolling(5).mean()
df['at_hvn'] = abs(df['close'] - df['price_level']) / df['close'] < 0.01
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['high_vol'].shift(1) & df['at_hvn'] & df['bullish']""",
        params={"period": [20], "mult": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VPX",
    ),
    # Low Volume Gap
    PatternBlock(
        id="LOW_VOL_GAP",
        name="Low Volume Gap",
        category="volume_profile_ext",
        formula_template="""df['vol_ma'] = df['volume'].rolling(20).mean()
df['low_vol_zone'] = df['volume'] < df['vol_ma'] * 0.5
df['low_vol_days'] = df['low_vol_zone'].rolling(5).sum() >= 3
df['break_up'] = df['close'] > df['high'].shift(1).rolling(5).max()
df['vol_increase'] = df['volume'] > df['vol_ma']
df['entry_signal'] = df['low_vol_days'].shift(1) & df['break_up'] & df['vol_increase']""",
        params={},
        direction="long",
        lookback=35,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="VPX",
    ),
    # Volume POC
    PatternBlock(
        id="VOL_POC",
        name="Volume POC",
        category="volume_profile_ext",
        formula_template="""df['vwap'] = (df['close'] * df['volume']).rolling({period}).sum() / df['volume'].rolling({period}).sum()
df['at_poc'] = abs(df['close'] - df['vwap']) / df['close'] < 0.005
df['bounce'] = df['close'] > df['open']
df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean()
df['entry_signal'] = df['at_poc'] & df['bounce'] & df['vol_confirm']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="VPX",
    ),
]


# =============================================================================
# TREND CHANGE BLOCKS
# =============================================================================

TREND_CHANGE_BLOCKS = [
    # MA Crossover Confirm
    PatternBlock(
        id="MA_CROSS_CONFIRM",
        name="MA Crossover Confirm",
        category="trend_change",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
df['cross_up'] = (df['ema_fast'] > df['ema_slow']) & (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))
df['price_confirm'] = df['close'] > df['ema_fast']
df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean()
df['entry_signal'] = df['cross_up'] & df['price_confirm'] & df['vol_confirm']""",
        params={"fast": [10, 20], "slow": [50]},
        direction="long",
        lookback=60,
        indicators=["EMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="TCH",
    ),
    # ADX Trend Shift
    PatternBlock(
        id="ADX_TREND_SHIFT",
        name="ADX Trend Shift",
        category="trend_change",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
df['di_cross'] = (df['plus_di'] > df['minus_di']) & (df['plus_di'].shift(1) <= df['minus_di'].shift(1))
df['adx_rising'] = df['adx'] > df['adx'].shift(3)
df['entry_signal'] = df['di_cross'] & df['adx_rising']""",
        params={},
        direction="long",
        lookback=25,
        indicators=["ADX", "PLUS_DI", "MINUS_DI"],
        combinable_with=["volume", "threshold"],
        strategy_type="TCH",
    ),
    # Momentum Flip
    PatternBlock(
        id="MOMENTUM_FLIP",
        name="Momentum Flip",
        category="trend_change",
        formula_template="""df['macd'], df['macd_signal'], df['macd_hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
df['hist_flip'] = (df['macd_hist'] > 0) & (df['macd_hist'].shift(1) <= 0)
df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['rsi_confirm'] = df['rsi'] > 50
df['entry_signal'] = df['hist_flip'] & df['rsi_confirm']""",
        params={},
        direction="long",
        lookback=35,
        indicators=["MACD", "RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="TCH",
    ),
]


# =============================================================================
# RANGE BOUND BLOCKS
# =============================================================================

RANGE_BOUND_BLOCKS = [
    # Range Detection
    PatternBlock(
        id="RANGE_DETECTION",
        name="Range Detection",
        category="range_bound",
        formula_template="""df['high_20'] = df['high'].rolling(20).max()
df['low_20'] = df['low'].rolling(20).min()
df['range_pct'] = (df['high_20'] - df['low_20']) / df['close'] * 100
df['tight_range'] = df['range_pct'] < {threshold}
df['at_bottom'] = df['close'] < df['low_20'] + (df['high_20'] - df['low_20']) * 0.3
df['bounce'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['tight_range'] & df['at_bottom'] & df['bounce']""",
        params={"threshold": [5, 8]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="RGB",
    ),
    # Mean Reversion Setup
    PatternBlock(
        id="MEAN_REVERSION_SETUP",
        name="Mean Reversion Setup",
        category="range_bound",
        formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
df['std'] = df['close'].rolling({period}).std()
df['lower_band'] = df['sma'] - df['std'] * {mult}
df['at_lower'] = df['close'] <= df['lower_band']
df['reversal'] = df['close'] > df['open']
df['entry_signal'] = df['at_lower'] & df['reversal']""",
        params={"period": [20], "mult": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=["SMA"],
        combinable_with=["volume", "threshold"],
        strategy_type="RGB",
    ),
    # Channel Midline
    PatternBlock(
        id="CHANNEL_MIDLINE",
        name="Channel Midline",
        category="range_bound",
        formula_template="""df['high_ch'] = df['high'].rolling({period}).max()
df['low_ch'] = df['low'].rolling({period}).min()
df['midline'] = (df['high_ch'] + df['low_ch']) / 2
df['cross_up'] = (df['close'] > df['midline']) & (df['close'].shift(1) <= df['midline'].shift(1))
df['vol_up'] = df['volume'] > df['volume'].rolling(10).mean()
df['entry_signal'] = df['cross_up'] & df['vol_up']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="RGB",
    ),
]


# =============================================================================
# MULTI TIMEFRAME PROXY BLOCKS
# =============================================================================

MULTI_TIMEFRAME_PROXY_BLOCKS = [
    # Higher MA Alignment
    PatternBlock(
        id="HIGHER_MA_ALIGN",
        name="Higher MA Alignment",
        category="multi_timeframe_proxy",
        formula_template="""df['ema20'] = ta.EMA(df['close'], timeperiod=20)
df['ema50'] = ta.EMA(df['close'], timeperiod=50)
df['ema100'] = ta.EMA(df['close'], timeperiod=100)
df['ema200'] = ta.EMA(df['close'], timeperiod=200)
df['aligned'] = (df['ema20'] > df['ema50']) & (df['ema50'] > df['ema100']) & (df['ema100'] > df['ema200'])
df['price_above'] = df['close'] > df['ema20']
df['entry_signal'] = df['aligned'] & df['price_above']""",
        params={},
        direction="long",
        lookback=210,
        indicators=["EMA"],
        combinable_with=["momentum", "volume"],
        strategy_type="MTF",
    ),
    # Multi-Period Momentum
    PatternBlock(
        id="MULTI_PERIOD_MOM",
        name="Multi-Period Momentum",
        category="multi_timeframe_proxy",
        formula_template="""df['roc_5'] = ta.ROC(df['close'], timeperiod=5)
df['roc_10'] = ta.ROC(df['close'], timeperiod=10)
df['roc_20'] = ta.ROC(df['close'], timeperiod=20)
df['all_positive'] = (df['roc_5'] > 0) & (df['roc_10'] > 0) & (df['roc_20'] > 0)
df['accelerating'] = df['roc_5'] > df['roc_10']
df['entry_signal'] = df['all_positive'] & df['accelerating']""",
        params={},
        direction="long",
        lookback=30,
        indicators=["ROC"],
        combinable_with=["volume", "threshold"],
        strategy_type="MTF",
    ),
    # Trend Stack
    PatternBlock(
        id="TREND_STACK",
        name="Trend Stack",
        category="multi_timeframe_proxy",
        formula_template="""df['above_sma20'] = df['close'] > ta.SMA(df['close'], timeperiod=20)
df['above_sma50'] = df['close'] > ta.SMA(df['close'], timeperiod=50)
df['above_sma100'] = df['close'] > ta.SMA(df['close'], timeperiod=100)
df['stack_score'] = df['above_sma20'].astype(int) + df['above_sma50'].astype(int) + df['above_sma100'].astype(int)
df['full_stack'] = df['stack_score'] == 3
df['was_partial'] = df['stack_score'].shift(1) == 2
df['entry_signal'] = df['full_stack'] & df['was_partial']""",
        params={},
        direction="long",
        lookback=110,
        indicators=["SMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="MTF",
    ),
]


# =============================================================================
# PRICE STRUCTURE BLOCKS
# =============================================================================

PRICE_STRUCTURE_BLOCKS = [
    # Higher High Confirm
    PatternBlock(
        id="HIGHER_HIGH_CONFIRM",
        name="Higher High Confirm",
        category="price_structure",
        formula_template="""df['high_5'] = df['high'].rolling(5).max()
df['prev_high'] = df['high_5'].shift(5)
df['higher_high'] = df['high_5'] > df['prev_high']
df['close_strong'] = df['close'] > df['close'].shift(5)
df['vol_confirm'] = df['volume'] > df['volume'].rolling(10).mean()
df['entry_signal'] = df['higher_high'] & df['close_strong'] & df['vol_confirm']""",
        params={},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="PST",
    ),
    # Lower Low Break
    PatternBlock(
        id="LOWER_LOW_BREAK",
        name="Lower Low Break",
        category="price_structure",
        formula_template="""df['low_5'] = df['low'].rolling(5).min()
df['prev_low'] = df['low_5'].shift(5)
df['lower_low'] = df['low_5'] < df['prev_low']
df['reversal'] = df['close'] > df['open']
df['reclaim'] = df['close'] > df['prev_low']
df['entry_signal'] = df['lower_low'].shift(1) & df['reversal'] & df['reclaim']""",
        params={},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PST",
    ),
    # Structure Shift
    PatternBlock(
        id="STRUCTURE_SHIFT",
        name="Structure Shift",
        category="price_structure",
        formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
df['swing_low'] = df['low'].rolling({period}).min()
df['break_high'] = df['close'] > df['swing_high'].shift(1)
df['was_downtrend'] = df['close'].shift(5) < df['close'].shift(10)
df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
df['entry_signal'] = df['break_high'] & df['was_downtrend'] & df['vol_surge']""",
        params={"period": [10]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="PST",
    ),
]


# =============================================================================
# VOLATILITY REGIME EXTENDED BLOCKS
# =============================================================================

VOLATILITY_REGIME_EXT_BLOCKS = [
    # Vol Expansion Phase
    PatternBlock(
        id="VOL_EXPANSION_PHASE",
        name="Vol Expansion Phase",
        category="volatility_regime_ext",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['atr_ma'] = df['atr'].rolling(20).mean()
df['expansion'] = df['atr'] > df['atr_ma'] * {mult}
df['trend_up'] = df['close'] > ta.EMA(df['close'], timeperiod=20)
df['entry_signal'] = df['expansion'] & df['trend_up']""",
        params={"mult": [1.3, 1.5]},
        direction="long",
        lookback=35,
        indicators=["ATR", "EMA"],
        combinable_with=["momentum", "volume"],
        strategy_type="VRE",
    ),
    # Contraction Alert
    PatternBlock(
        id="CONTRACTION_ALERT",
        name="Contraction Alert",
        category="volatility_regime_ext",
        formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
df['width_pct'] = df['bb_width'].rolling(50).apply(lambda x: (x.iloc[-1] < x).sum() / len(x) * 100, raw=False)
df['extreme_contraction'] = df['width_pct'] < {threshold}
df['entry_signal'] = df['extreme_contraction']""",
        params={"threshold": [10, 20]},
        direction="bidi",
        lookback=60,
        indicators=["BBANDS"],
        combinable_with=["volume", "momentum"],
        strategy_type="VRE",
    ),
    # Regime Change
    PatternBlock(
        id="REGIME_CHANGE",
        name="Regime Change",
        category="volatility_regime_ext",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['atr_fast'] = df['atr'].rolling(5).mean()
df['atr_slow'] = df['atr'].rolling(20).mean()
df['regime_shift'] = (df['atr_fast'] > df['atr_slow'] * {mult}) & (df['atr_fast'].shift(3) <= df['atr_slow'].shift(3))
df['direction'] = df['close'] > df['close'].shift(3)
df['entry_signal'] = df['regime_shift'] & df['direction']""",
        params={"mult": [1.2, 1.5]},
        direction="long",
        lookback=35,
        indicators=["ATR"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VRE",
    ),
]


# =============================================================================
# SMART MONEY BLOCKS
# =============================================================================

SMART_MONEY_BLOCKS = [
    # Accumulation Pattern
    PatternBlock(
        id="ACCUMULATION_PATTERN",
        name="Accumulation Pattern",
        category="smart_money",
        formula_template="""df['range'] = df['high'] - df['low']
df['narrow_range'] = df['range'] < df['range'].rolling(20).mean() * 0.7
df['high_volume'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
df['close_high'] = df['close'] > (df['high'] + df['low']) / 2
df['accumulation'] = df['narrow_range'] & df['high_volume'] & df['close_high']
df['accum_count'] = df['accumulation'].rolling(10).sum()
df['entry_signal'] = df['accum_count'] >= 2""",
        params={"mult": [1.3, 1.5]},
        direction="long",
        lookback=35,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="SMB",
    ),
    # Distribution Detect
    PatternBlock(
        id="DISTRIBUTION_DETECT",
        name="Distribution Detect",
        category="smart_money",
        formula_template="""df['range'] = df['high'] - df['low']
df['narrow_range'] = df['range'] < df['range'].rolling(20).mean() * 0.7
df['high_volume'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
df['close_low'] = df['close'] < (df['high'] + df['low']) / 2
df['distribution'] = df['narrow_range'] & df['high_volume'] & df['close_low']
df['dist_count'] = df['distribution'].rolling(10).sum()
df['entry_signal'] = df['dist_count'] >= 2""",
        params={"mult": [1.3, 1.5]},
        direction="short",
        lookback=35,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="SMB",
    ),
    # Institutional Volume
    PatternBlock(
        id="INSTITUTIONAL_VOL",
        name="Institutional Volume",
        category="smart_money",
        formula_template="""df['vol_ma'] = df['volume'].rolling(20).mean()
df['vol_std'] = df['volume'].rolling(20).std()
df['vol_zscore'] = (df['volume'] - df['vol_ma']) / df['vol_std']
df['inst_vol'] = df['vol_zscore'] > {threshold}
df['bullish_bar'] = df['close'] > df['open']
df['body_ratio'] = abs(df['close'] - df['open']) / (df['high'] - df['low'] + 0.0001)
df['strong_body'] = df['body_ratio'] > 0.6
df['entry_signal'] = df['inst_vol'] & df['bullish_bar'] & df['strong_body']""",
        params={"threshold": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="SMB",
    ),
]


# =============================================================================
# GAP ANALYSIS BLOCKS
# =============================================================================

GAP_ANALYSIS_BLOCKS = [
    # Gap Up Continuation
    PatternBlock(
        id="GAP_UP_CONT",
        name="Gap Up Continuation",
        category="gap_analysis",
        formula_template="""df['gap'] = df['open'] - df['close'].shift(1)
df['gap_pct'] = df['gap'] / df['close'].shift(1) * 100
df['gap_up'] = df['gap_pct'] > {threshold}
df['holds'] = df['low'] > df['close'].shift(1)
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['gap_up'] & df['holds'] & df['bullish']""",
        params={"threshold": [0.5, 1.0]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="GAX",
    ),
    # Gap Fill Reversal
    PatternBlock(
        id="GAP_FILL_REV",
        name="Gap Fill Reversal",
        category="gap_analysis",
        formula_template="""df['gap'] = df['open'] - df['close'].shift(1)
df['gap_pct'] = df['gap'] / df['close'].shift(1) * 100
df['gap_down'] = df['gap_pct'] < -{threshold}
df['filled'] = df['high'] >= df['close'].shift(1)
df['reversal'] = df['close'] > df['open']
df['entry_signal'] = df['gap_down'] & df['filled'] & df['reversal']""",
        params={"threshold": [0.5, 1.0]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="GAX",
    ),
    # Unfilled Gap Breakout
    PatternBlock(
        id="UNFILLED_GAP_BREAK",
        name="Unfilled Gap Breakout",
        category="gap_analysis",
        formula_template="""df['gap'] = df['open'] - df['close'].shift(1)
df['gap_pct'] = df['gap'] / df['close'].shift(1) * 100
df['gap_up'] = df['gap_pct'] > 0.3
df['unfilled'] = df['low'].rolling(5).min() > df['close'].shift(6)
df['break_high'] = df['close'] > df['high'].shift(1).rolling(3).max()
df['entry_signal'] = df['unfilled'] & df['break_high']""",
        params={},
        direction="long",
        lookback=15,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="GAX",
    ),
]


# =============================================================================
# ORDERFLOW PROXY BLOCKS
# =============================================================================

ORDERFLOW_PROXY_BLOCKS = [
    # Delta Divergence
    PatternBlock(
        id="DELTA_DIV",
        name="Delta Divergence",
        category="orderflow_proxy",
        formula_template="""df['delta'] = (df['close'] - df['open']) * df['volume']
df['cum_delta'] = df['delta'].rolling({period}).sum()
df['price_down'] = df['close'] < df['close'].shift({period})
df['delta_up'] = df['cum_delta'] > df['cum_delta'].shift({period})
df['divergence'] = df['price_down'] & df['delta_up']
df['entry_signal'] = df['divergence']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="OFP",
    ),
    # Absorption Pattern
    PatternBlock(
        id="ABSORPTION_PATTERN",
        name="Absorption Pattern",
        category="orderflow_proxy",
        formula_template="""df['range'] = df['high'] - df['low']
df['body'] = abs(df['close'] - df['open'])
df['small_body'] = df['body'] < df['range'] * 0.3
df['high_vol'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
df['absorption'] = df['small_body'] & df['high_vol']
df['next_bullish'] = df['close'] > df['open']
df['entry_signal'] = df['absorption'].shift(1) & df['next_bullish']""",
        params={"mult": [1.5, 2.0]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="OFP",
    ),
    # Imbalance Detect
    PatternBlock(
        id="IMBALANCE_DETECT",
        name="Imbalance Detect",
        category="orderflow_proxy",
        formula_template="""df['up_vol'] = df['volume'].where(df['close'] > df['open'], 0)
df['dn_vol'] = df['volume'].where(df['close'] < df['open'], 0)
df['vol_ratio'] = df['up_vol'].rolling({period}).sum() / (df['dn_vol'].rolling({period}).sum() + 1)
df['imbalance'] = df['vol_ratio'] > {threshold}
df['trend_up'] = df['close'] > ta.EMA(df['close'], timeperiod=20)
df['entry_signal'] = df['imbalance'] & df['trend_up']""",
        params={"period": [10], "threshold": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=["EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="OFP",
    ),
]


# =============================================================================
# LIQUIDITY BLOCKS
# =============================================================================

LIQUIDITY_BLOCKS = [
    # Liquidity Sweep
    PatternBlock(
        id="LIQUIDITY_SWEEP",
        name="Liquidity Sweep",
        category="liquidity",
        formula_template="""df['prev_low'] = df['low'].shift(1).rolling({period}).min()
df['sweep'] = df['low'] < df['prev_low']
df['reclaim'] = df['close'] > df['prev_low']
df['vol_spike'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
df['entry_signal'] = df['sweep'] & df['reclaim'] & df['vol_spike']""",
        params={"period": [10, 20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="LIQ",
    ),
    # Stop Hunt Reversal
    PatternBlock(
        id="STOP_HUNT_REV",
        name="Stop Hunt Reversal",
        category="liquidity",
        formula_template="""df['low_20'] = df['low'].rolling(20).min()
df['break_low'] = df['low'] < df['low_20'].shift(1)
df['wick'] = df['close'] - df['low']
df['body'] = abs(df['close'] - df['open'])
df['long_wick'] = df['wick'] > df['body'] * {mult}
df['bullish_close'] = df['close'] > df['open']
df['entry_signal'] = df['break_low'] & df['long_wick'] & df['bullish_close']""",
        params={"mult": [2.0, 3.0]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="LIQ",
    ),
    # Liquidity Void
    PatternBlock(
        id="LIQUIDITY_VOID",
        name="Liquidity Void",
        category="liquidity",
        formula_template="""df['gap'] = df['low'] - df['high'].shift(1)
df['void'] = df['gap'] > df['close'].shift(1) * 0.005
df['void_fill'] = df['low'] <= df['high'].shift(2)
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['void'].shift(1) & df['void_fill'] & df['bullish']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="LIQ",
    ),
]


# =============================================================================
# CYCLE DETECTION BLOCKS
# =============================================================================

CYCLE_DETECTION_BLOCKS = [
    # Cycle Low
    PatternBlock(
        id="CYCLE_LOW",
        name="Cycle Low",
        category="cycle_detection",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['rsi_low'] = df['rsi'].rolling({period}).min()
df['at_cycle_low'] = df['rsi'] <= df['rsi_low'] * 1.05
df['turning'] = df['rsi'] > df['rsi'].shift(1)
df['price_support'] = df['close'] > df['low'].rolling(10).min()
df['entry_signal'] = df['at_cycle_low'] & df['turning'] & df['price_support']""",
        params={"period": [20, 30]},
        direction="long",
        lookback=40,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="CYC",
    ),
    # Cycle High
    PatternBlock(
        id="CYCLE_HIGH",
        name="Cycle High",
        category="cycle_detection",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['rsi_high'] = df['rsi'].rolling({period}).max()
df['at_cycle_high'] = df['rsi'] >= df['rsi_high'] * 0.95
df['turning'] = df['rsi'] < df['rsi'].shift(1)
df['price_resist'] = df['close'] < df['high'].rolling(10).max()
df['entry_signal'] = df['at_cycle_high'] & df['turning'] & df['price_resist']""",
        params={"period": [20, 30]},
        direction="short",
        lookback=40,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="CYC",
    ),
    # Cycle Midpoint
    PatternBlock(
        id="CYCLE_MIDPOINT",
        name="Cycle Midpoint",
        category="cycle_detection",
        formula_template="""df['high_p'] = df['high'].rolling({period}).max()
df['low_p'] = df['low'].rolling({period}).min()
df['midpoint'] = (df['high_p'] + df['low_p']) / 2
df['cross_up'] = (df['close'] > df['midpoint']) & (df['close'].shift(1) <= df['midpoint'].shift(1))
df['momentum'] = df['close'] > df['close'].shift(3)
df['entry_signal'] = df['cross_up'] & df['momentum']""",
        params={"period": [20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="CYC",
    ),
]


# =============================================================================
# STRENGTH WEAKNESS BLOCKS
# =============================================================================

STRENGTH_WEAKNESS_BLOCKS = [
    # Relative Strength
    PatternBlock(
        id="RELATIVE_STRENGTH",
        name="Relative Strength",
        category="strength_weakness",
        formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
df['roc_ma'] = df['roc'].rolling(20).mean()
df['strong'] = df['roc'] > df['roc_ma'] * {mult}
df['trend_up'] = df['close'] > ta.EMA(df['close'], timeperiod=20)
df['entry_signal'] = df['strong'] & df['trend_up']""",
        params={"period": [10], "mult": [1.5, 2.0]},
        direction="long",
        lookback=35,
        indicators=["ROC", "EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="STW",
    ),
    # Weakness Confirm
    PatternBlock(
        id="WEAKNESS_CONFIRM",
        name="Weakness Confirm",
        category="strength_weakness",
        formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
df['weak'] = df['roc'] < -{threshold}
df['trend_down'] = df['close'] < ta.EMA(df['close'], timeperiod=20)
df['vol_up'] = df['volume'] > df['volume'].rolling(20).mean()
df['entry_signal'] = df['weak'] & df['trend_down'] & df['vol_up']""",
        params={"period": [10], "threshold": [2, 3]},
        direction="short",
        lookback=35,
        indicators=["ROC", "EMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="STW",
    ),
    # Strength Divergence
    PatternBlock(
        id="STRENGTH_DIV",
        name="Strength Divergence",
        category="strength_weakness",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['price_higher'] = df['close'] > df['close'].shift(10)
df['rsi_lower'] = df['rsi'] < df['rsi'].shift(10)
df['bearish_div'] = df['price_higher'] & df['rsi_lower']
df['overbought'] = df['rsi'] > 60
df['entry_signal'] = df['bearish_div'] & df['overbought']""",
        params={},
        direction="short",
        lookback=25,
        indicators=["RSI"],
        combinable_with=["volume", "threshold"],
        strategy_type="STW",
    ),
]


# =============================================================================
# PATTERN COMPLETION BLOCKS
# =============================================================================

PATTERN_COMPLETION_BLOCKS = [
    # Double Bottom Confirm
    PatternBlock(
        id="DOUBLE_BOTTOM_CONFIRM",
        name="Double Bottom Confirm",
        category="pattern_completion",
        formula_template="""df['low_10'] = df['low'].rolling(10).min()
df['first_low'] = df['low_10'].shift(10)
df['second_low'] = df['low_10']
df['similar'] = abs(df['second_low'] - df['first_low']) / df['close'] < 0.02
df['neckline'] = df['high'].shift(5).rolling(5).max()
df['break_neck'] = df['close'] > df['neckline']
df['entry_signal'] = df['similar'] & df['break_neck']""",
        params={},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PTC",
    ),
    # Head Shoulders Neckline
    PatternBlock(
        id="HS_NECKLINE",
        name="Head Shoulders Neckline",
        category="pattern_completion",
        formula_template="""df['high_20'] = df['high'].rolling(20).max()
df['was_high'] = df['high'].shift(10) >= df['high_20'].shift(10) * 0.98
df['lower_now'] = df['high'] < df['high'].shift(10) * 0.95
df['neckline'] = df['low'].shift(5).rolling(10).min()
df['break_neck'] = df['close'] < df['neckline']
df['entry_signal'] = df['was_high'] & df['lower_now'] & df['break_neck']""",
        params={},
        direction="short",
        lookback=35,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="PTC",
    ),
    # Wedge Break
    PatternBlock(
        id="WEDGE_BREAK",
        name="Wedge Break",
        category="pattern_completion",
        formula_template="""df['high_slope'] = (df['high'] - df['high'].shift({period})) / {period}
df['low_slope'] = (df['low'] - df['low'].shift({period})) / {period}
df['converging'] = df['high_slope'] < df['low_slope']
df['wedge'] = df['converging'].rolling(5).sum() >= 3
df['break_up'] = df['close'] > df['high'].shift(1).rolling(5).max()
df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
df['entry_signal'] = df['wedge'].shift(1) & df['break_up'] & df['vol_surge']""",
        params={"period": [10]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="PTC",
    ),
]


# =============================================================================
# MONEY FLOW EXTENDED BLOCKS
# =============================================================================

MONEY_FLOW_EXT_BLOCKS = [
    # Chaikin MF Extreme
    PatternBlock(
        id="CMF_EXTREME",
        name="Chaikin MF Extreme",
        category="money_flow_ext",
        formula_template="""df['mfm'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'] + 0.0001)
df['mfv'] = df['mfm'] * df['volume']
df['cmf'] = df['mfv'].rolling({period}).sum() / df['volume'].rolling({period}).sum()
df['extreme_low'] = df['cmf'] < -{threshold}
df['turning'] = df['cmf'] > df['cmf'].shift(1)
df['entry_signal'] = df['extreme_low'] & df['turning']""",
        params={"period": [20], "threshold": [0.2, 0.25]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="MFX",
    ),
    # MFI Divergence
    PatternBlock(
        id="MFI_DIV",
        name="MFI Divergence",
        category="money_flow_ext",
        formula_template="""df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)
df['price_lower'] = df['close'] < df['close'].shift({period})
df['mfi_higher'] = df['mfi'] > df['mfi'].shift({period})
df['bullish_div'] = df['price_lower'] & df['mfi_higher']
df['entry_signal'] = df['bullish_div']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=25,
        indicators=["MFI"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="MFX",
    ),
    # Flow Reversal
    PatternBlock(
        id="FLOW_REVERSAL",
        name="Flow Reversal",
        category="money_flow_ext",
        formula_template="""df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)
df['was_oversold'] = df['mfi'].shift(3) < 20
df['recovering'] = df['mfi'] > 30
df['price_up'] = df['close'] > df['close'].shift(3)
df['entry_signal'] = df['was_oversold'] & df['recovering'] & df['price_up']""",
        params={},
        direction="long",
        lookback=25,
        indicators=["MFI"],
        combinable_with=["volume", "threshold"],
        strategy_type="MFX",
    ),
]


# =============================================================================
# TREND FILTER BLOCKS
# =============================================================================

TREND_FILTER_BLOCKS = [
    # ADX Filter
    PatternBlock(
        id="ADX_FILTER",
        name="ADX Filter",
        category="trend_filter",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
df['trending'] = df['adx'] > {threshold}
df['bullish'] = df['plus_di'] > df['minus_di']
df['entry_signal'] = df['trending'] & df['bullish']""",
        params={"threshold": [20, 25]},
        direction="long",
        lookback=25,
        indicators=["ADX", "PLUS_DI", "MINUS_DI"],
        combinable_with=["momentum", "volume"],
        strategy_type="TFL",
    ),
    # MA Slope Filter
    PatternBlock(
        id="MA_SLOPE_FILTER",
        name="MA Slope Filter",
        category="trend_filter",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['slope'] = (df['ema'] - df['ema'].shift(5)) / df['ema'].shift(5) * 100
df['strong_slope'] = df['slope'] > {threshold}
df['price_above'] = df['close'] > df['ema']
df['entry_signal'] = df['strong_slope'] & df['price_above']""",
        params={"period": [20], "threshold": [0.5, 1.0]},
        direction="long",
        lookback=35,
        indicators=["EMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="TFL",
    ),
    # Momentum Filter
    PatternBlock(
        id="MOMENTUM_FILTER",
        name="Momentum Filter",
        category="trend_filter",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['macd'], _, df['macd_hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
df['rsi_bullish'] = df['rsi'] > 50
df['macd_bullish'] = df['macd_hist'] > 0
df['price_up'] = df['close'] > df['close'].shift(5)
df['entry_signal'] = df['rsi_bullish'] & df['macd_bullish'] & df['price_up']""",
        params={},
        direction="long",
        lookback=35,
        indicators=["RSI", "MACD"],
        combinable_with=["volume", "threshold"],
        strategy_type="TFL",
    ),
]


# =============================================================================
# ENTRY TIMING BLOCKS
# =============================================================================

ENTRY_TIMING_BLOCKS = [
    # Optimal Entry
    PatternBlock(
        id="OPTIMAL_ENTRY",
        name="Optimal Entry",
        category="entry_timing",
        formula_template="""df['ema20'] = ta.EMA(df['close'], timeperiod=20)
df['ema50'] = ta.EMA(df['close'], timeperiod=50)
df['uptrend'] = df['ema20'] > df['ema50']
df['pullback'] = df['close'] < df['ema20'] * 1.01
df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['not_oversold'] = df['rsi'] > 35
df['bounce'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['uptrend'] & df['pullback'] & df['not_oversold'] & df['bounce']""",
        params={},
        direction="long",
        lookback=60,
        indicators=["EMA", "RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="ETM",
    ),
    # Pullback Timing
    PatternBlock(
        id="PULLBACK_TIMING",
        name="Pullback Timing",
        category="entry_timing",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['distance'] = (df['close'] - df['ema']) / df['ema'] * 100
df['was_extended'] = df['distance'].shift(3) > 2
df['returned'] = abs(df['distance']) < 0.5
df['bounce'] = df['close'] > df['open']
df['entry_signal'] = df['was_extended'] & df['returned'] & df['bounce']""",
        params={"period": [20, 50]},
        direction="long",
        lookback=60,
        indicators=["EMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="ETM",
    ),
    # Breakout Timing
    PatternBlock(
        id="BREAKOUT_TIMING",
        name="Breakout Timing",
        category="entry_timing",
        formula_template="""df['high_20'] = df['high'].rolling(20).max()
df['break'] = df['close'] > df['high_20'].shift(1)
df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
df['strong_close'] = df['close'] > (df['high'] + df['low']) / 2
df['entry_signal'] = df['break'] & df['vol_confirm'] & df['strong_close']""",
        params={"mult": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="ETM",
    ),
]


# =============================================================================
# EXIT SIGNAL BLOCKS
# =============================================================================

EXIT_SIGNAL_BLOCKS = [
    # Profit Target Hit
    PatternBlock(
        id="PROFIT_TARGET",
        name="Profit Target Hit",
        category="exit_signal",
        formula_template="""df['entry_price'] = df['close'].shift({lookback})
df['profit_pct'] = (df['close'] - df['entry_price']) / df['entry_price'] * 100
df['target_hit'] = df['profit_pct'] >= {target}
df['momentum_fading'] = ta.RSI(df['close'], timeperiod=14) > 70
df['entry_signal'] = df['target_hit'] & df['momentum_fading']""",
        params={"lookback": [10], "target": [3, 5]},
        direction="short",
        lookback=25,
        indicators=["RSI"],
        combinable_with=["momentum", "threshold"],
        strategy_type="EXS",
    ),
    # Trailing Stop Trigger
    PatternBlock(
        id="TRAIL_STOP_TRIGGER",
        name="Trailing Stop Trigger",
        category="exit_signal",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['high_since'] = df['high'].rolling({period}).max()
df['trail_stop'] = df['high_since'] - df['atr'] * {mult}
df['stop_hit'] = df['close'] < df['trail_stop']
df['was_profit'] = df['high_since'] > df['close'].shift({period}) * 1.02
df['entry_signal'] = df['stop_hit'] & df['was_profit']""",
        params={"period": [10], "mult": [2.0, 3.0]},
        direction="short",
        lookback=25,
        indicators=["ATR"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="EXS",
    ),
    # Time Exit Signal
    PatternBlock(
        id="TIME_EXIT_SIGNAL",
        name="Time Exit Signal",
        category="exit_signal",
        formula_template="""df['bars_since_high'] = df['high'].rolling({period}).apply(lambda x: {period} - 1 - x.argmax(), raw=True)
df['stale'] = df['bars_since_high'] >= {period} - 2
df['momentum_lost'] = ta.RSI(df['close'], timeperiod=14) < 50
df['below_ma'] = df['close'] < ta.EMA(df['close'], timeperiod=20)
df['entry_signal'] = df['stale'] & df['momentum_lost'] & df['below_ma']""",
        params={"period": [10, 20]},
        direction="short",
        lookback=30,
        indicators=["RSI", "EMA"],
        combinable_with=["volume", "threshold"],
        strategy_type="EXS",
    ),
]


# =============================================================================
# MARKET REGIME BLOCKS
# =============================================================================

MARKET_REGIME_BLOCKS = [
    # Trending Regime
    PatternBlock(
        id="TRENDING_REGIME",
        name="Trending Regime",
        category="market_regime",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
df['trending'] = df['adx'] > {threshold}
df['bullish_trend'] = df['plus_di'] > df['minus_di']
df['adx_rising'] = df['adx'] > df['adx'].shift(3)
df['entry_signal'] = df['trending'] & df['bullish_trend'] & df['adx_rising']""",
        params={"threshold": [25, 30]},
        direction="long",
        lookback=25,
        indicators=["ADX", "PLUS_DI", "MINUS_DI"],
        combinable_with=["momentum", "volume"],
        strategy_type="MRG",
    ),
    # Ranging Regime
    PatternBlock(
        id="RANGING_REGIME",
        name="Ranging Regime",
        category="market_regime",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
df['ranging'] = df['adx'] < {threshold}
df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['oversold'] = df['rsi'] < 35
df['bounce'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['ranging'] & df['oversold'] & df['bounce']""",
        params={"threshold": [20, 25]},
        direction="long",
        lookback=25,
        indicators=["ADX", "RSI"],
        combinable_with=["volume", "threshold"],
        strategy_type="MRG",
    ),
    # Volatile Regime
    PatternBlock(
        id="VOLATILE_REGIME",
        name="Volatile Regime",
        category="market_regime",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['atr_ma'] = df['atr'].rolling(20).mean()
df['volatile'] = df['atr'] > df['atr_ma'] * {mult}
df['direction'] = df['close'] > ta.EMA(df['close'], timeperiod=20)
df['momentum'] = df['close'] > df['close'].shift(3)
df['entry_signal'] = df['volatile'] & df['direction'] & df['momentum']""",
        params={"mult": [1.5, 2.0]},
        direction="long",
        lookback=35,
        indicators=["ATR", "EMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="MRG",
    ),
]


# =============================================================================
# PRICE EFFICIENCY BLOCKS
# =============================================================================

PRICE_EFFICIENCY_BLOCKS = [
    # Efficiency Ratio Signal
    PatternBlock(
        id="EFFICIENCY_SIGNAL",
        name="Efficiency Ratio Signal",
        category="price_efficiency",
        formula_template="""df['change'] = abs(df['close'] - df['close'].shift({period}))
df['volatility'] = df['close'].diff().abs().rolling({period}).sum()
df['er'] = df['change'] / (df['volatility'] + 0.0001)
df['efficient'] = df['er'] > {threshold}
df['direction'] = df['close'] > df['close'].shift({period})
df['entry_signal'] = df['efficient'] & df['direction']""",
        params={"period": [10], "threshold": [0.5, 0.6]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["momentum", "volume"],
        strategy_type="PEF",
    ),
    # Fractal Efficiency
    PatternBlock(
        id="FRACTAL_EFFICIENCY",
        name="Fractal Efficiency",
        category="price_efficiency",
        formula_template="""df['range'] = df['high'].rolling({period}).max() - df['low'].rolling({period}).min()
df['path'] = (df['high'] - df['low']).rolling({period}).sum()
df['fe'] = df['range'] / (df['path'] + 0.0001)
df['high_fe'] = df['fe'] > {threshold}
df['trend_up'] = df['close'] > df['close'].shift({period})
df['entry_signal'] = df['high_fe'] & df['trend_up']""",
        params={"period": [10], "threshold": [0.4, 0.5]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PEF",
    ),
    # Noise Filter
    PatternBlock(
        id="NOISE_FILTER",
        name="Noise Filter",
        category="price_efficiency",
        formula_template="""df['signal'] = abs(df['close'] - df['close'].shift({period}))
df['noise'] = df['close'].diff().abs().rolling({period}).sum()
df['snr'] = df['signal'] / (df['noise'] + 0.0001)
df['clean'] = df['snr'] > {threshold}
df['bullish'] = df['close'] > df['close'].shift({period})
df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean()
df['entry_signal'] = df['clean'] & df['bullish'] & df['vol_confirm']""",
        params={"period": [10], "threshold": [0.3, 0.4]},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="PEF",
    ),
]


# =============================================================================
# VOLUME CLIMAX EXTENDED BLOCKS
# =============================================================================

VOLUME_CLIMAX_EXT_BLOCKS = [
    # Buying Climax
    PatternBlock(
        id="BUYING_CLIMAX",
        name="Buying Climax",
        category="volume_climax_ext",
        formula_template="""df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
df['wide_range'] = (df['high'] - df['low']) > (df['high'] - df['low']).rolling(20).mean() * 1.5
df['close_high'] = df['close'] > (df['high'] + df['low']) / 2
df['new_high'] = df['high'] >= df['high'].rolling(20).max()
df['climax'] = df['vol_surge'] & df['wide_range'] & df['close_high'] & df['new_high']
df['entry_signal'] = df['climax']""",
        params={"mult": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VCX",
    ),
    # Selling Climax
    PatternBlock(
        id="SELLING_CLIMAX",
        name="Selling Climax",
        category="volume_climax_ext",
        formula_template="""df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
df['wide_range'] = (df['high'] - df['low']) > (df['high'] - df['low']).rolling(20).mean() * 1.5
df['close_low'] = df['close'] < (df['high'] + df['low']) / 2
df['new_low'] = df['low'] <= df['low'].rolling(20).min()
df['climax'] = df['vol_surge'] & df['wide_range'] & df['close_low'] & df['new_low']
df['reversal'] = df['close'] > df['open']
df['entry_signal'] = df['climax'].shift(1) & df['reversal']""",
        params={"mult": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="VCX",
    ),
    # Exhaustion Volume
    PatternBlock(
        id="EXHAUSTION_VOL",
        name="Exhaustion Volume",
        category="volume_climax_ext",
        formula_template="""df['vol_spike'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
df['small_body'] = abs(df['close'] - df['open']) < (df['high'] - df['low']) * 0.3
df['exhaustion'] = df['vol_spike'] & df['small_body']
df['direction_change'] = (df['close'] > df['open']) != (df['close'].shift(1) > df['open'].shift(1))
df['entry_signal'] = df['exhaustion'] & df['direction_change']""",
        params={"mult": [2.0, 3.0]},
        direction="bidi",
        lookback=25,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VCX",
    ),
]


# =============================================================================
# REVERSAL CONFIRM BLOCKS
# =============================================================================

REVERSAL_CONFIRM_BLOCKS = [
    # Pin Bar Confirm
    PatternBlock(
        id="PIN_BAR_CONFIRM",
        name="Pin Bar Confirm",
        category="reversal_confirm",
        formula_template="""df['body'] = abs(df['close'] - df['open'])
df['range'] = df['high'] - df['low']
df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
df['pin_bar'] = (df['lower_wick'] > df['body'] * {mult}) & (df['body'] < df['range'] * 0.3)
df['at_low'] = df['low'] <= df['low'].rolling(10).min() * 1.01
df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean()
df['entry_signal'] = df['pin_bar'] & df['at_low'] & df['vol_confirm']""",
        params={"mult": [2.0, 2.5]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="RVC",
    ),
    # Engulfing Confirm
    PatternBlock(
        id="ENGULFING_CONFIRM",
        name="Engulfing Confirm",
        category="reversal_confirm",
        formula_template="""df['prev_bearish'] = df['close'].shift(1) < df['open'].shift(1)
df['curr_bullish'] = df['close'] > df['open']
df['engulfs'] = (df['open'] < df['close'].shift(1)) & (df['close'] > df['open'].shift(1))
df['engulfing'] = df['prev_bearish'] & df['curr_bullish'] & df['engulfs']
df['at_support'] = df['low'] <= df['low'].rolling(10).min() * 1.02
df['entry_signal'] = df['engulfing'] & df['at_support']""",
        params={},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="RVC",
    ),
    # Key Reversal
    PatternBlock(
        id="KEY_REVERSAL",
        name="Key Reversal",
        category="reversal_confirm",
        formula_template="""df['new_low'] = df['low'] < df['low'].shift(1).rolling(5).min()
df['close_above'] = df['close'] > df['high'].shift(1)
df['key_rev'] = df['new_low'] & df['close_above']
df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
df['entry_signal'] = df['key_rev'] & df['vol_surge']""",
        params={"mult": [1.5, 2.0]},
        direction="long",
        lookback=15,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="RVC",
    ),
]


# =============================================================================
# CONTINUATION PATTERN BLOCKS
# =============================================================================

CONTINUATION_PATTERN_BLOCKS = [
    # Flag Breakout
    PatternBlock(
        id="FLAG_BREAKOUT",
        name="Flag Breakout",
        category="continuation_pattern",
        formula_template="""df['prior_move'] = df['close'].shift(5) - df['close'].shift(15)
df['strong_move'] = df['prior_move'] > df['close'].shift(15) * 0.05
df['consolidation'] = (df['high'].rolling(5).max() - df['low'].rolling(5).min()) < df['close'] * 0.02
df['breakout'] = df['close'] > df['high'].shift(1).rolling(5).max()
df['entry_signal'] = df['strong_move'] & df['consolidation'].shift(1) & df['breakout']""",
        params={},
        direction="long",
        lookback=25,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="CNP",
    ),
    # Pennant Break
    PatternBlock(
        id="PENNANT_BREAK",
        name="Pennant Break",
        category="continuation_pattern",
        formula_template="""df['range'] = df['high'].rolling(5).max() - df['low'].rolling(5).min()
df['range_shrink'] = df['range'] < df['range'].shift(5) * {mult}
df['shrink_days'] = df['range_shrink'].rolling(5).sum() >= 3
df['break_up'] = df['close'] > df['high'].shift(1).rolling(3).max()
df['vol_up'] = df['volume'] > df['volume'].shift(1)
df['entry_signal'] = df['shrink_days'].shift(1) & df['break_up'] & df['vol_up']""",
        params={"mult": [0.7, 0.8]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="CNP",
    ),
    # Triangle Break
    PatternBlock(
        id="TRIANGLE_BREAK",
        name="Triangle Break",
        category="continuation_pattern",
        formula_template="""df['high_slope'] = df['high'].rolling({period}).apply(lambda x: (x.iloc[-1] - x.iloc[0]) / {period}, raw=False)
df['low_slope'] = df['low'].rolling({period}).apply(lambda x: (x.iloc[-1] - x.iloc[0]) / {period}, raw=False)
df['converging'] = (df['high_slope'] < 0) & (df['low_slope'] > 0)
df['break_high'] = df['close'] > df['high'].shift(1).rolling(5).max()
df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean() * 1.3
df['entry_signal'] = df['converging'].shift(1) & df['break_high'] & df['vol_confirm']""",
        params={"period": [10]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="CNP",
    ),
]


# =============================================================================
# OSCILLATOR CROSS EXTENDED BLOCKS
# =============================================================================

OSCILLATOR_CROSS_EXT_BLOCKS = [
    # RSI Cross 50
    PatternBlock(
        id="RSI_CROSS_50",
        name="RSI Cross 50",
        category="oscillator_cross_ext",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
df['cross_up'] = (df['rsi'] > 50) & (df['rsi'].shift(1) <= 50)
df['momentum'] = df['rsi'] > df['rsi'].shift(3)
df['entry_signal'] = df['cross_up'] & df['momentum']""",
        params={"period": [14]},
        direction="long",
        lookback=25,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="OCX",
    ),
    # Stoch Cross
    PatternBlock(
        id="STOCH_CROSS_EXT",
        name="Stoch Cross Extended",
        category="oscillator_cross_ext",
        formula_template="""df['stoch_k'], df['stoch_d'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowd_period=3)
df['cross_up'] = (df['stoch_k'] > df['stoch_d']) & (df['stoch_k'].shift(1) <= df['stoch_d'].shift(1))
df['oversold_zone'] = df['stoch_k'] < {level}
df['entry_signal'] = df['cross_up'] & df['oversold_zone']""",
        params={"level": [30, 40]},
        direction="long",
        lookback=25,
        indicators=["STOCH"],
        combinable_with=["momentum", "threshold"],
        strategy_type="OCX",
    ),
    # CCI Zero Cross
    PatternBlock(
        id="CCI_ZERO_CROSS",
        name="CCI Zero Cross",
        category="oscillator_cross_ext",
        formula_template="""df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod={period})
df['cross_up'] = (df['cci'] > 0) & (df['cci'].shift(1) <= 0)
df['was_oversold'] = df['cci'].shift(3) < -50
df['entry_signal'] = df['cross_up'] & df['was_oversold']""",
        params={"period": [14, 20]},
        direction="long",
        lookback=30,
        indicators=["CCI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="OCX",
    ),
]


# =============================================================================
# MA SYSTEM BLOCKS (MAS2)
# =============================================================================

MA_SYSTEM_EXT_BLOCKS = [
    # Triple MA System
    PatternBlock(
        id="TRIPLE_MA_SYS",
        name="Triple MA System",
        category="ma_system_ext",
        formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
df['ema_med'] = ta.EMA(df['close'], timeperiod={med})
df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
df['aligned'] = (df['ema_fast'] > df['ema_med']) & (df['ema_med'] > df['ema_slow'])
df['pullback'] = df['low'] <= df['ema_fast'] * 1.01
df['bounce'] = df['close'] > df['ema_fast']
df['entry_signal'] = df['aligned'] & df['pullback'] & df['bounce']""",
        params={"fast": [10], "med": [20], "slow": [50]},
        direction="long",
        lookback=60,
        indicators=["EMA"],
        combinable_with=["volume", "momentum"],
        strategy_type="MAS",
    ),
    # Ribbon Expansion
    PatternBlock(
        id="RIBBON_EXPANSION",
        name="Ribbon Expansion",
        category="ma_system_ext",
        formula_template="""df['ema10'] = ta.EMA(df['close'], timeperiod=10)
df['ema20'] = ta.EMA(df['close'], timeperiod=20)
df['ema30'] = ta.EMA(df['close'], timeperiod=30)
df['spread'] = (df['ema10'] - df['ema30']) / df['close'] * 100
df['expanding'] = df['spread'] > df['spread'].shift(3)
df['positive'] = df['spread'] > 0
df['entry_signal'] = df['expanding'] & df['positive']""",
        params={},
        direction="long",
        lookback=40,
        indicators=["EMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="MAS",
    ),
    # MA Squeeze
    PatternBlock(
        id="MA_SQUEEZE",
        name="MA Squeeze",
        category="ma_system_ext",
        formula_template="""df['ema10'] = ta.EMA(df['close'], timeperiod=10)
df['ema20'] = ta.EMA(df['close'], timeperiod=20)
df['ema50'] = ta.EMA(df['close'], timeperiod=50)
df['spread'] = (df['ema10'] - df['ema50']).abs() / df['close'] * 100
df['tight'] = df['spread'] < {threshold}
df['break_up'] = df['close'] > df['ema10']
df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
df['entry_signal'] = df['tight'].shift(1) & df['break_up'] & df['vol_surge']""",
        params={"threshold": [1.0, 1.5]},
        direction="long",
        lookback=60,
        indicators=["EMA"],
        combinable_with=["volume", "threshold"],
        strategy_type="MAS",
    ),
]


# =============================================================================
# PRICE LEVEL BLOCKS
# =============================================================================

PRICE_LEVEL_BLOCKS = [
    # Round Number
    PatternBlock(
        id="ROUND_NUMBER",
        name="Round Number",
        category="price_level",
        formula_template="""df['round_level'] = (df['close'] / {increment}).round() * {increment}
df['near_round'] = abs(df['close'] - df['round_level']) / df['close'] < 0.005
df['bounce'] = (df['low'] <= df['round_level'] * 1.005) & (df['close'] > df['round_level'])
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['near_round'] & df['bounce'] & df['bullish']""",
        params={"increment": [100, 1000]},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PLV",
    ),
    # Psychological Level
    PatternBlock(
        id="PSYCH_LEVEL",
        name="Psychological Level",
        category="price_level",
        formula_template="""df['pct_level'] = df['close'].rolling(50).min() * {mult}
df['near_level'] = abs(df['close'] - df['pct_level']) / df['close'] < 0.01
df['support_test'] = df['low'] <= df['pct_level'] * 1.01
df['hold'] = df['close'] > df['pct_level']
df['entry_signal'] = df['near_level'] & df['support_test'] & df['hold']""",
        params={"mult": [1.1, 1.2]},
        direction="long",
        lookback=60,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="PLV",
    ),
    # Pivot Cluster
    PatternBlock(
        id="PIVOT_CLUSTER",
        name="Pivot Cluster",
        category="price_level",
        formula_template="""df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
df['s1'] = 2 * df['pivot'] - df['high'].shift(1)
df['near_pivot'] = abs(df['close'] - df['pivot']) / df['close'] < 0.005
df['near_s1'] = abs(df['close'] - df['s1']) / df['close'] < 0.01
df['at_support'] = df['near_pivot'] | df['near_s1']
df['bounce'] = df['close'] > df['open']
df['entry_signal'] = df['at_support'] & df['bounce']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="PLV",
    ),
]


# =============================================================================
# VOLATILITY SQUEEZE EXTENDED BLOCKS
# =============================================================================

VOLATILITY_SQUEEZE_EXT_BLOCKS = [
    # Keltner Squeeze
    PatternBlock(
        id="KELTNER_SQUEEZE",
        name="Keltner Squeeze",
        category="volatility_squeeze_ext",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod=20)
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['kc_upper'] = df['ema'] + df['atr'] * 1.5
df['kc_lower'] = df['ema'] - df['atr'] * 1.5
df['bb_upper'], _, df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
df['squeeze'] = (df['bb_lower'] > df['kc_lower']) & (df['bb_upper'] < df['kc_upper'])
df['release'] = df['squeeze'].shift(1) & ~df['squeeze']
df['bullish'] = df['close'] > df['ema']
df['entry_signal'] = df['release'] & df['bullish']""",
        params={},
        direction="long",
        lookback=35,
        indicators=["EMA", "ATR", "BBANDS"],
        combinable_with=["momentum", "volume"],
        strategy_type="VSQ",
    ),
    # BB Squeeze Signal
    PatternBlock(
        id="BB_SQUEEZE_SIG",
        name="BB Squeeze Signal",
        category="volatility_squeeze_ext",
        formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
df['width_pct'] = df['bb_width'].rolling(50).apply(lambda x: (x.iloc[-1] < x).sum() / len(x) * 100, raw=False)
df['extreme_squeeze'] = df['width_pct'] < {threshold}
df['break_up'] = df['close'] > df['bb_upper']
df['entry_signal'] = df['extreme_squeeze'].shift(1) & df['break_up']""",
        params={"threshold": [10, 15]},
        direction="long",
        lookback=60,
        indicators=["BBANDS"],
        combinable_with=["volume", "confirmation"],
        strategy_type="VSQ",
    ),
    # ATR Squeeze
    PatternBlock(
        id="ATR_SQUEEZE",
        name="ATR Squeeze",
        category="volatility_squeeze_ext",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['atr_ma'] = df['atr'].rolling(20).mean()
df['squeeze'] = df['atr'] < df['atr_ma'] * {mult}
df['squeeze_days'] = df['squeeze'].rolling(5).sum() >= 3
df['expansion'] = df['atr'] > df['atr'].shift(1)
df['direction'] = df['close'] > df['close'].shift(3)
df['entry_signal'] = df['squeeze_days'].shift(1) & df['expansion'] & df['direction']""",
        params={"mult": [0.7, 0.8]},
        direction="long",
        lookback=35,
        indicators=["ATR"],
        combinable_with=["momentum", "threshold"],
        strategy_type="VSQ",
    ),
]


# =============================================================================
# SENTIMENT PROXY BLOCKS
# =============================================================================

SENTIMENT_PROXY_BLOCKS = [
    # Fear Extreme
    PatternBlock(
        id="FEAR_EXTREME",
        name="Fear Extreme",
        category="sentiment_proxy",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
df['below_bb'] = df['close'] < df['bb_lower']
df['rsi_fear'] = df['rsi'] < {rsi_level}
df['vol_spike'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
df['fear'] = df['below_bb'] & df['rsi_fear'] & df['vol_spike']
df['entry_signal'] = df['fear']""",
        params={"rsi_level": [25, 30]},
        direction="long",
        lookback=30,
        indicators=["RSI", "BBANDS"],
        combinable_with=["volume", "confirmation"],
        strategy_type="SNT",
    ),
    # Greed Extreme
    PatternBlock(
        id="GREED_EXTREME",
        name="Greed Extreme",
        category="sentiment_proxy",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
df['above_bb'] = df['close'] > df['bb_upper']
df['rsi_greed'] = df['rsi'] > {rsi_level}
df['vol_spike'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
df['greed'] = df['above_bb'] & df['rsi_greed'] & df['vol_spike']
df['entry_signal'] = df['greed']""",
        params={"rsi_level": [70, 75]},
        direction="short",
        lookback=30,
        indicators=["RSI", "BBANDS"],
        combinable_with=["volume", "momentum"],
        strategy_type="SNT",
    ),
    # Sentiment Flip
    PatternBlock(
        id="SENTIMENT_FLIP",
        name="Sentiment Flip",
        category="sentiment_proxy",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['was_fear'] = df['rsi'].shift(5) < 30
df['now_neutral'] = df['rsi'] > 45
df['price_recover'] = df['close'] > df['close'].shift(5)
df['flip'] = df['was_fear'] & df['now_neutral'] & df['price_recover']
df['entry_signal'] = df['flip']""",
        params={},
        direction="long",
        lookback=25,
        indicators=["RSI"],
        combinable_with=["volume", "threshold"],
        strategy_type="SNT",
    ),
]


# =============================================================================
# DIVERGENCE MULTI BLOCKS
# =============================================================================

DIVERGENCE_MULTI_BLOCKS = [
    # RSI + MACD Divergence
    PatternBlock(
        id="RSI_MACD_DIV",
        name="RSI MACD Divergence",
        category="divergence_multi",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['macd'], _, df['macd_hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
df['price_lower'] = df['close'] < df['close'].shift({period})
df['rsi_higher'] = df['rsi'] > df['rsi'].shift({period})
df['macd_higher'] = df['macd_hist'] > df['macd_hist'].shift({period})
df['double_div'] = df['price_lower'] & df['rsi_higher'] & df['macd_higher']
df['entry_signal'] = df['double_div']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=30,
        indicators=["RSI", "MACD"],
        combinable_with=["volume", "confirmation"],
        strategy_type="DVX",
    ),
    # Triple Oscillator Divergence
    PatternBlock(
        id="TRIPLE_OSC_DIV",
        name="Triple Oscillator Divergence",
        category="divergence_multi",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['stoch_k'], _ = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowd_period=3)
df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod=14)
df['price_low'] = df['close'] < df['close'].shift(10)
df['rsi_up'] = df['rsi'] > df['rsi'].shift(10)
df['stoch_up'] = df['stoch_k'] > df['stoch_k'].shift(10)
df['cci_up'] = df['cci'] > df['cci'].shift(10)
df['triple_div'] = df['price_low'] & df['rsi_up'] & df['stoch_up'] & df['cci_up']
df['entry_signal'] = df['triple_div']""",
        params={},
        direction="long",
        lookback=25,
        indicators=["RSI", "STOCH", "CCI"],
        combinable_with=["volume", "momentum"],
        strategy_type="DVX",
    ),
    # Volume Divergence
    PatternBlock(
        id="VOLUME_DIV",
        name="Volume Divergence",
        category="divergence_multi",
        formula_template="""df['obv'] = ta.OBV(df['close'], df['volume'])
df['price_lower'] = df['close'] < df['close'].shift({period})
df['obv_higher'] = df['obv'] > df['obv'].shift({period})
df['vol_increasing'] = df['volume'] > df['volume'].shift({period})
df['vol_div'] = df['price_lower'] & df['obv_higher'] & df['vol_increasing']
df['entry_signal'] = df['vol_div']""",
        params={"period": [10, 14]},
        direction="long",
        lookback=25,
        indicators=["OBV"],
        combinable_with=["momentum", "threshold"],
        strategy_type="DVX",
    ),
]


# =============================================================================
# BREAKOUT FILTER BLOCKS
# =============================================================================

BREAKOUT_FILTER_BLOCKS = [
    # Volume Breakout Filter
    PatternBlock(
        id="VOL_BREAKOUT_FILTER",
        name="Volume Breakout Filter",
        category="breakout_filter",
        formula_template="""df['high_20'] = df['high'].rolling(20).max()
df['breakout'] = df['close'] > df['high_20'].shift(1)
df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
df['body_strong'] = (df['close'] - df['open']) > (df['high'] - df['low']) * 0.5
df['entry_signal'] = df['breakout'] & df['vol_confirm'] & df['body_strong']""",
        params={"mult": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="BKF",
    ),
    # ATR Breakout Filter
    PatternBlock(
        id="ATR_BREAKOUT_FILTER",
        name="ATR Breakout Filter",
        category="breakout_filter",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['high_20'] = df['high'].rolling(20).max()
df['break_size'] = df['close'] - df['high_20'].shift(1)
df['strong_break'] = df['break_size'] > df['atr'] * {mult}
df['entry_signal'] = df['strong_break']""",
        params={"mult": [0.5, 1.0]},
        direction="long",
        lookback=30,
        indicators=["ATR"],
        combinable_with=["volume", "threshold"],
        strategy_type="BKF",
    ),
    # Momentum Breakout Filter
    PatternBlock(
        id="MOM_BREAKOUT_FILTER",
        name="Momentum Breakout Filter",
        category="breakout_filter",
        formula_template="""df['high_20'] = df['high'].rolling(20).max()
df['breakout'] = df['close'] > df['high_20'].shift(1)
df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['rsi_strong'] = df['rsi'] > {rsi_level}
df['rsi_rising'] = df['rsi'] > df['rsi'].shift(3)
df['entry_signal'] = df['breakout'] & df['rsi_strong'] & df['rsi_rising']""",
        params={"rsi_level": [55, 60]},
        direction="long",
        lookback=30,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="BKF",
    ),
]


# =============================================================================
# MEAN REVERSION EXTENDED BLOCKS
# =============================================================================

MEAN_REVERSION_EXT_BLOCKS = [
    # Bollinger Mean Reversion
    PatternBlock(
        id="BB_MEAN_REV",
        name="Bollinger Mean Reversion",
        category="mean_reversion_ext",
        formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
df['below_lower'] = df['close'] < df['bb_lower']
df['reversal'] = df['close'] > df['open']
df['cross_above'] = df['close'] > df['bb_lower']
df['entry_signal'] = df['below_lower'].shift(1) & df['reversal'] & df['cross_above']""",
        params={},
        direction="long",
        lookback=30,
        indicators=["BBANDS"],
        combinable_with=["volume", "momentum"],
        strategy_type="MRV",
    ),
    # RSI Mean Reversion
    PatternBlock(
        id="RSI_MEAN_REV",
        name="RSI Mean Reversion",
        category="mean_reversion_ext",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['oversold'] = df['rsi'] < {level}
df['turning'] = df['rsi'] > df['rsi'].shift(1)
df['cross_30'] = (df['rsi'] > 30) & (df['rsi'].shift(1) <= 30)
df['entry_signal'] = df['oversold'].shift(1) & df['turning'] & df['cross_30']""",
        params={"level": [25, 30]},
        direction="long",
        lookback=25,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MRV",
    ),
    # Z-Score Reversion
    PatternBlock(
        id="ZSCORE_REV",
        name="Z-Score Reversion",
        category="mean_reversion_ext",
        formula_template="""df['mean'] = df['close'].rolling({period}).mean()
df['std'] = df['close'].rolling({period}).std()
df['zscore'] = (df['close'] - df['mean']) / df['std']
df['extreme_low'] = df['zscore'] < -{threshold}
df['reversal'] = df['close'] > df['open']
df['entry_signal'] = df['extreme_low'] & df['reversal']""",
        params={"period": [20], "threshold": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "threshold"],
        strategy_type="MRV",
    ),
]


# =============================================================================
# TREND STRENGTH EXTENDED BLOCKS
# =============================================================================

TREND_STRENGTH_EXT_BLOCKS = [
    # ADX Strength
    PatternBlock(
        id="ADX_STRENGTH",
        name="ADX Strength",
        category="trend_strength_ext",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
df['strong_trend'] = df['adx'] > {threshold}
df['bullish'] = df['plus_di'] > ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
df['adx_rising'] = df['adx'] > df['adx'].shift(3)
df['entry_signal'] = df['strong_trend'] & df['bullish'] & df['adx_rising']""",
        params={"threshold": [25, 30]},
        direction="long",
        lookback=25,
        indicators=["ADX", "PLUS_DI", "MINUS_DI"],
        combinable_with=["momentum", "volume"],
        strategy_type="TSE",
    ),
    # Slope Strength
    PatternBlock(
        id="SLOPE_STRENGTH",
        name="Slope Strength",
        category="trend_strength_ext",
        formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
df['slope_norm'] = df['slope'] / df['close'] * 100
df['strong_slope'] = df['slope_norm'] > {threshold}
df['price_above'] = df['close'] > ta.EMA(df['close'], timeperiod=20)
df['entry_signal'] = df['strong_slope'] & df['price_above']""",
        params={"period": [14], "threshold": [0.3, 0.5]},
        direction="long",
        lookback=30,
        indicators=["LINEARREG_SLOPE", "EMA"],
        combinable_with=["volume", "confirmation"],
        strategy_type="TSE",
    ),
    # Momentum Strength
    PatternBlock(
        id="MOM_STRENGTH",
        name="Momentum Strength",
        category="trend_strength_ext",
        formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
df['roc_ma'] = df['roc'].rolling(10).mean()
df['strong_mom'] = df['roc'] > df['roc_ma'] * {mult}
df['positive'] = df['roc'] > 0
df['entry_signal'] = df['strong_mom'] & df['positive']""",
        params={"period": [10], "mult": [1.5, 2.0]},
        direction="long",
        lookback=25,
        indicators=["ROC"],
        combinable_with=["volume", "threshold"],
        strategy_type="TSE",
    ),
]


# =============================================================================
# CANDLE SEQUENCE BLOCKS
# =============================================================================

CANDLE_SEQUENCE_BLOCKS = [
    # Three White Soldiers
    PatternBlock(
        id="THREE_WHITE_SOLDIERS",
        name="Three White Soldiers",
        category="candle_sequence",
        formula_template="""df['bull1'] = df['close'].shift(2) > df['open'].shift(2)
df['bull2'] = df['close'].shift(1) > df['open'].shift(1)
df['bull3'] = df['close'] > df['open']
df['higher1'] = df['close'].shift(1) > df['close'].shift(2)
df['higher2'] = df['close'] > df['close'].shift(1)
df['body1'] = abs(df['close'].shift(2) - df['open'].shift(2)) > (df['high'].shift(2) - df['low'].shift(2)) * 0.5
df['body2'] = abs(df['close'].shift(1) - df['open'].shift(1)) > (df['high'].shift(1) - df['low'].shift(1)) * 0.5
df['body3'] = abs(df['close'] - df['open']) > (df['high'] - df['low']) * 0.5
df['soldiers'] = df['bull1'] & df['bull2'] & df['bull3'] & df['higher1'] & df['higher2'] & df['body1'] & df['body2'] & df['body3']
df['entry_signal'] = df['soldiers']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="CSQ",
    ),
    # Three Black Crows
    PatternBlock(
        id="THREE_BLACK_CROWS",
        name="Three Black Crows",
        category="candle_sequence",
        formula_template="""df['bear1'] = df['close'].shift(2) < df['open'].shift(2)
df['bear2'] = df['close'].shift(1) < df['open'].shift(1)
df['bear3'] = df['close'] < df['open']
df['lower1'] = df['close'].shift(1) < df['close'].shift(2)
df['lower2'] = df['close'] < df['close'].shift(1)
df['body1'] = abs(df['close'].shift(2) - df['open'].shift(2)) > (df['high'].shift(2) - df['low'].shift(2)) * 0.5
df['body2'] = abs(df['close'].shift(1) - df['open'].shift(1)) > (df['high'].shift(1) - df['low'].shift(1)) * 0.5
df['body3'] = abs(df['close'] - df['open']) > (df['high'] - df['low']) * 0.5
df['crows'] = df['bear1'] & df['bear2'] & df['bear3'] & df['lower1'] & df['lower2'] & df['body1'] & df['body2'] & df['body3']
df['entry_signal'] = df['crows']""",
        params={},
        direction="short",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="CSQ",
    ),
    # Morning Star
    PatternBlock(
        id="MORNING_STAR",
        name="Morning Star",
        category="candle_sequence",
        formula_template="""df['bear1'] = (df['close'].shift(2) < df['open'].shift(2)) & (abs(df['close'].shift(2) - df['open'].shift(2)) > (df['high'].shift(2) - df['low'].shift(2)) * 0.5)
df['small2'] = abs(df['close'].shift(1) - df['open'].shift(1)) < (df['high'].shift(1) - df['low'].shift(1)) * 0.3
df['bull3'] = (df['close'] > df['open']) & (abs(df['close'] - df['open']) > (df['high'] - df['low']) * 0.5)
df['gap_down'] = df['open'].shift(1) < df['close'].shift(2)
df['recovery'] = df['close'] > (df['open'].shift(2) + df['close'].shift(2)) / 2
df['morning_star'] = df['bear1'] & df['small2'] & df['bull3'] & df['recovery']
df['entry_signal'] = df['morning_star']""",
        params={},
        direction="long",
        lookback=10,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="CSQ",
    ),
]


# =============================================================================
# VOLATILITY FILTER BLOCKS
# =============================================================================

VOLATILITY_FILTER_BLOCKS = [
    # High Vol Filter
    PatternBlock(
        id="HIGH_VOL_FILTER",
        name="High Vol Filter",
        category="volatility_filter",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['atr_ma'] = df['atr'].rolling(20).mean()
df['high_vol'] = df['atr'] > df['atr_ma'] * {mult}
df['trend_up'] = df['close'] > ta.EMA(df['close'], timeperiod=20)
df['momentum'] = df['close'] > df['close'].shift(3)
df['entry_signal'] = df['high_vol'] & df['trend_up'] & df['momentum']""",
        params={"mult": [1.2, 1.5]},
        direction="long",
        lookback=35,
        indicators=["ATR", "EMA"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VFL",
    ),
    # Low Vol Filter
    PatternBlock(
        id="LOW_VOL_FILTER",
        name="Low Vol Filter",
        category="volatility_filter",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['atr_ma'] = df['atr'].rolling(20).mean()
df['low_vol'] = df['atr'] < df['atr_ma'] * {mult}
df['breakout'] = df['close'] > df['high'].shift(1).rolling(5).max()
df['vol_increase'] = df['atr'] > df['atr'].shift(1)
df['entry_signal'] = df['low_vol'].shift(1) & df['breakout'] & df['vol_increase']""",
        params={"mult": [0.7, 0.8]},
        direction="long",
        lookback=35,
        indicators=["ATR"],
        combinable_with=["volume", "momentum"],
        strategy_type="VFL",
    ),
    # Vol Regime Filter
    PatternBlock(
        id="VOL_REGIME_FILTER",
        name="Vol Regime Filter",
        category="volatility_filter",
        formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
df['atr_pct'] = df['atr'].rolling(50).apply(lambda x: (x.iloc[-1] > x).sum() / len(x) * 100, raw=False)
df['mid_vol'] = (df['atr_pct'] > 30) & (df['atr_pct'] < 70)
df['trend'] = df['close'] > ta.SMA(df['close'], timeperiod=20)
df['entry_signal'] = df['mid_vol'] & df['trend']""",
        params={},
        direction="long",
        lookback=60,
        indicators=["ATR", "SMA"],
        combinable_with=["momentum", "threshold"],
        strategy_type="VFL",
    ),
]


# =============================================================================
# PRICE PATTERN EXTENDED BLOCKS
# =============================================================================

PRICE_PATTERN_EXT_BLOCKS = [
    # Cup Handle
    PatternBlock(
        id="CUP_HANDLE",
        name="Cup Handle",
        category="price_pattern_ext",
        formula_template="""df['high_20'] = df['high'].rolling(20).max()
df['low_10'] = df['low'].rolling(10).min()
df['cup_depth'] = (df['high_20'] - df['low_10']) / df['high_20']
df['valid_cup'] = (df['cup_depth'] > 0.05) & (df['cup_depth'] < 0.30)
df['handle'] = df['close'] > df['high_20'] * 0.95
df['breakout'] = df['close'] > df['high_20']
df['entry_signal'] = df['valid_cup'].shift(5) & df['handle'].shift(1) & df['breakout']""",
        params={},
        direction="long",
        lookback=35,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="PPE",
    ),
    # Ascending Triangle
    PatternBlock(
        id="ASC_TRIANGLE",
        name="Ascending Triangle",
        category="price_pattern_ext",
        formula_template="""df['high_res'] = df['high'].rolling({period}).max()
df['stable_high'] = df['high_res'].diff().abs().rolling(5).mean() < df['close'] * 0.005
df['low_slope'] = df['low'].rolling({period}).apply(lambda x: (x.iloc[-1] - x.iloc[0]) / {period}, raw=False)
df['rising_lows'] = df['low_slope'] > 0
df['breakout'] = df['close'] > df['high_res'].shift(1)
df['entry_signal'] = df['stable_high'].shift(1) & df['rising_lows'].shift(1) & df['breakout']""",
        params={"period": [10]},
        direction="long",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="PPE",
    ),
    # Descending Triangle
    PatternBlock(
        id="DESC_TRIANGLE",
        name="Descending Triangle",
        category="price_pattern_ext",
        formula_template="""df['low_sup'] = df['low'].rolling({period}).min()
df['stable_low'] = df['low_sup'].diff().abs().rolling(5).mean() < df['close'] * 0.005
df['high_slope'] = df['high'].rolling({period}).apply(lambda x: (x.iloc[-1] - x.iloc[0]) / {period}, raw=False)
df['falling_highs'] = df['high_slope'] < 0
df['breakdown'] = df['close'] < df['low_sup'].shift(1)
df['entry_signal'] = df['stable_low'].shift(1) & df['falling_highs'].shift(1) & df['breakdown']""",
        params={"period": [10]},
        direction="short",
        lookback=20,
        indicators=[],
        combinable_with=["volume", "momentum"],
        strategy_type="PPE",
    ),
]


# =============================================================================
# MOMENTUM FILTER EXTENDED BLOCKS
# =============================================================================

MOMENTUM_FILTER_EXT_BLOCKS = [
    # RSI Filter
    PatternBlock(
        id="RSI_FILTER",
        name="RSI Filter",
        category="momentum_filter_ext",
        formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['rsi_mid'] = (df['rsi'] > {low}) & (df['rsi'] < {high})
df['rsi_rising'] = df['rsi'] > df['rsi'].shift(3)
df['price_up'] = df['close'] > df['close'].shift(3)
df['entry_signal'] = df['rsi_mid'] & df['rsi_rising'] & df['price_up']""",
        params={"low": [40, 45], "high": [60, 65]},
        direction="long",
        lookback=25,
        indicators=["RSI"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MFE",
    ),
    # MACD Filter
    PatternBlock(
        id="MACD_FILTER",
        name="MACD Filter",
        category="momentum_filter_ext",
        formula_template="""df['macd'], df['macd_signal'], df['macd_hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
df['macd_pos'] = df['macd_hist'] > 0
df['macd_rising'] = df['macd_hist'] > df['macd_hist'].shift(3)
df['price_trend'] = df['close'] > ta.EMA(df['close'], timeperiod=20)
df['entry_signal'] = df['macd_pos'] & df['macd_rising'] & df['price_trend']""",
        params={},
        direction="long",
        lookback=35,
        indicators=["MACD", "EMA"],
        combinable_with=["volume", "threshold"],
        strategy_type="MFE",
    ),
    # Stoch Filter
    PatternBlock(
        id="STOCH_FILTER",
        name="Stoch Filter",
        category="momentum_filter_ext",
        formula_template="""df['stoch_k'], df['stoch_d'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowd_period=3)
df['stoch_bull'] = df['stoch_k'] > df['stoch_d']
df['not_overbought'] = df['stoch_k'] < {level}
df['rising'] = df['stoch_k'] > df['stoch_k'].shift(3)
df['entry_signal'] = df['stoch_bull'] & df['not_overbought'] & df['rising']""",
        params={"level": [70, 80]},
        direction="long",
        lookback=25,
        indicators=["STOCH"],
        combinable_with=["volume", "confirmation"],
        strategy_type="MFE",
    ),
]


# =============================================================================
# VOLUME ANALYSIS EXTENDED BLOCKS
# =============================================================================

VOLUME_ANALYSIS_EXT_BLOCKS = [
    # Volume Trend
    PatternBlock(
        id="VOL_TREND",
        name="Volume Trend",
        category="volume_analysis_ext",
        formula_template="""df['vol_ma'] = df['volume'].rolling({period}).mean()
df['vol_trend'] = df['vol_ma'] > df['vol_ma'].shift(5)
df['price_trend'] = df['close'] > df['close'].shift(5)
df['aligned'] = df['vol_trend'] & df['price_trend']
df['entry_signal'] = df['aligned']""",
        params={"period": [10, 20]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "confirmation"],
        strategy_type="VAX",
    ),
    # Volume Breakout
    PatternBlock(
        id="VOL_BREAKOUT",
        name="Volume Breakout",
        category="volume_analysis_ext",
        formula_template="""df['vol_ma'] = df['volume'].rolling(20).mean()
df['vol_std'] = df['volume'].rolling(20).std()
df['vol_break'] = df['volume'] > df['vol_ma'] + df['vol_std'] * {mult}
df['price_break'] = df['close'] > df['high'].shift(1).rolling(5).max()
df['bullish'] = df['close'] > df['open']
df['entry_signal'] = df['vol_break'] & df['price_break'] & df['bullish']""",
        params={"mult": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["momentum", "threshold"],
        strategy_type="VAX",
    ),
    # Volume Reversal
    PatternBlock(
        id="VOL_REVERSAL",
        name="Volume Reversal",
        category="volume_analysis_ext",
        formula_template="""df['vol_spike'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
df['price_down'] = df['close'].shift(1) < df['close'].shift(5)
df['reversal'] = df['close'] > df['open']
df['reclaim'] = df['close'] > df['close'].shift(1)
df['entry_signal'] = df['vol_spike'] & df['price_down'] & df['reversal'] & df['reclaim']""",
        params={"mult": [2.0, 2.5]},
        direction="long",
        lookback=30,
        indicators=[],
        combinable_with=["volume", "confirmation"],
        strategy_type="VAX",
    ),
]


# =============================================================================
# CROSS INDICATOR BLOCKS
# =============================================================================

CROSS_INDICATOR_BLOCKS = [
    # MA + RSI Combo
    PatternBlock(
        id="MA_RSI_COMBO",
        name="MA RSI Combo",
        category="cross_indicator",
        formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
df['above_ma'] = df['close'] > df['ema']
df['rsi'] = ta.RSI(df['close'], timeperiod=14)
df['rsi_ok'] = (df['rsi'] > 40) & (df['rsi'] < 70)
df['ma_rising'] = df['ema'] > df['ema'].shift(5)
df['entry_signal'] = df['above_ma'] & df['rsi_ok'] & df['ma_rising']""",
        params={"period": [20, 50]},
        direction="long",
        lookback=60,
        indicators=["EMA", "RSI"],
        combinable_with=["volume", "momentum"],
        strategy_type="CRI",
    ),
    # BB + Volume Combo
    PatternBlock(
        id="BB_VOL_COMBO",
        name="BB Volume Combo",
        category="cross_indicator",
        formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
df['at_lower'] = df['low'] <= df['bb_lower']
df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
df['reversal'] = df['close'] > df['open']
df['entry_signal'] = df['at_lower'] & df['vol_surge'] & df['reversal']""",
        params={"mult": [1.5, 2.0]},
        direction="long",
        lookback=30,
        indicators=["BBANDS"],
        combinable_with=["momentum", "confirmation"],
        strategy_type="CRI",
    ),
    # ADX + DI Combo
    PatternBlock(
        id="ADX_DI_COMBO",
        name="ADX DI Combo",
        category="cross_indicator",
        formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
df['trending'] = df['adx'] > {adx_level}
df['bullish'] = df['plus_di'] > df['minus_di']
df['di_cross'] = (df['plus_di'] > df['minus_di']) & (df['plus_di'].shift(1) <= df['minus_di'].shift(1))
df['entry_signal'] = df['trending'] & df['di_cross']""",
        params={"adx_level": [20, 25]},
        direction="long",
        lookback=25,
        indicators=["ADX", "PLUS_DI", "MINUS_DI"],
        combinable_with=["volume", "threshold"],
        strategy_type="CRI",
    ),
]


# =============================================================================
# ALL BLOCKS COMBINED
# =============================================================================

ALL_BLOCKS = (
    THRESHOLD_BLOCKS
    + CROSSOVER_BLOCKS
    + VOLUME_BLOCKS
    + PRICE_ACTION_BLOCKS
    + STATISTICAL_BLOCKS
    + DIVERGENCE_BLOCKS
    + MORE_DIVERGENCE_BLOCKS
    + CONFIRMATION_BLOCKS
    + ADVANCED_PATTERN_BLOCKS
    + CANDLESTICK_BLOCKS
    + MOMENTUM_BLOCKS
    + CHANNEL_BLOCKS
    + MULTI_INDICATOR_BLOCKS
    + FILTERED_BLOCKS
    + VWAP_BLOCKS
    + ICHIMOKU_BLOCKS
    + ADX_DIRECTION_BLOCKS
    + SAR_BLOCKS
    + CONSECUTIVE_BLOCKS
    + RANGE_CONTRACTION_BLOCKS
    + GAP_FILL_BLOCKS
    + AROON_BLOCKS
    + CMF_BLOCKS
    + WAD_BLOCKS
    + TRIX_BLOCKS
    + ULTOSC_BLOCKS
    + ELDER_RAY_BLOCKS
    + TSI_BLOCKS
    + AO_BLOCKS
    + LINREG_BLOCKS
    + PIVOT_BLOCKS
    + PPO_BLOCKS
    + CMO_BLOCKS
    + DPO_BLOCKS
    + PRICE_EXTREMES_BLOCKS
    + VOLATILITY_RATIO_BLOCKS
    + ACCELERATION_BLOCKS
    + MA_RIBBON_BLOCKS
    + HEIKIN_ASHI_BLOCKS
    + FORCE_INDEX_BLOCKS
    + KLINGER_BLOCKS
    + EMV_BLOCKS
    + TEMA_DEMA_BLOCKS
    + COPPOCK_BLOCKS
    + KELTNER_BLOCKS
    + DONCHIAN_BLOCKS
    + WILLIAMS_R_BLOCKS
    + MFI_BLOCKS
    + KAMA_BLOCKS
    + NATR_BLOCKS
    + HILBERT_BLOCKS
    + CANDLE_PATTERN_BLOCKS
    + STOCH_RSI_BLOCKS
    + VWMA_BLOCKS
    + OBV_BLOCKS
    + ADOSC_BLOCKS
    + BOP_BLOCKS
    + PLUS_MINUS_DI_BLOCKS
    + PERCENT_RANK_BLOCKS
    + MEDIAN_PRICE_BLOCKS
    + TYPPRICE_BLOCKS
    + MOMENTUM_DIFF_BLOCKS
    + PRICE_OSC_BLOCKS
    + RANGE_PERCENT_BLOCKS
    + STDDEV_BLOCKS
    + ROC_MULTI_BLOCKS
    + BBANDS_WIDTH_BLOCKS
    + MACD_HIST_BLOCKS
    + RSI_SLOPE_BLOCKS
    + VOLUME_PRICE_BLOCKS
    + WCLPRICE_BLOCKS
    + AVGPRICE_BLOCKS
    + HIGH_LOW_DIFF_BLOCKS
    + CLOSE_POSITION_BLOCKS
    + SWING_POINTS_BLOCKS
    + MULTI_BAR_BLOCKS
    + PRICE_MA_DISTANCE_BLOCKS
    + ATR_BREAKOUT_BLOCKS
    + DUAL_MOMENTUM_BLOCKS
    + CANDLE_SIZE_BLOCKS
    + TREND_PERSISTENCE_BLOCKS
    + PRICE_VELOCITY_BLOCKS
    + VOLUME_TREND_BLOCKS
    + SUPPORT_RESISTANCE_BLOCKS
    + OPEN_CLOSE_REL_BLOCKS
    + BODY_WICK_RATIO_BLOCKS
    + HIGHER_LOWS_BLOCKS
    + CHANNEL_POSITION_BLOCKS
    + MOMENTUM_EXTREME_BLOCKS
    + VOLATILITY_REGIME_BLOCKS
    + TREND_QUALITY_BLOCKS
    + DOUBLE_PATTERN_BLOCKS
    + BREAKOUT_CONFIRM_BLOCKS
    + EMA_STACK_BLOCKS
    + INTRADAY_MOM_BLOCKS
    + PRICE_REJECTION_BLOCKS
    + CLIMAX_VOLUME_BLOCKS
    + RETRACEMENT_BLOCKS
    + EXPANSION_CYCLE_BLOCKS
    + PRICE_MEMORY_BLOCKS
    + MOMENTUM_SHIFT_BLOCKS
    + BARS_SINCE_BLOCKS
    + RELATIVE_POSITION_BLOCKS
    + THRUST_BLOCKS
    + PIVOT_EXT_BLOCKS
    + ATR_BANDS_BLOCKS
    + PRICE_CHANGE_RATE_BLOCKS
    + VOLUME_DISTRIBUTION_BLOCKS
    + TREND_EXHAUSTION_EXT_BLOCKS
    + REVERSAL_CANDLE_EXT_BLOCKS
    + MA_CONVERGENCE_BLOCKS
    + PRICE_RATIO_BLOCKS
    + STRUCTURE_BREAK_BLOCKS
    + IMPULSE_CORRECTION_BLOCKS
    + FRACTAL_BLOCKS
    + VOLUME_PROFILE_BLOCKS
    + ZIGZAG_BLOCKS
    + VORTEX_BLOCKS
    + MASS_INDEX_BLOCKS
    + CONNORS_RSI_BLOCKS
    + SQUEEZE_BLOCKS
    + PRICE_TRANSFORM_BLOCKS
    + ADAPTIVE_CHANNEL_BLOCKS
    + MOMENTUM_QUALITY_BLOCKS
    + PSAR_EXTENDED_BLOCKS
    + CUMULATIVE_DELTA_BLOCKS
    + EFFICIENCY_RATIO_BLOCKS
    + CHOPPINESS_BLOCKS
    + DETRENDED_PRICE_BLOCKS
    + TRUE_STRENGTH_INDEX_BLOCKS
    + ULTIMATE_OSC_EXT_BLOCKS
    + PRICE_ACTION_ZONES_BLOCKS
    + TWIN_RANGE_BLOCKS
    + IMPULSE_MACD_BLOCKS
    + WAVETREND_BLOCKS
    + QQE_BLOCKS
    + SCHAFF_TREND_BLOCKS
    + FISHER_TRANSFORM_BLOCKS
    + EHLERS_BLOCKS
    + CENTER_OF_GRAVITY_BLOCKS
    + RELATIVE_VIGOR_BLOCKS
    + RAINBOW_MA_BLOCKS
    + TREND_INTENSITY_BLOCKS
    + PRICE_ZONE_OSC_BLOCKS
    + SUPERTREND_BLOCKS
    + HURST_EXPONENT_BLOCKS
    + CHANDELIER_EXIT_BLOCKS
    + ELDER_IMPULSE_BLOCKS
    + DMI_ADX_EXT_BLOCKS
    + ALMA_BLOCKS
    + VIDYA_BLOCKS
    + MCGINLEY_BLOCKS
    + T3_MA_BLOCKS
    + JURIK_MA_BLOCKS
    + ZERO_LAG_MA_BLOCKS
    + HULL_MA_BLOCKS
    + LAGUERRE_BLOCKS
    + STOCHASTIC_EXT_BLOCKS
    + WILLIAMS_AD_BLOCKS
    + POSITIVE_VOLUME_BLOCKS
    + NEGATIVE_VOLUME_BLOCKS
    + INERTIA_BLOCKS
    + KNOW_SURE_THING_BLOCKS
    + SPECIAL_K_BLOCKS
    + PERCENTAGE_PRICE_OSC_BLOCKS
    + ABSOLUTE_PRICE_OSC_BLOCKS
    + DETRENDED_VOLUME_BLOCKS
    + RELATIVE_MOMENTUM_BLOCKS
    + STOCHASTIC_MOMENTUM_BLOCKS
    + PROJECTION_OSC_BLOCKS
    + PROJECTION_BANDS_BLOCKS
    + PRICE_MOMENTUM_OSC_BLOCKS
    + DECISION_POINT_BLOCKS
    + VOLUME_WEIGHTED_RSI_BLOCKS
    + EASE_OF_MOVEMENT_EXT_BLOCKS
    + ACCUMULATION_SWING_BLOCKS
    + DEMAND_INDEX_BLOCKS
    + HERRICK_PAYOFF_BLOCKS
    + TRADE_VOLUME_INDEX_BLOCKS
    + SWING_INDEX_BLOCKS
    + DYNAMIC_MOMENTUM_BLOCKS
    + MARKET_FACILITATION_BLOCKS
    + VOLATILITY_SYSTEM_BLOCKS
    + PRICE_CHANNEL_EXT_BLOCKS
    + BALANCE_OF_POWER_EXT_BLOCKS
    + CHAIKIN_VOLATILITY_BLOCKS
    + HISTORICAL_VOLATILITY_BLOCKS
    + STANDARD_ERROR_BLOCKS
    + REGRESSION_SLOPE_BLOCKS
    + PRICE_OSCILLATOR_EXT_BLOCKS
    + VOLUME_OSCILLATOR_BLOCKS
    + MOMENTUM_PERCENTILE_BLOCKS
    + TREND_SCORE_BLOCKS
    + ADAPTIVE_RSI_BLOCKS
    + RATE_OF_CHANGE_EXT_BLOCKS
    + VOLATILITY_BREAKOUT_BLOCKS
    + PRICE_DENSITY_BLOCKS
    + MOMENTUM_DIVERGENCE_EXT_BLOCKS
    + TREND_CONFIRMATION_BLOCKS
    + OSCILLATOR_EXTREME_BLOCKS
    + VOLUME_MOMENTUM_BLOCKS
    + CANDLE_MOMENTUM_BLOCKS
    + SUPPORT_BOUNCE_BLOCKS
    + BREAKOUT_STRENGTH_BLOCKS
    + RESISTANCE_REJECTION_BLOCKS
    + PULLBACK_ENTRY_BLOCKS
    + MOMENTUM_EXHAUSTION_EXT_BLOCKS
    + VOLUME_PROFILE_EXT_BLOCKS
    + TREND_CHANGE_BLOCKS
    + RANGE_BOUND_BLOCKS
    + MULTI_TIMEFRAME_PROXY_BLOCKS
    + PRICE_STRUCTURE_BLOCKS
    + VOLATILITY_REGIME_EXT_BLOCKS
    + SMART_MONEY_BLOCKS
    + GAP_ANALYSIS_BLOCKS
    + ORDERFLOW_PROXY_BLOCKS
    + LIQUIDITY_BLOCKS
    + CYCLE_DETECTION_BLOCKS
    + STRENGTH_WEAKNESS_BLOCKS
    + PATTERN_COMPLETION_BLOCKS
    + MONEY_FLOW_EXT_BLOCKS
    + TREND_FILTER_BLOCKS
    + ENTRY_TIMING_BLOCKS
    + EXIT_SIGNAL_BLOCKS
    + MARKET_REGIME_BLOCKS
    + PRICE_EFFICIENCY_BLOCKS
    + VOLUME_CLIMAX_EXT_BLOCKS
    + REVERSAL_CONFIRM_BLOCKS
    + CONTINUATION_PATTERN_BLOCKS
    + OSCILLATOR_CROSS_EXT_BLOCKS
    + MA_SYSTEM_EXT_BLOCKS
    + PRICE_LEVEL_BLOCKS
    + VOLATILITY_SQUEEZE_EXT_BLOCKS
    + SENTIMENT_PROXY_BLOCKS
    + DIVERGENCE_MULTI_BLOCKS
    + BREAKOUT_FILTER_BLOCKS
    + MEAN_REVERSION_EXT_BLOCKS
    + TREND_STRENGTH_EXT_BLOCKS
    + CANDLE_SEQUENCE_BLOCKS
    + VOLATILITY_FILTER_BLOCKS
    + PRICE_PATTERN_EXT_BLOCKS
    + MOMENTUM_FILTER_EXT_BLOCKS
    + VOLUME_ANALYSIS_EXT_BLOCKS
    + CROSS_INDICATOR_BLOCKS
)

# Index by ID for quick lookup
BLOCKS_BY_ID = {block.id: block for block in ALL_BLOCKS}

# Index by category
BLOCKS_BY_CATEGORY = {}
for block in ALL_BLOCKS:
    if block.category not in BLOCKS_BY_CATEGORY:
        BLOCKS_BY_CATEGORY[block.category] = []
    BLOCKS_BY_CATEGORY[block.category].append(block)


def get_block(block_id: str) -> PatternBlock:
    """Get a building block by ID."""
    if block_id not in BLOCKS_BY_ID:
        raise ValueError(f"Unknown block ID: {block_id}")
    return BLOCKS_BY_ID[block_id]


def get_blocks_by_category(category: str) -> List[PatternBlock]:
    """Get all blocks in a category."""
    return BLOCKS_BY_CATEGORY.get(category, [])


def get_compatible_blocks(block: PatternBlock) -> List[PatternBlock]:
    """Get blocks that can be combined with the given block."""
    compatible = []
    for cat in block.combinable_with:
        compatible.extend(get_blocks_by_category(cat))
    # Filter by compatible direction
    return [
        b for b in compatible
        if b.direction == "bidi" or b.direction == block.direction or block.direction == "bidi"
    ]


def get_all_block_ids() -> List[str]:
    """Get all block IDs."""
    return list(BLOCKS_BY_ID.keys())


def get_blocks_by_direction(direction: str) -> List[PatternBlock]:
    """Get blocks matching a direction (long, short, or bidi)."""
    if direction == "bidi":
        return ALL_BLOCKS
    return [b for b in ALL_BLOCKS if b.direction == direction or b.direction == "bidi"]
