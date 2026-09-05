"""Runtime configuration for TripMate.

Everything can be overridden with environment variables (see .env.example) or at
run time through the /admin/config endpoint (used by the test-suite).
"""
import os
from dataclasses import dataclass, field
from typing import List


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # LLM provider: mock (offline, deterministic) | openai | ollama
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")          # blank = api.openai.com
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1")
    temperature: float = float(os.getenv("TEMPERATURE", "0.3"))

    # Agent behaviour
    max_iterations: int = int(os.getenv("MAX_ITERATIONS", "10"))
    session_spend_limit: int = int(os.getenv("SESSION_SPEND_LIMIT", "50000"))   # INR
    disabled_tools: List[str] = field(default_factory=lambda: [t for t in os.getenv("DISABLED_TOOLS", "").split(",") if t])

    # Planted defects (classroom). Set DEFECTS_ENABLED=false to get the "fixed" build.
    defects_enabled: bool = _bool("DEFECTS_ENABLED", True)

    # Observability
    db_path: str = os.getenv("TRIPMATE_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tripmate.db"))
    log_dir: str = os.getenv("TRIPMATE_LOG_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs"))
    cost_alert_threshold_inr: float = float(os.getenv("COST_ALERT_INR", "5.0"))
    langfuse_public_key: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    langfuse_host: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))

    def model_name(self) -> str:
        if self.llm_provider == "openai":
            return self.openai_model
        if self.llm_provider == "ollama":
            return f"ollama/{self.ollama_model}"
        return "mock-llm-1.0"


settings = Settings()
