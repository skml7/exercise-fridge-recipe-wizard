from __future__ import annotations

from typing import List

from .config import settings


def retrieve_rag_context(query: str) -> List[str]:
    if not settings.rag_enabled:
        return []

    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except Exception:
        return []

    client = chromadb.PersistentClient(path=".chroma")
    collection = client.get_or_create_collection(settings.rag_collection)
    if collection.count() == 0:
        return []

    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    query_embedding = embedder.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=settings.rag_top_k,
    )
    documents = results.get("documents", [[]])[0]
    return [doc for doc in documents if doc]
