"""Import Idealista dataset from a URL. Run from backend/: PYTHONPATH=. python scripts/import_idealista_csv.py <URL>"""

import sys

from app.database import SessionLocal
from app.services.idealista_csv_import import import_idealista_csv_from_url


def main() -> None:
    url = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not url:
        print("Usage: PYTHONPATH=. python scripts/import_idealista_csv.py <URL>", file=sys.stderr)
        sys.exit(1)
    db = SessionLocal()
    try:
        out = import_idealista_csv_from_url(db, url)
        print(out.get("message", out))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
