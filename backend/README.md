# Fridge Recipe Wizard (Backend)

## Run locally (Windows 10, no WSL)

1. Install `uv` for Windows and ensure it is on PATH.
2. Create and activate a virtual environment:
   - `uv venv .venv`
   - `.venv\Scripts\activate`
3. Install dependencies:
   - `uv pip install -r requirements.txt`
   - Optional (RAG): `uv pip install -r requirements-rag.txt`
4. Copy `.env.example` to `.env` and add API keys if you want recipe APIs, RAG, or tracing.
5. Start the app (from `backend/`):
   - `uvicorn app.main:app --reload`

Open `http://localhost:8000/` for the UI and `http://localhost:8000/docs` for the API.
