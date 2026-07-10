from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import BaseAdapter
from app.adapters.openai_adapter import OpenAIAdapter
from app.adapters.anthropic_adapter import AnthropicAdapter
from app.adapters.gemini_adapter import GeminiAdapter
from app.config import settings
from app.models import ModelConfig


# Vendor -> the env var name that supplies its API key, used for clear errors
# when a model is selected but its credentials were never set in .env.
_VENDOR_ENV_VAR = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "glm": "GLM_API_KEY",
    "kimi": "KIMI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def get_adapter(adapter_type: str, vendor: str, base_url: str | None = None) -> BaseAdapter:
    """Synchronous adapter factory.

    Uses config credentials for the given vendor. A custom base_url overrides the
    vendor default, which is useful for private deployments or OpenAI/Anthropic
    compatible endpoints.
    """
    if vendor not in settings.vendor_credentials:
        raise ValueError(
            f"Unknown vendor '{vendor}'. Expected one of: "
            f"{', '.join(sorted(settings.vendor_credentials))}."
        )

    api_key, default_base_url = settings.vendor_credentials[vendor]
    if not api_key:
        env_var = _VENDOR_ENV_VAR.get(vendor, f"{vendor.upper()}_API_KEY")
        raise ValueError(
            f"No API key configured for vendor '{vendor}'. "
            f"Set {env_var} in backend/.env and restart the server."
        )

    final_base_url = (base_url or default_base_url).rstrip("/")

    if adapter_type == "openai" or adapter_type == "openai_compatible":
        return OpenAIAdapter(api_key=api_key, base_url=final_base_url)
    elif adapter_type == "anthropic" or adapter_type == "anthropic_compatible":
        return AnthropicAdapter(api_key=api_key, base_url=final_base_url)
    elif adapter_type == "gemini":
        return GeminiAdapter(api_key=api_key)
    else:
        raise ValueError(f"Unsupported adapter_type: {adapter_type}")


async def get_adapter_by_model_id(model_id: str, db: AsyncSession) -> BaseAdapter:
    """Asynchronous adapter factory backed by the ModelConfig registry."""
    result = await db.execute(
        select(ModelConfig).where(ModelConfig.model_id == model_id, ModelConfig.is_active == True)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise ValueError(f"Model not found or inactive: {model_id}")

    return get_adapter(
        adapter_type=config.adapter_type,
        vendor=config.vendor,
        base_url=config.base_url,
    )
