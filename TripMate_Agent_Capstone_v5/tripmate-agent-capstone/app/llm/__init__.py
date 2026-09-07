from .base import BaseLLM, LLMStep
from ..config import settings

# Every provider TripMate can talk to. "mock" is the offline, deterministic
# provider used by the automated test-suite; "openai", "groq" and "ollama"
# are live LLMs configured via .env / environment variables.
PROVIDERS = ("mock", "openai", "groq", "ollama")


def build_llm(provider: str) -> BaseLLM:
    """Construct a fresh LLM instance for the given provider name (raises for a
    misconfigured/missing API key so the caller can surface a clear error)."""
    if provider == "groq":
        from .groq_llm import GroqLLM
        return GroqLLM()
    if provider in ("openai", "ollama"):
        from .openai_llm import OpenAICompatibleLLM
        return OpenAICompatibleLLM(provider)
    from .mock_llm import MockLLM
    return MockLLM()


def get_llm() -> BaseLLM:
    """Build the LLM for the server's configured default provider (LLM_PROVIDER)."""
    return build_llm(settings.llm_provider)


def provider_status() -> dict:
    """Which providers are configured and usable right now — used by the UI's
    provider picker and the /api/providers endpoint. Never returns the key itself."""
    return {
        "default": settings.llm_provider,
        "providers": [
            {"id": "mock", "label": "Mock (offline, deterministic)", "configured": True},
            {"id": "openai", "label": "OpenAI", "configured": bool(settings.openai_api_key)},
            {"id": "groq", "label": "Groq", "configured": bool(settings.groq_api_key)},
            {"id": "ollama", "label": "Ollama (local)", "configured": True},
        ],
    }
