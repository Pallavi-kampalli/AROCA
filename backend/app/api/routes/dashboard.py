from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from datetime import datetime, timezone, timedelta
from app.db.session import get_db
from app.db import models
from app.core.security import get_current_active_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def summary(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    # Total incidents
    total = await db.scalar(select(func.count(models.Incident.id))) or 0

    # By status
    open_statuses = ["NEW", "TRIAGED", "INVESTIGATING", "AWAITING_APPROVAL", "IN_PROGRESS", "REOPENED"]
    open_count = await db.scalar(
        select(func.count(models.Incident.id)).where(models.Incident.status.in_(open_statuses))
    ) or 0

    critical = await db.scalar(
        select(func.count(models.Incident.id)).where(
            models.Incident.severity == "CRITICAL",
            models.Incident.status.in_(open_statuses),
        )
    ) or 0

    awaiting_approval = await db.scalar(
        select(func.count(models.Incident.id)).where(
            models.Incident.status == "AWAITING_APPROVAL"
        )
    ) or 0

    resolved = await db.scalar(
        select(func.count(models.Incident.id)).where(
            models.Incident.status.in_(["RESOLVED", "CLOSED"])
        )
    ) or 0

    sla_breaches = await db.scalar(
        select(func.count(models.Incident.id)).where(models.Incident.sla_breach == True)
    ) or 0

    # MTTR (mean time to resolution in minutes)
    resolved_with_times = await db.execute(
        select(models.Incident.created_at, models.Incident.resolved_at).where(
            models.Incident.resolved_at.isnot(None)
        ).limit(200)
    )
    times = resolved_with_times.all()
    if times:
        resolutions_minutes = [
            (row.resolved_at - row.created_at).total_seconds() / 60
            for row in times
            if row.resolved_at and row.created_at
        ]
        mttr_minutes = sum(resolutions_minutes) / len(resolutions_minutes) if resolutions_minutes else None
    else:
        mttr_minutes = None

    # RCA completion rate
    total_analyses = await db.scalar(select(func.count(models.RCAAnalysisRun.id))) or 0
    completed_analyses = await db.scalar(
        select(func.count(models.RCAAnalysisRun.id)).where(
            models.RCAAnalysisRun.status == "COMPLETED"
        )
    ) or 0
    rca_rate = (completed_analyses / total_analyses * 100) if total_analyses > 0 else None

    # Pending approvals
    pending_approvals = await db.scalar(
        select(func.count(models.ApprovalRequest.id)).where(
            models.ApprovalRequest.status == "PENDING"
        )
    ) or 0

    # Automated resolution rate (executions that resulted in verified resolution)
    total_executions = await db.scalar(select(func.count(models.RemediationExecution.id))) or 0
    verified_resolutions = await db.scalar(
        select(func.count(models.VerificationResult.id)).where(
            models.VerificationResult.is_resolved == True
        )
    ) or 0
    auto_resolution_rate = (verified_resolutions / total_executions * 100) if total_executions > 0 else None

    # Recent incidents
    recent_result = await db.execute(
        select(models.Incident).order_by(models.Incident.created_at.desc()).limit(5)
    )
    recent_incidents = [
        {
            "id": i.id,
            "number": i.number,
            "title": i.title,
            "severity": i.severity,
            "status": i.status,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in recent_result.scalars().all()
    ]

    # Recent analyses
    recent_analyses_result = await db.execute(
        select(models.RCAAnalysisRun).order_by(models.RCAAnalysisRun.created_at.desc()).limit(5)
    )
    recent_analyses = [
        {
            "id": r.id,
            "incident_id": r.incident_id,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in recent_analyses_result.scalars().all()
    ]

    # Pending approval items
    pending_items_result = await db.execute(
        select(models.ApprovalRequest)
        .where(models.ApprovalRequest.status == "PENDING")
        .order_by(models.ApprovalRequest.created_at.desc())
        .limit(5)
    )
    pending_items = [
        {
            "id": p.id,
            "action_id": p.action_id,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in pending_items_result.scalars().all()
    ]

    return {
        "total_incidents": total,
        "open_incidents": open_count,
        "critical_incidents": critical,
        "awaiting_approval": awaiting_approval,
        "resolved_incidents": resolved,
        "sla_breaches": sla_breaches,
        "mttr_minutes": round(mttr_minutes, 1) if mttr_minutes else None,
        "rca_completion_rate": round(rca_rate, 1) if rca_rate is not None else None,
        "pending_approvals": pending_approvals,
        "auto_resolution_rate": round(auto_resolution_rate, 1) if auto_resolution_rate is not None else None,
        "recent_incidents": recent_incidents,
        "recent_analyses": recent_analyses,
        "pending_approval_items": pending_items,
    }


@router.get("/trends")
async def trends(
    days: int = Query(default=30, ge=1, le=365),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Incident counts over time."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(models.Incident.created_at, models.Incident.severity, models.Incident.status)
        .where(models.Incident.created_at >= since)
        .order_by(models.Incident.created_at.asc())
    )
    rows = result.all()

    # Group by day
    from collections import defaultdict
    daily = defaultdict(lambda: {"total": 0, "critical": 0, "resolved": 0})
    for row in rows:
        if row.created_at:
            day = row.created_at.strftime("%Y-%m-%d")
            daily[day]["total"] += 1
            if row.severity == "CRITICAL":
                daily[day]["critical"] += 1
            if row.status in ("RESOLVED", "CLOSED"):
                daily[day]["resolved"] += 1

    return {
        "days": days,
        "data": [
            {"date": day, **counts}
            for day, counts in sorted(daily.items())
        ],
    }


@router.get("/distributions")
async def distributions(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Severity and category distributions."""
    # Severity
    sev_result = await db.execute(
        select(models.Incident.severity, func.count(models.Incident.id).label("count"))
        .group_by(models.Incident.severity)
    )
    severity_dist = [{"severity": r.severity, "count": r.count} for r in sev_result.all()]

    # Status
    status_result = await db.execute(
        select(models.Incident.status, func.count(models.Incident.id).label("count"))
        .group_by(models.Incident.status)
    )
    status_dist = [{"status": r.status, "count": r.count} for r in status_result.all()]

    # Category
    cat_result = await db.execute(
        select(models.Incident.category, func.count(models.Incident.id).label("count"))
        .where(models.Incident.category.isnot(None))
        .group_by(models.Incident.category)
        .order_by(func.count(models.Incident.id).desc())
        .limit(10)
    )
    cat_dist = [{"category": r.category, "count": r.count} for r in cat_result.all()]

    return {
        "severity": severity_dist,
        "status": status_dist,
        "category": cat_dist,
    }
