import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import api_v1_router
from app.rate_limit import limiter

logger = logging.getLogger(__name__)

if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        traces_sample_rate=0.1,
        environment=os.getenv("SPELIX_ENV", "development"),
    )


@asynccontextmanager
async def fastapi_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Enter the streaq worker's async context on startup so enqueue works.

    streaq 6.4.0 requires `async with worker:` before any `task.enqueue(...)`
    call — the underlying `worker.lib` (Redis publisher) is only constructed
    inside `__aenter__`. Without this, every `process_analysis.enqueue(...)`
    in an API request raises `StreaqError: Worker not initialized`.

    The worker container runs the Worker via `streaq run ...` which enters
    the context for the lifetime of the process. The FastAPI web process
    does the same here. Both share the same `Worker` instance defined in
    `app/workers/streaq_worker.py`, so task names and queue config match.

    The worker's own lifespan (`app.workers.streaq_worker.lifespan`) reads
    `SPELIX_WEB_PROCESS` and suppresses the heartbeat loop when True — so
    entering the context from FastAPI doesn't duplicate heartbeat writes
    and mask a dead worker container.
    """
    if os.environ.get("REDIS_URL"):
        try:
            from app.workers.streaq_worker import worker as streaq_worker

            async with streaq_worker:
                logger.info(
                    "FastAPI lifespan: entered streaq worker context (enqueue ready)"
                )
                yield
        except Exception:
            logger.exception(
                "FastAPI lifespan: failed to enter streaq worker context — "
                "enqueue will raise; web app continues without queue"
            )
            yield
    else:
        logger.info(
            "FastAPI lifespan: REDIS_URL unset — skipping streaq context"
        )
        yield


app = FastAPI(
    title="Spelix API",
    version="0.1.0",
    redirect_slashes=False,
    lifespan=fastapi_lifespan,
)

# Rate limiting (NFR-SECU-10)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# CORS per NFR-SECU-11: explicit origins only, no wildcard in production
_allowed_origins: list[str] = [
    "https://spelix.app",
    "https://www.spelix.app",
]

# Development origins
if os.getenv("SPELIX_ENV", "production") == "development":
    _allowed_origins += [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

# Vercel preview deployments
_vercel_preview = os.getenv("VERCEL_PREVIEW_ORIGIN")
if _vercel_preview:
    _allowed_origins.append(_vercel_preview)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Upload-Offset",
        "Tus-Resumable",
        "Upload-Length",
    ],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch any non-``HTTPException`` raised inside a route.

    Without this, an unhandled exception escapes ``ExceptionMiddleware`` and
    is caught by Starlette's outer ``ServerErrorMiddleware``, which emits a
    plain-text ``Internal Server Error`` response that bypasses CORS. The
    browser then sees a misleading "CORS policy" error and the real bug
    stays invisible — exactly the failure mode that hid the dormant
    ``StorageService`` bug for the entire existence of Phase 0 + Phase 1.

    Returns a JSON envelope matching the Spelix error contract.
    ``detail`` is intentionally ``None`` — exception type and message are
    NOT sent to the client because they can contain SQL errors, file paths,
    or connection strings (M-01 security fix). Full details, including
    tracebacks, go to ``logger.exception`` (server logs) only.

    Explicitly attaches CORS headers when the request origin is in the
    allow-list so the response actually reaches the browser.
    """
    logger.exception(
        "Unhandled exception in route %s %s", request.method, request.url.path
    )

    headers: dict[str, str] = {}
    origin = request.headers.get("origin")
    if origin and origin in _allowed_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again.",
                "detail": None,
            }
        },
        headers=headers,
    )


app.include_router(api_v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
