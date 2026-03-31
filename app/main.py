from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import AppError
from app.core.logging_config import configure_logging
from app.db import Base, engine
from app.routers import box, message, monitoring

configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI):
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


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
