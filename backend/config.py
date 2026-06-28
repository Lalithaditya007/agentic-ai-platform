from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────────────────
    # Primary provider. Options: "groq" | "google" | "openai" | "openrouter"
    # Groq is free (6k tokens/min), Google Gemini is free (15 req/min via AI Studio)
    LLM_PROVIDER: str = "groq"
    OPEN_ROUTER: str = ""
    OPENROUTER_MODEL: str = "google/gemma-4-31b-it:free"
    GROQ_API_KEY: str = ""
    # Model names — can be overridden per-env without touching code
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    OPENAI_API_KEY: str = ""

    # ── DATABASES ─────────────────────────────────────────────────────────────
    # Default is empty so the env file value is always used.
    # The canonical value (Neon cloud) lives in d:\XLVenture\.env
    DATABASE_URL: str = ""
    REDIS_URL: str = ""
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""
    CHROMADB_PERSIST_PATH: str = "./chroma_data"

    # ── SEARCH & DATA APIs ────────────────────────────────────────────────────
    TAVILY_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    HUNTER_API_KEY: str = ""

    # ── COMPANY DATA APIS (new — multi-source discovery) ──────────────────
    # Apollo.io: sign up free at https://app.apollo.io/
    APOLLO_API_KEY: str = ""
    # OpenCorporates: free 500 req/day without key; register at opencorporates.com for more
    OPENCORPORATES_API_KEY: str = ""
    # Companies House (UK): register at developer.company-information.service.gov.uk
    COMPANIES_HOUSE_API_KEY: str = ""

    # ── OBSERVABILITY ─────────────────────────────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "universal-agentic-platform"

    # ── APP ───────────────────────────────────────────────────────────────────
    DEMO_MODE: bool = False
    APP_ENV: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",   # Silently ignore NEXT_PUBLIC_* and other frontend vars
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
