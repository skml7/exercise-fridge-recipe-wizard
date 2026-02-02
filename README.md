# Fridge Recipe Wizard (Backend)

Fast weeknight recipe options from what you already have, powered by **FastAPI + LangGraph**.

## What you get

- **UI**: `GET /` (static HTML/CSS/JS)
- **API docs**: `GET /docs`
- **Health**: `GET /healthz`
- **Recipe options**: `POST /api/recipes/options`
- **Choose an option**: `POST /api/recipes/choose`

## Run locally (Windows 10, no WSL, `uv`)

From the repo root:

1. `cd .\backend`
2. Create + activate venv:
   - `uv venv .venv`
   - `.venv\Scripts\activate`
3. Install dependencies:
   - `uv pip install -r requirements.txt`
4. Create env file:
   - Copy `.env.example` → `.env`
5. Start the server:
   - `uvicorn app.main:app --reload`

Open:
- **UI**: `http://127.0.0.1:8000/`
- **Docs**: `http://127.0.0.1:8000/docs`

## Configuration (.env)

All configuration is read by `backend/app/config.py`.

- **Recipe sources**
  - `RECIPE_SOURCE_ENABLED=true|false`
  - `RECIPE_SOURCE_PROVIDER=auto|spoonacular|mealdb|none`
    - `auto`: use Spoonacular if `SPOONACULAR_API_KEY` exists, then fill remaining slots from TheMealDB.
    - `spoonacular`: Spoonacular only (requires key).
    - `mealdb`: TheMealDB only (defaults to dev key `1`).
    - `none`: disable recipe API tools (graph will proceed to optional fallbacks / local generation).
  - `SPOONACULAR_API_KEY=...` (optional)
  - `MEALDB_API_KEY=1` (TheMealDB dev key; change if you have your own)

- **LLM (optional)**
  - `OPENAI_API_KEY=...`
  - `OPENAI_MODEL=...`
  - If the key is missing or quota is exceeded, the planner will **fall back** to local heuristic generation.

- **Web search fallback (optional)**
  - `WEB_SEARCH_ENABLED=true|false`
  - Uses DuckDuckGo as a fallback context source when recipe APIs return no results.

- **RAG (optional)**
  - `RAG_ENABLED=true|false`
  - `RAG_COLLECTION=...`
  - `RAG_TOP_K=...`
  - See “Optional RAG install” below.

- **Tracing (optional)**
  - `LANGCHAIN_TRACING_V2=...`
  - `LANGCHAIN_PROJECT=...`
  - `LANGSMITH_API_KEY=...`

## Optional RAG install

RAG dependencies are intentionally separated to keep the base install lightweight and avoid platform wheel issues.

- `uv pip install -r requirements-rag.txt`

## API examples

### Get recipe options

Request:

```json
{
  "main_vegetables": ["broccoli", "carrots"],
  "aromatics": ["garlic", "onion"],
  "spices": ["cumin", "paprika"],
  "proteins": ["tofu"],
  "dietary": ["vegetarian"],
  "cuisine_mood": "spicy",
  "time_budget_minutes": 25,
  "servings": 2,
  "equipment": ["skillet"]
}
```

### Choose one option

`option_id` is a **0-based index** into the last returned options list.

```json
{
  "option_id": "0",
  "fridge_input": { "...": "same as above" }
}
```

## Troubleshooting

- **UI won’t open / connection refused**
  - The server is not running. Start it with `uvicorn app.main:app --reload` from `backend/`.

- **`No module named backend`**
  - You’re in `backend/` already; use `uvicorn app.main:app --reload`.
  - From repo root you can use `uvicorn backend.app.main:app --reload` instead.

- **500s when generating options**
  - If `OPENAI_API_KEY` is set but has no quota, the app will fall back automatically, but you may see warning logs.
  - If you want to avoid any LLM calls: clear `OPENAI_API_KEY` in `.env`.

- **DuckDuckGo warning about package rename**
  - You may see a runtime warning that `duckduckgo-search` was renamed to `ddgs`. It’s safe to ignore; functionality works.
