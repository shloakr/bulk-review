"""FastAPI backend for Arca Bulk Review (Step 1, local-only)."""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .config import get_settings
from .db import db, init_db
from .evaluation.metrics import evaluate_review
from .reviews.runner import create_review, run_review

app = FastAPI(title="Arca Bulk Review")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_tasks: set[asyncio.Task] = set()


@app.on_event("startup")
def _startup():
    init_db()


# ---------------------------------------------------------------- corpus ----

@app.get("/api/corpus/status")
def corpus_status():
    s = get_settings()
    n_pdfs = len(list(s.corpus_dir.glob("DOC-*.pdf")))
    with db() as conn:
        n_docs = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
        n_chunks = conn.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]
    return {"pdfs": n_pdfs, "indexed_documents": n_docs, "chunks": n_chunks}


@app.get("/api/documents")
def list_documents():
    with db() as conn:
        rows = conn.execute(
            "SELECT document_id, filename, page_count, chunk_count FROM documents "
            "ORDER BY document_id").fetchall()
    return {"documents": [dict(r) for r in rows]}


@app.get("/api/documents/{document_id}")
def get_document(document_id: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE document_id=?",
                           (document_id,)).fetchone()
    if not row:
        raise HTTPException(404, "unknown document")
    return dict(row)


@app.get("/api/documents/{document_id}/pdf")
def get_pdf(document_id: str):
    s = get_settings()
    path = s.corpus_dir / f"{document_id}.pdf"
    if not path.exists() or not document_id.startswith("DOC-"):
        raise HTTPException(404, "unknown document")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@app.get("/api/documents/{document_id}/pages/{page}")
def get_page(document_id: str, page: int):
    with db() as conn:
        rows = conn.execute(
            "SELECT block_id, kind, text, bbox FROM blocks "
            "WHERE document_id=? AND page=? ORDER BY block_index",
            (document_id, page)).fetchall()
    if not rows:
        raise HTTPException(404, "no such page")
    return {"document_id": document_id, "page": page,
            "blocks": [{**dict(r), "bbox": json.loads(r["bbox"]) if r["bbox"] else None}
                       for r in rows]}


# --------------------------------------------------------------- reviews ----

class CreateReview(BaseModel):
    prompt: str


@app.post("/api/reviews", status_code=202)
async def post_review(body: CreateReview):
    if not body.prompt.strip():
        raise HTTPException(400, "empty prompt")
    review_id = create_review(body.prompt.strip())
    task = asyncio.create_task(run_review(review_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"review_id": review_id}


@app.get("/api/reviews")
def list_reviews():
    with db() as conn:
        rows = conn.execute(
            "SELECT review_id, name, prompt, status, created_at FROM reviews "
            "ORDER BY created_at DESC LIMIT 25").fetchall()
    return {"reviews": [dict(r) for r in rows]}


@app.get("/api/reviews/{review_id}")
def get_review(review_id: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM reviews WHERE review_id=?", (review_id,)).fetchone()
        if not row:
            raise HTTPException(404, "unknown review")
        r = dict(row)
        r["plan"] = json.loads(r["plan"]) if r["plan"] else None
        counts = {
            "candidates": conn.execute(
                "SELECT COUNT(*) c FROM candidates WHERE review_id=?", (review_id,)).fetchone()["c"],
            "qualified_done": conn.execute(
                "SELECT COUNT(*) c FROM qualifications WHERE review_id=?", (review_id,)).fetchone()["c"],
            "qualified_relevant": conn.execute(
                "SELECT COUNT(*) c FROM qualifications WHERE review_id=? AND is_relevant=1",
                (review_id,)).fetchone()["c"],
            "extract_done": conn.execute(
                "SELECT COUNT(*) c FROM results WHERE review_id=? AND status IN ('done','failed')",
                (review_id,)).fetchone()["c"],
            "extract_total": conn.execute(
                "SELECT COUNT(*) c FROM results WHERE review_id=?", (review_id,)).fetchone()["c"],
        }
        r["progress"] = counts
    return r


def _resolve_citations(conn, citation_ids: list[str]) -> list[dict]:
    out = []
    for cid in citation_ids:
        row = conn.execute(
            "SELECT chunk_id, document_id, page, text, bboxes FROM chunks WHERE chunk_id=?",
            (cid,)).fetchone()
        if row:
            out.append({
                "chunk_id": row["chunk_id"], "document_id": row["document_id"],
                "page": row["page"], "text": row["text"],
                "bbox": (json.loads(row["bboxes"]) or [None])[0] if row["bboxes"] else None,
            })
    return out


@app.get("/api/reviews/{review_id}/results")
def get_results(review_id: str):
    with db() as conn:
        rows = conn.execute(
            "SELECT document_id, fields, status, tool_calls, error FROM results "
            "WHERE review_id=? ORDER BY document_id", (review_id,)).fetchall()
        results = []
        for r in rows:
            fields = json.loads(r["fields"]) if r["fields"] else None
            if fields:
                for f in fields.values():
                    f["citations"] = _resolve_citations(conn, f.get("citation_ids", []))
            results.append({
                "document_id": r["document_id"], "status": r["status"],
                "fields": fields,
                "tool_calls": json.loads(r["tool_calls"]) if r["tool_calls"] else [],
                "error": r["error"],
            })
    return {"results": results}


@app.get("/api/reviews/{review_id}/events")
def get_events(review_id: str, after: int = 0):
    with db() as conn:
        rows = conn.execute(
            "SELECT id, ts, stage, message, data FROM events "
            "WHERE review_id=? AND id>? ORDER BY id", (review_id, after)).fetchall()
    return {"events": [{**dict(r), "data": json.loads(r["data"]) if r["data"] else None}
                       for r in rows]}


# ------------------------------------------------------------ evaluation ----

@app.post("/api/evaluate/{review_id}")
def run_evaluation(review_id: str):
    try:
        metrics = evaluate_review(review_id)
    except FileNotFoundError:
        raise HTTPException(400, "ground_truth.json not found")
    return JSONResponse(metrics)


@app.get("/api/evaluate/{review_id}")
def get_evaluation(review_id: str):
    return run_evaluation(review_id)
