"""Embedding service for AgentService phase 2b-i (RAG).

Uses local ``sentence-transformers`` with ``BAAI/bge-small-zh-v1.5`` (512-dim,
good Chinese-notes retrieval, zero network cost). If torch or the model is
unavailable, falls back to :class:`FakeEmbedder` — a **no-op** rather than a
zero-vector embedder.

Why no-op instead of zero vectors: chromadb cosine over all-zero vectors
returns ``nan`` / degenerate ties, so a zero-vector fake would silently
produce garbage retrieval. Instead the fake returns ``[]`` and callers
(`KnowledgeService`) short-circuit: ``retrieve`` returns ``[]``,
``upload_document`` raises so the router can return 503. This makes the
missing-dependency state loud at upload time while keeping the server up.

The ``sentence_transformers`` import is lazy (inside :meth:`_load_model`) so
that importing this module — which happens transitively via
``conftest.py`` → ``main.py`` → ``routers`` → ``knowledge_service`` — does
not drag torch into the test process.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# bge-small-zh-v1.5 output dimension. FakeEmbedder matches for schema compat
# (though it never actually emits vectors).
_EMBED_DIM = 512


class FakeEmbedder:
    """No-op embedder used when the real model is unavailable.

    Returns empty lists; callers detect this via :meth:`is_available` and
    short-circuit rather than indexing/querying with garbage.
    """

    name = "fake"
    dim = _EMBED_DIM

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return []

    def embed_query(self, text: str) -> list[float]:
        return []


class EmbeddingService:
    """Module-level singleton wrapping the bge model with a fake fallback."""

    _instance: "EmbeddingService | None" = None

    def __init__(self) -> None:
        self._model: Any = None
        self._backend: str = ""  # "bge" | "fake"
        self._load_attempted: bool = False

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_model(self) -> None:
        """Lazily load the bge model. Safe to call repeatedly."""
        if self._load_attempted:
            return
        self._load_attempted = True
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(settings.embedding_model)
            # Touch the model to force a forward pass / surface download errors
            # early (the first encode may otherwise lazy-load weights).
            self._backend = "bge"
            logger.info("EmbeddingService: loaded %s", settings.embedding_model)
        except Exception as exc:  # ImportError / OSError / RuntimeError / network
            logger.warning(
                "EmbeddingService: %s unavailable (%s); falling back to FakeEmbedder. "
                "Install sentence-transformers and pre-fetch the model to enable RAG.",
                settings.embedding_model,
                exc,
            )
            self._model = FakeEmbedder()
            self._backend = "fake"

    @property
    def backend(self) -> str:
        self._load_model()
        return self._backend

    def is_available(self) -> bool:
        """True only when the real bge model loaded successfully."""
        self._load_model()
        return self._backend == "bge" and not isinstance(self._model, FakeEmbedder)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        if not self.is_available():
            return []
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, v)) for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        self._load_model()
        if not self.is_available():
            return []
        vector = self._model.encode([text], normalize_embeddings=True)[0]
        return list(map(float, vector))


embedding_service = EmbeddingService.get_instance()
