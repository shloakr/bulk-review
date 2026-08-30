"""Stage A — GPT planner: natural-language instruction -> review plan."""

from __future__ import annotations

from ..config import get_settings
from .llm import structured_call

PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "review_name": {"type": "string"},
        "document_scope": {
            "type": "string",
            "description": "One-sentence description of which documents belong in this review.",
        },
        "retrieval_queries": {
            "type": "array",
            "minItems": 4,
            "maxItems": 6,
            "items": {"type": "string"},
        },
        "fields": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "key": {"type": "string", "description": "snake_case identifier"},
                    "label": {"type": "string"},
                    "type": {"type": "string", "enum": ["string", "string[]", "boolean", "number"]},
                    "instruction": {"type": "string"},
                },
                "required": ["key", "label", "type", "instruction"],
            },
        },
    },
    "required": ["review_name", "document_scope", "retrieval_queries", "fields"],
}

SYSTEM = """You plan bulk document reviews over a corpus of pharmaceutical regulatory PDFs.

Given a user instruction, produce:
- review_name: short human-readable name
- document_scope: precise one-sentence definition of which documents are in scope
- retrieval_queries: 4-6 diverse search queries for hybrid (semantic + lexical) retrieval.
  Use varied phrasing: regulatory section numbers/terms of art (e.g. 3.2.P.4, USP-NF,
  ICH guideline ids) in some queries, plain-language paraphrases in others.
- fields: the structured output columns the user asked to extract, one entry per field,
  with snake_case keys and a precise extraction instruction each. Choose the narrowest
  suitable type. Use boolean only for genuine yes/no determinations.

Field instructions must be scoped to the review subject, not the whole document.
Regulatory documents cite many guidelines and values in boilerplate (stability, methods,
quality-system sections); an instruction like "list every guideline cited" would sweep
those in. Write instructions that bind each field to the subject matter of the review
(e.g. "guidance cited in connection with the excipient grade selection/control", not
"guidance cited anywhere in the document")."""


async def plan_review(prompt: str) -> dict:
    s = get_settings()
    return await structured_call(
        model=s.planner_model,
        system=SYSTEM,
        user=prompt,
        name="review_plan",
        schema=PLAN_SCHEMA,
    )
