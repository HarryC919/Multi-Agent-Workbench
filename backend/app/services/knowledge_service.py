"""Knowledge base service (AgentService phase 2b-i).

Owns:
    * SQLAlchemy CRUD over KnowledgeBase + KnowledgeDoc.
    * Markdown chunking via langchain-text-splitters (header split → recursive
      character split fallback) + SHA-256 dedup of uploaded text.
    * Embedding + chromadb upsert on upload, delete on KB/doc removal.
    * Retrieve(query, top_k, min_score) returning KnowledgeRetrievalResult.

Design notes:
    * chromadb is process-local; the persist directory lives under
      `settings.chroma_persist_dir`. The collection name is the KB id so
      deletion is a single `delete_collection` call.
    * We deliberately do NOT expose chromadb's `Embeddings` interface —
      EmbeddingService.embed_texts gives us plain floats and we call chromadb
      `add` with `embeddings=...` directly. This keeps the embedder swappable
      and avoids the langchain-chroma wrapper's extra abstractions.
    * All methods are sync. The FastAPI router runs them in a thread pool via
      `run_in_executor`-style `await` wrapping (or synchronous route handlers
      in the current router setup); the work is CPU/io-bound but durations are
      small enough that thread-pool offloading is sufficient. Full async would
      require either an async chromadb client or a worker queue and is
      deferred to 2b-ii per the plan.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import KnowledgeBase, KnowledgeDoc
from app.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeRetrievalResult,
)
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_markdown(text: str) -> list[dict[str, Any]]:
    """Chunk a markdown document.

    Strategy: try `MarkdownHeaderTextSplitter` first (semantic split by
    headings, each chunk tagged with its header path); then if any single
    chunk still exceeds `kb_chunk_size` characters, run it through
    `RecursiveCharacterTextSplitter` for safety. Falls back to pure
    recursive splitting if the markdown splitter rejects the input.
    """
    from langchain_text_splitters import (
        MarkdownHeaderTextSplitter,
        RecursiveCharacterTextSplitter,
    )

    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "h1"),
            ("##", "h2"),
            ("###", "h3"),
        ],
    )
    recursive = RecursiveCharacterTextSplitter(
        chunk_size=settings.kb_chunk_size,
        chunk_overlap=settings.kb_chunk_overlap,
    )

    try:
        md_chunks = md_splitter.split_text(text)
    except Exception:  # noqa: BLE001 — fall back to pure recursive
        md_chunks = []

    out: list[dict[str, Any]] = []
    if not md_chunks:
        # No headers detected or splitter blew up; treat whole doc as one
        # cell with no heading and let the recursive splitter carve it.
        for piece in recursive.split_text(text):
            out.append({"heading": None, "chunk_text": piece})
        return out

    for md_doc in md_chunks:
        heading = " / ".join(
            str(v) for v in md_doc.metadata.values() if v
        ) or None
        body = md_doc.page_content
        # If chunk_size is small enough that md_doc is already shorter, the
        # recursive splitter returns it whole — no harm in always running it.
        for piece in recursive.split_text(body):
            if not piece.strip():
                continue
            out.append({"heading": heading, "chunk_text": piece})
    return out


class KnowledgeService:
    """Owns the SQL + chromadb lifecycle for knowledge bases."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding = EmbeddingService.instance()

    # ------------------------------------------------------------------ KB

    async def create_kb(self, create: KnowledgeBaseCreate) -> KnowledgeBase:
        kb = KnowledgeBase(
            name=create.name,
            description=create.description or "",
        )
        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)
        return kb

    async def list_kbs(self) -> list[KnowledgeBase]:
        result = await self.db.execute(select(KnowledgeBase).order_by(KnowledgeBase.updated_at.desc()))
        return list(result.scalars().all())

    async def get_kb(self, kb_id: str) -> KnowledgeBase | None:
        result = await self.db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
        return result.scalar_one_or_none()

    async def update_kb(self, kb_id: str, update: KnowledgeBaseUpdate) -> KnowledgeBase | None:
        values: dict[str, Any] = {}
        if update.name is not None:
            values["name"] = update.name
        if update.description is not None:
            values["description"] = update.description
        if not values:
            return await self.get_kb(kb_id)
        await self.db.execute(update(KnowledgeBase).where(KnowledgeBase.id == kb_id).values(**values))
        await self.db.commit()
        return await self.get_kb(kb_id)

    async def delete_kb(self, kb_id: str) -> bool:
        kb = await self.get_kb(kb_id)
        if kb is None:
            return False
        await self.db.delete(kb)
        await self.db.commit()
        # Clean up the chromadb collection last so SQL rollback stays possible
        # if chromadb throws — the next `delete_kb` call will re-attempt.
        try:
            self._chroma_collection(kb_id, create=False).delete()
        except Exception:  # noqa: BLE001 — chroma may already be gone
            pass
        try:
            self._chroma_client().delete_collection(name=kb_id)
        except Exception:  # noqa: BLE001
            pass
        return True

    # ---------------------------------------------------------------- Docs

    async def list_documents(self, kb_id: str) -> list[KnowledgeDoc]:
        result = await self.db.execute(
            select(KnowledgeDoc)
            .where(KnowledgeDoc.knowledge_base_id == kb_id)
            .order_by(KnowledgeDoc.created_at)
        )
        return list(result.scalars().all())

    async def add_document(
        self,
        kb_id: str,
        filename: str,
        text: str,
    ) -> KnowledgeDoc:
        """Add a document to a KB and index it into chromadb."""
        kb = await self.get_kb(kb_id)
        if kb is None:
            raise ValueError(f"KnowledgeBase {kb_id!r} not found")
        doc = KnowledgeDoc(
            knowledge_base_id=kb_id,
            filename=filename,
            sha256=_sha256(text),
            text=text,
        )
        self.db.add(doc)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ValueError(f"Failed to persist document: {exc}") from exc
        await self.db.refresh(doc)

        # Index chunks into chromadb. Failures here are logged but do not
        # invalidate the upload — the doc is in SQL and can be re-indexed
        # later if needed. This is the pragmatic choice for a local workbench
        # where users tolerate transient embedding failures.
        try:
            self._index_doc(kb_id, doc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to index document %s for KB %s: %s", doc.id, kb_id, exc)
        return doc

    async def delete_document(self, kb_id: str, doc_id: str) -> bool:
        result = await self.db.execute(
            select(KnowledgeDoc).where(
                KnowledgeDoc.id == doc_id,
                KnowledgeDoc.knowledge_base_id == kb_id,
            )
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            return False
        await self.db.delete(doc)
        await self.db.commit()
        try:
            coll = self._chroma_collection(kb_id, create=False)
            coll.delete(where={"doc_id": doc_id})
        except Exception:  # noqa: BLE001
            pass
        return True

    # -------------------------------------------------------------- retrieve

    def retrieve(
        self,
        kb_id: str,
        query: str,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[KnowledgeRetrievalResult]:
        top_k = top_k if top_k is not None else settings.kb_top_k
        min_score = min_score if min_score is not None else settings.kb_min_score
        query_vec = self.embedding.embed_texts([query])[0]
        try:
            coll = self._chroma_collection(kb_id, create=False)
        except Exception:  # noqa: BLE001
            return []
        results = coll.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )
        out: list[KnowledgeRetrievalResult] = []
        # chromadb shape: {ids: [[...]], documents: [[...]], metadatas: [[...]],
        #                   distances: [[...]]} — one inner list per query.
        ids = (results.get("ids") or [[]])[0]
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[]])[0]
        for i, raw in enumerate(docs):
            distance = float(dists[i]) if i < len(dists) else 1.0
            # chromadb returns a *distance* (smaller = more similar for the
            # default cosine metric). Convert to a 0..1 similarity score:
            # score = 1 - distance (clamped). The min_score gate uses this
            # normalized score so configs stay metric-agnostic.
            score = max(0.0, 1.0 - distance)
            if score < min_score:
                continue
            meta = metas[i] if i < len(metas) and metas[i] else {}
            out.append(
                KnowledgeRetrievalResult(
                    doc_id=meta.get("doc_id", ""),
                    filename=meta.get("filename", ""),
                    heading=meta.get("heading"),
                    chunk_text=raw or "",
                    score=score,
                )
            )
        return out

    # ----------------------------------------------------------- internals

    def _index_doc(self, kb_id: str, doc: KnowledgeDoc) -> None:
        chunks = _split_markdown(doc.text)
        if not chunks:
            return
        texts = [c["chunk_text"] for c in chunks]
        embeddings = self.embedding.embed_texts(texts)
        coll = self._chroma_collection(kb_id, create=True)
        coll.add(
            ids=[f"{doc.id}-{i}" for i in range(len(texts))],
            embeddings=embeddings,
            documents=texts,
            metadatas=[
                {
                    "doc_id": doc.id,
                    "filename": doc.filename,
                    "heading": c["heading"] or "",
                    "chunk_idx": i,
                }
                for i, c in enumerate(chunks)
            ],
        )

    # ----------------------------------------------------------- chromadb

    _chroma_client_singleton: Any = None
    _chroma_lock = __import__("threading").Lock()

    @classmethod
    def _chroma_client(cls) -> Any:
        """Process-wide chromadb PersistentClient."""
        if cls._chroma_client_singleton is None:
            with cls._chroma_lock:
                if cls._chroma_client_singleton is None:
                    import chromadb  # noqa: WPS433 — lazy import keeps cold start cheap

                    cls._chroma_client_singleton = chromadb.PersistentClient(
                        path=settings.chroma_persist_dir
                    )
        return cls._chroma_client_singleton

    def _chroma_collection(self, kb_id: str, *, create: bool) -> Any:
        client = self._chroma_client()
        # Use the embedding dimension so chromadb stores vectors of the right
        # shape from the first upsert. `metadata={"hnsw:space": "cosine"}` keeps
        # our distance normalization above valid.
        metadata = {"hnsw:space": "cosine"}
        if create:
            return client.get_or_create_collection(name=kb_id, metadata=metadata)
        return client.get_collection(name=kb_id)


__all__ = ["KnowledgeService"]