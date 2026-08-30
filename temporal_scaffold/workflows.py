"""BulkReviewWorkflow — Step-2 durable orchestration (SCAFFOLDING ONLY).

Not imported by the running app. Requires `pip install temporalio` to run.

Design rules demonstrated here:
- The workflow is deterministic orchestration only: no I/O, no model calls,
  no timestamps/randomness outside Temporal APIs.
- Every model/DB touch is an activity with an explicit retry policy.
- Fan-out is per document, so each document job is independently retryable
  and a worker crash resumes exactly where it left off.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from . import activities

MODEL_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=5,
    non_retryable_error_types=["InvalidPromptError"],
)


@workflow.defn
class BulkReviewWorkflow:
    """plan → discover → fan-out qualify → fan-out extract → complete."""

    def __init__(self) -> None:
        self._progress: dict = {"stage": "PLAN"}

    @workflow.query
    def progress(self) -> dict:
        return self._progress

    @workflow.run
    async def run(self, review_id: str, prompt: str) -> dict:
        plan = await workflow.execute_activity(
            activities.plan_review,
            args=[review_id, prompt],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=MODEL_RETRY,
        )

        self._progress = {"stage": "DISCOVER"}
        candidate_ids: list[str] = await workflow.execute_activity(
            activities.discover_candidates,
            args=[review_id, plan],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=MODEL_RETRY,
        )

        self._progress = {"stage": "QUALIFY", "total": len(candidate_ids)}
        qualify_results = await asyncio.gather(*(
            workflow.execute_activity(
                activities.qualify_document,
                args=[review_id, doc_id, plan],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=MODEL_RETRY,
            )
            for doc_id in candidate_ids
        ))
        relevant = [d for d, ok in zip(candidate_ids, qualify_results) if ok]

        self._progress = {"stage": "EXTRACT", "total": len(relevant)}
        await asyncio.gather(*(
            workflow.execute_activity(
                activities.extract_document,
                args=[review_id, doc_id, plan],
                start_to_close_timeout=timedelta(minutes=15),
                heartbeat_timeout=timedelta(minutes=2),
                retry_policy=MODEL_RETRY,
            )
            for doc_id in relevant
        ))

        await workflow.execute_activity(
            activities.complete_review,
            args=[review_id],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=MODEL_RETRY,
        )
        self._progress = {"stage": "COMPLETE", "documents": len(relevant)}
        return {"review_id": review_id, "documents": len(relevant)}
