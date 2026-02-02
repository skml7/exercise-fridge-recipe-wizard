# AGENTS.md — Fridge Recipe Wizard

This repo is a **FastAPI + LangGraph** application that suggests weeknight recipes based on what you have on hand.

## Tech footprint

- **Backend**: Python 3.10+ (developed on Windows 10, no WSL), FastAPI + Uvicorn
- **Orchestration**: LangGraph (multi-step / conditional agent flow)
- **Tools**:
  - Recipe sources: **Spoonacular** (paid/free-tier) + **TheMealDB** (free dev key `1`)
  - Optional web-search fallback: DuckDuckGo
  - Optional RAG: Chroma + embeddings (installed separately)
- **Frontend**: minimal static HTML/CSS/JS served by the backend (`/` + `/static/*`)

## Where the “agents” live

- **Graph definition**: `backend/app/graph.py`
  - State type: `GraphState`
  - Nodes (functions): intake, cuisine mood, recipe search, optional RAG, optional web search, planner, critic, finalizer
  - Routing: conditional edges decide whether to use recipe APIs, then (optionally) RAG/search, then planning.

## Core design principles used here

- **Parallelism when it helps**: if the LLM is not available, the planner generates several variants in parallel (thread pool).
- **Tool-first for “grounded” results**: recipe APIs are preferred when enabled; they are “live data” sources.
- **Optional fallbacks**:
  - If recipe APIs yield no results, optionally pull context from RAG and/or web search to improve the generated options.
  - If the LLM is unavailable (missing key / quota / errors), the app **falls back to local heuristic generation** rather than failing.
- **Tracing hooks**: environment variables are read and applied (LangSmith-style tracing) without hard dependency on tracing being enabled.

## Environment/config conventions

- App config is centralized in `backend/app/config.py` (Pydantic settings).
- Runtime config comes from `backend/.env` (copy from `backend/.env.example`).
- Recipe source selection:
  - `RECIPE_SOURCE_PROVIDER=auto` uses Spoonacular if a key exists and then tops up with TheMealDB.
  - `RECIPE_SOURCE_PROVIDER=spoonacular` forces Spoonacular only.
  - `RECIPE_SOURCE_PROVIDER=mealdb` forces TheMealDB only.
  - `RECIPE_SOURCE_PROVIDER=none` disables recipe API tools.

## API surface (high level)

- `GET /` — serves the static UI
- `GET /docs` — Swagger UI
- `GET /healthz` — health check
- `POST /api/recipes/options` — returns recipe options
- `POST /api/recipes/choose` — returns chosen recipe (plus options)

## Adding new agents/tools (quick guide)

- Add a new tool in `backend/app/tools/` (pure function or thin wrapper around an API).
- Add a node function in `backend/app/graph.py`.
- Wire it into the graph with `add_node(...)` and edges / conditional routing.
- Keep tool calls **gated by config flags** so the app runs without keys.

## Common Windows notes

- Run the app from `backend/` using `uvicorn app.main:app --reload`.
- If you see dependency errors related to wheels (e.g., `onnxruntime`), keep optional components (like RAG) in separate requirements files.
