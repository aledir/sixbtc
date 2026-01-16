"""
SixBTC Control Center API

FastAPI application for the web dashboard.
Provides REST API endpoints + WebSocket for real-time updates.
"""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.config import load_config
from src.utils import setup_logging, get_logger

# Initialize logging with rotation
_config = load_config()._raw_config
setup_logging(
    log_file='logs/api.log',
    log_level=_config.get('logging', {}).get('level', 'INFO'),
)
logger = get_logger(__name__)

# Track startup time for uptime calculation
START_TIME = time.time()


def get_uptime_seconds() -> int:
    """Get API uptime in seconds"""
    return int(time.time() - START_TIME)


# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()

# Background task for snapshot refresh
_snapshot_refresh_task = None
SNAPSHOT_REFRESH_INTERVAL = 60  # Refresh every 60 seconds


async def _refresh_snapshot_background():
    """Background task to refresh the metrics snapshot periodically."""
    from src.api.routes.metrics import _refresh_snapshot_cache

    logger.info("Starting background snapshot refresh task")

    # Initial computation (run immediately)
    try:
        logger.info("Pre-computing initial metrics snapshot...")
        await asyncio.get_event_loop().run_in_executor(None, _refresh_snapshot_cache)
        logger.info("Initial snapshot ready")
    except Exception as e:
        logger.error(f"Error computing initial snapshot: {e}")

    # Periodic refresh
    while True:
        try:
            await asyncio.sleep(SNAPSHOT_REFRESH_INTERVAL)
            await asyncio.get_event_loop().run_in_executor(None, _refresh_snapshot_cache)
        except asyncio.CancelledError:
            logger.info("Background snapshot refresh task cancelled")
            break
        except Exception as e:
            logger.error(f"Error refreshing snapshot: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    global _snapshot_refresh_task

    logger.info("SixBTC Control Center API starting...")

    # Start background snapshot refresh
    _snapshot_refresh_task = asyncio.create_task(_refresh_snapshot_background())

    yield

    # Cancel background task on shutdown
    if _snapshot_refresh_task:
        _snapshot_refresh_task.cancel()
        try:
            await _snapshot_refresh_task
        except asyncio.CancelledError:
            pass

    logger.info("SixBTC Control Center API shutting down...")


# Create FastAPI app
app = FastAPI(
    title="SixBTC Control Center",
    description="Dashboard API for SixBTC AI Trading System",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS (allow localhost and Tailscale for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://100.95.179.24:5173",  # Tailscale fivebtc-dev
        "http://100.95.179.24:3000",
        "http://fivebtc-dev:5173",  # Tailscale hostname
        "http://fivebtc-dev:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# IMPORT AND REGISTER ROUTES
# =============================================================================

from src.api.routes import (
    config_router,
    execution_router,
    logs_router,
    metrics_router,
    performance_router,
    pipeline_router,
    positions_router,
    preflight_router,
    scheduler_router,
    coins_router,
    services_router,
    status_router,
    strategies_router,
    subaccounts_router,
    templates_router,
    trades_router,
    validation_router,
)

app.include_router(status_router, prefix="/api", tags=["Status"])
app.include_router(pipeline_router, prefix="/api", tags=["Pipeline"])
app.include_router(strategies_router, prefix="/api", tags=["Strategies"])
app.include_router(templates_router, prefix="/api", tags=["Templates"])
app.include_router(validation_router, prefix="/api", tags=["Validation"])
app.include_router(execution_router, prefix="/api", tags=["Execution"])
app.include_router(performance_router, prefix="/api", tags=["Performance"])
app.include_router(trades_router, prefix="/api", tags=["Trades"])
app.include_router(subaccounts_router, prefix="/api", tags=["Subaccounts"])
app.include_router(positions_router, prefix="/api", tags=["Positions"])
app.include_router(scheduler_router, prefix="/api", tags=["Scheduler"])
app.include_router(coins_router, prefix="/api", tags=["Coins"])
app.include_router(services_router, prefix="/api", tags=["Services"])
app.include_router(logs_router, prefix="/api", tags=["Logs"])
app.include_router(config_router, prefix="/api", tags=["Config"])
app.include_router(preflight_router, prefix="/api", tags=["Preflight"])
app.include_router(metrics_router, tags=["Metrics"])  # Already has /api prefix in router


# =============================================================================
# ROOT ENDPOINT
# =============================================================================

@app.get("/")
async def root():
    """API root - health check"""
    return {
        "name": "SixBTC Control Center API",
        "version": "1.0.0",
        "status": "running",
        "uptime_seconds": get_uptime_seconds(),
    }


# =============================================================================
# WEBSOCKET
# =============================================================================

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.

    Messages sent:
    - {"type": "status", "data": {...}} - System status updates
    - {"type": "trade", "data": {...}} - New trade events
    - {"type": "position", "data": {...}} - Position updates
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            # Echo or handle client messages if needed
            await websocket.send_json({"type": "pong", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def run():
    """Run the API server"""
    import uvicorn

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8080"))

    logger.info(f"Starting API server on {host}:{port}")

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()
