from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    # Always load `backend/.env` regardless of current working directory.
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # LLM provider (optional)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    force_llm: bool = False

    # Arize AX tracing (optional)
    arize_space_id: str | None = None
    arize_api_key: str | None = None
    arize_project_name: str = "fridge-recipe-wizard"
    arize_endpoint: str | None = None

    # Recipe source providers (optional)
    recipe_source_enabled: bool = True
    recipe_source_provider: str = "auto"  # auto | spoonacular | mealdb | none
    spoonacular_api_key: str | None = None
    mealdb_api_key: str = "1"

    # RAG (optional)
    rag_enabled: bool = False
    rag_collection: str = "fridge-recipes"
    rag_top_k: int = 4

    # Web search fallback (optional)
    web_search_enabled: bool = True

    # Tracing (optional)
    langchain_tracing_v2: str | None = None
    langchain_project: str = "fridge-recipe-wizard"
    langsmith_api_key: str | None = None


settings = Settings()
