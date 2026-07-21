"""Knowledge base management API (AgentService phase 2b-i).

REST surface:
    GET    /api/knowledge-bases                      list all KBs (+doc counts)
    POST   /api/knowledge-bases                      create a KB
    GET    /api/knowledge-bases/{kb_id}               read a KB
    PATCH  /api/knowledge-bases/{kb_id}              rename / update description
    DELETE /api/knowledge-bases/{kb_id}              delete a KB (cascades docs)
    GET    /api/knowledge-bases/{kb_id}/documents    list docs in a KB
    POST   /api/knowledge-bases/{kb_id}/documents    upload a .md/.txt document
    DELETE /api/knowledge-bases/{kb_id}/documents/{doc_id}  remove document

Doc upload is multipart form: ``file`` is the only field. The router decodes
UTF-8 text and passes it to KnowledgeService.add_document which handles
chunking + chromadb indexing synchronously.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models import KnowledgeDoc
from app.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
    KnowledgeDocOut,
)
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)
router = APIRouter()

# Cap upload size to 1MB to keep synchronous indexing responsive.
# Larger docs should be split by the user (markdown notes are rarely that big).
_MAX_UPLOAD_BYTES = 1 * 1024 * 1024
_ALLOWED_DOC_SUFFIXES = (".md", ".markdown", ".txt")


async def _load_kb(db: AsyncSession, kb_id: str) -> bool:
    svc = KnowledgeService(db)
    kb = await svc.get_kb(kb_id)
    return kb is not None


@router.get("/knowledge-bases")
async def list_knowledge_bases(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    svc = KnowledgeService(db)
    kbs = await svc.list_kbs()
    # Batch count documents per KB in one query to avoid N+1.
    counts: dict[str, int] = {}
    if kbs:
        rows = await db.execute(
            select(KnowledgeDoc.knowledge_base_id, func.count(KnowledgeDoc.id))
            .where(KnowledgeDoc.knowledge_base_id.in_([kb.id for kb in kbs]))
            .group_by(KnowledgeDoc.knowledge_base_id)
        )
        counts = {kb_id: int(cnt) for kb_id, cnt in rows.all()}

    out = []
    for kb in kbs:
        out.append(
            KnowledgeBaseOut(
                id=kb.id,
                name=kb.name,
                description=kb.description or "",
                created_at=kb.created_at,
                updated_at=kb.updated_at,
                document_count=counts.get(kb.id, 0),
            )
        )
    return {"knowledge_bases": out}


def _kb_out(kb, document_count: int = 0) -> KnowledgeBaseOut:
    return KnowledgeBaseOut(
        id=kb.id,
        name=kb.name,
        description=kb.description or "",
        created_at=kb.created_at,
        updated_at=kb.updated_at,
        document_count=document_count,
    )


@router.post("/knowledge-bases")
async def create_knowledge_base(
    create: KnowledgeBaseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeBaseOut:
    svc = KnowledgeService(db)
    kb = await svc.create_kb(create)
    return _kb_out(kb, document_count=0)


@router.get("/knowledge-bases/{kb_id}")
async def get_knowledge_base(
    kb_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    svc = KnowledgeService(db)
    kb = await svc.get_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    count_row = await db.execute(
        select(func.count(KnowledgeDoc.id)).where(KnowledgeDoc.knowledge_base_id == kb_id)
    )
    count = int(count_row.scalar() or 0)
    return {"knowledge_base": _kb_out(kb, document_count=count)}


@router.patch("/knowledge-bases/{kb_id}")
async def update_knowledge_base(
    kb_id: str,
    update: KnowledgeBaseUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeBaseOut:
    svc = KnowledgeService(db)
    kb = await svc.update_kb(kb_id, update)
    if kb is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return _kb_out(kb, document_count=0)


@router.delete("/knowledge-bases/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    svc = KnowledgeService(db)
    ok = await svc.delete_kb(kb_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    # chromadb cleanup happens inside the service; no synchronous cleanup API
    # is exposed yet because deleting a KB also deletes its docs (cascade).
    return {"deleted": True, "kb_id": kb_id}


@router.get("/knowledge-bases/{kb_id}/documents")
async def list_documents(
    kb_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    svc = KnowledgeService(db)
    if await svc.get_kb(kb_id) is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    docs = await svc.list_documents(kb_id)
    return {
        "documents": [
            KnowledgeDocOut(
                id=d.id,
                knowledge_base_id=d.knowledge_base_id,
                filename=d.filename,
                sha256=d.sha256,
                created_at=d.created_at,
                text_length=len(d.text or ""),
            )
            for d in docs
        ]
    }


@router.post("/knowledge-bases/{kb_id}/documents")
async def upload_document(
    kb_id: str,
    file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeDocOut:
    svc = KnowledgeService(db)
    if await svc.get_kb(kb_id) is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    name = (file.filename or "").lower()
    if not name.endswith(_ALLOWED_DOC_SUFFIXES):
        raise HTTPException(
            status_code=400,
            detail="Only .md / .markdown / .txt files are accepted.",
        )

    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {_MAX_UPLOAD_BYTES // 1024} KB).",
        )
    text = raw.decode("utf-8", errors="ignore")

    doc = await svc.add_document(kb_id, file.filename or "note.md", text)
    return KnowledgeDocOut(
        id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        filename=doc.filename,
        sha256=doc.sha256,
        created_at=doc.created_at,
        text_length=len(doc.text or ""),
    )


@router.delete("/knowledge-bases/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str,
    doc_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    svc = KnowledgeService(db)
    ok = await svc.delete_document(kb_id, doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True, "doc_id": doc_id}