from __future__ import annotations

from typing import List

from duckduckgo_search import DDGS

from ..config import settings


def web_search(query: str, max_results: int = 4) -> List[str]:
    if not settings.web_search_enabled:
        return []

    results: List[str] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            snippet = item.get("body") or ""
            if snippet:
                results.append(snippet)
    return results
