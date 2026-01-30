from __future__ import annotations

import concurrent.futures
import os
from typing import List, Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from .config import settings
from .models import FridgeInput, RecipeOption, RecipeResponse
from .rag import retrieve_rag_context
from .tools.recipe_search import search_recipes
from .tools.web_search import web_search


class GraphState(TypedDict, total=False):
    fridge_input: FridgeInput
    cuisine_hint: str
    recipe_options: List[RecipeOption]
    rag_context: List[str]
    search_context: List[str]
    errors: List[str]


def _get_llm() -> Optional[ChatOpenAI]:
    if not settings.openai_api_key:
        return None
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    return ChatOpenAI(model=settings.openai_model, temperature=0.4)


def _configure_tracing() -> None:
    if settings.langchain_tracing_v2:
        os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
    if settings.langchain_project:
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key


def _intake_node(state: GraphState) -> GraphState:
    fridge_input = state["fridge_input"]
    if fridge_input.time_budget_minutes <= 0:
        fridge_input.time_budget_minutes = 30
    if fridge_input.servings <= 0:
        fridge_input.servings = 2
    return {"fridge_input": fridge_input}


def _cuisine_mood_node(state: GraphState) -> GraphState:
    cuisine_hint = state["fridge_input"].cuisine_mood.strip() or "quick and comforting"
    return {"cuisine_hint": cuisine_hint}


def _recipe_search_node(state: GraphState) -> GraphState:
    options = search_recipes(state["fridge_input"])
    return {"recipe_options": options}


def _rag_node(state: GraphState) -> GraphState:
    if not settings.rag_enabled:
        return {"rag_context": []}
    query = f"{state['cuisine_hint']} recipes with {', '.join(state['fridge_input'].main_vegetables)}"
    return {"rag_context": retrieve_rag_context(query)}


def _web_search_node(state: GraphState) -> GraphState:
    if not settings.web_search_enabled:
        return {"search_context": []}
    query = f"{state['cuisine_hint']} weeknight recipe with {', '.join(state['fridge_input'].main_vegetables)}"
    return {"search_context": web_search(query)}


def _generate_option(
    fridge_input: FridgeInput,
    cuisine_hint: str,
    context: List[str],
    variant: str,
) -> RecipeOption:
    title = f"{cuisine_hint.title()} {variant} Skillet"
    ingredients = (
        fridge_input.main_vegetables
        + fridge_input.aromatics
        + fridge_input.spices
        + fridge_input.proteins
    )
    ingredients = [i for i in ingredients if i]
    steps = [
        f"Prep ingredients: {', '.join(ingredients) or 'basic pantry items'}.",
        f"Cook aromatics, then add main vegetables and {variant.lower()} seasoning.",
        "Finish with spices, adjust seasoning, and serve hot.",
    ]
    notes = None
    if context:
        notes = f"Tips: {context[0]}"
    return RecipeOption(
        title=title,
        cuisine=cuisine_hint,
        time_minutes=fridge_input.time_budget_minutes,
        difficulty="easy",
        ingredients=ingredients or ["pantry staples"],
        steps=steps,
        notes=notes,
        source="generated",
    )


def _planner_node(state: GraphState) -> GraphState:
    fridge_input = state["fridge_input"]
    cuisine_hint = state["cuisine_hint"]
    context = (state.get("rag_context") or []) + (state.get("search_context") or [])

    llm = _get_llm()
    if llm:
        try:
            prompt = (
                "Create a concise weeknight recipe option with title, ingredients, steps, time, and difficulty. "
                "Use the provided ingredients. Keep it under 30 minutes."
            )
            variants = ["Quick", "Herby", "Spicy"]
            options: List[RecipeOption] = []
            for variant in variants:
                messages = [
                    SystemMessage(content=prompt),
                    HumanMessage(
                        content=(
                            f"Ingredients: {fridge_input.model_dump()} | "
                            f"Cuisine mood: {cuisine_hint} | Variant: {variant} | "
                            f"Context: {context[:2]}"
                        )
                    ),
                ]
                response = llm.invoke(messages).content or ""
                options.append(
                    RecipeOption(
                        title=f"{cuisine_hint.title()} {variant} Skillet",
                        cuisine=cuisine_hint,
                        time_minutes=fridge_input.time_budget_minutes,
                        difficulty="easy",
                        ingredients=fridge_input.main_vegetables
                        + fridge_input.aromatics
                        + fridge_input.spices,
                        steps=[response] if response else ["Combine ingredients and cook until done."],
                        notes="AI-generated option.",
                        source="generated",
                    )
                )
            return {"recipe_options": options}
        except Exception:
            # Fall back to local generation when the LLM is unavailable.
            pass

    variants = ["Quick", "Herby", "Spicy"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(_generate_option, fridge_input, cuisine_hint, context, variant)
            for variant in variants
        ]
        options = [future.result() for future in futures]
    return {"recipe_options": options}


def _critic_node(state: GraphState) -> GraphState:
    options = state.get("recipe_options", [])
    options = sorted(options, key=lambda o: o.time_minutes)
    return {"recipe_options": options}


def _finalizer_node(state: GraphState) -> GraphState:
    return state


def _route_after_recipe_search(state: GraphState) -> str:
    options = state.get("recipe_options", [])
    if options:
        return "critic"
    if settings.rag_enabled:
        return "rag"
    if settings.web_search_enabled:
        return "web_search"
    return "planner"


def _route_after_rag(state: GraphState) -> str:
    if state.get("rag_context"):
        return "planner"
    if settings.web_search_enabled:
        return "web_search"
    return "planner"


def _route_after_web_search(state: GraphState) -> str:
    return "planner"


def build_graph() -> StateGraph:
    _configure_tracing()
    graph = StateGraph(GraphState)
    graph.add_node("intake", _intake_node)
    graph.add_node("cuisine", _cuisine_mood_node)
    graph.add_node("recipe_search", _recipe_search_node)
    graph.add_node("rag", _rag_node)
    graph.add_node("web_search", _web_search_node)
    graph.add_node("planner", _planner_node)
    graph.add_node("critic", _critic_node)
    graph.add_node("finalizer", _finalizer_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "cuisine")
    graph.add_edge("cuisine", "recipe_search")
    graph.add_conditional_edges(
        "recipe_search",
        _route_after_recipe_search,
        {"critic": "critic", "rag": "rag", "web_search": "web_search", "planner": "planner"},
    )
    graph.add_conditional_edges(
        "rag",
        _route_after_rag,
        {"planner": "planner", "web_search": "web_search"},
    )
    graph.add_conditional_edges(
        "web_search",
        _route_after_web_search,
        {"planner": "planner"},
    )
    graph.add_edge("planner", "critic")
    graph.add_edge("critic", "finalizer")
    graph.add_edge("finalizer", END)

    return graph.compile()


def run_recipe_graph(fridge_input: FridgeInput) -> RecipeResponse:
    graph = build_graph()
    state = graph.invoke({"fridge_input": fridge_input})
    options = state.get("recipe_options", [])
    return RecipeResponse(options=options)
