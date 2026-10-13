import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.db.session import get_db
from app.db import models
from app.core.security import get_current_active_user
from app.remediation.action_registry import execute_action, list_actions, get_action
from app.services.audit_service import log_action

router = APIRouter(tags=["remediation"])


class ProposeBody(BaseModel):
    action_key: str
    title: str
    description: str
    parameters: Optional[dict] = None
    risk_level: str = "MEDIUM"
    requires_approval: bool = True
    expected_outcome: Optional[str] = None
    rollback_procedure: Optional[str] = None


class ApprovalBody(BaseModel):
    review_notes: Optional[str] = None


@router.get("/remediation/registry")
async def get_registry(current_user=Depends(get_current_active_user)):
    return {"actions": list_actions()}


@router.post("/analyses/{analysis_id}/remediation-proposals", status_code=201)
async def propose_remediation(
    analysis_id: str,
    body: ProposeBody,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    run_result = await db.execute(
        select(models.RCAAnalysisRun).where(models.RCAAnalysisRun.id == analysis_id)
    )
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    if not get_action(body.action_key):
        raise HTTPException(
            status_code=400,
            detail=f"Action '{body.action_key}' not in allowlist. Available: {[a['key'] for a in list_actions()]}",
        )

    now = datetime.now(timezone.utc)
    action = models.RemediationAction(
        id=str(uuid.uuid4()),
        analysis_run_id=analysis_id,
        incident_id=run.incident_id,
        action_key=body.action_key,
        title=body.title,
        description=body.description,
        parameters=body.parameters,
        risk_level=body.risk_level,
        requires_approval=body.requires_approval,
        expected_outcome=body.expected_outcome,
        rollback_procedure=body.rollback_procedure,
        proposed_by_id=current_user.id,
        created_at=now,
    )
    db.add(action)
    await db.flush()

    await log_action(db=db, action="remediation.propose", user_id=current_user.id,
                     resource_type="remediation_action", resource_id=action.id,
                     details={"action_key": body.action_key, "risk_level": body.risk_level})

    return {"id": action.id, "requires_approval": body.requires_approval}


@router.post("/remediation/{action_id}/request-approval", status_code=201)
async def request_approval(
    action_id: str,
    body: dict = {},
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    action_result = await db.execute(
        select(models.RemediationAction).where(models.RemediationAction.id == action_id)
    )
    action = action_result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    now = datetime.now(timezone.utc)
    approval = models.ApprovalRequest(
        id=str(uuid.uuid4()),
        action_id=action_id,
        requested_by_id=current_user.id,
        status="PENDING",
        reason=body.get("reason"),
        expires_at=now + timedelta(hours=24),
        created_at=now,
    )
    db.add(approval)

    # Update incident status
    inc_result = await db.execute(
        select(models.Incident).where(models.Incident.id == action.incident_id)
    )
    incident = inc_result.scalar_one_or_none()
    if incident and incident.status not in ("RESOLVED", "CLOSED"):
        incident.status = "AWAITING_APPROVAL"
        incident.updated_at = now

    await log_action(db=db, action="remediation.request_approval", user_id=current_user.id,
                     resource_type="approval_request", resource_id=approval.id)
    return {"id": approval.id, "status": "PENDING"}


@router.post("/approvals/{approval_id}/approve")
async def approve(
    approval_id: str,
    body: ApprovalBody,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.ApprovalRequest).where(models.ApprovalRequest.id == approval_id)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Approval already {approval.status}")

    now = datetime.now(timezone.utc)
    approval.status = "APPROVED"
    approval.reviewed_by_id = current_user.id
    approval.review_notes = body.review_notes
    approval.reviewed_at = now

    await log_action(db=db, action="remediation.approve", user_id=current_user.id,
                     resource_type="approval_request", resource_id=approval_id)
    return {"status": "APPROVED"}


@router.post("/approvals/{approval_id}/reject")
async def reject(
    approval_id: str,
    body: ApprovalBody,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.ApprovalRequest).where(models.ApprovalRequest.id == approval_id)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Approval already {approval.status}")

    approval.status = "REJECTED"
    approval.reviewed_by_id = current_user.id
    approval.review_notes = body.review_notes
    approval.reviewed_at = datetime.now(timezone.utc)

    await log_action(db=db, action="remediation.reject", user_id=current_user.id,
                     resource_type="approval_request", resource_id=approval_id)
    return {"status": "REJECTED"}


@router.post("/remediation/{action_id}/execute", status_code=202)
async def execute(
    action_id: str,
    body: dict = {},
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    action_result = await db.execute(
        select(models.RemediationAction).where(models.RemediationAction.id == action_id)
    )
    action = action_result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    # Check approval if required
    approval = None
    if action.requires_approval:
        appr_result = await db.execute(
            select(models.ApprovalRequest)
            .where(
                models.ApprovalRequest.action_id == action_id,
                models.ApprovalRequest.status == "APPROVED",
            )
        )
        approval = appr_result.scalar_one_or_none()
        if not approval:
            raise HTTPException(
                status_code=403,
                detail="This action requires approval before execution. Submit for approval first.",
            )

    now = datetime.now(timezone.utc)
    execution = models.RemediationExecution(
        id=str(uuid.uuid4()),
        action_id=action_id,
        approval_id=approval.id if approval else None,
        executed_by_id=current_user.id,
        status="RUNNING",
        started_at=now,
        created_at=now,
    )
    db.add(execution)
    await db.flush()

    # Execute synchronously (for MVP)
    exec_result = await execute_action(
        action_key=action.action_key,
        parameters=action.parameters or {},
    )

    execution.status = "SUCCESS" if exec_result.get("success") else "FAILED"
    execution.output = exec_result.get("output", "")
    execution.error_message = exec_result.get("error")
    execution.completed_at = datetime.now(timezone.utc)

    # Create verification
    is_resolved = exec_result.get("success", False)
    verification = models.VerificationResult(
        id=str(uuid.uuid4()),
        execution_id=execution.id,
        is_resolved=is_resolved,
        verification_method="automated_handler",
        evidence=exec_result.get("output", "")[:1000],
        created_at=datetime.now(timezone.utc),
    )
    db.add(verification)

    await log_action(db=db, action="remediation.execute", user_id=current_user.id,
                     resource_type="remediation_execution", resource_id=execution.id,
                     details={"action_key": action.action_key, "success": is_resolved})

    return {
        "execution_id": execution.id,
        "status": execution.status,
        "output": execution.output,
        "verified_resolved": is_resolved,
    }


@router.get("/remediation/{execution_id}/status")
async def execution_status(
    execution_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.RemediationExecution).where(models.RemediationExecution.id == execution_id)
    )
    exec_ = result.scalar_one_or_none()
    if not exec_:
        raise HTTPException(status_code=404, detail="Execution not found")

    verif = None
    verif_result = await db.execute(
        select(models.VerificationResult).where(models.VerificationResult.execution_id == execution_id)
    )
    v = verif_result.scalar_one_or_none()
    if v:
        verif = {"is_resolved": v.is_resolved, "method": v.verification_method, "evidence": v.evidence}

    return {
        "id": exec_.id,
        "action_id": exec_.action_id,
        "status": exec_.status,
        "output": exec_.output,
        "error_message": exec_.error_message,
        "started_at": exec_.started_at.isoformat() if exec_.started_at else None,
        "completed_at": exec_.completed_at.isoformat() if exec_.completed_at else None,
        "verification": verif,
    }
