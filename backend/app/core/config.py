"""Application configuration."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
CONFIG_ENV_FILE = ROOT_DIR / "config" / "app.env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(CONFIG_ENV_FILE),),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SYNC_DATABASE_URL: str = "postgresql://localhost/gradconnect"
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
    CRAWL4AI_FORCE_HEADLESS_IF_NO_DISPLAY: bool = True
    GOOGLE_BROWSER_HEADLESS: bool = True
    GOOGLE_BROWSER_TIMEOUT_MS: int = 30000
    GOOGLE_BROWSER_WAIT_MS: int = 1200
    LINKEDIN_SESSION_TTL_MINUTES: int = 120
    LINKEDIN_MAX_RESULTS_PER_QUERY: int = 10
    LINKEDIN_LI_AT: str = ""
    LINKEDIN_BROWSER_HEADLESS: bool = True
    LINKEDIN_BROWSER_TIMEOUT_MS: int = 30000
    LINKEDIN_BROWSER_SCROLL_STEPS: int = 4
    LINKEDIN_BROWSER_SCROLL_WAIT_MS: int = 1200
    SEARCH_PROVIDER_ORDER: str = "bing,bing_rss,duckduckgo"
    SEARCH_PROXY_URLS: str = ""
    SEARCH_ENABLE_GOOGLE: bool = False
    SEARCH_GOOGLE_COOLDOWN_SECONDS: int = 300

    # API rate limiting (requests per minute per IP)
    API_RATE_LIMIT_PER_MINUTE: int = 60
    API_RATE_LIMIT_UPLOAD_PER_MINUTE: int = 10

    # File upload limits
    MAX_CV_FILE_SIZE_MB: int = 5


settings = Settings()
