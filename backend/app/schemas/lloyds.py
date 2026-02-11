"""
InstantRisk V3 - Lloyd's Market Schemas

Pydantic schemas using proper Lloyd's market terminology.
These schemas ensure the API speaks the language underwriters expect.

Key Lloyd's Terminology:
- UMR: Unique Market Reference (risk identifier)
- MRC: Market Reform Contract (standard slip format)
- Slip: The placing document
- Line: Syndicate participation percentage
- Signed Line: Final participation after bureau signing
- Lead: Primary underwriter taking largest line
- Following Market: Syndicates following the lead
- Subjectivities: Conditions precedent to cover
- PMDR: Premium and Claims Market Data Returns
- RDS: Realistic Disaster Scenarios
- Managing Agent: Company managing the syndicate
- Capacity: Annual underwriting limit
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, validator


# =============================================================================
# UMR (Unique Market Reference) Schemas
# =============================================================================

class UMRCreate(BaseModel):
    """Request to generate a new UMR."""
    broker_pin: Optional[str] = Field(
        None,
        description="Lloyd's broker PIN (e.g., 'B0999'). Defaults to system broker."
    )
    year_of_account: Optional[str] = Field(
        None,
        description="Year of account (YOA) - 2-digit year. Defaults to current."
    )
    class_of_business: Optional[str] = Field(
        None,
        description="Lloyd's class of business code"
    )
    risk_type: Optional[str] = Field(
        None,
        description="Type of risk being placed"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "broker_pin": "B0999",
                "year_of_account": "26",
                "class_of_business": "Property D&F",
                "risk_type": "commercial_property"
            }
        }


class UMRResponse(BaseModel):
    """Generated UMR details."""
    umr: str = Field(..., description="Unique Market Reference")
    broker_pin: str = Field(..., description="Lloyd's broker PIN")
    year_of_account: str = Field(..., description="Year of account")
    sequence: int = Field(..., description="Sequence number")
    status: str = Field(..., description="UMR status (active, placed, expired)")
    created_at: datetime


# =============================================================================
# Subscription Market / Placing Schemas
# =============================================================================

class PlacementCreate(BaseModel):
    """Request to create a new subscription placement."""
    umr: str = Field(..., description="Unique Market Reference for this risk")
    lead_syndicate: int = Field(
        ...,
        description="Lead underwriter's syndicate number"
    )
    lead_underwriter: Optional[str] = Field(
        None,
        description="Name of lead underwriter"
    )
    gross_premium: Decimal = Field(
        ...,
        description="Gross premium amount (100% basis)"
    )
    currency: str = Field(
        "GBP",
        description="Premium currency (ISO 4217)"
    )
    target_line: Decimal = Field(
        Decimal("100"),
        description="Target placement percentage"
    )
    minimum_lead_line: Decimal = Field(
        Decimal("25"),
        description="Minimum lead syndicate line percentage"
    )
    inception_date: datetime = Field(..., description="Policy inception date")
    expiry_date: datetime = Field(..., description="Policy expiry date")
    quote_deadline: Optional[datetime] = Field(
        None,
        description="Deadline for follower quotes"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "umr": "B099926ABC001",
                "lead_syndicate": 1234,
                "lead_underwriter": "J. Smith",
                "gross_premium": "125000.00",
                "currency": "GBP",
                "target_line": "100.00",
                "minimum_lead_line": "25.00",
                "inception_date": "2026-04-01T00:00:00Z",
                "expiry_date": "2027-03-31T23:59:59Z"
            }
        }


class SyndicateLineRequest(BaseModel):
    """Request to add or update a syndicate line."""
    syndicate_number: str = Field(
        ...,
        description="Lloyd's syndicate number (e.g., '1234')"
    )
    syndicate_name: Optional[str] = Field(
        None,
        description="Syndicate name"
    )
    written_line: Decimal = Field(
        ...,
        description="Written line percentage",
        ge=0,
        le=100
    )
    order_percentage: Optional[Decimal] = Field(
        None,
        description="Order percentage (for proportional placements)"
    )
    conditions: Optional[str] = Field(
        None,
        description="Special conditions or subjectivities"
    )
    subjectivities: Optional[List[str]] = Field(
        default_factory=list,
        description="List of subjectivities (conditions precedent)"
    )
    quote_reference: Optional[str] = Field(
        None,
        description="Syndicate's quote reference"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "syndicate_number": "5678",
                "syndicate_name": "ABC Syndicate",
                "written_line": "15.00",
                "conditions": "Subject to NTU",
                "subjectivities": [
                    "Subject satisfactory loss record",
                    "Subject signed slip within 7 days"
                ]
            }
        }


class SyndicateLineResponse(BaseModel):
    """Syndicate line details."""
    id: int
    syndicate_number: str
    syndicate_name: Optional[str]
    written_line: Decimal = Field(..., description="Written (quoted) line %")
    signed_line: Optional[Decimal] = Field(
        None,
        description="Signed line % (after bureau signing)"
    )
    order_percentage: Optional[Decimal]
    status: str = Field(
        ...,
        description="Line status: quoted, written, signed, declined, scratched"
    )
    conditions: Optional[str]
    subjectivities: List[str]
    quoted_at: Optional[datetime]
    written_at: Optional[datetime]
    signed_at: Optional[datetime]


class PlacementResponse(BaseModel):
    """Full placement details."""
    id: int
    umr: str
    lead_syndicate_id: int
    lead_underwriter_name: Optional[str]
    total_line: Decimal = Field(..., description="Total placed line %")
    target_line: Decimal
    minimum_lead_line: Decimal
    status: str = Field(
        ...,
        description="Placement status: marketing, quoting, placing, bound, declined"
    )
    gross_premium: Decimal
    currency: str
    inception_date: datetime
    expiry_date: datetime
    created_at: datetime
    placed_at: Optional[datetime]
    lines: List[SyndicateLineResponse] = Field(
        default_factory=list,
        description="Participating syndicate lines"
    )


class SigningSchedule(BaseModel):
    """Bureau signing schedule."""
    umr: str
    total_written_line: Decimal
    signing_date: Optional[datetime]
    lines: List[Dict[str, Any]] = Field(
        ...,
        description="Lines with calculated signed percentages"
    )


# =============================================================================
# Exposure Management Schemas
# =============================================================================

class ExposureByZone(BaseModel):
    """Exposure aggregated by geographic zone."""
    zone: str = Field(..., description="Geographic zone (e.g., 'NA', 'EU', 'APAC')")
    gross_exposure: Decimal
    net_exposure: Decimal
    policy_count: int
    utilization_percentage: Optional[Decimal] = Field(
        None,
        description="Zone capacity utilization %"
    )


class ExposureByPeril(BaseModel):
    """Exposure aggregated by peril type."""
    peril: str = Field(
        ...,
        description="Peril type (e.g., 'windstorm', 'earthquake', 'cyber')"
    )
    gross_exposure: Decimal
    net_exposure: Decimal
    pml_100yr: Optional[Decimal] = Field(
        None,
        description="100-year Probable Maximum Loss"
    )
    pml_250yr: Optional[Decimal] = Field(
        None,
        description="250-year Probable Maximum Loss"
    )


class ExposureDashboard(BaseModel):
    """Syndicate exposure dashboard data."""
    syndicate_id: int
    as_of: datetime
    total_gross_exposure: Decimal
    total_net_exposure: Decimal
    capacity: Optional[Decimal]
    utilization_percentage: Decimal
    by_zone: List[ExposureByZone]
    by_peril: List[ExposureByPeril]
    alerts: List[str] = Field(
        default_factory=list,
        description="Capacity breach alerts"
    )


class EventAccumulationRequest(BaseModel):
    """Request to run event accumulation analysis."""
    event_type: str = Field(
        ...,
        description="Type of event (e.g., 'hurricane', 'earthquake', 'cyber_event')"
    )
    event_name: str = Field(..., description="Event name/identifier")
    affected_region: str = Field(..., description="Geographic region affected")
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Event-specific parameters"
    )


class EventAccumulationResponse(BaseModel):
    """Event accumulation analysis results."""
    event_id: str
    event_name: str
    event_type: str
    region: str
    gross_exposure: Decimal
    net_exposure: Decimal
    policies_affected: int
    calculated_at: datetime


# =============================================================================
# Compliance Schemas
# =============================================================================

class PMDRRequest(BaseModel):
    """Request to generate PMDR return."""
    period: str = Field(
        ...,
        description="Reporting period (e.g., '2026-Q1', '2026-H1')"
    )
    include_classes: Optional[List[str]] = Field(
        None,
        description="Specific classes to include (or all if None)"
    )


class PMDRResponse(BaseModel):
    """PMDR return data."""
    period: str
    syndicate_id: int
    gross_written_premium: Decimal = Field(
        ...,
        description="GWP for the period"
    )
    net_written_premium: Decimal = Field(
        ...,
        description="NWP for the period"
    )
    gross_earned_premium: Decimal
    net_earned_premium: Decimal
    gross_claims_paid: Decimal
    net_claims_paid: Decimal
    gross_claims_outstanding: Decimal = Field(
        ...,
        description="GCOS - Gross Claims Outstanding"
    )
    net_claims_outstanding: Decimal = Field(
        ...,
        description="NCOS - Net Claims Outstanding"
    )
    reinsurance_premium_ceded: Decimal
    reinsurance_recoveries: Decimal
    by_class: Dict[str, Any]
    by_year_of_account: Dict[str, Any]
    validation_status: str
    generated_at: datetime


class RDSScenario(BaseModel):
    """Single RDS scenario result."""
    scenario_id: str = Field(..., description="RDS scenario identifier")
    scenario_name: str
    scenario_type: str = Field(..., description="nat_cat or man_made")
    region: str
    gross_loss: Decimal
    net_loss: Decimal
    policies_affected: int


class RDSResponse(BaseModel):
    """RDS calculation results."""
    period: str
    syndicate_id: int
    scenarios: List[RDSScenario]
    total_gross_loss: Decimal
    total_net_loss: Decimal
    pml_100yr: Decimal = Field(..., description="100-year PML")
    pml_250yr: Decimal = Field(..., description="250-year PML")
    validation_status: str
    calculated_at: datetime


class ComplianceSubmissionStatus(BaseModel):
    """Compliance submission status."""
    id: int
    submission_type: str = Field(
        ...,
        description="Type: PMDR, RDS, QRT, SCR"
    )
    period: str
    status: str = Field(
        ...,
        description="Status: draft, validated, submitted, accepted, rejected"
    )
    is_valid: bool
    validation_errors: List[Dict[str, str]]
    validation_warnings: List[Dict[str, str]]
    submitted_at: Optional[datetime]
    submission_reference: Optional[str] = Field(
        None,
        description="Lloyd's/regulator submission reference"
    )


# =============================================================================
# Data Quality Schemas
# =============================================================================

class DataQualityScore(BaseModel):
    """Data quality assessment scores."""
    overall_score: float = Field(..., ge=0, le=100)
    completeness_score: float = Field(
        ...,
        description="Required fields populated"
    )
    accuracy_score: float = Field(
        ...,
        description="Values within expected ranges"
    )
    consistency_score: float = Field(
        ...,
        description="No conflicting data"
    )
    timeliness_score: float = Field(
        ...,
        description="Data freshness"
    )
    validity_score: float = Field(
        ...,
        description="Format compliance"
    )
    passed: bool
    critical_issues: int
    total_issues: int


class DataQualityIssue(BaseModel):
    """Single data quality issue."""
    field: str
    severity: str = Field(..., description="critical, warning, info")
    message: str
    suggestion: Optional[str]


class DataQualityReport(BaseModel):
    """Complete data quality report."""
    assessment_id: UUID
    scores: DataQualityScore
    issues: List[DataQualityIssue]
    suggestions: List[str]
    auto_corrections_applied: int
    generated_at: datetime


# =============================================================================
# Integration Schemas
# =============================================================================

class ConnectorConfig(BaseModel):
    """Integration connector configuration."""
    connector_type: str = Field(
        ...,
        description="Type: rest_api, webhook, ppl, ecot, sftp"
    )
    name: str = Field(..., description="Connector display name")
    base_url: Optional[str]
    api_key: Optional[str] = Field(None, description="API key (write-only)")
    username: Optional[str]
    password: Optional[str] = Field(None, description="Password (write-only)")
    timeout: int = Field(30, description="Request timeout in seconds")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    event_filter: Optional[List[str]] = Field(
        None,
        description="For webhooks: events to send"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "connector_type": "webhook",
                "name": "UW Workbench Webhook",
                "base_url": "https://uw.syndicate.com/api/webhook",
                "event_filter": [
                    "assessment.completed",
                    "quote.generated"
                ]
            }
        }


class ConnectorStatus(BaseModel):
    """Connector health status."""
    id: int
    connector_type: str
    name: str
    status: str = Field(..., description="connected, disconnected, error")
    health: str = Field(..., description="healthy, degraded, unhealthy")
    last_sync_at: Optional[datetime]
    last_error: Optional[str]


class IngestRequest(BaseModel):
    """Request to ingest data from external system."""
    source: str = Field(..., description="Source system identifier")
    data_type: str = Field(
        ...,
        description="Type of data: submission, policy, claim, bordereaux"
    )
    data: Dict[str, Any] = Field(..., description="Data payload")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    """Response to data ingestion."""
    success: bool
    records_processed: int
    records_created: int
    records_updated: int
    errors: List[str]
    warnings: List[str]


# =============================================================================
# Pricing / Quote Schemas
# =============================================================================

class PricingRequest(BaseModel):
    """Request for technical pricing."""
    assessment_id: UUID
    class_of_business: str
    limit_of_liability: Decimal
    currency: str = "GBP"
    deductible: Optional[Decimal]
    territory: Optional[str]


class PricingResponse(BaseModel):
    """Technical pricing result."""
    assessment_id: UUID
    technical_premium: Decimal
    currency: str
    risk_score: float = Field(..., description="Risk score 0-100")
    risk_category: str = Field(..., description="low, medium, high, very_high")
    confidence_low: Decimal
    confidence_high: Decimal
    loading_factors: Dict[str, float]
    key_drivers: List[str]
    explanation: str


class QuoteCreate(BaseModel):
    """Request to generate a formal quote."""
    pricing_result_id: int
    quoted_premium: Decimal
    quoted_line: Optional[Decimal] = Field(
        None,
        description="Offered line percentage"
    )
    terms: Dict[str, Any] = Field(default_factory=dict)
    conditions: List[str] = Field(default_factory=list)
    subjectivities: List[str] = Field(
        default_factory=list,
        description="Conditions precedent to attachment"
    )
    exclusions: List[str] = Field(default_factory=list)
    valid_days: int = Field(14, description="Quote validity in days")


class QuoteResponse(BaseModel):
    """Generated quote details."""
    id: int
    quote_reference: str
    assessment_id: UUID
    quoted_premium: Decimal
    quoted_line: Optional[Decimal]
    currency: str
    terms: Dict[str, Any]
    conditions: List[str]
    subjectivities: List[str]
    exclusions: List[str]
    valid_from: datetime
    valid_until: datetime
    status: str = Field(
        ...,
        description="draft, issued, accepted, declined, expired"
    )
