from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import check_database_connection

router = APIRouter(prefix="/v1/monitoring", tags=["monitoring"])


@router.get("/heartbeat")
def heartbeat() -> str:
    return "Hearts Still Beating"


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> JSONResponse:
    ok, detail = check_database_connection()
    status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if ok else "degraded", "database": detail},
    )


@router.get("/metrics")
def metrics(request: Request) -> dict[str, object]:
    registry = request.app.state.metrics
    return registry.snapshot()


@router.get("/info")
def info(request: Request) -> dict[str, object]:
    snapshot = request.app.state.metrics.snapshot()
    return {
        "status": "ok",
        "app": request.app.title,
        "environment": settings.app_env,
        "observability": {
            "request_ids": True,
            "request_logging": True,
            "rate_limiting_metrics": True,
            "in_memory_metrics": True,
        },
        "process": {
            "started_at_unix": snapshot["started_at_unix"],
            "uptime_seconds": snapshot["uptime_seconds"],
        },
    }
