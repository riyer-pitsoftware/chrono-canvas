from pydantic_settings import BaseSettings


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

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    # Security
    secret_key: str = "change-me-in-production"

    # Content Moderation
    content_moderation_enabled: bool = True   # default-on keyword input validation
    # Optional layers (all off by default):
    # ENABLE_PUBLIC_DOMAIN_CHECK, ENABLE_PROMPT_GUARDRAIL via separate flags when implemented

    # Storage
    upload_dir: str = "./uploads"
    output_dir: str = "./output"

    # Rate Limiting
    rate_limit_rpm: int = 60
    llm_max_concurrent: int = 5

    # Research Cache (pgvector + sentence-transformers)
    research_cache_enabled: bool = True
    research_cache_threshold: float = 0.85   # cosine similarity threshold for a cache hit
    research_cache_model: str = "all-MiniLM-L6-v2"

    # Logging
    log_level: str = "INFO"


settings = Settings()
