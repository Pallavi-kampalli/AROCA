"""
RCA Engine: combines ML anomaly findings + LLM analysis + historical retrieval.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db import models
from app.ml.feature_extractor import extract_features
from app.ml.anomaly_detector import get_detector
from app.llm.provider import get_llm, LLMError
from app.llm.prompts import (
    RCA_SYSTEM, RCA_USER_TEMPLATE,
    COPILOT_SYSTEM, COPILOT_CONTEXT_TEMPLATE,
)
from app.services.audit_service import log_action
import structlog

logger = structlog.get_logger()

MAX_LOG_EVENTS_FOR_LLM = 50
MAX_EVIDENCE_CHARS = 8000


async def run_rca(
    incident_id: str,
    db: AsyncSession,
    triggered_by_id: Optional[str] = None,
) -> models.RCAAnalysisRun:
    """
    Main RCA orchestration. Creates a run record, performs ML + LLM analysis,
    saves candidate causes and evidence links.
    """
    now = datetime.now(timezone.utc)

    # Create run record
    run = models.RCAAnalysisRun(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        status=models.AnalysisStatus.RUNNING,
        started_at=now,
        created_at=now,
        triggered_by_id=triggered_by_id,
        llm_provider=__import__('app.core.config', fromlist=['settings']).settings.LLM_PROVIDER,
        llm_model=__import__('app.core.config', fromlist=['settings']).settings.LLM_MODEL,
    )
    db.add(run)
    await db.flush()

    try:
        # Load incident
        incident_result = await db.execute(
            select(models.Incident).where(models.Incident.id == incident_id)
        )
        incident = incident_result.scalar_one_or_none()
        if not incident:
            run.status = models.AnalysisStatus.FAILED
            run.error_message = "Incident not found"
            return run

        # Load log events
        jobs_result = await db.execute(
            select(models.LogIngestionJob).where(
                models.LogIngestionJob.incident_id == incident_id,
                models.LogIngestionJob.status == "completed",
            )
        )
        jobs = jobs_result.scalars().all()

        all_events = []
        for job in jobs:
            events_result = await db.execute(
                select(models.LogEvent).where(
                    models.LogEvent.ingestion_job_id == job.id
                ).order_by(models.LogEvent.timestamp.asc().nullslast()).limit(500)
            )
            all_events.extend(events_result.scalars().all())

        if not all_events:
            run.status = models.AnalysisStatus.INSUFFICIENT_DATA
            run.error_message = "No parsed log events available. Upload and ingest logs first."
            run.completed_at = datetime.now(timezone.utc)
            return run

        # ML inference
        event_dicts = [
            {
                "timestamp": e.timestamp,
                "level": e.level,
                "source": e.source,
                "message": e.message,
            }
            for e in all_events
        ]

        ml_result = {"data_sufficient": False, "explanation": "Insufficient data for ML inference"}
        ml_record = None

        feature_vec, feature_names, status_msg = extract_features(event_dicts)
        if feature_vec is not None:
            detector = get_detector()
            ml_result = detector.predict(feature_vec, feature_names)

            # Load or find active ML model record
            model_result = await db.execute(
                select(models.MLModel).where(models.MLModel.is_active == True).limit(1)
            )
            ml_model = model_result.scalar_one_or_none()

            if ml_model:
                ml_record = models.MLInferenceResult(
                    id=str(uuid.uuid4()),
                    model_id=ml_model.id,
                    incident_id=incident_id,
                    ingestion_job_id=jobs[0].id if jobs else None,
                    anomaly_score=ml_result.get("anomaly_score"),
                    is_anomalous=ml_result.get("is_anomalous", False),
                    features_used={name: float(val) for name, val in zip(feature_names, feature_vec)},
                    contributing_features=ml_result.get("contributing_features"),
                    data_sufficient=ml_result.get("data_sufficient", False),
                    explanation=ml_result.get("explanation"),
                    created_at=datetime.now(timezone.utc),
                )
                db.add(ml_record)
                await db.flush()
                run.ml_inference_id = ml_record.id

        # Build log excerpt for LLM (bounded)
        error_events = [e for e in all_events if e.level in ("ERROR", "CRITICAL")]
        warning_events = [e for e in all_events if e.level == "WARNING"]
        other_events = [e for e in all_events if e.level not in ("ERROR", "CRITICAL", "WARNING")]

        selected_events = (
            error_events[:20] +
            warning_events[:15] +
            other_events[:15]
        )[:MAX_LOG_EVENTS_FOR_LLM]

        log_lines = []
        for e in selected_events:
            ts = e.timestamp.isoformat() if e.timestamp else "no-timestamp"
            log_lines.append(f"[{ts}] [{e.level}] [{e.source or 'unknown'}] {e.message[:200]}")

        log_excerpt = "\n".join(log_lines)[:MAX_EVIDENCE_CHARS]

        # ML findings summary
        ml_findings = ml_result.get("explanation", "ML inference not available.")
        if ml_result.get("contributing_features"):
            cf = ml_result["contributing_features"][:3]
            ml_findings += f"\nTop contributing features: {json.dumps(cf)}"

        # Historical context (similar resolved incidents)
        historical_result = await db.execute(
            select(models.Incident).where(
                models.Incident.status.in_(["RESOLVED", "CLOSED"]),
                models.Incident.id != incident_id,
            ).order_by(models.Incident.created_at.desc()).limit(3)
        )
        historical = historical_result.scalars().all()

        historical_lines = []
        for h in historical:
            historical_lines.append(
                f"- {h.number}: {h.title} (Severity: {h.severity}, Category: {h.category or 'N/A'})"
            )
        historical_context = "\n".join(historical_lines) or "No resolved incidents in history yet."

        # Build LLM prompt
        user_prompt = RCA_USER_TEMPLATE.format(
            title=incident.title,
            severity=incident.severity,
            description=incident.description or "No description provided.",
            event_count=len(all_events),
            log_excerpt=log_excerpt or "No log content available.",
            ml_findings=ml_findings,
            historical_context=historical_context,
        )

        # Call LLM
        llm = get_llm()
        try:
            llm_result = await llm.complete(
                system_prompt=RCA_SYSTEM,
                user_prompt=user_prompt,
                operation="rca",
                incident_id=incident_id,
            )

            run.prompt_tokens = llm_result.get("prompt_tokens")
            run.completion_tokens = llm_result.get("completion_tokens")
            run.latency_ms = llm_result.get("latency_ms")

            # Parse JSON response
            content = llm_result["content"].strip()
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)
            run.summary = parsed.get("summary", "")

            # Persist candidate causes
            for cause_data in parsed.get("candidate_causes", []):
                cause = models.RCACandidateCause(
                    id=str(uuid.uuid4()),
                    analysis_run_id=run.id,
                    rank=cause_data.get("rank", 0),
                    description=cause_data.get("description", ""),
                    confidence_label=cause_data.get("confidence_label", "UNCERTAIN"),
                    confidence_score=cause_data.get("confidence_score"),
                    supporting_evidence=cause_data.get("supporting_evidence", []),
                    contradicting_evidence=cause_data.get("contradicting_evidence", []),
                    missing_evidence=cause_data.get("missing_evidence", []),
                    affected_components=cause_data.get("affected_components", []),
                    relevant_timestamps=cause_data.get("relevant_timestamps", []),
                    created_at=datetime.now(timezone.utc),
                )
                db.add(cause)
                await db.flush()

                # Link to ML evidence if anomalous
                if ml_record and ml_result.get("is_anomalous"):
                    link = models.RCAEvidenceLink(
                        id=str(uuid.uuid4()),
                        cause_id=cause.id,
                        evidence_type="ml_anomaly",
                        reference_id=ml_record.id,
                        reference_table="ml_inference_results",
                        description=ml_result.get("explanation", "ML anomaly detected"),
                        relevance_score=0.8,
                    )
                    db.add(link)

                # Link log evidence
                for i, ev_item in enumerate(cause_data.get("supporting_evidence", [])[:3]):
                    link = models.RCAEvidenceLink(
                        id=str(uuid.uuid4()),
                        cause_id=cause.id,
                        evidence_type="log_evidence",
                        reference_id=None,
                        reference_table="log_events",
                        description=str(ev_item)[:500],
                        relevance_score=0.9 - (i * 0.1),
                    )
                    db.add(link)

            # Persist remediation proposals
            for action_data in parsed.get("recommended_actions", []):
                action = models.RemediationAction(
                    id=str(uuid.uuid4()),
                    analysis_run_id=run.id,
                    incident_id=incident_id,
                    action_key=action_data.get("action_key", "general"),
                    title=action_data.get("title", ""),
                    description=action_data.get("description", ""),
                    risk_level=action_data.get("risk_level", "MEDIUM"),
                    requires_approval=action_data.get("requires_approval", True),
                    expected_outcome=action_data.get("expected_outcome"),
                    rollback_procedure=action_data.get("rollback_procedure"),
                    proposed_by_id=triggered_by_id,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(action)

            # Historical incident links
            for h in historical:
                link = models.HistoricalIncidentLink(
                    id=str(uuid.uuid4()),
                    analysis_run_id=run.id,
                    similar_incident_id=h.id,
                    similarity_score=0.5,
                    resolution_applicable=(h.status in ("RESOLVED", "CLOSED")),
                    created_at=datetime.now(timezone.utc),
                )
                db.add(link)

            run.status = models.AnalysisStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)

            # Record LLM usage
            usage = models.LLMUsageRecord(
                id=str(uuid.uuid4()),
                provider=llm_result.get("provider"),
                model=llm_result.get("model"),
                operation="rca",
                incident_id=incident_id,
                prompt_tokens=llm_result.get("prompt_tokens"),
                completion_tokens=llm_result.get("completion_tokens"),
                latency_ms=llm_result.get("latency_ms"),
                success=True,
                created_at=datetime.now(timezone.utc),
            )
            db.add(usage)

        except LLMError as e:
            run.status = models.AnalysisStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)
            usage = models.LLMUsageRecord(
                id=str(uuid.uuid4()),
                provider=__import__('app.core.config', fromlist=['settings']).settings.LLM_PROVIDER,
                model=__import__('app.core.config', fromlist=['settings']).settings.LLM_MODEL,
                operation="rca",
                incident_id=incident_id,
                success=False,
                error_message=str(e),
                created_at=datetime.now(timezone.utc),
            )
            db.add(usage)

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            run.status = models.AnalysisStatus.FAILED
            run.error_message = f"Failed to parse LLM response: {str(e)}"
            run.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        run.status = models.AnalysisStatus.FAILED
        run.error_message = f"Unexpected error: {str(e)}"
        run.completed_at = datetime.now(timezone.utc)

    await log_action(
        db=db,
        action="rca.run",
        user_id=triggered_by_id,
        resource_type="rca_analysis_run",
        resource_id=run.id,
        details={"incident_id": incident_id, "status": run.status},
    )

    return run
