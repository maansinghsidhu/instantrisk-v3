"""
Global Event Model

Stores real-time global events from GDELT, USGS, NOAA, NASA FIRMS, and CISA
that may affect the portfolio of insured assessments.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class GlobalEvent(Base):
    """
    Global event from external monitoring sources.

    Event types:
    - earthquake      (USGS)
    - hurricane       (NOAA)
    - wildfire        (NASA FIRMS)
    - cyber_alert     (CISA)
    - geopolitical    (GDELT)
    - flood           (NOAA)
    - tornado         (NOAA)
    - tsunami         (USGS)

    Severity levels: low, medium, high, critical
    """
    __tablename__ = "global_events"

    id = Column(Integer, primary_key=True, index=True)

    # Classification
    event_type = Column(String(50), nullable=False, index=True)
    source = Column(String(50), nullable=False, index=True)
    # Sources: gdelt, usgs, noaa, nasa_firms, cisa

    # Content
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="low", index=True)
    # Levels: low, medium, high, critical

    # Location
    location = Column(String(255), nullable=True, index=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    affected_region = Column(String(255), nullable=True)

    # Raw source data
    raw_data = Column(JSONB, default=dict)

    # Timing
    event_time = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Processing state
    is_processed = Column(Boolean, default=False, nullable=False)
    affected_assessment_count = Column(Integer, default=0)
