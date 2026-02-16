from __future__ import annotations

import json
import logging
from contextlib import nullcontext
from typing import Any, Iterator

from arize.otel import Endpoint, register
from openinference.instrumentation.langchain import LangChainInstrumentor
from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import trace as trace_api

from .config import settings

logger = logging.getLogger(__name__)

_TRACING_ENABLED = False
_TRACING_INIT_ERROR: str | None = None


def setup_tracing() -> None:
    """
    Initialize Arize AX tracing for LangGraph/LangChain.
    Safe to call multiple times; only initializes once.
    """
    global _TRACING_ENABLED
    global _TRACING_INIT_ERROR
    if _TRACING_ENABLED:
        return

    if not settings.arize_space_id or not settings.arize_api_key:
        _TRACING_INIT_ERROR = (
            "Arize tracing disabled: missing ARIZE_SPACE_ID and/or ARIZE_API_KEY in backend/.env"
        )
        logger.info(_TRACING_INIT_ERROR)
        return

    try:
        register_kwargs: dict[str, Any] = {
            "space_id": settings.arize_space_id,
            "api_key": settings.arize_api_key,
            "project_name": settings.arize_project_name,
        }
        if settings.arize_endpoint:
            endpoint_value = settings.arize_endpoint.strip()
            if endpoint_value.upper() == "ARIZE_EUROPE":
                register_kwargs["endpoint"] = Endpoint.ARIZE_EUROPE
            else:
                register_kwargs["endpoint"] = endpoint_value
        tracer_provider = register(**register_kwargs)
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

        _TRACING_ENABLED = True
        _TRACING_INIT_ERROR = None
        logger.info("Arize tracing enabled for project '%s'.", settings.arize_project_name)
    except Exception as e:
        _TRACING_ENABLED = False
        _TRACING_INIT_ERROR = f"Arize tracing init failed: {type(e).__name__}"
        logger.exception("Failed to initialize Arize tracing.")


def tracing_status() -> dict[str, Any]:
    """
    Safe runtime view of tracing configuration (no secrets).
    """
    langsmith_enabled = bool(
        (settings.langchain_tracing_v2 or "").strip().lower() in {"1", "true", "yes", "on"}
        and settings.langsmith_api_key
    )
    return {
        "arize": {
            "enabled": _TRACING_ENABLED,
            "project_name": settings.arize_project_name,
            "endpoint": settings.arize_endpoint,
            "missing_space_id": not bool(settings.arize_space_id),
            "missing_api_key": not bool(settings.arize_api_key),
            "last_error": _TRACING_INIT_ERROR,
        },
        "langsmith": {
            "enabled": langsmith_enabled,
            "project_name": settings.langchain_project,
            "configured_tracing_v2": bool(settings.langchain_tracing_v2),
            "missing_api_key": not bool(settings.langsmith_api_key),
        },
    }


def get_tracer():
    return trace_api.get_tracer("fridge-recipe-wizard")


def start_span(
    name: str,
    kind: OpenInferenceSpanKindValues,
    *,
    input_value: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any]:
    if not _TRACING_ENABLED:
        return nullcontext()

    attributes: dict[str, Any] = {
        SpanAttributes.OPENINFERENCE_SPAN_KIND: kind.value,
    }
    if input_value is not None:
        attributes[SpanAttributes.INPUT_VALUE] = input_value
    if metadata:
        attributes[SpanAttributes.METADATA] = json.dumps(metadata)

    tracer = get_tracer()
    return tracer.start_as_current_span(name, attributes=attributes)
