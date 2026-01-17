# Coding Examples and Patterns

Quick reference for common patterns in SixBTC.

---

## No Fallback, Fast Fail

```python
# WRONG - Masks configuration problems
timeout = config.get('timeout', 30)
api_key = os.getenv('API_KEY', 'default_key')

# CORRECT - Forces proper configuration
timeout = config['timeout']  # Crash if missing = good!
api_key = os.environ['API_KEY']  # Must be in environment
```

---

## No Hardcoding

```python
# FORBIDDEN
MAX_POSITIONS = 10
STOP_LOSS_PCT = 0.02

# REQUIRED
max_positions = config['risk']['max_open_positions']
stop_loss = config['risk']['fixed_risk_per_trade']
```

---

## Structural Fixes Only

```python
# PATCH - Masks the problem
try:
    result = unreliable_function()
except Exception:
    result = None  # Band-aid!

# STRUCTURAL - Fixes root cause
def reliable_function():
    # Redesigned logic that doesn't fail
    return properly_calculated_result()
```

---

## Dependency Injection

```python
# WRONG - Creates dependencies internally
class Executor:
    def __init__(self):
        self.client = HyperliquidClient()  # Hardcoded

# CORRECT - Injects dependencies
class Executor:
    def __init__(self, client: HyperliquidClient):
        self.client = client  # Testable, flexible
```

---

## StrategyCore Contract

```python
# All strategies must inherit from StrategyCore
class Strategy_MOM_a7f3d8b2(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        # Pure function - no state, no side effects
        pass
```

---

## No Lookahead Bias

```python
# FORBIDDEN - Uses future data
df['swing_high'] = df['high'].rolling(11, center=True).max()  # center=True!
future_price = df['close'].shift(-1)  # Negative shift!

# CORRECT - Only past data
df['swing_high'] = df['high'].rolling(10).max()  # Lookback only
current_price = df['close'].iloc[-1]  # Current bar
```

---

## Timeframe Agnostic

```python
# WRONG - Hardcoded timeframe
bars_24h = 96  # Assumes 15m timeframe

# CORRECT - Dynamic calculation
from src.features.timeframe import bars_in_period
bars_24h = bars_in_period('24h')  # Works with any TF
```

---

## WebSocket First

```python
# FORBIDDEN - REST for data that WebSocket provides
balance = client.get_account_balance()  # Wrong! Use webData2 subscription

# CORRECT - REST only for actions
client.place_order(order)  # OK - WebSocket doesn't support order placement
```

---

## AI Prompts with Jinja2

```python
# FORBIDDEN - Hardcoded prompts
prompt = f"Generate a strategy with RSI < {threshold}"

# REQUIRED - Use Jinja2 templates
from jinja2 import Environment
template = env.get_template('generate_strategy.j2')
prompt = template.render(threshold=threshold, patterns=patterns)
```

---

## Risk-Based Position Sizing

```python
# Risk-based position sizing
risk_amount = equity * risk_pct      # How much to risk in USD
notional = risk_amount / sl_pct      # Position size needed for that risk
margin_needed = notional / leverage  # Margin required

# Margin check (simulate exchange)
if margin_needed > (equity - margin_used):
    skip_trade()  # Insufficient margin

# Minimum notional check (Hyperliquid requirement)
if notional < min_notional:  # 10 USDC
    skip_trade()
```

---

## Logging (ASCII only)

```python
# WRONG
logger.info("📊 Strategia generata con successo!")  # Emoji + Italian

# CORRECT
logger.info("Strategy generated successfully")  # English + ASCII

# OK for Rich dashboards only
console.print("● RUNNING", style="green")  # Unicode OK in UI
```
