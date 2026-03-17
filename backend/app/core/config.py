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
    EMBEDDING_MODEL: str = "nomic-embed-text"

    CRAWLER_REQUESTS_PER_MINUTE: int = 30
    CRAWLER_GLOBAL_REQUESTS_PER_MINUTE: int = 120

    CV_RETENTION_DAYS: int = 365
    MATCH_RETENTION_DAYS: int = 730
    EMAIL_DRAFT_RETENTION_DAYS: int = 90


settings = Settings()
