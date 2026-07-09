from app.adapters.base import BaseAdapter
from app.adapters.openai_adapter import OpenAIAdapter
from app.adapters.anthropic_adapter import AnthropicAdapter
from app.adapters.gemini_adapter import GeminiAdapter
from app.config import settings


def get_adapter(adapter_type: str, vendor: str, base_url: str | None = None) -> BaseAdapter:
    api_key, default_base_url = settings.vendor_credentials.get(vendor, ("", ""))
    final_base_url = (base_url or default_base_url).rstrip("/")

    if adapter_type == "openai" or adapter_type == "openai_compatible":
        return OpenAIAdapter(api_key=api_key, base_url=final_base_url)
    elif adapter_type == "anthropic":
        return AnthropicAdapter(api_key=api_key)
    elif adapter_type == "gemini":
        return GeminiAdapter(api_key=api_key)
    else:
        raise ValueError(f"Unsupported adapter_type: {adapter_type}")
