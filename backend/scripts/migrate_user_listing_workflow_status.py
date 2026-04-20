"""Add user_listing_state.workflow_status (Part 3 workflow). Run from backend/: PYTHONPATH=. python scripts/migrate_user_listing_workflow_status.py"""

from sqlalchemy import text

from app.database import SessionLocal


def main() -> None:
    stmts = [
        "alter table public.user_listing_state add column if not exists workflow_status text",
        "alter table public.user_listing_state drop constraint if exists user_listing_state_workflow_chk",
        """alter table public.user_listing_state add constraint user_listing_state_workflow_chk check (
            workflow_status is null
            or workflow_status in (
              'new', 'seen', 'favourite', 'need_to_call', 'viewing_arranged',
              'offer_made', 'not_available', 'not_interested'
            )
        )""",
        """update public.user_listing_state set workflow_status = case
            when coalesce(is_hidden, false) then 'not_interested'
            when coalesce(is_saved, false) then 'favourite'
            when coalesce(is_seen, false) then 'seen'
            else 'new'
          end
          where workflow_status is null""",
    ]
    db = SessionLocal()
    try:
        for s in stmts:
            db.execute(text(s))
        db.commit()
        print("user_listing_state.workflow_status migration OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
