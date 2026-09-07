"""Groq provider for TripMate.

Groq exposes an OpenAI-compatible Chat Completions API (base URL
https://api.groq.com/openai/v1) in front of very fast open-weight model
inference (Llama 3.x, Mixtral, Gemma, ...). Because the wire format matches
OpenAI's, we reuse the OpenAI-compatible provider's message-building,
planning and tool-calling logic wholesale (`OpenAICompatibleLLM`) and only
override how the client/model are constructed — same system prompt, same
tools, same guardrails, same agent loop as the `openai` and `ollama`
providers. Set LLM_PROVIDER=groq and GROQ_API_KEY to use it (see .env.example).
"""
from ..config import settings
from ..tools import TOOLS
from .openai_llm import OpenAICompatibleLLM


class GroqLLM(OpenAICompatibleLLM):
    name = "groq"

    def __init__(self):
        from openai import OpenAI  # lazy import so mock/other modes need no SDK installed
        if not settings.groq_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=groq but GROQ_API_KEY is not set. Get a free key at "
                "https://console.groq.com/keys and put it in .env."
            )
        self.client = OpenAI(base_url=settings.groq_base_url, api_key=settings.groq_api_key)
        self.model = settings.groq_model
        self.tools = [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in TOOLS.values()
        ]
