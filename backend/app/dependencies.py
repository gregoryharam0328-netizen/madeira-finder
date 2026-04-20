import logging
import time
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.exc import InternalError, OperationalError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

log = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=True)

# Supabase transaction pooler sometimes returns "DbHandler exited" / InternalError on transient blips.
_TRANSIENT_DB = (OperationalError, InternalError)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = None
    for attempt in range(3):
        try:
            user = db.query(User).filter(User.id == user_uuid, User.is_active.is_(True)).first()
            break
        except _TRANSIENT_DB as exc:
            log.warning("Transient DB error loading user (attempt %s/3): %s", attempt + 1, exc)
            try:
                db.rollback()
            except Exception:
                pass
            try:
                db.connection().invalidate()
            except Exception:
                pass
            if attempt == 2:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database temporarily unavailable. Please retry.",
                ) from exc
            time.sleep(0.12 * (attempt + 1))

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
