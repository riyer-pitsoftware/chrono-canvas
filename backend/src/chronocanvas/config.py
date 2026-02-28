import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_INSECURE_DEFAULT_KEY = "change-me-in-production"


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Database
    database_url: str = "postgresql+asyncpg://chronocanvas:chronocanvas@localhost:5432/chronocanvas"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM Providers
    ollama_base_url: str = "http://localhost:11434"
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Web Search
    serpapi_key: str = ""

    # LLM Routing
    default_llm_provider: str = "ollama"
    ollama_model: str = "llama3.1:8b"
    claude_model: str = "claude-sonnet-4-5-20250929"
    openai_model: str = "gpt-4o"

    # Image Generation
    image_provider: str = "mock"
    sd_api_url: str = "http://localhost:7860"
    comfyui_api_url: str = "http://localhost:8188"
    comfyui_model: str = "sdxl"  # "sdxl" or "flux"
    comfyui_sdxl_checkpoint: str = "juggernautXL_v9.safetensors"
    facefusion_api_url: str = "http://localhost:7861"
    facefusion_source_path: str = ""
    facefusion_enabled: bool = False

    # Pipeline toggles (for eval conditions)
    # When False, validation still runs but never triggers regenerate
    validation_retry_enabled: bool = True
    # When False, the face_search node is skipped entirely
    face_search_enabled: bool = True

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    # Security
    secret_key: str = _INSECURE_DEFAULT_KEY

    # Content Moderation
    content_moderation_enabled: bool = True   # default-on keyword input validation
    # Optional layers (all off by default):
    # ENABLE_PUBLIC_DOMAIN_CHECK, ENABLE_PROMPT_GUARDRAIL via separate flags when implemented

    # Storage
    upload_dir: str = "./uploads"
    output_dir: str = "./output"
    eval_dir: str = "./eval"

    # Rate Limiting
    rate_limit_rpm: int = 60
    llm_max_concurrent: int = 5

    # Research Cache (pgvector + sentence-transformers)
    research_cache_enabled: bool = True
    research_cache_threshold: float = 0.85   # cosine similarity threshold for a cache hit
    research_cache_model: str = "all-MiniLM-L6-v2"

    # Invariant checks (runtime validation of pipeline contracts)
    invariant_checks_enabled: bool = True    # run pre/postcondition checks on pipeline nodes
    invariant_strict: bool = False           # raise on violation (True) vs log warning (False)

    # Logging
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _reject_insecure_secret_key(self) -> "Settings":
        if self.secret_key == _INSECURE_DEFAULT_KEY:
            if "sqlite" in self.database_url:
                # Test/dev environment using SQLite — allow the default
                logger.warning("Using insecure default SECRET_KEY (ok for testing)")
            else:
                raise ValueError(
                    "SECRET_KEY is set to the insecure default. "
                    "Set a strong, unique SECRET_KEY via environment variable or .env file."
                )
        return self


settings = Settings()
