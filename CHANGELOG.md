# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- FastAPI backend with minimal static frontend served from `/` and `/static/*`.
- LangGraph orchestration with conditional tool routing (recipe sources, optional web search, optional RAG).
- Live recipe-source integration: Spoonacular + TheMealDB, including `auto` mode to combine both.
- Optional tracing env hooks for LangSmith/LangChain-style tracing.
- Developer docs: `AGENTS.md` and expanded `backend/README.md`.

### Changed

- Optional RAG dependencies moved to `backend/requirements-rag.txt` to keep base installs compatible on Windows/Python versions without required wheels.

### Fixed

- LangGraph graph now includes a `START` edge to satisfy LangGraph entrypoint requirements.
- Planner now falls back gracefully when the LLM is unavailable (e.g., quota errors) instead of crashing.
