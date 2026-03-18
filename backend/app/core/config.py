"""Application configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://localhost/gradconnect"
    SYNC_DATABASE_URL: str = "postgresql://localhost/gradconnect"
    API_SECRET_KEY: str = "change-me"
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    # Optional override for embedding device, e.g. "cuda:0", "cuda:1", "cpu", "mps".
    EMBEDDING_DEVICE: str | None = None

    # LLM (vLLM + Qwen3.5)
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = "EMPTY"
    LLM_MODEL: str = "Qwen/Qwen3.5-0.8B"

    # LLM context & output sizing (tunable via env)
    # Qwen context can be very large (e.g. 262144), but we keep this configurable to control latency/cost.
    LLM_MAX_INPUT_CHARS: int = 200000
    LLM_MAX_OUTPUT_TOKENS_TOPICS: int = 256
    LLM_MAX_OUTPUT_TOKENS_PROFESSORS: int = 2048
    LLM_MAX_OUTPUT_TOKENS_EMAIL: int = 768

    CRAWL4AI_HEADLESS: bool = True

    CRAWLER_REQUESTS_PER_MINUTE: int = 30
    CRAWLER_GLOBAL_REQUESTS_PER_MINUTE: int = 120

    CV_RETENTION_DAYS: int = 365
    MATCH_RETENTION_DAYS: int = 730
    EMAIL_DRAFT_RETENTION_DAYS: int = 90

    # API rate limiting (requests per minute per IP)
    API_RATE_LIMIT_PER_MINUTE: int = 60
    API_RATE_LIMIT_UPLOAD_PER_MINUTE: int = 10

    # File upload limits
    MAX_CV_FILE_SIZE_MB: int = 5


settings = Settings()
