from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

connect_args: dict = {}
engine_kwargs: dict = {"future": True}

if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif settings.database_url.startswith("postgresql+psycopg"):
    # Supabase's poolers (transaction mode) can break with prepared statements.
    # Disabling them avoids errors like "DuplicatePreparedStatement".
    # psycopg3: prepare_threshold=None disables server-side prepared statements.
    # connect_timeout avoids indefinite hang; keepalives help detect dead pooler sockets.
    connect_args = {
        "prepare_threshold": None,
        "connect_timeout": 15,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    }

# Hosted Postgres / Supabase often closes idle connections; without this, the pool
# can hand out dead sockets → "server closed the connection unexpectedly".
if not settings.database_url.startswith("sqlite"):
    engine_kwargs["pool_pre_ping"] = True
    # Recycle before typical pooler / proxy idle cutoffs (seconds).
    engine_kwargs["pool_recycle"] = 300
    # Return connections in a clean state for PgBouncer / Supabase pooler.
    engine_kwargs["pool_reset_on_return"] = "rollback"

engine = create_engine(settings.database_url, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()
_schema_ready = False

def get_db():
    global _schema_ready
    # If startup DB bootstrap was skipped (temporary DB outage), recover on first request.
    if not _schema_ready:
        try:
            Base.metadata.create_all(bind=engine)
            _schema_ready = True
        except Exception:
            # Keep request path alive; endpoint-level DB errors will still surface if DB is down.
            pass
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
