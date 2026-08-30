"""Append a batch of PDFs to an existing corpus WITHOUT reshuffling it.

Usage:
    python scripts/append_distractors.py <subdir>[:count] [<subdir>[:count] ...]

For each data/_staging/<subdir>/, takes up to `count` PDFs (all by default).
The combined batch is deterministically shuffled, then assigned the next
DOC-#### ids. Manifest rows are appended; ground truth entries are added:
  - if data/_staging/<subdir>_ground_truth.json exists, its entry is used and
    tagged with `"relevant_to": "<subdir>"` (a positives pool / test set);
  - otherwise `{"relevant_to": null}` (distractor).

Existing document ids, reviews, and index entries are untouched; run the
indexer afterwards to ingest only the new documents.

Caveat vs a full build_dataset.py shuffle: appended positives live somewhere
in the appended id range. Nothing in the live system reads id order, but for
a fully order-blind corpus, rebuild from scratch instead.
"""

from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

SEED = 20260902
ROOT = Path(__file__).resolve().parent.parent
STAGING = ROOT / "data" / "_staging"
CORPUS = ROOT / "data" / "corpus"
MANIFEST = ROOT / "data" / "manifest.jsonl"
GT = ROOT / "data" / "ground_truth.json"


def main():
    manifest = [json.loads(l) for l in MANIFEST.read_text().splitlines() if l.strip()]
    gt = json.loads(GT.read_text())
    existing_urls = {r.get("source_url") for r in manifest if r.get("source_url")}
    next_num = max(int(r["document_id"].split("-")[1]) for r in manifest) + 1

    batch = []  # (src_path, meta, gt_entry_or_None, subdir)
    for spec in sys.argv[1:]:
        subdir, _, cnt = spec.partition(":")
        count = int(cnt) if cnt else 10 ** 9
        pool = STAGING / subdir
        mpath = STAGING / f"{subdir}_manifest.jsonl"
        meta = {}
        if mpath.exists():
            meta = {e["file"]: e for e in (json.loads(l) for l in mpath.read_text().splitlines() if l.strip())}
        gpath = STAGING / f"{subdir}_ground_truth.json"
        pool_gt = json.loads(gpath.read_text()) if gpath.exists() else {}
        taken = 0
        for src in sorted(pool.glob("*.pdf")):
            if taken >= count:
                break
            m = meta.get(src.name, {})
            if m.get("url") and m["url"] in existing_urls:
                continue
            batch.append((src, m, pool_gt.get(src.stem), subdir))
            taken += 1
        print(f"{subdir}: staged {taken}")

    random.Random(SEED).shuffle(batch)
    for src, m, entry, subdir in batch:
        doc_id = f"DOC-{next_num:04d}"
        shutil.copy2(src, CORPUS / f"{doc_id}.pdf")
        manifest.append({"document_id": doc_id, "source_url": m.get("url"),
                         "source_title": m.get("title")})
        if entry is not None:
            e = dict(entry)
            e["relevant_to"] = subdir
            e["synthetic_id"] = src.stem
            gt[doc_id] = e
        else:
            gt[doc_id] = {"relevant_to": None}
        next_num += 1

    MANIFEST.write_text("\n".join(json.dumps(r) for r in manifest) + "\n")
    GT.write_text(json.dumps(gt, indent=2))
    n_pos = sum(1 for _, _, e, _ in batch if e is not None)
    print(f"appended {len(batch)} docs ({n_pos} positives); corpus now {len(manifest)}")


if __name__ == "__main__":
    main()
