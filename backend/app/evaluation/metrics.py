"""Evaluation vs data/ground_truth.json (evaluation-only; never used live).

Two test sets live in the corpus:
    cmc        40 synthetic excipient-control documents, 4 fields
    stability  20 synthetic stability protocols, 6 fields

Which test a review belongs to is detected by mapping the review's planner
field keys against each test's field patterns; the test that maps the most
fields wins.
"""

from __future__ import annotations

import difflib
import json
import re

from ..config import get_settings
from ..db import db

TESTS: dict[str, dict[str, str]] = {
    # gt_key -> regex over the planner field's key+label (first match wins)
    "cmc": {
        "contradicts_current_spec": r"contradict|conflict|spec",
        "guidance_cited": r"guidance|cited",
        "justification": r"justif|rationale|basis|reason",
        "excipient_grade": r"grade|excipient",
    },
    "stability": {
        "storage_condition": r"storage|condition",
        "timepoints": r"time.?point|schedule|interval|pull",
        "acceptance_criteria": r"acceptance|criteri",
        "deviations": r"deviation",
        "bracketing_justification": r"bracket",
        "post_approval_commitment": r"commit|post.?approval",
    },
}


def _load_gt() -> dict:
    path = get_settings().data_dir / "ground_truth.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text())


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _numbers(s) -> set[float]:
    if isinstance(s, (list, tuple)):
        s = " ".join(str(x) for x in s)
    return {float(m) for m in re.findall(r"\d+(?:\.\d+)?", str(s))}


def _fuzzy(pred, truth) -> bool:
    if pred is None:
        return False
    p, t = _norm(pred), _norm(truth)
    if t in p or p in t:
        return True
    return difflib.SequenceMatcher(None, p, t).ratio() >= 0.6


def _paraphrase(pred, truth) -> bool:
    """Accept accurate paraphrases: every number preserved + most content words."""
    if _fuzzy(pred, truth):
        return True
    if pred is None:
        return False
    if not _numbers(truth) <= _numbers(pred):
        return False
    t_words = {w for w in _norm(truth).split() if len(w) > 3}
    p_words = set(_norm(pred).split())
    return bool(t_words) and len(t_words & p_words) / len(t_words) >= 0.5


def _map_field_keys(plan_fields: list[dict], test: str) -> dict[str, str]:
    """planner key -> gt key for the given test."""
    mapping: dict[str, str] = {}
    taken: set[str] = set()
    for gt_key, pat in TESTS[test].items():
        for f in plan_fields:
            if f["key"] in mapping:
                continue
            blob = _norm(f["key"] + " " + f.get("label", ""))
            if gt_key not in taken and re.search(pat, blob):
                mapping[f["key"]] = gt_key
                taken.add(gt_key)
                break
    return mapping


def detect_test(plan_fields: list[dict]) -> tuple[str, dict[str, str]]:
    best = ("cmc", {})
    for test in TESTS:
        m = _map_field_keys(plan_fields, test)
        if len(m) > len(best[1]):
            best = (test, m)
    return best


# ---------------------------------------------------------------- matchers ----

def _match_cmc(gt_key: str, f: dict, truth: dict) -> bool:
    v = f.get("value")
    if gt_key == "excipient_grade":
        if v is None:
            return False
        p, t = _norm(v), _norm(truth["value"])
        return p == t or t in p or p in t
    if gt_key == "guidance_cited":
        return isinstance(v, list) and {_norm(x) for x in v} == {_norm(x) for x in truth["value"]}
    if gt_key == "justification":
        return _fuzzy(v, truth["value"])
    return isinstance(v, bool) and v == truth["value"]  # contradicts_current_spec


def _match_stability(gt_key: str, f: dict, truth: dict) -> bool:
    v = f.get("value")
    tv = truth["value"]
    if gt_key == "storage_condition":
        return v is not None and _numbers(tv) <= _numbers(v)
    if gt_key == "timepoints":
        return v is not None and (set(float(x) for x in tv) - {0.0}) <= _numbers(v)
    if gt_key == "acceptance_criteria":
        return _fuzzy(v, tv) or (v is not None and _numbers(tv) <= _numbers(v))
    return _paraphrase(v, tv)  # deviations, bracketing_justification, post_approval_commitment


def _field_correct(test: str, gt_key: str, f: dict, truth: dict) -> bool:
    if truth["status"] == "not_found":
        v = f.get("value")
        return (f.get("status") == "not_found" or v in (None, "", [])
                or bool(re.search(r"\bno deviation|\bnone\b", _norm(v))))
    if test == "cmc":
        return _match_cmc(gt_key, f, truth)
    return _match_stability(gt_key, f, truth)


# --------------------------------------------------------------- evaluation ----

def evaluate_review(review_id: str) -> dict:
    gt = _load_gt()

    with db() as conn:
        plan_row = conn.execute("SELECT plan FROM reviews WHERE review_id=?",
                                (review_id,)).fetchone()
        plan = json.loads(plan_row["plan"]) if plan_row and plan_row["plan"] else {"fields": []}
        cand = {r["document_id"] for r in conn.execute(
            "SELECT document_id FROM candidates WHERE review_id=?", (review_id,))}
        qual = {r["document_id"] for r in conn.execute(
            "SELECT document_id FROM qualifications WHERE review_id=? AND is_relevant=1",
            (review_id,))}
        results = {r["document_id"]: r for r in conn.execute(
            "SELECT document_id, fields, status FROM results WHERE review_id=?", (review_id,))}
        chunk_pages = {r["chunk_id"]: r["page"] for r in conn.execute(
            "SELECT chunk_id, page FROM chunks")}

    test, key_map = detect_test(plan.get("fields", []))
    inv_map = {v: k for k, v in key_map.items()}
    gt_keys = list(TESTS[test])
    positives = {d for d, v in gt.items() if v.get("relevant_to") == test}

    # docs whose extraction produced substantive content (mirrors the UI's
    # empty-row rule: any non-boolean field with a real value)
    nonbool_keys = [f["key"] for f in plan.get("fields", []) if f.get("type") != "boolean"]
    substantive: set[str] = set()
    for doc_id, row in results.items():
        if row["status"] != "done" or not row["fields"]:
            continue
        fields = json.loads(row["fields"])
        if any(fields.get(k, {}).get("value") not in (None, "", [])
               for k in (nonbool_keys or list(fields))):
            substantive.add(doc_id)

    cand_hits = positives & cand
    qual_hits = positives & qual
    discovery = {
        "test": test,
        "candidate_recall": len(cand_hits) / len(positives) if positives else None,
        "qualified_recall": len(qual_hits) / len(positives) if positives else None,
        "qualified_precision": len(qual_hits) / len(qual) if qual else None,
        "final_precision": (len(positives & substantive) / len(substantive)
                            if substantive else None),
        "substantive_documents": len(substantive),
        "false_positives_with_content": sorted(substantive - positives),
        "candidates": len(cand),
        "qualified": len(qual),
        "missed_candidates": sorted(positives - cand),
        "missed_qualified": sorted((positives & cand) - qual),
        "false_positives_qualified": sorted(qual - positives),
    }

    per_field = {k: {"correct": 0, "total": 0, "errors": []} for k in gt_keys}
    cite_page_hits = cite_page_total = cite_cov_num = cite_cov_den = 0

    for doc_id in sorted(positives & set(results)):
        row = results[doc_id]
        if row["status"] != "done" or not row["fields"]:
            continue
        fields = json.loads(row["fields"])
        gt_fields = gt[doc_id]["fields"]
        for gt_key in gt_keys:
            plan_key = inv_map.get(gt_key)
            if not plan_key or plan_key not in fields:
                continue
            f = fields[plan_key]
            truth = gt_fields[gt_key]
            per_field[gt_key]["total"] += 1
            ok = _field_correct(test, gt_key, f, truth)
            per_field[gt_key]["correct"] += int(ok)
            if not ok:
                per_field[gt_key]["errors"].append(
                    {"document_id": doc_id, "predicted": f.get("value"),
                     "status": f.get("status"), "expected": truth["value"]})

            if truth["status"] == "found" and f.get("status") == "found":
                cite_cov_den += 1
                cids = f.get("citation_ids", [])
                if cids:
                    cite_cov_num += 1
                    pages = {chunk_pages.get(c) for c in cids} - {None}
                    expected = set(truth.get("expected_pages", []))
                    if expected:
                        cite_page_total += 1
                        cite_page_hits += int(bool(pages & expected))

    totals = sum(v["total"] for v in per_field.values())
    corrects = sum(v["correct"] for v in per_field.values())

    return {
        "review_id": review_id,
        "test": test,
        "field_key_map": key_map,
        "discovery": discovery,
        "extraction": {
            "overall_field_accuracy": corrects / totals if totals else None,
            "per_field": {
                k: {"accuracy": v["correct"] / v["total"] if v["total"] else None,
                    "correct": v["correct"], "total": v["total"], "errors": v["errors"][:10]}
                for k, v in per_field.items()
            },
            "extracted_positives": len([d for d in positives if d in results]),
        },
        "citations": {
            "citation_page_accuracy": cite_page_hits / cite_page_total if cite_page_total else None,
            "citation_coverage": cite_cov_num / cite_cov_den if cite_cov_den else None,
        },
    }
