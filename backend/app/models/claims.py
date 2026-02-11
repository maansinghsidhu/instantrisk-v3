"""
ClaimSense Claims Data Models

Stores claims data fetched from Parametriks ClaimSense API.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON

from app.core.database import Base


class ClaimRecord(Base):
    """Individual claim record from ClaimSense."""

    __tablename__ = "claim_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(String(255), unique=True, index=True, nullable=False)
    policyholder = Column(String(500), default="")
    cause = Column(String(500), default="")
    amount = Column(Float, default=0.0)
    date_of_loss = Column(String(100), default="")
    status = Column(String(100), default="")
    line_of_business = Column(String(255), default="")
    raw_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ClaimsSyncLog(Base):
    """Tracks ClaimSense data sync history."""

    __tablename__ = "claims_sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    records_fetched = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_errors = Column(Integer, default=0)
    source_url = Column(String(500), default="")
    synced_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
