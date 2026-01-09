#!/usr/bin/env python3
"""
Generate Prompt for Manual Strategy Creation

Outputs a complete prompt to give to Claude for creating a manual strategy.
The prompt includes:
- Strategy type legend
- Naming convention
- StrategyCore template
- All required elements (entry, exit, SL/TP, leverage)

Usage:
    python scripts/manual_strategy/generate_prompt.py

Then copy the output and add your strategy idea before giving it to Claude.
"""

PROMPT_TEMPLATE = '''
================================================================================
MANUAL STRATEGY CREATION PROMPT
================================================================================

You are creating a manual trading strategy for SixBTC. Follow these instructions
exactly.

--------------------------------------------------------------------------------
STRATEGY TYPE LEGEND
--------------------------------------------------------------------------------
Choose the appropriate type based on the strategy logic:

  MOM = Momentum
        - RSI oversold/overbought entries
        - Price momentum breakouts
        - Volume-confirmed moves

  REV = Mean Reversion
        - Bollinger Band bounces
        - Return to moving average
        - Oversold/overbought reversals

  TRN = Trend Following
        - EMA/SMA crossovers
        - ADX trend confirmation
        - Higher highs / lower lows

  BRE = Breakout
        - Support/resistance breaks
        - Range expansion
        - Volume breakouts

  SCA = Scalping
        - Short timeframes (1m-15m)
        - Quick entries/exits
        - Small profit targets

  VOL = Volatility
        - ATR-based entries
        - Volatility expansion/contraction
        - Squeeze breakouts

--------------------------------------------------------------------------------
NAMING CONVENTION
--------------------------------------------------------------------------------
File name format:
    ManStrat_<TYPE>_<8char_hash>.py

Examples:
    ManStrat_MOM_a1b2c3d4.py
    ManStrat_REV_e5f6g7h8.py
    ManStrat_TRN_12345678.py

The hash should be 8 random hex characters (0-9, a-f).
The class name inside the file MUST match the file name (without .py).

--------------------------------------------------------------------------------
REQUIRED ELEMENTS
--------------------------------------------------------------------------------
Every strategy must define:

1. ENTRY CONDITIONS
   - Clear long entry conditions
   - Clear short entry conditions (optional, can be long-only)
   - Minimum data requirements (warmup period)

2. EXIT CONDITIONS (via Signal)
   - Stop Loss: REQUIRED (use StopLossType)
   - Take Profit: REQUIRED (use TakeProfitType)

3. LEVERAGE
   - Set as class attribute: leverage = N (1-10 recommended)

4. TIMEFRAME
   - Strategy should work on: 15m, 30m, 1h, 2h
   - Use bars_in_period() for timeframe-agnostic calculations

--------------------------------------------------------------------------------
STRATEGY TEMPLATE
--------------------------------------------------------------------------------
Save the file in: strategies/manual/ManStrat_<TYPE>_<hash>.py

```python
"""
Manual Strategy: <Brief Description>

Type: <MOM|REV|TRN|BRE|SCA|VOL>
Timeframe: <target timeframe, e.g., 15m, 1h>
Author: Manual
Created: <date>

Entry Logic:
    LONG: <describe conditions>
    SHORT: <describe conditions>

Exit Logic:
    SL: <describe stop loss method>
    TP: <describe take profit method>
"""

import pandas as pd
import numpy as np
import talib as ta
from src.strategies.base import (
    StrategyCore,
    Signal,
    StopLossType,
    TakeProfitType
)


class ManStrat_<TYPE>_<hash>(StrategyCore):
    """
    <Strategy description>
    """

    # Target leverage (capped at coin's max_leverage)
    leverage = 5

    # Indicator columns for lookahead detection
    indicator_columns = ['rsi', 'atr', 'ema_fast', 'ema_slow']

    def __init__(self, params: dict = None):
        """Initialize with parameters"""
        super().__init__(params)

        # Strategy parameters (customize these)
        self.rsi_period = self.params.get('rsi_period', 14)
        self.atr_period = self.params.get('atr_period', 14)
        # Add more parameters as needed

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate ALL indicators on the dataframe.
        Called ONCE before signal generation.

        IMPORTANT:
        - Always return df.copy()
        - Use only lookback operations (no center=True, no shift(-N))
        """
        df = df.copy()

        # Calculate indicators
        df['rsi'] = ta.RSI(df['close'], timeperiod=self.rsi_period)
        df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=self.atr_period)

        # Add more indicators as needed
        # df['ema_fast'] = ta.EMA(df['close'], timeperiod=12)
        # df['ema_slow'] = ta.EMA(df['close'], timeperiod=26)

        return df

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str = None
    ) -> Signal | None:
        """
        Generate trading signal from pre-calculated indicators.

        IMPORTANT:
        - Only read values using iloc[-1] or iloc[-2]
        - Do NOT recalculate indicators here
        - Return None if conditions not met
        """
        # Minimum data requirement
        min_bars = max(self.rsi_period, self.atr_period) + 10
        if len(df) < min_bars:
            return None

        # Read pre-calculated indicator values
        current_rsi = df['rsi'].iloc[-1]
        current_atr = df['atr'].iloc[-1]
        current_close = df['close'].iloc[-1]

        # Check for NaN values
        if pd.isna(current_rsi) or pd.isna(current_atr):
            return None

        # =====================================================================
        # LONG ENTRY CONDITIONS
        # =====================================================================
        long_condition = (
            current_rsi < 30  # Example: RSI oversold
            # Add more conditions
        )

        if long_condition:
            return Signal(
                direction='long',
                leverage=self.leverage,
                sl_type=StopLossType.ATR,
                atr_stop_multiplier=2.0,
                tp_type=TakeProfitType.ATR,
                atr_take_multiplier=3.0,
                reason=f"Long entry: RSI={current_rsi:.1f}"
            )

        # =====================================================================
        # SHORT ENTRY CONDITIONS (optional)
        # =====================================================================
        short_condition = (
            current_rsi > 70  # Example: RSI overbought
            # Add more conditions
        )

        if short_condition:
            return Signal(
                direction='short',
                leverage=self.leverage,
                sl_type=StopLossType.ATR,
                atr_stop_multiplier=2.0,
                tp_type=TakeProfitType.ATR,
                atr_take_multiplier=3.0,
                reason=f"Short entry: RSI={current_rsi:.1f}"
            )

        return None
```

--------------------------------------------------------------------------------
STOP LOSS TYPES (choose one)
--------------------------------------------------------------------------------
StopLossType.ATR          - Dynamic SL based on ATR (recommended)
                            Use: atr_stop_multiplier=2.0

StopLossType.PERCENTAGE   - Fixed percentage from entry
                            Use: sl_pct=0.02 (2%)

StopLossType.STRUCTURE    - Based on swing high/low
                            Use: sl_price=48500.0

StopLossType.VOLATILITY   - Based on standard deviation
                            Use: sl_std_multiplier=2.0

StopLossType.TRAILING     - Trailing stop
                            Use: trailing_stop_pct=0.03

--------------------------------------------------------------------------------
TAKE PROFIT TYPES (choose one)
--------------------------------------------------------------------------------
TakeProfitType.ATR        - Dynamic TP based on ATR (recommended)
                            Use: atr_take_multiplier=3.0

TakeProfitType.RR_RATIO   - Based on Risk/Reward ratio
                            Use: rr_ratio=2.0 (2:1)

TakeProfitType.PERCENTAGE - Fixed percentage from entry
                            Use: tp_pct=0.05 (5%)

TakeProfitType.TRAILING   - Trailing take profit
                            Use: trailing_tp_pct=0.02

--------------------------------------------------------------------------------
AVAILABLE INDICATORS (talib)
--------------------------------------------------------------------------------
Momentum:     RSI, STOCH, STOCHRSI, WILLR, CCI, MOM, ROC
Trend:        EMA, SMA, DEMA, TEMA, WMA, ADX, PLUS_DI, MINUS_DI, AROON
Volatility:   ATR, NATR, TRANGE, BBANDS
Volume:       OBV, AD, ADOSC, MFI
Pattern:      CDLENGULFING, CDLHAMMER, CDLDOJI, etc.

--------------------------------------------------------------------------------
YOUR STRATEGY IDEA
--------------------------------------------------------------------------------
<< ADD YOUR STRATEGY DESCRIPTION HERE >>

Example:
"Create a strategy on 15m timeframe that:
- Goes LONG when price breaks above yesterday's high with RSI > 50
- Goes SHORT when price breaks below yesterday's low with RSI < 50
- Uses 2x ATR stop loss and 3x ATR take profit
- Leverage 5x"

================================================================================
'''


def main():
    """Print the prompt template"""
    print(PROMPT_TEMPLATE)


if __name__ == '__main__':
    main()
