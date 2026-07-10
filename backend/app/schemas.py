from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    is_active: bool = True


class ModelConfigUpdate(BaseModel):
    vendor: str | None = None
    name: str | None = None
    adapter_type: Literal["openai", "anthropic", "gemini", "openai_compatible", "anthropic_compatible"] | None = None
    base_url: str | None = None
    is_active: bool | None = None


class ModelConfigOut(BaseModel):
    id: str
    model_id: str
    vendor: str
    name: str
    adapter_type: str
    base_url: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Resolve forward reference
ConversationDetailOut.model_rebuild()
