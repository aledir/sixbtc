"""
Regime Detector - Unger Method Implementation

Determines market regime (TREND vs REVERSAL) using two simple tests:

Test 1 (Breakout/Trend Following):
    - Long: Buy when price breaks above previous bar's high
    - Short: Sell when price breaks below previous bar's low
    - If profitable -> market is TREND FOLLOWING

Test 2 (Reversal/Mean Reversion):
    - Long: Buy at previous bar's low (limit order)
    - Short: Sell at previous bar's high (limit order)
    - If profitable -> market is MEAN REVERTING

Interpretation:
    - Test 1 profitable, Test 2 loses -> TREND
    - Test 2 profitable, Test 1 loses -> REVERSAL
    - Both similar or unclear -> MIXED

Reference: Andrea Unger (4x World Trading Champion)
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional, Dict, List
import pandas as pd
import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


class RegimeType(str, Enum):
    """Market regime classification."""
    TREND = "TREND"
    REVERSAL = "REVERSAL"
    MIXED = "MIXED"


@dataclass
class RegimeResult:
    """
    Result of regime detection for a single symbol.

    Attributes:
        symbol: Trading pair symbol (e.g., 'BTC', 'ETH')
        regime_type: TREND, REVERSAL, or MIXED
        strength: Confidence in regime (0-1), higher = stronger signal
        direction: Whether regime favors LONG, SHORT, or BOTH
        breakout_pnl: Total PnL % from breakout test
        breakout_long_pnl: Long-only PnL from breakout
        breakout_short_pnl: Short-only PnL from breakout
        reversal_pnl: Total PnL % from reversal test
        reversal_long_pnl: Long-only PnL from reversal
        reversal_short_pnl: Short-only PnL from reversal
        regime_score: breakout_pnl - reversal_pnl (positive = trend)
        window_days: Number of days analyzed
        calculated_at: Timestamp of calculation
    """
    symbol: str
    regime_type: Literal["TREND", "REVERSAL", "MIXED"]
    strength: float
    direction: Literal["BOTH", "LONG", "SHORT"]
    breakout_pnl: float
    breakout_long_pnl: float
    breakout_short_pnl: float
    reversal_pnl: float
    reversal_long_pnl: float
    reversal_short_pnl: float
    regime_score: float
    window_days: int
    calculated_at: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON/DB storage."""
        d = asdict(self)
        d['calculated_at'] = self.calculated_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> 'RegimeResult':
        """Create from dictionary."""
        d = d.copy()
        if isinstance(d['calculated_at'], str):
            d['calculated_at'] = datetime.fromisoformat(d['calculated_at'])
        return cls(**d)

    def __repr__(self) -> str:
        return (
            f"RegimeResult({self.symbol}: {self.regime_type}, "
            f"strength={self.strength:.2f}, score={self.regime_score:+.2f}%)"
        )


class RegimeDetector:
    """
    Detects market regime using Unger's breakout vs reversal tests.

    All calculations are vectorized with pandas/numpy for speed.
    No Numba needed - runs in milliseconds per symbol.

    Usage:
        detector = RegimeDetector(window_days=90)
        result = detector.detect(df_daily, symbol='BTC')

        # Or detect all coins at once
        results = detector.detect_all(pairs=['BTC', 'ETH', 'SOL'])
    """

    def __init__(
        self,
        window_days: int = 90,
        trend_threshold: float = 0.6,
        reversal_threshold: float = 0.6,
        min_strength: float = 0.5,
        data_dir: str = 'data/binance'
    ):
        """
        Initialize regime detector.

        Args:
            window_days: Rolling window for regime analysis (default 90)
            trend_threshold: Ratio threshold for TREND classification
            reversal_threshold: Ratio threshold for REVERSAL classification
            min_strength: Minimum strength for non-MIXED classification
            data_dir: Directory for OHLCV data files
        """
        self.window_days = window_days
        self.trend_threshold = trend_threshold
        self.reversal_threshold = reversal_threshold
        self.min_strength = min_strength
        self.data_dir = data_dir

    def detect(self, df: pd.DataFrame, symbol: str = 'UNKNOWN') -> RegimeResult:
        """
        Detect regime for a single symbol.

        Args:
            df: OHLCV DataFrame with columns [timestamp, open, high, low, close, volume]
                Must have at least window_days + 1 rows
            symbol: Symbol name for result labeling

        Returns:
            RegimeResult with regime classification and metrics
        """
        # Validate input
        if df is None or len(df) < self.window_days + 1:
            logger.warning(
                f"{symbol}: Insufficient data ({len(df) if df is not None else 0} bars, "
                f"need {self.window_days + 1})"
            )
            return self._empty_result(symbol)

        # Use last window_days
        df = df.tail(self.window_days + 1).copy().reset_index(drop=True)

        # Run tests
        breakout_results = self._test_breakout(df)
        reversal_results = self._test_reversal(df)

        # Calculate totals
        breakout_pnl = breakout_results['long_pnl'] + breakout_results['short_pnl']
        reversal_pnl = reversal_results['long_pnl'] + reversal_results['short_pnl']

        # Regime score: positive = trend, negative = reversal
        regime_score = breakout_pnl - reversal_pnl

        # Classify regime
        regime_type, strength = self._classify_regime(
            breakout_pnl, reversal_pnl,
            breakout_results, reversal_results
        )

        # Determine direction bias
        direction = self._determine_direction(
            breakout_results if regime_type == "TREND" else reversal_results
        )

        return RegimeResult(
            symbol=symbol,
            regime_type=regime_type,
            strength=strength,
            direction=direction,
            breakout_pnl=round(breakout_pnl, 4),
            breakout_long_pnl=round(breakout_results['long_pnl'], 4),
            breakout_short_pnl=round(breakout_results['short_pnl'], 4),
            reversal_pnl=round(reversal_pnl, 4),
            reversal_long_pnl=round(reversal_results['long_pnl'], 4),
            reversal_short_pnl=round(reversal_results['short_pnl'], 4),
            regime_score=round(regime_score, 4),
            window_days=self.window_days,
            calculated_at=datetime.now(timezone.utc)
        )

    def _test_breakout(self, df: pd.DataFrame) -> dict:
        """
        Test 1: Breakout/Trend Following strategy.

        Rules:
        - Long entry: close > previous high
        - Short entry: close < previous low
        - Exit: next bar close

        All vectorized for speed.
        """
        # Previous bar's high/low
        prev_high = df['high'].shift(1)
        prev_low = df['low'].shift(1)

        # Entry signals
        long_entry = df['close'] > prev_high
        short_entry = df['close'] < prev_low

        # Next bar close for exit
        next_close = df['close'].shift(-1)

        # PnL calculation (percentage)
        # Long: (exit - entry) / entry
        # Short: (entry - exit) / entry
        long_pnl = ((next_close - df['close']) / df['close']) * long_entry
        short_pnl = ((df['close'] - next_close) / df['close']) * short_entry

        # Remove NaN (first/last bars)
        long_pnl = long_pnl.dropna()
        short_pnl = short_pnl.dropna()

        return {
            'long_pnl': long_pnl.sum() * 100,  # As percentage
            'short_pnl': short_pnl.sum() * 100,
            'long_trades': int(long_entry.sum()),
            'short_trades': int(short_entry.sum()),
        }

    def _test_reversal(self, df: pd.DataFrame) -> dict:
        """
        Test 2: Reversal/Mean Reversion strategy.

        Rules:
        - Long entry: price touches previous bar's low (limit order filled)
        - Short entry: price touches previous bar's high (limit order filled)
        - Exit: next bar close

        For simplicity, we assume limit orders are filled if:
        - Long: current low <= previous low
        - Short: current high >= previous high

        Entry price is the limit price (previous low/high).
        """
        # Previous bar's high/low (limit order prices)
        prev_high = df['high'].shift(1)
        prev_low = df['low'].shift(1)

        # Check if limit order would be filled
        # Long: current bar's low must reach previous low
        long_filled = df['low'] <= prev_low
        # Short: current bar's high must reach previous high
        short_filled = df['high'] >= prev_high

        # Next bar close for exit
        next_close = df['close'].shift(-1)

        # Entry price is the limit price
        long_entry_price = prev_low
        short_entry_price = prev_high

        # PnL calculation (percentage)
        # Long: (exit - entry) / entry (only if filled)
        # Short: (entry - exit) / entry (only if filled)
        long_pnl = ((next_close - long_entry_price) / long_entry_price) * long_filled
        short_pnl = ((short_entry_price - next_close) / short_entry_price) * short_filled

        # Remove NaN
        long_pnl = long_pnl.dropna()
        short_pnl = short_pnl.dropna()

        return {
            'long_pnl': long_pnl.sum() * 100,  # As percentage
            'short_pnl': short_pnl.sum() * 100,
            'long_trades': int(long_filled.sum()),
            'short_trades': int(short_filled.sum()),
        }

    def _classify_regime(
        self,
        breakout_pnl: float,
        reversal_pnl: float,
        breakout_results: dict,
        reversal_results: dict
    ) -> tuple:
        """
        Classify regime based on test results.

        Returns:
            (regime_type, strength) tuple
        """
        # Handle edge cases
        if breakout_pnl == 0 and reversal_pnl == 0:
            return ("MIXED", 0.0)

        # Calculate ratio (avoid division by zero)
        if reversal_pnl <= 0 and breakout_pnl > 0:
            # Breakout profitable, reversal loses -> strong TREND
            strength = min(1.0, breakout_pnl / 10)  # Normalize to 0-1
            if strength >= self.min_strength:
                return ("TREND", strength)
            return ("MIXED", strength)

        if breakout_pnl <= 0 and reversal_pnl > 0:
            # Reversal profitable, breakout loses -> strong REVERSAL
            strength = min(1.0, reversal_pnl / 10)
            if strength >= self.min_strength:
                return ("REVERSAL", strength)
            return ("MIXED", strength)

        # Both positive or both negative - compare ratios
        if breakout_pnl > 0 and reversal_pnl > 0:
            ratio = breakout_pnl / reversal_pnl
            if ratio > self.trend_threshold + 1:
                strength = min(1.0, (ratio - 1) / 2)
                return ("TREND", strength)
            elif ratio < 1 / (self.reversal_threshold + 1):
                strength = min(1.0, (1/ratio - 1) / 2)
                return ("REVERSAL", strength)
            else:
                # Close to even
                strength = 0.3
                return ("MIXED", strength)

        # Both negative - less reliable
        if breakout_pnl < 0 and reversal_pnl < 0:
            # Which loses less?
            if abs(breakout_pnl) < abs(reversal_pnl) * 0.5:
                return ("TREND", 0.3)
            elif abs(reversal_pnl) < abs(breakout_pnl) * 0.5:
                return ("REVERSAL", 0.3)
            else:
                return ("MIXED", 0.2)

        return ("MIXED", 0.0)

    def _determine_direction(self, results: dict) -> Literal["BOTH", "LONG", "SHORT"]:
        """
        Determine if regime favors longs, shorts, or both.
        """
        long_pnl = results['long_pnl']
        short_pnl = results['short_pnl']

        # If one side is clearly better
        if long_pnl > 0 and short_pnl <= 0:
            return "LONG"
        if short_pnl > 0 and long_pnl <= 0:
            return "SHORT"

        # Both positive or both negative
        if long_pnl > 0 and short_pnl > 0:
            ratio = long_pnl / short_pnl if short_pnl != 0 else float('inf')
            if ratio > 2:
                return "LONG"
            elif ratio < 0.5:
                return "SHORT"

        return "BOTH"

    def _empty_result(self, symbol: str) -> RegimeResult:
        """Create empty result for insufficient data."""
        return RegimeResult(
            symbol=symbol,
            regime_type="MIXED",
            strength=0.0,
            direction="BOTH",
            breakout_pnl=0.0,
            breakout_long_pnl=0.0,
            breakout_short_pnl=0.0,
            reversal_pnl=0.0,
            reversal_long_pnl=0.0,
            reversal_short_pnl=0.0,
            regime_score=0.0,
            window_days=self.window_days,
            calculated_at=datetime.now(timezone.utc)
        )

    def detect_from_file(self, symbol: str, timeframe: str = '1d') -> RegimeResult:
        """
        Detect regime by loading data from cache file.

        Args:
            symbol: Trading pair symbol
            timeframe: Data timeframe (default '1d')

        Returns:
            RegimeResult
        """
        from pathlib import Path

        file_path = Path(self.data_dir) / f"{symbol}_{timeframe}.parquet"

        if not file_path.exists():
            logger.warning(f"{symbol}: No {timeframe} data file found at {file_path}")
            return self._empty_result(symbol)

        try:
            df = pd.read_parquet(file_path)
            return self.detect(df, symbol)
        except Exception as e:
            logger.error(f"{symbol}: Failed to read data file: {e}")
            return self._empty_result(symbol)

    def detect_all(
        self,
        pairs: Optional[List[str]] = None,
        timeframe: str = '1d',
        limit: int = 30
    ) -> List[RegimeResult]:
        """
        Detect regime for multiple symbols.

        Args:
            pairs: List of symbols (if None, uses get_active_pairs)
            timeframe: Data timeframe
            limit: Max pairs to analyze

        Returns:
            List of RegimeResult sorted by strength descending
        """
        if pairs is None:
            from src.data.coin_registry import get_active_pairs
            pairs = get_active_pairs(limit=limit)

        results = []
        for symbol in pairs:
            result = self.detect_from_file(symbol, timeframe)
            results.append(result)

        # Sort by strength descending, then symbol for deterministic ordering
        results.sort(key=lambda r: (-r.strength, r.symbol))

        return results

    def get_summary(self, results: List[RegimeResult]) -> Dict:
        """
        Generate summary statistics from regime results.

        Args:
            results: List of RegimeResult

        Returns:
            Summary dict with counts and percentages
        """
        total = len(results)
        if total == 0:
            return {'total': 0, 'trend': 0, 'reversal': 0, 'mixed': 0}

        trend_count = sum(1 for r in results if r.regime_type == "TREND")
        reversal_count = sum(1 for r in results if r.regime_type == "REVERSAL")
        mixed_count = sum(1 for r in results if r.regime_type == "MIXED")

        return {
            'total': total,
            'trend': trend_count,
            'trend_pct': round(trend_count / total * 100, 1),
            'reversal': reversal_count,
            'reversal_pct': round(reversal_count / total * 100, 1),
            'mixed': mixed_count,
            'mixed_pct': round(mixed_count / total * 100, 1),
            'avg_strength': round(
                sum(r.strength for r in results) / total, 2
            ),
        }

    def get_all_regimes(self, timeframe: str = '1d') -> Dict[str, RegimeResult]:
        """
        Calculate regime for all active coins.

        Args:
            timeframe: Data timeframe (default '1d')

        Returns:
            Dict mapping symbol -> RegimeResult
        """
        from src.data.coin_registry import get_active_pairs

        pairs = get_active_pairs(limit=None)  # All active coins
        logger.info(f"Calculating regime for {len(pairs)} coins...")

        results = {}
        for symbol in pairs:
            result = self.detect_from_file(symbol, timeframe)
            results[symbol] = result

        logger.info(f"Regime calculated for {len(results)} coins")
        return results

    def group_by_regime(
        self,
        regimes: Dict[str, RegimeResult]
    ) -> Dict[tuple, List[str]]:
        """
        Group coins by (regime_type, direction).

        Args:
            regimes: Dict mapping symbol -> RegimeResult

        Returns:
            Dict mapping (type, direction) -> [symbols]
        """
        groups: Dict[tuple, List[str]] = {}

        for symbol, regime in regimes.items():
            key = (regime.regime_type, regime.direction)
            if key not in groups:
                groups[key] = []
            groups[key].append(symbol)

        # Log group sizes
        for key, coins in groups.items():
            logger.debug(f"Regime group {key}: {len(coins)} coins")

        return groups

    def save_to_db(self, results: List[RegimeResult]) -> int:
        """
        Save regime results to database.

        Uses upsert (INSERT ... ON CONFLICT UPDATE) to update existing records.

        Args:
            results: List of RegimeResult to save

        Returns:
            Number of records saved
        """
        from src.database import get_session, MarketRegime

        saved = 0
        with get_session() as session:
            for r in results:
                # Convert numpy types to native Python (psycopg2 compatibility)
                breakout_pnl = float(r.breakout_pnl)
                breakout_long_pnl = float(r.breakout_long_pnl)
                breakout_short_pnl = float(r.breakout_short_pnl)
                reversal_pnl = float(r.reversal_pnl)
                reversal_long_pnl = float(r.reversal_long_pnl)
                reversal_short_pnl = float(r.reversal_short_pnl)
                regime_score = float(r.regime_score)
                strength = float(r.strength)

                # Upsert pattern
                existing = session.query(MarketRegime).filter_by(
                    symbol=r.symbol
                ).first()

                if existing:
                    # Update existing
                    existing.regime_type = r.regime_type
                    existing.strength = strength
                    existing.direction = r.direction
                    existing.breakout_pnl = breakout_pnl
                    existing.breakout_long_pnl = breakout_long_pnl
                    existing.breakout_short_pnl = breakout_short_pnl
                    existing.reversal_pnl = reversal_pnl
                    existing.reversal_long_pnl = reversal_long_pnl
                    existing.reversal_short_pnl = reversal_short_pnl
                    existing.regime_score = regime_score
                    existing.window_days = r.window_days
                    existing.calculated_at = r.calculated_at
                else:
                    # Insert new
                    regime = MarketRegime(
                        symbol=r.symbol,
                        regime_type=r.regime_type,
                        strength=strength,
                        direction=r.direction,
                        breakout_pnl=breakout_pnl,
                        breakout_long_pnl=breakout_long_pnl,
                        breakout_short_pnl=breakout_short_pnl,
                        reversal_pnl=reversal_pnl,
                        reversal_long_pnl=reversal_long_pnl,
                        reversal_short_pnl=reversal_short_pnl,
                        regime_score=regime_score,
                        window_days=r.window_days,
                        calculated_at=r.calculated_at
                    )
                    session.add(regime)

                saved += 1

            session.commit()

        logger.info(f"Saved {saved} regime records to database")
        return saved

    def refresh_all(self, save_to_db: bool = True) -> Dict:
        """
        Refresh regime detection for all active pairs.

        This is the main entry point for scheduled regime refresh.

        Args:
            save_to_db: If True, saves results to database

        Returns:
            Summary dict with counts and stats
        """
        from src.config import load_config

        config = load_config()
        regime_config = config._raw_config.get('regime', {})
        timeframe = regime_config.get('timeframe', '1d')

        # Detect all active coins (no limit - analyze entire universe)
        results = self.detect_all(pairs=None, timeframe=timeframe, limit=None)

        # Save to DB if requested
        if save_to_db:
            self.save_to_db(results)

        # Generate summary
        summary = self.get_summary(results)

        # Log summary
        logger.info(
            f"Regime refresh complete: TREND={summary['trend']}, "
            f"REVERSAL={summary['reversal']}, MIXED={summary['mixed']}"
        )

        return summary


def refresh_market_regimes() -> Dict:
    """
    Scheduled task to refresh market regimes.

    Called by scheduler daemon daily.

    Returns:
        Summary dict with regime counts
    """
    from src.config import load_config

    config = load_config()
    regime_config = config._raw_config.get('regime', {})

    if not regime_config.get('enabled', False):
        logger.info("Regime detection disabled in config")
        return {'enabled': False}

    detector = RegimeDetector(
        window_days=regime_config.get('window_days', 90),
        trend_threshold=regime_config.get('trend_threshold', 0.6),
        reversal_threshold=regime_config.get('reversal_threshold', 0.6),
        min_strength=regime_config.get('min_strength', 0.5),
    )

    return detector.refresh_all(save_to_db=True)


def run_regime_detection():
    """
    CLI entry point for regime detection.

    Usage:
        python -m src.generator.regime.detector
    """
    from src.config import load_config
    from src.data.coin_registry import get_active_pairs

    config = load_config()
    regime_config = config._raw_config.get('regime', {})
    window_days = regime_config.get('window_days', 90)

    detector = RegimeDetector(
        window_days=window_days,
        trend_threshold=regime_config.get('trend_threshold', 0.6),
        reversal_threshold=regime_config.get('reversal_threshold', 0.6),
        min_strength=regime_config.get('min_strength', 0.5),
    )

    # Get top pairs by volume
    pairs = get_active_pairs(limit=30)

    print(f"\nREGIME DETECTION ({window_days}d window, {datetime.now(timezone.utc).date()})")
    print("=" * 80)
    print(f"{'Symbol':<8} {'Regime':<10} {'Strength':>8} {'Direction':>10} "
          f"{'Breakout%':>10} {'Reversal%':>10} {'Score':>8}")
    print("-" * 80)

    results = detector.detect_all(pairs, timeframe='1d')

    for r in results:
        print(
            f"{r.symbol:<8} {r.regime_type:<10} {r.strength:>8.2f} {r.direction:>10} "
            f"{r.breakout_pnl:>+10.2f} {r.reversal_pnl:>+10.2f} {r.regime_score:>+8.2f}"
        )

    print("-" * 80)
    summary = detector.get_summary(results)
    print(f"\nSummary:")
    print(f"  TREND: {summary['trend']}/{summary['total']} ({summary['trend_pct']}%)")
    print(f"  REVERSAL: {summary['reversal']}/{summary['total']} ({summary['reversal_pct']}%)")
    print(f"  MIXED: {summary['mixed']}/{summary['total']} ({summary['mixed_pct']}%)")
    print(f"  Avg Strength: {summary['avg_strength']}")


if __name__ == "__main__":
    run_regime_detection()
