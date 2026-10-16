import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import check_database_health
from app.api.routes import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("ragllm.backend")


import os
import sys
import threading
from app.services.redis_service import redis_service

_embedded_redis_server = None
_background_worker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for application startup and shutdown events."""
    global _embedded_redis_server, _background_worker

    logger.info("Starting Document Intelligence RAG Backend...")
    logger.info("Environment: %s", settings.ENVIRONMENT)
    logger.info("CORS Origins configured: %s", settings.CORS_ORIGINS)

    # Check database connectivity safely on startup
    db_status = check_database_health()
    logger.info("Database connectivity status at startup: %s", db_status)

    # Check Redis connectivity; automatically spin up embedded local Redis server if not reachable
    if redis_service.check_health() != "connected":
        try:
            import fakeredis
            logger.info("External Redis not detected. Starting embedded local Redis server on 127.0.0.1:6379...")
            _embedded_redis_server = fakeredis.TcpFakeServer(("127.0.0.1", 6379))
            t = threading.Thread(
                target=_embedded_redis_server.serve_forever,
                daemon=True,
                name="EmbeddedRedisServer",
            )
            t.start()
            logger.info("Embedded local Redis server started on 127.0.0.1:6379.")
        except Exception as exc:
            logger.warning("Could not start embedded local Redis server (port may be in use): %s", exc)

    # Automatically start background ingestion worker daemon thread in server mode (not in pytest)
    if "pytest" not in sys.modules and os.environ.get("PYTEST_CURRENT_TEST") is None:
        try:
            from worker.worker import start_worker_thread
            _background_worker = start_worker_thread()
            logger.info("Background document ingestion worker thread initialized.")
        except Exception as exc:
            logger.warning("Could not initialize background ingestion worker thread: %s", exc)

    yield

    logger.info("Shutting down Document Intelligence RAG Backend...")
    if _background_worker:
        _background_worker.stop()
    if _embedded_redis_server:
        try:
            _embedded_redis_server.shutdown()
            _embedded_redis_server.server_close()
            logger.info("Embedded local Redis server shut down.")
        except Exception as exc:
            logger.warning("Error shutting down embedded Redis server: %s", exc)


def create_application() -> FastAPI:
    """FastAPI application factory."""
    application = FastAPI(
        title="Document Intelligence RAG API",
        description="FastAPI Backend for Document Intelligence RAG Engine with Supabase & Qdrant.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_private_network=True,
    )

    # Include versioned API router under /api/v1
    application.include_router(api_router, prefix="/api/v1")

    return application


app = create_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=(settings.ENVIRONMENT == "development"),
    )
