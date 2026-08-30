"""Stage B — high-recall corpus discovery (spec §15-16).

Chunk-level hybrid search across all documents per planner query, then
document aggregation via reciprocal-rank of each doc's best chunk per query.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import get_settings
from .hybrid import hybrid_search


@dataclass
class CandidateDoc:
    document_id: str
    score: float = 0.0
    rank: int = 0
    matching_queries: list[str] = field(default_factory=list)
    top_chunk_ids: list[str] = field(default_factory=list)


def discover(queries: list[str]) -> list[CandidateDoc]:
    s = get_settings()
    docs: dict[str, CandidateDoc] = {}
    for q in queries:
        hits = hybrid_search(q, limit=s.fused_limit, prefetch=s.dense_prefetch)
        best_rank: dict[str, int] = {}
        best_chunk: dict[str, str] = {}
        for rank, h in enumerate(hits, start=1):
            if h.document_id not in best_rank:
                best_rank[h.document_id] = rank
                best_chunk[h.document_id] = h.chunk_id
        for doc_id, rank in best_rank.items():
            c = docs.setdefault(doc_id, CandidateDoc(document_id=doc_id))
            c.score += 1.0 / (s.rrf_k + rank)
            c.matching_queries.append(q)
            if best_chunk[doc_id] not in c.top_chunk_ids:
                c.top_chunk_ids.append(best_chunk[doc_id])

    ranked = sorted(docs.values(), key=lambda c: c.score, reverse=True)
    ranked = ranked[: s.candidate_doc_budget]
    for i, c in enumerate(ranked, start=1):
        c.rank = i
    return ranked
