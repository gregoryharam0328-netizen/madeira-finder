# Madeira Property Finder Tool

A full-stack MVP codebase for a private property discovery assistant tailored to the client's requirements:

- Daily automated property discovery
- Madeira-only filters
- Houses + apartments
- 2+ bedrooms
- Budget range support
- Deduplication and listing grouping
- Morning email digest
- Shared dashboard access for two users
- Save / Seen / Hide actions
- Clean visual dashboard

## Stack

- Frontend: Next.js 14 + Tailwind CSS
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL / Supabase-compatible
- Auth: JWT-based email/password auth
- Email: Resend-ready digest service
- Scraping: Pluggable scraper adapters with normalization and dedup scaffolding
- Scheduler: Python worker for daily run

## Project Structure

```text
madeira-property-finder/
  backend/
  frontend/
  database/
  .env.example
```

## Important

This project is a **production-oriented MVP scaffold**:
- Core backend, DB models, API routes, auth, worker, digest service, and dashboard UI are implemented.
- Scrapers are implemented for the client’s priority portals (Imovirtual, Supercasa, Kyero, RE/MAX Madeira office listings, Century 21, Pink Real Estate) using **curl-cffi + BeautifulSoup**, with **Playwright** for heavily client-rendered pages.
- **Idealista** is integrated via **Apify** (recommended) because direct scraping is often blocked without residential proxies / additional anti-bot work.
- Email delivery uses Resend placeholders; add real API keys before deployment.

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload
```

### 2. Frontend

```bash
cd frontend
npm install
cp ../.env.example .env.local
npm run dev
```

### 3. Database

Run the SQL in:

```text
database/schema.sql
```

against PostgreSQL or Supabase.

## Default Flow

1. Create 2 user accounts with `/auth/register`
2. Run scraper worker:
   ```bash
   python -m app.workers.daily_runner
   ```
3. Log in on the frontend
4. View:
   - New Today
   - All Listings
   - Saved
   - Price Changes
5. Trigger digest sending by worker or scheduler

## Client Requirement Mapping

### Included
- Shared login access for client + partner
- Priority source config
- Madeira-wide filtering
- Daily automation scaffolding
- Morning digest
- De-duplication framework
- Clean dashboard UI
- Save/favourite/seen/hide actions
- Tracking of new and updated listings

### Left for live deployment tuning
- Production scraper selectors per source
- Proxy/anti-bot hardening if needed
- Final branding assets
- Real SMTP/email or Resend credentials
- Hosting secrets and DNS

## Suggested Deployment

- Frontend → Vercel
- Backend + Worker → Railway / Render / Fly.io
- DB → Supabase Postgres

## License

Private client project scaffold.
