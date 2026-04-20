import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import TokenResponse, UserCreate, UserLogin, UserOut
from app.security import (
    create_access_token,
    get_password_hash,
    normalize_email,
    verify_password,
)

log = logging.getLogger(__name__)
router = APIRouter()


def _signup_http_exception(exc: BaseException) -> HTTPException | None:
    """Map Postgres / Supabase failures to actionable HTTP errors (not generic 500)."""
    if isinstance(exc, IntegrityError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    if not isinstance(exc, SQLAlchemyError):
        return None
    orig = getattr(exc, "orig", None)
    raw = str(orig or exc)
    lowered = raw.lower()
    if "row-level security" in lowered or "violates row-level security policy" in lowered:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Database blocked signup (row-level security on public.users). "
                "In Supabase Table Editor: disable RLS for public.users, or add a policy that allows "
                "INSERT (and SELECT for RETURNING) for the Postgres role used in DATABASE_URL."
            ),
        )
    if "permission denied" in lowered:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database permission denied while creating the user. Check grants on public.users.",
        )
    if isinstance(exc, DBAPIError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database error during signup. Check API logs and public.users schema vs app models.",
        )
    return None


@router.get("/test")
def test():
    return {"message": "API is working"}


@router.post("/register", response_model=UserOut)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    email_key = normalize_email(str(payload.email))
    try:
        existing = (
            db.query(User)
            .filter(func.lower(func.trim(User.email)) == email_key)
            .first()
        )
    except SQLAlchemyError as exc:
        log.exception("Database error during register lookup")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable. Please try again shortly.",
        ) from exc
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    try:
        password_hash = get_password_hash(payload.password)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password",
        ) from exc
    except Exception as exc:
        log.exception("Password hashing failed during register")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not process password",
        ) from exc
    user = User(
        email=email_key,
        full_name=payload.full_name,
        password_hash=password_hash,
        role="member",
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except Exception as exc:
        db.rollback()
        mapped = _signup_http_exception(exc)
        if mapped is not None:
            raise mapped
        log.exception("Unexpected error during register commit")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        ) from exc
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    email_key = normalize_email(str(payload.email))
    try:
        user = (
            db.query(User)
            .filter(func.lower(func.trim(User.email)) == email_key)
            .first()
        )
    except SQLAlchemyError as exc:
        log.exception("Database error during login lookup")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable. Please try again shortly.",
        ) from exc
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        password_ok = verify_password(payload.password, user.password_hash)
    except Exception:
        # Treat broken or incompatible stored hashes as invalid credentials,
        # and log details for server-side triage.
        log.exception("Password verification failed for user %s", user.email)
        password_ok = False
    if not password_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        token = create_access_token(user.id)
    except Exception as exc:
        log.exception("JWT creation failed for user %s", user.email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create session",
        ) from exc
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
