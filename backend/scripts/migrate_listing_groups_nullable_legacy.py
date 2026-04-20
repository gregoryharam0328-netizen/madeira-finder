"""Relax NOT NULL on legacy listing_groups columns (hybrid Supabase schema). Run from backend/ with PYTHONPATH=."""

from sqlalchemy import text

from app.database import SessionLocal


def main() -> None:
    stmts = [
        "alter table public.listing_groups alter column title drop not null",
        "alter table public.listing_groups alter column canonical_url drop not null",
        "alter table public.listing_groups alter column fuzzy_signature drop not null",
        "alter table public.listing_groups alter column first_seen_at drop not null",
        "alter table public.listing_groups alter column last_seen_at drop not null",
    ]
    db = SessionLocal()
    try:
        for s in stmts:
            db.execute(text(s))
        db.commit()
        print("listing_groups legacy columns nullable OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
