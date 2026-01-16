"""
API route modules
"""
from .status import router as status_router
from .pipeline import router as pipeline_router
from .strategies import router as strategies_router
from .templates import router as templates_router
from .validation import router as validation_router
from .execution import router as execution_router
from .performance import router as performance_router
from .trades import router as trades_router
from .subaccounts import router as subaccounts_router
from .services import router as services_router
from .logs import router as logs_router
from .config import router as config_router
from .scheduler import router as scheduler_router
from .coins import router as coins_router
from .metrics import router as metrics_router
from .positions import router as positions_router

__all__ = [
    "status_router",
    "pipeline_router",
    "strategies_router",
    "templates_router",
    "validation_router",
    "execution_router",
    "performance_router",
    "trades_router",
    "subaccounts_router",
    "services_router",
    "logs_router",
    "config_router",
    "scheduler_router",
    "coins_router",
    "metrics_router",
    "positions_router",
]
