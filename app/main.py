"""
FingerPay — Application Factory
==================================
FastAPI app creation, middleware, and lifespan.
"""

import logging
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import STRIPE_PUBLISHABLE_KEY, validate_env
from app.db import init_db
from app.routes import register_routes

# ── Structured logging ──────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = structlog.get_logger("fingerpay")

# ── Rate limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import os

    validate_env()
    init_db()

    # Warn if someone tries to run multiple workers (POS state is in-memory)
    workers = os.environ.get("WEB_CONCURRENCY", "1")
    if workers != "1":
        logger.warning(
            "WEB_CONCURRENCY=%s but POS WebSocket state is in-memory. "
            "Only 1 worker is supported. See ADR-0005.",
            workers,
        )

    # Run initial cleanup on startup
    from app.services.cleanup import run_all_cleanups

    run_all_cleanups()

    logger.info("FingerPay started")
    yield

    # Log any in-flight POS transactions on shutdown
    from app.routes.pos import manager

    pending = {k: v for k, v in manager.transactions.items() if v.get("status") == "pending"}
    if pending:
        logger.warning(
            "Shutting down with %d pending POS transactions: %s", len(pending), list(pending.keys())
        )
    connected = list(manager.terminals.keys())
    if connected:
        logger.info("Disconnecting %d terminals: merchant_ids=%s", len(connected), connected)


app = FastAPI(title="FingerPay", version="0.1.0", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Upload size limit — 5 MB max
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    """Reject oversized uploads. Checks Content-Length header when present.
    For chunked uploads without Content-Length, enforcement relies on the
    reverse proxy (Render / nginx client_max_body_size). Individual route
    handlers should also validate file size after reading."""
    if request.method in ("POST", "PUT", "PATCH"):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_UPLOAD_BYTES:
                    return JSONResponse(
                        status_code=413, content={"detail": "File too large. Max 5MB."}
                    )
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length."})
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://js.stripe.com https://cdnjs.cloudflare.com 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "frame-src https://js.stripe.com; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    return response


@app.middleware("http")
async def request_id_and_log(request: Request, call_next):
    """Assign a request ID, bind it to structlog context, log the request, and
    return the ID in a response header for traceability."""
    request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
    )
    return response


# ── Static files ─────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Routes ───────────────────────────────────────────────────────────────────
register_routes(app)


# ── Health ───────────────────────────────────────────────────────────────────


@app.get("/healthz")
def healthz():
    """Liveness probe. Process is up."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    """Readiness probe. Process is up and DB is reachable."""
    try:
        from app.db.connection import _get_conn

        with _get_conn() as conn:
            conn.cursor().execute("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": str(e)})


# ── Top-level redirects ──────────────────────────────────────────────────────


@app.get("/")
def home():
    return RedirectResponse(url="/static/index.html")


@app.get("/config")
def get_config():
    """Returns public config for the frontend (Stripe publishable key)."""
    return {"publishable_key": STRIPE_PUBLISHABLE_KEY}


@app.get("/kiosk")
def kiosk():
    return RedirectResponse(url="/static/kiosk.html")


@app.get("/business")
def merchant_signup():
    return RedirectResponse(url="/static/merchant-signup.html")


@app.get("/business/login")
def merchant_login():
    return RedirectResponse(url="/static/merchant-login.html")


@app.get("/business/dashboard")
def merchant_dashboard():
    return RedirectResponse(url="/static/merchant-dashboard.html")


@app.get("/business/reset-password")
def merchant_reset_password(token: str = None):
    if token:
        return RedirectResponse(url=f"/static/merchant-reset-password.html?token={token}")
    return RedirectResponse(url="/static/merchant-reset-password.html")


@app.get("/my-account")
def customer_portal():
    return RedirectResponse(url="/static/customer-portal.html")
