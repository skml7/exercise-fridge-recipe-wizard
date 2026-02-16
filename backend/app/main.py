from __future__ import annotations

from typing import List
import re

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from langchain_core.messages import HumanMessage, SystemMessage

from .graph import run_recipe_graph, _get_llm
from .models import (
    ChatTurnRequest,
    ChatTurnResponse,
    FridgeInput,
    RecipeChoiceRequest,
    RecipeResponse,
)
from .tracing import setup_tracing, start_span, tracing_status
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

app = FastAPI(title="Fridge Recipe Wizard")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
def _startup() -> None:
    setup_tracing()


@app.middleware("http")
async def request_tracing(request: Request, call_next):
    with start_span(
        "http_request",
        OpenInferenceSpanKindValues.CHAIN,
        input_value=f"{request.method} {request.url.path}",
        metadata={
            "http.method": request.method,
            "http.path": request.url.path,
            "http.query": request.url.query,
        },
    ) as span:
        response = await call_next(request)
        if span is not None:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, str(response.status_code))
        return response


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/healthz")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/debug/tracing")
def debug_tracing() -> dict:
    if settings.app_env != "dev":
        raise HTTPException(status_code=404, detail="Not found")
    return tracing_status()


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


def _last_user_message(messages: list) -> str:
    for message in reversed(messages):
        if getattr(message, "role", "") == "user":
            return str(message.content or "")
    return ""


def _split_tokens(text: str) -> list[str]:
    cleaned = re.sub(r"\s+(and|&)\s+", ",", text, flags=re.IGNORECASE)
    parts = re.split(r"[,\n]", cleaned)
    return [p.strip() for p in parts if p.strip()]


def _extract_dietary(text: str) -> list[str]:
    keywords = {
        "vegetarian": "vegetarian",
        "vegan": "vegan",
        "gluten free": "gluten-free",
        "gluten-free": "gluten-free",
        "dairy free": "dairy-free",
        "dairy-free": "dairy-free",
        "keto": "keto",
        "low carb": "low-carb",
        "low-carb": "low-carb",
    }
    found = []
    lower = text.lower()
    for key, label in keywords.items():
        if key in lower and label not in found:
            found.append(label)
    return found


def _extract_mood(text: str) -> str | None:
    moods = {
        "spicy": "spicy",
        "comforting": "comforting",
        "cozy": "comforting",
        "italian": "italian-ish",
        "asian": "asian-ish",
        "fresh": "fresh",
        "quick": "quick and comforting",
    }
    lower = text.lower()
    for key, value in moods.items():
        if key in lower:
            return value
    return None


def _extract_time(text: str) -> int | None:
    match = re.search(r"(\d{1,2})\s*(?:min|mins|minutes)\b", text.lower())
    if match:
        return max(10, min(60, int(match.group(1))))
    return None


def _extract_servings(text: str) -> int | None:
    match = re.search(r"(?:serves?|for)\s*(\d{1,2})\b", text.lower())
    if match:
        return max(1, min(10, int(match.group(1))))
    return None


def _merge_unique(values: list[str], extra: list[str]) -> list[str]:
    seen = {v.lower() for v in values}
    merged = list(values)
    for item in extra:
        key = item.lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(item)
    return merged


def _build_followup(missing: list[str]) -> str:
    llm = _get_llm()
    fallback = "What ingredients do you have on hand? A comma-separated list is perfect."
    if not missing:
        return "Anything else you'd like to add?"
    if not llm:
        return fallback

    prompt = (
        "You are a friendly cooking assistant. Ask a single short follow-up question "
        "to collect the missing info. Keep it to one sentence."
    )
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=f"Missing info: {', '.join(missing)}"),
    ]
    with start_span(
        "chat_followup_llm",
        OpenInferenceSpanKindValues.LLM,
        input_value=str(messages),
    ) as span:
        response = llm.invoke(messages).content or fallback
        if span is not None:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, response)
    return response


@app.post("/api/chat/turn", response_model=ChatTurnResponse)
def chat_turn(payload: ChatTurnRequest) -> ChatTurnResponse:
    with start_span(
        "chat_turn",
        OpenInferenceSpanKindValues.CHAIN,
        input_value=str(payload.model_dump()),
    ) as span:
        fridge_input = payload.fridge_input or FridgeInput()
        latest_user_text = _last_user_message(payload.messages)

        tokens = _split_tokens(latest_user_text)
        if tokens:
            fridge_input.main_vegetables = _merge_unique(fridge_input.main_vegetables, tokens)

        dietary = _extract_dietary(latest_user_text)
        if dietary:
            fridge_input.dietary = _merge_unique(fridge_input.dietary, dietary)

        mood = _extract_mood(latest_user_text)
        if mood:
            fridge_input.cuisine_mood = mood

        time_budget = _extract_time(latest_user_text)
        if time_budget:
            fridge_input.time_budget_minutes = time_budget

        servings = _extract_servings(latest_user_text)
        if servings:
            fridge_input.servings = servings

        missing = []
        if not fridge_input.main_vegetables:
            missing.append("ingredients")

        if missing:
            assistant_message = _build_followup(missing)
            if span is not None:
                span.set_attribute(SpanAttributes.OUTPUT_VALUE, "ask")
            return ChatTurnResponse(
                next_action="ask",
                assistant_message=assistant_message,
                options=[],
                fridge_input=fridge_input,
            )

        response = run_recipe_graph(fridge_input)
        assistant_message = "Here are a few options based on what you shared."
        if span is not None:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, "options")
        return ChatTurnResponse(
            next_action="options",
            assistant_message=assistant_message,
            options=response.options,
            fridge_input=fridge_input,
        )


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
