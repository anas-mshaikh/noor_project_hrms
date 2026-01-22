"""
HR RQ worker entrypoint.

Run locally (outside Docker):
  python -m app.worker.hr_worker

Why a dedicated worker?
- We keep HR parsing jobs on a separate queue ("hr") from CCTV video jobs ("video_jobs")
  so a large batch of resumes doesn't block video processing.
"""

from __future__ import annotations

import os
import sys

from rq import Queue, Worker
from rq.worker import SpawnWorker  # macOS-safe: uses os.spawn() instead of fork()

from app.hr.queue import QUEUE_NAME
from app.queue.rq import get_redis_conn


# macOS + RQ fork() + native libs (opencv/onnx) can crash without this.
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

