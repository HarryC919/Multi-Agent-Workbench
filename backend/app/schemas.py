from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class FileContent(BaseModel):
    name: str
    content: str


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    model: str
    messages: list[ChatMessage]
    files: list[FileContent] = []
    stream: bool = True
    thinking: bool = False  # enable chain-of-thought / reasoning output
    rag_knowledge_base_id: str | None = None  # reserved for RAG extension


class AgentChatRequest(ChatRequest):
    """Request body for `/api/agent-chat` (AgentService phase 2a).

    Inherits all ChatRequest fields. Adds knobs for the ReAct loop. The
    step / final temperature fields are now forwarded to adapters (phase 2a
    wired temperature/top_p through BaseAdapter.stream_chat).

    ``enable_skills`` controls which Skills are exposed to the LangGraph
    agent as tools. ``None`` = use all registered skills; an explicit list
    acts as a whitelist (names not in the registry are silently ignored so
    a frontend stale-config doesn't 500 the request).
    """

    max_steps: int = 8
    step_temperature: float | None = None
    final_temperature: float | None = None
    enable_skills: list[str] | None = None


class ChatChunk(BaseModel):
    type: Literal[
        "text",
        "thinking",
        "done",
        "error",
        "warning",
        "action",
        "observation",
        # Phase 2b-ii: step-bounded event stream (kept alongside the flat
        # events above for backward compatibility).
        "step_start",
        "step_end",
        "retrieved",
    ]
    content: str | None = None
    finish_reason: str | None = None
    message: str | None = None
    # Fields used by the phase 2a action / observation events.
    name: str | None = None
    step: int | None = None
    # Phase 2b-ii step-bounded event fields.
    input: str | None = None  # action event (aligned with the TS ChatChunk)
    max_steps: int | None = None  # warning event (aligned with TS)
    finish: str | None = None  # step_end: final|tool|empty|max_steps|error
    label: str | None = None  # step_start label
    docs: list[dict] | None = None  # retrieved chunk documents


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationUpdate(BaseModel):
    title: str


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailOut(ConversationOut):
    messages: list["MessageOut"] = []


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    thinking: str = ""
    model: str | None = None
    status: str
    # AgentService phase 2a: per-agent metadata (step_count, aborted flag,
    # tool_calls transcript). Plain chat messages have an empty dict.
    # The ORM attribute is named ``metadata_`` (SQLAlchemy reserves
    # ``metadata``); the validator below bridges the two so the API field
    # stays ``metadata`` for frontend consumers.
    metadata: dict = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _metadata_alias(cls, data: object) -> object:
        if isinstance(data, dict):
            return data
        # ORM object: copy metadata_ → metadata for the serializer.
        meta = getattr(data, "metadata_", None) or {}
        return {
            "id": getattr(data, "id"),
            "conversation_id": getattr(data, "conversation_id"),
            "role": getattr(data, "role"),
            "content": getattr(data, "content"),
            "thinking": getattr(data, "thinking", ""),
            "model": getattr(data, "model", None),
            "status": getattr(data, "status"),
            "metadata": meta,
            "created_at": getattr(data, "created_at"),
        }


class UploadedFileOut(BaseModel):
    id: str
    name: str
    text_content: str

    model_config = ConfigDict(from_attributes=True)


class UploadFileResponse(BaseModel):
    file_id: str
    name: str
    text_content: str


# --- KnowledgeBase (AgentService phase 2b-i) ---


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class KnowledgeBaseOut(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    document_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocOut(BaseModel):
    id: str
    knowledge_base_id: str
    filename: str
    sha256: str
    created_at: datetime
    # We do not expose the full `text` in list responses (potentially huge);
    # callers that need it (e.g. re-index) go through the service layer.
    text_length: int = 0

    model_config = ConfigDict(from_attributes=True)


class KnowledgeRetrievalResult(BaseModel):
    """One chunk returned by a RAG retrieve call."""

    doc_id: str
    filename: str
    heading: str | None = None
    chunk_text: str
    score: float


class ModelConfigCreate(BaseModel):
    model_id: str
    vendor: str
    name: str
    adapter_type: Literal["openai", "anthropic", "gemini", "openai_compatible", "anthropic_compatible"]
    base_url: str | None = None
    api_key: str | None = None
    is_active: bool = True


class ModelConfigUpdate(BaseModel):
    vendor: str | None = None
    name: str | None = None
    adapter_type: Literal["openai", "anthropic", "gemini", "openai_compatible", "anthropic_compatible"] | None = None
    base_url: str | None = None
    # None on update means "leave unchanged"; empty string means "clear it".
    # To distinguish, the router treats unset (excluded) vs explicit None/"".
    api_key: str | None = None
    is_active: bool | None = None


class ModelConfigOut(BaseModel):
    id: str
    model_id: str
    vendor: str
    name: str
    adapter_type: str
    base_url: str | None = None
    # Never return the key itself; only whether one is configured. Populated
    # from the ORM model's api_key attribute via the model_validator below.
    has_api_key: bool = False
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _populate_has_api_key(cls, data: object) -> object:
        # When constructed from an ORM object (dict-like / attributes), derive
        # has_api_key from the api_key attribute without exposing the value.
        if isinstance(data, dict):
            if "has_api_key" not in data:
                data["has_api_key"] = bool(data.get("api_key"))
            data.pop("api_key", None)
        else:
            # ORM object: read api_key attr, set has_api_key, let from_attributes
            # handle the rest. We return a dict to avoid leaking api_key.
            api_key = getattr(data, "api_key", None)
            return {
                "id": getattr(data, "id"),
                "model_id": getattr(data, "model_id"),
                "vendor": getattr(data, "vendor"),
                "name": getattr(data, "name"),
                "adapter_type": getattr(data, "adapter_type"),
                "base_url": getattr(data, "base_url", None),
                "has_api_key": bool(api_key),
                "is_active": getattr(data, "is_active"),
                "created_at": getattr(data, "created_at"),
                "updated_at": getattr(data, "updated_at"),
            }
        return data


# Resolve forward reference
ConversationDetailOut.model_rebuild()
