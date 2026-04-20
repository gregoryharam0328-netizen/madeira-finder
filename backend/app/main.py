import asyncio
import logging
from contextlib import asynccontextmanager

from app.win_asyncio import apply_windows_proactor_policy

apply_windows_proactor_policy()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import auth, health, listings, actions, dashboard
from app.workers.daily_catchup import ensure_today_ingestion_if_missed
from app.workers.daily_scheduler import daily_scheduler_loop

log = logging.getLogger(__name__)

try:
    Base.metadata.create_all(bind=engine)
except Exception:
    # Keep API booting even if DB is briefly unreachable (DNS/network hiccup).
    # Requests that need DB will still fail with clear errors until connectivity returns.
    log.exception("Database bootstrap check failed at startup; continuing without create_all.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1) If we missed today's successful scheduled run, ingest once now ("today" data).
    if settings.enable_startup_daily_catchup:
        await asyncio.to_thread(ensure_today_ingestion_if_missed)
    # 2) From the next configured local time onward, run the same job automatically each day (while this process runs).
    sched_task: asyncio.Task | None = None
    if settings.enable_daily_scheduler:
        sched_task = asyncio.create_task(daily_scheduler_loop(), name="daily-ingestion-scheduler")
    if (settings.idealista_csv_import_url or "").strip() and settings.idealista_csv_import_on_startup:

        async def _idealista_csv_startup():
            from app.services.idealista_csv_import import run_idealista_csv_import_logged

            try:
                await asyncio.to_thread(run_idealista_csv_import_logged)
            except Exception:
                log.exception("Idealista CSV import on startup failed")

        asyncio.create_task(_idealista_csv_startup(), name="idealista-csv-import")
    yield
    if sched_task is not None:
        sched_task.cancel()
        try:
            await sched_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title=settings.app_name, lifespan=lifespan)

_raw = [o.strip().rstrip("/") for o in settings.backend_cors_origins.split(",") if o.strip()]
_dev = ["http://localhost:3000", "http://127.0.0.1:3000", "https://madeira-frontend.onrender.com"]
# Never use "*" with allow_credentials=True (browsers reject it).
# Union local dev origins with BACKEND_CORS_ORIGINS so a Render-only .env still works locally.
origins = list(dict.fromkeys(_dev + _raw))
# origin_regex = (settings.backend_cors_origin_regex or "").strip() or None
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(listings.router, prefix="/listings", tags=["listings"])
app.include_router(actions.router, prefix="/actions", tags=["actions"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
