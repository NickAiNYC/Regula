"""
Regula Health - Analytics & Dashboard API
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from decimal import Decimal
from datetime import date, timedelta

from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.models import User, Claim, Provider
from app.schemas import DashboardMetrics, PayerStats, ClaimResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get dashboard summary metrics
    
    Returns key metrics for the last N days:
    - Total claims processed
    - Number of violations
    - Violation rate percentage
    - Total recoverable amount
    - Average underpayment
    - Top violators (payers)
    """
    # Get provider IDs for this organization
    provider_stmt = select(Provider.id).where(
        Provider.organization_id == current_user.organization_id
    )
    provider_result = await db.execute(provider_stmt)
    provider_ids = [row[0] for row in provider_result.fetchall()]
    
    if not provider_ids:
        return DashboardMetrics(
            total_claims=0,
            violations=0,
            violation_rate=0.0,
            total_recoverable=Decimal("0.00"),
            avg_underpayment=Decimal("0.00"),
            top_violators=[],
            recent_claims=[]
        )
    
    # Date range filter
    start_date = date.today() - timedelta(days=days)
    base_filters = [
        Claim.provider_id.in_(provider_ids),
        Claim.dos >= start_date
    ]
    
    # Total claims
    total_stmt = select(func.count(Claim.id)).where(and_(*base_filters))
    total_result = await db.execute(total_stmt)
    total_claims = total_result.scalar() or 0
    
    # Violations count
    violation_stmt = select(func.count(Claim.id)).where(
        and_(*base_filters, Claim.is_violation == True)
    )
    violation_result = await db.execute(violation_stmt)
    violations = violation_result.scalar() or 0
    
    # Violation rate
    violation_rate = (violations / total_claims * 100) if total_claims > 0 else 0.0
    
    # Total recoverable amount (sum of deltas for violations)
    recoverable_stmt = select(func.sum(Claim.delta)).where(
        and_(*base_filters, Claim.is_violation == True)
    )
    recoverable_result = await db.execute(recoverable_stmt)
    total_recoverable = recoverable_result.scalar() or Decimal("0.00")
    
    # Average underpayment
    avg_underpayment = (total_recoverable / violations) if violations > 0 else Decimal("0.00")
    
    # Top violators (payers with most violations)
    top_violators_stmt = (
        select(
            Claim.payer,
            func.count(Claim.id).label("violation_count"),
            func.sum(Claim.delta).label("total_amount")
        )
        .where(and_(*base_filters, Claim.is_violation == True))
        .group_by(Claim.payer)
        .order_by(func.count(Claim.id).desc())
        .limit(5)
    )
    top_violators_result = await db.execute(top_violators_stmt)
    top_violators = [
        {
            "payer": row[0],
            "violation_count": row[1],
            "total_amount": float(row[2] or 0)
        }
        for row in top_violators_result.fetchall()
    ]
    
    # Recent claims (last 10)
    recent_stmt = (
        select(Claim)
        .where(and_(*base_filters))
        .order_by(Claim.created_at.desc())
        .limit(10)
    )
    recent_result = await db.execute(recent_stmt)
    recent_claims = recent_result.scalars().all()
    
    return DashboardMetrics(
        total_claims=total_claims,
        violations=violations,
        violation_rate=round(violation_rate, 2),
        total_recoverable=total_recoverable,
        avg_underpayment=avg_underpayment,
        top_violators=top_violators,
        recent_claims=recent_claims
    )


@router.get("/payers", response_model=list[PayerStats])
async def get_payer_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get payer-specific statistics
    
    Returns violation statistics for each payer.
    """
    # Get provider IDs
    provider_stmt = select(Provider.id).where(
        Provider.organization_id == current_user.organization_id
    )
    provider_result = await db.execute(provider_stmt)
    provider_ids = [row[0] for row in provider_result.fetchall()]
    
    if not provider_ids:
        return []
    
    # Payer statistics
    # Count violations using CASE expression for database compatibility
    from sqlalchemy import case
    payer_stats_stmt = (
        select(
            Claim.payer,
            func.count(Claim.id).label("total_claims"),
            func.sum(case((Claim.is_violation == True, 1), else_=0)).label("violations"),
            func.sum(Claim.delta).filter(Claim.is_violation == True).label("recoverable")
        )
        .where(Claim.provider_id.in_(provider_ids))
        .group_by(Claim.payer)
        .order_by(func.count(Claim.id).desc())
    )
    
    result = await db.execute(payer_stats_stmt)
    rows = result.fetchall()
    
    stats = []
    for row in rows:
        payer, total, violations, recoverable = row
        violation_rate = (violations / total * 100) if total > 0 else 0.0
        
        stats.append(PayerStats(
            payer=payer,
            total_claims=total or 0,
            violations=violations or 0,
            violation_rate=round(violation_rate, 2),
            total_recoverable=recoverable or Decimal("0.00")
        ))
    
    return stats
