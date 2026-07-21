"""Knowledge base service for AgentService phase 2b-i (RAG).

Two-track persistence:
- SQLAlchemy tables ``KnowledgeBase`` / ``KnowledgeDoc`` hold KB/doc metadata
  and the raw text (so a re-embed / re-chunk is possible without re-upload).
- chromadb holds the pure vector index — one collection per KB
  (``f"kb_{kb_id}"``) so deleting a KB is O(1) ``delete_collection`` and
  retrieval needs no metadata filter.

Chunking: ``MarkdownHeaderTextSplitter`` (#/##/###) →
``RecursiveCharacterTextSplitter`` (chunk_size / overlap from settings). Files
without markdown headers yield a single whole-doc chunk with an empty heading,
which the recursive splitter then splits by length.

Embedding goes through :data:`embedding_service` (bge-small-zh with a
FakeEmbedder no-op fallback). When the real model is unavailable:
``upload_document`` raises ``RuntimeError`` (router → 503) and ``retrieve``
returns ``[]`` — RAG degrades gracefully rather than indexing garbage.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import _BACKEND_ROOT, settings
from app.models import KnowledgeBase, KnowledgeDoc
from app.schemas import (
    DocumentUploadResponse,
    KnowledgeBaseCreate,
    RetrievedChunk,
)
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

# Allow these suffixes for KB document uploads.
_ALLOWED_SUFFIXES = {".md", ".markdown", ".txt"}
_MAX_DOC_BYTES = 10 * 1024 * 1024  # 10 MB

_chroma_client: Any = None


def _resolve_persist_dir() -> Path:
    """Resolve chroma_persist_dir against the backend root, not CWD.

    Mirrors the .env resolution in config.py so the on-disk index lives in a
    stable location regardless of the process working directory.
    """
    p = Path(settings.chroma_persist_dir)
    if not p.is_absolute():
        p = _BACKEND_ROOT / p
    return p


def _get_chroma_client() -> Any:
    """Lazy module-level chromadb PersistentClient singleton."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb  # lazy: avoid eager import at module load

        _chroma_client = chromadb.PersistentClient(path=str(_resolve_persist_dir()))
    return _chroma_client


def _collection_name(kb_id: str) -> str:
    return f"kb_{kb_id}"


def _get_collection(kb_id: str) -> Any:
    """Get (creating if needed) the chromadb collection for a KB.

    Uses cosine distance so ``score = 1 - distance`` maps to similarity in
    [0, 1] for normalized embeddings (bge encodes with normalize_embeddings=True).
    """
    return _get_chroma_client().get_or_create_collection(
        name=_collection_name(kb_id),
        metadata={"hnsw:space": "cosine"},
    )


def _chunk_text(text: str) -> list[dict[str, str]]:
    """Split markdown text into ``[{text, heading}]`` chunks.

    Lazy-imports langchain_text_splitters (not langchain-core). Markdown-
    header splitting yields one chunk per header section; the recursive
    splitter then bounds chunk length. Falls back to a single whole-doc
    chunk (length-bounded) if the splitter libs are unavailable.
    """
    try:
        from langchain_text_splitters import (
            MarkdownHeaderTextSplitter,
            RecursiveCharacterTextSplitter,
        )
    except Exception as exc:  # pragma: no cover - dep is declared
        logger.warning("text splitters unavailable (%s); single-chunk fallback", exc)
        return [{"text": text, "heading": ""}]

    headers_to_split_on = [
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ]
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on, strip_headers=False
    )
    md_chunks = md_splitter.split_text(text)

    recursive = RecursiveCharacterTextSplitter(
        chunk_size=settings.kb_chunk_size,
        chunk_overlap=settings.kb_chunk_overlap,
    )
    out: list[dict[str, str]] = []
    for md_chunk in md_chunks:
        heading = " / ".join(
            v for v in (
                md_chunk.metadata.get("h1"),
                md_chunk.metadata.get("h2"),
                md_chunk.metadata.get("h3"),
            )
            if v
        )
        for piece in recursive.split_text(md_chunk.page_content):
            piece = piece.strip()
            if piece:
                out.append({"text": piece, "heading": heading})
    return out or [{"text": text, "heading": ""}]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class KnowledgeService:
    """Per-request KB/doc CRUD + chunking + embed + retrieve."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -- KB CRUD -----------------------------------------------------------

    async def list_knowledge_bases(self) -> list[KnowledgeBase]:
        result = await self.db.execute(
            select(KnowledgeBase).order_by(KnowledgeBase.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_knowledge_base(self, kb_id: str) -> KnowledgeBase | None:
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        )
        return result.scalar_one_or_none()

    async def create_knowledge_base(self, data: KnowledgeBaseCreate) -> KnowledgeBase:
        kb = KnowledgeBase(name=data.name, description=data.description or "")
        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)
        return kb

    async def delete_knowledge_base(self, kb_id: str) -> bool:
        kb = await self.get_knowledge_base(kb_id)
        if not kb:
            return False
        # Cascade deletes KnowledgeDoc rows via the ORM relationship; the
        # chromadb collection is dropped best-effort.
        await self.db.delete(kb)
        await self.db.commit()
        try:
            _get_chroma_client().delete_collection(name=_collection_name(kb_id))
        except Exception as exc:  # collection may not exist
            logger.debug("chroma delete_collection(%s) skipped: %s", kb_id, exc)
        return True

    # -- Document CRUD -----------------------------------------------------

    async def list_documents(self, kb_id: str) -> list[KnowledgeDoc]:
        result = await self.db.execute(
            select(KnowledgeDoc)
            .where(KnowledgeDoc.kb_id == kb_id)
            .order_by(KnowledgeDoc.created_at.desc())
        )
        return list(result.scalars().all())

    async def _find_doc_by_sha(self, kb_id: str, sha: str) -> KnowledgeDoc | None:
        result = await self.db.execute(
            select(KnowledgeDoc).where(
                KnowledgeDoc.kb_id == kb_id,
                KnowledgeDoc.sha256 == sha,
            )
        )
        return result.scalar_one_or_none()

    async def upload_document(
        self,
        kb_id: str,
        filename: str,
        content_bytes: bytes,
    ) -> DocumentUploadResponse:
        """Decode, dedup, chunk, embed, and index a document into the KB.

        Raises ``RuntimeError`` when the embedding model is unavailable (the
        router maps this to HTTP 503) — we refuse to store un-searchable
        vectors.
        """
        kb = await self.get_knowledge_base(kb_id)
        if not kb:
            raise ValueError(f"Knowledge base not found: {kb_id}")

        suffix = Path(filename).suffix.lower()
        if suffix not in _ALLOWED_SUFFIXES:
            raise ValueError(
                f"Unsupported file type '{suffix}'. Allowed: {sorted(_ALLOWED_SUFFIXES)}"
            )
        if len(content_bytes) > _MAX_DOC_BYTES:
            raise ValueError(
                f"File too large ({len(content_bytes)} bytes); limit {_MAX_DOC_BYTES} bytes"
            )

        try:
            text = content_bytes.decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover - decode is forgiving
            raise ValueError(f"Could not decode file as text: {exc}") from exc

        sha = _sha256(text)
        existing = await self._find_doc_by_sha(kb_id, sha)
        if existing:
            return DocumentUploadResponse(
                doc_id=existing.id,
                filename=existing.filename,
                chunks=0,
                deduplicated=True,
            )

        if not embedding_service.is_available():
            raise RuntimeError(
                "Embedding model unavailable — install sentence-transformers "
                "and pre-fetch the model to upload documents."
            )

        chunks = _chunk_text(text)
        embeddings = embedding_service.embed_texts([c["text"] for c in chunks])
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Embedding count mismatch: {len(embeddings)} vs {len(chunks)} chunks"
            )

        doc = KnowledgeDoc(kb_id=kb_id, filename=filename, sha256=sha, text=text)
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)

        collection = _get_collection(kb_id)
        ids = [f"{doc.id}_{i}" for i in range(len(chunks))]
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=[c["text"] for c in chunks],
            metadatas=[
                {"doc_id": doc.id, "filename": filename, "heading": c["heading"]}
                for c in chunks
            ],
        )
        return DocumentUploadResponse(
            doc_id=doc.id,
            filename=filename,
            chunks=len(chunks),
            deduplicated=False,
        )

    async def delete_document(self, kb_id: str, doc_id: str) -> bool:
        result = await self.db.execute(
            select(KnowledgeDoc).where(
                KnowledgeDoc.id == doc_id,
                KnowledgeDoc.kb_id == kb_id,
            )
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return False
        await self.db.delete(doc)
        await self.db.commit()
        try:
            collection = _get_collection(kb_id)
            collection.delete(where={"doc_id": doc_id})
        except Exception as exc:
            logger.debug("chroma delete(where doc_id=%s) skipped: %s", doc_id, exc)
        return True

    # -- Retrieval ---------------------------------------------------------

    async def retrieve(
        self,
        kb_id: str,
        query: str,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[RetrievedChunk]:
        """Vector top-K retrieval. Returns ``[]`` when the embedding model is
        unavailable (RAG no-op) or the KB has no indexed documents."""
        if not embedding_service.is_available():
            return []
        kb = await self.get_knowledge_base(kb_id)
        if not kb:
            return []

        top_k = top_k if top_k is not None else settings.kb_top_k
        min_score = min_score if min_score is not None else settings.kb_min_score

        query_vec = embedding_service.embed_query(query)
        if not query_vec:
            return []

        try:
            collection = _get_collection(kb_id)
            result = collection.query(
                query_embeddings=[query_vec],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.debug("chroma query(kb=%s) failed: %s", kb_id, exc)
            return []

        if not result or not result.get("ids") or not result["ids"][0]:
            return []

        ids = result["ids"][0]
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]

        chunks: list[RetrievedChunk] = []
        for i, _chunk_id in enumerate(ids):
            distance = distances[i]
            # cosine distance ∈ [0, 2]; similarity = 1 - distance.
            score = max(0.0, 1.0 - float(distance))
            if score < min_score:
                continue
            meta = metadatas[i] or {}
            chunks.append(
                RetrievedChunk(
                    doc_id=str(meta.get("doc_id", "")),
                    filename=str(meta.get("filename", "")),
                    heading=str(meta.get("heading", "")),
                    score=score,
                    text=documents[i],
                )
            )
        return chunks
