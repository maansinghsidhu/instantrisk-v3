"""
Health Check Router

Provides health status endpoint for ALB health checks and monitoring.
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis

from app.config import settings
from app.core.database import get_db

import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


class HealthStatus(BaseModel):
    """Health status response."""
    status: str
    timestamp: str
    version: str
    environment: str
    checks: Dict[str, Any]


class ComponentHealth(BaseModel):
    """Individual component health."""
    status: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None


async def check_database(db: AsyncSession) -> ComponentHealth:
    """Check database connectivity."""
    start = datetime.utcnow()
    try:
        await db.execute(text("SELECT 1"))
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        return ComponentHealth(status="healthy", latency_ms=latency)
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return ComponentHealth(status="unhealthy", error=str(e))


async def check_redis() -> ComponentHealth:
    """Check Redis connectivity."""
    start = datetime.utcnow()
    try:
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        return ComponentHealth(status="healthy", latency_ms=latency)
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        # Redis failure is degraded, not unhealthy
        return ComponentHealth(status="degraded", error=str(e))


async def check_pgvector() -> ComponentHealth:
    """Check pgvector extension availability."""
    start = datetime.utcnow()
    try:
        from app.services.rag_indexer import rag_indexer
        count = rag_indexer.get_collection_count()
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        return ComponentHealth(status="healthy", latency_ms=latency)
    except Exception as e:
        logger.warning(f"pgvector health check failed: {e}")
        return ComponentHealth(status="degraded", error=str(e))


async def check_s3() -> ComponentHealth:
    """Check S3 connectivity."""
    start = datetime.utcnow()
    try:
        import boto3
        s3 = boto3.client("s3", region_name=settings.S3_REGION)
        s3.head_bucket(Bucket=settings.S3_DOCUMENTS_BUCKET)
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        return ComponentHealth(status="healthy", latency_ms=latency)
    except Exception as e:
        logger.warning(f"S3 health check failed: {e}")
        return ComponentHealth(status="degraded", error=str(e))


@router.get(
    "/health",
    response_model=HealthStatus,
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is unhealthy"},
    },
)
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Comprehensive health check endpoint.

    Used by ALB for health monitoring.
    Returns 200 if core services (database) are healthy.
    Returns 503 if any critical component is unhealthy.
    """
    # Run all checks concurrently
    db_check, redis_check, pgvector_check, s3_check = await asyncio.gather(
        check_database(db),
        check_redis(),
        check_pgvector(),
        check_s3(),
        return_exceptions=True,
    )

    # Handle exceptions
    if isinstance(db_check, Exception):
        db_check = ComponentHealth(status="unhealthy", error=str(db_check))
    if isinstance(redis_check, Exception):
        redis_check = ComponentHealth(status="degraded", error=str(redis_check))
    if isinstance(pgvector_check, Exception):
        pgvector_check = ComponentHealth(status="degraded", error=str(pgvector_check))
    if isinstance(s3_check, Exception):
        s3_check = ComponentHealth(status="degraded", error=str(s3_check))

    checks = {
        "database": db_check.model_dump(),
        "redis": redis_check.model_dump(),
        "pgvector": pgvector_check.model_dump(),
        "s3": s3_check.model_dump(),
    }

    # Determine overall status
    # Unhealthy if database is down (critical)
    # Degraded if other services are down
    if db_check.status == "unhealthy":
        overall_status = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif any(c.status == "unhealthy" for c in [redis_check, pgvector_check, s3_check]):
        overall_status = "degraded"
        status_code = status.HTTP_200_OK  # Still return 200 for ALB
    elif any(c.status == "degraded" for c in [redis_check, pgvector_check, s3_check]):
        overall_status = "degraded"
        status_code = status.HTTP_200_OK
    else:
        overall_status = "healthy"
        status_code = status.HTTP_200_OK

    response = HealthStatus(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        version="2.0.0",
        environment=settings.ENVIRONMENT,
        checks=checks,
    )

    return JSONResponse(
        content=response.model_dump(),
        status_code=status_code,
    )


@router.get("/health/live")
async def liveness_check():
    """
    Simple liveness check.

    Returns 200 if the service process is running.
    Used for Kubernetes/ECS liveness probes.
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Readiness check.

    Returns 200 if the service is ready to accept traffic.
    Checks database connectivity.
    """
    db_check = await check_database(db)

    if db_check.status == "healthy":
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
        }
    else:
        return JSONResponse(
            content={
                "status": "not_ready",
                "error": db_check.error,
                "timestamp": datetime.utcnow().isoformat(),
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
