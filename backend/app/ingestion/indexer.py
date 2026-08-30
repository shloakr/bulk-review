"""Corpus ingestion driver: parse -> chunk -> embed -> Qdrant + SQLite.

Idempotent/resumable: documents already registered in SQLite are skipped.
Run as a module:  python -m app.ingestion.indexer
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from qdrant_client import models

from ..config import get_settings
from ..db import db, init_db
from ..retrieval.qdrant import ensure_collection, get_client, point_id_for
from .chunker import Chunk, chunk_document
from .embeddings import embed_dense, embed_sparse
from .parser import parse_pdf


def ingest_document(pdf_path: Path, document_id: str) -> int:
    s = get_settings()
    blocks, page_count = parse_pdf(pdf_path, document_id)
    chunks = chunk_document(blocks)
    if not chunks:
        chunks = [Chunk(f"{document_id}_P0001_C00", document_id, 1, 0, "text", "(empty document)", [])]

    texts = [c.text for c in chunks]
    dense = embed_dense(texts)
    sparse = embed_sparse(texts)

    points = [
        models.PointStruct(
            id=point_id_for(c.chunk_id),
            vector={
                "dense": dv,
                "sparse": models.SparseVector(indices=si, values=sv),
            },
            payload={
                "document_id": c.document_id,
                "chunk_id": c.chunk_id,
                "page_number": c.page,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "kind": c.kind,
                "bbox": c.bboxes[0] if c.bboxes else None,
            },
        )
        for c, dv, (si, sv) in zip(chunks, dense, sparse)
    ]
    get_client().upsert(collection_name=s.collection, points=points)

    with db() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO blocks VALUES (?,?,?,?,?,?,?)",
            [(b.block_id, b.document_id, b.page, b.block_index, b.kind, b.text,
              json.dumps(b.bbox) if b.bbox else None) for b in blocks],
        )
        conn.executemany(
            "INSERT OR REPLACE INTO chunks VALUES (?,?,?,?,?,?,?)",
            [(c.chunk_id, c.document_id, c.page, c.chunk_index, c.kind, c.text,
              json.dumps(c.bboxes)) for c in chunks],
        )
        conn.execute(
            "INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?)",
            (document_id, pdf_path.name, page_count, len(chunks), time.time()),
        )
    return len(chunks)


def main():
    s = get_settings()
    init_db()
    ensure_collection()
    pdfs = sorted(s.corpus_dir.glob("DOC-*.pdf"))
    if not pdfs:
        sys.exit(f"no PDFs in {s.corpus_dir}; run scripts/build_dataset.py first")
    with db() as conn:
        done = {r["document_id"] for r in conn.execute("SELECT document_id FROM documents")}
    todo = [p for p in pdfs if p.stem not in done]
    print(f"{len(pdfs)} PDFs, {len(done)} already ingested, {len(todo)} to go")
    t0 = time.time()
    total_chunks = 0
    for i, p in enumerate(todo, 1):
        try:
            n = ingest_document(p, p.stem)
        except Exception as e:
            print(f"FAILED {p.stem}: {e}", file=sys.stderr)
            continue
        total_chunks += n
        if i % 10 == 0 or i == len(todo):
            rate = i / (time.time() - t0)
            print(f"[{i}/{len(todo)}] {p.stem} ({n} chunks) — {rate:.2f} docs/s")
    print(f"done: {total_chunks} new chunks in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
