"""Knowledge base management router (AgentService phase 2b-i).

CRUD for knowledge bases + multipart document upload / delete. Mirrors the
style of ``routers/models.py`` (response_model on every endpoint, service
constructed per-request from the AsyncSession dependency).

The document upload endpoint is the only one that needs the embedding model:
``KnowledgeService.upload_document`` raises ``RuntimeError`` when it is
unavailable, which we map to HTTP 503 so the frontend can show a clear
"install sentence-transformers" message rather than a generic 500.
"""
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas import (
    DocumentUploadResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeDocOut,
)
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/knowledge-bases")
async def list_knowledge_bases(db: AsyncSession = Depends(get_db)):
    svc = KnowledgeService(db)
    kbs = await svc.list_knowledge_bases()
    return {"knowledge_bases": [KnowledgeBaseOut.model_validate(k) for k in kbs]}


@router.post("/knowledge-bases", response_model=KnowledgeBaseOut)
async def create_knowledge_base(
    data: KnowledgeBaseCreate, db: AsyncSession = Depends(get_db)
):
    svc = KnowledgeService(db)
    kb = await svc.create_knowledge_base(data)
    return kb


@router.delete("/knowledge-bases/{kb_id}")
async def delete_knowledge_base(kb_id: str, db: AsyncSession = Depends(get_db)):
    svc = KnowledgeService(db)
    deleted = await svc.delete_knowledge_base(kb_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return {"deleted": True}


@router.get("/knowledge-bases/{kb_id}/documents")
async def list_documents(kb_id: str, db: AsyncSession = Depends(get_db)):
    svc = KnowledgeService(db)
    if not await svc.get_knowledge_base(kb_id):
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    docs = await svc.list_documents(kb_id)
    return {"documents": [KnowledgeDocOut.model_validate(d) for d in docs]}


@router.post(
    "/knowledge-bases/{kb_id}/documents", response_model=DocumentUploadResponse
)
async def upload_document(
    kb_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")
    content_bytes = await file.read()
    svc = KnowledgeService(db)
    try:
        resp = await svc.upload_document(kb_id, file.filename, content_bytes)
    except ValueError as exc:
        # Unknown KB / bad type / oversize / decode error → 400 (404 for
        # unknown KB is more precise).
        if "not found" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Embedding model unavailable → 503 so the client can surface a clear
        # "install sentence-transformers" message.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return resp


@router.delete("/knowledge-bases/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str, doc_id: str, db: AsyncSession = Depends(get_db)
):
    svc = KnowledgeService(db)
    deleted = await svc.delete_document(kb_id, doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True}
