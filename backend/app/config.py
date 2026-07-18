"""
app/config.py

Single source of truth for configuration. Every value here comes from
an environment variable (set via .env locally, or via docker-compose /
your deployment platform in production).

Why centralize this instead of calling os.getenv() everywhere?
- One place to see everything the app depends on.
- pydantic-settings validates types and gives a clear error at startup
  if something required is missing, instead of a confusing crash later
  deep inside a request.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM provider keys (all optional individually — the router
    # skips any provider whose key is missing) ---
    GROQ_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None

    # --- Model names per provider (overridable without touching code) ---
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_MODEL: str = "gemini-2.5-flash"  # gemini-1.5-flash was fully shut down; 2.0-flash also retired June 2026
    OPENAI_MODEL: str = "gpt-4o-mini"

    # --- App behavior ---
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080,http://localhost:8123"

    # --- RAG ---
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"


settings = Settings()