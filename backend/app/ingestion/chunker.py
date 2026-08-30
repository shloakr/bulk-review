"""Page-aware chunking (spec §11).

Rules: never merge across pages; tables stay atomic when reasonably sized;
prose target ~700-1000 tokens with ~100-token overlap when a page needs
multiple chunks; exact source text and contributing bboxes retained.
"""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from .parser import ParsedBlock

ENC = tiktoken.get_encoding("cl100k_base")

TARGET_TOKENS = 850
MAX_TOKENS = 1000
OVERLAP_TOKENS = 100
TABLE_ATOMIC_MAX = 1200  # tables larger than this get split like prose


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    page: int
    chunk_index: int
    kind: str                 # "text" | "table"
    text: str
    bboxes: list[list[float]]


def _tok_len(text: str) -> int:
    return len(ENC.encode(text, disallowed_special=()))


def chunk_document(blocks: list[ParsedBlock]) -> list[Chunk]:
    chunks: list[Chunk] = []
    by_page: dict[int, list[ParsedBlock]] = {}
    for b in blocks:
        by_page.setdefault(b.page, []).append(b)

    doc_id = blocks[0].document_id if blocks else ""
    for page in sorted(by_page):
        page_chunks: list[tuple[str, str, list]] = []  # (kind, text, bboxes)
        cur_text: list[str] = []
        cur_bboxes: list = []
        cur_tokens = 0

        def flush():
            nonlocal cur_text, cur_bboxes, cur_tokens
            if cur_text:
                page_chunks.append(("text", "\n\n".join(cur_text), cur_bboxes))
                # keep tail as overlap seed for the next chunk
                tail_ids = ENC.encode("\n\n".join(cur_text), disallowed_special=())[-OVERLAP_TOKENS:]
                cur_text = [ENC.decode(tail_ids)] if tail_ids else []
                cur_bboxes = list(cur_bboxes[-1:])
                cur_tokens = len(tail_ids)

        for b in by_page[page]:
            btok = _tok_len(b.text)
            if b.kind == "table" and btok <= TABLE_ATOMIC_MAX:
                flush()
                # drop overlap seed before an atomic table
                cur_text, cur_bboxes, cur_tokens = [], [], 0
                page_chunks.append(("table", b.text, [b.bbox] if b.bbox else []))
                continue
            if cur_tokens + btok > MAX_TOKENS and cur_tokens >= TARGET_TOKENS // 2:
                flush()
            cur_text.append(b.text)
            if b.bbox:
                cur_bboxes.append(b.bbox)
            cur_tokens += btok
            if cur_tokens >= TARGET_TOKENS:
                flush()

        if cur_text and cur_tokens > OVERLAP_TOKENS:  # avoid pure-overlap remnant
            page_chunks.append(("text", "\n\n".join(cur_text), cur_bboxes))

        for i, (kind, text, bboxes) in enumerate(page_chunks):
            if not text.strip():
                continue
            chunks.append(Chunk(
                chunk_id=f"{doc_id}_P{page:04d}_C{i:02d}",
                document_id=doc_id, page=page, chunk_index=i,
                kind=kind, text=text, bboxes=[b for b in bboxes if b],
            ))
    return chunks
