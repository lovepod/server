"""Run API with Uvicorn: `python -m app` from the `api` directory."""

from __future__ import annotations

import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.uvicorn_host,
        port=settings.uvicorn_port,
        reload=settings.app_env == "development",
    )
