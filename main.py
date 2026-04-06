"""
FingerPay — Main Entry Point
=============================
FastAPI app for fingerprint-based payments.
"""

import os
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from pipeline.database import init_db
from routes.enroll import router as enroll_router
from routes.authenticate import router as authenticate_router
from routes.pay import router as pay_router
from routes.merchants import router as merchants_router

# ── Logging (no sensitive data) ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("fingerpay")

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield

app = FastAPI(title="FingerPay", version="1.0.0", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Upload size limit — 5MB max
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    if request.method == "POST":
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=413, content={"detail": "File too large. Max 5MB."})
    return await call_next(request)


# ── Request logging (no sensitive data) ───────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} → {response.status_code}")
    return response


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Register routes
app.include_router(enroll_router)
app.include_router(authenticate_router)
app.include_router(pay_router)
app.include_router(merchants_router)


@app.get("/config")
def get_config():
    """Returns public config for the frontend (Stripe publishable key)."""
    return {"publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY")}


@app.get("/kiosk")
def kiosk():
    return RedirectResponse(url="/static/kiosk.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
