"""
CLI: re-fetch portal listing pages and fix wrong prices in ``listings`` + ``listings_raw``.

  cd backend && set PYTHONPATH=. && python scripts/refetch_listing_prices.py

Optional env (same as app): DATABASE_URL, etc.
"""

from __future__ import annotations

import os
import sys

# Run from repo root or backend/
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.database import SessionLocal  # noqa: E402
from app.services.listing_price_refetch import refetch_suspicious_listing_prices  # noqa: E402


def main() -> None:
    limit = int(os.environ.get("REFETCH_LIMIT", "300"))
    delay = float(os.environ.get("REFETCH_DELAY", "0.7"))
    suspicious = os.environ.get("REFETCH_SUSPICIOUS_ONLY", "1").strip() not in ("0", "false", "no")
    src = os.environ.get("REFETCH_SOURCE", "imovirtual").strip() or None

    db = SessionLocal()
    try:
        stats = refetch_suspicious_listing_prices(
            db,
            limit=limit,
            delay_seconds=delay,
            suspicious_only=suspicious,
            source_name_contains=src,
        )
        db.commit()
        print(stats)
    finally:
        db.close()


if __name__ == "__main__":
    main()
