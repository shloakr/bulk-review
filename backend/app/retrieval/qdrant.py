"""Qdrant client + collection management.

Server mode when QDRANT_URL is set (docker compose), embedded local mode
otherwise. Both expose the same Query API (prefetch + RRF fusion).
"""

from __future__ import annotations

import threading
import uuid
from functools import lru_cache

from qdrant_client import QdrantClient, models

from ..config import get_settings

_client_lock = threading.Lock()
# Serializes queries in embedded mode: QdrantLocal is not thread-safe, and
# concurrent lru_cache misses would otherwise race the constructor too.
query_lock = threading.Lock()


@lru_cache
def _make_client() -> QdrantClient:
    s = get_settings()
    if s.qdrant_url:
        return QdrantClient(url=s.qdrant_url, timeout=60)
    return QdrantClient(path=str(s.qdrant_local_path))


def get_client() -> QdrantClient:
    with _client_lock:
        return _make_client()


def is_embedded() -> bool:
    return not get_settings().qdrant_url


def point_id_for(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def ensure_collection():
    s = get_settings()
    client = get_client()
    if client.collection_exists(s.collection):
        return
    client.create_collection(
        collection_name=s.collection,
        vectors_config={
            "dense": models.VectorParams(size=s.embedding_dim, distance=models.Distance.COSINE),
        },
        sparse_vectors_config={
            # no IDF modifier: SPLADE term weights already encode importance
            "sparse": models.SparseVectorParams(),
        },
    )
    for field, ftype in [("document_id", models.PayloadSchemaType.KEYWORD),
                         ("page_number", models.PayloadSchemaType.INTEGER),
                         ("kind", models.PayloadSchemaType.KEYWORD)]:
        try:
            client.create_payload_index(s.collection, field_name=field, field_schema=ftype)
        except Exception:
            pass  # embedded mode may not need/support explicit indexes
