from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────
    LLM_PROVIDER: str = "groq"
    GOOGLE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # ── DATABASES ─────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:aditya1%40s@localhost:5432/platform_db?ssl=disable"
    REDIS_URL: str = ""
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""
    CHROMADB_PERSIST_PATH: str = "./chroma_data"

    # ── SEARCH & DATA APIs ────────────────────────────────────────
    TAVILY_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    HUNTER_API_KEY: str = ""

    # ── OBSERVABILITY ─────────────────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "universal-agentic-platform"

    # ── APP ───────────────────────────────────────────────────────
    DEMO_MODE: bool = False
    APP_ENV: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # Silently ignore NEXT_PUBLIC_* and other frontend vars
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

