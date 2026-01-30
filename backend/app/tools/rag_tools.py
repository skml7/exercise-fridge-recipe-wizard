from __future__ import annotations

from typing import List

from ..rag import retrieve_rag_context


def rag_lookup(query: str) -> List[str]:
    return retrieve_rag_context(query)
