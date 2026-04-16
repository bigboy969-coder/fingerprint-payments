"""
FingerPay — POS Integration Routes
=====================================
WebSocket /ws/terminal      - kiosk tablet connects here and listens for payment requests
POST      /pos/charge       - POS calls this to send a payment request to the tablet
GET       /pos/status/{id}  - POS polls this to check if payment completed
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.routes.deps import verify_merchant_api_key

router = APIRouter()


# ── Connection Manager ────────────────────────────────────────────────────────


class TerminalManager:
    def __init__(self):
        self.terminals: dict[int, WebSocket] = {}
        self.transactions: dict[str, dict] = {}

    async def connect(self, merchant_id: int, ws: WebSocket):
        await ws.accept()
        self.terminals[merchant_id] = ws

    def disconnect(self, merchant_id: int):
        self.terminals.pop(merchant_id, None)

    def is_connected(self, merchant_id: int) -> bool:
        return merchant_id in self.terminals

    async def send_payment_request(self, merchant_id: int, amount: float, transaction_id: str):
        ws = self.terminals.get(merchant_id)
        if not ws:
            raise ValueError("Terminal is not connected.")
        await ws.send_json(
            {
                "type": "payment_request",
                "amount": amount,
                "transaction_id": transaction_id,
            }
        )

    async def send_to_terminal(self, merchant_id: int, message: dict):
        ws = self.terminals.get(merchant_id)
        if ws:
            await ws.send_json(message)

    def record_transaction(self, transaction_id: str, status: str, data: dict = None):
        self.transactions[transaction_id] = {
            "status": status,
            "data": data or {},
            "updated_at": datetime.now(UTC).isoformat(),
        }

    def get_transaction(self, transaction_id: str) -> dict | None:
        return self.transactions.get(transaction_id)


manager = TerminalManager()


# ── WebSocket — Kiosk connects here ──────────────────────────────────────────


@router.websocket("/ws/terminal")
async def terminal_websocket(ws: WebSocket):
    """
    Kiosk tablet connects here on startup.
    Auth via first message: client sends {"type":"auth","api_key":"..."} within
    5 seconds, or the connection is closed. API key is NOT in the URL.
    """
    await ws.accept()

    # Wait for auth message (5-second timeout via receive_json)
    import asyncio

    try:
        data = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
    except (TimeoutError, Exception):
        await ws.close(code=4001, reason="Auth timeout")
        return

    if data.get("type") != "auth" or not data.get("api_key"):
        await ws.close(code=4001, reason="Missing auth message")
        return

    try:
        merchant = verify_merchant_api_key(data["api_key"])
    except ValueError:
        await ws.close(code=4001, reason="Invalid API key")
        return

    merchant_id = merchant["id"]
    manager.terminals[merchant_id] = ws
    await ws.send_json({"type": "auth_ok"})

    try:
        while True:
            msg = await ws.receive_json()

            if msg.get("type") == "payment_complete":
                tx_id = msg.get("transaction_id")
                if tx_id:
                    manager.record_transaction(tx_id, "success", msg)

            elif msg.get("type") == "payment_failed":
                tx_id = msg.get("transaction_id")
                if tx_id:
                    manager.record_transaction(tx_id, "failed", msg)

            elif msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(merchant_id)


# ── POST /pos/charge ─────────────────────────────────────────────────────────


class POSChargeRequest(BaseModel):
    api_key: str
    amount: float
    description: str = ""


@router.post("/pos/charge")
async def pos_charge(body: POSChargeRequest):
    try:
        merchant = verify_merchant_api_key(body.api_key)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    if not manager.is_connected(merchant["id"]):
        raise HTTPException(
            status_code=503, detail="Terminal is not connected. Make sure the kiosk is open."
        )

    transaction_id = str(uuid.uuid4())
    manager.record_transaction(transaction_id, "pending")

    try:
        await manager.send_payment_request(
            merchant_id=merchant["id"],
            amount=body.amount,
            transaction_id=transaction_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "success": True,
        "transaction_id": transaction_id,
        "message": "Payment request sent to terminal.",
    }


# ── GET /pos/status/{id} ─────────────────────────────────────────────────────


@router.get("/pos/status/{transaction_id}")
async def pos_status(transaction_id: str):
    tx = manager.get_transaction(transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return tx


# ── GET /pos/terminal/status ─────────────────────────────────────────────────


@router.get("/pos/terminal/status")
async def terminal_status(api_key: str):
    try:
        merchant = verify_merchant_api_key(api_key)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    return {"connected": manager.is_connected(merchant["id"])}
