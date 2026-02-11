"""
Claims Router - ClaimSense Data API

Endpoints for syncing and querying claims data from Parametriks ClaimSense.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.claimsense_service import ClaimSenseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/claims", tags=["Claims"])


@router.post("/sync")
async def sync_claims(db: AsyncSession = Depends(get_db)):
    """Trigger sync of claims data from ClaimSense API."""
    service = ClaimSenseService(db)
    result = await service.sync_claims_data()
    return result


@router.get("/")
async def list_claims(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    cause: Optional[str] = Query(None),
    policyholder: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Query local claims with optional filters."""
    service = ClaimSenseService(db)
    claims = await service.get_claims(
        limit=limit,
        offset=offset,
        cause=cause,
        policyholder=policyholder,
    )
    return {"claims": claims, "count": len(claims)}


@router.get("/stats")
async def claims_stats(db: AsyncSession = Depends(get_db)):
    """Get claims statistics (total, average, highest, etc.)."""
    service = ClaimSenseService(db)
    stats = await service.get_stats()
    return stats
