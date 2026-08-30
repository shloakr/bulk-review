"""Dense (OpenAI) + sparse (SPLADE++ via FastEmbed) embedding helpers."""

from __future__ import annotations

import threading
from functools import lru_cache

from fastembed import SparseTextEmbedding
from openai import OpenAI

from ..config import get_settings

MAX_EMBED_TOKENS_APPROX_CHARS = 24000  # crude guard; chunks are ~1k tokens anyway

# fastembed model: guard construction and inference against concurrent threads
_splade_lock = threading.Lock()


@lru_cache
def _openai() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)


@lru_cache
def _splade_model() -> SparseTextEmbedding:
    return SparseTextEmbedding(model_name=get_settings().sparse_model_name)


def _splade() -> SparseTextEmbedding:
    with _splade_lock:
        return _splade_model()


def embed_dense(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    out: list[list[float]] = []
    clipped = [t[:MAX_EMBED_TOKENS_APPROX_CHARS] for t in texts]
    for i in range(0, len(clipped), 128):
        batch = clipped[i:i + 128]
        resp = _openai().embeddings.create(model=s.embedding_model, input=batch)
        out.extend(d.embedding for d in resp.data)
    return out


def embed_sparse(texts: list[str]) -> list[tuple[list[int], list[float]]]:
    """Returns (indices, values) per text for Qdrant sparse vectors."""
    out = []
    for emb in _splade().embed(texts, batch_size=16):
        out.append((emb.indices.tolist(), emb.values.tolist()))
    return out


@lru_cache(maxsize=512)
def embed_query(text: str) -> tuple[list[float], tuple[list[int], list[float]]]:
    """Cached: qualification re-runs the same planner queries per candidate doc."""
    dense = embed_dense([text])[0]
    with _splade_lock:
        sparse = list(_splade_model().query_embed(text))[0]
    return dense, (sparse.indices.tolist(), sparse.values.tolist())
