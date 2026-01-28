"""
Work RQ worker entrypoint.

This worker listens to the "work" queue which is used for operational task
assignment jobs. Keeping it separate from other queues prevents backlogs in one
domain from impacting others.
"""

from __future__ import annotations

import os
import sys

from rq import Queue, Worker
from rq.worker import SpawnWorker  # macOS-safe: uses os.spawn() instead of fork()

from app.queue.rq import get_redis_conn
from app.work.queue import QUEUE_NAME


# macOS + RQ fork() + native libs can crash without this.
if sys.platform == "darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")


def main() -> None:
    redis_conn = get_redis_conn()
    queue = Queue(QUEUE_NAME, connection=redis_conn)

    WorkerClass = SpawnWorker if sys.platform == "darwin" else Worker
    worker = WorkerClass([queue], connection=redis_conn)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()

