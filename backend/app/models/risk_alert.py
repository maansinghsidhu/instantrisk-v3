"""
Risk Monitoring Alert Model

Stores real-time risk alerts from various monitoring sources.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.models.base import Base


class RiskMonitoringAlert(Base):
    """
    Risk monitoring alerts from continuous monitoring systems.

    Sources:
    - Data breaches (HIBP)
    - Regulatory violations (FCA, OSHA, EPA)
    - Financial distress (SEC filings, credit changes)
    - Cyber vulnerabilities (CVE, CISA)
    - Weather/climate events (NOAA, NASA)
    - News sentiment (adverse media)
    """
    __tablename__ = "risk_monitoring_alerts"

    id = Column(Integer, primary_key=True, index=True)

    # Associated assessment
    assessment_id = Column(
        PgUUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Alert classification
    alert_type = Column(String(50), nullable=False, index=True)
    # Types: credit_drop, breach_detected, regulatory_violation,
    #        cyber_vulnerability, weather_event, adverse_media

    severity = Column(String(20), nullable=False, index=True)
    # Levels: low, medium, high, critical

    # Alert content
    message = Column(Text, nullable=False)
    details = Column(JSONB, default=dict)

    # Source
    source = Column(String(100), nullable=False)
    # Sources: hibp, sec_edgar, fca, osha, epa, noaa, gdelt, etc.

    source_url = Column(Text, nullable=True)

    # Status
    acknowledged = Column(Boolean, default=False, index=True)
    acknowledged_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    assessment = relationship("Assessment", backref="monitoring_alerts")
