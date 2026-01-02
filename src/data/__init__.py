"""
Data Layer Module

Handles all market data operations:
- Binance historical data download (backtesting)
- Hyperliquid WebSocket real-time data (live trading)
- Data caching and storage

Note: Imports are explicit to avoid circular imports and allow
running submodules as scripts (python -m src.data.binance_downloader)
"""

# Lazy imports - use explicit imports where needed:
# from src.data.binance_downloader import BinanceDataDownloader
# from src.data.hyperliquid_websocket import HyperliquidDataProvider

__all__ = [
    'BinanceDataDownloader',
    'HyperliquidDataProvider',
]


def __getattr__(name):
    """Lazy import for backwards compatibility"""
    if name == 'BinanceDataDownloader':
        from src.data.binance_downloader import BinanceDataDownloader
        return BinanceDataDownloader
    elif name == 'HyperliquidDataProvider':
        from src.data.hyperliquid_websocket import HyperliquidDataProvider
        return HyperliquidDataProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
