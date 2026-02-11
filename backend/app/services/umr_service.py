"""
InstantRisk V3 - UMR (Unique Market Reference) Service

Generates and manages Lloyd's Unique Market References.
UMR Format: B0999ABCDEF001
- B0999: Broker code (assigned by Lloyd's)
- 26: Year (last 2 digits)
- XXXXXX: Sequence number (alphanumeric)
"""

import re
from datetime import datetime
from typing import Optional, NamedTuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lloyds import UniqueMarketReference


class UMRComponents(NamedTuple):
    """Parsed components of a UMR."""
    broker_code: str
    year: str
    sequence: str
    full_umr: str


class UMRService:
    """
    Service for generating and managing Lloyd's UMRs.
    """

    # UMR format: B followed by 4 digits, then 6-10 alphanumeric characters
    UMR_PATTERN = re.compile(r'^B\d{4}[A-Z0-9]{6,10}$')

    # Default broker code prefix
    DEFAULT_BROKER_PREFIX = "B0999"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_umr(
        self,
        broker_code: Optional[str] = None,
        year: Optional[str] = None,
        assessment_id: Optional[str] = None,
        risk_type: Optional[str] = None,
        class_of_business: Optional[str] = None,
    ) -> str:
        """
        Generate a new Unique Market Reference.

        Args:
            broker_code: Lloyd's broker code (e.g., "B0999"). Defaults to system broker.
            year: 2-digit year (e.g., "26"). Defaults to current year.
            assessment_id: Optional linked assessment ID.
            risk_type: Optional risk type classification.
            class_of_business: Optional class of business.

        Returns:
            Generated UMR string.

        Raises:
            ValueError: If broker_code format is invalid.
        """
        # Default broker code
        if not broker_code:
            broker_code = self.DEFAULT_BROKER_PREFIX

        # Validate broker code format
        if not re.match(r'^B\d{4}$', broker_code):
            raise ValueError(f"Invalid broker code format: {broker_code}. Expected format: B followed by 4 digits (e.g., B0999)")

        # Default year
        if not year:
            year = datetime.now().strftime("%y")

        # Get next sequence number for this broker/year combination
        sequence = await self._get_next_sequence(broker_code, year)

        # Format sequence as alphanumeric (base 36 for compactness)
        sequence_str = self._format_sequence(sequence)

        # Build UMR
        umr = f"{broker_code}{year}{sequence_str}"

        # Create database record
        umr_record = UniqueMarketReference(
            umr=umr,
            broker_code=broker_code,
            year=year,
            sequence=sequence,
            assessment_id=assessment_id,
            risk_type=risk_type,
            class_of_business=class_of_business,
            status="active",
        )

        self.db.add(umr_record)
        await self.db.flush()

        return umr

    async def _get_next_sequence(self, broker_code: str, year: str) -> int:
        """
        Get the next sequence number for a broker/year combination.

        Args:
            broker_code: Lloyd's broker code.
            year: 2-digit year.

        Returns:
            Next sequence number (1-based).
        """
        # Query max sequence for this broker/year
        result = await self.db.execute(
            select(func.max(UniqueMarketReference.sequence))
            .where(UniqueMarketReference.broker_code == broker_code)
            .where(UniqueMarketReference.year == year)
        )
        max_sequence = result.scalar()

        if max_sequence is None:
            return 1
        return max_sequence + 1

    def _format_sequence(self, sequence: int) -> str:
        """
        Format sequence number as alphanumeric string.

        Uses base-36 encoding (0-9, A-Z) for compact representation.
        Pads to 6 characters for consistency.

        Args:
            sequence: Integer sequence number.

        Returns:
            6-character alphanumeric string.
        """
        # Convert to base 36
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if sequence == 0:
            return "000001"

        result = ""
        n = sequence
        while n:
            result = chars[n % 36] + result
            n //= 36

        # Pad to 6 characters
        return result.zfill(6)

    def validate_umr(self, umr: str) -> bool:
        """
        Validate UMR format.

        Args:
            umr: UMR string to validate.

        Returns:
            True if valid, False otherwise.
        """
        if not umr:
            return False

        # Check basic format
        if not self.UMR_PATTERN.match(umr):
            return False

        # Additional validation could check:
        # - Broker code exists in Lloyd's registry
        # - Year is reasonable (not future, not too old)

        return True

    def parse_umr(self, umr: str) -> Optional[UMRComponents]:
        """
        Parse a UMR into its component parts.

        Args:
            umr: UMR string to parse.

        Returns:
            UMRComponents namedtuple or None if invalid.
        """
        if not self.validate_umr(umr):
            return None

        # Extract components
        broker_code = umr[:5]  # B0999
        year = umr[5:7]        # 26
        sequence = umr[7:]     # XXXXXX

        return UMRComponents(
            broker_code=broker_code,
            year=year,
            sequence=sequence,
            full_umr=umr,
        )

    async def get_umr(self, umr: str) -> Optional[UniqueMarketReference]:
        """
        Get a UMR record by its identifier.

        Args:
            umr: UMR string.

        Returns:
            UniqueMarketReference model or None.
        """
        result = await self.db.execute(
            select(UniqueMarketReference).where(UniqueMarketReference.umr == umr)
        )
        return result.scalar_one_or_none()

    async def get_umr_by_assessment(self, assessment_id: str) -> Optional[UniqueMarketReference]:
        """
        Get UMR record linked to an assessment.

        Args:
            assessment_id: Assessment ID.

        Returns:
            UniqueMarketReference model or None.
        """
        result = await self.db.execute(
            select(UniqueMarketReference)
            .where(UniqueMarketReference.assessment_id == assessment_id)
        )
        return result.scalar_one_or_none()

    async def update_status(self, umr: str, status: str) -> bool:
        """
        Update the status of a UMR.

        Args:
            umr: UMR string.
            status: New status (active, placed, expired, cancelled).

        Returns:
            True if updated, False if not found.
        """
        valid_statuses = ["active", "placed", "expired", "cancelled"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

        umr_record = await self.get_umr(umr)
        if not umr_record:
            return False

        umr_record.status = status
        await self.db.flush()
        return True

    async def link_to_assessment(self, umr: str, assessment_id: str) -> bool:
        """
        Link a UMR to an assessment.

        Args:
            umr: UMR string.
            assessment_id: Assessment ID to link.

        Returns:
            True if linked, False if UMR not found.
        """
        umr_record = await self.get_umr(umr)
        if not umr_record:
            return False

        umr_record.assessment_id = assessment_id
        await self.db.flush()
        return True

    async def list_umrs(
        self,
        broker_code: Optional[str] = None,
        year: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UniqueMarketReference]:
        """
        List UMRs with optional filtering.

        Args:
            broker_code: Filter by broker code.
            year: Filter by year.
            status: Filter by status.
            limit: Maximum results.
            offset: Results offset.

        Returns:
            List of UniqueMarketReference models.
        """
        query = select(UniqueMarketReference)

        if broker_code:
            query = query.where(UniqueMarketReference.broker_code == broker_code)
        if year:
            query = query.where(UniqueMarketReference.year == year)
        if status:
            query = query.where(UniqueMarketReference.status == status)

        query = query.order_by(UniqueMarketReference.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())


# Convenience function for dependency injection
async def get_umr_service(db: AsyncSession) -> UMRService:
    """Get UMR service instance."""
    return UMRService(db)
