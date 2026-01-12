"""
Unger Patterns Library - 60 Price Action Patterns

Based on Andrea Unger's 4x World Trading Champion methodology.
Original 43 patterns from EasyLanguage + 17 additional patterns.

All patterns are vectorized boolean conditions that can be applied to OHLCV DataFrames.
Each pattern returns a boolean Series where True = pattern is active on that bar.

Usage:
    from src.generator.regime.unger_patterns import UngerPatterns

    # Check single pattern
    mask = UngerPatterns.pattern_01_small_bar(df)

    # Get pattern by number
    mask = UngerPatterns.get_pattern(1, df)

    # Get all patterns for a DataFrame
    results = UngerPatterns.evaluate_all(df)
"""

import pandas as pd
import numpy as np
from typing import Callable


class UngerPatterns:
    """
    60 Unger Price Action Patterns.

    Pattern Categories:
    - 01-03: Volatility/Indecision patterns
    - 04-07: Directional/Range expansion patterns
    - 08-09: Consecutive closes patterns
    - 10-11: Higher/Lower structure patterns
    - 12-13: Range expansion/contraction patterns
    - 14-31: Close position and gap analysis patterns
    - 32-40: Inside/outside day and gap patterns
    - 41-43: Crypto 7-day extension patterns
    - 44-49: (Reserved)
    - 50-54: Candlestick reversal patterns
    - 55-57: Volume patterns
    - 58-60: Range patterns (NR4, NR7, Wide Range)
    - 61-66: Structure and reversal patterns
    """

    # =========================================================================
    # ORIGINAL 43 UNGER PATTERNS (from EasyLanguage)
    # =========================================================================

    @staticmethod
    def pattern_01_small_bar(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 01: Small bar (low volatility)
        Bar range < 50% of previous bar range.
        Indicates indecision/consolidation.
        """
        curr_range = df['high'] - df['low']
        prev_range = curr_range.shift(1)
        return curr_range < (prev_range * 0.5)

    @staticmethod
    def pattern_02_small_body(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 02: Small body
        Body (abs(close-open)) < 30% of bar range.
        Indicates indecision - similar to doji.
        """
        body = (df['close'] - df['open']).abs()
        bar_range = df['high'] - df['low']
        # Avoid division by zero
        return body < (bar_range * 0.3)

    @staticmethod
    def pattern_03_narrow_range(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 03: Narrow range bar
        Range < 75% of 5-bar average range.
        Compression before expansion.
        """
        curr_range = df['high'] - df['low']
        avg_range = curr_range.rolling(5).mean().shift(1)
        return curr_range < (avg_range * 0.75)

    @staticmethod
    def pattern_04_range_expansion_up(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 04: Range expansion with bullish close
        Range > 150% of previous + close in upper 30%.
        Strong directional move up.
        """
        curr_range = df['high'] - df['low']
        prev_range = curr_range.shift(1)
        close_position = (df['close'] - df['low']) / curr_range.replace(0, np.nan)
        return (curr_range > prev_range * 1.5) & (close_position > 0.7)

    @staticmethod
    def pattern_05_range_expansion_down(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 05: Range expansion with bearish close
        Range > 150% of previous + close in lower 30%.
        Strong directional move down.
        """
        curr_range = df['high'] - df['low']
        prev_range = curr_range.shift(1)
        close_position = (df['close'] - df['low']) / curr_range.replace(0, np.nan)
        return (curr_range > prev_range * 1.5) & (close_position < 0.3)

    @staticmethod
    def pattern_06_wide_range_bar(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 06: Wide range bar
        Range > 200% of 10-bar average.
        Momentum/breakout bar.
        """
        curr_range = df['high'] - df['low']
        avg_range = curr_range.rolling(10).mean().shift(1)
        return curr_range > (avg_range * 2.0)

    @staticmethod
    def pattern_07_breakout_bar(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 07: Breakout bar
        Close above 5-bar high OR below 5-bar low.
        New local extreme.
        """
        high_5 = df['high'].rolling(5).max().shift(1)
        low_5 = df['low'].rolling(5).min().shift(1)
        return (df['close'] > high_5) | (df['close'] < low_5)

    @staticmethod
    def pattern_08_three_up_closes(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 08: Three consecutive higher closes
        Close > Close[1] > Close[2] > Close[3].
        Bullish momentum.
        """
        c0 = df['close']
        c1 = df['close'].shift(1)
        c2 = df['close'].shift(2)
        c3 = df['close'].shift(3)
        return (c0 > c1) & (c1 > c2) & (c2 > c3)

    @staticmethod
    def pattern_09_three_down_closes(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 09: Three consecutive lower closes
        Close < Close[1] < Close[2] < Close[3].
        Bearish momentum.
        """
        c0 = df['close']
        c1 = df['close'].shift(1)
        c2 = df['close'].shift(2)
        c3 = df['close'].shift(3)
        return (c0 < c1) & (c1 < c2) & (c2 < c3)

    @staticmethod
    def pattern_10_higher_high_higher_low(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 10: Higher high AND higher low
        Bullish structure - uptrend bar.
        """
        return (df['high'] > df['high'].shift(1)) & (df['low'] > df['low'].shift(1))

    @staticmethod
    def pattern_11_lower_high_lower_low(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 11: Lower high AND lower low
        Bearish structure - downtrend bar.
        """
        return (df['high'] < df['high'].shift(1)) & (df['low'] < df['low'].shift(1))

    @staticmethod
    def pattern_12_range_contraction_2bars(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 12: 2-bar range contraction
        Current range < Previous range < Range[2].
        Tightening consolidation.
        """
        r0 = df['high'] - df['low']
        r1 = r0.shift(1)
        r2 = r0.shift(2)
        return (r0 < r1) & (r1 < r2)

    @staticmethod
    def pattern_13_range_expansion_2bars(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 13: 2-bar range expansion
        Current range > Previous range > Range[2].
        Expanding volatility.
        """
        r0 = df['high'] - df['low']
        r1 = r0.shift(1)
        r2 = r0.shift(2)
        return (r0 > r1) & (r1 > r2)

    @staticmethod
    def pattern_14_close_above_open(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 14: Close above open (bullish bar)
        Simple bullish candle.
        """
        return df['close'] > df['open']

    @staticmethod
    def pattern_15_close_below_open(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 15: Close below open (bearish bar)
        Simple bearish candle.
        """
        return df['close'] < df['open']

    @staticmethod
    def pattern_16_close_upper_quartile(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 16: Close in upper 25% of range
        Strong buying pressure.
        """
        bar_range = df['high'] - df['low']
        close_pos = (df['close'] - df['low']) / bar_range.replace(0, np.nan)
        return close_pos > 0.75

    @staticmethod
    def pattern_17_close_lower_quartile(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 17: Close in lower 25% of range
        Strong selling pressure.
        """
        bar_range = df['high'] - df['low']
        close_pos = (df['close'] - df['low']) / bar_range.replace(0, np.nan)
        return close_pos < 0.25

    @staticmethod
    def pattern_18_gap_up(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 18: Gap up
        Open > Previous high.
        Bullish gap.
        """
        return df['open'] > df['high'].shift(1)

    @staticmethod
    def pattern_19_gap_down(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 19: Gap down
        Open < Previous low.
        Bearish gap.
        """
        return df['open'] < df['low'].shift(1)

    @staticmethod
    def pattern_20_gap_filled_up(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 20: Gap up but filled (weak gap)
        Opened above prev high but traded back to fill.
        """
        gap_up = df['open'] > df['high'].shift(1)
        filled = df['low'] <= df['high'].shift(1)
        return gap_up & filled

    @staticmethod
    def pattern_21_gap_filled_down(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 21: Gap down but filled (weak gap)
        Opened below prev low but traded back to fill.
        """
        gap_down = df['open'] < df['low'].shift(1)
        filled = df['high'] >= df['low'].shift(1)
        return gap_down & filled

    @staticmethod
    def pattern_22_close_above_prev_high(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 22: Close above previous high
        Bullish breakout close.
        """
        return df['close'] > df['high'].shift(1)

    @staticmethod
    def pattern_23_close_below_prev_low(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 23: Close below previous low
        Bearish breakdown close.
        """
        return df['close'] < df['low'].shift(1)

    @staticmethod
    def pattern_24_close_in_prev_range(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 24: Close within previous bar's range
        No breakout - consolidation.
        """
        return (df['close'] <= df['high'].shift(1)) & (df['close'] >= df['low'].shift(1))

    @staticmethod
    def pattern_25_open_in_prev_range(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 25: Open within previous bar's range
        Normal open - no gap.
        """
        return (df['open'] <= df['high'].shift(1)) & (df['open'] >= df['low'].shift(1))

    @staticmethod
    def pattern_26_body_gt_avg(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 26: Body greater than 5-bar average body
        Strong conviction move.
        """
        body = (df['close'] - df['open']).abs()
        avg_body = body.rolling(5).mean().shift(1)
        return body > avg_body

    @staticmethod
    def pattern_27_body_lt_avg(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 27: Body less than 5-bar average body
        Weak conviction - indecision.
        """
        body = (df['close'] - df['open']).abs()
        avg_body = body.rolling(5).mean().shift(1)
        return body < avg_body

    @staticmethod
    def pattern_28_high_above_prev_2(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 28: High above previous 2 bars' highs
        Local breakout to upside.
        """
        return (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(2))

    @staticmethod
    def pattern_29_low_below_prev_2(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 29: Low below previous 2 bars' lows
        Local breakdown to downside.
        """
        return (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(2))

    @staticmethod
    def pattern_30_close_near_high(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 30: Close within 10% of high
        Strong close - buyers in control.
        """
        bar_range = df['high'] - df['low']
        distance_from_high = df['high'] - df['close']
        return distance_from_high < (bar_range * 0.1)

    @staticmethod
    def pattern_31_close_near_low(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 31: Close within 10% of low
        Weak close - sellers in control.
        """
        bar_range = df['high'] - df['low']
        distance_from_low = df['close'] - df['low']
        return distance_from_low < (bar_range * 0.1)

    @staticmethod
    def pattern_32_inside_bar(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 32: Inside bar
        High < Previous high AND Low > Previous low.
        Consolidation - breakout setup.
        """
        return (df['high'] < df['high'].shift(1)) & (df['low'] > df['low'].shift(1))

    @staticmethod
    def pattern_33_outside_bar(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 33: Outside bar (engulfing range)
        High > Previous high AND Low < Previous low.
        Reversal or continuation signal.
        """
        return (df['high'] > df['high'].shift(1)) & (df['low'] < df['low'].shift(1))

    @staticmethod
    def pattern_34_two_inside_bars(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 34: Two consecutive inside bars
        Strong compression - bigger breakout expected.
        """
        inside_1 = (df['high'] < df['high'].shift(1)) & (df['low'] > df['low'].shift(1))
        inside_2 = (df['high'].shift(1) < df['high'].shift(2)) & (df['low'].shift(1) > df['low'].shift(2))
        return inside_1 & inside_2

    @staticmethod
    def pattern_35_gap_and_go_up(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 35: Gap up and continue (no fill)
        Strong bullish momentum - gap acts as support.
        """
        gap_up = df['open'] > df['high'].shift(1)
        no_fill = df['low'] > df['high'].shift(1)
        return gap_up & no_fill

    @staticmethod
    def pattern_36_gap_and_go_down(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 36: Gap down and continue (no fill)
        Strong bearish momentum - gap acts as resistance.
        """
        gap_down = df['open'] < df['low'].shift(1)
        no_fill = df['high'] < df['low'].shift(1)
        return gap_down & no_fill

    @staticmethod
    def pattern_37_reversal_bar_up(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 37: Bullish reversal bar
        Lower low than previous BUT closes above previous close.
        """
        lower_low = df['low'] < df['low'].shift(1)
        higher_close = df['close'] > df['close'].shift(1)
        return lower_low & higher_close

    @staticmethod
    def pattern_38_reversal_bar_down(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 38: Bearish reversal bar
        Higher high than previous BUT closes below previous close.
        """
        higher_high = df['high'] > df['high'].shift(1)
        lower_close = df['close'] < df['close'].shift(1)
        return higher_high & lower_close

    @staticmethod
    def pattern_39_thrust_up(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 39: Bullish thrust
        Open in lower 30% of range, Close in upper 30%.
        Strong intrabar reversal up.
        """
        bar_range = df['high'] - df['low']
        open_pos = (df['open'] - df['low']) / bar_range.replace(0, np.nan)
        close_pos = (df['close'] - df['low']) / bar_range.replace(0, np.nan)
        return (open_pos < 0.3) & (close_pos > 0.7)

    @staticmethod
    def pattern_40_thrust_down(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 40: Bearish thrust
        Open in upper 30% of range, Close in lower 30%.
        Strong intrabar reversal down.
        """
        bar_range = df['high'] - df['low']
        open_pos = (df['open'] - df['low']) / bar_range.replace(0, np.nan)
        close_pos = (df['close'] - df['low']) / bar_range.replace(0, np.nan)
        return (open_pos > 0.7) & (close_pos < 0.3)

    @staticmethod
    def pattern_41_seven_day_high(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 41: 7-day high (crypto adaptation)
        Close is highest close in 7 bars.
        Bullish momentum breakout.
        """
        return df['close'] >= df['close'].rolling(7).max()

    @staticmethod
    def pattern_42_seven_day_low(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 42: 7-day low (crypto adaptation)
        Close is lowest close in 7 bars.
        Bearish momentum breakdown.
        """
        return df['close'] <= df['close'].rolling(7).min()

    @staticmethod
    def pattern_43_seven_day_range_breakout(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 43: 7-day range breakout (crypto adaptation)
        Close above 7-bar high OR below 7-bar low.
        Range expansion after consolidation.
        """
        high_7 = df['high'].rolling(7).max().shift(1)
        low_7 = df['low'].rolling(7).min().shift(1)
        return (df['close'] > high_7) | (df['close'] < low_7)

    # =========================================================================
    # PATTERNS 44-49: RESERVED FOR FUTURE
    # =========================================================================

    # =========================================================================
    # PATTERNS 50-54: CANDLESTICK REVERSAL PATTERNS
    # =========================================================================

    @staticmethod
    def pattern_50_doji(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 50: Doji
        Body < 10% of range.
        Maximum indecision - potential reversal.
        """
        body = (df['close'] - df['open']).abs()
        bar_range = df['high'] - df['low']
        return body < (bar_range * 0.1)

    @staticmethod
    def pattern_51_hammer(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 51: Hammer (bullish reversal)
        Small body in upper third, long lower shadow (>2x body).
        Rejection of lower prices.
        """
        body = (df['close'] - df['open']).abs()
        bar_range = df['high'] - df['low']
        body_high = df[['close', 'open']].max(axis=1)
        body_low = df[['close', 'open']].min(axis=1)
        upper_shadow = df['high'] - body_high
        lower_shadow = body_low - df['low']

        # Body in upper third
        body_position = (body_low - df['low']) / bar_range.replace(0, np.nan)

        return (body_position > 0.6) & (lower_shadow > body * 2) & (upper_shadow < body)

    @staticmethod
    def pattern_52_shooting_star(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 52: Shooting star (bearish reversal)
        Small body in lower third, long upper shadow (>2x body).
        Rejection of higher prices.
        """
        body = (df['close'] - df['open']).abs()
        bar_range = df['high'] - df['low']
        body_high = df[['close', 'open']].max(axis=1)
        body_low = df[['close', 'open']].min(axis=1)
        upper_shadow = df['high'] - body_high
        lower_shadow = body_low - df['low']

        # Body in lower third
        body_position = (body_high - df['low']) / bar_range.replace(0, np.nan)

        return (body_position < 0.4) & (upper_shadow > body * 2) & (lower_shadow < body)

    @staticmethod
    def pattern_53_bullish_engulfing(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 53: Bullish engulfing
        Previous bar bearish, current bar bullish and body engulfs previous body.
        Strong bullish reversal.
        """
        prev_bearish = df['close'].shift(1) < df['open'].shift(1)
        curr_bullish = df['close'] > df['open']

        prev_body_high = df[['close', 'open']].shift(1).max(axis=1)
        prev_body_low = df[['close', 'open']].shift(1).min(axis=1)

        engulfs = (df['close'] > prev_body_high) & (df['open'] < prev_body_low)

        return prev_bearish & curr_bullish & engulfs

    @staticmethod
    def pattern_54_bearish_engulfing(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 54: Bearish engulfing
        Previous bar bullish, current bar bearish and body engulfs previous body.
        Strong bearish reversal.
        """
        prev_bullish = df['close'].shift(1) > df['open'].shift(1)
        curr_bearish = df['close'] < df['open']

        prev_body_high = df[['close', 'open']].shift(1).max(axis=1)
        prev_body_low = df[['close', 'open']].shift(1).min(axis=1)

        engulfs = (df['open'] > prev_body_high) & (df['close'] < prev_body_low)

        return prev_bullish & curr_bearish & engulfs

    # =========================================================================
    # PATTERNS 55-57: VOLUME PATTERNS
    # =========================================================================

    @staticmethod
    def pattern_55_volume_spike(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 55: Volume spike
        Volume > 200% of 20-bar average.
        Significant interest - potential reversal or continuation.
        """
        if 'volume' not in df.columns:
            return pd.Series(False, index=df.index)
        avg_volume = df['volume'].rolling(20).mean().shift(1)
        return df['volume'] > (avg_volume * 2.0)

    @staticmethod
    def pattern_56_low_volume(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 56: Low volume bar
        Volume < 50% of 20-bar average.
        Lack of conviction - potential reversal.
        """
        if 'volume' not in df.columns:
            return pd.Series(False, index=df.index)
        avg_volume = df['volume'].rolling(20).mean().shift(1)
        return df['volume'] < (avg_volume * 0.5)

    @staticmethod
    def pattern_57_volume_climax(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 57: Volume climax
        Highest volume in 20 bars + wide range bar.
        Exhaustion move - potential reversal.
        """
        if 'volume' not in df.columns:
            return pd.Series(False, index=df.index)

        max_volume_20 = df['volume'].rolling(20).max()
        is_highest_volume = df['volume'] >= max_volume_20

        bar_range = df['high'] - df['low']
        avg_range = bar_range.rolling(20).mean().shift(1)
        is_wide_range = bar_range > (avg_range * 1.5)

        return is_highest_volume & is_wide_range

    # =========================================================================
    # PATTERNS 58-60: RANGE PATTERNS
    # =========================================================================

    @staticmethod
    def pattern_58_nr4(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 58: NR4 (Narrow Range 4)
        Smallest range in last 4 bars.
        Compression before expansion.
        """
        bar_range = df['high'] - df['low']
        min_range_4 = bar_range.rolling(4).min()
        return bar_range <= min_range_4

    @staticmethod
    def pattern_59_nr7(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 59: NR7 (Narrow Range 7)
        Smallest range in last 7 bars.
        Strong compression - expect bigger move.
        """
        bar_range = df['high'] - df['low']
        min_range_7 = bar_range.rolling(7).min()
        return bar_range <= min_range_7

    @staticmethod
    def pattern_60_wide_range_7(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 60: Wide Range 7
        Largest range in last 7 bars.
        Strong momentum bar.
        """
        bar_range = df['high'] - df['low']
        max_range_7 = bar_range.rolling(7).max()
        return bar_range >= max_range_7

    # =========================================================================
    # PATTERNS 61-66: STRUCTURE AND REVERSAL PATTERNS
    # =========================================================================

    @staticmethod
    def pattern_61_double_inside(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 61: Double inside bar (2 consecutive)
        Extreme compression - explosive move expected.
        """
        inside_0 = (df['high'] < df['high'].shift(1)) & (df['low'] > df['low'].shift(1))
        inside_1 = (df['high'].shift(1) < df['high'].shift(2)) & (df['low'].shift(1) > df['low'].shift(2))
        return inside_0 & inside_1

    @staticmethod
    def pattern_62_pin_bar_up(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 62: Bullish pin bar
        Long lower wick (>66% of range), body in upper third, lower low than previous.
        Rejection of lower prices after probe.
        """
        bar_range = df['high'] - df['low']
        body_low = df[['close', 'open']].min(axis=1)
        lower_wick = body_low - df['low']

        long_lower_wick = lower_wick > (bar_range * 0.66)
        body_in_upper = (body_low - df['low']) > (bar_range * 0.66)
        made_lower_low = df['low'] < df['low'].shift(1)

        return long_lower_wick & body_in_upper & made_lower_low

    @staticmethod
    def pattern_63_pin_bar_down(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 63: Bearish pin bar
        Long upper wick (>66% of range), body in lower third, higher high than previous.
        Rejection of higher prices after probe.
        """
        bar_range = df['high'] - df['low']
        body_high = df[['close', 'open']].max(axis=1)
        upper_wick = df['high'] - body_high

        long_upper_wick = upper_wick > (bar_range * 0.66)
        body_in_lower = (df['high'] - body_high) > (bar_range * 0.66)
        made_higher_high = df['high'] > df['high'].shift(1)

        return long_upper_wick & body_in_lower & made_higher_high

    @staticmethod
    def pattern_64_failed_breakout_up(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 64: Failed breakout up (bull trap)
        Made new 5-bar high but closed below previous close.
        Bearish reversal signal.
        """
        high_5 = df['high'].rolling(5).max().shift(1)
        made_new_high = df['high'] > high_5
        closed_lower = df['close'] < df['close'].shift(1)
        return made_new_high & closed_lower

    @staticmethod
    def pattern_65_failed_breakout_down(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 65: Failed breakout down (bear trap)
        Made new 5-bar low but closed above previous close.
        Bullish reversal signal.
        """
        low_5 = df['low'].rolling(5).min().shift(1)
        made_new_low = df['low'] < low_5
        closed_higher = df['close'] > df['close'].shift(1)
        return made_new_low & closed_higher

    @staticmethod
    def pattern_66_momentum_shift(df: pd.DataFrame) -> pd.Series:
        """
        Pattern 66: Momentum shift
        3 bars same direction then reversal bar.
        Potential trend change.
        """
        # 3 consecutive up closes
        up_3 = (
            (df['close'].shift(1) > df['close'].shift(2)) &
            (df['close'].shift(2) > df['close'].shift(3)) &
            (df['close'].shift(3) > df['close'].shift(4))
        )
        reversal_down = df['close'] < df['close'].shift(1)
        bull_to_bear = up_3 & reversal_down

        # 3 consecutive down closes
        down_3 = (
            (df['close'].shift(1) < df['close'].shift(2)) &
            (df['close'].shift(2) < df['close'].shift(3)) &
            (df['close'].shift(3) < df['close'].shift(4))
        )
        reversal_up = df['close'] > df['close'].shift(1)
        bear_to_bull = down_3 & reversal_up

        return bull_to_bear | bear_to_bull

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    @classmethod
    def get_pattern(cls, pattern_num: int, df: pd.DataFrame) -> pd.Series:
        """
        Get pattern by number.

        Args:
            pattern_num: Pattern number (1-66, gaps at 44-49)
            df: OHLCV DataFrame

        Returns:
            Boolean Series with pattern activation
        """
        pattern_map = cls._get_pattern_map()

        if pattern_num not in pattern_map:
            raise ValueError(f"Pattern {pattern_num} not found. Valid: {sorted(pattern_map.keys())}")

        return pattern_map[pattern_num](df)

    @classmethod
    def get_pattern_name(cls, pattern_num: int) -> str:
        """Get human-readable name for pattern number."""
        method_name = f"pattern_{pattern_num:02d}_"
        for name in dir(cls):
            if name.startswith(method_name):
                # Extract name after pattern_XX_
                return name[len(method_name):]
        return f"pattern_{pattern_num}"

    @classmethod
    def evaluate_all(cls, df: pd.DataFrame) -> dict[int, pd.Series]:
        """
        Evaluate all patterns on DataFrame.

        Args:
            df: OHLCV DataFrame

        Returns:
            Dict mapping pattern number to boolean Series
        """
        pattern_map = cls._get_pattern_map()
        results = {}

        for num, func in pattern_map.items():
            try:
                results[num] = func(df)
            except Exception as e:
                # Log error but continue with other patterns
                results[num] = pd.Series(False, index=df.index)

        return results

    @classmethod
    def get_active_patterns(cls, df: pd.DataFrame, bar_index: int = -1) -> list[int]:
        """
        Get list of pattern numbers active at specific bar.

        Args:
            df: OHLCV DataFrame
            bar_index: Index of bar to check (default: last bar)

        Returns:
            List of active pattern numbers
        """
        all_patterns = cls.evaluate_all(df)
        active = []

        for num, series in all_patterns.items():
            if series.iloc[bar_index]:
                active.append(num)

        return sorted(active)

    @classmethod
    def get_pattern_stats(cls, df: pd.DataFrame) -> dict[int, dict]:
        """
        Get statistics for all patterns.

        Args:
            df: OHLCV DataFrame

        Returns:
            Dict with pattern stats (count, frequency)
        """
        all_patterns = cls.evaluate_all(df)
        total_bars = len(df)
        stats = {}

        for num, series in all_patterns.items():
            count = series.sum()
            stats[num] = {
                'name': cls.get_pattern_name(num),
                'count': int(count),
                'frequency': float(count / total_bars) if total_bars > 0 else 0.0
            }

        return stats

    @classmethod
    def _get_pattern_map(cls) -> dict[int, Callable]:
        """Build mapping of pattern number to method."""
        pattern_map = {}

        for name in dir(cls):
            if name.startswith('pattern_') and callable(getattr(cls, name)):
                # Extract number from pattern_XX_name
                try:
                    num = int(name.split('_')[1])
                    pattern_map[num] = getattr(cls, name)
                except (IndexError, ValueError):
                    continue

        return pattern_map

    @classmethod
    def get_available_patterns(cls) -> list[int]:
        """Get list of all available pattern numbers."""
        return sorted(cls._get_pattern_map().keys())

    @classmethod
    def get_patterns_by_category(cls) -> dict[str, list[int]]:
        """
        Get patterns organized by category.

        Returns:
            Dict mapping category name to list of pattern numbers
        """
        return {
            'volatility_indecision': [1, 2, 3],
            'directional_expansion': [4, 5, 6, 7],
            'consecutive_closes': [8, 9],
            'structure': [10, 11],
            'range_dynamics': [12, 13],
            'close_analysis': [14, 15, 16, 17, 26, 27, 30, 31],
            'gap_analysis': [18, 19, 20, 21, 35, 36],
            'breakout': [22, 23, 24, 25, 28, 29],
            'inside_outside': [32, 33, 34],
            'reversal_bars': [37, 38, 39, 40],
            'crypto_extensions': [41, 42, 43],
            'candlestick_reversal': [50, 51, 52, 53, 54],
            'volume': [55, 56, 57],
            'range_patterns': [58, 59, 60],
            'advanced_structure': [61, 62, 63, 64, 65, 66],
        }

    @classmethod
    def get_bullish_patterns(cls) -> list[int]:
        """Get list of bullish pattern numbers."""
        return [4, 8, 10, 14, 16, 18, 22, 28, 30, 35, 37, 39, 41, 51, 53, 62, 65]

    @classmethod
    def get_bearish_patterns(cls) -> list[int]:
        """Get list of bearish pattern numbers."""
        return [5, 9, 11, 15, 17, 19, 23, 29, 31, 36, 38, 40, 42, 52, 54, 63, 64]

    @classmethod
    def get_neutral_patterns(cls) -> list[int]:
        """Get list of neutral (direction-agnostic) pattern numbers."""
        return [1, 2, 3, 6, 7, 12, 13, 24, 25, 26, 27, 32, 33, 34, 43,
                50, 55, 56, 57, 58, 59, 60, 61, 66]
