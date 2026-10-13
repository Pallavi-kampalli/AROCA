"""
Remediation action registry: allowlisted actions with typed parameters.
No arbitrary shell execution. Actions are bounded and audited.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field


@dataclass
class ActionDefinition:
    key: str
    name: str
    description: str
    risk_level: str  # LOW / MEDIUM / HIGH / CRITICAL
    requires_approval: bool
    timeout_seconds: int
    parameters_schema: Dict[str, str] = field(default_factory=dict)
    handler: Optional[Callable] = None


# ─── Registered Action Handlers ─────────────────────────────────────────────

async def _health_check_handler(params: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate a health check against the incident's service."""
    await asyncio.sleep(1)
    service = params.get("service_name", "unknown-service")
    return {
        "success": True,
        "output": f"Health check executed for service '{service}'. HTTP 200 OK received.",
        "details": {
            "service": service,
            "status": "healthy",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
    }


async def _reprocess_job_handler(params: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate reprocessing a failed job."""
    await asyncio.sleep(2)
    job_id = params.get("job_id", "unknown-job")
    return {
        "success": True,
        "output": f"Job '{job_id}' requeued for reprocessing. Check job status in 5 minutes.",
        "details": {"job_id": job_id, "queued_at": datetime.now(timezone.utc).isoformat()},
    }


async def _retry_task_handler(params: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate bounded retry of a failed task."""
    max_retries = min(int(params.get("max_retries", 3)), 3)
    task_name = params.get("task_name", "unknown-task")
    await asyncio.sleep(1)
    return {
        "success": True,
        "output": f"Task '{task_name}' scheduled for retry (max {max_retries} attempts).",
        "details": {"task_name": task_name, "max_retries": max_retries},
    }


async def _review_config_handler(params: Dict[str, Any]) -> Dict[str, Any]:
    """Flag a configuration item for human review — no changes made."""
    config_item = params.get("config_item", "unspecified configuration")
    return {
        "success": True,
        "output": f"Configuration review ticket created for: {config_item}. No changes were made automatically.",
        "details": {"config_item": config_item, "action": "review_only"},
    }


async def _escalate_handler(params: Dict[str, Any]) -> Dict[str, Any]:
    """Record an escalation — requires human to complete."""
    team = params.get("escalation_team", "Platform Engineering")
    reason = params.get("reason", "Further investigation required")
    return {
        "success": True,
        "output": f"Escalation recorded to {team}. Reason: {reason}. A human engineer must follow up.",
        "details": {"team": team, "reason": reason, "note": "Human action required"},
    }


# ─── Registry ─────────────────────────────────────────────────────────────────

ACTION_REGISTRY: Dict[str, ActionDefinition] = {
    "health_check": ActionDefinition(
        key="health_check",
        name="Run Service Health Check",
        description="Execute a health check against the affected service to verify its current status.",
        risk_level="LOW",
        requires_approval=False,
        timeout_seconds=30,
        parameters_schema={"service_name": "string"},
        handler=_health_check_handler,
    ),
    "reprocess_job": ActionDefinition(
        key="reprocess_job",
        name="Reprocess Failed Job",
        description="Requeue a specific failed background job for reprocessing.",
        risk_level="MEDIUM",
        requires_approval=True,
        timeout_seconds=60,
        parameters_schema={"job_id": "string"},
        handler=_reprocess_job_handler,
    ),
    "retry_task": ActionDefinition(
        key="retry_task",
        name="Retry Failed Task",
        description="Retry a failed task with a bounded retry count (maximum 3 attempts).",
        risk_level="LOW",
        requires_approval=False,
        timeout_seconds=60,
        parameters_schema={"task_name": "string", "max_retries": "integer (1-3)"},
        handler=_retry_task_handler,
    ),
    "review_config": ActionDefinition(
        key="review_config",
        name="Flag Configuration for Review",
        description="Mark a configuration item for human review. No automated changes are made.",
        risk_level="LOW",
        requires_approval=False,
        timeout_seconds=5,
        parameters_schema={"config_item": "string"},
        handler=_review_config_handler,
    ),
    "escalate": ActionDefinition(
        key="escalate",
        name="Escalate to Engineering Team",
        description="Record a formal escalation to the specified team. Human follow-up is required.",
        risk_level="LOW",
        requires_approval=False,
        timeout_seconds=5,
        parameters_schema={"escalation_team": "string", "reason": "string"},
        handler=_escalate_handler,
    ),
}


def get_action(key: str) -> Optional[ActionDefinition]:
    return ACTION_REGISTRY.get(key)


def list_actions() -> list:
    return [
        {
            "key": a.key,
            "name": a.name,
            "description": a.description,
            "risk_level": a.risk_level,
            "requires_approval": a.requires_approval,
            "parameters_schema": a.parameters_schema,
        }
        for a in ACTION_REGISTRY.values()
    ]


async def execute_action(
    action_key: str,
    parameters: Dict[str, Any],
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    """Execute a registered action with timeout."""
    definition = get_action(action_key)
    if not definition:
        return {
            "success": False,
            "error": f"Action '{action_key}' is not in the allowlist. Only registered actions can execute.",
        }
    if not definition.handler:
        return {
            "success": False,
            "error": f"Action '{action_key}' has no configured handler in this environment.",
        }
    try:
        result = await asyncio.wait_for(
            definition.handler(parameters),
            timeout=min(timeout_seconds, definition.timeout_seconds),
        )
        return result
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": f"Action timed out after {definition.timeout_seconds}s",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
