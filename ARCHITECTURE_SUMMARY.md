# Arca Bulk Review — One-Page Summary

This product discovers the correct document set in an unstructured regulatory corpus → extract a user-defined structured
schema from every relevant document → attach auditable source evidence to every claim. One table, one row per document, every cell citable.

## Shape chosen

```text
PyMuPDF → page-aware chunks → dense (text-embedding-3-large) + SPLADE sparse → Qdrant (RRF hybrid)
→ LLM planner (queries + column schema from a natural-language ask)
→ chunk-level high-recall discovery (all docs → top-100 candidates)
→ LLM qualification per candidate (precision recovered by reasoning)
→ ONE bounded subagent research session per document (search_document · find_exact · open_page, ≤8 calls)
→ server-validated citations → Next.js records table + evidence drawer
```

Key decisions: **recall first, precision later** (a positive missed at
discovery is unrecoverable; a false positive costs one visible junk row that
extraction empties out); **chunk-level search** so a 2-page section in a long
PDF can't be diluted; **SPLADE for exact regulatory tokens** (`3.2.P.4`,
`PH-102`) + dense for paraphrase; **one session per document** because fields
are related (the contradiction column needs grade + spec jointly); **the model
may only cite chunk ids its tools actually returned** — validated server-side,
UI shows stored source text, never a model quotation.

## Measured (620-doc corpus: 60 hidden synthetic positives + 560 real FDA PDFs)

| | Test 1: CMC excipients (4 fields, 40 docs) | Test 2: Stability protocols (6 fields, 20 docs) |
|---|---|---|
| Prompt | *"Find the CMC excipient-control sections across the portfolio. For each relevant document, extract the excipient grade used, justification, guidance cited, and whether it contradicts the current specification."* | *"Take our stability protocols across the portfolio and for each one answer these six questions: what is the long-term storage condition, what are the testing timepoints, what stability acceptance criteria apply, were there any protocol deviations, what is the bracketing justification, and what post-approval stability commitment is made."* |
| Candidate / qualified recall | 100% / 100% | 100% / 100% |
| Final precision (rows with content) | 100% | 100% |
| Field accuracy | 97.5% (contradiction 40/40) | 97.5% (storage/timepoints/criteria 20/20) |
| Citation page accuracy / coverage | 96.8% / 100% | 99.1% / 100% |

Test 2 reused the pipeline unchanged — a different prompt produced a
different 6-column schema at the same accuracy. Evaluation runs against
render-time ground truth (values + expected evidence pages recorded while
generating the synthetic PDFs), auto-detecting which test a review targets.

## Rejected for the MVP — and the tradeoff taken

Temporal execution (scaffolded in `temporal_scaffold/`, not wired), S3, queue,
review agent, OCR pipeline, heavy rerankers, 500k indexing, multi-tenancy.
Tradeoff: reviews run in-process (`asyncio` + semaphore, SQLite, embedded
Qdrant) — a restart loses in-flight work. Accepted deliberately: the time went
into a real end-to-end loop with a measurable eval harness instead of
production machinery.

## Scale story (100k+ concurrent runs)

100k runs = 100k **durable document jobs**, not 100k concurrent GPT calls.
`BulkReviewWorkflow` (see scaffold) fans out per-document activities with
retries/heartbeats; a bounded worker fleet holds model pressure at
provider-rate-limit levels; per-tenant task queues give fairness. The Step-1
stages are already JSON-in/JSON-out functions, so activities are thin wrappers
— that seam was designed in. At 500k docs: hierarchical retrieval
(metadata filters + section-level index → chunk search inside candidates),
S3 for artifacts, Postgres for state.

## With more time

1. Wire Temporal + run 2k→10k→50k corpus scaling tests (candidate-budget vs recall curve)
2. Parser/OCR benchmark (Docling, Unstructured) scored on downstream citation accuracy 
3. Cross-document current-spec comparison (entity resolution, versioning, effective dates)
4. Review agent with for `conflicting`/`uncertain`/`not_found` cells, off the hot path, audit-logged
5. Real labeled eval set; tenant isolation + document ACLs enforced before retrieval reaches any model; cost/latency observability per review
