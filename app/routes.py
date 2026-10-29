import math
import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import organization_output, router as auth_router
from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user, require_membership
from app.models import Membership, Organization, User, UsageEvent
from app.schemas import (
    MeResponse, OrganizationCreate, OrganizationOut, SummarizeRequest,
    SummarizeResponse, UsageEventOut, UsageResponse,
)
from app.services.ai import AIProviderError, estimate_tokens, generate_summary
from app.services.usage import (
    adjust_reservation, create_usage_event, current_billing_month,
    reserve_tokens, roll_month_if_needed, usage_rollup,
)

router = APIRouter(prefix="/api")
router.include_router(auth_router)


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
    return f"{base[:110]}-{secrets.token_hex(3)}"


@router.get("/me", response_model=MeResponse, tags=["account"])
def get_me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(id=user.id, email=user.email)


@router.get("/organizations", response_model=list[OrganizationOut], tags=["organizations"])
def list_organizations(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[OrganizationOut]:
    rows = db.execute(
        select(Membership, Organization)
        .join(Organization, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.created_at.asc())
    ).all()
    return [organization_output(org, membership.role) for membership, org in rows]


@router.post("/organizations", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED, tags=["organizations"])
def create_organization(
    payload: OrganizationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationOut:
    month = current_billing_month()
    organization = Organization(
        name=payload.name.strip(), slug=slugify(payload.name),
        monthly_token_limit=settings.default_monthly_token_limit,
        monthly_used_tokens=0, usage_month=month,
    )
    db.add(organization)
    db.flush()
    db.add(Membership(user_id=user.id, organization_id=organization.id, role="owner"))
    db.commit()
    db.refresh(organization)
    return organization_output(organization, "owner")


@router.get("/organizations/{organization_id}/usage", response_model=UsageResponse, tags=["usage"])
def get_usage(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsageResponse:
    require_membership(db, user.id, organization_id)
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    month = current_billing_month()
    organization = roll_month_if_needed(db, organization, month)
    rollup = usage_rollup(db, organization.id, month)
    return UsageResponse(
        organization_id=organization.id, billing_month=month,
        used_tokens=organization.monthly_used_tokens,
        limit_tokens=organization.monthly_token_limit,
        remaining_tokens=max(0, organization.monthly_token_limit - organization.monthly_used_tokens),
        event_count=int(rollup["event_count"]),
        estimated_cost_usd=round(float(rollup["estimated_cost_usd"]), 8),
    )


@router.get("/organizations/{organization_id}/usage/events", response_model=list[UsageEventOut], tags=["usage"])
def list_usage_events(
    organization_id: str,
    limit: int = Query(default=25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UsageEventOut]:
    require_membership(db, user.id, organization_id)
    rows = db.scalars(
        select(UsageEvent)
        .where(UsageEvent.organization_id == organization_id)
        .order_by(UsageEvent.created_at.desc())
        .limit(limit)
    ).all()
    return [UsageEventOut(
        id=row.id, user_id=row.user_id, operation=row.operation,
        provider=row.provider, model=row.model, input_tokens=row.input_tokens,
        output_tokens=row.output_tokens, total_tokens=row.total_tokens,
        estimated_cost_usd=row.estimated_cost_usd, billing_month=row.billing_month,
        created_at=row.created_at.isoformat(),
    ) for row in rows]


@router.post("/ai/summarize", response_model=SummarizeResponse, tags=["AI features"])
def summarize(
    payload: SummarizeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SummarizeResponse:
    require_membership(db, user.id, payload.organization_id)
    organization = db.get(Organization, payload.organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")

    month = current_billing_month()
    # Reserve a conservative input estimate plus the configured output ceiling.
    # The actual model usage later releases the unused portion.
    reserved_tokens = estimate_tokens(payload.input_text) + payload.max_output_tokens
    if not reserve_tokens(db, organization.id, reserved_tokens, month):
        raise HTTPException(
            status_code=429,
            detail="Monthly token limit reached. Reduce the request size or contact your workspace owner.",
        )

    try:
        generated = generate_summary(payload.input_text, payload.max_output_tokens)
        actual_tokens = generated.input_tokens + generated.output_tokens
        adjust_reservation(db, organization.id, month, actual_tokens - reserved_tokens)
        event = create_usage_event(
            db,
            organization_id=organization.id,
            user_id=user.id,
            provider=generated.provider,
            model=generated.model,
            input_tokens=generated.input_tokens,
            output_tokens=generated.output_tokens,
            estimated_cost_usd=generated.estimated_cost_usd,
            month=month,
        )
    except AIProviderError as exc:
        adjust_reservation(db, organization.id, month, -reserved_tokens)
        raise HTTPException(status_code=503, detail="AI provider unavailable; quota reservation was released.") from exc
    except Exception:
        adjust_reservation(db, organization.id, month, -reserved_tokens)
        raise

    db.refresh(organization)
    return SummarizeResponse(
        organization_id=organization.id,
        summary=generated.summary,
        provider=generated.provider,
        model=generated.model,
        input_tokens=generated.input_tokens,
        output_tokens=generated.output_tokens,
        total_tokens=event.total_tokens,
        estimated_cost_usd=round(generated.estimated_cost_usd, 8),
        usage_month=month,
        usage_used_tokens=organization.monthly_used_tokens,
        usage_limit_tokens=organization.monthly_token_limit,
        remaining_tokens=max(0, organization.monthly_token_limit - organization.monthly_used_tokens),
    )
