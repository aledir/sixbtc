"""
API route modules
"""
from .status import router as status_router
from .strategies import router as strategies_router
from .trades import router as trades_router
from .subaccounts import router as subaccounts_router
from .services import router as services_router
from .logs import router as logs_router
from .config import router as config_router

__all__ = [
    "status_router",
    "strategies_router",
    "trades_router",
    "subaccounts_router",
    "services_router",
    "logs_router",
    "config_router",
]
