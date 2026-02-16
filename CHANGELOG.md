# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Manual OpenInference spans for LangGraph nodes and tool calls to ensure Arize tracing works even without LLM usage.
- OpenInference semantic conventions dependency to support manual tracing attributes.
- Request-level tracing spans around all HTTP endpoints.
- Dev-only `GET /debug/tracing` endpoint to show safe tracing status (enabled/disabled + missing config).
- Chat-first UI flow with a multi-turn assistant endpoint that asks follow-up questions before generating options.
- Added `FORCE_LLM` setting to force the LLM planner path even when recipe APIs return results.
- Added evaluation rubric, workflow guidance, and eval record schema documentation.

### Changed

- Bumped static asset cache-busting versions to ensure the chat UI script and styles load.
- When `FORCE_LLM` is enabled, skip recipe search nodes entirely and route straight to the planner.
- When `FORCE_LLM` is enabled, `run_recipe_graph` bypasses the graph and runs the planner pipeline directly.
- Enabled `FORCE_LLM` in the default dev environment to force generated recipes.
- LLM planner now requests JSON output and maps titles/ingredients/steps to match displayed options.
- Updated the hero banner image and removed option card thumbnails to reduce repetition.

### Fixed

- Tracing now reliably loads `backend/.env` regardless of the current working directory when starting Uvicorn.
- Arize tracing initialization failures now emit useful logs instead of failing silently.
- Arize tracing now supports an explicit OTLP endpoint for EU/region-specific routing.
- Arize tracing now accepts `ARIZE_ENDPOINT=ARIZE_EUROPE` to use the official EU endpoint enum.

### Security

- Removed an accidentally committed example Arize API key from `backend/.env.example`.

## [1.0.0] - 2026-02-02

### Added

- FastAPI backend with minimal static frontend served from `/` and `/static/*`.
- LangGraph orchestration with conditional tool routing (recipe sources, optional web search, optional RAG).
- Live recipe-source integration: Spoonacular + TheMealDB, including `auto` mode to combine both.
- Optional tracing env hooks for LangSmith/LangChain-style tracing.
- Arize AX tracing with OpenInference instrumentation for LangGraph/LangChain and OpenAI.
- Developer docs: `AGENTS.md` and expanded `backend/README.md`.

### Changed

- Optional RAG dependencies moved to `backend/requirements-rag.txt` to keep base installs compatible on Windows/Python versions without required wheels.
- Restyled the frontend to a clean, editorial layout and switched the hero/option visuals to real food photography.
- Added cache-busting query strings for static CSS/JS to ensure UI updates appear after reloads.

### Fixed

- LangGraph graph now includes a `START` edge to satisfy LangGraph entrypoint requirements.
- Planner now falls back gracefully when the LLM is unavailable (e.g., quota errors) instead of crashing.
