from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file (backend/app/config.py) so it is found
# regardless of the process working directory. Without this, pydantic-settings
# looks up ".env" relative to CWD and silently skips it when run from the
# project root or anywhere other than backend/.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # Anthropic
    anthropic_api_key: str = ""

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # GLM
    glm_api_key: str = ""
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"

    # Kimi
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"

    # Gemini
    gemini_api_key: str = ""

    # AgentService phase 1 — ReAct loop knobs.
    # NOTE: step_temperature / final_temperature are accepted here as
    # placeholders; the current adapters do not accept a temperature
    # argument, so they are not yet forwarded. Phase 2 will wire them
    # through the adapter layer.
    agent_max_steps: int = 8
    agent_step_temperature: float = 0.7
    agent_final_temperature: float = 0.4

    # AgentService phase 2b-i — RAG / knowledge base knobs. The embedding
    # model is loaded lazily by EmbeddingService; if torch or the model
    # is unavailable, EmbeddingService falls back to a deterministic fake
    # embedder so the rest of the KB pipeline (CRUD, chunking, retrieve)
    # stays exercisable in tests and on light environments.
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    # Device for the embedding model. Default "cpu": on Apple Silicon the
    # auto-selected "mps" backend hangs for minutes on the first
    # SentenceTransformer load, which makes the first document upload appear to
    # 500/timeout. CPU is fast enough for the small batch sizes RAG uses here.
    embedding_device: str = "cpu"
    chroma_persist_dir: str = "./.chroma"
    kb_chunk_size: int = 800
    kb_chunk_overlap: int = 100
    kb_top_k: int = 4
    kb_min_score: float = 0.3

    # Database
    database_url: str = "sqlite+aiosqlite:///./workbench.db"

    # Phase 3 — markdown-defined skills. Directory scanned for .md files at
    # startup; relative to the backend root (resolved at import time).
    skills_md_dir: str = "skills_md"

    # Phase 3 - Tavily web search API key (web_search skill).
    # Free tier at tavily.com; empty key -> web_search returns an error shape.
    tavily_api_key: str = ""

    # AgentService phase 2b-i — RAG / knowledge base knobs.
    # Embedding uses local sentence-transformers + bge-small-zh-v1.5; if torch
    # or the model is unavailable, EmbeddingService falls back to a FakeEmbedder
    # no-op (uploads 503, retrieve returns []). chroma_persist_dir is resolved
    # against the backend root in KnowledgeService to avoid CWD dependence.
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    chroma_persist_dir: str = ".chroma"
    kb_chunk_size: int = 800
    kb_chunk_overlap: int = 100
    kb_top_k: int = 4
    kb_min_score: float = 0.3

    @property
    def vendor_credentials(self) -> dict[str, tuple[str, str]]:
        """Return vendor -> (api_key, base_url) mapping."""
        return {
            "openai": (self.openai_api_key, self.openai_base_url),
            "anthropic": (self.anthropic_api_key, "https://api.anthropic.com/v1"),
            "deepseek": (self.deepseek_api_key, self.deepseek_base_url),
            "glm": (self.glm_api_key, self.glm_base_url),
            "kimi": (self.kimi_api_key, self.kimi_base_url),
            "gemini": (self.gemini_api_key, "https://generativelanguage.googleapis.com/v1beta"),
        }


settings = Settings()
