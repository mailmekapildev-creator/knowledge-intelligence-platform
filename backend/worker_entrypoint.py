"""
Standalone worker entrypoint. Demonstrates the queue-consumer shape referenced in
docs/architecture.md ("Worker Services") -- in the portfolio build, ingestion runs via
FastAPI BackgroundTasks (see backend/app/api/routes/ingest.py) so the whole pipeline is
exercisable with `docker compose up` alone; this file shows the production shape for
when a real broker (SQS/RabbitMQ) is wired in, without duplicating pipeline logic.
"""
from __future__ import annotations

import json
import os
import time

from app.worker.tasks import process_document

POLL_INTERVAL_SECONDS = float(os.environ.get("WORKER_POLL_INTERVAL", "2"))


def consume_forever():
    """
    Production implementation would replace this loop body with, e.g.:

        import boto3
        sqs = boto3.client("sqs")
        while True:
            messages = sqs.receive_message(QueueUrl=QUEUE_URL, MaxNumberOfMessages=10,
                                            WaitTimeSeconds=20)
            for msg in messages.get("Messages", []):
                job = json.loads(msg["Body"])
                process_document(**job)
                sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])

    The pipeline function (`process_document`) is identical whether it's invoked from a
    FastAPI BackgroundTask or a queue consumer -- that's the point of the abstraction.
    """
    print("[worker] no broker configured in this portfolio build; idling. "
          "Wire in SQS/RabbitMQ per the docstring above for a production deployment.")
    while True:
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    consume_forever()
