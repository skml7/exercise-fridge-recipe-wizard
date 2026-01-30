from __future__ import annotations

from typing import List

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .graph import run_recipe_graph
from .models import FridgeInput, RecipeChoiceRequest, RecipeResponse

app = FastAPI(title="Fridge Recipe Wizard")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/healthz")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/api/recipes/options", response_model=RecipeResponse)
def recipe_options(fridge_input: FridgeInput) -> RecipeResponse:
    return run_recipe_graph(fridge_input)


@app.post("/api/recipes/choose", response_model=RecipeResponse)
def choose_recipe(request: RecipeChoiceRequest) -> RecipeResponse:
    response = run_recipe_graph(request.fridge_input)
    options = response.options
    if not options:
        raise HTTPException(status_code=404, detail="No recipe options available.")

    selected = None
    try:
        index = int(request.option_id)
        if 0 <= index < len(options):
            selected = options[index]
    except ValueError:
        for option in options:
            if option.title.lower() == request.option_id.lower():
                selected = option
                break

    if not selected:
        raise HTTPException(status_code=404, detail="Selected recipe not found.")

    return RecipeResponse(options=options, selected=selected)


def run() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "dev",
    )


if __name__ == "__main__":
    run()
