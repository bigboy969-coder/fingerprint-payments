"""
FingerPay — Route Registry
============================
Central place to import all routers. main.py calls register_routes(app).
"""

from fastapi import FastAPI

from app.routes.authenticate import router as authenticate_router
from app.routes.customers import router as customers_router
from app.routes.enroll import router as enroll_router
from app.routes.merchants import router as merchants_router
from app.routes.pay import router as pay_router
from app.routes.pos import router as pos_router
from app.routes.pos_auth import router as pos_auth_router
from app.routes.webhooks import router as webhooks_router


def register_routes(app: FastAPI) -> None:
    app.include_router(enroll_router)
    app.include_router(authenticate_router)
    app.include_router(pay_router)
    app.include_router(merchants_router)
    app.include_router(pos_router)
    app.include_router(pos_auth_router)
    app.include_router(customers_router)
    app.include_router(webhooks_router)
