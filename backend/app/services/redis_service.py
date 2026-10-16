"""
Clean Redis connection service abstraction.
Manages connection pooling, client lifecycle, timeouts, and health checks.
Strictly decoupled: zero application business logic inside this layer.
"""

import logging
from typing import Optional
import redis
from redis.connection import ConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisService:
    """
    Manages Redis client connections and health status.
    Uses connection pooling and graceful error handling.
    """

    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None

    def _get_pool(self) -> ConnectionPool:
        if self._pool is None:
            redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
            logger.info("Initializing Redis connection pool for %s", settings.masked_redis_url)
            self._pool = ConnectionPool.from_url(
                redis_url,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                decode_responses=False,
            )
        return self._pool

    def get_client(self) -> redis.Redis:
        """
        Returns a thread-safe Redis client instance backed by the shared connection pool.
        """
        if self._client is None:
            pool = self._get_pool()
            self._client = redis.Redis(connection_pool=pool)
        return self._client

    def check_health(self) -> str:
        """
        Executes an isolated PING health check against Redis.
        Returns:
            - 'connected': Redis is reachable and responds to PING.
            - 'disconnected': Redis is unconfigured, unreachable, or timed out.
        Safe check: Never raises unhandled exceptions and never leaks credentials.
        """
        if not settings.REDIS_URL:
            return "disconnected"

        try:
            client = self.get_client()
            # Perform a fast PING with tight timeout
            if client.ping():
                return "connected"
            return "disconnected"
        except (redis.ConnectionError, redis.TimeoutError) as exc:
            logger.warning("Redis health check failed (unreachable): %s", type(exc).__name__)
            return "disconnected"
        except Exception as exc:
            logger.error("Redis health check unexpected error: %s", type(exc).__name__)
            return "disconnected"

    def close(self) -> None:
        """Gracefully closes all connections in the pool."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        if self._pool:
            try:
                self._pool.disconnect()
            except Exception:
                pass
            self._pool = None
        logger.info("Redis connection pool closed.")


redis_service = RedisService()
