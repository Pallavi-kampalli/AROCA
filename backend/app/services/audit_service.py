"""
Audit logging service - append-only records of sensitive actions.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import models
import uuid


async def log_action(
    db: AsyncSession,
    action: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> models.AuditLog:
    entry = models.AuditLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip_address,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.flush()
    return entry
