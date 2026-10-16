"""
Queue abstraction for asynchronous job dispatch and worker coordination.
Encapsulates Redis queue operations with strictly minimal payloads:
Only identifiers and coordination metadata are stored in Redis.
PostgreSQL remains the sole authoritative source of truth.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID

import redis

from app.core.config import settings
from app.services.redis_service import redis_service

logger = logging.getLogger(__name__)


class QueueServiceError(RuntimeError):
    """Raised when an operation against the job queue fails."""
    pass


class QueueService:
    """
    Manages document ingestion job dispatch and retrieval over Redis.
    Guarantees minimal payload: only {"job_id": "...", "enqueued_at": "..."}.
    """

    def __init__(self):
        self.queue_name = settings.REDIS_QUEUE_NAME or "rag_ingestion_queue"

    def enqueue_ingestion_job(self, job_id: Union[UUID, str]) -> bool:
        """
        Enqueues an ingestion job using strictly its job_id.
        Raises QueueServiceError if Redis is unavailable or rejects the push.
        """
        clean_job_id = str(job_id).strip()
        if not clean_job_id:
            raise ValueError("job_id must be a valid non-empty UUID or string.")

        payload = {
            "job_id": clean_job_id,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }
        serialized = json.dumps(payload)

        try:
            client = redis_service.get_client()
            # Push to the head of the queue (LPUSH), worker pops from tail (BRPOP)
            client.lpush(self.queue_name, serialized)
            logger.info("Enqueued ingestion job to Redis: job_id=%s queue=%s", clean_job_id, self.queue_name)
            return True
        except (redis.ConnectionError, redis.TimeoutError) as net_err:
            logger.error("Failed to enqueue job %s: Redis connection error (%s)", clean_job_id, net_err)
            raise QueueServiceError(f"Redis queue unreachable: {type(net_err).__name__}") from net_err
        except Exception as exc:
            logger.exception("Failed to enqueue job %s to Redis: %s", clean_job_id, exc)
            raise QueueServiceError(f"Failed to dispatch job to queue: {type(exc).__name__}") from exc

    def dequeue_ingestion_job(self, timeout: int = 2) -> Optional[Dict[str, Any]]:
        """
        Pops the next available job from the queue using blocking pop (BRPOP).
        Returns parsed payload dict, or None if timeout expired with no job.
        """
        try:
            client = redis_service.get_client()
            # brpop returns a tuple of (queue_name, item_bytes) or None
            result = client.brpop(self.queue_name, timeout=timeout)
            if not result:
                return None

            _, item_bytes = result
            if isinstance(item_bytes, bytes):
                raw_text = item_bytes.decode("utf-8")
            else:
                raw_text = str(item_bytes)

            payload = json.loads(raw_text)
            return payload
        except (redis.ConnectionError, redis.TimeoutError) as net_err:
            logger.warning("Redis dequeue connection issue: %s", net_err)
            raise QueueServiceError(f"Redis queue dequeue error: {type(net_err).__name__}") from net_err
        except json.JSONDecodeError as json_err:
            logger.error("Invalid JSON payload encountered in queue: %s", json_err)
            return None
        except Exception as exc:
            logger.exception("Unexpected error during job dequeue: %s", exc)
            raise QueueServiceError(f"Dequeue error: {type(exc).__name__}") from exc

    def get_queue_length(self) -> int:
        """Returns the number of pending jobs in the queue."""
        try:
            client = redis_service.get_client()
            return int(client.llen(self.queue_name))
        except Exception as exc:
            logger.warning("Failed to check queue length: %s", exc)
            return 0

    def clear_queue(self) -> None:
        """Flushes all items from the ingestion queue. For testing/maintenance."""
        try:
            client = redis_service.get_client()
            client.delete(self.queue_name)
            logger.info("Cleared queue %s", self.queue_name)
        except Exception as exc:
            logger.warning("Failed to clear queue %s: %s", self.queue_name, exc)


queue_service = QueueService()
