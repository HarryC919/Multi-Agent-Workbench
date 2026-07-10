from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelConfig


DEFAULT_MODELS = [
    {
        "model_id": "gpt-5.5",
        "vendor": "openai",
        "name": "GPT-5.5",
        "adapter_type": "openai",
    },
    {
        "model_id": "gpt-5.4",
        "vendor": "openai",
        "name": "GPT-5.4",
        "adapter_type": "openai",
    },
    {
        "model_id": "claude-opus-4.8",
        "vendor": "anthropic",
        "name": "Claude Opus 4.8",
        "adapter_type": "anthropic",
    },
    {
        "model_id": "claude-sonnet-5",
        "vendor": "anthropic",
        "name": "Claude Sonnet 5",
        "adapter_type": "anthropic",
    },
    {
        "model_id": "gemini-3.1-pro",
        "vendor": "gemini",
        "name": "Gemini 3.1 Pro",
        "adapter_type": "gemini",
    },
    {
        "model_id": "gemini-3.5-flash",
        "vendor": "gemini",
        "name": "Gemini 3.5 Flash",
        "adapter_type": "gemini",
    },
    {
        "model_id": "deepseek-v4-flash",
        "vendor": "deepseek",
        "name": "DeepSeek-V4-Flash",
        "adapter_type": "openai_compatible",
    },
    {
        "model_id": "deepseek-v4-pro",
        "vendor": "deepseek",
        "name": "DeepSeek-V4-Pro",
        "adapter_type": "openai_compatible",
    },
    {
        "model_id": "kimi-k2.6",
        "vendor": "kimi",
        "name": "Kimi K2.6",
        "adapter_type": "openai_compatible",
    },
    {
        "model_id": "glm-5.2",
        "vendor": "glm",
        "name": "GLM-5.2",
        "adapter_type": "openai_compatible",
    },
    {
        "model_id": "glm-4.7",
        "vendor": "glm",
        "name": "GLM-4.7",
        "adapter_type": "openai_compatible",
    },
]


async def seed_models(session: AsyncSession) -> None:
    """Seed default model configurations if the table is empty."""
    result = await session.execute(select(ModelConfig).limit(1))
    if result.scalar_one_or_none() is not None:
        return

    for model_data in DEFAULT_MODELS:
        session.add(ModelConfig(**model_data))

    await session.commit()
