from rq import Worker, Queue
from rq.worker import SpawnWorker  # macOS-safe: uses os.spawn() instead of fork()
from app.queue.rq import QUEUE_NAME, get_redis_conn
import os
import sys

# macOS + RQ fork() + native libs (opencv/onnx) can crash without this.
if sys.platform == "darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

def main() -> None:
    # 1. Get your established Redis connection
    redis_conn = get_redis_conn()

    # 2. Pass the connection directly to the Queue
    queue = Queue(QUEUE_NAME, connection=redis_conn)

    # 3. Pass the connection and the queue to the Worker
    # Note: Worker expects a list of Queue objects
    WorkerClass = SpawnWorker if sys.platform == "darwin" else Worker
    worker = WorkerClass([queue], connection=redis_conn)

    # 4. Start the worker
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
