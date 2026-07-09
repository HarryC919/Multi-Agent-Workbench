from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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
