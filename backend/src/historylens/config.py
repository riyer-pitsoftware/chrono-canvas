from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Database
    database_url: str = "postgresql+asyncpg://historylens:historylens@localhost:5432/historylens"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM Providers
    ollama_base_url: str = "http://localhost:11434"
    anthropic_api_key: str = ""
    openai_api_key: str = ""

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

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    # Security
    secret_key: str = "change-me-in-production"

    # Storage
    upload_dir: str = "./uploads"
    output_dir: str = "./output"

    # Rate Limiting
    rate_limit_rpm: int = 60
    llm_max_concurrent: int = 5

    # Logging
    log_level: str = "INFO"


settings = Settings()
