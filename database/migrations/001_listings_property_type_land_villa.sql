-- PostgreSQL: extend property_type check for villa + land (Kyero plots, etc.).
-- Run once on existing DBs created from an older schema.sql.
ALTER TABLE public.listings DROP CONSTRAINT IF EXISTS listings_property_type_check;
ALTER TABLE public.listings
  ADD CONSTRAINT listings_property_type_check
  CHECK (property_type IS NULL OR property_type IN ('house', 'apartment', 'villa', 'land', 'other'));
