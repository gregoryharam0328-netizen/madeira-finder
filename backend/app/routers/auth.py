import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import TokenResponse, UserCreate, UserLogin, UserOut
from app.security import create_access_token, get_password_hash, verify_password
from app.dependencies import get_current_user

log = logging.getLogger(__name__)
router = APIRouter()

@router.get("/test")
def test():
    return {"message": "API is working"}
@router.post("/register", response_model=UserOut)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    try:
        existing = db.query(User).filter(User.email == payload.email.lower()).first()
    except SQLAlchemyError as exc:
        log.exception("Database error during register lookup")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable. Please try again shortly.",
        ) from exc
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = User(email=payload.email.lower(), full_name=payload.full_name, password_hash=get_password_hash(payload.password), role="member")
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        log.exception("Database error during register commit")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable. Please try again shortly.",
        ) from exc
    return user
@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.email == payload.email.lower()).first()
    except SQLAlchemyError as exc:
        log.exception("Database error during login lookup")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable. Please try again shortly.",
        ) from exc
    if not user:
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
    return TokenResponse(access_token=create_access_token(user.id))
@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
