import time
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from redis import Redis
from app.core.database import get_db
from app.core.redis import get_redis
from loguru import logger

router = APIRouter()

@router.get(
    "/health", 
    status_code=status.HTTP_200_OK,
    summary="Complete System Dependency Check"
)
def check_health(
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis)
):
    """
    Validates operational states of critical underlying systems:
    - Postgres DB transactional liveness and query latency.
    - Redis connectivity and ping latencies.
    """
    health_payload = {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {}
    }
    
    # 1. Test PostgreSQL liveness
    try:
        db_start = time.perf_counter()
        db.execute(text("SELECT 1"))
        db_latency = (time.perf_counter() - db_start) * 1000
        health_payload["services"]["database"] = {
            "status": "online",
            "latency_ms": round(db_latency, 2)
        }
    except Exception as e:
        logger.error(f"Healthcheck failed on database connect: {e}")
        health_payload["status"] = "unhealthy"
        health_payload["services"]["database"] = {
            "status": "offline",
            "error": str(e)
        }
        
    # 2. Test Redis connection liveness
    try:
        redis_start = time.perf_counter()
        redis_client.ping()
        redis_latency = (time.perf_counter() - redis_start) * 1000
        health_payload["services"]["redis"] = {
            "status": "online",
            "latency_ms": round(redis_latency, 2),
            "mode": "mock" if hasattr(redis_client, "is_mock") and redis_client.is_mock else "live"
        }
    except Exception as e:
        logger.error(f"Healthcheck failed on Redis connection: {e}")
        health_payload["status"] = "unhealthy"
        health_payload["services"]["redis"] = {
            "status": "offline",
            "error": str(e)
        }
        
    if health_payload["status"] == "unhealthy":
        logger.warning(f"System health check failed: {health_payload}")
        
    return health_payload
