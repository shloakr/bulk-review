"""Finalize the corpus from all staging pools.

Pools:
    data/_staging/synthetic/     40 CMC positives        (test: cmc)
    data/_staging/stability/     20 stability positives  (test: stability)
    data/_staging/fda/           general FDA distractors
    data/_staging/fda_quality/   chemistry/quality-review near-miss distractors

Deterministic shuffle, rename to DOC-0001..DOC-NNNN, write:
    data/corpus/DOC-*.pdf
    data/manifest.jsonl        (attribution only — no labels, no pool markers)
    data/ground_truth.json     (evaluation-only; per-doc "relevant_to": test name)
"""

from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

SEED = 20260831
ROOT = Path(__file__).resolve().parent.parent
STAGING = ROOT / "data" / "_staging"
CORPUS = ROOT / "data" / "corpus"
MANIFEST = ROOT / "data" / "manifest.jsonl"
GT_OUT = ROOT / "data" / "ground_truth.json"


def load_jsonl_map(path: Path) -> dict:
    if not path.exists():
        return {}
    return {e["file"]: e for e in (json.loads(l) for l in path.read_text().splitlines() if l.strip())}


def main():
    syn = sorted((STAGING / "synthetic").glob("SYN-*.pdf"))
    stab = sorted((STAGING / "stability").glob("STB-*.pdf"))
    fda = sorted((STAGING / "fda").glob("FDA-*.pdf"))
    fdaq = sorted((STAGING / "fda_quality").glob("FDA-*.pdf"))
    if len(syn) != 40:
        sys.exit(f"expected 40 synthetic CMC PDFs, found {len(syn)}")
    if len(stab) != 20:
        sys.exit(f"expected 20 stability PDFs, found {len(stab)}")
    if not fda:
        sys.exit("no FDA PDFs staged")

    fda_meta = load_jsonl_map(STAGING / "fda_manifest.jsonl")
    fdaq_meta = load_jsonl_map(STAGING / "fda_quality_manifest.jsonl")
    cmc_gt = json.loads((STAGING / "synthetic_ground_truth.json").read_text())
    stab_gt = json.loads((STAGING / "stability_ground_truth.json").read_text())

    entries = ([("cmc", p, None) for p in syn]
               + [("stability", p, None) for p in stab]
               + [("fda", p, fda_meta.get(p.name)) for p in fda]
               + [("fdaq", p, fdaq_meta.get(p.name)) for p in fdaq])
    rng = random.Random(SEED)
    rng.shuffle(entries)

    if CORPUS.exists():
        shutil.rmtree(CORPUS)
    CORPUS.mkdir(parents=True)

    manifest_rows, gt = [], {}
    for i, (kind, src, meta) in enumerate(entries, start=1):
        doc_id = f"DOC-{i:04d}"
        shutil.copy2(src, CORPUS / f"{doc_id}.pdf")
        manifest_rows.append({
            "document_id": doc_id,
            "source_url": (meta or {}).get("url"),
            "source_title": (meta or {}).get("title"),
        })
        if kind == "cmc":
            entry = dict(cmc_gt[src.stem])
            entry["relevant_to"] = "cmc"
            entry["synthetic_id"] = src.stem
            gt[doc_id] = entry
        elif kind == "stability":
            entry = dict(stab_gt[src.stem])
            entry["relevant_to"] = "stability"
            entry["synthetic_id"] = src.stem
            gt[doc_id] = entry
        else:
            gt[doc_id] = {"relevant_to": None}

    MANIFEST.write_text("\n".join(json.dumps(r) for r in manifest_rows) + "\n")
    GT_OUT.write_text(json.dumps(gt, indent=2))
    n_cmc = sum(1 for v in gt.values() if v.get("relevant_to") == "cmc")
    n_stab = sum(1 for v in gt.values() if v.get("relevant_to") == "stability")
    print(f"corpus: {len(entries)} PDFs -> {CORPUS}")
    print(f"  cmc positives: {n_cmc} · stability positives: {n_stab} · "
          f"general distractors: {len(fda)} · quality-review distractors: {len(fdaq)}")


if __name__ == "__main__":
    main()
