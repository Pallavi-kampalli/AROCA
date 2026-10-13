import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db import models
from app.core.security import get_current_active_user
from app.rca.engine import run_rca
from app.services.audit_service import log_action

router = APIRouter(tags=["analysis"])


@router.post("/incidents/{incident_id}/analyze", status_code=202)
async def trigger_analysis(
    incident_id: str,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Incident).where(models.Incident.id == incident_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Incident not found")

    # Check for any running analysis
    running = await db.execute(
        select(models.RCAAnalysisRun).where(
            models.RCAAnalysisRun.incident_id == incident_id,
            models.RCAAnalysisRun.status == "RUNNING",
        )
    )
    if running.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Analysis already running for this incident")

    background_tasks.add_task(_run_analysis_bg, incident_id, current_user.id)
    return {"message": "Analysis started", "incident_id": incident_id}


async def _run_analysis_bg(incident_id: str, user_id: str):
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await run_rca(incident_id, db, triggered_by_id=user_id)
        await db.commit()


@router.get("/incidents/{incident_id}/analyses")
async def list_analyses(
    incident_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.RCAAnalysisRun)
        .where(models.RCAAnalysisRun.incident_id == incident_id)
        .order_by(models.RCAAnalysisRun.created_at.desc())
    )
    runs = result.scalars().all()
    return [
        {
            "id": r.id,
            "status": r.status,
            "llm_provider": r.llm_provider,
            "llm_model": r.llm_model,
            "summary": r.summary,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "error_message": r.error_message,
        }
        for r in runs
    ]


@router.get("/analyses/{analysis_id}")
async def get_analysis(
    analysis_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.RCAAnalysisRun).where(models.RCAAnalysisRun.id == analysis_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Candidate causes
    causes_result = await db.execute(
        select(models.RCACandidateCause)
        .where(models.RCACandidateCause.analysis_run_id == analysis_id)
        .order_by(models.RCACandidateCause.rank.asc())
    )
    causes = []
    for c in causes_result.scalars().all():
        # Evidence links
        links_result = await db.execute(
            select(models.RCAEvidenceLink).where(models.RCAEvidenceLink.cause_id == c.id)
        )
        links = [
            {
                "id": l.id,
                "evidence_type": l.evidence_type,
                "reference_id": l.reference_id,
                "reference_table": l.reference_table,
                "description": l.description,
                "relevance_score": l.relevance_score,
            }
            for l in links_result.scalars().all()
        ]
        causes.append({
            "id": c.id,
            "rank": c.rank,
            "description": c.description,
            "confidence_label": c.confidence_label,
            "confidence_score": c.confidence_score,
            "supporting_evidence": c.supporting_evidence,
            "contradicting_evidence": c.contradicting_evidence,
            "missing_evidence": c.missing_evidence,
            "affected_components": c.affected_components,
            "relevant_timestamps": c.relevant_timestamps,
            "human_validated": c.human_validated,
            "evidence_links": links,
        })

    # Remediation proposals
    remediation_result = await db.execute(
        select(models.RemediationAction).where(models.RemediationAction.analysis_run_id == analysis_id)
    )
    actions = [
        {
            "id": a.id,
            "action_key": a.action_key,
            "title": a.title,
            "description": a.description,
            "risk_level": a.risk_level,
            "requires_approval": a.requires_approval,
            "expected_outcome": a.expected_outcome,
            "rollback_procedure": a.rollback_procedure,
        }
        for a in remediation_result.scalars().all()
    ]

    # Historical links
    hist_result = await db.execute(
        select(models.HistoricalIncidentLink).where(
            models.HistoricalIncidentLink.analysis_run_id == analysis_id
        )
    )
    historical = [
        {
            "similar_incident_id": h.similar_incident_id,
            "similarity_score": h.similarity_score,
            "resolution_applicable": h.resolution_applicable,
        }
        for h in hist_result.scalars().all()
    ]

    # ML result
    ml_info = None
    if run.ml_inference_id:
        ml_result = await db.execute(
            select(models.MLInferenceResult).where(models.MLInferenceResult.id == run.ml_inference_id)
        )
        ml = ml_result.scalar_one_or_none()
        if ml:
            ml_info = {
                "anomaly_score": ml.anomaly_score,
                "is_anomalous": ml.is_anomalous,
                "data_sufficient": ml.data_sufficient,
                "explanation": ml.explanation,
                "contributing_features": ml.contributing_features,
            }

    return {
        "id": run.id,
        "incident_id": run.incident_id,
        "status": run.status,
        "llm_provider": run.llm_provider,
        "llm_model": run.llm_model,
        "summary": run.summary,
        "error_message": run.error_message,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "latency_ms": run.latency_ms,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "candidate_causes": causes,
        "remediation_proposals": actions,
        "historical_incidents": historical,
        "ml_findings": ml_info,
    }
