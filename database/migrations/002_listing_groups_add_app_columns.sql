-- Align legacy `listing_groups` (denormalized rows with title/price/...) with the app ORM.
-- Adds columns the FastAPI models expect. Legacy extra columns may remain.
-- Run in Supabase SQL editor or: psql $DATABASE_URL -f 002_listing_groups_add_app_columns.sql
-- Optional: python scripts/migrate_listing_groups_columns.py (from backend/, PYTHONPATH=. )

alter table public.listing_groups
  add column if not exists group_status text not null default 'active',
  add column if not exists confidence_score numeric(5,2),
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

-- If your table still has first_seen_at / last_seen_at (legacy), run:
-- update public.listing_groups set created_at = coalesce(first_seen_at, created_at);
-- update public.listing_groups set updated_at = coalesce(last_seen_at, last_changed_at, updated_at);
