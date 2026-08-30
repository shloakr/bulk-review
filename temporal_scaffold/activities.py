"""Temporal activities wrapping the existing Step-1 pipeline (SCAFFOLDING ONLY).

Each activity is a thin, idempotent wrapper: JSON-in/JSON-out, persists its
own result keyed by (review_id, document_id), so a retry overwrites rather
than duplicates. The pipeline functions themselves are unchanged Step-1 code.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity

# The Step-1 backend package, imported lazily so this module only needs the
# app's dependencies when a worker actually runs.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


@activity.defn
async def plan_review(review_id: str, prompt: str) -> dict:
    from app.reviews.planner import plan_review as _plan
    return await _plan(prompt)  # persisting to the review row happens here in a real impl


@activity.defn
async def discover_candidates(review_id: str, plan: dict) -> list[str]:
    import asyncio
    from app.retrieval.discovery import discover
    candidates = await asyncio.to_thread(discover, plan["retrieval_queries"])
    return [c.document_id for c in candidates]


@activity.defn
async def qualify_document(review_id: str, document_id: str, plan: dict) -> bool:
    from app.reviews.qualifier import qualify_document as _qualify
    out = await _qualify(document_id, plan)
    return bool(out.get("is_relevant"))


@activity.defn
async def extract_document(review_id: str, document_id: str, plan: dict) -> dict:
    from app.reviews.extraction import extract_document as _extract
    activity.heartbeat(document_id)  # long-running: heartbeat between tool turns in a real impl
    return await _extract(document_id, plan)


@activity.defn
async def complete_review(review_id: str) -> None:
    from app.db import set_review_status
    set_review_status(review_id, "COMPLETE")
