import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from app.db.session import get_db
from app.db import models
from app.core.security import get_current_active_user

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class CreateDocBody(BaseModel):
    title: str
    content: str
    source_incident_id: Optional[str] = None
    tags: Optional[list] = None


@router.post("/documents", status_code=201)
async def create_document(
    body: CreateDocBody,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    doc = models.KnowledgeDocument(
        id=str(uuid.uuid4()),
        title=body.title,
        content=body.content,
        source_incident_id=body.source_incident_id,
        tags=body.tags,
        created_by_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(doc)
    await db.flush()

    # Create chunk
    chunk = models.KnowledgeChunk(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        chunk_index=0,
        content=body.content[:4000],
        created_at=now,
    )
    db.add(chunk)

    return {"id": doc.id}


@router.get("/search")
async def search_knowledge(
    q: str = Query(default="", description="Search query"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(models.KnowledgeDocument)
    if q:
        query = query.where(
            models.KnowledgeDocument.title.ilike(f"%{q}%") |
            models.KnowledgeDocument.content.ilike(f"%{q}%")
        )
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.order_by(models.KnowledgeDocument.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    docs = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": d.id,
                "title": d.title,
                "content_preview": d.content[:200],
                "is_verified": d.is_verified,
                "source_incident_id": d.source_incident_id,
                "tags": d.tags,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ],
    }


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.KnowledgeDocument).where(models.KnowledgeDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "is_verified": doc.is_verified,
        "source_incident_id": doc.source_incident_id,
        "tags": doc.tags,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }
