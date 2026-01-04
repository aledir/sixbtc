"""
Pairs Updater

Updates coins table in database with top N coins by volume.
Uses Hyperliquid API for volume and max_leverage data,
filtered by Binance availability.

Design Principles:
- KISS: Simple volume-based selection
- Fast Fail: Crash if API unavailable
- No Defaults: All parameters from config
- Database: Coins stored in DB (not JSON)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import requests

from src.config.loader import load_config
from src.data.binance_downloader import BinanceDataDownloader
from src.database import get_session, Coin, PairsUpdateLog
from src.scheduler.task_tracker import track_task_execution

logger = logging.getLogger(__name__)


class PairsUpdater:
    """
    Updates trading pairs configuration based on volume.

    Features:
    - Fetches Hyperliquid market data (symbols + volumes)
    - Filters to Binance-available symbols only
    - Selects top N by 24h volume
    - Saves to config/trading_pairs.json atomically
    """

    HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize PairsUpdater

        Args:
            config: Configuration dict (loads from file if None)
        """
        self.config = config or load_config()

        # Configuration
        self.top_pairs_count = self.config.get('data_scheduler.top_pairs_count', 50)

        # Use trading.min_volume_24h as primary source (for live trading filter)
        # Fall back to data_scheduler.min_volume_usd for backwards compatibility
        self.min_volume_usd = self.config.get(
            'trading.min_volume_24h',
            self.config.get('data_scheduler.min_volume_usd', 1_000_000)
        )

        # Binance downloader for symbol intersection
        self._binance_downloader: Optional[BinanceDataDownloader] = None

        logger.info(
            f"PairsUpdater initialized: "
            f"top_pairs={self.top_pairs_count}, min_volume=${self.min_volume_usd:,.0f}"
        )

    @property
    def binance_downloader(self) -> BinanceDataDownloader:
        """Lazy init binance downloader"""
        if self._binance_downloader is None:
            self._binance_downloader = BinanceDataDownloader(self.config)
        return self._binance_downloader

    def get_hyperliquid_markets(self) -> List[Dict[str, Any]]:
        """
        Fetch all Hyperliquid market data including volumes.

        Returns:
            List of market dicts with: name, volume_24h, price, max_leverage
        """
        try:
            # Fetch meta info (symbols + leverage)
            meta_response = requests.post(
                self.HYPERLIQUID_INFO_URL,
                json={"type": "meta"},
                timeout=10
            )
            meta_response.raise_for_status()
            meta = meta_response.json()

            # Fetch asset contexts (volumes, prices, funding)
            ctx_response = requests.post(
                self.HYPERLIQUID_INFO_URL,
                json={"type": "metaAndAssetCtxs"},
                timeout=10
            )
            ctx_response.raise_for_status()
            ctx_data = ctx_response.json()

            # Parse response
            # metaAndAssetCtxs returns [meta, [ctx1, ctx2, ...]]
            asset_ctxs = ctx_data[1] if len(ctx_data) > 1 else []

            # Build market list
            markets = []

            for i, asset in enumerate(meta['universe']):
                symbol = asset['name']
                max_leverage = asset.get('maxLeverage', 10)

                # Get context data for this asset
                if i < len(asset_ctxs):
                    ctx = asset_ctxs[i]
                    volume_24h = float(ctx.get('dayNtlVlm', 0))
                    price = float(ctx.get('markPx', 0))
                else:
                    volume_24h = 0.0
                    price = 0.0

                markets.append({
                    'symbol': symbol,
                    'volume_24h': volume_24h,
                    'price': price,
                    'max_leverage': max_leverage,
                })

            logger.info(f"Fetched {len(markets)} Hyperliquid markets")
            return markets

        except Exception as e:
            logger.error(f"Failed to fetch Hyperliquid markets: {e}")
            raise

    def get_binance_symbols(self) -> set:
        """
        Get set of Binance perpetual symbols for intersection filter.

        Returns:
            Set of symbol names (e.g., {'BTC', 'ETH', ...})
        """
        return set(self.binance_downloader.get_binance_perps())

    def get_top_pairs_by_volume(self, n_pairs: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get top N pairs by volume (Hyperliquid + Binance intersection).

        Args:
            n_pairs: Number of pairs (defaults to config value)

        Returns:
            List of top pair dicts sorted by volume
        """
        n_pairs = n_pairs or self.top_pairs_count

        # Get Hyperliquid markets with volumes
        hl_markets = self.get_hyperliquid_markets()

        # Get Binance symbols for intersection
        binance_symbols = self.get_binance_symbols()
        logger.info(f"Binance has {len(binance_symbols)} perpetual symbols")

        # Filter to intersection + volume threshold
        filtered = []

        for market in hl_markets:
            symbol = market['symbol']
            volume = market['volume_24h']

            # Must be on Binance
            if symbol not in binance_symbols:
                continue

            # Must meet volume threshold
            if volume < self.min_volume_usd:
                continue

            filtered.append(market)

        # Sort by volume (descending)
        filtered.sort(key=lambda x: x['volume_24h'], reverse=True)

        # Take top N
        top_pairs = filtered[:n_pairs]

        logger.info(
            f"Selected top {len(top_pairs)} pairs by volume "
            f"(from {len(filtered)} eligible, {len(hl_markets)} total HL)"
        )

        return top_pairs

    def save_coins_to_db(self, pairs: List[Dict[str, Any]]) -> dict:
        """
        Save coins to database (upsert).

        Args:
            pairs: List of pair dicts from get_top_pairs_by_volume()

        Returns:
            Dict with counts: total_pairs, new_pairs, updated_pairs, deactivated_pairs
        """
        now = datetime.now(timezone.utc)
        new_pairs = 0
        updated_pairs = 0
        deactivated_pairs = 0

        with get_session() as session:
            # Track currently active coins before update
            previously_active = session.query(Coin.symbol).filter(
                Coin.is_active == True
            ).all()
            previously_active_symbols = {c.symbol for c in previously_active}

            # Mark all existing coins as inactive
            session.query(Coin).update({Coin.is_active: False})

            # Track which symbols will be active after update
            new_active_symbols = {p['symbol'] for p in pairs}

            # Calculate deactivated count
            deactivated_pairs = len(previously_active_symbols - new_active_symbols)

            # Upsert each coin
            for pair in pairs:
                existing = session.query(Coin).filter(
                    Coin.symbol == pair['symbol']
                ).first()

                if existing:
                    # Update existing
                    existing.max_leverage = pair['max_leverage']
                    existing.volume_24h = pair['volume_24h']
                    existing.price = pair['price']
                    existing.is_active = True
                    existing.updated_at = now
                    updated_pairs += 1
                else:
                    # Insert new
                    coin = Coin(
                        symbol=pair['symbol'],
                        max_leverage=pair['max_leverage'],
                        volume_24h=pair['volume_24h'],
                        price=pair['price'],
                        is_active=True,
                        updated_at=now
                    )
                    session.add(coin)
                    new_pairs += 1

        logger.info(
            f"Saved {len(pairs)} coins to database: "
            f"{new_pairs} new, {updated_pairs} updated, {deactivated_pairs} deactivated"
        )

        return {
            'total_pairs': len(pairs),
            'new_pairs': new_pairs,
            'updated_pairs': updated_pairs,
            'deactivated_pairs': deactivated_pairs
        }

    def update(
        self,
        n_pairs: Optional[int] = None,
        triggered_by: str = 'system'
    ) -> dict:
        """
        Full update: fetch markets, select top N, save to database.

        Args:
            n_pairs: Number of pairs (defaults to config value)
            triggered_by: Who triggered the update ('system', 'user:email', 'api')

        Returns:
            Dict with update results
        """
        with track_task_execution(
            'update_pairs',
            task_type='data_update',
            triggered_by=triggered_by
        ) as tracker:
            logger.info("Starting pairs update...")

            # Get top pairs
            top_pairs = self.get_top_pairs_by_volume(n_pairs)

            if not top_pairs:
                raise ValueError("No pairs found - check API connectivity and volume threshold")

            # Save to database and get detailed results
            result = self.save_coins_to_db(top_pairs)

            # Add metadata to tracker
            tracker.add_metadata('total_pairs', result['total_pairs'])
            tracker.add_metadata('new_pairs', result['new_pairs'])
            tracker.add_metadata('updated_pairs', result['updated_pairs'])
            tracker.add_metadata('deactivated_pairs', result['deactivated_pairs'])

            # Save detailed log
            with get_session() as session:
                log = PairsUpdateLog(
                    execution_id=tracker.execution_id,
                    total_pairs=result['total_pairs'],
                    new_pairs=result['new_pairs'],
                    updated_pairs=result['updated_pairs'],
                    deactivated_pairs=result['deactivated_pairs'],
                    top_10_symbols=[p['symbol'] for p in top_pairs[:10]]
                )
                session.add(log)
                session.commit()

            # Log summary
            total_volume = sum(p['volume_24h'] for p in top_pairs)
            logger.info(
                f"Pairs update complete: {len(top_pairs)} pairs, "
                f"total 24h volume: ${total_volume:,.0f}"
            )

            # Return detailed results
            result['pair_whitelist'] = [p['symbol'] for p in top_pairs]
            return result

    def get_pair_whitelist(self) -> List[str]:
        """
        Get current pair whitelist from database.

        Returns:
            List of active symbol names
        """
        with get_session() as session:
            coins = session.query(Coin.symbol).filter(
                Coin.is_active == True
            ).order_by(Coin.volume_24h.desc()).all()

            return [c.symbol for c in coins]

    def get_coin_max_leverage(self, symbol: str) -> int:
        """
        Get max leverage for a specific coin.

        Args:
            symbol: Coin symbol (e.g., 'BTC', 'ETH')

        Returns:
            Max leverage (defaults to 10 if not found)
        """
        with get_session() as session:
            coin = session.query(Coin).filter(
                Coin.symbol == symbol
            ).first()

            if coin:
                return coin.max_leverage

        # No fallback - coin must be in DB
        raise ValueError(
            f"Coin {symbol} not found in DB - cannot determine max_leverage. "
            "Run pairs_updater.update() to sync coins from Hyperliquid."
        )

    def is_config_stale(self, max_age_hours: int = 24) -> bool:
        """
        Check if coin data is stale (older than max_age_hours).

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            True if stale or missing, False if fresh
        """
        with get_session() as session:
            latest = session.query(Coin.updated_at).order_by(
                Coin.updated_at.desc()
            ).first()

            if not latest or not latest.updated_at:
                return True

            age_hours = (datetime.now(timezone.utc) - latest.updated_at).total_seconds() / 3600
            return age_hours > max_age_hours


def update_pairs(n_pairs: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Convenience function to update pairs.

    Args:
        n_pairs: Number of pairs (uses config default if None)

    Returns:
        List of saved pair dicts
    """
    updater = PairsUpdater()
    return updater.update(n_pairs)


def get_current_pairs() -> List[str]:
    """
    Get current pair whitelist directly from database.

    This is a lightweight function that queries the DB directly
    without instantiating PairsUpdater.

    Returns:
        List of active symbol names ordered by volume
    """
    with get_session() as session:
        coins = session.query(Coin.symbol).filter(
            Coin.is_active == True
        ).order_by(Coin.volume_24h.desc()).all()

        return [c.symbol for c in coins]


def get_coins_last_updated() -> Optional[datetime]:
    """
    Get the most recent updated_at timestamp from coins table.

    Used for cache invalidation - if DB was updated after cache was loaded,
    the cache should be refreshed.

    Returns:
        Most recent updated_at datetime, or None if no coins
    """
    with get_session() as session:
        result = session.query(Coin.updated_at).order_by(
            Coin.updated_at.desc()
        ).first()

        return result.updated_at if result else None


def get_coin_max_leverage(symbol: str) -> int:
    """
    Convenience function to get max leverage for a coin.

    Args:
        symbol: Coin symbol (e.g., 'BTC', 'ETH')

    Returns:
        Max leverage from database
    """
    updater = PairsUpdater()
    return updater.get_coin_max_leverage(symbol)


def get_tradable_pairs_for_strategy(
    strategy_backtest_pairs: List[str],
    pattern_coins: Optional[List[str]] = None
) -> List[str]:
    """
    Get pairs tradable for a strategy with pattern-awareness.

    DEPRECATED: Use CoinRegistry.get_tradable_for_strategy() directly.
    This function is kept for backward compatibility.

    Priority:
    1. pattern_coins (if available) - already edge-filtered, preferred
    2. backtest_pairs (fallback) - audit trail pairs

    Intersected with currently active liquid coins.

    Args:
        strategy_backtest_pairs: List from Strategy.backtest_pairs
        pattern_coins: List from Strategy.pattern_coins (high-edge coins)

    Returns:
        List of tradable symbols (maintains pattern order if pattern_coins used)
    """
    # Delegate to CoinRegistry
    from src.data.coin_registry import get_registry

    return get_registry().get_tradable_for_strategy(
        pattern_coins=pattern_coins,
        backtest_pairs=strategy_backtest_pairs
    )
