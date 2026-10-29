import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise unauthorized
    except jwt.PyJWTError as exc:
        raise unauthorized from exc
    user = db.get(User, str(user_id))
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_membership(db: Session, user_id: str, organization_id: str):
    from sqlalchemy import select
    from app.models import Membership

    membership = db.scalar(select(Membership).where(
        Membership.user_id == user_id,
        Membership.organization_id == organization_id,
    ))
    if membership is None:
        # A consistent 404 avoids confirming that another tenant's ID exists.
        raise HTTPException(status_code=404, detail="Organization not found.")
    return membership
