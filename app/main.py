from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import AppError
from app.core.logging_config import configure_logging
from app.core.metrics import MetricsRegistry
from app.core.rate_limit import InMemoryRateLimiter
from app.db import Base, engine
from app.routers import box, message, monitoring

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_alembic_migrations() -> None:
    """
    Ensure DB schema is compatible with current ORM models.
    On serverless, deploys can update code before migrations are applied; this avoids 500s like
    "UndefinedColumn" on production.
    """
    cfg = AlembicConfig(str(_PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("prepend_sys_path", ".")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.getenv("RUN_MIGRATIONS_ON_STARTUP", "1").strip().lower() not in {"0", "false", "no"}:
        try:
            _run_alembic_migrations()
            logger.info("alembic_migrations_applied")
        except Exception:
            # Do not crash the app on migration errors; logs will show the root cause.
            logger.exception("alembic_migrations_failed")

    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


_docs_url = "/docs" if settings.docs_enabled else None
_redoc_url = "/redoc" if settings.docs_enabled else None

app = FastAPI(
    title="LovePod API",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)
app.state.metrics = MetricsRegistry()
app.state.rate_limiter = InMemoryRateLimiter(
    limit=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

_origins = settings.cors_origin_list()
_allow_credentials = "*" not in _origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

_hosts = settings.trusted_host_list()
if _hosts is not None:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)

app.include_router(box.router, prefix=settings.api_prefix)
app.include_router(message.router, prefix=settings.api_prefix)
app.include_router(monitoring.router, prefix=settings.api_prefix)


def _get_client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    client_ip = _get_client_ip(request)
    path = request.url.path

    if settings.rate_limit_enabled and path.startswith(settings.api_prefix):
        if not path.startswith(f"{settings.api_prefix}/v1/monitoring"):
            allowed, retry_after = request.app.state.rate_limiter.check(client_ip)
            if not allowed:
                request.app.state.metrics.incr("rate_limited_total")
                response = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
                response.headers["Retry-After"] = str(retry_after)
                response.headers["X-Request-ID"] = request_id
                return response

    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (perf_counter() - started) * 1000
        request.app.state.metrics.record_request(
            method=request.method,
            path=path,
            status_code=500,
            duration_ms=duration_ms,
        )
        logger.exception(
            "request_failed request_id=%s method=%s path=%s client_ip=%s duration_ms=%.2f",
            request_id,
            request.method,
            path,
            client_ip,
            duration_ms,
        )
        raise

    duration_ms = (perf_counter() - started) * 1000
    request.app.state.metrics.record_request(
        method=request.method,
        path=path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    if settings.security_headers_enabled:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s client_ip=%s duration_ms=%.2f",
        request_id,
        request.method,
        path,
        response.status_code,
        client_ip,
        duration_ms,
    )
    return response


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
