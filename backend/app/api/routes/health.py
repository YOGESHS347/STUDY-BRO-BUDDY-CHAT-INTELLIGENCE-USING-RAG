from typing import Dict
from fastapi import APIRouter
from app.core.database import check_database_health
from app.services.redis_service import redis_service
from app.services.storage_service import storage_service

router = APIRouter()


@router.get("/health", response_model=Dict[str, str])
def health_check() -> Dict[str, str]:
    """
    Health check endpoint returning system status, database connectivity,
    storage connectivity, and Redis connectivity.
    Safe check: no credentials, secret keys, or sensitive URLs are ever exposed.
    """
    db_status = check_database_health()
    storage_status = storage_service.check_health()
    redis_status = redis_service.check_health()
    return {
        "status": "ok",
        "database": db_status,
        "storage": storage_status,
        "redis": redis_status,
    }
