"""PyMuPDF parsing: ordered text blocks + native tables per page."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass
class ParsedBlock:
    block_id: str
    document_id: str
    page: int              # 1-based
    block_index: int
    kind: str              # "text" | "table"
    text: str
    bbox: list[float] | None


def _table_to_markdown(table) -> str:
    rows = table.extract()
    if not rows:
        return ""
    def clean(cell):
        return (cell or "").replace("\n", " ").strip()
    lines = ["| " + " | ".join(clean(c) for c in rows[0]) + " |"]
    lines.append("|" + "---|" * len(rows[0]))
    for r in rows[1:]:
        lines.append("| " + " | ".join(clean(c) for c in r) + " |")
    return "\n".join(lines)


def parse_pdf(path: Path, document_id: str) -> tuple[list[ParsedBlock], int]:
    """Return (blocks in reading order, page_count)."""
    doc = pymupdf.open(path)
    blocks: list[ParsedBlock] = []
    for pno, page in enumerate(doc, start=1):
        page_items: list[tuple[float, ParsedBlock]] = []  # (y0, block)
        table_rects = []
        bidx = 0

        # native tables first, so overlapping text blocks can be skipped
        try:
            tabs = page.find_tables()
        except Exception:
            tabs = None
        if tabs:
            for t in tabs.tables:
                md = _table_to_markdown(t)
                if not md.strip():
                    continue
                rect = pymupdf.Rect(t.bbox)
                table_rects.append(rect)
                b = ParsedBlock(
                    block_id=f"{document_id}_P{pno:04d}_B{bidx:02d}",
                    document_id=document_id, page=pno, block_index=bidx,
                    kind="table", text=md, bbox=list(t.bbox),
                )
                page_items.append((rect.y0, b))
                bidx += 1

        for x0, y0, x1, y1, text, _bno, btype in page.get_text("blocks", sort=True):
            if btype != 0:
                continue  # skip image blocks
            text = text.strip()
            if not text:
                continue
            rect = pymupdf.Rect(x0, y0, x1, y1)
            # skip text already captured inside a table
            if any(rect.intersects(tr) and (rect & tr).get_area() > 0.5 * rect.get_area()
                   for tr in table_rects if not rect.is_empty):
                continue
            b = ParsedBlock(
                block_id=f"{document_id}_P{pno:04d}_B{bidx:02d}",
                document_id=document_id, page=pno, block_index=bidx,
                kind="text", text=text, bbox=[x0, y0, x1, y1],
            )
            page_items.append((y0, b))
            bidx += 1

        # reading order by vertical position (tables interleaved with prose)
        page_items.sort(key=lambda it: it[0])
        for i, (_, b) in enumerate(page_items):
            b.block_index = i
            b.block_id = f"{document_id}_P{b.page:04d}_B{i:02d}"
        blocks.extend(b for _, b in page_items)
    n = doc.page_count
    doc.close()
    return blocks, n
