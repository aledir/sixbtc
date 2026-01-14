"""
128 Entry Conditions organized by category.

Each entry has: id, name, logic_template, direction, params, category, lookback_required, indicators_used.

Categories (Base - 68):
- breakout (12): Price breakout patterns
- crossover (14): MA/indicator crossovers
- threshold (16): Indicator threshold conditions
- volatility (8): Volatility-based entries
- candlestick (10): Candlestick patterns
- mean_reversion (8): Mean reversion setups

Categories (Advanced - 60, using pandas_ta):
- trend_advanced (20): Supertrend, PSAR, Ichimoku, Aroon, Vortex, HMA, ALMA
- momentum_advanced (24): TSI, Fisher, CMO, UO, Squeeze, StochRSI, RVGI, QQE, RSX
- volume_flow (16): CMF, EFI, KVO, PVO, NVI, PVI, AOBV, AD, ADOSC
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class EntryCondition:
    """Definition of an entry condition."""

    id: str                                    # e.g., "BRK_01"
    name: str                                  # e.g., "Breakout Previous High"
    category: str                              # e.g., "breakout", "crossover", "threshold"
    direction: Literal['LONG', 'SHORT', 'BIDI']
    logic_template: str                        # Python code with {params}
    params: dict = field(default_factory=dict)  # e.g., {"N": [5, 10, 20]}
    lookback_required: int = 20                # Minimum lookback needed
    indicators_used: list = field(default_factory=list)  # e.g., ["RSI", "MA"]


# =============================================================================
# BREAKOUT ENTRIES (12)
# =============================================================================

BREAKOUT_ENTRIES = [
    # BRK_01: Breakout Previous High (LONG)
    EntryCondition(
        id="BRK_01",
        name="Breakout Previous High",
        category="breakout",
        direction="LONG",
        logic_template='entry_condition = df["close"].iloc[-1] > df["high"].iloc[-2]',
        params={},
        lookback_required=5,
        indicators_used=[],
    ),
    # BRK_02: Breakout Previous Low (SHORT)
    EntryCondition(
        id="BRK_02",
        name="Breakout Previous Low",
        category="breakout",
        direction="SHORT",
        logic_template='entry_condition = df["close"].iloc[-1] < df["low"].iloc[-2]',
        params={},
        lookback_required=5,
        indicators_used=[],
    ),
    # BRK_03: Breakout N-Bar High (LONG)
    EntryCondition(
        id="BRK_03",
        name="Breakout N-Bar High",
        category="breakout",
        direction="LONG",
        logic_template='entry_condition = df["close"].iloc[-1] > df["high"].iloc[-{N}-1:-1].max()',
        params={"N": [5, 10, 20, 50]},
        lookback_required=55,
        indicators_used=[],
    ),
    # BRK_04: Breakout N-Bar Low (SHORT)
    EntryCondition(
        id="BRK_04",
        name="Breakout N-Bar Low",
        category="breakout",
        direction="SHORT",
        logic_template='entry_condition = df["close"].iloc[-1] < df["low"].iloc[-{N}-1:-1].min()',
        params={"N": [5, 10, 20, 50]},
        lookback_required=55,
        indicators_used=[],
    ),
    # BRK_05: Donchian Upper Breakout (LONG)
    EntryCondition(
        id="BRK_05",
        name="Donchian Upper Breakout",
        category="breakout",
        direction="LONG",
        logic_template='entry_condition = df["close"].iloc[-1] > df["high"].rolling({N}).max().iloc[-2]',
        params={"N": [20, 55]},
        lookback_required=60,
        indicators_used=[],
    ),
    # BRK_06: Donchian Lower Breakout (SHORT)
    EntryCondition(
        id="BRK_06",
        name="Donchian Lower Breakout",
        category="breakout",
        direction="SHORT",
        logic_template='entry_condition = df["close"].iloc[-1] < df["low"].rolling({N}).min().iloc[-2]',
        params={"N": [20, 55]},
        lookback_required=60,
        indicators_used=[],
    ),
    # BRK_07: ATR Breakout Up (LONG)
    EntryCondition(
        id="BRK_07",
        name="ATR Breakout Up",
        category="breakout",
        direction="LONG",
        logic_template='''atr = (df["high"] - df["low"]).rolling(14).mean()
entry_condition = df["close"].iloc[-1] > df["close"].iloc[-2] + atr.iloc[-1] * {M}''',
        params={"M": [1.0, 1.5, 2.0]},
        lookback_required=20,
        indicators_used=["ATR"],
    ),
    # BRK_08: ATR Breakout Down (SHORT)
    EntryCondition(
        id="BRK_08",
        name="ATR Breakout Down",
        category="breakout",
        direction="SHORT",
        logic_template='''atr = (df["high"] - df["low"]).rolling(14).mean()
entry_condition = df["close"].iloc[-1] < df["close"].iloc[-2] - atr.iloc[-1] * {M}''',
        params={"M": [1.0, 1.5, 2.0]},
        lookback_required=20,
        indicators_used=["ATR"],
    ),
    # BRK_09: Range Expansion Breakout Up (LONG)
    EntryCondition(
        id="BRK_09",
        name="Range Expansion Breakout Up",
        category="breakout",
        direction="LONG",
        logic_template='''curr_range = df["high"].iloc[-1] - df["low"].iloc[-1]
avg_range = (df["high"] - df["low"]).iloc[-{N}-1:-1].mean()
entry_condition = (curr_range > avg_range * 1.5) and (df["close"].iloc[-1] > df["open"].iloc[-1])''',
        params={"N": [5, 10, 20]},
        lookback_required=25,
        indicators_used=[],
    ),
    # BRK_10: Range Expansion Breakout Down (SHORT)
    EntryCondition(
        id="BRK_10",
        name="Range Expansion Breakout Down",
        category="breakout",
        direction="SHORT",
        logic_template='''curr_range = df["high"].iloc[-1] - df["low"].iloc[-1]
avg_range = (df["high"] - df["low"]).iloc[-{N}-1:-1].mean()
entry_condition = (curr_range > avg_range * 1.5) and (df["close"].iloc[-1] < df["open"].iloc[-1])''',
        params={"N": [5, 10, 20]},
        lookback_required=25,
        indicators_used=[],
    ),
    # BRK_11: Inside Bar Breakout Up (LONG)
    EntryCondition(
        id="BRK_11",
        name="Inside Bar Breakout Up",
        category="breakout",
        direction="LONG",
        logic_template='''inside_bar = (df["high"].iloc[-2] < df["high"].iloc[-3]) and (df["low"].iloc[-2] > df["low"].iloc[-3])
entry_condition = inside_bar and (df["close"].iloc[-1] > df["high"].iloc[-2])''',
        params={},
        lookback_required=10,
        indicators_used=[],
    ),
    # BRK_12: Inside Bar Breakout Down (SHORT)
    EntryCondition(
        id="BRK_12",
        name="Inside Bar Breakout Down",
        category="breakout",
        direction="SHORT",
        logic_template='''inside_bar = (df["high"].iloc[-2] < df["high"].iloc[-3]) and (df["low"].iloc[-2] > df["low"].iloc[-3])
entry_condition = inside_bar and (df["close"].iloc[-1] < df["low"].iloc[-2])''',
        params={},
        lookback_required=10,
        indicators_used=[],
    ),
]


# =============================================================================
# CROSSOVER ENTRIES (14)
# =============================================================================

CROSSOVER_ENTRIES = [
    # CRS_01: MA Fast Cross Up (LONG)
    EntryCondition(
        id="CRS_01",
        name="MA Fast Cross Up",
        category="crossover",
        direction="LONG",
        logic_template='''ma_fast = df["close"].rolling({fast}).mean()
ma_slow = df["close"].rolling({slow}).mean()
entry_condition = (ma_fast.iloc[-1] > ma_slow.iloc[-1]) and (ma_fast.iloc[-2] <= ma_slow.iloc[-2])''',
        params={"fast": [5, 10, 20], "slow": [20, 50, 100]},
        lookback_required=105,
        indicators_used=["MA"],
    ),
    # CRS_02: MA Fast Cross Down (SHORT)
    EntryCondition(
        id="CRS_02",
        name="MA Fast Cross Down",
        category="crossover",
        direction="SHORT",
        logic_template='''ma_fast = df["close"].rolling({fast}).mean()
ma_slow = df["close"].rolling({slow}).mean()
entry_condition = (ma_fast.iloc[-1] < ma_slow.iloc[-1]) and (ma_fast.iloc[-2] >= ma_slow.iloc[-2])''',
        params={"fast": [5, 10, 20], "slow": [20, 50, 100]},
        lookback_required=105,
        indicators_used=["MA"],
    ),
    # CRS_03: Price Cross MA Up (LONG)
    EntryCondition(
        id="CRS_03",
        name="Price Cross MA Up",
        category="crossover",
        direction="LONG",
        logic_template='''ma = df["close"].rolling({N}).mean()
entry_condition = (df["close"].iloc[-1] > ma.iloc[-1]) and (df["close"].iloc[-2] <= ma.iloc[-2])''',
        params={"N": [10, 20, 50]},
        lookback_required=55,
        indicators_used=["MA"],
    ),
    # CRS_04: Price Cross MA Down (SHORT)
    EntryCondition(
        id="CRS_04",
        name="Price Cross MA Down",
        category="crossover",
        direction="SHORT",
        logic_template='''ma = df["close"].rolling({N}).mean()
entry_condition = (df["close"].iloc[-1] < ma.iloc[-1]) and (df["close"].iloc[-2] >= ma.iloc[-2])''',
        params={"N": [10, 20, 50]},
        lookback_required=55,
        indicators_used=["MA"],
    ),
    # CRS_05: MACD Cross Signal Up (LONG)
    EntryCondition(
        id="CRS_05",
        name="MACD Cross Signal Up",
        category="crossover",
        direction="LONG",
        logic_template='''ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
macd = ema12 - ema26
signal = macd.ewm(span=9, adjust=False).mean()
entry_condition = (macd.iloc[-1] > signal.iloc[-1]) and (macd.iloc[-2] <= signal.iloc[-2])''',
        params={},
        lookback_required=35,
        indicators_used=["MACD"],
    ),
    # CRS_06: MACD Cross Signal Down (SHORT)
    EntryCondition(
        id="CRS_06",
        name="MACD Cross Signal Down",
        category="crossover",
        direction="SHORT",
        logic_template='''ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
macd = ema12 - ema26
signal = macd.ewm(span=9, adjust=False).mean()
entry_condition = (macd.iloc[-1] < signal.iloc[-1]) and (macd.iloc[-2] >= signal.iloc[-2])''',
        params={},
        lookback_required=35,
        indicators_used=["MACD"],
    ),
    # CRS_07: MACD Cross Zero Up (LONG)
    EntryCondition(
        id="CRS_07",
        name="MACD Cross Zero Up",
        category="crossover",
        direction="LONG",
        logic_template='''ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
macd = ema12 - ema26
entry_condition = (macd.iloc[-1] > 0) and (macd.iloc[-2] <= 0)''',
        params={},
        lookback_required=35,
        indicators_used=["MACD"],
    ),
    # CRS_08: MACD Cross Zero Down (SHORT)
    EntryCondition(
        id="CRS_08",
        name="MACD Cross Zero Down",
        category="crossover",
        direction="SHORT",
        logic_template='''ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
macd = ema12 - ema26
entry_condition = (macd.iloc[-1] < 0) and (macd.iloc[-2] >= 0)''',
        params={},
        lookback_required=35,
        indicators_used=["MACD"],
    ),
    # CRS_09: EMA Cross Up (LONG)
    EntryCondition(
        id="CRS_09",
        name="EMA Cross Up",
        category="crossover",
        direction="LONG",
        logic_template='''ema_fast = df["close"].ewm(span={fast}, adjust=False).mean()
ema_slow = df["close"].ewm(span={slow}, adjust=False).mean()
entry_condition = (ema_fast.iloc[-1] > ema_slow.iloc[-1]) and (ema_fast.iloc[-2] <= ema_slow.iloc[-2])''',
        params={"fast": [8, 12], "slow": [21, 26]},
        lookback_required=35,
        indicators_used=["EMA"],
    ),
    # CRS_10: EMA Cross Down (SHORT)
    EntryCondition(
        id="CRS_10",
        name="EMA Cross Down",
        category="crossover",
        direction="SHORT",
        logic_template='''ema_fast = df["close"].ewm(span={fast}, adjust=False).mean()
ema_slow = df["close"].ewm(span={slow}, adjust=False).mean()
entry_condition = (ema_fast.iloc[-1] < ema_slow.iloc[-1]) and (ema_fast.iloc[-2] >= ema_slow.iloc[-2])''',
        params={"fast": [8, 12], "slow": [21, 26]},
        lookback_required=35,
        indicators_used=["EMA"],
    ),
    # CRS_11: Stochastic Cross Up (LONG)
    EntryCondition(
        id="CRS_11",
        name="Stochastic Cross Up",
        category="crossover",
        direction="LONG",
        logic_template='''low_min = df["low"].rolling(14).min()
high_max = df["high"].rolling(14).max()
stoch_k = 100 * (df["close"] - low_min) / (high_max - low_min + 1e-10)
stoch_d = stoch_k.rolling(3).mean()
entry_condition = (stoch_k.iloc[-1] > stoch_d.iloc[-1]) and (stoch_k.iloc[-2] <= stoch_d.iloc[-2]) and (stoch_k.iloc[-1] < 30)''',
        params={},
        lookback_required=25,
        indicators_used=["STOCH"],
    ),
    # CRS_12: Stochastic Cross Down (SHORT)
    EntryCondition(
        id="CRS_12",
        name="Stochastic Cross Down",
        category="crossover",
        direction="SHORT",
        logic_template='''low_min = df["low"].rolling(14).min()
high_max = df["high"].rolling(14).max()
stoch_k = 100 * (df["close"] - low_min) / (high_max - low_min + 1e-10)
stoch_d = stoch_k.rolling(3).mean()
entry_condition = (stoch_k.iloc[-1] < stoch_d.iloc[-1]) and (stoch_k.iloc[-2] >= stoch_d.iloc[-2]) and (stoch_k.iloc[-1] > 70)''',
        params={},
        lookback_required=25,
        indicators_used=["STOCH"],
    ),
    # CRS_13: Price Cross VWAP Up (LONG)
    EntryCondition(
        id="CRS_13",
        name="Price Cross VWAP Up",
        category="crossover",
        direction="LONG",
        logic_template='''typical_price = (df["high"] + df["low"] + df["close"]) / 3
cum_vol = df["volume"].cumsum()
cum_tp_vol = (typical_price * df["volume"]).cumsum()
vwap = cum_tp_vol / cum_vol
entry_condition = (df["close"].iloc[-1] > vwap.iloc[-1]) and (df["close"].iloc[-2] <= vwap.iloc[-2])''',
        params={},
        lookback_required=20,
        indicators_used=["VWAP"],
    ),
    # CRS_14: Price Cross VWAP Down (SHORT)
    EntryCondition(
        id="CRS_14",
        name="Price Cross VWAP Down",
        category="crossover",
        direction="SHORT",
        logic_template='''typical_price = (df["high"] + df["low"] + df["close"]) / 3
cum_vol = df["volume"].cumsum()
cum_tp_vol = (typical_price * df["volume"]).cumsum()
vwap = cum_tp_vol / cum_vol
entry_condition = (df["close"].iloc[-1] < vwap.iloc[-1]) and (df["close"].iloc[-2] >= vwap.iloc[-2])''',
        params={},
        lookback_required=20,
        indicators_used=["VWAP"],
    ),
]


# =============================================================================
# THRESHOLD ENTRIES (16)
# =============================================================================

THRESHOLD_ENTRIES = [
    # THR_01: RSI Oversold (LONG)
    EntryCondition(
        id="THR_01",
        name="RSI Oversold",
        category="threshold",
        direction="LONG",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling({period}).mean()
loss = (-delta.clip(upper=0)).rolling({period}).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
entry_condition = rsi.iloc[-1] < {threshold}''',
        params={"threshold": [20, 25, 30], "period": [7, 14]},
        lookback_required=20,
        indicators_used=["RSI"],
    ),
    # THR_02: RSI Overbought (SHORT)
    EntryCondition(
        id="THR_02",
        name="RSI Overbought",
        category="threshold",
        direction="SHORT",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling({period}).mean()
loss = (-delta.clip(upper=0)).rolling({period}).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
entry_condition = rsi.iloc[-1] > {threshold}''',
        params={"threshold": [70, 75, 80], "period": [7, 14]},
        lookback_required=20,
        indicators_used=["RSI"],
    ),
    # THR_03: RSI Exit Oversold (LONG)
    EntryCondition(
        id="THR_03",
        name="RSI Exit Oversold",
        category="threshold",
        direction="LONG",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
entry_condition = (rsi.iloc[-1] > {threshold}) and (rsi.iloc[-2] <= {threshold})''',
        params={"threshold": [30, 35]},
        lookback_required=20,
        indicators_used=["RSI"],
    ),
    # THR_04: RSI Exit Overbought (SHORT)
    EntryCondition(
        id="THR_04",
        name="RSI Exit Overbought",
        category="threshold",
        direction="SHORT",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
entry_condition = (rsi.iloc[-1] < {threshold}) and (rsi.iloc[-2] >= {threshold})''',
        params={"threshold": [65, 70]},
        lookback_required=20,
        indicators_used=["RSI"],
    ),
    # THR_05: Stochastic Oversold (LONG)
    EntryCondition(
        id="THR_05",
        name="Stochastic Oversold",
        category="threshold",
        direction="LONG",
        logic_template='''low_min = df["low"].rolling(14).min()
high_max = df["high"].rolling(14).max()
stoch = 100 * (df["close"] - low_min) / (high_max - low_min + 1e-10)
entry_condition = stoch.iloc[-1] < {threshold}''',
        params={"threshold": [15, 20, 25]},
        lookback_required=20,
        indicators_used=["STOCH"],
    ),
    # THR_06: Stochastic Overbought (SHORT)
    EntryCondition(
        id="THR_06",
        name="Stochastic Overbought",
        category="threshold",
        direction="SHORT",
        logic_template='''low_min = df["low"].rolling(14).min()
high_max = df["high"].rolling(14).max()
stoch = 100 * (df["close"] - low_min) / (high_max - low_min + 1e-10)
entry_condition = stoch.iloc[-1] > {threshold}''',
        params={"threshold": [75, 80, 85]},
        lookback_required=20,
        indicators_used=["STOCH"],
    ),
    # THR_07: CCI Oversold (LONG)
    EntryCondition(
        id="THR_07",
        name="CCI Oversold",
        category="threshold",
        direction="LONG",
        logic_template='''tp = (df["high"] + df["low"] + df["close"]) / 3
sma_tp = tp.rolling(20).mean()
mad = tp.rolling(20).apply(lambda x: abs(x - x.mean()).mean())
cci = (tp - sma_tp) / (0.015 * mad + 1e-10)
entry_condition = cci.iloc[-1] < -{threshold}''',
        params={"threshold": [100, 150, 200]},
        lookback_required=25,
        indicators_used=["CCI"],
    ),
    # THR_08: CCI Overbought (SHORT)
    EntryCondition(
        id="THR_08",
        name="CCI Overbought",
        category="threshold",
        direction="SHORT",
        logic_template='''tp = (df["high"] + df["low"] + df["close"]) / 3
sma_tp = tp.rolling(20).mean()
mad = tp.rolling(20).apply(lambda x: abs(x - x.mean()).mean())
cci = (tp - sma_tp) / (0.015 * mad + 1e-10)
entry_condition = cci.iloc[-1] > {threshold}''',
        params={"threshold": [100, 150, 200]},
        lookback_required=25,
        indicators_used=["CCI"],
    ),
    # THR_09: ADX Strong Trend (BIDI)
    EntryCondition(
        id="THR_09",
        name="ADX Strong Trend",
        category="threshold",
        direction="BIDI",
        logic_template='''high_diff = df["high"].diff()
low_diff = -df["low"].diff()
plus_dm = ((high_diff > low_diff) & (high_diff > 0)) * high_diff
minus_dm = ((low_diff > high_diff) & (low_diff > 0)) * low_diff
tr = (df["high"] - df["low"]).rolling(14).mean()
plus_di = 100 * plus_dm.rolling(14).mean() / (tr + 1e-10)
minus_di = 100 * minus_dm.rolling(14).mean() / (tr + 1e-10)
dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
adx = dx.rolling(14).mean()
entry_condition = adx.iloc[-1] > {threshold}''',
        params={"threshold": [20, 25, 30]},
        lookback_required=35,
        indicators_used=["ADX"],
    ),
    # THR_10: Williams %R Oversold (LONG)
    EntryCondition(
        id="THR_10",
        name="Williams %R Oversold",
        category="threshold",
        direction="LONG",
        logic_template='''high_max = df["high"].rolling(14).max()
low_min = df["low"].rolling(14).min()
willr = -100 * (high_max - df["close"]) / (high_max - low_min + 1e-10)
entry_condition = willr.iloc[-1] < -{threshold}''',
        params={"threshold": [80, 85, 90]},
        lookback_required=20,
        indicators_used=["WILLR"],
    ),
    # THR_11: Williams %R Overbought (SHORT)
    EntryCondition(
        id="THR_11",
        name="Williams %R Overbought",
        category="threshold",
        direction="SHORT",
        logic_template='''high_max = df["high"].rolling(14).max()
low_min = df["low"].rolling(14).min()
willr = -100 * (high_max - df["close"]) / (high_max - low_min + 1e-10)
entry_condition = willr.iloc[-1] > -{threshold}''',
        params={"threshold": [10, 15, 20]},
        lookback_required=20,
        indicators_used=["WILLR"],
    ),
    # THR_12: MFI Oversold (LONG)
    EntryCondition(
        id="THR_12",
        name="MFI Oversold",
        category="threshold",
        direction="LONG",
        logic_template='''tp = (df["high"] + df["low"] + df["close"]) / 3
mf = tp * df["volume"]
pos_mf = ((tp > tp.shift(1)) * mf).rolling(14).sum()
neg_mf = ((tp < tp.shift(1)) * mf).rolling(14).sum()
mfi = 100 * pos_mf / (pos_mf + neg_mf + 1e-10)
entry_condition = mfi.iloc[-1] < {threshold}''',
        params={"threshold": [20, 25, 30]},
        lookback_required=20,
        indicators_used=["MFI"],
    ),
    # THR_13: MFI Overbought (SHORT)
    EntryCondition(
        id="THR_13",
        name="MFI Overbought",
        category="threshold",
        direction="SHORT",
        logic_template='''tp = (df["high"] + df["low"] + df["close"]) / 3
mf = tp * df["volume"]
pos_mf = ((tp > tp.shift(1)) * mf).rolling(14).sum()
neg_mf = ((tp < tp.shift(1)) * mf).rolling(14).sum()
mfi = 100 * pos_mf / (pos_mf + neg_mf + 1e-10)
entry_condition = mfi.iloc[-1] > {threshold}''',
        params={"threshold": [70, 75, 80]},
        lookback_required=20,
        indicators_used=["MFI"],
    ),
    # THR_14: ROC Positive (LONG)
    EntryCondition(
        id="THR_14",
        name="ROC Positive Momentum",
        category="threshold",
        direction="LONG",
        logic_template='''roc = 100 * (df["close"] - df["close"].shift({N})) / df["close"].shift({N})
entry_condition = roc.iloc[-1] > {threshold}''',
        params={"N": [10, 14, 20], "threshold": [0, 2, 5]},
        lookback_required=25,
        indicators_used=["ROC"],
    ),
    # THR_15: ROC Negative (SHORT)
    EntryCondition(
        id="THR_15",
        name="ROC Negative Momentum",
        category="threshold",
        direction="SHORT",
        logic_template='''roc = 100 * (df["close"] - df["close"].shift({N})) / df["close"].shift({N})
entry_condition = roc.iloc[-1] < -{threshold}''',
        params={"N": [10, 14, 20], "threshold": [0, 2, 5]},
        lookback_required=25,
        indicators_used=["ROC"],
    ),
    # THR_16: Momentum Threshold (LONG)
    EntryCondition(
        id="THR_16",
        name="Momentum Threshold",
        category="threshold",
        direction="LONG",
        logic_template='''mom = df["close"] - df["close"].shift({N})
entry_condition = mom.iloc[-1] > mom.rolling({N}).std().iloc[-1] * {mult}''',
        params={"N": [10, 20], "mult": [1.0, 1.5, 2.0]},
        lookback_required=25,
        indicators_used=["MOM"],
    ),
]


# =============================================================================
# VOLATILITY ENTRIES (8)
# =============================================================================

VOLATILITY_ENTRIES = [
    # VOL_01: BB Upper Touch Trend (LONG)
    EntryCondition(
        id="VOL_01",
        name="BB Upper Touch Trend",
        category="volatility",
        direction="LONG",
        logic_template='''sma = df["close"].rolling(20).mean()
std = df["close"].rolling(20).std()
bb_upper = sma + 2 * std
entry_condition = df["close"].iloc[-1] > bb_upper.iloc[-1]''',
        params={},
        lookback_required=25,
        indicators_used=["BB"],
    ),
    # VOL_02: BB Lower Touch Trend (SHORT)
    EntryCondition(
        id="VOL_02",
        name="BB Lower Touch Trend",
        category="volatility",
        direction="SHORT",
        logic_template='''sma = df["close"].rolling(20).mean()
std = df["close"].rolling(20).std()
bb_lower = sma - 2 * std
entry_condition = df["close"].iloc[-1] < bb_lower.iloc[-1]''',
        params={},
        lookback_required=25,
        indicators_used=["BB"],
    ),
    # VOL_03: BB Squeeze Release Up (LONG)
    EntryCondition(
        id="VOL_03",
        name="BB Squeeze Release Up",
        category="volatility",
        direction="LONG",
        logic_template='''sma = df["close"].rolling(20).mean()
std = df["close"].rolling(20).std()
bb_width = (4 * std) / sma
squeeze = bb_width < bb_width.rolling(50).quantile(0.2)
release = (squeeze.iloc[-2]) and (not squeeze.iloc[-1])
entry_condition = release and (df["close"].iloc[-1] > sma.iloc[-1])''',
        params={},
        lookback_required=55,
        indicators_used=["BB"],
    ),
    # VOL_04: BB Squeeze Release Down (SHORT)
    EntryCondition(
        id="VOL_04",
        name="BB Squeeze Release Down",
        category="volatility",
        direction="SHORT",
        logic_template='''sma = df["close"].rolling(20).mean()
std = df["close"].rolling(20).std()
bb_width = (4 * std) / sma
squeeze = bb_width < bb_width.rolling(50).quantile(0.2)
release = (squeeze.iloc[-2]) and (not squeeze.iloc[-1])
entry_condition = release and (df["close"].iloc[-1] < sma.iloc[-1])''',
        params={},
        lookback_required=55,
        indicators_used=["BB"],
    ),
    # VOL_05: Keltner Upper Break (LONG)
    EntryCondition(
        id="VOL_05",
        name="Keltner Upper Break",
        category="volatility",
        direction="LONG",
        logic_template='''ema = df["close"].ewm(span=20, adjust=False).mean()
atr = (df["high"] - df["low"]).rolling(14).mean()
keltner_upper = ema + atr * {mult}
entry_condition = df["close"].iloc[-1] > keltner_upper.iloc[-1]''',
        params={"mult": [1.5, 2.0, 2.5]},
        lookback_required=25,
        indicators_used=["KELT", "ATR"],
    ),
    # VOL_06: Keltner Lower Break (SHORT)
    EntryCondition(
        id="VOL_06",
        name="Keltner Lower Break",
        category="volatility",
        direction="SHORT",
        logic_template='''ema = df["close"].ewm(span=20, adjust=False).mean()
atr = (df["high"] - df["low"]).rolling(14).mean()
keltner_lower = ema - atr * {mult}
entry_condition = df["close"].iloc[-1] < keltner_lower.iloc[-1]''',
        params={"mult": [1.5, 2.0, 2.5]},
        lookback_required=25,
        indicators_used=["KELT", "ATR"],
    ),
    # VOL_07: ATR Expansion (BIDI)
    EntryCondition(
        id="VOL_07",
        name="ATR Expansion",
        category="volatility",
        direction="BIDI",
        logic_template='''atr = (df["high"] - df["low"]).rolling(14).mean()
atr_ma = atr.rolling(20).mean()
entry_condition = atr.iloc[-1] > atr_ma.iloc[-1] * {mult}''',
        params={"mult": [1.5, 2.0]},
        lookback_required=40,
        indicators_used=["ATR"],
    ),
    # VOL_08: Volatility Contraction Setup (BIDI)
    EntryCondition(
        id="VOL_08",
        name="Volatility Contraction",
        category="volatility",
        direction="BIDI",
        logic_template='''atr = (df["high"] - df["low"]).rolling(14).mean()
atr_ma = atr.rolling(20).mean()
entry_condition = atr.iloc[-1] < atr_ma.iloc[-1] * {mult}''',
        params={"mult": [0.5, 0.7]},
        lookback_required=40,
        indicators_used=["ATR"],
    ),
]


# =============================================================================
# CANDLESTICK ENTRIES (10)
# =============================================================================

CANDLESTICK_ENTRIES = [
    # CDL_01: Bullish Engulfing (LONG)
    EntryCondition(
        id="CDL_01",
        name="Bullish Engulfing",
        category="candlestick",
        direction="LONG",
        logic_template='''prev_bearish = df["close"].iloc[-2] < df["open"].iloc[-2]
curr_bullish = df["close"].iloc[-1] > df["open"].iloc[-1]
engulfs = (df["open"].iloc[-1] < df["close"].iloc[-2]) and (df["close"].iloc[-1] > df["open"].iloc[-2])
entry_condition = prev_bearish and curr_bullish and engulfs''',
        params={},
        lookback_required=10,
        indicators_used=[],
    ),
    # CDL_02: Bearish Engulfing (SHORT)
    EntryCondition(
        id="CDL_02",
        name="Bearish Engulfing",
        category="candlestick",
        direction="SHORT",
        logic_template='''prev_bullish = df["close"].iloc[-2] > df["open"].iloc[-2]
curr_bearish = df["close"].iloc[-1] < df["open"].iloc[-1]
engulfs = (df["open"].iloc[-1] > df["close"].iloc[-2]) and (df["close"].iloc[-1] < df["open"].iloc[-2])
entry_condition = prev_bullish and curr_bearish and engulfs''',
        params={},
        lookback_required=10,
        indicators_used=[],
    ),
    # CDL_03: Hammer (LONG)
    EntryCondition(
        id="CDL_03",
        name="Hammer",
        category="candlestick",
        direction="LONG",
        logic_template='''body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
lower_wick = min(df["close"].iloc[-1], df["open"].iloc[-1]) - df["low"].iloc[-1]
upper_wick = df["high"].iloc[-1] - max(df["close"].iloc[-1], df["open"].iloc[-1])
entry_condition = (lower_wick > body * 2) and (upper_wick < body * 0.3) and (body > 0)''',
        params={},
        lookback_required=5,
        indicators_used=[],
    ),
    # CDL_04: Shooting Star (SHORT)
    EntryCondition(
        id="CDL_04",
        name="Shooting Star",
        category="candlestick",
        direction="SHORT",
        logic_template='''body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
lower_wick = min(df["close"].iloc[-1], df["open"].iloc[-1]) - df["low"].iloc[-1]
upper_wick = df["high"].iloc[-1] - max(df["close"].iloc[-1], df["open"].iloc[-1])
entry_condition = (upper_wick > body * 2) and (lower_wick < body * 0.3) and (body > 0)''',
        params={},
        lookback_required=5,
        indicators_used=[],
    ),
    # CDL_05: Doji (BIDI)
    EntryCondition(
        id="CDL_05",
        name="Doji",
        category="candlestick",
        direction="BIDI",
        logic_template='''body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
range_ = df["high"].iloc[-1] - df["low"].iloc[-1]
entry_condition = (body < range_ * 0.1) and (range_ > 0)''',
        params={},
        lookback_required=5,
        indicators_used=[],
    ),
    # CDL_06: Three White Soldiers (LONG)
    EntryCondition(
        id="CDL_06",
        name="Three White Soldiers",
        category="candlestick",
        direction="LONG",
        logic_template='''c1_bull = df["close"].iloc[-3] > df["open"].iloc[-3]
c2_bull = df["close"].iloc[-2] > df["open"].iloc[-2]
c3_bull = df["close"].iloc[-1] > df["open"].iloc[-1]
c2_higher = df["close"].iloc[-2] > df["close"].iloc[-3]
c3_higher = df["close"].iloc[-1] > df["close"].iloc[-2]
entry_condition = c1_bull and c2_bull and c3_bull and c2_higher and c3_higher''',
        params={},
        lookback_required=10,
        indicators_used=[],
    ),
    # CDL_07: Three Black Crows (SHORT)
    EntryCondition(
        id="CDL_07",
        name="Three Black Crows",
        category="candlestick",
        direction="SHORT",
        logic_template='''c1_bear = df["close"].iloc[-3] < df["open"].iloc[-3]
c2_bear = df["close"].iloc[-2] < df["open"].iloc[-2]
c3_bear = df["close"].iloc[-1] < df["open"].iloc[-1]
c2_lower = df["close"].iloc[-2] < df["close"].iloc[-3]
c3_lower = df["close"].iloc[-1] < df["close"].iloc[-2]
entry_condition = c1_bear and c2_bear and c3_bear and c2_lower and c3_lower''',
        params={},
        lookback_required=10,
        indicators_used=[],
    ),
    # CDL_08: Morning Star (LONG)
    EntryCondition(
        id="CDL_08",
        name="Morning Star",
        category="candlestick",
        direction="LONG",
        logic_template='''c1_bear = df["close"].iloc[-3] < df["open"].iloc[-3]
c2_small = abs(df["close"].iloc[-2] - df["open"].iloc[-2]) < (df["high"].iloc[-2] - df["low"].iloc[-2]) * 0.3
c3_bull = df["close"].iloc[-1] > df["open"].iloc[-1]
c3_closes_above_mid = df["close"].iloc[-1] > (df["open"].iloc[-3] + df["close"].iloc[-3]) / 2
entry_condition = c1_bear and c2_small and c3_bull and c3_closes_above_mid''',
        params={},
        lookback_required=10,
        indicators_used=[],
    ),
    # CDL_09: Evening Star (SHORT)
    EntryCondition(
        id="CDL_09",
        name="Evening Star",
        category="candlestick",
        direction="SHORT",
        logic_template='''c1_bull = df["close"].iloc[-3] > df["open"].iloc[-3]
c2_small = abs(df["close"].iloc[-2] - df["open"].iloc[-2]) < (df["high"].iloc[-2] - df["low"].iloc[-2]) * 0.3
c3_bear = df["close"].iloc[-1] < df["open"].iloc[-1]
c3_closes_below_mid = df["close"].iloc[-1] < (df["open"].iloc[-3] + df["close"].iloc[-3]) / 2
entry_condition = c1_bull and c2_small and c3_bear and c3_closes_below_mid''',
        params={},
        lookback_required=10,
        indicators_used=[],
    ),
    # CDL_10: Pin Bar Up (LONG)
    EntryCondition(
        id="CDL_10",
        name="Pin Bar Up",
        category="candlestick",
        direction="LONG",
        logic_template='''body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
lower_wick = min(df["close"].iloc[-1], df["open"].iloc[-1]) - df["low"].iloc[-1]
upper_wick = df["high"].iloc[-1] - max(df["close"].iloc[-1], df["open"].iloc[-1])
range_ = df["high"].iloc[-1] - df["low"].iloc[-1]
body_at_top = max(df["close"].iloc[-1], df["open"].iloc[-1]) > df["low"].iloc[-1] + range_ * 0.7
entry_condition = (lower_wick > body * 2.5) and body_at_top and (range_ > 0)''',
        params={},
        lookback_required=5,
        indicators_used=[],
    ),
]


# =============================================================================
# MEAN REVERSION ENTRIES (8)
# =============================================================================

MEAN_REVERSION_ENTRIES = [
    # REV_01: Price Below MA (LONG)
    EntryCondition(
        id="REV_01",
        name="Price Below MA",
        category="mean_reversion",
        direction="LONG",
        logic_template='''ma = df["close"].rolling({N}).mean()
entry_condition = df["close"].iloc[-1] < ma.iloc[-1] * (1 - {pct}/100)''',
        params={"N": [20, 50], "pct": [2, 3, 5]},
        lookback_required=55,
        indicators_used=["MA"],
    ),
    # REV_02: Price Above MA (SHORT)
    EntryCondition(
        id="REV_02",
        name="Price Above MA",
        category="mean_reversion",
        direction="SHORT",
        logic_template='''ma = df["close"].rolling({N}).mean()
entry_condition = df["close"].iloc[-1] > ma.iloc[-1] * (1 + {pct}/100)''',
        params={"N": [20, 50], "pct": [2, 3, 5]},
        lookback_required=55,
        indicators_used=["MA"],
    ),
    # REV_03: Failed Breakdown (LONG)
    EntryCondition(
        id="REV_03",
        name="Failed Breakdown",
        category="mean_reversion",
        direction="LONG",
        logic_template='''broke_low = df["low"].iloc[-1] < df["low"].iloc[-2]
closed_higher = df["close"].iloc[-1] > df["close"].iloc[-2]
entry_condition = broke_low and closed_higher''',
        params={},
        lookback_required=10,
        indicators_used=[],
    ),
    # REV_04: Failed Breakout (SHORT)
    EntryCondition(
        id="REV_04",
        name="Failed Breakout",
        category="mean_reversion",
        direction="SHORT",
        logic_template='''broke_high = df["high"].iloc[-1] > df["high"].iloc[-2]
closed_lower = df["close"].iloc[-1] < df["close"].iloc[-2]
entry_condition = broke_high and closed_lower''',
        params={},
        lookback_required=10,
        indicators_used=[],
    ),
    # REV_05: Return to VWAP Long (LONG)
    EntryCondition(
        id="REV_05",
        name="Return to VWAP Long",
        category="mean_reversion",
        direction="LONG",
        logic_template='''typical_price = (df["high"] + df["low"] + df["close"]) / 3
cum_vol = df["volume"].cumsum()
cum_tp_vol = (typical_price * df["volume"]).cumsum()
vwap = cum_tp_vol / cum_vol
entry_condition = df["close"].iloc[-1] < vwap.iloc[-1] * 0.98''',
        params={},
        lookback_required=20,
        indicators_used=["VWAP"],
    ),
    # REV_06: Return to VWAP Short (SHORT)
    EntryCondition(
        id="REV_06",
        name="Return to VWAP Short",
        category="mean_reversion",
        direction="SHORT",
        logic_template='''typical_price = (df["high"] + df["low"] + df["close"]) / 3
cum_vol = df["volume"].cumsum()
cum_tp_vol = (typical_price * df["volume"]).cumsum()
vwap = cum_tp_vol / cum_vol
entry_condition = df["close"].iloc[-1] > vwap.iloc[-1] * 1.02''',
        params={},
        lookback_required=20,
        indicators_used=["VWAP"],
    ),
    # REV_07: Oversold Bounce (LONG)
    EntryCondition(
        id="REV_07",
        name="Oversold Bounce",
        category="mean_reversion",
        direction="LONG",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
entry_condition = (rsi.iloc[-1] < 30) and (rsi.iloc[-1] > rsi.iloc[-2])''',
        params={},
        lookback_required=20,
        indicators_used=["RSI"],
    ),
    # REV_08: Overbought Fade (SHORT)
    EntryCondition(
        id="REV_08",
        name="Overbought Fade",
        category="mean_reversion",
        direction="SHORT",
        logic_template='''delta = df["close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / (loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
entry_condition = (rsi.iloc[-1] > 70) and (rsi.iloc[-1] < rsi.iloc[-2])''',
        params={},
        lookback_required=20,
        indicators_used=["RSI"],
    ),
]


# =============================================================================
# TREND ADVANCED ENTRIES (20) - Using pandas_ta indicators
# =============================================================================

TREND_ADVANCED_ENTRIES = [
    # TRD_01: Supertrend Bullish (LONG)
    EntryCondition(
        id="TRD_01",
        name="Supertrend Bullish",
        category="trend_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
st = ta.supertrend(df["high"], df["low"], df["close"], length={length}, multiplier={mult})
st_dir = st[f"SUPERTd_{length}_{mult}"]
entry_condition = (st_dir.iloc[-1] == 1) and (st_dir.iloc[-2] == -1)''',
        params={"length": [7, 10, 14], "mult": [2.0, 3.0]},
        lookback_required=40,
        indicators_used=["SUPERTREND"],
    ),
    # TRD_02: Supertrend Bearish (SHORT)
    EntryCondition(
        id="TRD_02",
        name="Supertrend Bearish",
        category="trend_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
st = ta.supertrend(df["high"], df["low"], df["close"], length={length}, multiplier={mult})
st_dir = st[f"SUPERTd_{length}_{mult}"]
entry_condition = (st_dir.iloc[-1] == -1) and (st_dir.iloc[-2] == 1)''',
        params={"length": [7, 10, 14], "mult": [2.0, 3.0]},
        lookback_required=40,
        indicators_used=["SUPERTREND"],
    ),
    # TRD_03: PSAR Bullish Flip (LONG)
    EntryCondition(
        id="TRD_03",
        name="PSAR Bullish Flip",
        category="trend_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
psar = ta.psar(df["high"], df["low"])
psar_long = psar["PSARl_0.02_0.2"]
psar_short = psar["PSARs_0.02_0.2"]
entry_condition = pd.notna(psar_long.iloc[-1]) and pd.notna(psar_short.iloc[-2])''',
        params={},
        lookback_required=40,
        indicators_used=["PSAR"],
    ),
    # TRD_04: PSAR Bearish Flip (SHORT)
    EntryCondition(
        id="TRD_04",
        name="PSAR Bearish Flip",
        category="trend_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
psar = ta.psar(df["high"], df["low"])
psar_long = psar["PSARl_0.02_0.2"]
psar_short = psar["PSARs_0.02_0.2"]
entry_condition = pd.notna(psar_short.iloc[-1]) and pd.notna(psar_long.iloc[-2])''',
        params={},
        lookback_required=40,
        indicators_used=["PSAR"],
    ),
    # TRD_05: Ichimoku TK Cross Up (LONG)
    EntryCondition(
        id="TRD_05",
        name="Ichimoku TK Cross Up",
        category="trend_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
ichi = ta.ichimoku(df["high"], df["low"], df["close"])[0]
tenkan = ichi["ITS_9"]
kijun = ichi["IKS_26"]
entry_condition = (tenkan.iloc[-1] > kijun.iloc[-1]) and (tenkan.iloc[-2] <= kijun.iloc[-2])''',
        params={},
        lookback_required=65,
        indicators_used=["ICHIMOKU"],
    ),
    # TRD_06: Ichimoku TK Cross Down (SHORT)
    EntryCondition(
        id="TRD_06",
        name="Ichimoku TK Cross Down",
        category="trend_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
ichi = ta.ichimoku(df["high"], df["low"], df["close"])[0]
tenkan = ichi["ITS_9"]
kijun = ichi["IKS_26"]
entry_condition = (tenkan.iloc[-1] < kijun.iloc[-1]) and (tenkan.iloc[-2] >= kijun.iloc[-2])''',
        params={},
        lookback_required=65,
        indicators_used=["ICHIMOKU"],
    ),
    # TRD_07: Ichimoku Price Above Cloud (LONG)
    EntryCondition(
        id="TRD_07",
        name="Ichimoku Price Above Cloud",
        category="trend_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
ichi = ta.ichimoku(df["high"], df["low"], df["close"])[0]
span_a = ichi["ISA_9"]
span_b = ichi["ISB_26"]
cloud_top = span_a.combine(span_b, max)
entry_condition = (df["close"].iloc[-1] > cloud_top.iloc[-1]) and (df["close"].iloc[-2] <= cloud_top.iloc[-2])''',
        params={},
        lookback_required=65,
        indicators_used=["ICHIMOKU"],
    ),
    # TRD_08: Ichimoku Price Below Cloud (SHORT)
    EntryCondition(
        id="TRD_08",
        name="Ichimoku Price Below Cloud",
        category="trend_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
ichi = ta.ichimoku(df["high"], df["low"], df["close"])[0]
span_a = ichi["ISA_9"]
span_b = ichi["ISB_26"]
cloud_bottom = span_a.combine(span_b, min)
entry_condition = (df["close"].iloc[-1] < cloud_bottom.iloc[-1]) and (df["close"].iloc[-2] >= cloud_bottom.iloc[-2])''',
        params={},
        lookback_required=65,
        indicators_used=["ICHIMOKU"],
    ),
    # TRD_09: Aroon Bullish Cross (LONG)
    EntryCondition(
        id="TRD_09",
        name="Aroon Bullish Cross",
        category="trend_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
aroon = ta.aroon(df["high"], df["low"], length={length})
aroon_up = aroon[f"AROONU_{length}"]
aroon_down = aroon[f"AROOND_{length}"]
entry_condition = (aroon_up.iloc[-1] > aroon_down.iloc[-1]) and (aroon_up.iloc[-2] <= aroon_down.iloc[-2])''',
        params={"length": [14, 25]},
        lookback_required=40,
        indicators_used=["AROON"],
    ),
    # TRD_10: Aroon Bearish Cross (SHORT)
    EntryCondition(
        id="TRD_10",
        name="Aroon Bearish Cross",
        category="trend_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
aroon = ta.aroon(df["high"], df["low"], length={length})
aroon_up = aroon[f"AROONU_{length}"]
aroon_down = aroon[f"AROOND_{length}"]
entry_condition = (aroon_down.iloc[-1] > aroon_up.iloc[-1]) and (aroon_down.iloc[-2] <= aroon_up.iloc[-2])''',
        params={"length": [14, 25]},
        lookback_required=40,
        indicators_used=["AROON"],
    ),
    # TRD_11: Aroon Extreme Up (LONG)
    EntryCondition(
        id="TRD_11",
        name="Aroon Extreme Up",
        category="trend_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
aroon = ta.aroon(df["high"], df["low"], length={length})
aroon_up = aroon[f"AROONU_{length}"]
entry_condition = aroon_up.iloc[-1] >= {threshold}''',
        params={"length": [14, 25], "threshold": [90, 100]},
        lookback_required=40,
        indicators_used=["AROON"],
    ),
    # TRD_12: Aroon Extreme Down (SHORT)
    EntryCondition(
        id="TRD_12",
        name="Aroon Extreme Down",
        category="trend_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
aroon = ta.aroon(df["high"], df["low"], length={length})
aroon_down = aroon[f"AROOND_{length}"]
entry_condition = aroon_down.iloc[-1] >= {threshold}''',
        params={"length": [14, 25], "threshold": [90, 100]},
        lookback_required=40,
        indicators_used=["AROON"],
    ),
    # TRD_13: Vortex Bullish Cross (LONG)
    EntryCondition(
        id="TRD_13",
        name="Vortex Bullish Cross",
        category="trend_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
vortex = ta.vortex(df["high"], df["low"], df["close"], length={length})
vip = vortex[f"VTXP_{length}"]
vim = vortex[f"VTXM_{length}"]
entry_condition = (vip.iloc[-1] > vim.iloc[-1]) and (vip.iloc[-2] <= vim.iloc[-2])''',
        params={"length": [14, 21]},
        lookback_required=40,
        indicators_used=["VORTEX"],
    ),
    # TRD_14: Vortex Bearish Cross (SHORT)
    EntryCondition(
        id="TRD_14",
        name="Vortex Bearish Cross",
        category="trend_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
vortex = ta.vortex(df["high"], df["low"], df["close"], length={length})
vip = vortex[f"VTXP_{length}"]
vim = vortex[f"VTXM_{length}"]
entry_condition = (vim.iloc[-1] > vip.iloc[-1]) and (vim.iloc[-2] <= vip.iloc[-2])''',
        params={"length": [14, 21]},
        lookback_required=40,
        indicators_used=["VORTEX"],
    ),
    # TRD_15: Choppiness Low (Trending) (BIDI)
    EntryCondition(
        id="TRD_15",
        name="Choppiness Low",
        category="trend_advanced",
        direction="BIDI",
        logic_template='''import pandas_ta as ta
chop = ta.chop(df["high"], df["low"], df["close"], length={length})
entry_condition = chop.iloc[-1] < {threshold}''',
        params={"length": [14], "threshold": [38.2, 40]},
        lookback_required=40,
        indicators_used=["CHOP"],
    ),
    # TRD_16: Chandelier Exit Long (LONG)
    EntryCondition(
        id="TRD_16",
        name="Chandelier Exit Long Entry",
        category="trend_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
ce = ta.chandelier_exit(df["high"], df["low"], df["close"], length={length}, mult={mult})
ce_long = ce.iloc[:, 0]  # CHDLREXTl column (long)
entry_condition = (df["close"].iloc[-1] > ce_long.iloc[-1]) and (df["close"].iloc[-2] <= ce_long.iloc[-2])''',
        params={"length": [22], "mult": [3.0]},
        lookback_required=40,
        indicators_used=["CHANDELIER"],
    ),
    # TRD_17: Chandelier Exit Short (SHORT)
    EntryCondition(
        id="TRD_17",
        name="Chandelier Exit Short Entry",
        category="trend_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
ce = ta.chandelier_exit(df["high"], df["low"], df["close"], length={length}, mult={mult})
ce_short = ce.iloc[:, 1]  # CHDLREXTs column (short)
entry_condition = (df["close"].iloc[-1] < ce_short.iloc[-1]) and (df["close"].iloc[-2] >= ce_short.iloc[-2])''',
        params={"length": [22], "mult": [3.0]},
        lookback_required=40,
        indicators_used=["CHANDELIER"],
    ),
    # TRD_18: HMA Trend Up (LONG)
    EntryCondition(
        id="TRD_18",
        name="HMA Trend Up",
        category="trend_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
hma = ta.hma(df["close"], length={length})
entry_condition = (hma.iloc[-1] > hma.iloc[-2]) and (hma.iloc[-2] <= hma.iloc[-3])''',
        params={"length": [9, 14, 21]},
        lookback_required=40,
        indicators_used=["HMA"],
    ),
    # TRD_19: HMA Trend Down (SHORT)
    EntryCondition(
        id="TRD_19",
        name="HMA Trend Down",
        category="trend_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
hma = ta.hma(df["close"], length={length})
entry_condition = (hma.iloc[-1] < hma.iloc[-2]) and (hma.iloc[-2] >= hma.iloc[-3])''',
        params={"length": [9, 14, 21]},
        lookback_required=40,
        indicators_used=["HMA"],
    ),
    # TRD_20: ALMA Cross Up (LONG)
    EntryCondition(
        id="TRD_20",
        name="ALMA Cross Up",
        category="trend_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
alma = ta.alma(df["close"], length={length})
entry_condition = (df["close"].iloc[-1] > alma.iloc[-1]) and (df["close"].iloc[-2] <= alma.iloc[-2])''',
        params={"length": [9, 14, 21]},
        lookback_required=40,
        indicators_used=["ALMA"],
    ),
]


# =============================================================================
# MOMENTUM ADVANCED ENTRIES (24) - Using pandas_ta indicators
# =============================================================================

MOMENTUM_ADVANCED_ENTRIES = [
    # MOM_01: TSI Cross Zero Up (LONG)
    EntryCondition(
        id="MOM_01",
        name="TSI Cross Zero Up",
        category="momentum_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
tsi = ta.tsi(df["close"], fast={fast}, slow={slow})
tsi_val = tsi.iloc[:, 0]  # TSI value column
entry_condition = (tsi_val.iloc[-1] > 0) and (tsi_val.iloc[-2] <= 0)''',
        params={"fast": [13], "slow": [25]},
        lookback_required=50,
        indicators_used=["TSI"],
    ),
    # MOM_02: TSI Cross Zero Down (SHORT)
    EntryCondition(
        id="MOM_02",
        name="TSI Cross Zero Down",
        category="momentum_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
tsi = ta.tsi(df["close"], fast={fast}, slow={slow})
tsi_val = tsi.iloc[:, 0]  # TSI value column
entry_condition = (tsi_val.iloc[-1] < 0) and (tsi_val.iloc[-2] >= 0)''',
        params={"fast": [13], "slow": [25]},
        lookback_required=50,
        indicators_used=["TSI"],
    ),
    # MOM_03: TSI Cross Signal Up (LONG)
    EntryCondition(
        id="MOM_03",
        name="TSI Cross Signal Up",
        category="momentum_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
tsi = ta.tsi(df["close"], fast={fast}, slow={slow})
tsi_val = tsi.iloc[:, 0]  # TSI value column
tsi_sig = tsi.iloc[:, 1]  # TSI signal column
entry_condition = (tsi_val.iloc[-1] > tsi_sig.iloc[-1]) and (tsi_val.iloc[-2] <= tsi_sig.iloc[-2])''',
        params={"fast": [13], "slow": [25]},
        lookback_required=50,
        indicators_used=["TSI"],
    ),
    # MOM_04: TSI Cross Signal Down (SHORT)
    EntryCondition(
        id="MOM_04",
        name="TSI Cross Signal Down",
        category="momentum_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
tsi = ta.tsi(df["close"], fast={fast}, slow={slow})
tsi_val = tsi.iloc[:, 0]  # TSI value column
tsi_sig = tsi.iloc[:, 1]  # TSI signal column
entry_condition = (tsi_val.iloc[-1] < tsi_sig.iloc[-1]) and (tsi_val.iloc[-2] >= tsi_sig.iloc[-2])''',
        params={"fast": [13], "slow": [25]},
        lookback_required=50,
        indicators_used=["TSI"],
    ),
    # MOM_05: Fisher Transform Cross Up (LONG)
    EntryCondition(
        id="MOM_05",
        name="Fisher Transform Cross Up",
        category="momentum_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
fisher = ta.fisher(df["high"], df["low"], length={length})
fish = fisher[f"FISHERT_{length}_1"]
fish_sig = fisher[f"FISHERTs_{length}_1"]
entry_condition = (fish.iloc[-1] > fish_sig.iloc[-1]) and (fish.iloc[-2] <= fish_sig.iloc[-2])''',
        params={"length": [9, 14]},
        lookback_required=40,
        indicators_used=["FISHER"],
    ),
    # MOM_06: Fisher Transform Cross Down (SHORT)
    EntryCondition(
        id="MOM_06",
        name="Fisher Transform Cross Down",
        category="momentum_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
fisher = ta.fisher(df["high"], df["low"], length={length})
fish = fisher[f"FISHERT_{length}_1"]
fish_sig = fisher[f"FISHERTs_{length}_1"]
entry_condition = (fish.iloc[-1] < fish_sig.iloc[-1]) and (fish.iloc[-2] >= fish_sig.iloc[-2])''',
        params={"length": [9, 14]},
        lookback_required=40,
        indicators_used=["FISHER"],
    ),
    # MOM_07: CMO Oversold (LONG)
    EntryCondition(
        id="MOM_07",
        name="CMO Oversold",
        category="momentum_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
cmo = ta.cmo(df["close"], length={length})
entry_condition = cmo.iloc[-1] < -{threshold}''',
        params={"length": [14, 20], "threshold": [40, 50]},
        lookback_required=40,
        indicators_used=["CMO"],
    ),
    # MOM_08: CMO Overbought (SHORT)
    EntryCondition(
        id="MOM_08",
        name="CMO Overbought",
        category="momentum_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
cmo = ta.cmo(df["close"], length={length})
entry_condition = cmo.iloc[-1] > {threshold}''',
        params={"length": [14, 20], "threshold": [40, 50]},
        lookback_required=40,
        indicators_used=["CMO"],
    ),
    # MOM_09: Ultimate Oscillator Oversold (LONG)
    EntryCondition(
        id="MOM_09",
        name="Ultimate Oscillator Oversold",
        category="momentum_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
uo = ta.uo(df["high"], df["low"], df["close"])
entry_condition = uo.iloc[-1] < {threshold}''',
        params={"threshold": [30, 35]},
        lookback_required=40,
        indicators_used=["UO"],
    ),
    # MOM_10: Ultimate Oscillator Overbought (SHORT)
    EntryCondition(
        id="MOM_10",
        name="Ultimate Oscillator Overbought",
        category="momentum_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
uo = ta.uo(df["high"], df["low"], df["close"])
entry_condition = uo.iloc[-1] > {threshold}''',
        params={"threshold": [65, 70]},
        lookback_required=40,
        indicators_used=["UO"],
    ),
    # MOM_11: Squeeze Pro Fire Long (LONG)
    EntryCondition(
        id="MOM_11",
        name="Squeeze Pro Fire Long",
        category="momentum_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
sqz = ta.squeeze_pro(df["high"], df["low"], df["close"], bb_length=20, kc_length=20)
sqz_val = sqz.iloc[:, 0]  # SQZPRO momentum value column
in_squeeze = sqz_val.iloc[-2] != 0
firing_long = sqz_val.iloc[-1] > 0
entry_condition = in_squeeze and firing_long''',
        params={},
        lookback_required=35,
        indicators_used=["SQUEEZE"],
    ),
    # MOM_12: Squeeze Pro Fire Short (SHORT)
    EntryCondition(
        id="MOM_12",
        name="Squeeze Pro Fire Short",
        category="momentum_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
sqz = ta.squeeze_pro(df["high"], df["low"], df["close"], bb_length=20, kc_length=20)
sqz_val = sqz.iloc[:, 0]  # SQZPRO momentum value column
in_squeeze = sqz_val.iloc[-2] != 0
firing_short = sqz_val.iloc[-1] < 0
entry_condition = in_squeeze and firing_short''',
        params={},
        lookback_required=35,
        indicators_used=["SQUEEZE"],
    ),
    # MOM_13: Stochastic RSI Oversold (LONG)
    EntryCondition(
        id="MOM_13",
        name="Stochastic RSI Oversold",
        category="momentum_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
stochrsi = ta.stochrsi(df["close"], length={length}, rsi_length={length})
stochrsi_k = stochrsi[f"STOCHRSIk_{length}_{length}_3_3"]
entry_condition = stochrsi_k.iloc[-1] < {threshold}''',
        params={"length": [14], "threshold": [10, 20]},
        lookback_required=40,
        indicators_used=["STOCHRSI"],
    ),
    # MOM_14: Stochastic RSI Overbought (SHORT)
    EntryCondition(
        id="MOM_14",
        name="Stochastic RSI Overbought",
        category="momentum_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
stochrsi = ta.stochrsi(df["close"], length={length}, rsi_length={length})
stochrsi_k = stochrsi[f"STOCHRSIk_{length}_{length}_3_3"]
entry_condition = stochrsi_k.iloc[-1] > {threshold}''',
        params={"length": [14], "threshold": [80, 90]},
        lookback_required=40,
        indicators_used=["STOCHRSI"],
    ),
    # MOM_15: Stochastic RSI Cross Up (LONG)
    EntryCondition(
        id="MOM_15",
        name="Stochastic RSI Cross Up",
        category="momentum_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
stochrsi = ta.stochrsi(df["close"], length={length}, rsi_length={length})
stochrsi_k = stochrsi[f"STOCHRSIk_{length}_{length}_3_3"]
stochrsi_d = stochrsi[f"STOCHRSId_{length}_{length}_3_3"]
entry_condition = (stochrsi_k.iloc[-1] > stochrsi_d.iloc[-1]) and (stochrsi_k.iloc[-2] <= stochrsi_d.iloc[-2]) and (stochrsi_k.iloc[-1] < 50)''',
        params={"length": [14]},
        lookback_required=40,
        indicators_used=["STOCHRSI"],
    ),
    # MOM_16: Stochastic RSI Cross Down (SHORT)
    EntryCondition(
        id="MOM_16",
        name="Stochastic RSI Cross Down",
        category="momentum_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
stochrsi = ta.stochrsi(df["close"], length={length}, rsi_length={length})
stochrsi_k = stochrsi[f"STOCHRSIk_{length}_{length}_3_3"]
stochrsi_d = stochrsi[f"STOCHRSId_{length}_{length}_3_3"]
entry_condition = (stochrsi_k.iloc[-1] < stochrsi_d.iloc[-1]) and (stochrsi_k.iloc[-2] >= stochrsi_d.iloc[-2]) and (stochrsi_k.iloc[-1] > 50)''',
        params={"length": [14]},
        lookback_required=40,
        indicators_used=["STOCHRSI"],
    ),
    # MOM_17: RVGI Cross Up (LONG)
    EntryCondition(
        id="MOM_17",
        name="RVGI Cross Up",
        category="momentum_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
rvgi = ta.rvgi(df["open"], df["high"], df["low"], df["close"], length={length})
rvgi_val = rvgi[f"RVGI_{length}_4"]
rvgi_sig = rvgi[f"RVGIs_{length}_4"]
entry_condition = (rvgi_val.iloc[-1] > rvgi_sig.iloc[-1]) and (rvgi_val.iloc[-2] <= rvgi_sig.iloc[-2])''',
        params={"length": [10, 14]},
        lookback_required=50,
        indicators_used=["RVGI"],
    ),
    # MOM_18: RVGI Cross Down (SHORT)
    EntryCondition(
        id="MOM_18",
        name="RVGI Cross Down",
        category="momentum_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
rvgi = ta.rvgi(df["open"], df["high"], df["low"], df["close"], length={length})
rvgi_val = rvgi[f"RVGI_{length}_4"]
rvgi_sig = rvgi[f"RVGIs_{length}_4"]
entry_condition = (rvgi_val.iloc[-1] < rvgi_sig.iloc[-1]) and (rvgi_val.iloc[-2] >= rvgi_sig.iloc[-2])''',
        params={"length": [10, 14]},
        lookback_required=50,
        indicators_used=["RVGI"],
    ),
    # MOM_19: QQE Long Signal (LONG)
    EntryCondition(
        id="MOM_19",
        name="QQE Long Signal",
        category="momentum_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
qqe = ta.qqe(df["close"], length={length})
qqe_long = qqe.iloc[:, 2]  # QQEl column (long signal)
entry_condition = qqe_long.iloc[-1] == 1''',
        params={"length": [14]},
        lookback_required=85,
        indicators_used=["QQE"],
    ),
    # MOM_20: QQE Short Signal (SHORT)
    EntryCondition(
        id="MOM_20",
        name="QQE Short Signal",
        category="momentum_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
qqe = ta.qqe(df["close"], length={length})
qqe_short = qqe.iloc[:, 3]  # QQEs column (short signal)
entry_condition = qqe_short.iloc[-1] == 1''',
        params={"length": [14]},
        lookback_required=85,
        indicators_used=["QQE"],
    ),
    # MOM_21: Inertia Rising (LONG)
    EntryCondition(
        id="MOM_21",
        name="Inertia Rising",
        category="momentum_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
inertia = ta.inertia(df["close"], df["high"], df["low"], length={length})
entry_condition = (inertia.iloc[-1] > inertia.iloc[-2]) and (inertia.iloc[-2] <= inertia.iloc[-3]) and (inertia.iloc[-1] > 50)''',
        params={"length": [14, 20]},
        lookback_required=60,
        indicators_used=["INERTIA"],
    ),
    # MOM_22: Inertia Falling (SHORT)
    EntryCondition(
        id="MOM_22",
        name="Inertia Falling",
        category="momentum_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
inertia = ta.inertia(df["close"], df["high"], df["low"], length={length})
entry_condition = (inertia.iloc[-1] < inertia.iloc[-2]) and (inertia.iloc[-2] >= inertia.iloc[-3]) and (inertia.iloc[-1] < 50)''',
        params={"length": [14, 20]},
        lookback_required=60,
        indicators_used=["INERTIA"],
    ),
    # MOM_23: RSX Oversold (LONG)
    EntryCondition(
        id="MOM_23",
        name="RSX Oversold",
        category="momentum_advanced",
        direction="LONG",
        logic_template='''import pandas_ta as ta
rsx = ta.rsx(df["close"], length={length})
entry_condition = rsx.iloc[-1] < {threshold}''',
        params={"length": [14], "threshold": [20, 30]},
        lookback_required=40,
        indicators_used=["RSX"],
    ),
    # MOM_24: RSX Overbought (SHORT)
    EntryCondition(
        id="MOM_24",
        name="RSX Overbought",
        category="momentum_advanced",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
rsx = ta.rsx(df["close"], length={length})
entry_condition = rsx.iloc[-1] > {threshold}''',
        params={"length": [14], "threshold": [70, 80]},
        lookback_required=40,
        indicators_used=["RSX"],
    ),
]


# =============================================================================
# VOLUME FLOW ENTRIES (16) - Using pandas_ta indicators
# =============================================================================

VOLUME_FLOW_ENTRIES = [
    # VFL_01: CMF Positive Flow (LONG)
    EntryCondition(
        id="VFL_01",
        name="CMF Positive Flow",
        category="volume_flow",
        direction="LONG",
        logic_template='''import pandas_ta as ta
cmf = ta.cmf(df["high"], df["low"], df["close"], df["volume"], length={length})
entry_condition = (cmf.iloc[-1] > {threshold}) and (cmf.iloc[-2] <= {threshold})''',
        params={"length": [20, 21], "threshold": [0, 0.05]},
        lookback_required=40,
        indicators_used=["CMF"],
    ),
    # VFL_02: CMF Negative Flow (SHORT)
    EntryCondition(
        id="VFL_02",
        name="CMF Negative Flow",
        category="volume_flow",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
cmf = ta.cmf(df["high"], df["low"], df["close"], df["volume"], length={length})
entry_condition = (cmf.iloc[-1] < -{threshold}) and (cmf.iloc[-2] >= -{threshold})''',
        params={"length": [20, 21], "threshold": [0, 0.05]},
        lookback_required=40,
        indicators_used=["CMF"],
    ),
    # VFL_03: EFI Bullish (LONG)
    EntryCondition(
        id="VFL_03",
        name="EFI Bullish",
        category="volume_flow",
        direction="LONG",
        logic_template='''import pandas_ta as ta
efi = ta.efi(df["close"], df["volume"], length={length})
entry_condition = (efi.iloc[-1] > 0) and (efi.iloc[-2] <= 0)''',
        params={"length": [13]},
        lookback_required=40,
        indicators_used=["EFI"],
    ),
    # VFL_04: EFI Bearish (SHORT)
    EntryCondition(
        id="VFL_04",
        name="EFI Bearish",
        category="volume_flow",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
efi = ta.efi(df["close"], df["volume"], length={length})
entry_condition = (efi.iloc[-1] < 0) and (efi.iloc[-2] >= 0)''',
        params={"length": [13]},
        lookback_required=40,
        indicators_used=["EFI"],
    ),
    # VFL_05: KVO Bullish Cross (LONG)
    EntryCondition(
        id="VFL_05",
        name="KVO Bullish Cross",
        category="volume_flow",
        direction="LONG",
        logic_template='''import pandas_ta as ta
kvo = ta.kvo(df["high"], df["low"], df["close"], df["volume"])
kvo_val = kvo["KVO_34_55_13"]
kvo_sig = kvo["KVOs_34_55_13"]
entry_condition = (kvo_val.iloc[-1] > kvo_sig.iloc[-1]) and (kvo_val.iloc[-2] <= kvo_sig.iloc[-2])''',
        params={},
        lookback_required=80,
        indicators_used=["KVO"],
    ),
    # VFL_06: KVO Bearish Cross (SHORT)
    EntryCondition(
        id="VFL_06",
        name="KVO Bearish Cross",
        category="volume_flow",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
kvo = ta.kvo(df["high"], df["low"], df["close"], df["volume"])
kvo_val = kvo["KVO_34_55_13"]
kvo_sig = kvo["KVOs_34_55_13"]
entry_condition = (kvo_val.iloc[-1] < kvo_sig.iloc[-1]) and (kvo_val.iloc[-2] >= kvo_sig.iloc[-2])''',
        params={},
        lookback_required=80,
        indicators_used=["KVO"],
    ),
    # VFL_07: PVO Bullish (LONG)
    EntryCondition(
        id="VFL_07",
        name="PVO Bullish Cross",
        category="volume_flow",
        direction="LONG",
        logic_template='''import pandas_ta as ta
pvo = ta.pvo(df["volume"])
pvo_val = pvo["PVO_12_26_9"]
pvo_sig = pvo["PVOs_12_26_9"]
entry_condition = (pvo_val.iloc[-1] > pvo_sig.iloc[-1]) and (pvo_val.iloc[-2] <= pvo_sig.iloc[-2])''',
        params={},
        lookback_required=40,
        indicators_used=["PVO"],
    ),
    # VFL_08: PVO Bearish (SHORT)
    EntryCondition(
        id="VFL_08",
        name="PVO Bearish Cross",
        category="volume_flow",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
pvo = ta.pvo(df["volume"])
pvo_val = pvo["PVO_12_26_9"]
pvo_sig = pvo["PVOs_12_26_9"]
entry_condition = (pvo_val.iloc[-1] < pvo_sig.iloc[-1]) and (pvo_val.iloc[-2] >= pvo_sig.iloc[-2])''',
        params={},
        lookback_required=40,
        indicators_used=["PVO"],
    ),
    # VFL_09: NVI Rising (LONG)
    EntryCondition(
        id="VFL_09",
        name="NVI Signal Cross Up",
        category="volume_flow",
        direction="LONG",
        logic_template='''import pandas_ta as ta
nvi = ta.nvi(df["close"], df["volume"])
nvi_ma = nvi.rolling(255).mean()
entry_condition = (nvi.iloc[-1] > nvi_ma.iloc[-1]) and (nvi.iloc[-2] <= nvi_ma.iloc[-2])''',
        params={},
        lookback_required=260,
        indicators_used=["NVI"],
    ),
    # VFL_10: PVI Falling (SHORT)
    EntryCondition(
        id="VFL_10",
        name="PVI Signal Cross Down",
        category="volume_flow",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
pvi_df = ta.pvi(df["close"], df["volume"])
pvi = pvi_df.iloc[:, 0]  # PVI value column
pvi_ma = pvi.rolling(255).mean()
entry_condition = (pvi.iloc[-1] < pvi_ma.iloc[-1]) and (pvi.iloc[-2] >= pvi_ma.iloc[-2])''',
        params={},
        lookback_required=260,
        indicators_used=["PVI"],
    ),
    # VFL_11: AOBV Cross Up (LONG)
    EntryCondition(
        id="VFL_11",
        name="AOBV Cross Up",
        category="volume_flow",
        direction="LONG",
        logic_template='''import pandas_ta as ta
aobv = ta.aobv(df["close"], df["volume"])
obv = aobv["OBV"]
obv_min = aobv["OBV_min_2"]
obv_max = aobv["OBV_max_2"]
entry_condition = (obv.iloc[-1] > obv_max.iloc[-1]) and (obv.iloc[-2] <= obv_max.iloc[-2])''',
        params={},
        lookback_required=40,
        indicators_used=["AOBV"],
    ),
    # VFL_12: AOBV Cross Down (SHORT)
    EntryCondition(
        id="VFL_12",
        name="AOBV Cross Down",
        category="volume_flow",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
aobv = ta.aobv(df["close"], df["volume"])
obv = aobv["OBV"]
obv_min = aobv["OBV_min_2"]
entry_condition = (obv.iloc[-1] < obv_min.iloc[-1]) and (obv.iloc[-2] >= obv_min.iloc[-2])''',
        params={},
        lookback_required=40,
        indicators_used=["AOBV"],
    ),
    # VFL_13: AD Line Rising (LONG)
    EntryCondition(
        id="VFL_13",
        name="AD Line Rising",
        category="volume_flow",
        direction="LONG",
        logic_template='''import pandas_ta as ta
ad = ta.ad(df["high"], df["low"], df["close"], df["volume"])
ad_ma = ad.rolling({length}).mean()
entry_condition = (ad.iloc[-1] > ad_ma.iloc[-1]) and (ad.iloc[-2] <= ad_ma.iloc[-2])''',
        params={"length": [10, 20]},
        lookback_required=40,
        indicators_used=["AD"],
    ),
    # VFL_14: AD Line Falling (SHORT)
    EntryCondition(
        id="VFL_14",
        name="AD Line Falling",
        category="volume_flow",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
ad = ta.ad(df["high"], df["low"], df["close"], df["volume"])
ad_ma = ad.rolling({length}).mean()
entry_condition = (ad.iloc[-1] < ad_ma.iloc[-1]) and (ad.iloc[-2] >= ad_ma.iloc[-2])''',
        params={"length": [10, 20]},
        lookback_required=40,
        indicators_used=["AD"],
    ),
    # VFL_15: ADOSC Bullish (LONG)
    EntryCondition(
        id="VFL_15",
        name="ADOSC Bullish",
        category="volume_flow",
        direction="LONG",
        logic_template='''import pandas_ta as ta
adosc = ta.adosc(df["high"], df["low"], df["close"], df["volume"])
entry_condition = (adosc.iloc[-1] > 0) and (adosc.iloc[-2] <= 0)''',
        params={},
        lookback_required=40,
        indicators_used=["ADOSC"],
    ),
    # VFL_16: ADOSC Bearish (SHORT)
    EntryCondition(
        id="VFL_16",
        name="ADOSC Bearish",
        category="volume_flow",
        direction="SHORT",
        logic_template='''import pandas_ta as ta
adosc = ta.adosc(df["high"], df["low"], df["close"], df["volume"])
entry_condition = (adosc.iloc[-1] < 0) and (adosc.iloc[-2] >= 0)''',
        params={},
        lookback_required=40,
        indicators_used=["ADOSC"],
    ),
]


# =============================================================================
# MASTER LIST
# =============================================================================

ALL_ENTRIES: list[EntryCondition] = (
    BREAKOUT_ENTRIES +
    CROSSOVER_ENTRIES +
    THRESHOLD_ENTRIES +
    VOLATILITY_ENTRIES +
    CANDLESTICK_ENTRIES +
    MEAN_REVERSION_ENTRIES +
    TREND_ADVANCED_ENTRIES +
    MOMENTUM_ADVANCED_ENTRIES +
    VOLUME_FLOW_ENTRIES
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_entries_by_category(category: str) -> list[EntryCondition]:
    """Get all entries for a specific category."""
    return [e for e in ALL_ENTRIES if e.category == category]


def get_entries_by_direction(direction: str) -> list[EntryCondition]:
    """Get all entries compatible with a direction (LONG, SHORT, or BIDI)."""
    if direction == 'BIDI':
        return ALL_ENTRIES
    return [e for e in ALL_ENTRIES if e.direction == direction or e.direction == 'BIDI']


def get_entry_by_id(entry_id: str) -> EntryCondition | None:
    """Get a specific entry by ID."""
    for e in ALL_ENTRIES:
        if e.id == entry_id:
            return e
    return None


def get_category_counts() -> dict[str, int]:
    """Get count of entries per category."""
    from collections import Counter
    return dict(Counter(e.category for e in ALL_ENTRIES))
