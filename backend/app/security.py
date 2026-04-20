import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.config import settings


def normalize_email(email: str) -> str:
    """Lowercase + trim for consistent lookup (Postgres `users.email`, not Supabase Auth)."""
    return (email or "").strip().lower()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    # Native bcrypt avoids passlib/backend breakage on newer bcrypt wheels (common on Render/Linux).
    digest = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return digest.decode("utf-8")


def create_access_token(subject: str | uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    # RFC 7519 NumericDate (seconds since epoch) — explicit for all python-jose versions.
    payload = {"sub": str(subject), "exp": int(expire.timestamp())}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
