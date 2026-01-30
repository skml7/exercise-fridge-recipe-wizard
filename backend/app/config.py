from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # LLM provider (optional)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Recipe source providers (optional)
    recipe_source_enabled: bool = True
    recipe_source_provider: str = "spoonacular"  # spoonacular | edamam | none
    spoonacular_api_key: str | None = None
    edamam_app_id: str | None = None
    edamam_app_key: str | None = None

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

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
