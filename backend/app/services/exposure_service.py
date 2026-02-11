"""
InstantRisk V3 - Exposure Monitoring Service

Provides real-time portfolio exposure monitoring for Lloyd's syndicates.
Addresses exposure accumulation, capacity management, and PML calculations.

Key Features:
- Exposure aggregation by zone, peril, and class of business
- Catastrophe event accumulation monitoring
- Capacity limit alerts
- PML (Probable Maximum Loss) calculations
- Historical exposure trend analysis
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lloyds import (
    ExposureSnapshot,
    ExposureAggregate,
    EventAccumulation,
    SyndicateLine,
    SubscriptionPlacement,
)
from app.models.syndicate import Syndicate


class AlertSeverity(Enum):
    """Severity levels for capacity alerts."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CapacityAlert:
    """Represents a capacity limit alert."""
    alert_type: str
    severity: AlertSeverity
    dimension: str  # zone, peril, class, total
    key: str
    current_exposure: Decimal
    limit: Decimal
    utilization_pct: float
    message: str


@dataclass
class PMLResult:
    """Probable Maximum Loss calculation result."""
    return_period: int
    gross_pml: Decimal
    net_pml: Decimal
    by_zone: Dict[str, Decimal]
    by_peril: Dict[str, Decimal]
    confidence_level: float
    calculation_date: datetime


class ExposureMonitoringService:
    """
    Service for real-time portfolio exposure monitoring.

    Provides exposure calculations, capacity monitoring, and
    PML analysis for Lloyd's syndicates.
    """

    # Default capacity utilization thresholds
    WARNING_THRESHOLD = 0.75  # 75% utilization
    CRITICAL_THRESHOLD = 0.90  # 90% utilization

    # Standard return periods for PML calculations
    RETURN_PERIODS = [10, 25, 50, 100, 250, 500, 1000]

    # Geographic zone definitions
    GEOGRAPHIC_ZONES = {
        'NA': ['US', 'CA', 'MX'],
        'EU': ['GB', 'DE', 'FR', 'IT', 'ES', 'NL', 'BE', 'CH', 'AT', 'IE'],
        'APAC': ['JP', 'AU', 'NZ', 'SG', 'HK', 'CN', 'KR', 'TW', 'IN'],
        'LATAM': ['BR', 'AR', 'CL', 'CO', 'PE', 'MX'],
        'MEA': ['AE', 'SA', 'ZA', 'EG', 'IL'],
        'ROW': [],  # Rest of World
    }

    # Peril categories
    PERIL_CATEGORIES = [
        'windstorm',
        'earthquake',
        'flood',
        'wildfire',
        'cyber',
        'terrorism',
        'marine',
        'aviation',
        'casualty',
        'other',
    ]

    def __init__(self, db: AsyncSession):
        """
        Initialize the exposure monitoring service.

        Args:
            db: Async database session.
        """
        self.db = db

    async def calculate_exposure_by_zone(self, syndicate_id: int) -> Dict[str, Decimal]:
        """
        Calculate current exposure aggregated by geographic zone.

        Args:
            syndicate_id: ID of the syndicate.

        Returns:
            Dictionary mapping zone codes to exposure amounts.
        """
        # Get the most recent snapshot timestamp for this syndicate
        latest_time = await self._get_latest_snapshot_time(syndicate_id)

        if not latest_time:
            # No snapshots, calculate from live data
            return await self._calculate_live_exposure_by_zone(syndicate_id)

        # Query aggregated exposure by zone from snapshots
        result = await self.db.execute(
            select(
                ExposureSnapshot.geographic_zone,
                func.sum(ExposureSnapshot.net_exposure).label('total_exposure')
            )
            .where(
                and_(
                    ExposureSnapshot.syndicate_id == syndicate_id,
                    ExposureSnapshot.timestamp == latest_time
                )
            )
            .group_by(ExposureSnapshot.geographic_zone)
        )

        rows = result.all()

        # Build result dictionary, ensuring all zones are represented
        exposure_by_zone = {zone: Decimal('0') for zone in self.GEOGRAPHIC_ZONES.keys()}

        for row in rows:
            zone = row.geographic_zone or 'ROW'
            exposure_by_zone[zone] = Decimal(str(row.total_exposure or 0))

        return exposure_by_zone

    async def calculate_exposure_by_peril(self, syndicate_id: int) -> Dict[str, Decimal]:
        """
        Calculate current exposure aggregated by peril type.

        Args:
            syndicate_id: ID of the syndicate.

        Returns:
            Dictionary mapping peril types to exposure amounts.
        """
        latest_time = await self._get_latest_snapshot_time(syndicate_id)

        if not latest_time:
            return await self._calculate_live_exposure_by_peril(syndicate_id)

        result = await self.db.execute(
            select(
                ExposureSnapshot.peril,
                func.sum(ExposureSnapshot.net_exposure).label('total_exposure')
            )
            .where(
                and_(
                    ExposureSnapshot.syndicate_id == syndicate_id,
                    ExposureSnapshot.timestamp == latest_time
                )
            )
            .group_by(ExposureSnapshot.peril)
        )

        rows = result.all()

        # Build result dictionary
        exposure_by_peril = {peril: Decimal('0') for peril in self.PERIL_CATEGORIES}

        for row in rows:
            peril = row.peril or 'other'
            if peril in exposure_by_peril:
                exposure_by_peril[peril] = Decimal(str(row.total_exposure or 0))
            else:
                exposure_by_peril['other'] += Decimal(str(row.total_exposure or 0))

        return exposure_by_peril

    async def calculate_exposure_by_class(self, syndicate_id: int) -> Dict[str, Decimal]:
        """
        Calculate current exposure aggregated by class of business.

        Args:
            syndicate_id: ID of the syndicate.

        Returns:
            Dictionary mapping class codes to exposure amounts.
        """
        latest_time = await self._get_latest_snapshot_time(syndicate_id)

        if not latest_time:
            return await self._calculate_live_exposure_by_class(syndicate_id)

        result = await self.db.execute(
            select(
                ExposureSnapshot.class_of_business,
                func.sum(ExposureSnapshot.net_exposure).label('total_exposure')
            )
            .where(
                and_(
                    ExposureSnapshot.syndicate_id == syndicate_id,
                    ExposureSnapshot.timestamp == latest_time
                )
            )
            .group_by(ExposureSnapshot.class_of_business)
        )

        rows = result.all()

        exposure_by_class = {}
        for row in rows:
            class_code = row.class_of_business or 'unclassified'
            exposure_by_class[class_code] = Decimal(str(row.total_exposure or 0))

        return exposure_by_class

    async def run_event_accumulation(
        self,
        syndicate_id: int,
        event_definition: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run catastrophe event accumulation analysis.

        Calculates total exposure for a defined event scenario based on
        geographic footprint and peril type.

        Args:
            syndicate_id: ID of the syndicate.
            event_definition: Dictionary defining the event:
                - event_id: Unique identifier (e.g., 'HURRICANE_2026_01')
                - event_name: Human-readable name
                - event_type: Type of event (hurricane, earthquake, etc.)
                - region: Geographic region affected
                - countries: List of affected country codes
                - perils: List of perils triggered
                - damage_factor: Optional loss factor (0.0 to 1.0)

        Returns:
            Dictionary with accumulation results.
        """
        event_id = event_definition.get('event_id', f"EVENT_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        event_name = event_definition.get('event_name', 'Unnamed Event')
        event_type = event_definition.get('event_type', 'catastrophe')
        region = event_definition.get('region')
        countries = event_definition.get('countries', [])
        perils = event_definition.get('perils', [])
        damage_factor = Decimal(str(event_definition.get('damage_factor', 1.0)))

        # Build query conditions
        conditions = [ExposureSnapshot.syndicate_id == syndicate_id]

        # Get latest snapshot time
        latest_time = await self._get_latest_snapshot_time(syndicate_id)
        if latest_time:
            conditions.append(ExposureSnapshot.timestamp == latest_time)

        # Filter by countries if specified
        if countries:
            conditions.append(ExposureSnapshot.country.in_(countries))

        # Filter by perils if specified
        if perils:
            conditions.append(ExposureSnapshot.peril.in_(perils))

        # Filter by region if specified
        if region and not countries:
            # Get countries for the region
            region_countries = self.GEOGRAPHIC_ZONES.get(region, [])
            if region_countries:
                conditions.append(ExposureSnapshot.country.in_(region_countries))

        # Query exposure
        result = await self.db.execute(
            select(
                func.sum(ExposureSnapshot.gross_exposure).label('gross_total'),
                func.sum(ExposureSnapshot.net_exposure).label('net_total'),
                func.sum(ExposureSnapshot.reinsurance_recovery).label('ri_recovery'),
                func.count(ExposureSnapshot.id).label('policy_count')
            )
            .where(and_(*conditions))
        )

        row = result.one()

        gross_exposure = Decimal(str(row.gross_total or 0)) * damage_factor
        net_exposure = Decimal(str(row.net_total or 0)) * damage_factor
        ri_recovery = Decimal(str(row.ri_recovery or 0)) * damage_factor
        policies_affected = row.policy_count or 0

        # Save or update accumulation record
        existing = await self.db.execute(
            select(EventAccumulation)
            .where(
                and_(
                    EventAccumulation.event_id == event_id,
                    EventAccumulation.syndicate_id == syndicate_id
                )
            )
        )
        accumulation = existing.scalar_one_or_none()

        if accumulation:
            accumulation.gross_exposure = gross_exposure
            accumulation.net_exposure = net_exposure
            accumulation.policies_affected = policies_affected
            accumulation.last_calculated = datetime.now(timezone.utc)
        else:
            accumulation = EventAccumulation(
                event_id=event_id,
                event_name=event_name,
                event_type=event_type,
                region=region,
                syndicate_id=syndicate_id,
                gross_exposure=gross_exposure,
                net_exposure=net_exposure,
                policies_affected=policies_affected,
                last_calculated=datetime.now(timezone.utc),
                calculation_method='snapshot_aggregation',
            )
            self.db.add(accumulation)

        await self.db.flush()

        return {
            'event_id': event_id,
            'event_name': event_name,
            'event_type': event_type,
            'region': region,
            'gross_exposure': float(gross_exposure),
            'net_exposure': float(net_exposure),
            'reinsurance_recovery': float(ri_recovery),
            'policies_affected': policies_affected,
            'damage_factor': float(damage_factor),
            'calculation_timestamp': datetime.now(timezone.utc).isoformat(),
        }

    async def check_capacity_limits(self, syndicate_id: int) -> List[CapacityAlert]:
        """
        Check capacity limits and generate alerts.

        Compares current exposure against defined limits for zones,
        perils, classes, and total capacity.

        Args:
            syndicate_id: ID of the syndicate.

        Returns:
            List of CapacityAlert objects for any breaches or warnings.
        """
        alerts: List[CapacityAlert] = []

        # Get syndicate to check total capacity
        result = await self.db.execute(
            select(Syndicate).where(Syndicate.id == syndicate_id)
        )
        syndicate = result.scalar_one_or_none()

        if not syndicate:
            return alerts

        # Check total capacity
        total_exposure = await self._get_total_exposure(syndicate_id)
        if syndicate.capacity:
            capacity = Decimal(str(syndicate.capacity))
            utilization = float(total_exposure / capacity) if capacity > 0 else 0

            if utilization >= self.CRITICAL_THRESHOLD:
                alerts.append(CapacityAlert(
                    alert_type='capacity_breach',
                    severity=AlertSeverity.CRITICAL,
                    dimension='total',
                    key='total_capacity',
                    current_exposure=total_exposure,
                    limit=capacity,
                    utilization_pct=utilization * 100,
                    message=f"CRITICAL: Total capacity at {utilization:.1%} - immediate action required"
                ))
            elif utilization >= self.WARNING_THRESHOLD:
                alerts.append(CapacityAlert(
                    alert_type='capacity_warning',
                    severity=AlertSeverity.WARNING,
                    dimension='total',
                    key='total_capacity',
                    current_exposure=total_exposure,
                    limit=capacity,
                    utilization_pct=utilization * 100,
                    message=f"WARNING: Total capacity at {utilization:.1%}"
                ))

        # Check zone limits from aggregates
        zone_alerts = await self._check_aggregate_limits(syndicate_id, 'zone')
        alerts.extend(zone_alerts)

        # Check peril limits from aggregates
        peril_alerts = await self._check_aggregate_limits(syndicate_id, 'peril')
        alerts.extend(peril_alerts)

        # Check class limits from aggregates
        class_alerts = await self._check_aggregate_limits(syndicate_id, 'class')
        alerts.extend(class_alerts)

        # Sort alerts by severity (critical first)
        severity_order = {AlertSeverity.CRITICAL: 0, AlertSeverity.WARNING: 1, AlertSeverity.INFO: 2}
        alerts.sort(key=lambda a: severity_order.get(a.severity, 3))

        return alerts

    async def calculate_pml(
        self,
        syndicate_id: int,
        return_period: int
    ) -> Dict[str, Any]:
        """
        Calculate Probable Maximum Loss for a given return period.

        Uses stored PML estimates from snapshots and applies standard
        actuarial techniques for estimation.

        Args:
            syndicate_id: ID of the syndicate.
            return_period: Return period in years (e.g., 100, 250).

        Returns:
            Dictionary with PML calculation results.
        """
        latest_time = await self._get_latest_snapshot_time(syndicate_id)

        if not latest_time:
            return {
                'return_period': return_period,
                'gross_pml': 0,
                'net_pml': 0,
                'by_zone': {},
                'by_peril': {},
                'confidence_level': 0,
                'calculation_date': datetime.now(timezone.utc).isoformat(),
                'error': 'No exposure data available'
            }

        # Determine which PML column to use
        pml_column = ExposureSnapshot.pml_100yr if return_period <= 100 else ExposureSnapshot.pml_250yr

        # Get total PML by zone
        result = await self.db.execute(
            select(
                ExposureSnapshot.geographic_zone,
                func.sum(pml_column).label('zone_pml'),
                func.sum(ExposureSnapshot.gross_exposure).label('gross_exposure'),
                func.sum(ExposureSnapshot.net_exposure).label('net_exposure')
            )
            .where(
                and_(
                    ExposureSnapshot.syndicate_id == syndicate_id,
                    ExposureSnapshot.timestamp == latest_time
                )
            )
            .group_by(ExposureSnapshot.geographic_zone)
        )

        zone_rows = result.all()

        # Get total PML by peril
        result = await self.db.execute(
            select(
                ExposureSnapshot.peril,
                func.sum(pml_column).label('peril_pml')
            )
            .where(
                and_(
                    ExposureSnapshot.syndicate_id == syndicate_id,
                    ExposureSnapshot.timestamp == latest_time
                )
            )
            .group_by(ExposureSnapshot.peril)
        )

        peril_rows = result.all()

        # Calculate totals and build response
        gross_pml = Decimal('0')
        net_pml = Decimal('0')
        by_zone = {}
        by_peril = {}

        for row in zone_rows:
            zone = row.geographic_zone or 'ROW'
            zone_pml_val = Decimal(str(row.zone_pml or 0))
            by_zone[zone] = float(zone_pml_val)

            # Estimate net PML based on gross/net exposure ratio
            gross = Decimal(str(row.gross_exposure or 0))
            net = Decimal(str(row.net_exposure or 0))
            ratio = (net / gross) if gross > 0 else Decimal('1')

            gross_pml += zone_pml_val
            net_pml += zone_pml_val * ratio

        for row in peril_rows:
            peril = row.peril or 'other'
            by_peril[peril] = float(row.peril_pml or 0)

        # Apply return period scaling if needed
        # For simplicity, we use linear interpolation between 100yr and 250yr
        if return_period != 100 and return_period != 250:
            scale_factor = self._calculate_return_period_factor(return_period)
            gross_pml = gross_pml * Decimal(str(scale_factor))
            net_pml = net_pml * Decimal(str(scale_factor))
            by_zone = {k: v * scale_factor for k, v in by_zone.items()}
            by_peril = {k: v * scale_factor for k, v in by_peril.items()}

        # Confidence level based on data quality
        confidence_level = 1.0 / return_period  # Simplified - 1% for 100yr

        return {
            'return_period': return_period,
            'gross_pml': float(gross_pml),
            'net_pml': float(net_pml),
            'by_zone': by_zone,
            'by_peril': by_peril,
            'confidence_level': confidence_level,
            'calculation_date': datetime.now(timezone.utc).isoformat(),
        }

    async def record_snapshot(self, syndicate_id: int) -> None:
        """
        Save current exposure state as a snapshot.

        Creates a point-in-time record of exposure across all dimensions
        for historical tracking and trend analysis.

        Args:
            syndicate_id: ID of the syndicate.
        """
        now = datetime.now(timezone.utc)

        # Get current exposure data from live placements
        exposure_data = await self._gather_live_exposure_data(syndicate_id)

        # Create snapshot records for each dimension combination
        for data in exposure_data:
            snapshot = ExposureSnapshot(
                timestamp=now,
                syndicate_id=syndicate_id,
                class_of_business=data.get('class_of_business'),
                geographic_zone=data.get('geographic_zone'),
                peril=data.get('peril'),
                country=data.get('country'),
                gross_exposure=Decimal(str(data.get('gross_exposure', 0))),
                net_exposure=Decimal(str(data.get('net_exposure', 0))),
                reinsurance_recovery=Decimal(str(data.get('reinsurance_recovery', 0))),
                pml_100yr=Decimal(str(data.get('pml_100yr', 0))),
                pml_250yr=Decimal(str(data.get('pml_250yr', 0))),
                policy_count=data.get('policy_count', 0),
            )
            self.db.add(snapshot)

        await self.db.flush()

    async def get_exposure_trend(
        self,
        syndicate_id: int,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get historical exposure trend data.

        Retrieves daily exposure totals for trend analysis and
        visualization.

        Args:
            syndicate_id: ID of the syndicate.
            days: Number of days of history (default 30).

        Returns:
            List of daily exposure summaries.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Query daily aggregated exposure
        result = await self.db.execute(
            select(
                func.date_trunc('day', ExposureSnapshot.timestamp).label('date'),
                func.sum(ExposureSnapshot.gross_exposure).label('gross_exposure'),
                func.sum(ExposureSnapshot.net_exposure).label('net_exposure'),
                func.sum(ExposureSnapshot.policy_count).label('policy_count')
            )
            .where(
                and_(
                    ExposureSnapshot.syndicate_id == syndicate_id,
                    ExposureSnapshot.timestamp >= cutoff_date
                )
            )
            .group_by(func.date_trunc('day', ExposureSnapshot.timestamp))
            .order_by(func.date_trunc('day', ExposureSnapshot.timestamp))
        )

        rows = result.all()

        trend_data = []
        for row in rows:
            trend_data.append({
                'date': row.date.isoformat() if row.date else None,
                'gross_exposure': float(row.gross_exposure or 0),
                'net_exposure': float(row.net_exposure or 0),
                'policy_count': row.policy_count or 0,
            })

        # Calculate daily change percentages
        for i in range(1, len(trend_data)):
            prev_net = trend_data[i - 1]['net_exposure']
            curr_net = trend_data[i]['net_exposure']
            if prev_net > 0:
                trend_data[i]['change_pct'] = ((curr_net - prev_net) / prev_net) * 100
            else:
                trend_data[i]['change_pct'] = 0

        if trend_data:
            trend_data[0]['change_pct'] = 0

        return trend_data

    async def update_aggregates(self, syndicate_id: int) -> None:
        """
        Update pre-aggregated exposure data for dashboard performance.

        Refreshes the ExposureAggregate table with current totals and
        calculates trend metrics.

        Args:
            syndicate_id: ID of the syndicate.
        """
        now = datetime.now(timezone.utc)

        # Calculate zone aggregates
        zone_exposure = await self.calculate_exposure_by_zone(syndicate_id)
        for zone, exposure in zone_exposure.items():
            await self._upsert_aggregate(
                syndicate_id=syndicate_id,
                aggregation_type='zone',
                aggregation_key=zone,
                current_exposure=exposure,
                updated_at=now
            )

        # Calculate peril aggregates
        peril_exposure = await self.calculate_exposure_by_peril(syndicate_id)
        for peril, exposure in peril_exposure.items():
            await self._upsert_aggregate(
                syndicate_id=syndicate_id,
                aggregation_type='peril',
                aggregation_key=peril,
                current_exposure=exposure,
                updated_at=now
            )

        # Calculate class aggregates
        class_exposure = await self.calculate_exposure_by_class(syndicate_id)
        for class_code, exposure in class_exposure.items():
            await self._upsert_aggregate(
                syndicate_id=syndicate_id,
                aggregation_type='class',
                aggregation_key=class_code,
                current_exposure=exposure,
                updated_at=now
            )

        # Calculate total aggregate
        total_exposure = sum(zone_exposure.values())
        await self._upsert_aggregate(
            syndicate_id=syndicate_id,
            aggregation_type='total',
            aggregation_key='all',
            current_exposure=total_exposure,
            updated_at=now
        )

        await self.db.flush()

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    async def _get_latest_snapshot_time(self, syndicate_id: int) -> Optional[datetime]:
        """Get the timestamp of the most recent snapshot for a syndicate."""
        result = await self.db.execute(
            select(func.max(ExposureSnapshot.timestamp))
            .where(ExposureSnapshot.syndicate_id == syndicate_id)
        )
        return result.scalar()

    async def _get_total_exposure(self, syndicate_id: int) -> Decimal:
        """Get total net exposure for a syndicate."""
        latest_time = await self._get_latest_snapshot_time(syndicate_id)

        if not latest_time:
            return Decimal('0')

        result = await self.db.execute(
            select(func.sum(ExposureSnapshot.net_exposure))
            .where(
                and_(
                    ExposureSnapshot.syndicate_id == syndicate_id,
                    ExposureSnapshot.timestamp == latest_time
                )
            )
        )

        total = result.scalar()
        return Decimal(str(total or 0))

    async def _check_aggregate_limits(
        self,
        syndicate_id: int,
        aggregation_type: str
    ) -> List[CapacityAlert]:
        """Check limits for a specific aggregation type."""
        alerts = []

        result = await self.db.execute(
            select(ExposureAggregate)
            .where(
                and_(
                    ExposureAggregate.syndicate_id == syndicate_id,
                    ExposureAggregate.aggregation_type == aggregation_type
                )
            )
        )

        aggregates = result.scalars().all()

        for agg in aggregates:
            if agg.limit and agg.limit > 0:
                utilization = float(agg.current_exposure / agg.limit)

                if utilization >= self.CRITICAL_THRESHOLD:
                    alerts.append(CapacityAlert(
                        alert_type='limit_breach',
                        severity=AlertSeverity.CRITICAL,
                        dimension=aggregation_type,
                        key=agg.aggregation_key,
                        current_exposure=agg.current_exposure,
                        limit=agg.limit,
                        utilization_pct=utilization * 100,
                        message=f"CRITICAL: {aggregation_type.capitalize()} '{agg.aggregation_key}' at {utilization:.1%}"
                    ))
                elif utilization >= self.WARNING_THRESHOLD:
                    alerts.append(CapacityAlert(
                        alert_type='limit_warning',
                        severity=AlertSeverity.WARNING,
                        dimension=aggregation_type,
                        key=agg.aggregation_key,
                        current_exposure=agg.current_exposure,
                        limit=agg.limit,
                        utilization_pct=utilization * 100,
                        message=f"WARNING: {aggregation_type.capitalize()} '{agg.aggregation_key}' at {utilization:.1%}"
                    ))

        return alerts

    async def _upsert_aggregate(
        self,
        syndicate_id: int,
        aggregation_type: str,
        aggregation_key: str,
        current_exposure: Decimal,
        updated_at: datetime
    ) -> None:
        """Insert or update an aggregate record."""
        # Try to find existing record
        result = await self.db.execute(
            select(ExposureAggregate)
            .where(
                and_(
                    ExposureAggregate.syndicate_id == syndicate_id,
                    ExposureAggregate.aggregation_type == aggregation_type,
                    ExposureAggregate.aggregation_key == aggregation_key
                )
            )
        )

        existing = result.scalar_one_or_none()

        if existing:
            # Calculate trends
            trend_7d = await self._calculate_trend(syndicate_id, aggregation_type, aggregation_key, 7)
            trend_30d = await self._calculate_trend(syndicate_id, aggregation_type, aggregation_key, 30)

            # Calculate utilization if limit is set
            utilization = Decimal('0')
            if existing.limit and existing.limit > 0:
                utilization = (current_exposure / existing.limit) * 100

            existing.current_exposure = current_exposure
            existing.utilization_pct = utilization
            existing.trend_7d = trend_7d
            existing.trend_30d = trend_30d
            existing.updated_at = updated_at
        else:
            aggregate = ExposureAggregate(
                syndicate_id=syndicate_id,
                aggregation_type=aggregation_type,
                aggregation_key=aggregation_key,
                current_exposure=current_exposure,
                limit=None,  # To be set by administrator
                utilization_pct=Decimal('0'),
                trend_7d=None,
                trend_30d=None,
                updated_at=updated_at
            )
            self.db.add(aggregate)

    async def _calculate_trend(
        self,
        syndicate_id: int,
        aggregation_type: str,
        aggregation_key: str,
        days: int
    ) -> Optional[Decimal]:
        """Calculate percentage change over a period."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)

        # Get exposure at cutoff
        result = await self.db.execute(
            select(func.sum(ExposureSnapshot.net_exposure))
            .where(
                and_(
                    ExposureSnapshot.syndicate_id == syndicate_id,
                    ExposureSnapshot.timestamp <= cutoff,
                    ExposureSnapshot.timestamp >= cutoff - timedelta(hours=24)
                )
            )
        )

        old_exposure = result.scalar()

        if not old_exposure or old_exposure == 0:
            return None

        # Get current exposure
        current_result = await self.db.execute(
            select(ExposureAggregate.current_exposure)
            .where(
                and_(
                    ExposureAggregate.syndicate_id == syndicate_id,
                    ExposureAggregate.aggregation_type == aggregation_type,
                    ExposureAggregate.aggregation_key == aggregation_key
                )
            )
        )

        current = current_result.scalar()

        if current is None:
            return None

        change = ((Decimal(str(current)) - Decimal(str(old_exposure))) / Decimal(str(old_exposure))) * 100
        return change

    def _calculate_return_period_factor(self, return_period: int) -> float:
        """
        Calculate scaling factor for non-standard return periods.

        Uses log-linear interpolation between standard return periods.
        """
        import math

        # Reference points: 100yr = 1.0, 250yr = 1.5 (typical cat model scaling)
        if return_period <= 100:
            # Scale down from 100yr
            factor = math.log(return_period) / math.log(100)
        else:
            # Scale up from 100yr towards 250yr
            base_factor = 1.0
            target_factor = 1.5  # 250yr is typically 1.5x 100yr
            rp_ratio = (math.log(return_period) - math.log(100)) / (math.log(250) - math.log(100))
            factor = base_factor + (target_factor - base_factor) * rp_ratio

        return factor

    async def _gather_live_exposure_data(
        self,
        syndicate_id: int
    ) -> List[Dict[str, Any]]:
        """
        Gather current exposure data from live placements.

        Aggregates exposure from bound syndicate lines.
        """
        # Query active syndicate lines
        result = await self.db.execute(
            select(
                SyndicateLine,
                SubscriptionPlacement
            )
            .join(SubscriptionPlacement, SyndicateLine.placement_id == SubscriptionPlacement.id)
            .where(
                and_(
                    SyndicateLine.syndicate_id == syndicate_id,
                    SyndicateLine.status.in_(['written', 'signed']),
                    SubscriptionPlacement.status.in_(['bound', 'placing'])
                )
            )
        )

        rows = result.all()

        # Aggregate by dimensions
        exposure_map: Dict[tuple, Dict[str, Any]] = {}

        for line, placement in rows:
            # Calculate exposure based on line percentage and premium
            if placement.gross_premium and line.signed_line:
                gross_exposure = placement.gross_premium * (line.signed_line / 100)
            elif placement.gross_premium and line.line_percentage:
                gross_exposure = placement.gross_premium * (line.line_percentage / 100)
            else:
                continue

            # Get dimensions from placement (would come from assessment in full implementation)
            # For now, use placeholder aggregation
            key = ('unclassified', 'ROW', 'other', None)

            if key not in exposure_map:
                exposure_map[key] = {
                    'class_of_business': key[0],
                    'geographic_zone': key[1],
                    'peril': key[2],
                    'country': key[3],
                    'gross_exposure': Decimal('0'),
                    'net_exposure': Decimal('0'),
                    'reinsurance_recovery': Decimal('0'),
                    'pml_100yr': Decimal('0'),
                    'pml_250yr': Decimal('0'),
                    'policy_count': 0,
                }

            exposure_map[key]['gross_exposure'] += Decimal(str(gross_exposure))
            exposure_map[key]['net_exposure'] += Decimal(str(gross_exposure))  # Simplified
            exposure_map[key]['policy_count'] += 1

        return list(exposure_map.values())

    async def _calculate_live_exposure_by_zone(
        self,
        syndicate_id: int
    ) -> Dict[str, Decimal]:
        """Calculate exposure by zone from live data when no snapshots exist."""
        exposure_by_zone = {zone: Decimal('0') for zone in self.GEOGRAPHIC_ZONES.keys()}

        # Query active syndicate lines
        result = await self.db.execute(
            select(
                SyndicateLine,
                SubscriptionPlacement
            )
            .join(SubscriptionPlacement, SyndicateLine.placement_id == SubscriptionPlacement.id)
            .where(
                and_(
                    SyndicateLine.syndicate_id == syndicate_id,
                    SyndicateLine.status.in_(['written', 'signed']),
                    SubscriptionPlacement.status.in_(['bound', 'placing'])
                )
            )
        )

        rows = result.all()

        for line, placement in rows:
            if placement.gross_premium and line.signed_line:
                exposure = Decimal(str(placement.gross_premium)) * (Decimal(str(line.signed_line)) / 100)
                exposure_by_zone['ROW'] += exposure  # Default to ROW without detailed data

        return exposure_by_zone

    async def _calculate_live_exposure_by_peril(
        self,
        syndicate_id: int
    ) -> Dict[str, Decimal]:
        """Calculate exposure by peril from live data when no snapshots exist."""
        exposure_by_peril = {peril: Decimal('0') for peril in self.PERIL_CATEGORIES}

        result = await self.db.execute(
            select(
                SyndicateLine,
                SubscriptionPlacement
            )
            .join(SubscriptionPlacement, SyndicateLine.placement_id == SubscriptionPlacement.id)
            .where(
                and_(
                    SyndicateLine.syndicate_id == syndicate_id,
                    SyndicateLine.status.in_(['written', 'signed']),
                    SubscriptionPlacement.status.in_(['bound', 'placing'])
                )
            )
        )

        rows = result.all()

        for line, placement in rows:
            if placement.gross_premium and line.signed_line:
                exposure = Decimal(str(placement.gross_premium)) * (Decimal(str(line.signed_line)) / 100)
                exposure_by_peril['other'] += exposure  # Default to 'other' without detailed data

        return exposure_by_peril

    async def _calculate_live_exposure_by_class(
        self,
        syndicate_id: int
    ) -> Dict[str, Decimal]:
        """Calculate exposure by class from live data when no snapshots exist."""
        exposure_by_class: Dict[str, Decimal] = {}

        result = await self.db.execute(
            select(
                SyndicateLine,
                SubscriptionPlacement
            )
            .join(SubscriptionPlacement, SyndicateLine.placement_id == SubscriptionPlacement.id)
            .where(
                and_(
                    SyndicateLine.syndicate_id == syndicate_id,
                    SyndicateLine.status.in_(['written', 'signed']),
                    SubscriptionPlacement.status.in_(['bound', 'placing'])
                )
            )
        )

        rows = result.all()

        for line, placement in rows:
            if placement.gross_premium and line.signed_line:
                exposure = Decimal(str(placement.gross_premium)) * (Decimal(str(line.signed_line)) / 100)
                class_code = 'unclassified'  # Default without detailed data

                if class_code not in exposure_by_class:
                    exposure_by_class[class_code] = Decimal('0')

                exposure_by_class[class_code] += exposure

        return exposure_by_class


# Convenience function for dependency injection
async def get_exposure_service(db: AsyncSession) -> ExposureMonitoringService:
    """Get exposure monitoring service instance."""
    return ExposureMonitoringService(db)
