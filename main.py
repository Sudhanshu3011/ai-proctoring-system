
"""
main.py  — FINAL
FastAPI application entry point — all routers registered.

Run:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors    import CORSMiddleware
from fastapi.responses          import JSONResponse
from fastapi.exceptions         import RequestValidationError

from core.config         import settings
from core.logging_config import setup_logging
from db.session          import init_db, close_db

# ── Routers ───────────────────────────────────────────────────────
from api.v1.auth       import router as auth_router
from api.v1.exam       import router as exam_router
from api.v1.monitoring import router as monitoring_router, ws_router
from api.v1.reports    import router as reports_router
from api.v1.admin      import router as admin_router, admin_ws_router


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Lifespan
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs setup before the app starts accepting requests,
    and teardown when the app shuts down.
    """
    setup_logging()
    settings.create_dirs()
    init_db()
    logger.info(
        f"{settings.APP_NAME} started | "
        f"env={settings.APP_ENV} | "
        f"http://{settings.APP_HOST}:{settings.APP_PORT}"
    )
    yield
    close_db()
    logger.info(f"{settings.APP_NAME} shut down.")


# ─────────────────────────────────────────────
#  App
# ─────────────────────────────────────────────
app = FastAPI(
    title       = settings.APP_NAME,
    description = "AI-Based Intelligent Online Exam Proctoring System",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
    debug       = settings.APP_DEBUG,
    lifespan    = lifespan,
)


# ─────────────────────────────────────────────
#  Middleware
# ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.cors_origins,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"← {response.status_code} {request.url.path}")
    return response


# ─────────────────────────────────────────────
#  Exception handlers
# ─────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(l) for l in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation failed", "errors": errors},
    )

@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ─────────────────────────────────────────────
#  Routers
# ─────────────────────────────────────────────
API = "/api/v1"

app.include_router(auth_router,       prefix=API)
app.include_router(exam_router,       prefix=API)
app.include_router(monitoring_router, prefix=API)
app.include_router(reports_router,    prefix=API)
app.include_router(admin_router,      prefix=API)

# WebSocket routers — NO prefix (WS URLs must be exact)
app.include_router(ws_router)        # /ws/monitor/{session_id}
app.include_router(admin_ws_router)  # /ws/admin/live


# ─────────────────────────────────────────────
#  Health check
# ─────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health():
    return {
        "status" : "ok",
        "app"    : settings.APP_NAME,
        "env"    : settings.APP_ENV,
        "version": "1.0.0",
    }

@app.get("/", tags=["Health"])
def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs"   : "/docs",
        "health" : "/health",
    }