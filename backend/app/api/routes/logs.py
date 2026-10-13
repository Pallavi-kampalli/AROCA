import uuid
import os
import aiofiles
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db import models
from app.core.security import get_current_active_user
from app.core.config import settings
from app.services.log_parser import parse_file
from app.services.audit_service import log_action

router = APIRouter(tags=["logs"])

ALLOWED_EXTENSIONS = {".log", ".txt", ".json", ".jsonl", ".csv"}
MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


async def _ingest_logs(
    incident_id: str,
    artifact_id: str,
    job_id: str,
    storage_path: str,
    original_filename: str,
    db_session_factory,
):
    """Background task: parse uploaded log file and persist events."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            # Update job status
            job_result = await db.execute(
                select(models.LogIngestionJob).where(models.LogIngestionJob.id == job_id)
            )
            job = job_result.scalar_one()
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

            # Read file
            async with aiofiles.open(storage_path, "r", encoding="utf-8", errors="replace") as f:
                content = await f.read()

            # Parse
            parsed_count = 0
            failed_count = 0
            total_lines = 0
            events_to_insert = []

            for line_num, event_dict in parse_file(content, original_filename):
                total_lines = max(total_lines, line_num)
                if event_dict.get("parse_error"):
                    failed_count += 1
                else:
                    log_event = models.LogEvent(
                        id=str(uuid.uuid4()),
                        ingestion_job_id=job_id,
                        line_number=event_dict.get("line_number"),
                        timestamp=event_dict.get("timestamp"),
                        level=event_dict.get("level", "UNKNOWN"),
                        source=event_dict.get("source"),
                        message=event_dict.get("message", "")[:2000],
                        raw_line=event_dict.get("raw_line", "")[:2000],
                        correlation_id=event_dict.get("correlation_id"),
                        service_name=event_dict.get("service_name"),
                        extra_fields=event_dict.get("extra_fields"),
                        is_anomalous=False,
                    )
                    events_to_insert.append(log_event)
                    parsed_count += 1

                    # Insert in batches
                    if len(events_to_insert) >= 500:
                        db.add_all(events_to_insert)
                        await db.flush()
                        events_to_insert = []

            if events_to_insert:
                db.add_all(events_to_insert)
                await db.flush()

            # Update job
            job.status = "completed"
            job.total_lines = total_lines
            job.parsed_events = parsed_count
            job.failed_lines = failed_count
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            async with AsyncSessionLocal() as err_db:
                err_result = await err_db.execute(
                    select(models.LogIngestionJob).where(models.LogIngestionJob.id == job_id)
                )
                err_job = err_result.scalar_one_or_none()
                if err_job:
                    err_job.status = "failed"
                    err_job.error_message = str(e)[:1000]
                    err_job.completed_at = datetime.now(timezone.utc)
                    await err_db.commit()


@router.post("/incidents/{incident_id}/logs", status_code=201)
async def upload_logs(
    incident_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate incident exists
    inc_result = await db.execute(select(models.Incident).where(models.Incident.id == incident_id))
    if not inc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Incident not found")

    # Validate file extension
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Read and validate size
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    # Save file
    now = datetime.now(timezone.utc)
    safe_name = f"{str(uuid.uuid4())}{ext}"
    incident_dir = os.path.join(settings.UPLOAD_DIR, incident_id)
    os.makedirs(incident_dir, exist_ok=True)
    storage_path = os.path.join(incident_dir, safe_name)

    async with aiofiles.open(storage_path, "wb") as f:
        await f.write(content)

    # Create artifact record
    artifact = models.UploadedArtifact(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        filename=safe_name,
        original_filename=file.filename[:255],
        content_type=file.content_type or "application/octet-stream",
        file_size_bytes=len(content),
        storage_path=storage_path,
        uploader_id=current_user.id,
        created_at=now,
    )
    db.add(artifact)
    await db.flush()

    # Create ingestion job
    job = models.LogIngestionJob(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        artifact_id=artifact.id,
        status="pending",
        created_at=now,
    )
    db.add(job)
    await db.flush()

    await log_action(db=db, action="log.upload", user_id=current_user.id,
                     resource_type="uploaded_artifact", resource_id=artifact.id,
                     details={"incident_id": incident_id, "filename": file.filename})

    # Start background ingestion
    background_tasks.add_task(
        _ingest_logs, incident_id, artifact.id, job.id, storage_path, file.filename, None
    )

    return {
        "artifact_id": artifact.id,
        "job_id": job.id,
        "filename": file.filename,
        "status": "pending",
        "message": "Log file accepted. Parsing in background.",
    }


@router.get("/incidents/{incident_id}/logs")
async def get_logs(
    incident_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    level: Optional[str] = None,
    search: Optional[str] = None,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Get all jobs for this incident
    jobs_result = await db.execute(
        select(models.LogIngestionJob.id).where(models.LogIngestionJob.incident_id == incident_id)
    )
    job_ids = [r[0] for r in jobs_result.all()]

    if not job_ids:
        return {"total": 0, "items": [], "jobs": []}

    # Log events query
    from sqlalchemy import or_
    q = select(models.LogEvent).where(models.LogEvent.ingestion_job_id.in_(job_ids))
    if level:
        q = q.where(models.LogEvent.level == level.upper())
    if search:
        q = q.where(models.LogEvent.message.ilike(f"%{search}%"))

    from sqlalchemy import func
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(models.LogEvent.timestamp.asc().nullslast()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    events = result.scalars().all()

    # Job summaries
    jobs_full_result = await db.execute(
        select(models.LogIngestionJob).where(models.LogIngestionJob.incident_id == incident_id)
    )
    jobs_info = [
        {
            "id": j.id,
            "status": j.status,
            "parsed_events": j.parsed_events,
            "failed_lines": j.failed_lines,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs_full_result.scalars().all()
    ]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "jobs": jobs_info,
        "items": [
            {
                "id": e.id,
                "line_number": e.line_number,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "level": e.level,
                "source": e.source,
                "message": e.message,
                "service_name": e.service_name,
                "correlation_id": e.correlation_id,
                "is_anomalous": e.is_anomalous,
                "anomaly_score": e.anomaly_score,
            }
            for e in events
        ],
    }


@router.get("/logs/{log_event_id}")
async def get_log_event(
    log_event_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.LogEvent).where(models.LogEvent.id == log_event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Log event not found")
    return {
        "id": event.id,
        "ingestion_job_id": event.ingestion_job_id,
        "line_number": event.line_number,
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        "level": event.level,
        "source": event.source,
        "message": event.message,
        "raw_line": event.raw_line,
        "service_name": event.service_name,
        "correlation_id": event.correlation_id,
        "extra_fields": event.extra_fields,
        "is_anomalous": event.is_anomalous,
        "anomaly_score": event.anomaly_score,
    }
