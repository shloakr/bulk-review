# Temporal scaffolding (Step 2 — not wired into the running app)

This directory is **scaffolding only**. Nothing in `backend/app/` imports it,
it is not on any code path of the demo, and `temporalio` is deliberately not
in `backend/requirements.txt`. It exists to show exactly how the Step-1
pipeline maps onto durable execution.

## Why Temporal (and why not in Step 1)

Step 1 runs a review as an in-process `asyncio` task: a backend restart loses
in-flight work. That is acceptable for a demo and intentional — the production
problem is different:

```text
1,000 reviews × 100 documents = 100,000 durable document jobs
                              ≠ 100,000 concurrent GPT calls
```

Temporal gives each document job durable state, retries, resumability, and
cancellation, while **worker concurrency stays bounded** by provider rate
limits and cost controls — scale the backlog, not the blast radius.

## Mapping (Step 1 code → Temporal)

| Step-1 code (unchanged)              | Temporal unit                             |
|--------------------------------------|-------------------------------------------|
| `reviews/runner.run_review`          | `BulkReviewWorkflow` (orchestration only) |
| `reviews/planner.plan_review`        | `plan_review` activity                    |
| `retrieval/discovery.discover`       | `discover_candidates` activity            |
| `reviews/qualifier.qualify_document` | `qualify_document` activity (fan-out)     |
| `reviews/extraction.extract_document`| `extract_document` activity (fan-out)     |
| `asyncio.Semaphore(5)`               | worker `max_concurrent_activities` + task-queue partitioning |

The pipeline stages are already pure(ish) functions with JSON-serializable
inputs/outputs, so the activities in `activities.py` are thin wrappers —
that seam was the point of the Step-1 design.

## Files

- `workflows.py` — `BulkReviewWorkflow`: plan → discover → fan-out qualify →
  fan-out extract → complete. Deterministic orchestration only; every model
  call lives in an activity with an explicit retry policy.
- `activities.py` — wrappers around the existing pipeline functions.
- `worker.py` — worker entrypoint (task queue `bulk-review`), where bounded
  concurrency is enforced.

## Running it (when you actually want to)

```bash
pip install temporalio
temporal server start-dev          # local dev server + UI on :8233
python -m temporal_scaffold.worker # from repo root, in another terminal
```

Then `POST /api/reviews` would start `BulkReviewWorkflow` via the Temporal
client instead of `asyncio.create_task` — a ~10-line change in
`backend/app/main.py`, deliberately not made in Step 1.

## Production notes (discussion points)

- **Per-tenant fairness**: one task queue per tier (or per tenant) plus
  worker-side rate limiting; priority reviews land on a faster queue.
- **Rate limits**: provider RPM/TPM enforced at the worker (shared limiter),
  not per-activity; activities heartbeat during long extractions.
- **Idempotency**: activity results keyed by `(review_id, document_id, stage)`
  and upserted — a retried activity overwrites its own row, never duplicates.
- **Large payloads**: activities pass ids, not documents; parsed text stays in
  the DB/object store (Temporal payloads should stay small).
- **Cancellation**: cancelling the workflow cancels outstanding activities;
  completed per-document results are kept.
