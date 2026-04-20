"""One-off: add ORM columns to legacy listing_groups on Postgres. Run from backend/: python scripts/migrate_listing_groups_columns.py"""

from sqlalchemy import text

from app.database import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                alter table public.listing_groups
                  add column if not exists group_status text not null default 'active',
                  add column if not exists confidence_score numeric(5,2),
                  add column if not exists created_at timestamptz not null default now(),
                  add column if not exists updated_at timestamptz not null default now();
                """
            )
        )
        db.commit()
        r = db.execute(
            text(
                """
                select count(*) from information_schema.columns
                where table_schema = 'public' and table_name = 'listing_groups'
                  and column_name = 'first_seen_at';
                """
            )
        ).scalar()
        if r:
            db.execute(
                text(
                    "update public.listing_groups set created_at = coalesce(first_seen_at, created_at);"
                )
            )
            db.commit()
        r2 = db.execute(
            text(
                """
                select count(*) from information_schema.columns
                where table_schema = 'public' and table_name = 'listing_groups'
                  and column_name = 'last_seen_at';
                """
            )
        ).scalar()
        if r2:
            db.execute(
                text(
                    "update public.listing_groups set updated_at = coalesce(last_seen_at, last_changed_at, updated_at);"
                )
            )
            db.commit()
        print("listing_groups columns OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
