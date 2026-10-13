import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.db import models
from app.core.security import get_current_active_user
from app.ml.anomaly_detector import get_detector
from app.ml.feature_extractor import extract_features_batch
from app.llm.provider import get_llm
from app.services.audit_service import log_action

router = APIRouter(tags=["models"])


@router.get("/models/status")
async def model_status(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    detector = get_detector()
    llm = get_llm()
    llm_status = await llm.check_availability()

    # DB model records
    models_result = await db.execute(
        select(models.MLModel).order_by(models.MLModel.created_at.desc()).limit(5)
    )
    model_records = [
        {
            "id": m.id,
            "name": m.name,
            "model_type": m.model_type,
            "version": m.version,
            "is_active": m.is_active,
            "training_samples": m.training_samples,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in models_result.scalars().all()
    ]

    training_runs_result = await db.execute(
        select(models.MLTrainingRun).order_by(models.MLTrainingRun.created_at.desc()).limit(5)
    )
    training_runs = [
        {
            "id": r.id,
            "model_id": r.model_id,
            "status": r.status,
            "samples_used": r.samples_used,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "error_message": r.error_message,
        }
        for r in training_runs_result.scalars().all()
    ]

    total_inferences = await db.scalar(select(func.count(models.MLInferenceResult.id))) or 0
    anomaly_count = await db.scalar(
        select(func.count(models.MLInferenceResult.id)).where(models.MLInferenceResult.is_anomalous == True)
    ) or 0

    return {
        "isolation_forest": {
            "trained": detector.is_trained(),
            "training_samples": detector.training_samples,
            "trained_at": detector.trained_at.isoformat() if detector.trained_at else None,
            "features": detector.feature_names,
        },
        "llm": llm_status,
        "model_records": model_records,
        "training_runs": training_runs,
        "total_inferences": total_inferences,
        "anomaly_detections": anomaly_count,
    }


@router.post("/models/train")
async def train_model(
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Count available completed ingestion jobs
    jobs_result = await db.execute(
        select(models.LogIngestionJob).where(models.LogIngestionJob.status == "completed")
    )
    jobs = jobs_result.scalars().all()

    if len(jobs) < 2:
        return {
            "status": "insufficient_data",
            "message": f"Need at least 2 completed log ingestion jobs to train. Have {len(jobs)}.",
        }

    now = datetime.now(timezone.utc)
    # Create model record
    model_record = models.MLModel(
        id=str(uuid.uuid4()),
        name="Isolation Forest Anomaly Detector",
        model_type="isolation_forest",
        version=f"v{now.strftime('%Y%m%d%H%M%S')}",
        is_active=False,
        created_at=now,
    )
    db.add(model_record)
    await db.flush()

    training_run = models.MLTrainingRun(
        id=str(uuid.uuid4()),
        model_id=model_record.id,
        status="pending",
        created_at=now,
    )
    db.add(training_run)
    await db.flush()

    await log_action(db=db, action="ml.train", user_id=current_user.id,
                     resource_type="ml_training_run", resource_id=training_run.id)

    background_tasks.add_task(_train_bg, model_record.id, training_run.id, [j.id for j in jobs])
    return {"training_run_id": training_run.id, "status": "pending"}


async def _train_bg(model_id: str, training_run_id: str, job_ids: list):
    from app.db.session import AsyncSessionLocal
    import numpy as np

    async with AsyncSessionLocal() as db:
        try:
            run_result = await db.execute(
                select(models.MLTrainingRun).where(models.MLTrainingRun.id == training_run_id)
            )
            training_run = run_result.scalar_one()
            training_run.status = "running"
            training_run.started_at = datetime.now(timezone.utc)
            await db.commit()

            # Load events per job
            events_by_job = {}
            for job_id in job_ids:
                events_result = await db.execute(
                    select(models.LogEvent).where(models.LogEvent.ingestion_job_id == job_id).limit(500)
                )
                events = events_result.scalars().all()
                events_by_job[job_id] = [
                    {"timestamp": e.timestamp, "level": e.level, "source": e.source, "message": e.message}
                    for e in events
                ]

            X, feature_names, status_msg = extract_features_batch(events_by_job)
            if X is None:
                training_run.status = "failed"
                training_run.error_message = status_msg
                training_run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            detector = get_detector()
            result = detector.train(X, feature_names)

            if result.get("success"):
                training_run.status = "completed"
                training_run.samples_used = result.get("samples", 0)
                training_run.features_count = len(feature_names)
                training_run.metrics = {k: v for k, v in result.items() if k != "success"}

                # Update model record
                model_result = await db.execute(
                    select(models.MLModel).where(models.MLModel.id == model_id)
                )
                model = model_result.scalar_one()
                model.is_active = True
                model.training_samples = result.get("samples", 0)
                model.features_used = feature_names
                model.artifact_path = detector.model_path

                # Deactivate other models
                other_result = await db.execute(
                    select(models.MLModel).where(
                        models.MLModel.id != model_id,
                        models.MLModel.is_active == True,
                    )
                )
                for other in other_result.scalars().all():
                    other.is_active = False
            else:
                training_run.status = "failed"
                training_run.error_message = result.get("error", "Training failed")

            training_run.completed_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            async with AsyncSessionLocal() as err_db:
                err_result = await err_db.execute(
                    select(models.MLTrainingRun).where(models.MLTrainingRun.id == training_run_id)
                )
                t = err_result.scalar_one_or_none()
                if t:
                    t.status = "failed"
                    t.error_message = str(e)[:500]
                    t.completed_at = datetime.now(timezone.utc)
                    await err_db.commit()


@router.get("/models/training-runs")
async def list_training_runs(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.MLTrainingRun).order_by(models.MLTrainingRun.created_at.desc()).limit(20)
    )
    return [
        {
            "id": r.id,
            "model_id": r.model_id,
            "status": r.status,
            "samples_used": r.samples_used,
            "features_count": r.features_count,
            "metrics": r.metrics,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in result.scalars().all()
    ]


@router.get("/audit/events")
async def list_audit_events(
    page: int = 1,
    page_size: int = 50,
    action: str = None,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(models.AuditLog)
    if action:
        q = q.where(models.AuditLog.action.ilike(f"%{action}%"))
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(models.AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    logs = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": l.id,
                "action": l.action,
                "user_id": l.user_id,
                "resource_type": l.resource_type,
                "resource_id": l.resource_id,
                "details": l.details,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ],
    }
