from .base import BaseLLM, LLMStep
from ..config import settings


def get_llm() -> BaseLLM:
    if settings.llm_provider in ("openai", "ollama"):
        from .openai_llm import OpenAICompatibleLLM
        return OpenAICompatibleLLM()
    from .mock_llm import MockLLM
    return MockLLM()
