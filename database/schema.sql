-- Madeira Property Finder - PostgreSQL/Supabase schema
create extension if not exists pgcrypto;

create table if not exists public.users (
    id uuid primary key default gen_random_uuid(),
    email text not null unique,
    full_name text,
    password_hash text not null,
    role text not null default 'member' check (role in ('owner','member')),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.sources (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    base_url text not null,
    source_type text not null check (source_type in ('portal','agency','marketplace')),
    country_code text not null default 'PT',
    is_active boolean not null default true,
    priority integer not null default 1,
    config_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.scrape_runs (
    id uuid primary key default gen_random_uuid(),
    source_id uuid references public.sources(id) on delete cascade,
    run_type text not null default 'scheduled' check (run_type in ('scheduled','manual','retry')),
    status text not null default 'running' check (status in ('running','success','partial_success','failed')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    pages_scanned integer not null default 0,
    listings_found integer not null default 0,
    listings_inserted integer not null default 0,
    listings_updated integer not null default 0,
    listings_filtered integer not null default 0,
    error_log text,
    meta_json jsonb
);

create table if not exists public.listings_raw (
    id uuid primary key default gen_random_uuid(),
    scrape_run_id uuid references public.scrape_runs(id) on delete set null,
    source_id uuid not null references public.sources(id) on delete cascade,
    source_listing_id text,
    source_url text not null,
    checksum text,
    raw_payload_json jsonb not null,
    scraped_at timestamptz not null default now()
);

create table if not exists public.listings (
    id uuid primary key default gen_random_uuid(),
    source_id uuid not null references public.sources(id) on delete cascade,
    raw_listing_id uuid references public.listings_raw(id) on delete set null,
    source_listing_id text,
    canonical_url text not null,
    source_url text not null,
    title text not null,
    normalized_title text,
    description text,
    normalized_description text,
    price numeric(12,2),
    currency text not null default 'EUR',
    location_text text,
    normalized_location text,
    area_name text,
    municipality text,
    island text default 'Madeira',
    latitude numeric(10,7),
    longitude numeric(10,7),
    bedrooms integer,
    bathrooms integer,
    property_type text check (property_type in ('house','apartment','villa','land','other')),
    listing_type text not null default 'sale' check (listing_type in ('sale','rent','other')),
    image_url text,
    published_at timestamptz,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    fingerprint text,
    is_active boolean not null default true,
    eligibility_status text not null default 'eligible' check (eligibility_status in ('eligible','filtered_out','duplicate','inactive')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (source_id, canonical_url)
);

create table if not exists public.listing_groups (
    id uuid primary key default gen_random_uuid(),
    group_status text not null default 'active' check (group_status in ('active','inactive','relisted')),
    confidence_score numeric(5,2),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.listing_group_members (
    id uuid primary key default gen_random_uuid(),
    listing_group_id uuid not null references public.listing_groups(id) on delete cascade,
    listing_id uuid not null references public.listings(id) on delete cascade,
    match_method text not null check (match_method in ('url','source_listing_id','fingerprint','fuzzy','manual')),
    match_score numeric(5,2),
    created_at timestamptz not null default now(),
    unique (listing_id)
);

create table if not exists public.listing_events (
    id uuid primary key default gen_random_uuid(),
    listing_id uuid not null references public.listings(id) on delete cascade,
    event_type text not null check (event_type in ('new','updated','price_changed','back_on_market','relisted','marked_inactive')),
    old_value_json jsonb,
    new_value_json jsonb,
    detected_at timestamptz not null default now()
);

create table if not exists public.user_listing_state (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    listing_group_id uuid not null references public.listing_groups(id) on delete cascade,
    is_saved boolean not null default false,
    saved_at timestamptz,
    is_seen boolean not null default false,
    seen_at timestamptz,
    is_hidden boolean not null default false,
    hidden_at timestamptz,
    workflow_status text,
    note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, listing_group_id),
    constraint user_listing_state_workflow_chk check (
        workflow_status is null
        or workflow_status in (
            'new',
            'seen',
            'favourite',
            'need_to_call',
            'viewing_arranged',
            'offer_made',
            'not_available',
            'not_interested'
        )
    )
);

create table if not exists public.digest_runs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references public.users(id) on delete cascade,
    generated_at timestamptz not null default now(),
    listing_count integer not null default 0,
    status text not null default 'pending' check (status in ('pending','sent','failed','skipped')),
    digest_payload_json jsonb,
    error_log text
);

create index if not exists idx_listings_fingerprint on public.listings(fingerprint);
create index if not exists idx_listings_price on public.listings(price);
create index if not exists idx_listings_first_seen_at on public.listings(first_seen_at desc);
create index if not exists idx_listings_last_seen_at on public.listings(last_seen_at desc);
create index if not exists idx_user_listing_state_user_id on public.user_listing_state(user_id);
create index if not exists idx_listing_group_members_group_id on public.listing_group_members(listing_group_id);

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_users_updated_at on public.users;
create trigger trg_users_updated_at before update on public.users
for each row execute function public.set_updated_at();

drop trigger if exists trg_sources_updated_at on public.sources;
create trigger trg_sources_updated_at before update on public.sources
for each row execute function public.set_updated_at();

drop trigger if exists trg_listings_updated_at on public.listings;
create trigger trg_listings_updated_at before update on public.listings
for each row execute function public.set_updated_at();

drop trigger if exists trg_listing_groups_updated_at on public.listing_groups;
create trigger trg_listing_groups_updated_at before update on public.listing_groups
for each row execute function public.set_updated_at();

drop trigger if exists trg_user_listing_state_updated_at on public.user_listing_state;
create trigger trg_user_listing_state_updated_at before update on public.user_listing_state
for each row execute function public.set_updated_at();

insert into public.sources (name, base_url, source_type, priority)
values
('Idealista', 'https://www.idealista.pt', 'portal', 1),
('Imovirtual', 'https://www.imovirtual.com', 'portal', 1),
('Supercasa', 'https://supercasa.pt', 'portal', 1),
('Kyero', 'https://www.kyero.com', 'portal', 2),
('Green-Acres', 'https://www.green-acres.pt', 'portal', 2),
('RE/MAX Portugal', 'https://www.remax.pt', 'agency', 2),
('Century 21 Portugal', 'https://www.century21.pt', 'agency', 2),
('Pink Real Estate', 'https://www.pinkrealestate.pt', 'agency', 2)
on conflict (name) do nothing;
