from rq import Connection, Queue, Worker

from app.queue.rq import QUEUE_NAME, get_redis_conn


def main() -> None:
    redis_conn = get_redis_conn()
    with Connection(redis_conn):
        worker = Worker([Queue(QUEUE_NAME)])
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
