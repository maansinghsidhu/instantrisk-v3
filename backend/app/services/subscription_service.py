"""
InstantRisk V3 - Subscription Workflow Service

Manages Lloyd's subscription market placements where risks are placed across
multiple syndicates. Handles the full placement lifecycle from marketing
through to binding.

Key concepts:
- Placement: The overall risk being placed in the market
- Lead syndicate: The first syndicate to quote, sets terms and conditions
- Follower lines: Subsequent syndicates that follow the lead
- Signed line: Final adjusted line after signing (may differ from written line)
- Signing schedule: The calculation that adjusts lines to reach 100%
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, List, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lloyds import (
    SubscriptionPlacement,
    SyndicateLine,
    PlacementActivityLog,
    UniqueMarketReference,
)
from app.models.syndicate import Syndicate


class SubscriptionWorkflowService:
    """
    Service for managing Lloyd's subscription market placements.

    The subscription market workflow involves:
    1. Creating a placement with a lead syndicate
    2. Adding follower lines from other syndicates
    3. Tracking line statuses (quoted, written, signed, declined)
    4. Calculating signed lines when placement is complete
    5. Generating the signing schedule for settlement
    """

    # Valid placement statuses
    PLACEMENT_STATUSES = ["marketing", "quoting", "placing", "bound", "declined", "expired"]

    # Valid line statuses
    LINE_STATUSES = ["quoted", "written", "signed", "declined", "scratched"]

    def __init__(self, db: AsyncSession):
        """
        Initialize the subscription workflow service.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    async def create_placement(
        self,
        umr: str,
        lead_syndicate_id: int,
        details: dict,
    ) -> SubscriptionPlacement:
        """
        Create a new subscription placement.

        Args:
            umr: Unique Market Reference for the risk.
            lead_syndicate_id: ID of the lead syndicate.
            details: Additional placement details including:
                - lead_underwriter_name: Name of lead underwriter
                - gross_premium: Total premium amount
                - currency: Currency code (default GBP)
                - target_line: Target percentage (default 100)
                - minimum_lead_line: Minimum lead line % (default 25)
                - quote_deadline: Deadline for quotes
                - inception_date: Policy inception date
                - expiry_date: Policy expiry date

        Returns:
            Created SubscriptionPlacement instance.

        Raises:
            ValueError: If UMR doesn't exist or lead syndicate is invalid.
        """
        # Verify UMR exists
        umr_result = await self.db.execute(
            select(UniqueMarketReference).where(UniqueMarketReference.umr == umr)
        )
        umr_record = umr_result.scalar_one_or_none()
        if not umr_record:
            raise ValueError(f"UMR not found: {umr}")

        # Verify lead syndicate exists
        syndicate_result = await self.db.execute(
            select(Syndicate).where(Syndicate.id == lead_syndicate_id)
        )
        lead_syndicate = syndicate_result.scalar_one_or_none()
        if not lead_syndicate:
            raise ValueError(f"Lead syndicate not found: {lead_syndicate_id}")

        # Create placement
        placement = SubscriptionPlacement(
            umr=umr,
            lead_syndicate_id=lead_syndicate_id,
            lead_underwriter_name=details.get("lead_underwriter_name"),
            gross_premium=details.get("gross_premium"),
            currency=details.get("currency", "GBP"),
            target_line=details.get("target_line", Decimal("100")),
            minimum_lead_line=details.get("minimum_lead_line", Decimal("25")),
            quote_deadline=details.get("quote_deadline"),
            inception_date=details.get("inception_date"),
            expiry_date=details.get("expiry_date"),
            status="marketing",
            total_line=Decimal("0"),
        )

        self.db.add(placement)
        await self.db.flush()

        # Log the creation
        await self.log_activity(
            placement_id=placement.id,
            action="placement_created",
            actor_id=details.get("created_by_id"),
            actor_type=details.get("created_by_type", "system"),
            details={
                "umr": umr,
                "lead_syndicate_id": lead_syndicate_id,
                "lead_syndicate_name": lead_syndicate.name,
            },
        )

        return placement

    async def get_placement(self, placement_id: int) -> Optional[SubscriptionPlacement]:
        """
        Get a placement by ID with all related data.

        Args:
            placement_id: Placement ID.

        Returns:
            SubscriptionPlacement instance or None if not found.
        """
        result = await self.db.execute(
            select(SubscriptionPlacement)
            .options(
                selectinload(SubscriptionPlacement.lines).selectinload(SyndicateLine.syndicate),
                selectinload(SubscriptionPlacement.lead_syndicate),
                selectinload(SubscriptionPlacement.activity_log),
            )
            .where(SubscriptionPlacement.id == placement_id)
        )
        return result.scalar_one_or_none()

    async def get_placement_by_umr(self, umr: str) -> Optional[SubscriptionPlacement]:
        """
        Get a placement by UMR with all related data.

        Args:
            umr: Unique Market Reference.

        Returns:
            SubscriptionPlacement instance or None if not found.
        """
        result = await self.db.execute(
            select(SubscriptionPlacement)
            .options(
                selectinload(SubscriptionPlacement.lines).selectinload(SyndicateLine.syndicate),
                selectinload(SubscriptionPlacement.lead_syndicate),
                selectinload(SubscriptionPlacement.activity_log),
            )
            .where(SubscriptionPlacement.umr == umr)
        )
        return result.scalar_one_or_none()

    async def add_follower_line(
        self,
        placement_id: int,
        syndicate_id: int,
        line_percentage: float,
        conditions: str = None,
    ) -> SyndicateLine:
        """
        Add a follower syndicate line to a placement.

        Args:
            placement_id: Placement ID.
            syndicate_id: Syndicate ID.
            line_percentage: Percentage of risk the syndicate is taking.
            conditions: Optional conditions attached to the line.

        Returns:
            Created SyndicateLine instance.

        Raises:
            ValueError: If placement or syndicate not found, or syndicate already has a line.
        """
        # Get placement
        placement = await self.get_placement(placement_id)
        if not placement:
            raise ValueError(f"Placement not found: {placement_id}")

        # Verify syndicate exists
        syndicate_result = await self.db.execute(
            select(Syndicate).where(Syndicate.id == syndicate_id)
        )
        syndicate = syndicate_result.scalar_one_or_none()
        if not syndicate:
            raise ValueError(f"Syndicate not found: {syndicate_id}")

        # Check if syndicate already has a line on this placement
        existing_line_result = await self.db.execute(
            select(SyndicateLine).where(
                and_(
                    SyndicateLine.placement_id == placement_id,
                    SyndicateLine.syndicate_id == syndicate_id,
                )
            )
        )
        if existing_line_result.scalar_one_or_none():
            raise ValueError(f"Syndicate {syndicate_id} already has a line on placement {placement_id}")

        # Create the line
        line = SyndicateLine(
            placement_id=placement_id,
            syndicate_id=syndicate_id,
            syndicate_number=syndicate.aiin,
            syndicate_name=syndicate.name,
            line_percentage=Decimal(str(line_percentage)),
            conditions=conditions,
            status="quoted",
            quoted_at=datetime.now(timezone.utc),
        )

        self.db.add(line)
        await self.db.flush()

        # Update total line on placement
        await self._update_total_line(placement_id)

        # Log the activity
        await self.log_activity(
            placement_id=placement_id,
            action="line_quoted",
            actor_id=syndicate_id,
            actor_type="syndicate",
            details={
                "syndicate_id": syndicate_id,
                "syndicate_name": syndicate.name,
                "line_percentage": float(line_percentage),
                "conditions": conditions,
            },
        )

        return line

    async def update_line_status(self, line_id: int, status: str) -> SyndicateLine:
        """
        Update the status of a syndicate line.

        Args:
            line_id: SyndicateLine ID.
            status: New status (quoted, written, signed, declined, scratched).

        Returns:
            Updated SyndicateLine instance.

        Raises:
            ValueError: If line not found or invalid status.
        """
        if status not in self.LINE_STATUSES:
            raise ValueError(f"Invalid line status: {status}. Must be one of {self.LINE_STATUSES}")

        # Get line
        result = await self.db.execute(
            select(SyndicateLine)
            .options(selectinload(SyndicateLine.syndicate))
            .where(SyndicateLine.id == line_id)
        )
        line = result.scalar_one_or_none()
        if not line:
            raise ValueError(f"Line not found: {line_id}")

        old_status = line.status
        line.status = status

        # Update timestamps based on status
        now = datetime.now(timezone.utc)
        if status == "written":
            line.written_at = now
        elif status == "signed":
            line.signed_at = now

        await self.db.flush()

        # Update total line on placement (exclude declined/scratched lines)
        await self._update_total_line(line.placement_id)

        # Log the activity
        await self.log_activity(
            placement_id=line.placement_id,
            action=f"line_{status}",
            actor_id=line.syndicate_id,
            actor_type="syndicate",
            details={
                "line_id": line_id,
                "syndicate_id": line.syndicate_id,
                "syndicate_name": line.syndicate_name,
                "old_status": old_status,
                "new_status": status,
            },
        )

        return line

    async def _update_total_line(self, placement_id: int) -> None:
        """
        Update the total line percentage on a placement.

        Only counts lines that are not declined or scratched.

        Args:
            placement_id: Placement ID.
        """
        result = await self.db.execute(
            select(func.sum(SyndicateLine.line_percentage))
            .where(SyndicateLine.placement_id == placement_id)
            .where(SyndicateLine.status.not_in(["declined", "scratched"]))
        )
        total = result.scalar() or Decimal("0")

        # Update placement
        placement_result = await self.db.execute(
            select(SubscriptionPlacement).where(SubscriptionPlacement.id == placement_id)
        )
        placement = placement_result.scalar_one_or_none()
        if placement:
            placement.total_line = total
            await self.db.flush()

    async def calculate_signed_lines(self, placement_id: int) -> dict:
        """
        Calculate the signing schedule for a placement.

        The signing schedule adjusts written lines proportionally to reach
        the target line (typically 100%). This is necessary when the total
        written line exceeds or falls short of the target.

        Args:
            placement_id: Placement ID.

        Returns:
            Dictionary containing:
                - total_written: Total written line percentage
                - target_line: Target percentage
                - signing_percentage: Percentage applied to calculate signed lines
                - lines: List of lines with calculated signed amounts

        Raises:
            ValueError: If placement not found.
        """
        placement = await self.get_placement(placement_id)
        if not placement:
            raise ValueError(f"Placement not found: {placement_id}")

        # Get all active lines (not declined/scratched)
        active_lines = [
            line for line in placement.lines
            if line.status not in ["declined", "scratched"]
        ]

        # Calculate total written line
        total_written = sum(float(line.line_percentage) for line in active_lines)
        target = float(placement.target_line)

        # Calculate signing percentage
        # If total_written > target, lines are signed down
        # If total_written < target, lines may be signed up (rare in practice)
        if total_written > 0:
            signing_percentage = (target / total_written) * 100
        else:
            signing_percentage = 100.0

        # Calculate signed lines for each syndicate
        lines_data = []
        for line in active_lines:
            written = float(line.line_percentage)
            signed = written * (signing_percentage / 100)
            lines_data.append({
                "line_id": line.id,
                "syndicate_id": line.syndicate_id,
                "syndicate_name": line.syndicate_name,
                "written_line": round(written, 4),
                "signed_line": round(signed, 4),
                "status": line.status,
            })

        return {
            "placement_id": placement_id,
            "umr": placement.umr,
            "total_written": round(total_written, 4),
            "target_line": round(target, 4),
            "signing_percentage": round(signing_percentage, 4),
            "lines": lines_data,
        }

    async def generate_signing_schedule(self, placement_id: int) -> list:
        """
        Generate and apply the signing schedule for a placement.

        This calculates each syndicate's signed line and updates the database.
        The signing schedule is the official record of each syndicate's
        participation after adjustment.

        Args:
            placement_id: Placement ID.

        Returns:
            List of dictionaries with each syndicate's signed line details.

        Raises:
            ValueError: If placement not found or no active lines.
        """
        signing_data = await self.calculate_signed_lines(placement_id)

        if not signing_data["lines"]:
            raise ValueError(f"No active lines on placement {placement_id}")

        schedule = []

        for line_data in signing_data["lines"]:
            # Update the signed line in database
            result = await self.db.execute(
                select(SyndicateLine).where(SyndicateLine.id == line_data["line_id"])
            )
            line = result.scalar_one_or_none()
            if line:
                line.signed_line = Decimal(str(line_data["signed_line"]))
                line.order_percentage = Decimal(str(signing_data["signing_percentage"]))

                schedule.append({
                    "line_id": line.id,
                    "syndicate_id": line.syndicate_id,
                    "syndicate_number": line.syndicate_number,
                    "syndicate_name": line.syndicate_name,
                    "written_line": line_data["written_line"],
                    "signed_line": line_data["signed_line"],
                    "order_percentage": signing_data["signing_percentage"],
                    "conditions": line.conditions,
                })

        await self.db.flush()

        # Log the signing schedule generation
        await self.log_activity(
            placement_id=placement_id,
            action="signing_schedule_generated",
            actor_id=None,
            actor_type="system",
            details={
                "total_written": signing_data["total_written"],
                "target_line": signing_data["target_line"],
                "signing_percentage": signing_data["signing_percentage"],
                "syndicate_count": len(schedule),
            },
        )

        return schedule

    async def check_minimum_met(self, placement_id: int) -> bool:
        """
        Check if the placement has met minimum requirements.

        Requirements checked:
        1. Lead line meets minimum lead line percentage
        2. Total line meets or exceeds target

        Args:
            placement_id: Placement ID.

        Returns:
            True if minimum requirements are met, False otherwise.

        Raises:
            ValueError: If placement not found.
        """
        placement = await self.get_placement(placement_id)
        if not placement:
            raise ValueError(f"Placement not found: {placement_id}")

        # Find lead syndicate's line
        lead_line = None
        for line in placement.lines:
            if line.syndicate_id == placement.lead_syndicate_id:
                lead_line = line
                break

        # Check lead line minimum
        if not lead_line:
            return False

        if lead_line.status in ["declined", "scratched"]:
            return False

        lead_percentage = float(lead_line.line_percentage)
        minimum_lead = float(placement.minimum_lead_line)

        if lead_percentage < minimum_lead:
            return False

        # Check total line meets target
        total = float(placement.total_line)
        target = float(placement.target_line)

        return total >= target

    async def log_activity(
        self,
        placement_id: int,
        action: str,
        actor_id: Optional[int],
        actor_type: str,
        details: dict,
    ) -> PlacementActivityLog:
        """
        Log an activity on a placement.

        Args:
            placement_id: Placement ID.
            action: Action type (e.g., line_quoted, line_written, status_changed).
            actor_id: ID of the actor (user, syndicate, or None for system).
            actor_type: Type of actor (broker, underwriter, syndicate, system).
            details: Additional details about the activity.

        Returns:
            Created PlacementActivityLog instance.
        """
        # Get actor name if it's a syndicate
        actor_name = None
        if actor_type == "syndicate" and actor_id:
            syndicate_result = await self.db.execute(
                select(Syndicate).where(Syndicate.id == actor_id)
            )
            syndicate = syndicate_result.scalar_one_or_none()
            if syndicate:
                actor_name = syndicate.name

        log_entry = PlacementActivityLog(
            placement_id=placement_id,
            action=action,
            actor_id=actor_id,
            actor_type=actor_type,
            actor_name=actor_name,
            details=details,
        )

        self.db.add(log_entry)
        await self.db.flush()

        return log_entry

    async def list_placements(
        self,
        status: str = None,
        syndicate_id: int = None,
        limit: int = 100,
    ) -> List[SubscriptionPlacement]:
        """
        List placements with optional filtering.

        Args:
            status: Filter by placement status.
            syndicate_id: Filter by syndicate (as lead or follower).
            limit: Maximum number of results (default 100).

        Returns:
            List of SubscriptionPlacement instances.
        """
        query = select(SubscriptionPlacement).options(
            selectinload(SubscriptionPlacement.lines),
            selectinload(SubscriptionPlacement.lead_syndicate),
        )

        if status:
            if status not in self.PLACEMENT_STATUSES:
                raise ValueError(f"Invalid status: {status}. Must be one of {self.PLACEMENT_STATUSES}")
            query = query.where(SubscriptionPlacement.status == status)

        if syndicate_id:
            # Find placements where syndicate is lead or has a line
            subquery = select(SyndicateLine.placement_id).where(
                SyndicateLine.syndicate_id == syndicate_id
            ).distinct()

            query = query.where(
                or_(
                    SubscriptionPlacement.lead_syndicate_id == syndicate_id,
                    SubscriptionPlacement.id.in_(subquery),
                )
            )

        query = query.order_by(SubscriptionPlacement.created_at.desc())
        query = query.limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_placement_status(self, placement_id: int, status: str) -> SubscriptionPlacement:
        """
        Update the status of a placement.

        Args:
            placement_id: Placement ID.
            status: New status (marketing, quoting, placing, bound, declined, expired).

        Returns:
            Updated SubscriptionPlacement instance.

        Raises:
            ValueError: If placement not found or invalid status.
        """
        if status not in self.PLACEMENT_STATUSES:
            raise ValueError(f"Invalid status: {status}. Must be one of {self.PLACEMENT_STATUSES}")

        placement = await self.get_placement(placement_id)
        if not placement:
            raise ValueError(f"Placement not found: {placement_id}")

        old_status = placement.status
        placement.status = status

        # Update placed_at timestamp if binding
        if status == "bound":
            placement.placed_at = datetime.now(timezone.utc)

        await self.db.flush()

        # Log the status change
        await self.log_activity(
            placement_id=placement_id,
            action="status_changed",
            actor_id=None,
            actor_type="system",
            details={
                "old_status": old_status,
                "new_status": status,
            },
        )

        return placement


# Convenience function for dependency injection
async def get_subscription_service(db: AsyncSession) -> SubscriptionWorkflowService:
    """Get subscription workflow service instance."""
    return SubscriptionWorkflowService(db)
