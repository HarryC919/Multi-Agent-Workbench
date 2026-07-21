"""Embedding service for AgentService phase 2b-i.

Looks up a local sentence-transformers model (default `BAAI/bge-small-zh-v1.5`)
and exposes a sync `embed_texts` API used by KnowledgeService. If torch or the
underlying model is unavailable (network blocked, model not downloaded,
running in CI without heavy extras), the service degrades to a deterministic
fake embedder that returns hash-derived vectors. The fake path keeps KB CRUD
and retrieve logic exercisable in tests without dragging in 2GB of torch.

We intentionally do NOT surface LangChain's `Embeddings` interface from this
module — KnowledgeService calls `EmbeddingService.embed_texts` and feeds
plain float lists to chromadb. That way LangChain imports stay narrow.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Process-singleton wrapper around a sentence-transformers model.

    The class itself is cheap to construct; the heavy load happens lazily on
    first embed_texts call so importing this module is free in tests.
    """

    _instance: "EmbeddingService | None" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._model: Any = None
        self._model_loaded = False
        self._load_attempted = False
        self._fake_mode = False
        # Cache the configured dimension lazily — both real bge-small-zh (512)
        # and fake-hashed (1024) shapes are queried via `dim`.
        self._dim: int | None = None

    @classmethod
    def instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ---------------------------------------------------------------- load

    def _ensure_model(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        try:
            from sentence_transformers import SentenceTransformer  # noqa: WPS433
        except ImportError:
            logger.warning(
                "sentence-transformers not installed; using FakeEmbedder "
                "(vectors are hash-derived, retrieval will be meaningless)."
            )
            self._fake_mode = True
            return
        try:
            # Explicit device: see config.embedding_device. Default cpu avoids
            # the Apple Silicon "mps" first-load hang that makes uploads appear
            # to time out.
            self._model = SentenceTransformer(
                settings.embedding_model, device=settings.embedding_device
            )
            self._model_loaded = True
        except Exception as exc:  # noqa: BLE001 — network / disk / model issues
            logger.warning(
                "Failed to load embedding model %s: %s. Using FakeEmbedder; "
                "RAG retrieve will return meaningless rankings.",
                settings.embedding_model,
                exc,
            )
            self._fake_mode = True

    @property
    def dim(self) -> int:
        self._ensure_model()
        if self._dim is not None:
            return self._dim
        if self._fake_mode:
            self._dim = 1024
        else:
            # `get_sentence_embedding_dimension` is a cheap attribute on ST.
            self._dim = int(self._model.get_sentence_embedding_dimension())
        return self._dim

    # ---------------------------------------------------------------- embed

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_model()
        if self._fake_mode:
            return [self._fake_vector(t) for t in texts]
        vectors = self._model.encode(texts, normalize_embeddings=True)
        # sentence-transformers returns numpy arrays; coerce to plain floats
        # so chromadb and JSON serde stay simple.
        return [[float(x) for x in v] for v in vectors]

    # ---------------------------------------------------------------- fake

    _FAKE_DIM = 1024

    def _fake_vector(self, text: str) -> list[float]:
        """Deterministic 1024-dim vector keyed by text hash.

        Not semantically meaningful — only guarantees the same input maps to
        the same vector so unit tests can assert retrieve-by-exact-match.
        """
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Stretch 32 bytes to 1024 floats by cycling the digest.
        out: list[float] = []
        for i in range(self._FAKE_DIM):
            b = digest[i % len(digest)]
            out.append((b - 128) / 128.0)
        return out


__all__ = ["EmbeddingService"]