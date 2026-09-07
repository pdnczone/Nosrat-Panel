"""FastAPI application factory & entry point for the nosrat WebUI backend."""
from __future__ import annotations

import logging
import logging.config
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api import auth, crypto, health, nodes, plugins, servers, settings as settings_api
from api import speed, tunnels, users, ws
from core.config import ensure_directories, settings
from core.database import init_db
from core.plugin_loader import plugin_registry
from db.migrations import run_migrations
from db.schemas import ErrorResponse, HealthInfo


# ── Logging configuration ──────────────────────────────────────────────────


def _configure_logging() -> None:
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handlers: dict[str, dict[str, object]] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": settings.log_level,
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": str(log_path),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "level": settings.log_level,
        },
    }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                }
            },
            "handlers": handlers,
            "root": {"handlers": list(handlers.keys()), "level": settings.log_level},
            "loggers": {
                "uvicorn.error": {"level": settings.log_level},
                "uvicorn.access": {"level": "INFO", "propagate": True},
            },
        }
    )


_configure_logging()
logger = logging.getLogger("nosrat.app")


# ── Lifespan ───────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialise the database, plugins and bootstrap admin user."""
    ensure_directories()
    logger.info("starting %s v%s (env=%s)", settings.app_name, settings.app_version, settings.environment)

    init_db()
    run_migrations()
    plugin_registry.load()
    logger.info("loaded %d plugin(s)", len(plugin_registry.list()))

    yield

    logger.info("shutting down")


# ── App factory ────────────────────────────────────────────────────────────


_STARTED_AT = time.monotonic()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── Middleware ───────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _request_timing(request: Request, call_next):  # type: ignore[no-untyped-def]
        started = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - started) * 1000.0
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
        if settings.debug:
            logger.debug(
                "%s %s -> %s in %.2fms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        return response

    # ── Exception handlers ──────────────────────────────────────────────
    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:  # type: ignore[no-untyped-def]
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=str(exc.detail),
                code=f"http_{exc.status_code}",
                details=getattr(exc, "headers", None) and {"headers": dict(exc.headers)},
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:  # type: ignore[no-untyped-def]
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="validation error",
                code="validation_error",
                details={"errors": exc.errors()},
            ).model_dump(),
        )

    # ── Routers ─────────────────────────────────────────────────────────
    _mount_routers(app)

    # ── Root + health endpoints ──────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def _root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/api/health/live",
        }

    @app.get("/api/health/info", response_model=HealthInfo)
    async def _info() -> HealthInfo:
        return HealthInfo(
            status="ok",
            version=settings.app_version,
            uptime_seconds=round(time.monotonic() - _STARTED_AT, 2),
            database=settings.db_url.split("://", 1)[0],
            environment=settings.environment,
        )

    return app


def _mount_routers(app: FastAPI) -> None:
    routers = [
        auth.router,
        crypto.router,
        health.router,
        nodes.router,
        plugins.router,
        servers.router,
        settings_api.router,
        speed.router,
        tunnels.router,
        users.router,
        ws.router,
    ]
    for r in routers:
        app.include_router(r)
    logger.info("mounted %d router(s)", len(routers))


# ── Module-level ASGI app for ``uvicorn app:app`` ───────────────────────────

app = create_app()


def main() -> None:
    """Run with ``python -m app`` or ``python app.py``."""
    import uvicorn

    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers if not settings.reload else 1,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()