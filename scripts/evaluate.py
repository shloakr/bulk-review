"""Evaluate a completed review against data/ground_truth.json.

Usage:
    python scripts/evaluate.py [review_id]

With no argument, evaluates the most recent completed review.
Reads SQLite directly (no Qdrant/API needed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db import db  # noqa: E402
from app.evaluation.metrics import evaluate_review  # noqa: E402


def pct(x):
    return f"{100 * x:5.1f}%" if x is not None else "  n/a"


def main():
    if len(sys.argv) > 1:
        review_id = sys.argv[1]
    else:
        with db() as conn:
            row = conn.execute(
                "SELECT review_id FROM reviews WHERE status='COMPLETE' "
                "ORDER BY created_at DESC LIMIT 1").fetchone()
        if not row:
            sys.exit("no completed reviews")
        review_id = row["review_id"]

    m = evaluate_review(review_id)
    d, e, c = m["discovery"], m["extraction"], m["citations"]
    print(f"Review {review_id}  ·  test set: {m['test']}")
    print(f"  Candidate recall:        {pct(d['candidate_recall'])}   ({d['candidates']} candidates)")
    print(f"  Qualified recall:        {pct(d['qualified_recall'])}   ({d['qualified']} qualified)")
    print(f"  Qualified precision:     {pct(d['qualified_precision'])}")
    print(f"  Final precision:         {pct(d.get('final_precision'))}   "
          f"({d.get('substantive_documents', 0)} docs with content)")
    print(f"  Field accuracy:          {pct(e['overall_field_accuracy'])}")
    for k, v in e["per_field"].items():
        print(f"    {k:28s} {pct(v['accuracy'])}  ({v['correct']}/{v['total']})")
    print(f"  Citation field hit rate: {pct(c['citation_field_hit_rate'])}   (>=1 cited page correct)")
    print(f"  Citation precision:      {pct(c['citation_precision'])}   (each cited page correct)")
    print(f"  All citations expected:  {pct(c['fields_all_citations_expected'])}")
    print(f"  Citation coverage:       {pct(c['citation_coverage'])}   (invariant; <100% = bug)")
    if d["missed_candidates"]:
        print(f"  Missed at discovery:     {d['missed_candidates']}")
    if d["missed_qualified"]:
        print(f"  Missed at qualification: {d['missed_qualified']}")
    if d["false_positives_qualified"]:
        print(f"  Qualified false pos:     {d['false_positives_qualified']}")

    out = Path(__file__).resolve().parent.parent / "data" / f"eval_{review_id}.json"
    out.write_text(json.dumps(m, indent=2))
    print(f"\nfull report -> {out}")


if __name__ == "__main__":
    main()
