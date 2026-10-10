"""JLMIRROR FastAPI application entry point.

Implements the modular monolith API (ADR-001) with a versioned HTTP API
(ADR-007). Each bounded context exposes its own router under ``app/routers/``.
Tenant isolation is enforced via RLS (ADR-003) and the middleware in
``app/context.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on the path so domain primitives are importable.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import close_pool, get_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the DB pool on startup.
    get_pool()
    yield
    # Clean up on shutdown.
    close_pool()


app = FastAPI(
    title="JLMIRROR API",
    description=(
        "Enterprise-grade multi-tenant platform for infrastructure monitoring, "
        "operational intelligence, IT service management, automation, governance, "
        "and extensible integrations."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Liveness probe — does not check database connectivity."""
    return {"status": "ok", "environment": settings.environment_class}


@app.get("/health/ready", tags=["system"])
async def health_ready() -> dict[str, str]:
    """Readiness probe — checks database connectivity."""
    try:
        pool = get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database not ready: {exc}",
        ) from exc


# Register domain routers.
from app.routers import authority, async_ops, monitoring, observability, release  # noqa: E402

app.include_router(authority.router, prefix="/api/v1", tags=["authority"])
app.include_router(monitoring.router, prefix="/api/v1", tags=["monitoring"])
app.include_router(async_ops.router, prefix="/api/v1", tags=["async"])
app.include_router(observability.router, prefix="/api/v1", tags=["observability"])
app.include_router(release.router, prefix="/api/v1", tags=["release"])


def run() -> None:
    """Entry point for the ``jlmirror-api`` console script."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
