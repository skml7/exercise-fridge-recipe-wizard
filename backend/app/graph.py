from __future__ import annotations

import concurrent.futures
import json
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
from .tracing import start_span
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes


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
    with start_span(
        "intake",
        OpenInferenceSpanKindValues.CHAIN,
        input_value=state["fridge_input"].model_dump_json(),
    ) as span:
        fridge_input = state["fridge_input"]
        if fridge_input.time_budget_minutes <= 0:
            fridge_input.time_budget_minutes = 30
        if fridge_input.servings <= 0:
            fridge_input.servings = 2
        if span is not None:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, fridge_input.model_dump_json())
        return {"fridge_input": fridge_input}


def _cuisine_mood_node(state: GraphState) -> GraphState:
    with start_span(
        "cuisine_mood",
        OpenInferenceSpanKindValues.CHAIN,
        input_value=state["fridge_input"].cuisine_mood,
    ) as span:
        cuisine_hint = state["fridge_input"].cuisine_mood.strip() or "quick and comforting"
        if span is not None:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, cuisine_hint)
        return {"cuisine_hint": cuisine_hint}


def _recipe_search_node(state: GraphState) -> GraphState:
    with start_span(
        "recipe_search",
        OpenInferenceSpanKindValues.TOOL,
        input_value=state["fridge_input"].model_dump_json(),
    ) as span:
        options = search_recipes(state["fridge_input"])
        if span is not None:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"{len(options)} options")
        return {"recipe_options": options}


def _rag_node(state: GraphState) -> GraphState:
    if not settings.rag_enabled:
        return {"rag_context": []}
    query = f"{state['cuisine_hint']} recipes with {', '.join(state['fridge_input'].main_vegetables)}"
    with start_span(
        "rag_retrieve",
        OpenInferenceSpanKindValues.RETRIEVER,
        input_value=query,
    ) as span:
        context = retrieve_rag_context(query)
        if span is not None:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"{len(context)} snippets")
        return {"rag_context": context}


def _web_search_node(state: GraphState) -> GraphState:
    if not settings.web_search_enabled:
        return {"search_context": []}
    query = f"{state['cuisine_hint']} weeknight recipe with {', '.join(state['fridge_input'].main_vegetables)}"
    with start_span(
        "web_search",
        OpenInferenceSpanKindValues.TOOL,
        input_value=query,
    ) as span:
        context = web_search(query)
        if span is not None:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"{len(context)} snippets")
        return {"search_context": context}


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
                "Create a concise weeknight recipe option as JSON with keys: "
                "title (string), ingredients (array of strings), steps (array of strings), "
                "time_minutes (number), difficulty (string). "
                "Use the provided ingredients. Keep it under 30 minutes. "
                "Return only valid JSON."
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
                with start_span(
                    "planner_llm",
                    OpenInferenceSpanKindValues.LLM,
                    input_value=str(messages),
                ) as span:
                    response = llm.invoke(messages).content or ""
                    if span is not None:
                        span.set_attribute(SpanAttributes.OUTPUT_VALUE, response)
                parsed = {}
                if response:
                    try:
                        parsed = json.loads(response)
                    except json.JSONDecodeError:
                        parsed = {}
                title = str(parsed.get("title") or f"{cuisine_hint.title()} {variant} Skillet")
                ingredients = parsed.get("ingredients")
                if not isinstance(ingredients, list) or not ingredients:
                    ingredients = fridge_input.main_vegetables + fridge_input.aromatics + fridge_input.spices
                steps = parsed.get("steps")
                if not isinstance(steps, list) or not steps:
                    steps = ["Combine ingredients and cook until done."]
                time_minutes = parsed.get("time_minutes")
                if not isinstance(time_minutes, int):
                    time_minutes = fridge_input.time_budget_minutes
                difficulty = str(parsed.get("difficulty") or "easy")
                options.append(
                    RecipeOption(
                        title=title,
                        cuisine=cuisine_hint,
                        time_minutes=time_minutes,
                        difficulty=difficulty,
                        ingredients=[str(item) for item in ingredients],
                        steps=[str(step) for step in steps],
                        notes="AI-generated option.",
                        source="generated",
                    )
                )
            return {"recipe_options": options}
        except Exception:
            # Fall back to local generation when the LLM is unavailable.
            pass

    variants = ["Quick", "Herby", "Spicy"]
    with start_span(
        "planner_local",
        OpenInferenceSpanKindValues.CHAIN,
        input_value=fridge_input.model_dump_json(),
    ) as span:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(_generate_option, fridge_input, cuisine_hint, context, variant)
                for variant in variants
            ]
            options = [future.result() for future in futures]
        if span is not None:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"{len(options)} options")
        return {"recipe_options": options}


def _critic_node(state: GraphState) -> GraphState:
    with start_span(
        "critic",
        OpenInferenceSpanKindValues.CHAIN,
    ) as span:
        options = state.get("recipe_options", [])
        options = sorted(options, key=lambda o: o.time_minutes)
        if span is not None:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"{len(options)} options")
        return {"recipe_options": options}


def _finalizer_node(state: GraphState) -> GraphState:
    with start_span(
        "finalizer",
        OpenInferenceSpanKindValues.CHAIN,
    ) as span:
        if span is not None:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, "finalized")
        return state


def _route_after_recipe_search(state: GraphState) -> str:
    if settings.force_llm:
        return "planner"
    options = state.get("recipe_options", [])
    if options:
        return "critic"
    if settings.rag_enabled:
        return "rag"
    if settings.web_search_enabled:
        return "web_search"
    return "planner"


def _route_after_rag(state: GraphState) -> str:
    if settings.force_llm:
        return "planner"
    if state.get("rag_context"):
        return "planner"
    if settings.web_search_enabled:
        return "web_search"
    return "planner"


def _route_after_web_search(state: GraphState) -> str:
    if settings.force_llm:
        return "planner"
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
    if settings.force_llm:
        graph.add_edge("cuisine", "planner")
    else:
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
    with start_span(
        "recipe_graph",
        OpenInferenceSpanKindValues.AGENT,
        input_value=fridge_input.model_dump_json(),
    ) as span:
        if settings.force_llm:
            state: GraphState = {"fridge_input": fridge_input}
            state.update(_intake_node(state))
            state.update(_cuisine_mood_node(state))
            state.update(_planner_node(state))
            state.update(_critic_node(state))
        else:
            graph = build_graph()
            state = graph.invoke({"fridge_input": fridge_input})
        options = state.get("recipe_options", [])
        if span is not None:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"{len(options)} options")
        return RecipeResponse(options=options)
