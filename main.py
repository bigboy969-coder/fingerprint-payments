"""
FingerPay — Entry Point
=========================
Thin wrapper so `uvicorn main:app` continues to work.
All logic lives in the app/ package.
"""

from app.main import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
