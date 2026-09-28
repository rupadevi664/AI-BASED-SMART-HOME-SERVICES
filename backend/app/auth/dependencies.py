"""JWT authentication and role-based authorization dependencies."""
import logging

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import User
from app.models.user import UserRole

logger = logging.getLogger(__name__)

# tokenUrl points at the form login so Swagger's "Authorize" button works.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login-form", auto_error=True)

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the JWT from the Authorization header to an active DB user.

    1. Read Authorization header (Bearer token) — handled by oauth2_scheme
    2. Decode + validate JWT (signature, expiration)
    3. Extract user id from `sub`
    4. Load user from the database
    5. Check the user is active
    """
    try:
        payload = decode_access_token(token)
    except pyjwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except pyjwt.InvalidTokenError as exc:
        raise CREDENTIALS_EXCEPTION from exc

    subject = payload.get("sub")
    if subject is None:
        raise CREDENTIALS_EXCEPTION
    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise CREDENTIALS_EXCEPTION from exc

    user = db.get(User, user_id)
    if user is None:
        # Token is valid but the user no longer exists (e.g. deleted).
        raise CREDENTIALS_EXCEPTION
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*roles: UserRole):
    """Dependency factory: allow access only to users whose role is one of `roles`."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return current_user

    return role_checker


# --- Reusable role dependencies --------------------------------------------

require_customer = require_roles(UserRole.CUSTOMER)
require_expert = require_roles(UserRole.EXPERT)
require_admin = require_roles(UserRole.ADMIN)
