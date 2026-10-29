from datetime import datetime, timezone

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.orm import Session

from app.models import Organization, UsageEvent


def current_billing_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def reserve_tokens(db: Session, organization_id: str, tokens: int, month: str) -> bool:
    """Atomically reserve estimated usage before provider work begins.

    This protects quota checks across concurrent requests in a single database.
    The database's conditional UPDATE is the enforcement point, not a Python
    read-modify-write. Reservation estimates can differ from actual token counts.
    """
    if tokens <= 0:
        return False
    allowed = or_(
        and_(Organization.usage_month != month, Organization.monthly_token_limit >= tokens),
        and_(Organization.usage_month == month,
             Organization.monthly_used_tokens + tokens <= Organization.monthly_token_limit),
    )
    statement = (
        update(Organization)
        .where(Organization.id == organization_id, allowed)
        .values(
            usage_month=month,
            monthly_used_tokens=case(
                (Organization.usage_month != month, tokens),
                else_=Organization.monthly_used_tokens + tokens,
            ),
        )
        .execution_options(synchronize_session=False)
    )
    result = db.execute(statement)
    db.commit()
    return result.rowcount == 1


def adjust_reservation(db: Session, organization_id: str, month: str, delta: int) -> None:
    """Add delta to the current-month counter; negative delta releases tokens."""
    if delta == 0:
        return
    # Keep the counter non-negative when releasing a reservation after failure.
    new_value = case(
        (Organization.monthly_used_tokens + delta < 0, 0),
        else_=Organization.monthly_used_tokens + delta,
    )
    db.execute(
        update(Organization)
        .where(Organization.id == organization_id, Organization.usage_month == month)
        .values(monthly_used_tokens=new_value)
        .execution_options(synchronize_session=False)
    )
    db.commit()


def roll_month_if_needed(db: Session, organization: Organization, month: str) -> Organization:
    if organization.usage_month != month:
        organization.usage_month = month
        organization.monthly_used_tokens = 0
        db.commit()
        db.refresh(organization)
    return organization


def create_usage_event(
    db: Session,
    *, organization_id: str,
    user_id: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: float,
    month: str,
) -> UsageEvent:
    event = UsageEvent(
        organization_id=organization_id,
        user_id=user_id,
        operation="summarize",
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated_cost_usd=estimated_cost_usd,
        billing_month=month,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def usage_rollup(db: Session, organization_id: str, month: str) -> dict[str, float | int]:
    row = db.execute(
        select(
            func.coalesce(func.sum(UsageEvent.total_tokens), 0),
            func.count(UsageEvent.id),
            func.coalesce(func.sum(UsageEvent.estimated_cost_usd), 0.0),
        ).where(
            UsageEvent.organization_id == organization_id,
            UsageEvent.billing_month == month,
        )
    ).one()
    return {"event_tokens": int(row[0]), "event_count": int(row[1]), "estimated_cost_usd": float(row[2])}
