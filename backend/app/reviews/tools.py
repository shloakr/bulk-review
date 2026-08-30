"""Bounded per-document research tools (spec §19-20).

A DocumentToolbox is scoped to one document and one extraction session.
It records every chunk id it returns, so citation validation can enforce
"the model may only cite what a tool actually showed it".
"""

from __future__ import annotations

import json
import re

from ..config import get_settings
from ..db import db
from ..retrieval.hybrid import hybrid_search

TOOL_DEFS = [
    {
        "type": "function",
        "name": "search_document",
        "description": "Semantic + lexical hybrid search inside the current document. "
                       "Use for concepts and paraphrases (e.g. 'why was this grade selected').",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["query", "top_k"],
        },
    },
    {
        "type": "function",
        "name": "find_exact",
        "description": "Case-insensitive literal substring search (like Cmd-F) over the current "
                       "document's text. Use for identifiers: grade names, spec ids, ICH/USP refs.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string"},
                "max_hits": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query", "max_hits"],
        },
    },
    {
        "type": "function",
        "name": "open_page",
        "description": "Open 1-3 consecutive pages and read every parsed block in reading order. "
                       "Use to inspect full context around a hit.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "start_page": {"type": "integer", "minimum": 1},
                "end_page": {"type": "integer", "minimum": 1},
            },
            "required": ["start_page", "end_page"],
        },
    },
]


def _norm(text: str) -> str:
    # collapse whitespace + heal PDF line-break hyphenation for literal search
    text = re.sub(r"-\s*\n\s*", "", text)
    return re.sub(r"\s+", " ", text)


class DocumentToolbox:
    def __init__(self, document_id: str):
        self.document_id = document_id
        self.settings = get_settings()
        self.returned_chunk_ids: set[str] = set()
        # block ids shown via open_page -> (page, text) so citation validation
        # can translate a cited block id into its containing chunk
        self.returned_blocks: dict[str, tuple[int, str]] = {}
        self.calls: list[dict] = []

    # -- tool implementations ------------------------------------------------

    def search_document(self, query: str, top_k: int = 8) -> dict:
        top_k = min(int(top_k), self.settings.max_search_top_k)
        hits = hybrid_search(query, limit=top_k, document_id=self.document_id, prefetch=40)
        for h in hits:
            self.returned_chunk_ids.add(h.chunk_id)
        self.calls.append({"tool": "search_document", "arg": query})
        return {"results": [
            {"chunk_id": h.chunk_id, "page": h.page, "text": h.text, "score": round(h.score, 4)}
            for h in hits
        ]}

    def find_exact(self, query: str, max_hits: int = 20) -> dict:
        max_hits = min(int(max_hits), self.settings.max_find_hits)
        needle = _norm(query).lower()
        hits = []
        with db() as conn:
            rows = conn.execute(
                "SELECT chunk_id, page, text FROM chunks WHERE document_id=? "
                "ORDER BY page, chunk_index", (self.document_id,))
            for r in rows:
                hay = _norm(r["text"]).lower()
                if needle in hay:
                    hits.append({"chunk_id": r["chunk_id"], "page": r["page"], "text": r["text"]})
                    if len(hits) >= max_hits:
                        break
        for h in hits:
            self.returned_chunk_ids.add(h["chunk_id"])
        self.calls.append({"tool": "find_exact", "arg": query})
        return {"hits": hits, "total": len(hits)}

    def open_page(self, start_page: int, end_page: int) -> dict:
        start = max(1, int(start_page))
        end = max(start, int(end_page))
        end = min(end, start + self.settings.max_pages_per_open - 1)
        pages = []
        with db() as conn:
            for p in range(start, end + 1):
                blocks = [
                    {"block_id": r["block_id"], "kind": r["kind"], "text": r["text"],
                     "bbox": json.loads(r["bbox"]) if r["bbox"] else None}
                    for r in conn.execute(
                        "SELECT block_id, kind, text, bbox FROM blocks "
                        "WHERE document_id=? AND page=? ORDER BY block_index",
                        (self.document_id, p))
                ]
                chunk_ids = [r["chunk_id"] for r in conn.execute(
                    "SELECT chunk_id FROM chunks WHERE document_id=? AND page=? ORDER BY chunk_index",
                    (self.document_id, p))]
                if blocks:
                    pages.append({"page": p, "blocks": blocks, "citable_chunk_ids": chunk_ids})
                    self.returned_chunk_ids.update(chunk_ids)
                    for b in blocks:
                        self.returned_blocks[b["block_id"]] = (p, b["text"])
        self.calls.append({"tool": "open_page", "arg": f"{start}-{end}"})
        return {"pages": pages}

    # -- dispatch ------------------------------------------------------------

    def dispatch(self, name: str, args: dict) -> dict:
        try:
            if name == "search_document":
                return self.search_document(args.get("query", ""), args.get("top_k", 8))
            if name == "find_exact":
                return self.find_exact(args.get("query", ""), args.get("max_hits", 20))
            if name == "open_page":
                return self.open_page(args.get("start_page", 1), args.get("end_page", 1))
            return {"error": f"unknown tool {name}"}
        except Exception as e:
            return {"error": str(e)}
