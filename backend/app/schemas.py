from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    effort: float = Field(0.7, ge=0.0, le=1.0)
    files: list[FileContent] = []
    stream: bool = True
    rag_knowledge_base_id: str | None = None  # reserved for RAG extension


class ChatChunk(BaseModel):
    type: Literal["text", "done", "error"]
    content: str | None = None
    finish_reason: str | None = None
    message: str | None = None


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
    model: str | None = None
    effort: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadedFileOut(BaseModel):
    id: str
    name: str
    text_content: str

    model_config = ConfigDict(from_attributes=True)


class UploadFileResponse(BaseModel):
    file_id: str
    name: str
    text_content: str


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
