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

    # Database
    database_url: str = "sqlite+aiosqlite:///./workbench.db"

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
