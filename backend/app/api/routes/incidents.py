import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from pydantic import BaseModel
from app.db.session import get_db
from app.db import models
from app.core.security import get_current_active_user
from app.services.audit_service import log_action

router = APIRouter(prefix="/incidents", tags=["incidents"])

VALID_TRANSITIONS = {
    "NEW": ["TRIAGED", "CLOSED"],
    "TRIAGED": ["INVESTIGATING", "CLOSED"],
    "INVESTIGATING": ["AWAITING_APPROVAL", "IN_PROGRESS", "RESOLVED"],
    "AWAITING_APPROVAL": ["IN_PROGRESS", "INVESTIGATING"],
    "IN_PROGRESS": ["RESOLVED", "AWAITING_APPROVAL"],
    "RESOLVED": ["CLOSED", "REOPENED"],
    "CLOSED": ["REOPENED"],
    "REOPENED": ["TRIAGED", "INVESTIGATING"],
}


def next_incident_number(count: int) -> str:
    return f"INC{str(count + 1).zfill(7)}"


class CreateIncidentBody(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str = "MEDIUM"
    category: Optional[str] = None
    affected_component: Optional[str] = None
    business_impact: Optional[str] = None
    environment_name: Optional[str] = None
    assignee_id: Optional[str] = None
    service_id: Optional[str] = None


class UpdateIncidentBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    affected_component: Optional[str] = None
    business_impact: Optional[str] = None
    environment_name: Optional[str] = None
    assignee_id: Optional[str] = None


class CommentBody(BaseModel):
    content: str
    is_internal: bool = True


class RelationshipBody(BaseModel):
    target_id: str
    relationship_type: str = "related"


@router.get("")
async def list_incidents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    severity: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(models.Incident)
    if severity:
        q = q.where(models.Incident.severity == severity.upper())
    if status:
        q = q.where(models.Incident.status == status.upper())
    if search:
        q = q.where(or_(
            models.Incident.title.ilike(f"%{search}%"),
            models.Incident.number.ilike(f"%{search}%"),
            models.Incident.description.ilike(f"%{search}%"),
        ))

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(models.Incident.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    incidents = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": i.id,
                "number": i.number,
                "title": i.title,
                "severity": i.severity,
                "status": i.status,
                "category": i.category,
                "environment_name": i.environment_name,
                "created_at": i.created_at.isoformat() if i.created_at else None,
                "updated_at": i.updated_at.isoformat() if i.updated_at else None,
                "sla_breach": i.sla_breach,
            }
            for i in incidents
        ],
    }


@router.post("", status_code=201)
async def create_incident(
    body: CreateIncidentBody,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Generate incident number
    count = await db.scalar(select(func.count(models.Incident.id))) or 0
    number = next_incident_number(count)
    now = datetime.now(timezone.utc)

    # Validate severity
    valid_severities = [s.value for s in models.Severity]
    if body.severity.upper() not in valid_severities:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Valid: {valid_severities}")

    incident = models.Incident(
        id=str(uuid.uuid4()),
        number=number,
        title=body.title,
        description=body.description,
        severity=body.severity.upper(),
        status="NEW",
        category=body.category,
        affected_component=body.affected_component,
        business_impact=body.business_impact,
        environment_name=body.environment_name,
        reporter_id=current_user.id,
        assignee_id=body.assignee_id,
        service_id=body.service_id,
        created_at=now,
        updated_at=now,
    )
    db.add(incident)
    await db.flush()

    # Create timeline event
    event = models.IncidentEvent(
        id=str(uuid.uuid4()),
        incident_id=incident.id,
        event_type="created",
        description=f"Incident {number} created",
        actor_id=current_user.id,
        occurred_at=now,
    )
    db.add(event)

    await log_action(db=db, action="incident.create", user_id=current_user.id,
                     resource_type="incident", resource_id=incident.id,
                     details={"number": number, "title": body.title})

    return {"id": incident.id, "number": incident.number, "status": incident.status}


@router.get("/{incident_id}")
async def get_incident(
    incident_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Incident).where(models.Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Reporter and assignee
    reporter = None
    if incident.reporter_id:
        r = await db.execute(select(models.User).where(models.User.id == incident.reporter_id))
        ru = r.scalar_one_or_none()
        if ru:
            reporter = {"id": ru.id, "username": ru.username, "full_name": ru.full_name}

    assignee = None
    if incident.assignee_id:
        a = await db.execute(select(models.User).where(models.User.id == incident.assignee_id))
        au = a.scalar_one_or_none()
        if au:
            assignee = {"id": au.id, "username": au.username, "full_name": au.full_name}

    # Comments
    comm_result = await db.execute(
        select(models.IncidentComment)
        .where(models.IncidentComment.incident_id == incident_id)
        .order_by(models.IncidentComment.created_at.asc())
    )
    comments = [
        {
            "id": c.id,
            "content": c.content,
            "is_internal": c.is_internal,
            "author_id": c.author_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comm_result.scalars().all()
    ]

    # Events
    event_result = await db.execute(
        select(models.IncidentEvent)
        .where(models.IncidentEvent.incident_id == incident_id)
        .order_by(models.IncidentEvent.occurred_at.asc())
    )
    events = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "description": e.description,
            "actor_id": e.actor_id,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        }
        for e in event_result.scalars().all()
    ]

    # Artifacts
    art_result = await db.execute(
        select(models.UploadedArtifact).where(models.UploadedArtifact.incident_id == incident_id)
    )
    artifacts = [
        {
            "id": a.id,
            "filename": a.original_filename,
            "content_type": a.content_type,
            "file_size_bytes": a.file_size_bytes,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in art_result.scalars().all()
    ]

    # Latest RCA
    rca_result = await db.execute(
        select(models.RCAAnalysisRun)
        .where(models.RCAAnalysisRun.incident_id == incident_id)
        .order_by(models.RCAAnalysisRun.created_at.desc())
        .limit(1)
    )
    latest_rca = rca_result.scalar_one_or_none()

    return {
        "id": incident.id,
        "number": incident.number,
        "title": incident.title,
        "description": incident.description,
        "severity": incident.severity,
        "status": incident.status,
        "category": incident.category,
        "affected_component": incident.affected_component,
        "business_impact": incident.business_impact,
        "environment_name": incident.environment_name,
        "reporter": reporter,
        "assignee": assignee,
        "sla_breach": incident.sla_breach,
        "acknowledged_at": incident.acknowledged_at.isoformat() if incident.acknowledged_at else None,
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
        "closed_at": incident.closed_at.isoformat() if incident.closed_at else None,
        "created_at": incident.created_at.isoformat() if incident.created_at else None,
        "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
        "comments": comments,
        "events": events,
        "artifacts": artifacts,
        "latest_rca_id": latest_rca.id if latest_rca else None,
        "latest_rca_status": latest_rca.status if latest_rca else None,
    }


@router.patch("/{incident_id}")
async def update_incident(
    incident_id: str,
    body: UpdateIncidentBody,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Incident).where(models.Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    changes = {}
    now = datetime.now(timezone.utc)

    if body.status is not None:
        new_status = body.status.upper()
        allowed = VALID_TRANSITIONS.get(incident.status, [])
        if new_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transition from {incident.status} to {new_status}. Allowed: {allowed}",
            )
        changes["status"] = (incident.status, new_status)
        incident.status = new_status
        if new_status == "RESOLVED":
            incident.resolved_at = now
        elif new_status == "CLOSED":
            incident.closed_at = now

    for field in ["title", "description", "severity", "category", "affected_component",
                  "business_impact", "environment_name", "assignee_id"]:
        val = getattr(body, field)
        if val is not None:
            old = getattr(incident, field)
            if old != val:
                changes[field] = (old, val)
                setattr(incident, field, val)

    incident.updated_at = now

    if changes:
        event = models.IncidentEvent(
            id=str(uuid.uuid4()),
            incident_id=incident.id,
            event_type="updated",
            description=f"Updated: {', '.join(changes.keys())}",
            actor_id=current_user.id,
            metadata={"changes": {k: {"from": str(v[0]), "to": str(v[1])} for k, v in changes.items()}},
            occurred_at=now,
        )
        db.add(event)

    await log_action(db=db, action="incident.update", user_id=current_user.id,
                     resource_type="incident", resource_id=incident_id, details={"changes": list(changes.keys())})

    return {"id": incident.id, "status": incident.status}


@router.post("/{incident_id}/comments", status_code=201)
async def add_comment(
    incident_id: str,
    body: CommentBody,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Incident).where(models.Incident.id == incident_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Incident not found")

    now = datetime.now(timezone.utc)
    comment = models.IncidentComment(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        author_id=current_user.id,
        content=body.content,
        is_internal=body.is_internal,
        created_at=now,
        updated_at=now,
    )
    db.add(comment)
    await db.flush()

    event = models.IncidentEvent(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        event_type="comment_added",
        description="Comment added",
        actor_id=current_user.id,
        occurred_at=now,
    )
    db.add(event)

    return {"id": comment.id}


@router.post("/{incident_id}/relationships", status_code=201)
async def add_relationship(
    incident_id: str,
    body: RelationshipBody,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    rel = models.IncidentRelationship(
        id=str(uuid.uuid4()),
        source_id=incident_id,
        target_id=body.target_id,
        relationship_type=body.relationship_type,
        created_at=datetime.now(timezone.utc),
    )
    db.add(rel)
    return {"id": rel.id}


@router.post("/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    body: dict = {},
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Incident).where(models.Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    allowed = VALID_TRANSITIONS.get(incident.status, [])
    if "RESOLVED" not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resolve from status {incident.status}",
        )

    now = datetime.now(timezone.utc)
    incident.status = "RESOLVED"
    incident.resolved_at = now
    incident.updated_at = now

    resolution_notes = body.get("resolution_notes", "")
    if resolution_notes:
        comment = models.IncidentComment(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            author_id=current_user.id,
            content=f"Resolution notes: {resolution_notes}",
            is_internal=True,
            created_at=now,
            updated_at=now,
        )
        db.add(comment)

    event = models.IncidentEvent(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        event_type="resolved",
        description="Incident marked as resolved",
        actor_id=current_user.id,
        occurred_at=now,
    )
    db.add(event)
    await log_action(db=db, action="incident.resolve", user_id=current_user.id,
                     resource_type="incident", resource_id=incident_id)
    return {"status": "RESOLVED"}


@router.post("/{incident_id}/reopen")
async def reopen_incident(
    incident_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Incident).where(models.Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    allowed = VALID_TRANSITIONS.get(incident.status, [])
    if "REOPENED" not in allowed:
        raise HTTPException(status_code=400, detail=f"Cannot reopen from {incident.status}")

    now = datetime.now(timezone.utc)
    incident.status = "REOPENED"
    incident.resolved_at = None
    incident.updated_at = now

    event = models.IncidentEvent(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        event_type="reopened",
        description="Incident reopened",
        actor_id=current_user.id,
        occurred_at=now,
    )
    db.add(event)
    await log_action(db=db, action="incident.reopen", user_id=current_user.id,
                     resource_type="incident", resource_id=incident_id)
    return {"status": "REOPENED"}
