"""
RQ queue configuration for the Work module.

We keep operational task assignment jobs on a dedicated queue so they don't block:
- CCTV video processing jobs ("video_jobs")
- HR parsing/screening jobs ("hr")
"""

from redis import Redis
from rq import Queue

from app.core.config import settings
from app.queue.rq import get_redis_conn


QUEUE_NAME = "work"

# Task assignment should be fast (pure SQL + deterministic scoring), but keep a
# conservative default timeout to avoid "stuck" jobs when a store has many tasks.
DEFAULT_JOB_TIMEOUT_SEC = 60 * 10  # 10 minutes


def get_work_redis_conn() -> Redis:
    return get_redis_conn()


def get_work_queue() -> Queue:
    # Allow overriding queue name if needed in the future.
    name = getattr(settings, "work_queue_name", QUEUE_NAME)
    return Queue(
        name=name,
        connection=get_work_redis_conn(),
        default_timeout=DEFAULT_JOB_TIMEOUT_SEC,
    )

