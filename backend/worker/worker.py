"""
Standalone Background Worker Process for Document Ingestion.
Polls Redis ingestion queue using BRPOP and invokes IngestionWorker.
Handles graceful shutdown on SIGINT / SIGTERM.
"""

import logging
import signal
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.services.queue_service import QueueServiceError, queue_service
from app.services.redis_service import redis_service
from worker.ingestion_worker import ingestion_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [WORKER] %(name)s: %(message)s",
)
logger = logging.getLogger("rag.worker")


class WorkerProcess:
    """
    Continuous worker daemon consuming ingestion jobs from Redis.
    """

    def __init__(self):
        self._running = True
        self._poll_timeout = settings.WORKER_POLL_TIMEOUT_SECONDS or 2

    def stop(self, signum=None, frame=None):
        logger.info("Shutdown signal received (%s). Gracefully stopping worker...", signum)
        self._running = False

    def run(self, handle_signals: bool = True):
        # Register OS signal handlers for graceful shutdown if running in main thread
        if handle_signals:
            try:
                signal.signal(signal.SIGINT, self.stop)
                signal.signal(signal.SIGTERM, self.stop)
            except (ValueError, AttributeError):
                pass

        logger.info("============================================================")
        logger.info("DOCUMENT INTELLIGENCE RAG — INGESTION WORKER STARTED")
        logger.info("Redis URL   : %s", settings.masked_redis_url)
        logger.info("Queue Name  : %s", queue_service.queue_name)
        logger.info("Max Retries : %d", settings.WORKER_MAX_RETRIES)
        logger.info("Poll Timeout: %ds", self._poll_timeout)
        logger.info("============================================================")

        # Confirm Redis connectivity on start
        health = redis_service.check_health()
        if health != "connected":
            logger.warning("Redis is currently reported as '%s'. Worker will wait for connections...", health)

        consecutive_errors = 0

        while self._running:
            try:
                # 1. Block on queue pop
                job_payload = queue_service.dequeue_ingestion_job(timeout=self._poll_timeout)
                if not job_payload:
                    consecutive_errors = 0
                    continue

                job_id = job_payload.get("job_id")
                if not job_id:
                    logger.warning("Received malformed job payload without job_id: %s", job_payload)
                    continue

                logger.info("Dequeued job: %s", job_id)
                consecutive_errors = 0

                # 2. Process job via IngestionWorker
                success = ingestion_worker.process_job(job_id=job_id)
                if success:
                    logger.info("Job %s processed successfully.", job_id)
                else:
                    logger.warning("Job %s did not complete successfully.", job_id)

            except QueueServiceError as queue_err:
                consecutive_errors += 1
                wait_sec = min(10, 2 ** min(consecutive_errors, 4))
                logger.error("Queue service error (#%d): %s. Backing off for %ds...", consecutive_errors, queue_err, wait_sec)
                time.sleep(wait_sec)
            except Exception as exc:
                logger.exception("Unexpected error in worker loop: %s", exc)
                time.sleep(1)

        logger.info("Worker process terminated cleanly.")
        redis_service.close()


def start_worker_thread() -> WorkerProcess:
    """Starts WorkerProcess in a background daemon thread."""
    import threading
    worker = WorkerProcess()
    thread = threading.Thread(
        target=worker.run,
        kwargs={"handle_signals": False},
        daemon=True,
        name="IngestionWorkerThread",
    )
    thread.start()
    return worker


def main():
    worker = WorkerProcess()
    worker.run()


if __name__ == "__main__":
    main()
