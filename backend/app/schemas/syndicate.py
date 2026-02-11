"""
InstantRisk V2 - Syndicate Schemas

Pydantic schemas for Syndicate CRUD operations.
Used by the Lloyd's Admin Dashboard for syndicate management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr


class SyndicateBase(BaseModel):
    """Base syndicate schema with common fields."""
    name: str = Field(..., description="Syndicate name", min_length=1, max_length=255)
    aiin: str = Field(..., description="Assigned Identification Number (unique Lloyd's identifier)", min_length=1, max_length=50)
    managing_agent: Optional[str] = Field(None, description="Name of the managing agent", max_length=255)

    # Capacity and financial settings
    capacity: Optional[float] = Field(None, description="Annual capacity in GBP")
    current_utilization: Optional[float] = Field(0.0, ge=0, le=100, description="Current capacity utilization percentage")
    min_premium: Optional[float] = Field(None, description="Minimum premium in GBP")
    max_premium: Optional[float] = Field(None, description="Maximum premium in GBP")
    target_loss_ratio: Optional[float] = Field(0.65, ge=0, le=1, description="Target loss ratio (0.0 to 1.0)")

    # Risk appetite configuration
    risk_appetite: Optional[Dict[str, Any]] = Field(default_factory=dict, description="JSON containing risk appetite parameters")

    # Business line configuration
    lines_of_business: Optional[List[str]] = Field(default_factory=list, description="List of business lines written")

    # Territory configuration
    excluded_territories: Optional[List[str]] = Field(default_factory=list, description="List of excluded territories")
    preferred_territories: Optional[List[str]] = Field(default_factory=list, description="List of preferred territories")

    # Contact information
    contact_email: Optional[EmailStr] = Field(None, description="Primary contact email")
    contact_phone: Optional[str] = Field(None, description="Primary contact phone number", max_length=50)
    notes: Optional[str] = Field(None, description="Additional notes about the syndicate")


class SyndicateCreate(SyndicateBase):
    """Schema for creating a new syndicate."""
    is_active: bool = Field(True, description="Whether the syndicate is currently active")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Apex Syndicate",
                "aiin": "1234",
                "managing_agent": "Apex Managing Agent Ltd",
                "capacity": 500000000.0,
                "min_premium": 50000.0,
                "max_premium": 10000000.0,
                "target_loss_ratio": 0.65,
                "lines_of_business": ["Marine", "Aviation", "Property D&F"],
                "excluded_territories": ["Sanctioned Countries"],
                "preferred_territories": ["UK", "EU", "USA"],
                "contact_email": "underwriting@apex.com",
                "contact_phone": "+44 20 7123 4567"
            }
        }


class SyndicateUpdate(BaseModel):
    """Schema for updating an existing syndicate. All fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    managing_agent: Optional[str] = Field(None, max_length=255)

    # Capacity and financial settings
    capacity: Optional[float] = None
    current_utilization: Optional[float] = Field(None, ge=0, le=100)
    min_premium: Optional[float] = None
    max_premium: Optional[float] = None
    target_loss_ratio: Optional[float] = Field(None, ge=0, le=1)

    # Risk appetite configuration
    risk_appetite: Optional[Dict[str, Any]] = None

    # Business line configuration
    lines_of_business: Optional[List[str]] = None

    # Territory configuration
    excluded_territories: Optional[List[str]] = None
    preferred_territories: Optional[List[str]] = None

    # Contact information
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None

    # Status
    is_active: Optional[bool] = None


class SyndicateResponse(BaseModel):
    """Schema for syndicate response."""
    id: int
    name: str
    aiin: str
    managing_agent: Optional[str]

    # Capacity and financial settings
    capacity: Optional[float]
    current_utilization: Optional[float]
    min_premium: Optional[float]
    max_premium: Optional[float]
    target_loss_ratio: Optional[float]

    # Risk appetite configuration
    risk_appetite: Optional[Dict[str, Any]]

    # Business line configuration
    lines_of_business: Optional[List[str]]

    # Territory configuration
    excluded_territories: Optional[List[str]]
    preferred_territories: Optional[List[str]]

    # Contact information
    contact_email: Optional[str]
    contact_phone: Optional[str]
    notes: Optional[str]

    # Status and timestamps
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Computed fields
    user_count: Optional[int] = Field(None, description="Number of users assigned to this syndicate")
    assessment_count: Optional[int] = Field(None, description="Number of assessments for this syndicate")

    class Config:
        from_attributes = True


class SyndicateListResponse(BaseModel):
    """Schema for paginated syndicate list response."""
    syndicates: List[SyndicateResponse]
    total: int
    skip: int
    limit: int


class SyndicateUserResponse(BaseModel):
    """Schema for users belonging to a syndicate."""
    id: UUID
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SyndicateUsersListResponse(BaseModel):
    """Schema for list of syndicate users."""
    users: List[SyndicateUserResponse]
    total: int
    syndicate_id: int
    syndicate_name: str
