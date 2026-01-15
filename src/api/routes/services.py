"""
Services API routes (Supervisor integration)

GET /api/services - Get all services status
POST /api/services/{name}/start - Start a service
POST /api/services/{name}/stop - Stop a service
POST /api/services/{name}/restart - Restart a service
"""
import subprocess
from typing import List

from fastapi import APIRouter, HTTPException

from src.api.schemas import ServiceControlResponse, ServiceInfo
from src.api.routes.status import get_supervisor_status
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


# List of valid service names
VALID_SERVICES = [
    "generator",
    "backtester",
    "validator",
    "executor",
    "monitor",
    "scheduler",
    "data",
    "api",
]


def run_supervisorctl(command: str, service: str = None) -> tuple[bool, str]:
    """
    Run a supervisorctl command.

    Args:
        command: The command (start, stop, restart)
        service: The service name (optional)

    Returns:
        (success, message)
    """
    try:
        if service:
            cmd = ["supervisorctl", command, service]
        else:
            cmd = ["supervisorctl", command]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return True, result.stdout.strip() or f"Service {service} {command} successful"
        else:
            return False, result.stderr.strip() or f"Failed to {command} {service}"

    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        return False, "supervisorctl not found"
    except Exception as e:
        return False, str(e)


@router.get("/services", response_model=List[ServiceInfo])
async def list_services():
    """
    Get status of all supervisor-managed services.
    """
    return get_supervisor_status()


@router.post("/services/{service_name}/start", response_model=ServiceControlResponse)
async def start_service(service_name: str):
    """
    Start a specific service.
    """
    if service_name not in VALID_SERVICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service name. Valid services: {', '.join(VALID_SERVICES)}"
        )

    logger.info(f"Starting service: {service_name}")
    success, message = run_supervisorctl("start", service_name)

    return ServiceControlResponse(
        success=success,
        message=message,
        service=service_name,
        action="start",
    )


@router.post("/services/{service_name}/stop", response_model=ServiceControlResponse)
async def stop_service(service_name: str):
    """
    Stop a specific service.
    """
    if service_name not in VALID_SERVICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service name. Valid services: {', '.join(VALID_SERVICES)}"
        )

    logger.info(f"Stopping service: {service_name}")
    success, message = run_supervisorctl("stop", service_name)

    return ServiceControlResponse(
        success=success,
        message=message,
        service=service_name,
        action="stop",
    )


@router.post("/services/{service_name}/restart", response_model=ServiceControlResponse)
async def restart_service(service_name: str):
    """
    Restart a specific service.
    """
    if service_name not in VALID_SERVICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service name. Valid services: {', '.join(VALID_SERVICES)}"
        )

    logger.info(f"Restarting service: {service_name}")
    success, message = run_supervisorctl("restart", service_name)

    return ServiceControlResponse(
        success=success,
        message=message,
        service=service_name,
        action="restart",
    )


