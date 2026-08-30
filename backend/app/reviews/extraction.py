"""Stage D — one bounded tool-using GPT research session per document.

The model investigates the document with search_document / find_exact /
open_page, then returns one structured result object. Citations are
validated server-side against what the tools actually returned.
"""

from __future__ import annotations

import json

from ..config import get_settings
from ..db import db
from .llm import client, strict_schema
from .tools import TOOL_DEFS, DocumentToolbox

STATUSES = ["found", "not_found", "conflicting", "uncertain"]

SYSTEM = """You are a regulatory document researcher. You must extract a set of fields
from ONE document, using the provided tools to investigate it like a human reviewer:
semantic search for concepts, exact find (Cmd-F) for identifiers, page opening for context.

Method:
- Investigate enough to answer ALL fields; fields are related, so read surrounding context.
- After discovering an identifier (a grade name, spec id, guideline number), use find_exact
  to locate every other mention of it before concluding.
- If a determination requires comparing two statements (e.g. a selected value vs a current
  specification), locate and cite BOTH.
- Do not guess. If evidence is absent after a reasonable search, use status "not_found".
- If the document contains genuinely conflicting statements you cannot resolve, use
  "conflicting" and cite the conflicting passages. If evidence is ambiguous, use "uncertain".
- Distinguish historical/development/superseded references from the current/commercial one;
  the field value should reflect the current selection unless instructed otherwise.
- Keep values concise: the answer itself only (e.g. a grade name, not a sentence about it).
  Explanations, comparisons, and caveats belong in "note".
- Fields are scoped to the review subject. Regulatory documents cite many guidelines and
  values in unrelated boilerplate (stability, analytical methods, quality systems); include
  only what is stated in connection with the in-scope content, not everything in the document.
- A document stating that a used/selected value differs from a specification/reference value
  is NOT "conflicting" — that difference is usually exactly what a comparison field captures.
  Reserve "conflicting" for genuinely irreconcilable statements about the same fact.

Citations:
- Every non-null claim requires at least one citation_id.
- citation_ids must be CHUNK ids (format DOC-XXXX_PXXXX_CXX) exactly as returned by
  search_document/find_exact, or listed under citable_chunk_ids by open_page. Do not
  cite block ids (..._BXX). Never invent ids, quotes, or page numbers.
- If a document contains none of the in-scope content at all, return not_found for
  EVERY field — including boolean comparison fields: when there is nothing to compare,
  the answer is not_found, not false.

You have a limited tool budget; it is shown in the task. Be efficient."""


def result_schema(fields: list[dict]) -> dict:
    type_map = {
        "string": {"type": ["string", "null"]},
        "number": {"type": ["number", "null"]},
        "boolean": {"type": ["boolean", "null"]},
        "string[]": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
    }
    props = {}
    for f in fields:
        props[f["key"]] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "value": type_map.get(f["type"], {"type": ["string", "null"]}),
                "status": {"type": "string", "enum": STATUSES},
                "citation_ids": {"type": "array", "items": {"type": "string"}},
                "note": {"type": ["string", "null"],
                         "description": "Optional caveat, e.g. what conflicts or why uncertain."},
            },
            "required": ["value", "status", "citation_ids", "note"],
        }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"fields": {
            "type": "object", "additionalProperties": False,
            "properties": props, "required": list(props),
        }},
        "required": ["fields"],
    }


def _validate_citations(document_id: str, fields: dict, toolbox: DocumentToolbox) -> dict:
    """Spec §22: ids must exist, belong to this doc, and have been shown by a tool."""
    with db() as conn:
        page_chunks: dict[int, list[tuple[str, str]]] = {}
        existing = set()
        for r in conn.execute(
                "SELECT chunk_id, page, text FROM chunks WHERE document_id=? "
                "ORDER BY page, chunk_index", (document_id,)):
            existing.add(r["chunk_id"])
            page_chunks.setdefault(r["page"], []).append((r["chunk_id"], r["text"]))

    def to_chunk(cid: str) -> str | None:
        """Accept a chunk id, or translate a block id the model saw via open_page
        into the chunk containing that block's text."""
        if cid in existing and cid in toolbox.returned_chunk_ids:
            return cid
        blk = toolbox.returned_blocks.get(cid)
        if blk:
            page, text = blk
            probe = text.strip()[:80]
            for chunk_id, chunk_text in page_chunks.get(page, []):
                if probe and probe in chunk_text:
                    return chunk_id
            if page_chunks.get(page):
                return page_chunks[page][0][0]
        return None

    for key, f in fields.items():
        raw = f.get("citation_ids") or []
        valid = list(dict.fromkeys(c for c in (to_chunk(c) for c in raw) if c))
        dropped = len(raw) - len(valid)
        f["citation_ids"] = valid
        if dropped:
            f["note"] = ((f.get("note") or "") + f" [{dropped} invalid citation(s) removed]").strip()
        if f.get("status") == "found" and f.get("value") is not None and not valid:
            f["status"] = "uncertain"
            f["note"] = ((f.get("note") or "") + " [no valid citation for claim]").strip()
    return fields


async def extract_document(document_id: str, plan: dict) -> dict:
    """Run one logical extraction session; returns {fields, tool_calls}."""
    s = get_settings()
    toolbox = DocumentToolbox(document_id)
    with db() as conn:
        row = conn.execute("SELECT page_count FROM documents WHERE document_id=?",
                           (document_id,)).fetchone()
    page_count = row["page_count"] if row else "?"

    field_lines = "\n".join(
        f"- {f['key']} ({f['type']}): {f['instruction']}" for f in plan["fields"])
    user = (
        f"Document: {document_id} ({page_count} pages)\n"
        f"Review scope: {plan['document_scope']}\n\n"
        f"Fields to extract:\n{field_lines}\n\n"
        f"Tool budget: at most {s.max_tool_calls_per_doc} tool calls total. "
        f"When done (or out of budget), return the structured result."
    )

    schema = strict_schema("extraction_result", result_schema(plan["fields"]))
    kwargs = dict(model=s.extractor_model, tools=TOOL_DEFS, text=schema)

    resp = await client().responses.create(
        input=[{"role": "system", "content": SYSTEM},
               {"role": "user", "content": user}],
        **kwargs,
    )

    used = 0
    for _turn in range(s.max_tool_calls_per_doc + 4):
        calls = [it for it in resp.output if it.type == "function_call"]
        if not calls:
            break
        outputs = []
        for call in calls:
            used += 1
            if used > s.max_tool_calls_per_doc:
                result = {"error": "tool budget exhausted; return your final structured answer now"}
            else:
                try:
                    args = json.loads(call.arguments)
                except Exception:
                    args = {}
                result = toolbox.dispatch(call.name, args)
            outputs.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result),
            })
        force_final = used >= s.max_tool_calls_per_doc
        resp = await client().responses.create(
            input=outputs,
            previous_response_id=resp.id,
            tool_choice="none" if force_final else "auto",
            **kwargs,
        )

    try:
        parsed = json.loads(resp.output_text)
        fields = parsed["fields"]
    except Exception as e:
        raise RuntimeError(f"extractor returned unparseable output: {e}") from e

    fields = _validate_citations(document_id, fields, toolbox)
    return {"fields": fields, "tool_calls": toolbox.calls, "tool_call_count": used}
