"""Stage C — candidate qualification (spec §17).

Per candidate document: gather top evidence chunks via document-filtered
hybrid retrieval over the planner queries, dedupe, cap, and ask GPT for a
relevance decision. Cited chunk ids are validated server-side against the
supplied evidence.
"""

from __future__ import annotations

import asyncio

from ..config import get_settings
from ..retrieval.hybrid import Hit, hybrid_search
from .llm import structured_call

QUALIFY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "is_relevant": {"type": "boolean"},
        "reason_summary": {"type": "string"},
        "evidence_chunk_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["is_relevant", "reason_summary", "evidence_chunk_ids"],
}

SYSTEM = """You qualify candidate documents for a bulk regulatory review.

You are given the review scope and text excerpts retrieved from ONE document.
Decide whether this document actually belongs in the review.

Rules:
- Judge only from the supplied excerpts.
- is_relevant=true only if the document itself contains the in-scope content
  (not merely vocabulary overlap, mentions in passing, or a different document
  type that references the topic).
- evidence_chunk_ids: list the ids of the excerpts that support your decision.
  Use ONLY ids shown in the excerpts. Do not invent ids, quotes, or pages."""


def gather_evidence(document_id: str, queries: list[str]) -> list[Hit]:
    s = get_settings()
    seen: dict[str, Hit] = {}
    per_query = max(3, s.qualify_evidence_chunks // max(len(queries), 1) + 1)
    for q in queries:
        for h in hybrid_search(q, limit=per_query, document_id=document_id, prefetch=40):
            seen.setdefault(h.chunk_id, h)
    hits = list(seen.values())[: s.qualify_evidence_chunks]
    return hits


async def qualify_document(document_id: str, plan: dict) -> dict:
    s = get_settings()
    hits = await asyncio.to_thread(gather_evidence, document_id, plan["retrieval_queries"])
    if not hits:
        return {"is_relevant": False, "reason_summary": "No retrievable content.",
                "evidence_chunk_ids": []}
    # full chunk text: chunks are already ~1k tokens max, and truncation here
    # can hide the in-scope section when it sits late in a page's chunk
    excerpts = "\n\n".join(
        f"[{h.chunk_id}] (page {h.page})\n{h.text}" for h in hits
    )
    user = (
        f"Review scope: {plan['document_scope']}\n"
        f"Fields to be extracted later: "
        + ", ".join(f["label"] for f in plan["fields"])
        + f"\n\nDocument: {document_id}\n\nExcerpts:\n\n{excerpts}"
    )
    out = await structured_call(
        model=s.qualifier_model, system=SYSTEM, user=user,
        name="qualification", schema=QUALIFY_SCHEMA,
    )
    # server-side validation: cited ids must come from supplied evidence
    supplied = {h.chunk_id for h in hits}
    out["evidence_chunk_ids"] = [c for c in out["evidence_chunk_ids"] if c in supplied]
    return out
