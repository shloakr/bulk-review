# Arca Bulk Review — Step 1 MVP

Local end-to-end prototype for bulk regulatory document review: discover the
right documents in a mixed 600-PDF corpus, then extract a user-defined
structured schema from every relevant document, with auditable citations to
original page/source text for every claim.

Demo prompt:

> Find the CMC excipient-control sections across the portfolio. For each
> relevant document, extract the excipient grade used, justification, guidance
> cited, and whether it contradicts the current specification.

## Architecture

```text
600 PDFs
 ↓
PyMuPDF (ordered blocks + native tables, page provenance)
 ↓
page-aware chunks (~700–1000 tokens, never merged across pages)
 ↓
OpenAI text-embedding-3-large (dense) + SPLADE++ via FastEmbed (sparse)
 ↓
Qdrant (named dense + sparse vectors, RRF hybrid fusion)
 ↓
GPT planner  →  4–6 retrieval queries + output field schema
 ↓
high-recall hybrid discovery (chunk-level, all docs → top 100 candidate docs)
 ↓
GPT candidate qualification (per-doc evidence bundle → relevance decision)
 ↓
per-document GPT researcher (ONE bounded tool session per doc)
   ↕  search_document · find_exact · open_page
 ↓
structured results + server-validated citations
 ↓
Next.js bulk-review table (Beautiful UI patterns)
```

## Why this shape

- **Retrieval and extraction are separate problems.** Stage B maximizes
  recall (a positive that never enters the candidate set is unrecoverable);
  Stage C buys precision back with stronger reasoning over per-document
  evidence.
- **Chunk-level search over all documents** prevents a small relevant section
  inside a long PDF from being diluted by a document-level embedding. Docs are
  ranked by the reciprocal rank of their best chunk per query, so long PDFs
  aren't rewarded for having many mediocre chunks.
- **SPLADE + dense hybrid**: SPLADE nails exact regulatory terminology
  (`3.2.P.4`, `PH-102`, `USP-NF`, `ICH Q8(R2)`); dense embeddings catch
  semantic equivalence ("basis for excipient selection" ≈ "justification for
  chosen grade"). RRF fuses ranks without pretending scores are comparable.
- **One research session per document** (not per field): grade, rationale,
  guidance and current spec are related facts, often pages apart; the
  contradiction determination requires joint reasoning across them.
- **Bounded tools keep extraction auditable**: the model can only cite chunk
  ids that a tool actually returned in its session; the server validates
  existence, document ownership, and session provenance, and the UI renders
  the original source text — never a model-generated quotation.

## Repository layout

```text
data/            corpus/ (DOC-0001..0600.pdf), manifest.jsonl, ground_truth.json
scripts/         generate_synthetic_cmc.py, download_fda_distractors.py,
                 build_dataset.py, evaluate.py
backend/app/     FastAPI app: ingestion/, retrieval/, reviews/, evaluation/
frontend/        Next.js app (prompt bar, task rows, records table, citation drawer)
temporal_scaffold/  Step-2 durable-execution scaffolding (not wired into the app)
```

`data/ground_truth.json` is **evaluation-only**. It is never read by the
planner, retriever, qualifier, or extractor, and file names / manifest carry
no relevance signal.

## Setup

Prereqs: Python 3.11+, Node 20+, an OpenAI API key. Docker is optional
(Qdrant server mode); by default the app uses qdrant-client's embedded local
mode, persisted at `.qdrant_local/`.

### Fast path (repo ships batteries-included)

The repo includes the built 620-PDF corpus, the embedded Qdrant index, and the
SQLite state DB — including the two completed benchmark reviews with their
results and citations. So running it is just:

```bash
cp .env.example .env        # put your OPENAI_API_KEY in .env
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend && ../.venv/bin/uvicorn app.main:app --port 8000   # terminal 1
cd frontend && npm install && npm run dev                     # terminal 2
# open http://localhost:3000 — click a benchmark card to run a fresh review
```

A fresh review costs a few dollars of OpenAI usage and takes ~5-10 min; the
two pre-loaded completed reviews are browsable (results, citations, eval)
without any API calls.

### Rebuilding the dataset from scratch (optional)

The 60 synthetic positives regenerate deterministically; the FDA distractor
set depends on what Drugs@FDA serves at download time, and
`ground_truth.json` is always regenerated to match whatever corpus was built,
so evaluation stays valid.

```bash
# 1. Build the dataset: 40 CMC + 20 stability synthetic positives
#    + 560 public FDA distractor PDFs (download takes ~5-10 min)
.venv/bin/python scripts/generate_synthetic_cmc.py
.venv/bin/python scripts/generate_synthetic_stability.py
.venv/bin/python scripts/download_fda_distractors.py 560   # arg = distractor count
.venv/bin/python scripts/build_dataset.py

# 2. Wipe the old state, then ingest + index (~20 min: parses, embeds, indexes)
rm -rf .qdrant_local data/app.db
cd backend && ../.venv/bin/python -m app.ingestion.indexer && cd ..

# then start the servers as in the fast path above
```

Evaluate from the CLI (equivalent of the UI's "Run evaluation" button):

```bash
.venv/bin/python scripts/evaluate.py     # most recent completed review
```

Optional Qdrant server mode: `docker compose up -d`, then set
`QDRANT_URL=http://localhost:6333` in `.env` **before** ingesting.
Note: embedded mode allows only one process at a time — ingest first, then
start the backend.

## The two benchmark tests

The corpus hides two synthetic positive sets among the real FDA distractors:

| Test | Positives | Fields |
|---|---|---|
| CMC excipient review | 40 docs | grade, justification, guidance cited, contradicts current spec |
| Stability protocols | 20 docs | storage condition, timepoints, acceptance criteria, deviations, bracketing justification, post-approval commitment |

Both are one click from the home page. Evaluation auto-detects which test a
review belongs to by mapping the planner's generated field keys against each
test's field patterns (`backend/app/evaluation/metrics.py`) — the eval card
shows which set it matched.

## Evaluation

`scripts/evaluate.py` (or `GET /api/evaluate/{review_id}`) computes, against
the hidden ground truth:

- **Discovery**: candidate recall, qualified recall, qualified precision.
  Candidate recall is the primary retrieval concern.
- **Extraction**: per-field accuracy (grade, guidance list, contradiction,
  normalized justification match) over the 40 synthetic positives.
- **Citations**: citation page accuracy vs expected evidence pages, and
  citation coverage (every found claim cites ≥1 validated source chunk).

## Known Step-1 limitations (intentional)

- Only 600 PDFs (spec default is 200; distractor count is a CLI arg); no production-scale (500k) indexing or load testing.
- No durable workflow engine and no queue: reviews run in-process via
  `asyncio` + a semaphore. **A backend restart loses in-flight reviews** —
  this limitation motivates Temporal in Step 2 (see `temporal_scaffold/`).
- Local filesystem for PDFs (no S3); local/embedded Qdrant; SQLite app state.
- No OCR pipeline — scanned-image PDFs yield little text.
- The "current specification" is assumed to live inside the same PDF;
  cross-document current-spec reasoning is Step 2.
- No auth / multi-tenancy / document ACLs.
- No post-extraction review agent; `conflicting`/`uncertain` cells are
  surfaced to the user instead.

See `ARCHITECTURE_SUMMARY.md` for the one-page interview summary and the
Step-2 scaling roadmap (hierarchical retrieval, Temporal, S3, metadata
catalog, cross-document reasoning, review agent).
