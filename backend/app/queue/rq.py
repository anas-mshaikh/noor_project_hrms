from redis import Redis
from rq import Queue

from app.core.config import settings

QUEUE_NAME = "video_jobs"
DEFAULT_JOB_TIMEOUT_SEC = 60 * 60 * 24  # 24h (video processing can be long)


def get_redis_conn() -> Redis:
    return Redis.from_url(settings.redis_url)


def get_queue() -> Queue:
    return Queue(
        name=QUEUE_NAME,
        connection=get_redis_conn(),
        default_timeout=DEFAULT_JOB_TIMEOUT_SEC,
    )
