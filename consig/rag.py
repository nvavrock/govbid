"""Chroma + OpenAI embeddings retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from openai import OpenAI

from consig.config import chroma_path, embedding_model, openai_api_key, top_k

COLLECTION_NAME = "govbid_corpus"


def _client() -> OpenAI:
    return OpenAI(api_key=openai_api_key())


def _collection():
    path = chroma_path()
    path.mkdir(parents=True, exist_ok=True)
    db = chromadb.PersistentClient(
        path=str(path),
        settings=Settings(anonymized_telemetry=False),
    )
    return db.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    resp = _client().embeddings.create(model=embedding_model(), input=texts)
    return [item.embedding for item in resp.data]


def search(query: str, k: int | None = None) -> list[dict[str, Any]]:
    k = k or top_k()
    coll = _collection()
    if coll.count() == 0:
        return []
    q_emb = embed_texts([query])[0]
    results = coll.query(
        query_embeddings=[q_emb],
        n_results=min(k, coll.count()),
        include=["documents", "metadatas", "distances"],
    )
    out: list[dict[str, Any]] = []
    docs = results.get("documents") or [[]]
    metas = results.get("metadatas") or [[]]
    for doc, meta in zip(docs[0], metas[0]):
        out.append(
            {
                "text": doc,
                "source": (meta or {}).get("source", "unknown"),
                "title": (meta or {}).get("title", ""),
            }
        )
    return out


def index_chunks(chunks: list[dict[str, Any]], *, reset: bool = False) -> int:
    """chunks: {id, text, source, title}"""
    path = chroma_path()
    path.mkdir(parents=True, exist_ok=True)
    db = chromadb.PersistentClient(
        path=str(path),
        settings=Settings(anonymized_telemetry=False),
    )
    if reset:
        try:
            db.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    coll = db.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    if not chunks:
        return 0
    batch_size = 64
    total = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        ids = [c["id"] for c in batch]
        texts = [c["text"] for c in batch]
        metadatas = [{"source": c["source"], "title": c.get("title", "")} for c in batch]
        embeddings = embed_texts(texts)
        coll.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
        total += len(batch)
    return total


def collection_count() -> int:
    try:
        return _collection().count()
    except Exception:
        return 0
