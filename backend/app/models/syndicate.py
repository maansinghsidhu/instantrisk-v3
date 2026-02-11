"""
InstantRisk V2 - Syndicate Model

This module defines the Syndicate SQLAlchemy model representing
Lloyd's syndicates with their risk appetite and capacity settings.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class Syndicate(Base):
    """
    Syndicate model representing Lloyd's market syndicates.

    Attributes:
        id: Primary key identifier.
        name: Syndicate name.
        aiin: Assigned Identification Number (unique Lloyd's identifier).
        managing_agent: Name of the managing agent.
        capacity: Annual capacity in GBP.
        risk_appetite: JSON field containing risk appetite parameters.
        lines_of_business: JSON array of business lines the syndicate writes.
        excluded_territories: JSON array of territories not covered.
        min_premium: Minimum acceptable premium.
        max_premium: Maximum acceptable premium.
        target_loss_ratio: Target loss ratio percentage.
        is_active: Whether the syndicate is currently active.
        contact_email: Primary contact email.
        contact_phone: Primary contact phone number.
        notes: Additional notes about the syndicate.
        created_at: Timestamp when the syndicate was created.
        updated_at: Timestamp when the syndicate was last updated.
    """

    __tablename__ = "syndicates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    aiin = Column(String(50), unique=True, index=True, nullable=False)
    managing_agent = Column(String(255), nullable=True)

    # Capacity and financial settings
    capacity = Column(Float, nullable=True, comment="Annual capacity in GBP")
    current_utilization = Column(Float, default=0.0, comment="Current capacity utilization percentage")
    min_premium = Column(Float, nullable=True, comment="Minimum premium in GBP")
    max_premium = Column(Float, nullable=True, comment="Maximum premium in GBP")
    target_loss_ratio = Column(Float, default=0.65, comment="Target loss ratio (0.0 to 1.0)")

    # Risk appetite configuration
    risk_appetite = Column(
        JSON,
        default=dict,
        comment="JSON containing risk appetite parameters"
    )

    # Business line configuration
    lines_of_business = Column(
        JSON,
        default=list,
        comment="JSON array of business lines written"
    )

    # Territory configuration
    excluded_territories = Column(
        JSON,
        default=list,
        comment="JSON array of excluded territories"
    )
    preferred_territories = Column(
        JSON,
        default=list,
        comment="JSON array of preferred territories"
    )

    # Status and contact
    is_active = Column(Boolean, default=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    users = relationship("User", back_populates="syndicate")
    assessments = relationship("Assessment", back_populates="syndicate")
    reference_documents = relationship("ReferenceDocument", back_populates="syndicate")
    losses = relationship("ExposureLoss", back_populates="syndicate", cascade="all, delete-orphan")
    claims = relationship("ExposureClaim", back_populates="syndicate", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """String representation of the Syndicate."""
        return f"<Syndicate(id={self.id}, name='{self.name}', aiin='{self.aiin}')>"

    def has_capacity_for(self, amount: float) -> bool:
        """
        Check if the syndicate has capacity for a given amount.

        Args:
            amount: The amount to check capacity for.

        Returns:
            bool: True if capacity is available, False otherwise.
        """
        if self.capacity is None:
            return True
        available = self.capacity * (1 - (self.current_utilization / 100))
        return available >= amount

    def is_in_risk_appetite(self, risk_params: dict) -> bool:
        """
        Check if a risk falls within the syndicate's appetite.

        Args:
            risk_params: Dictionary of risk parameters to evaluate.

        Returns:
            bool: True if the risk is within appetite, False otherwise.
        """
        if not self.risk_appetite:
            return True

        # Basic validation - extend as needed
        for key, value in risk_params.items():
            if key in self.risk_appetite:
                appetite = self.risk_appetite[key]
                if isinstance(appetite, dict):
                    min_val = appetite.get("min")
                    max_val = appetite.get("max")
                    if min_val is not None and value < min_val:
                        return False
                    if max_val is not None and value > max_val:
                        return False

        return True
