"""Temporal worker entrypoint (SCAFFOLDING ONLY — not part of the running app).

    pip install temporalio
    temporal server start-dev
    python -m temporal_scaffold.worker

Bounded concurrency lives HERE, not in the workflow: the backlog can hold
100k queued document jobs while max_concurrent_activities keeps actual model
pressure at provider-safe levels. Scale out by adding workers; partition task
queues per tenant/priority tier for fairness.
"""

from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from . import activities
from .workflows import BulkReviewWorkflow

TASK_QUEUE = "bulk-review"
MAX_CONCURRENT_MODEL_ACTIVITIES = 5  # mirrors Step-1 MAX_MODEL_CONCURRENCY


async def main():
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[BulkReviewWorkflow],
        activities=[
            activities.plan_review,
            activities.discover_candidates,
            activities.qualify_document,
            activities.extract_document,
            activities.complete_review,
        ],
        max_concurrent_activities=MAX_CONCURRENT_MODEL_ACTIVITIES,
    )
    print(f"worker up on task queue {TASK_QUEUE!r}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
