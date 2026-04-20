-- Supabase may still have the OLD denormalized listing_groups shape (title, canonical_url, … NOT NULL).
-- The app creates "cluster-only" rows with only group_status / confidence_score / timestamps.
-- Relax NOT NULL on legacy columns so ORM inserts succeed; listing detail lives in `listings`.

alter table public.listing_groups alter column title drop not null;
alter table public.listing_groups alter column canonical_url drop not null;
alter table public.listing_groups alter column fuzzy_signature drop not null;
alter table public.listing_groups alter column first_seen_at drop not null;
alter table public.listing_groups alter column last_seen_at drop not null;
