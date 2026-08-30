"""Download 160 real public FDA PDFs as distractor documents.

Source: openFDA Drugs@FDA endpoint (application_docs carry public
accessdata.fda.gov URLs for approval letters, labels, reviews, etc.).

Behavior:
  - gathers candidate doc URLs via the openFDA API
  - excludes obviously CMC/quality-flavored docs by type/url keywords
  - deterministic candidate ordering (seeded shuffle) so runs are reproducible
  - resumable: already-downloaded files (tracked in the manifest) are kept
  - handles dead URLs, non-PDF responses, dupes (sha256), oversized files

Outputs (staging):
    data/_staging/fda/FDA-0001.pdf ...
    data/_staging/fda_manifest.jsonl
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import httpx

SEED = 20260831
TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 160
# mode "general": letters/labels/etc, CMC-ish excluded (default).
# mode "quality": chemistry/product-quality review PDFs (ChemR etc.) only.
MODE = sys.argv[2] if len(sys.argv) > 2 else "general"
MAX_PDF_BYTES = 20 * 1024 * 1024
MIN_PDF_BYTES = 15 * 1024
CONCURRENCY = 3

ROOT = Path(__file__).resolve().parent.parent
_suffix = "" if MODE == "general" else "_quality"
OUT_DIR = ROOT / "data" / "_staging" / f"fda{_suffix}"
MANIFEST = ROOT / "data" / "_staging" / f"fda{_suffix}_manifest.jsonl"

OPENFDA = "https://api.fda.gov/drug/drugsfda.json"

# Prefer non-CMC document flavors (matched against openFDA doc type + URL)
INCLUDE_TYPES = {"letter", "label", "medical review", "review", "other"}
EXCLUDE_TERMS = [
    "chemistry", "cmc", "quality", "chemr", "prntlbl",  # prntlbl often huge image scans
    "excipient", "drug substance", "drug product",
]
PREFERRED_URL_HINTS = ["appletter", "label", "medr", "admincorres", "corres", "sumr", "cross"]
QUALITY_URL_HINTS = ["chemr", "prodqualr", "chemistry", "otherr"]
QUALITY_PDF_PAT = re.compile(r"chemr|prodqualr|chemistry|integrated.?quality|quality.?review", re.I)


def load_manifest() -> list[dict]:
    if not MANIFEST.exists():
        return []
    return [json.loads(l) for l in MANIFEST.read_text().splitlines() if l.strip()]


async def fetch_candidates(client: httpx.AsyncClient) -> list[dict]:
    """Page through openFDA collecting application_doc URLs."""
    candidates: dict[str, dict] = {}
    cfm_pages: dict[str, None] = {}
    limit = 100
    for skip in range(0, 15000, limit):
        try:
            r = await client.get(OPENFDA, params={"limit": limit, "skip": skip}, timeout=30)
            r.raise_for_status()
        except Exception as e:  # transient API failure: keep what we have
            print(f"openFDA page skip={skip} failed: {e}", file=sys.stderr)
            continue
        for app in r.json().get("results", []):
            brand = ""
            products = app.get("products") or []
            if products:
                brand = products[0].get("brand_name", "")
            for sub in app.get("submissions", []) or []:
                for doc in sub.get("application_docs", []) or []:
                    url = doc.get("url", "")
                    dtype = (doc.get("type") or "").lower()
                    low = (url + " " + dtype).lower()
                    if MODE == "quality" and url.lower().endswith((".cfm", ".html", ".htm")) and "review" in low:
                        cfm_pages.setdefault(url, None)
                        continue
                    if not url.lower().endswith(".pdf"):
                        continue
                    if MODE == "quality":
                        if not any(h in low for h in QUALITY_URL_HINTS):
                            continue
                    else:
                        if any(t in low for t in EXCLUDE_TERMS):
                            continue
                        if dtype not in INCLUDE_TYPES:
                            continue
                    title = f"{brand or app.get('application_number', '')} — {doc.get('type', 'Document')} ({doc.get('date', '')})"
                    candidates[url] = {"url": url, "title": title.strip(), "type": dtype}
        if MODE != "quality" and len(candidates) > max(3000, TARGET * 8):
            break
        if MODE == "quality" and len(cfm_pages) > TARGET * 4:
            break
    if MODE == "quality" and cfm_pages:
        # TOC pages build their PDF links in JavaScript, but the scheme is
        # deterministic: <toc_base>ChemR.pdf (newer) / <toc_base>_ChemR.pdf
        # (older). Synthesize candidates and let the download phase probe them.
        for toc in cfm_pages:
            base = re.sub(r"TOC\.(html?|cfm)$", "", toc, flags=re.I)
            if base == toc:
                continue
            for suffix in ("ChemR.pdf", "_ChemR.pdf"):
                full = base + suffix
                candidates.setdefault(full, {
                    "url": full,
                    "title": f"Chemistry Review — {full.rsplit('/', 1)[-1]}",
                    "type": "chemistry review",
                })
        print(f"{len(cfm_pages)} review TOCs -> {len(candidates)} chemistry-review probe URLs")

    out = list(candidates.values())
    rng = random.Random(SEED)
    rng.shuffle(out)
    hints = QUALITY_URL_HINTS if MODE == "quality" else PREFERRED_URL_HINTS
    out.sort(key=lambda c: min((hints.index(h) for h in hints if h in c["url"].lower()), default=99))
    return out


async def try_download(client: httpx.AsyncClient, cand: dict, idx_seen: set[str]) -> tuple[bytes, str] | None:
    for attempt in range(3):
        try:
            r = await client.get(cand["url"], timeout=60, follow_redirects=True)
            if r.status_code != 200:
                return None
            data = r.content
            if not data.startswith(b"%PDF"):
                return None
            if not (MIN_PDF_BYTES <= len(data) <= MAX_PDF_BYTES):
                return None
            sha = hashlib.sha256(data).hexdigest()
            if sha in idx_seen:
                return None
            return data, sha
        except (httpx.TimeoutException, httpx.TransportError):
            await asyncio.sleep(1.5 * (attempt + 1))
        except Exception:
            return None
    return None


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = load_manifest()
    have = [e for e in existing if (OUT_DIR / e["file"]).exists()]
    seen_sha = {e["sha256"] for e in have}
    seen_url = {e["url"] for e in have}
    print(f"resuming with {len(have)} already downloaded")

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}) as client:
        cands = await fetch_candidates(client)
        cands = [c for c in cands if c["url"] not in seen_url]
        print(f"{len(cands)} candidate URLs")

        sem = asyncio.Semaphore(CONCURRENCY)
        lock = asyncio.Lock()
        results = list(have)

        async def worker(cand):
            async with sem:
                if len(results) >= TARGET:
                    return
                got = await try_download(client, cand, seen_sha)
                if not got:
                    return
                data, sha = got
                async with lock:
                    if len(results) >= TARGET or sha in seen_sha:
                        return
                    seen_sha.add(sha)
                    n = len(results) + 1
                    fname = f"FDA-{n:04d}.pdf"
                    (OUT_DIR / fname).write_bytes(data)
                    results.append({"file": fname, "url": cand["url"], "title": cand["title"],
                                    "type": cand["type"], "sha256": sha, "bytes": len(data)})
                    if n % 10 == 0:
                        print(f"downloaded {n}/{TARGET}")

        # process in chunks so we stop dispatching once target reached
        CHUNK = 40
        for i in range(0, len(cands), CHUNK):
            if len(results) >= TARGET:
                break
            await asyncio.gather(*(worker(c) for c in cands[i:i + CHUNK]))

        MANIFEST.write_text("\n".join(json.dumps(e) for e in results) + "\n")
        print(f"done: {len(results)} PDFs in {OUT_DIR}")
        if len(results) < TARGET:
            print("WARNING: target not reached; re-run to fetch more", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
