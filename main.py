"""
FingerPay — Main Entry Point
=============================
FastAPI app for fingerprint-based payments.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from pipeline.database import init_db
from routes.enroll import router as enroll_router
from routes.authenticate import router as authenticate_router
from routes.pay import router as pay_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield

app = FastAPI(title="FingerPay", version="1.0.0", lifespan=lifespan)

# Register routes
app.include_router(enroll_router)
app.include_router(authenticate_router)
app.include_router(pay_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
