"""
Risk Monitoring Router

API endpoints for continuous risk monitoring and alerts.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.models.risk_alert import RiskMonitoringAlert
from app.services.hibp_monitor import hibp_monitor

router = APIRouter()


# Response schemas
class AlertResponse(BaseModel):
    """Risk monitoring alert."""
    id: int
    assessment_id: str
    alert_type: str
    severity: str
    message: str
    source: str
    detected_at: datetime
    acknowledged: bool


class MonitoringStatusResponse(BaseModel):
    """Monitoring status for assessment."""
    assessment_id: str
    total_alerts: int
    critical_alerts: int
    unacknowledged_alerts: int
    latest_alert: Optional[AlertResponse]
    monitoring_active: bool


@router.get(
    "/alerts",
    response_model=List[AlertResponse],
    summary="List all risk alerts"
)
async def list_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List risk monitoring alerts.

    Filters:
    - severity: low, medium, high, critical
    - acknowledged: true/false
    - limit: max results
    """

    query = select(RiskMonitoringAlert).order_by(
        RiskMonitoringAlert.detected_at.desc()
    )

    if severity:
        query = query.where(RiskMonitoringAlert.severity == severity)

    if acknowledged is not None:
        query = query.where(RiskMonitoringAlert.acknowledged == acknowledged)

    query = query.limit(limit)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return [
        AlertResponse(
            id=alert.id,
            assessment_id=str(alert.assessment_id),
            alert_type=alert.alert_type,
            severity=alert.severity,
            message=alert.message,
            source=alert.source,
            detected_at=alert.detected_at,
            acknowledged=alert.acknowledged
        )
        for alert in alerts
    ]


@router.get(
    "/status/{assessment_id}",
    response_model=MonitoringStatusResponse,
    summary="Get monitoring status"
)
async def get_monitoring_status(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get risk monitoring status for an assessment.

    Shows:
    - Total alerts
    - Critical alerts
    - Unacknowledged alerts
    - Latest alert
    """

    # Get alert statistics
    total = await db.execute(
        select(func.count()).select_from(RiskMonitoringAlert).where(
            RiskMonitoringAlert.assessment_id == assessment_id
        )
    )
    total_count = total.scalar()

    critical = await db.execute(
        select(func.count()).select_from(RiskMonitoringAlert).where(
            RiskMonitoringAlert.assessment_id == assessment_id,
            RiskMonitoringAlert.severity == 'critical'
        )
    )
    critical_count = critical.scalar()

    unacked = await db.execute(
        select(func.count()).select_from(RiskMonitoringAlert).where(
            RiskMonitoringAlert.assessment_id == assessment_id,
            RiskMonitoringAlert.acknowledged == False
        )
    )
    unacked_count = unacked.scalar()

    # Get latest alert
    latest_result = await db.execute(
        select(RiskMonitoringAlert).where(
            RiskMonitoringAlert.assessment_id == assessment_id
        ).order_by(RiskMonitoringAlert.detected_at.desc()).limit(1)
    )
    latest_alert = latest_result.scalar_one_or_none()

    return MonitoringStatusResponse(
        assessment_id=str(assessment_id),
        total_alerts=total_count,
        critical_alerts=critical_count,
        unacknowledged_alerts=unacked_count,
        latest_alert=AlertResponse(
            id=latest_alert.id,
            assessment_id=str(latest_alert.assessment_id),
            alert_type=latest_alert.alert_type,
            severity=latest_alert.severity,
            message=latest_alert.message,
            source=latest_alert.source,
            detected_at=latest_alert.detected_at,
            acknowledged=latest_alert.acknowledged
        ) if latest_alert else None,
        monitoring_active=True
    )


@router.post(
    "/check-breaches/{assessment_id}",
    summary="Check assessment for data breaches"
)
async def check_assessment_breaches(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check if assessment's insured company has data breaches.

    Uses Have I Been Pwned API (free, no key required).
    """

    assessment = await db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found"
        )

    # Run HIBP check
    result = await hibp_monitor.monitor_assessment(db, assessment)

    # If breaches found, create alert
    if result['status'] == 'breaches_found':
        alert = RiskMonitoringAlert(
            assessment_id=assessment.id,
            alert_type='breach_detected',
            severity=result['severity'],
            message=f"{result['breach_count']} data breaches detected for {result['domain']}",
            details={"breaches": result['breaches']},
            source='hibp',
            source_url='https://haveibeenpwned.com'
        )
        db.add(alert)
        await db.commit()

    return result


@router.post(
    "/acknowledge/{alert_id}",
    summary="Acknowledge alert"
)
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark alert as acknowledged by underwriter.
    """

    alert = await db.get(RiskMonitoringAlert, alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found"
        )

    alert.acknowledged = True
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.now(timezone.utc)

    await db.commit()

    return {"message": "Alert acknowledged", "alert_id": alert_id}
