"""
main.py

FastAPI application entry point.

Wires together:
  - Logging setup
  - Database init
  - All API routers
  - Middleware (CORS, logging)

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Interactive API docs available at:
    http://localhost:8000/docs      (Swagger UI)
    http://localhost:8000/redoc     (ReDoc)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from core.config         import settings
from core.logging_config import setup_logging
from db.session          import init_db, close_db
from api.v1.auth         import router as auth_router
from api.v1.monitoring import router as monitoring_router, ws_router

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Lifespan — startup and shutdown
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs setup before the app starts accepting requests,
    and teardown when the app shuts down.
    """
    # ── STARTUP ──────────────────────────────
    setup_logging()
    settings.create_dirs()    # create storage/, logs/ directories
    init_db()                 # create DB tables if they don't exist
    logger.info(
        f"{settings.APP_NAME} started | "
        f"env={settings.APP_ENV} | "
        f"http://{settings.APP_HOST}:{settings.APP_PORT}"
    )
    yield   # app is now running and serving requests

    # ── SHUTDOWN ─────────────────────────────
    close_db()
    logger.info(f"{settings.APP_NAME} shutting down.")


# ─────────────────────────────────────────────
#  Create FastAPI app
# ─────────────────────────────────────────────
app = FastAPI(
    title       = settings.APP_NAME,
    description = "AI-Based Intelligent Online Exam Proctoring System — REST API",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
    debug       = settings.APP_DEBUG,
    lifespan    = lifespan,
)


# ─────────────────────────────────────────────
#  Middleware
# ─────────────────────────────────────────────

# CORS — allow frontend (React on :3000) to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.cors_origins,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# Request/response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every incoming request and its response status."""
    logger.info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"← {response.status_code} {request.url.path}")
    return response


# ─────────────────────────────────────────────
#  Exception handlers
# ─────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """
    Returns clean 422 errors instead of FastAPI's default verbose format.
    Easier for the frontend to parse.
    """
    errors = [
        {"field": ".".join(str(l) for l in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
        content     = {"detail": "Validation failed", "errors": errors},
    )


@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — never expose stack traces."""
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
        content     = {"detail": "Internal server error"},
    )


# ─────────────────────────────────────────────
#  Routers  (add more here in Phase 2)
# ─────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth_router, prefix=API_PREFIX)

from api.v1.exam       import router as exam_router
from api.v1.monitoring import router as monitoring_router
# from api.v1.violations import router as violations_router
# from api.v1.reports    import router as reports_router
# from api.v1.admin      import router as admin_router
app.include_router(exam_router,       prefix=API_PREFIX)
app.include_router(monitoring_router, prefix=API_PREFIX)
app.include_router(ws_router)                              # NO prefix — WS is at /ws/monitor/{id}
# app.include_router(violations_router, prefix=API_PREFIX)
# app.include_router(reports_router,    prefix=API_PREFIX)
# app.include_router(admin_router,      prefix=API_PREFIX)


# ─────────────────────────────────────────────
#  Health check
# ─────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    """Quick liveness check — used by Docker/Kubernetes health probes."""
    return {
        "status":  "ok",
        "app":     settings.APP_NAME,
        "env":     settings.APP_ENV,
        "version": "1.0.0",
    }


@app.get("/", tags=["Health"])
def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs":    "/docs",
        "health":  "/health",
    }
