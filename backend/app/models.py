import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), default="新会话")
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )
    files: Mapped[list["UploadedFile"]] = relationship(
        "UploadedFile", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))  # system / user / assistant
    content: Mapped[str] = mapped_column(Text, default="")
    thinking: Mapped[str] = mapped_column(Text, default="")  # reasoning / chain-of-thought content
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="done")  # pending / streaming / done / error
    # AgentService phase 2a: per-agent metadata (step_count, aborted flag,
    # tool_calls transcript). Stored as JSON; older chat rows simply have {}
    # via the default-dict below. SQLite stores JSON as TEXT.
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    text_content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=now_utc)

    conversation: Mapped["Conversation | None"] = relationship("Conversation", back_populates="files")


class KnowledgeBase(Base):
    """RAG knowledge base (AgentService phase 2b-i).

    Holds metadata + raw documents in SQLAlchemy; embeddings live in chromadb
    keyed by doc_id+chunk_idx so retrieval is decoupled from the relational
    store. Deleting a KnowledgeBase cascades to its documents (and the
    KnowledgeService is responsible for the matching chromadb cleanup).
    """

    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)

    documents: Mapped[list["KnowledgeDoc"]] = relationship(
        "KnowledgeDoc", back_populates="knowledge_base", cascade="all, delete-orphan", order_by="KnowledgeDoc.created_at"
    )


class KnowledgeDoc(Base):
    """A single document uploaded into a KnowledgeBase.

    The full extracted text is persisted here so we can re-chunk later if
    chunking strategy changes; embeddings are recomputed on demand by
    KnowledgeService.index_document rather than stored.
    """

    __tablename__ = "knowledge_docs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    knowledge_base_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=now_utc)

    knowledge_base: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="documents")


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    vendor: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(50), nullable=False)  # openai / anthropic / gemini / openai_compatible
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Per-model API key. When set, takes precedence over the vendor key read
    # from .env. Required for openai_compatible / anthropic_compatible models
    # whose vendor has no .env entry.
    api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)

