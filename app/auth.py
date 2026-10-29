import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Membership, Organization, User
from app.schemas import AuthResponse, LoginRequest, OrganizationOut, RegisterRequest, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
    return f"{base[:110]}-{secrets.token_hex(3)}"


def organization_output(org: Organization, role: str) -> OrganizationOut:
    return OrganizationOut(
        id=org.id, name=org.name, slug=org.slug, role=role,
        monthly_token_limit=org.monthly_token_limit,
        monthly_used_tokens=org.monthly_used_tokens, usage_month=org.usage_month,
    )


def build_auth_response(user: User, db: Session) -> AuthResponse:
    memberships = db.execute(select(Membership, Organization).join(
        Organization, Membership.organization_id == Organization.id
    ).where(Membership.user_id == user.id)).all()
    organizations = [organization_output(org, membership.role) for membership, org in memberships]
    return AuthResponse(
        access_token=create_access_token(user.id, user.email),
        user=UserOut(id=user.id, email=user.email),
        organizations=organizations,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.strip().lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(payload.password))
    organization = Organization(
        name=payload.organization_name.strip(), slug=slugify(payload.organization_name),
        monthly_token_limit=settings.default_monthly_token_limit,
        monthly_used_tokens=0, usage_month=datetime.now(timezone.utc).strftime("%Y-%m"),
    )
    try:
        db.add_all([user, organization])
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=organization.id, role="owner"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create account; email may already be registered.") from exc
    db.refresh(user)
    return build_auth_response(user, db)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.", headers={"WWW-Authenticate": "Bearer"})
    return build_auth_response(user, db)
