"""
RQ queue configuration for the HR module.

We intentionally keep HR jobs on a separate queue from video processing so:
- long resume parsing does not delay CCTV processing jobs
- we can scale HR workers separately later if needed
"""

from redis import Redis
from rq import Queue

from app.queue.rq import get_redis_conn

QUEUE_NAME = "hr"

# Resume parsing should typically complete quickly, but PDFs can still be large.
# Keep this conservative and configurable by adjusting RQ worker setup later.
DEFAULT_JOB_TIMEOUT_SEC = 60 * 30  # 30 minutes


def get_hr_redis_conn() -> Redis:
    return get_redis_conn()


def get_hr_queue() -> Queue:
    return Queue(
        name=QUEUE_NAME,
        connection=get_hr_redis_conn(),
        default_timeout=DEFAULT_JOB_TIMEOUT_SEC,
    )

