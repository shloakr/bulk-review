# Arca Bulk Review

Bulk regulatory document review: discover the right documents in a 620-PDF
corpus, extract a user-defined structured schema from every relevant one, with
auditable citations to source pages. Architecture, measured results, and
tradeoffs: see [`ARCHITECTURE_SUMMARY.md`](ARCHITECTURE_SUMMARY.md).

## Setup

Prereqs: Python 3.11+, Node 20+, an OpenAI API key.

The repo ships batteries-included: the built 620-PDF corpus, the embedded
Qdrant index, and the SQLite state DB with two completed benchmark reviews
(browsable — results, citations, eval — without any API calls).

```bash
cp .env.example .env        # put your OPENAI_API_KEY in .env

python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# terminal 1
cd backend && ../.venv/bin/uvicorn app.main:app --port 8000

# terminal 2
cd frontend && npm install && npm run dev
```

Open http://localhost:3000 and click a benchmark card (Test 1: CMC excipients
· Test 2: stability protocols) or type any prompt. A fresh review costs a few
dollars of OpenAI usage and takes ~4 min.

Evaluate against the hidden ground truth from the UI ("Run evaluation" on a
completed review) or the CLI:

```bash
.venv/bin/python scripts/evaluate.py     # most recent completed review
```

## Rebuilding the dataset from scratch (optional)

The 60 synthetic positives regenerate deterministically; the FDA distractor
set depends on what Drugs@FDA serves at download time, and
`ground_truth.json` is regenerated to match whatever corpus was built.

```bash
.venv/bin/python scripts/generate_synthetic_cmc.py
.venv/bin/python scripts/generate_synthetic_stability.py
.venv/bin/python scripts/download_fda_distractors.py 560   # arg = distractor count
.venv/bin/python scripts/build_dataset.py

rm -rf .qdrant_local data/app.db     # wipe old state
cd backend && ../.venv/bin/python -m app.ingestion.indexer && cd ..   # ~20 min
```

Optional Qdrant server mode instead of embedded: `docker compose up -d`, set
`QDRANT_URL=http://localhost:6333` in `.env` **before** ingesting. Embedded
mode allows one process at a time — ingest first, then start the backend.
