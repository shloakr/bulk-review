"""Review lifecycle orchestrator: PLAN -> DISCOVER -> QUALIFY -> EXTRACT -> COMPLETE.

In-process asyncio execution under a shared semaphore (spec §23). A backend
restart loses in-flight reviews — intentional Step-1 limitation.
"""

from __future__ import annotations

import asyncio
import json
import time
import traceback
import uuid

from ..config import get_settings
from ..db import add_event, db, set_review_status
from ..retrieval.discovery import discover
from .extraction import extract_document
from .planner import plan_review
from .qualifier import qualify_document

_semaphore: asyncio.Semaphore | None = None


def model_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().max_model_concurrency)
    return _semaphore


def create_review(prompt: str) -> str:
    review_id = f"rev-{uuid.uuid4().hex[:10]}"
    now = time.time()
    with db() as conn:
        conn.execute(
            "INSERT INTO reviews (review_id, prompt, name, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (review_id, prompt, None, "PLAN", now, now),
        )
    return review_id


async def run_review(review_id: str):
    try:
        await _run_review(review_id)
    except Exception as e:
        traceback.print_exc()
        set_review_status(review_id, "FAILED", error=str(e))
        add_event(review_id, "FAILED", f"Review failed: {e}")


async def _run_review(review_id: str):
    sem = model_semaphore()
    with db() as conn:
        prompt = conn.execute(
            "SELECT prompt FROM reviews WHERE review_id=?", (review_id,)).fetchone()["prompt"]

    # ---- PLAN ----
    set_review_status(review_id, "PLAN")
    add_event(review_id, "PLAN", "Planning review")
    async with sem:
        plan = await plan_review(prompt)
    with db() as conn:
        conn.execute("UPDATE reviews SET plan=?, name=?, updated_at=? WHERE review_id=?",
                     (json.dumps(plan), plan.get("review_name"), time.time(), review_id))
    add_event(review_id, "PLAN", f"Planned {len(plan['retrieval_queries'])} retrieval queries",
              {"queries": plan["retrieval_queries"],
               "fields": [f["key"] for f in plan["fields"]]})

    # ---- DISCOVER ----
    set_review_status(review_id, "DISCOVER")
    with db() as conn:
        n_docs = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
    add_event(review_id, "DISCOVER", f"Searching {n_docs} documents")
    candidates = await asyncio.to_thread(discover, plan["retrieval_queries"])
    with db() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?)",
            [(review_id, c.document_id, c.score, c.rank,
              json.dumps(c.matching_queries), json.dumps(c.top_chunk_ids))
             for c in candidates],
        )
    add_event(review_id, "DISCOVER",
              f"Found {len(candidates)} candidate documents", {"count": len(candidates)})

    # ---- QUALIFY ----
    set_review_status(review_id, "QUALIFY")
    add_event(review_id, "QUALIFY", f"Qualifying {len(candidates)} candidates")
    qualified: list[str] = []
    done = 0
    lock = asyncio.Lock()

    async def _qualify(c):
        nonlocal done
        async with sem:
            try:
                out = await qualify_document(c.document_id, plan)
                err = None
            except Exception as e:
                out = {"is_relevant": None, "reason_summary": "", "evidence_chunk_ids": []}
                err = str(e)
        with db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO qualifications VALUES (?,?,?,?,?,?)",
                (review_id, c.document_id,
                 None if out["is_relevant"] is None else int(out["is_relevant"]),
                 out["reason_summary"], json.dumps(out["evidence_chunk_ids"]), err),
            )
        async with lock:
            done += 1
            if out.get("is_relevant"):
                qualified.append(c.document_id)
            if done % 10 == 0 or done == len(candidates):
                add_event(review_id, "QUALIFY",
                          f"Qualified {done}/{len(candidates)} candidates "
                          f"({len(qualified)} relevant)",
                          {"done": done, "total": len(candidates),
                           "relevant": len(qualified)})

    await asyncio.gather(*(_qualify(c) for c in candidates))
    qualified.sort()
    add_event(review_id, "QUALIFY",
              f"{len(qualified)} documents qualified as relevant")

    # ---- EXTRACT ----
    set_review_status(review_id, "EXTRACT")
    add_event(review_id, "EXTRACT", f"Extracting {len(qualified)} documents")
    with db() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO results (review_id, document_id, status) VALUES (?,?,?)",
            [(review_id, d, "pending") for d in qualified],
        )
    ex_done = 0

    async def _extract(doc_id: str):
        nonlocal ex_done
        with db() as conn:
            conn.execute("UPDATE results SET status='running' WHERE review_id=? AND document_id=?",
                         (review_id, doc_id))
        async with sem:
            try:
                out = await extract_document(doc_id, plan)
                with db() as conn:
                    conn.execute(
                        "UPDATE results SET fields=?, status='done', tool_calls=? "
                        "WHERE review_id=? AND document_id=?",
                        (json.dumps(out["fields"]), json.dumps(out["tool_calls"]),
                         review_id, doc_id),
                    )
            except Exception as e:
                with db() as conn:
                    conn.execute(
                        "UPDATE results SET status='failed', error=? "
                        "WHERE review_id=? AND document_id=?",
                        (str(e), review_id, doc_id),
                    )
        async with lock:
            ex_done += 1
            add_event(review_id, "EXTRACT",
                      f"Extracted {ex_done}/{len(qualified)} documents",
                      {"done": ex_done, "total": len(qualified), "document_id": doc_id})

    await asyncio.gather(*(_extract(d) for d in qualified))

    set_review_status(review_id, "COMPLETE")
    add_event(review_id, "COMPLETE", "Review complete")
