"""Hybrid retrieval: dense + SPLADE prefetch fused with RRF (Qdrant Query API)."""

from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import models

import contextlib

from ..config import get_settings
from ..ingestion.embeddings import embed_query
from .qdrant import get_client, is_embedded, query_lock


@dataclass
class Hit:
    chunk_id: str
    document_id: str
    page: int
    kind: str
    text: str
    score: float


def hybrid_search(
    query: str,
    limit: int,
    document_id: str | None = None,
    prefetch: int | None = None,
) -> list[Hit]:
    s = get_settings()
    dense, (sp_idx, sp_val) = embed_query(query)
    flt = None
    if document_id:
        flt = models.Filter(must=[models.FieldCondition(
            key="document_id", match=models.MatchValue(value=document_id))])
    pf = prefetch or max(s.dense_prefetch, limit)
    # embedded QdrantLocal is not safe under concurrent query threads
    guard = query_lock if is_embedded() else contextlib.nullcontext()
    with guard:
        res = _query(s, dense, sp_idx, sp_val, flt, pf, limit)
    return [
        Hit(
            chunk_id=p.payload["chunk_id"],
            document_id=p.payload["document_id"],
            page=p.payload["page_number"],
            kind=p.payload.get("kind", "text"),
            text=p.payload["text"],
            score=p.score,
        )
        for p in res.points
    ]


def _query(s, dense, sp_idx, sp_val, flt, pf, limit):
    return get_client().query_points(
        collection_name=s.collection,
        prefetch=[
            models.Prefetch(query=dense, using="dense", limit=pf, filter=flt),
            models.Prefetch(
                query=models.SparseVector(indices=sp_idx, values=sp_val),
                using="sparse", limit=pf, filter=flt),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
