import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.db.session import get_db
from app.db import models
from app.core.security import get_current_active_user
from app.llm.provider import get_llm, LLMError
from app.llm.prompts import COPILOT_SYSTEM, COPILOT_CONTEXT_TEMPLATE
from app.services.audit_service import log_action

router = APIRouter(tags=["copilot"])


class CopilotMessageBody(BaseModel):
    message: str


@router.post("/incidents/{incident_id}/copilot/messages")
async def send_message(
    incident_id: str,
    body: CopilotMessageBody,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Load incident
    inc_result = await db.execute(select(models.Incident).where(models.Incident.id == incident_id))
    incident = inc_result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    now = datetime.now(timezone.utc)

    # Save user message
    user_msg = models.CopilotMessage(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        role="user",
        content=body.message,
        user_id=current_user.id,
        created_at=now,
    )
    db.add(user_msg)
    await db.flush()

    # Load context: recent log events
    jobs_result = await db.execute(
        select(models.LogIngestionJob.id).where(models.LogIngestionJob.incident_id == incident_id)
    )
    job_ids = [r[0] for r in jobs_result.all()]

    log_snippet = ""
    if job_ids:
        events_result = await db.execute(
            select(models.LogEvent)
            .where(
                models.LogEvent.ingestion_job_id.in_(job_ids),
                models.LogEvent.level.in_(["ERROR", "CRITICAL", "WARNING"]),
            )
            .order_by(models.LogEvent.timestamp.desc().nullslast())
            .limit(20)
        )
        events = events_result.scalars().all()
        log_lines = []
        for e in events:
            ts = e.timestamp.isoformat() if e.timestamp else "no-ts"
            log_lines.append(f"[{ts}][{e.level}] {e.message[:150]}")
        log_snippet = "\n".join(log_lines) or "No error/warning events found."
    else:
        log_snippet = "No logs uploaded yet."

    # Latest RCA summary
    rca_result = await db.execute(
        select(models.RCAAnalysisRun)
        .where(models.RCAAnalysisRun.incident_id == incident_id, models.RCAAnalysisRun.status == "COMPLETED")
        .order_by(models.RCAAnalysisRun.created_at.desc())
        .limit(1)
    )
    latest_rca = rca_result.scalar_one_or_none()
    rca_summary = latest_rca.summary if latest_rca else "No analysis completed yet."

    # Load history (last 10 messages)
    history_result = await db.execute(
        select(models.CopilotMessage)
        .where(models.CopilotMessage.incident_id == incident_id)
        .order_by(models.CopilotMessage.created_at.asc())
        .limit(10)
    )
    history = history_result.scalars().all()

    # Build context
    context = COPILOT_CONTEXT_TEMPLATE.format(
        title=incident.title,
        number=incident.number,
        severity=incident.severity,
        status=incident.status,
        description=incident.description or "No description.",
        log_excerpt=log_snippet[:3000],
        rca_summary=rca_summary[:1000],
    )

    # Build messages list
    messages_for_llm = [
        {"role": "system", "content": COPILOT_SYSTEM + "\n\n" + context},
    ]
    for msg in history[:-1]:  # All except the just-added user message
        messages_for_llm.append({"role": msg.role, "content": msg.content})
    messages_for_llm.append({"role": "user", "content": body.message})

    # Call LLM
    llm = get_llm()
    try:
        from openai import AsyncOpenAI
        from app.core.config import settings
        import time
        client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        start = time.time()
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages_for_llm,
            temperature=0.3,
            max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
        )
        latency_ms = int((time.time() - start) * 1000)
        reply_content = response.choices[0].message.content or "I couldn't generate a response."

        # Save assistant reply
        assistant_msg = models.CopilotMessage(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            role="assistant",
            content=reply_content,
            created_at=datetime.now(timezone.utc),
        )
        db.add(assistant_msg)

        # LLM usage
        usage = models.LLMUsageRecord(
            id=str(uuid.uuid4()),
            provider=settings.LLM_PROVIDER,
            model=settings.LLM_MODEL,
            operation="copilot",
            incident_id=incident_id,
            prompt_tokens=response.usage.prompt_tokens if response.usage else None,
            completion_tokens=response.usage.completion_tokens if response.usage else None,
            latency_ms=latency_ms,
            success=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add(usage)

        return {"message_id": assistant_msg.id, "reply": reply_content, "role": "assistant"}

    except Exception as e:
        error_msg = f"AI Copilot unavailable: {str(e)}"
        err_reply = models.CopilotMessage(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            role="assistant",
            content=error_msg,
            created_at=datetime.now(timezone.utc),
        )
        db.add(err_reply)
        return {"message_id": err_reply.id, "reply": error_msg, "role": "assistant", "error": True}


@router.get("/incidents/{incident_id}/copilot/history")
async def get_history(
    incident_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.CopilotMessage)
        .where(models.CopilotMessage.incident_id == incident_id)
        .order_by(models.CopilotMessage.created_at.asc())
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in result.scalars().all()
    ]
