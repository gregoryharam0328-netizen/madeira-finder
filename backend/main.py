"""Shim so `uvicorn main:app` works from the `backend/` directory."""
from app.main import app

__all__ = ["app"]
