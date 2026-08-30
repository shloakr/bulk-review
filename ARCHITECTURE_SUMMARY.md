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

The core design principle is to spend cheap retrieval compute broadly and expensive model reasoning only after the search space has collapsed.
```

Key decisions: **recall first, precision later**:a false negative at discovery is unrecoverable; a false positive can still be rejected during qualification or extraction. **Chunk-level search** so a 2-page section in a long
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
| Citation field hit rate (≥1 cited page correct) | 96.8% | 99.1% |
| Citation precision (each cited page correct) | 93.7% | 85.4% |
| All cited pages expected (per field) | 92.4% | 83.8% |

Citation metrics are tiered by strictness; precision treats any citation to
a page other than where ground truth rendered the fact as wrong, even when the
fact legitimately repeats there (chunk overlap, restatements) — read it as a
lower bound. Coverage (found claim ⇒ ≥1 validated citation) is enforced at
extraction time, so it is an invariant, not a result.

Test 2 reused the pipeline unchanged — a different prompt produced a
different 6-column schema at the same accuracy. Evaluation runs against
render-time ground truth (values + expected evidence pages recorded while
generating the synthetic PDFs), auto-detecting which test a review targets.

Ground-truth labels and expected values are evaluation-only and are never exposed to the planner, retriever, qualifier, or extraction agents.

## Cost & latency (measured)

Latency, wall-clock at `MAX_MODEL_CONCURRENCY=5` on the 620-doc corpus:
**both benchmark reviews complete in ~3m45s** — plan ~9s, discovery ~8s,
qualify 100 candidates ~1.5-2min, extract 20-41 docs ~1.5-2min. The document
researcher averaged 7.4 tool calls/doc (CMC) and 6.7 (stability). One-time
ingest: ~30-40 min for 620 PDFs (CPU SPLADE dominates; 915k embedding tokens = $0.12).

Cost, from an instrumented probe (per-call `usage` captured, × published prices):

| Stage (model) | Tokens per unit | Cost |
|---|---|---|
| Planner (terra) | ~420 in / ~410 out, 1 call | ~$0.006 / review |
| Qualifier (luna) | ~1.4k in / ~160 out per doc | ~$0.0005 / doc → **~$0.05 per 100 candidates** |
| Extractor (terra) | ~9k fresh + ~15k cached in, ~600 out per doc | **~$0.05-0.10 / doc** |

≈ **$2-4 per CMC review** (41 extractions), **$1-2 per stability review** (20).
Extraction is >90% of spend — which is the point of the staged design: the
100-candidate volume runs on the cheap model, and the expensive tool-using
model only touches documents that survived qualification. Responses-API
prompt caching cuts extractor input cost ~5× on the multi-turn sessions.

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
