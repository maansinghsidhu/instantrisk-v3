"""
InstantRisk V3 - Lloyd's Market Models

This module defines models for Lloyd's market operations:
- UMR (Unique Market Reference) tracking
- Subscription placements and syndicate lines
- Exposure monitoring
- Data quality reports
- Pricing models and quotes
- Audit logging
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float,
    Text, JSON, ForeignKey, DECIMAL, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID as PgUUID
from sqlalchemy.orm import relationship

from app.core.database import Base


# =============================================================================
# UMR (Unique Market Reference) Management
# =============================================================================

class UniqueMarketReference(Base):
    """
    Tracks Lloyd's Unique Market References (UMRs).

    UMR Format: B0999ABCDEF001
    - B0999: Broker code (assigned by Lloyd's)
    - 26: Year (last 2 digits)
    - XXXXXX: Sequence number
    """
    __tablename__ = "unique_market_references"

    id = Column(Integer, primary_key=True, index=True)
    umr = Column(String(20), unique=True, nullable=False, index=True)
    broker_code = Column(String(10), nullable=False, index=True)
    year = Column(String(2), nullable=False)
    sequence = Column(Integer, nullable=False)

    # Link to assessment
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=True)

    # Risk metadata
    risk_type = Column(String(50), nullable=True)
    class_of_business = Column(String(100), nullable=True)

    # Status tracking
    status = Column(String(20), default="active")  # active, placed, expired, cancelled

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    assessment = relationship("Assessment", backref="umr")
    placements = relationship("SubscriptionPlacement", back_populates="umr_ref")

    __table_args__ = (
        Index("idx_umr_broker_year", "broker_code", "year"),
        UniqueConstraint("broker_code", "year", "sequence", name="uq_broker_year_sequence"),
    )

    def __repr__(self):
        return f"<UMR({self.umr})>"


# =============================================================================
# Subscription Market Workflow
# =============================================================================

class SubscriptionPlacement(Base):
    """
    Tracks subscription market placements across multiple syndicates.
    """
    __tablename__ = "subscription_placements"

    id = Column(Integer, primary_key=True, index=True)
    umr = Column(String(20), ForeignKey("unique_market_references.umr"), nullable=False, index=True)

    # Lead underwriter
    lead_syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=False)
    lead_underwriter_name = Column(String(255), nullable=True)

    # Placement progress
    total_line = Column(DECIMAL(5, 2), default=0)  # Total % placed
    target_line = Column(DECIMAL(5, 2), default=100)  # Target %
    minimum_lead_line = Column(DECIMAL(5, 2), default=25)  # Minimum lead line %

    # Status
    status = Column(String(20), default="marketing")
    # marketing, quoting, placing, bound, declined, expired

    # Financial
    gross_premium = Column(DECIMAL(18, 2), nullable=True)
    currency = Column(String(3), default="GBP")

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    quote_deadline = Column(DateTime(timezone=True), nullable=True)
    placed_at = Column(DateTime(timezone=True), nullable=True)
    inception_date = Column(DateTime(timezone=True), nullable=True)
    expiry_date = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    umr_ref = relationship("UniqueMarketReference", back_populates="placements")
    lead_syndicate = relationship("Syndicate", backref="lead_placements")
    lines = relationship("SyndicateLine", back_populates="placement", cascade="all, delete-orphan")
    activity_log = relationship("PlacementActivityLog", back_populates="placement", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Placement(umr={self.umr}, status={self.status}, line={self.total_line}%)>"


class SyndicateLine(Base):
    """
    Tracks individual syndicate participation in a placement.
    """
    __tablename__ = "syndicate_lines"

    id = Column(Integer, primary_key=True, index=True)
    placement_id = Column(Integer, ForeignKey("subscription_placements.id"), nullable=False)
    syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=False)

    # Syndicate identification
    syndicate_number = Column(String(10), nullable=True)  # e.g., "1234"
    syndicate_name = Column(String(255), nullable=True)

    # Line details
    line_percentage = Column(DECIMAL(5, 2), nullable=False)  # Quoted/written line
    signed_line = Column(DECIMAL(5, 2), nullable=True)  # After signing
    order_percentage = Column(DECIMAL(5, 2), nullable=True)  # Order %

    # Status
    status = Column(String(20), default="quoted")
    # quoted, written, signed, declined, scratched

    # Conditions
    conditions = Column(Text, nullable=True)
    subjectivities = Column(ARRAY(String), default=list)

    # Quote reference
    quote_reference = Column(String(50), nullable=True)

    # Timestamps
    quoted_at = Column(DateTime(timezone=True), nullable=True)
    written_at = Column(DateTime(timezone=True), nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    placement = relationship("SubscriptionPlacement", back_populates="lines")
    syndicate = relationship("Syndicate", backref="lines")

    __table_args__ = (
        UniqueConstraint("placement_id", "syndicate_id", name="uq_placement_syndicate"),
    )

    def __repr__(self):
        return f"<SyndicateLine(syndicate={self.syndicate_number}, line={self.line_percentage}%)>"


class PlacementActivityLog(Base):
    """
    Audit log for placement activities.
    """
    __tablename__ = "placement_activity_log"

    id = Column(Integer, primary_key=True, index=True)
    placement_id = Column(Integer, ForeignKey("subscription_placements.id"), nullable=False)

    # Activity details
    action = Column(String(50), nullable=False)
    # line_quoted, line_written, line_signed, subjectivity_cleared, status_changed

    actor_id = Column(Integer, nullable=True)
    actor_type = Column(String(20), nullable=True)  # broker, underwriter, system
    actor_name = Column(String(255), nullable=True)

    # Details
    details = Column(JSONB, default=dict)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    placement = relationship("SubscriptionPlacement", back_populates="activity_log")


# =============================================================================
# Exposure Monitoring
# =============================================================================

class ExposureSnapshot(Base):
    """
    Time-series exposure data for portfolio monitoring.
    Consider using TimescaleDB hypertable for production.
    """
    __tablename__ = "exposure_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=False, index=True)

    # Dimensions
    class_of_business = Column(String(50), nullable=True)
    geographic_zone = Column(String(20), nullable=True)  # NA, EU, APAC, LATAM, etc.
    peril = Column(String(50), nullable=True)  # windstorm, earthquake, flood, cyber, etc.
    country = Column(String(3), nullable=True)  # ISO country code

    # Exposure metrics
    gross_exposure = Column(DECIMAL(18, 2), default=0)
    net_exposure = Column(DECIMAL(18, 2), default=0)
    reinsurance_recovery = Column(DECIMAL(18, 2), default=0)

    # PML estimates
    pml_100yr = Column(DECIMAL(18, 2), nullable=True)
    pml_250yr = Column(DECIMAL(18, 2), nullable=True)

    # Policy count
    policy_count = Column(Integer, default=0)

    # Relationships
    syndicate = relationship("Syndicate", backref="exposure_snapshots")

    __table_args__ = (
        Index("idx_exposure_syndicate_time", "syndicate_id", "timestamp"),
        Index("idx_exposure_zone_peril", "geographic_zone", "peril"),
    )


class ExposureAggregate(Base):
    """
    Pre-aggregated exposure data for dashboard performance.
    """
    __tablename__ = "exposure_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=False, index=True)

    # Aggregation type
    aggregation_type = Column(String(20), nullable=False)  # zone, peril, class, total
    aggregation_key = Column(String(100), nullable=False)

    # Current values
    current_exposure = Column(DECIMAL(18, 2), default=0)
    limit = Column(DECIMAL(18, 2), nullable=True)
    utilization_pct = Column(DECIMAL(5, 2), default=0)

    # Trends
    trend_7d = Column(DECIMAL(5, 2), nullable=True)  # % change
    trend_30d = Column(DECIMAL(5, 2), nullable=True)

    # Timestamp
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("syndicate_id", "aggregation_type", "aggregation_key", name="uq_exposure_agg"),
    )


class EventAccumulation(Base):
    """
    Tracks exposure accumulation for specific events (e.g., hurricanes).
    """
    __tablename__ = "event_accumulations"

    id = Column(Integer, primary_key=True, index=True)

    # Event identification
    event_id = Column(String(50), nullable=False, index=True)  # HURRICANE_2026_01
    event_name = Column(String(200), nullable=False)
    event_type = Column(String(50), nullable=False)  # hurricane, earthquake, cyber_event
    region = Column(String(50), nullable=True)

    # Syndicate
    syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=False)

    # Accumulation
    gross_exposure = Column(DECIMAL(18, 2), default=0)
    net_exposure = Column(DECIMAL(18, 2), default=0)
    policies_affected = Column(Integer, default=0)

    # Calculation metadata
    last_calculated = Column(DateTime(timezone=True), nullable=True)
    calculation_method = Column(String(50), nullable=True)

    # Relationships
    syndicate = relationship("Syndicate", backref="event_accumulations")


# =============================================================================
# Data Quality
# =============================================================================

class DataQualityReport(Base):
    """
    Stores data quality assessment results for submissions.
    """
    __tablename__ = "data_quality_reports"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False, index=True)

    # Overall score (0-100)
    overall_score = Column(Float, nullable=False)

    # Dimension scores (0-100)
    completeness_score = Column(Float, nullable=True)
    accuracy_score = Column(Float, nullable=True)
    consistency_score = Column(Float, nullable=True)
    timeliness_score = Column(Float, nullable=True)
    validity_score = Column(Float, nullable=True)

    # Issues found
    issues = Column(JSONB, default=dict)  # {field: issue_description}
    issue_count = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)

    # Corrections applied
    corrections = Column(JSONB, default=dict)  # {field: {old, new, confidence}}
    auto_corrected_count = Column(Integer, default=0)

    # Suggestions
    suggestions = Column(JSONB, default=list)

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    assessment = relationship("Assessment", backref="quality_reports")


# =============================================================================
# Pricing & Quotes
# =============================================================================

class PricingModel(Base):
    """
    Stores pricing model configurations.
    """
    __tablename__ = "pricing_models"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(20), default="1.0")

    # Classification
    class_of_business = Column(String(50), nullable=True)
    model_type = Column(String(50), nullable=False)  # glm, xgboost, neural, rule_based

    # Model configuration
    parameters = Column(JSONB, default=dict)
    features = Column(ARRAY(String), default=list)

    # Performance
    performance_metrics = Column(JSONB, default=dict)  # {r2, mae, mape}

    # Status
    is_active = Column(Boolean, default=True)
    trained_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))


class PricingResult(Base):
    """
    Stores pricing calculation results.
    """
    __tablename__ = "pricing_results"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False, index=True)
    model_id = Column(Integer, ForeignKey("pricing_models.id"), nullable=True)

    # Pricing output
    technical_premium = Column(DECIMAL(18, 2), nullable=False)
    currency = Column(String(3), default="GBP")

    # Risk assessment
    risk_score = Column(Float, nullable=True)  # 0-100
    risk_category = Column(String(20), nullable=True)  # low, medium, high, very_high

    # Confidence
    confidence_interval_low = Column(DECIMAL(18, 2), nullable=True)
    confidence_interval_high = Column(DECIMAL(18, 2), nullable=True)

    # Loading factors
    loading_factors = Column(JSONB, default=dict)
    # {cat_load, expense_load, profit_margin, etc.}

    # Explanation
    explanation = Column(JSONB, default=dict)
    key_drivers = Column(ARRAY(String), default=list)

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    assessment = relationship("Assessment", backref="pricing_results")
    model = relationship("PricingModel", backref="results")


class Quote(Base):
    """
    Formal quotes generated from pricing.
    """
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False)
    pricing_result_id = Column(Integer, ForeignKey("pricing_results.id"), nullable=True)
    syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=True)

    # Quote identification
    quote_reference = Column(String(50), unique=True, nullable=False, index=True)

    # Pricing
    quoted_premium = Column(DECIMAL(18, 2), nullable=False)
    currency = Column(String(3), default="GBP")
    quoted_line = Column(DECIMAL(5, 2), nullable=True)  # % line offered

    # Terms
    terms = Column(JSONB, default=dict)
    conditions = Column(ARRAY(String), default=list)
    subjectivities = Column(ARRAY(String), default=list)
    exclusions = Column(ARRAY(String), default=list)

    # Validity
    valid_from = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    valid_until = Column(DateTime(timezone=True), nullable=True)

    # Status
    status = Column(String(20), default="draft")
    # draft, issued, accepted, declined, expired, superseded

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    issued_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    assessment = relationship("Assessment", backref="quotes")
    pricing_result = relationship("PricingResult", backref="quotes")
    syndicate = relationship("Syndicate", backref="quotes")


# =============================================================================
# Compliance
# =============================================================================

class ComplianceSubmission(Base):
    """
    Tracks regulatory compliance submissions.
    """
    __tablename__ = "compliance_submissions"

    id = Column(Integer, primary_key=True, index=True)
    syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=False, index=True)

    # Submission type
    submission_type = Column(String(50), nullable=False)  # PMDR, RDS, QRT, SCR
    period = Column(String(20), nullable=False)  # 2026-Q1, 2026-H1, 2026

    # Data
    data = Column(JSONB, nullable=False)

    # Validation
    validation_errors = Column(JSONB, default=list)
    validation_warnings = Column(JSONB, default=list)
    is_valid = Column(Boolean, default=False)

    # Status
    status = Column(String(20), default="draft")
    # draft, validated, submitted, accepted, rejected

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    validated_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    # Response
    submission_reference = Column(String(100), nullable=True)
    response_data = Column(JSONB, default=dict)

    # Relationships
    syndicate = relationship("Syndicate", backref="compliance_submissions")


class ComplianceRule(Base):
    """
    Stores compliance validation rules.
    """
    __tablename__ = "compliance_rules"

    id = Column(Integer, primary_key=True, index=True)

    # Rule identification
    regulation = Column(String(50), nullable=False)  # PMDR, RDS, SOLVENCY_II
    rule_code = Column(String(50), nullable=False, index=True)

    # Description
    description = Column(Text, nullable=True)

    # Validation
    validation_logic = Column(Text, nullable=True)  # Python expression or JSON schema
    field_path = Column(String(200), nullable=True)  # Field to validate

    # Severity
    severity = Column(String(20), default="error")  # error, warning, info

    # Status
    is_active = Column(Boolean, default=True)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("regulation", "rule_code", name="uq_compliance_rule"),
    )


# =============================================================================
# Audit Logging
# =============================================================================

class AuditLog(Base):
    """
    Comprehensive audit trail for all system actions.
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    # Actor
    user_id = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    user_email = Column(String(255), nullable=True)

    # Action
    action = Column(String(100), nullable=False, index=True)
    # create_assessment, update_placement, generate_quote, etc.

    # Entity
    entity_type = Column(String(50), nullable=True, index=True)
    entity_id = Column(String(100), nullable=True)

    # Changes
    old_values = Column(JSONB, default=dict)
    new_values = Column(JSONB, default=dict)

    # Context
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(100), nullable=True)

    # Relationships
    user = relationship("User", backref="audit_logs")

    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_user_time", "user_id", "timestamp"),
    )


class AIDecisionLog(Base):
    """
    Audit trail for AI/ML decisions for explainability.
    """
    __tablename__ = "ai_decision_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    # AI agent info
    agent_name = Column(String(100), nullable=False, index=True)
    agent_version = Column(String(20), nullable=True)
    model_name = Column(String(100), nullable=True)

    # Decision context
    decision_type = Column(String(100), nullable=False)
    # risk_assessment, pricing, document_classification, etc.

    # Assessment link
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=True)

    # Input/Output
    input_data = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)

    # Confidence and reasoning
    confidence_score = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    key_factors = Column(ARRAY(String), default=list)

    # Human override
    human_override = Column(Boolean, default=False)
    override_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    override_reason = Column(Text, nullable=True)
    override_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    assessment = relationship("Assessment", backref="ai_decisions")
    override_user = relationship("User", foreign_keys=[override_by])

    __table_args__ = (
        Index("idx_ai_decision_assessment", "assessment_id"),
        Index("idx_ai_decision_agent", "agent_name", "timestamp"),
    )


# =============================================================================
# Integration / Connectors
# =============================================================================

class IntegrationConnector(Base):
    """
    Stores connector configurations for external system integration.
    """
    __tablename__ = "integration_connectors"

    id = Column(Integer, primary_key=True, index=True)
    syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=False)

    # Connector identification
    connector_type = Column(String(50), nullable=False)
    # ppl, ecot, crystal, rest_api, webhook, sftp
    name = Column(String(100), nullable=False)

    # Configuration (encrypted in production)
    config = Column(JSONB, nullable=False, default=dict)
    # {base_url, api_key, credentials, etc.}

    # Status
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    # Health
    health_status = Column(String(20), default="unknown")
    # healthy, degraded, unhealthy, unknown

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    syndicate = relationship("Syndicate", backref="connectors")

    __table_args__ = (
        UniqueConstraint("syndicate_id", "connector_type", "name", name="uq_connector"),
    )


class IntegrationSyncLog(Base):
    """
    Tracks data sync operations with external systems.
    """
    __tablename__ = "integration_sync_log"

    id = Column(Integer, primary_key=True, index=True)
    connector_id = Column(Integer, ForeignKey("integration_connectors.id"), nullable=False)

    # Sync details
    sync_type = Column(String(20), nullable=False)  # inbound, outbound, bidirectional
    direction = Column(String(10), nullable=False)  # push, pull

    # Status
    status = Column(String(20), nullable=False)  # started, completed, failed

    # Metrics
    records_processed = Column(Integer, default=0)
    records_created = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, default=dict)

    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    connector = relationship("IntegrationConnector", backref="sync_logs")
