from contextlib import asynccontextmanager
from time import monotonic
from uuid import UUID, uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from structlog.contextvars import bind_contextvars, clear_contextvars

from fab_identity.api.routes import router
from fab_identity.config import get_settings
from fab_identity.domain.errors import DomainError
from fab_identity.infrastructure.database import engine
from fab_identity.logging import configure_logging


configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("service_started", environment=get_settings().environment)
    yield
    engine.dispose()
    logger.info("service_stopped")


app = FastAPI(title="Fab Wafer Identity Service", version="0.1.0", lifespan=lifespan)
app.include_router(router)


def _request_id(value: str | None) -> str:
    if value is None:
        return str(uuid4())
    try:
        return str(UUID(value))
    except ValueError:
        return str(uuid4())


@app.middleware("http")
async def request_context(request: Request, call_next):
    settings = get_settings()
    request_id = _request_id(request.headers.get(settings.request_id_header))
    clear_contextvars()
    bind_contextvars(request_id=request_id, method=request.method, path=request.url.path)
    started = monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed", duration_ms=round((monotonic() - started) * 1000, 2))
        raise
    response.headers[settings.request_id_header] = request_id
    logger.info(
        "request_completed",
        status_code=response.status_code,
        duration_ms=round((monotonic() - started) * 1000, 2),
    )
    clear_contextvars()
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}

