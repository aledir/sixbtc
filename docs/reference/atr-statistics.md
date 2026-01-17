# Pattern-Discovery API - ATR Statistics

## Overview

Pattern-discovery provides **ATR statistics** for each pattern, calculated during walk-forward validation. These statistics describe the volatility conditions when the pattern historically fired signals.

## Fields in PatternResponse

```python
# From pattern-discovery API: GET /api/v1/patterns
{
    "name": "return_24h_gt_pos6",
    "tier": 1,
    "test_edge": 0.045,
    # ... existing fields ...

    # ATR statistics (price-normalized, e.g., 0.03 = 3% of price)
    "atr_signal_median": 0.0113,  # Median ATR when pattern signals fire
    "atr_signal_std": 0.0081,     # Std dev of ATR at signals
    "atr_signal_min": 0.0014,     # Min ATR observed at signals
    "atr_signal_max": 0.3884,     # Max ATR observed at signals
}
```

## What ATR Statistics Mean

- **atr_signal_median**: The typical volatility when this pattern fires. If a pattern has `atr_signal_median = 0.02` (2%), it means historically the pattern triggered when ATR was around 2% of price.

- **atr_signal_std**: How variable the volatility conditions are. High std = pattern fires in both calm and volatile markets. Low std = pattern is specific to certain volatility regimes.

- **atr_signal_min/max**: The range of volatility where the pattern has been observed to work.

## Usage - Volatility Quality Filter

Use ATR statistics to skip signals in abnormally low volatility (where edge may not exist):

```python
def generate_signal(self, df: pd.DataFrame) -> Signal | None:
    entry_condition = self._check_entry(df)

    if entry_condition:
        # Calculate current ATR (price-normalized)
        atr = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        atr_normalized = atr / df['close']
        current_atr = atr_normalized.iloc[-1]

        # Skip if current ATR < 50% of pattern's historical median
        atr_threshold = {atr_signal_median} * 0.5

        if current_atr < atr_threshold:
            return None  # Low volatility - skip signal

        return Signal(...)
```

## Why This Matters

1. **Empirical vs Arbitrary**: Instead of hardcoding `atr_threshold = 1.0`, use the pattern's actual historical volatility profile.

2. **Pattern-Specific**: A momentum pattern might need high volatility (`atr_signal_median = 0.03`), while a mean-reversion pattern might work in calmer markets (`atr_signal_median = 0.01`).

3. **Quality Filter**: If current market is much calmer than when the pattern was validated, the edge may not exist.

## Recommended Thresholds

| Scenario | Threshold | Use Case |
|----------|-----------|----------|
| Conservative | `atr_signal_median * 0.7` | Skip only extreme low volatility |
| Standard | `atr_signal_median * 0.5` | Skip when ATR is half the norm |
| Aggressive | `atr_signal_median * 0.3` | Only skip very dead markets |

## API Endpoint

```bash
# Get patterns with ATR statistics
curl "http://localhost:8001/api/v1/patterns?tier=1"

# Response includes atr_signal_* fields for all patterns
```

## ATR-Based Stop Loss for Close-Based Patterns

For `close_based` patterns (time-based exit), the SL is calculated using ATR instead of target magnitude:

```python
# In parametric_backtest.py build_execution_type_space():
if execution_type == 'close_based':
    if atr_signal_median and atr_signal_median > 0:
        # ATR-based SL: pattern fired at this volatility level
        # For close_based, the edge manifests at TIME EXIT (e.g., 24h)
        # SL must be wide enough to survive normal volatility until then
        # Typical 24h price swing: 3-5x daily ATR
        # Multipliers: 4x to 10x ATR for sufficient breathing room
        sl_multipliers = [4.0, 6.0, 8.0, 10.0]
        sl_values = [atr_signal_median * mult for mult in sl_multipliers]
    else:
        # Fallback: wider magnitude-based (less accurate)
        sl_values = [base_magnitude * mult for mult in [4.0, 6.0, 8.0, 10.0]]
```

**Why ATR-based SL?**
- Pattern-discovery validates close_based patterns with no SL (only time exit)
- Real trading needs SL for risk management
- SL must be wide enough to survive normal volatility until time exit
- Typical 24h price swing: 3-5x daily ATR, so multipliers 4-10x give breathing room

**Example:**
- Pattern `return_24h_gt_pos6`: magnitude=3%, atr_signal_median=1.13%
- SL (ATR×4-10): [4.5%, 6.8%, 9.0%, 11.3%]
- Wide enough to avoid premature stop-outs before time exit
