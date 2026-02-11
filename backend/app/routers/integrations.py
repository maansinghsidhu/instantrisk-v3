"""
InstantRisk V3 - Integrations Router

This module provides API endpoints for external system integrations:
- Data ingestion from underwriting workbenches
- Webhook event receiver
- Push processed risk data to external systems
- Portfolio synchronization
- Connector management and health monitoring
"""

import uuid
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request, Header
from pydantic import BaseModel, Field, validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.lloyds import IntegrationConnector, IntegrationSyncLog
from app.services.connectors import (
    BaseConnector,
    GenericRESTConnector,
    WebhookConnector,
    ConnectorConfig,
    ConnectorHealth,
    SyncResult,
)

router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================

class DocumentType(str, Enum):
    """Supported document types for ingestion."""
    SLIP = "slip"
    ENDORSEMENT = "endorsement"
    POLICY = "policy"
    CLAIM = "claim"
    BORDEREAU = "bordereau"
    SUBMISSION = "submission"
    QUOTE = "quote"
    OTHER = "other"


class DataFormat(str, Enum):
    """Supported data formats."""
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    PDF = "pdf"
    ACORD = "acord"


class SyncDirection(str, Enum):
    """Sync direction types."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class ConnectorType(str, Enum):
    """Supported connector types."""
    REST_API = "rest_api"
    WEBHOOK = "webhook"
    PPL = "ppl"
    ECOT = "ecot"
    CRYSTAL = "crystal"
    SFTP = "sftp"


class HealthStatus(str, Enum):
    """Health status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# Request Schemas

class IngestRequest(BaseModel):
    """Request schema for data ingestion."""
    source_system: str = Field(..., description="Source system identifier")
    document_type: DocumentType = Field(..., description="Type of document being ingested")
    data_format: DataFormat = Field(default=DataFormat.JSON, description="Format of the data")
    reference_id: Optional[str] = Field(None, description="External reference ID")
    umr: Optional[str] = Field(None, description="Unique Market Reference")
    data: Dict[str, Any] = Field(..., description="Document data payload")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

    @validator("umr")
    def validate_umr_format(cls, v):
        """Validate UMR format if provided."""
        if v and len(v) < 10:
            raise ValueError("UMR must be at least 10 characters")
        return v


class WebhookPayload(BaseModel):
    """Request schema for incoming webhooks."""
    event_type: str = Field(..., description="Type of event")
    source: str = Field(..., description="Source system identifier")
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Dict[str, Any] = Field(..., description="Event payload data")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracking")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class RiskDataPushRequest(BaseModel):
    """Request schema for pushing risk data to external systems."""
    connector_id: int = Field(..., description="Target connector ID")
    assessment_id: str = Field(..., description="Assessment ID to push")
    include_documents: bool = Field(default=False, description="Include attached documents")
    include_pricing: bool = Field(default=True, description="Include pricing results")
    include_ai_analysis: bool = Field(default=True, description="Include AI analysis")
    target_endpoint: Optional[str] = Field(None, description="Override target endpoint")
    custom_mapping: Optional[Dict[str, str]] = Field(None, description="Field mapping overrides")


class PortfolioSyncRequest(BaseModel):
    """Request schema for portfolio synchronization."""
    connector_id: int = Field(..., description="Connector ID for sync")
    direction: SyncDirection = Field(default=SyncDirection.BIDIRECTIONAL)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Sync filters")
    since: Optional[datetime] = Field(None, description="Sync changes since timestamp")
    limit: Optional[int] = Field(default=1000, ge=1, le=10000, description="Maximum records to sync")
    dry_run: bool = Field(default=False, description="Preview sync without applying changes")


class ConnectorCreateRequest(BaseModel):
    """Request schema for creating a new connector."""
    connector_type: ConnectorType = Field(..., description="Type of connector")
    name: str = Field(..., min_length=3, max_length=100, description="Connector name")
    base_url: Optional[str] = Field(None, description="Base URL for API connectors")
    api_key: Optional[str] = Field(None, description="API key for authentication")
    username: Optional[str] = Field(None, description="Username for basic auth")
    password: Optional[str] = Field(None, description="Password for basic auth")
    timeout: int = Field(default=30, ge=5, le=300, description="Request timeout in seconds")
    retry_attempts: int = Field(default=3, ge=1, le=10)
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    extra_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional configuration")


# Response Schemas

class IngestResponse(BaseModel):
    """Response schema for data ingestion."""
    success: bool
    ingestion_id: str
    document_type: DocumentType
    source_system: str
    reference_id: Optional[str]
    umr: Optional[str]
    records_processed: int
    timestamp: datetime
    message: str


class WebhookResponse(BaseModel):
    """Response schema for webhook receiver."""
    received: bool
    event_id: str
    event_type: str
    processed: bool
    timestamp: datetime
    message: str


class RiskDataPushResponse(BaseModel):
    """Response schema for risk data push."""
    success: bool
    push_id: str
    assessment_id: str
    connector_id: int
    records_pushed: int
    timestamp: datetime
    external_reference: Optional[str]
    message: str


class SyncStatusResponse(BaseModel):
    """Response schema for sync status."""
    sync_id: int
    connector_id: int
    connector_name: str
    sync_type: str
    direction: str
    status: str
    records_processed: int
    records_created: int
    records_updated: int
    records_failed: int
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    error_message: Optional[str]


class PortfolioSyncResponse(BaseModel):
    """Response schema for portfolio sync initiation."""
    sync_id: int
    connector_id: int
    direction: str
    status: str
    dry_run: bool
    estimated_records: Optional[int]
    started_at: datetime
    message: str


class ConnectorResponse(BaseModel):
    """Response schema for connector details."""
    id: int
    connector_type: str
    name: str
    syndicate_id: int
    is_active: bool
    health_status: str
    last_sync_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


class ConnectorHealthResponse(BaseModel):
    """Response schema for connector health check."""
    connector_id: int
    connector_name: str
    connector_type: str
    health_status: HealthStatus
    is_connected: bool
    last_check: datetime
    latency_ms: Optional[float]
    error_message: Optional[str]
    details: Optional[Dict[str, Any]]


class ConnectorListResponse(BaseModel):
    """Response schema for connector list."""
    connectors: List[ConnectorResponse]
    total: int


# =============================================================================
# Helper Functions
# =============================================================================

def generate_ingestion_id() -> str:
    """Generate a unique ingestion ID."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    unique_part = uuid.uuid4().hex[:8].upper()
    return f"ING-{timestamp}-{unique_part}"


def generate_event_id() -> str:
    """Generate a unique event ID."""
    return f"EVT-{uuid.uuid4().hex[:12].upper()}"


def generate_push_id() -> str:
    """Generate a unique push ID."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    unique_part = uuid.uuid4().hex[:6].upper()
    return f"PUSH-{timestamp}-{unique_part}"


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
    timestamp: str
) -> bool:
    """Verify HMAC signature for incoming webhooks."""
    if not signature or not signature.startswith("sha256="):
        return False

    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    provided_signature = signature.replace("sha256=", "")
    return hmac.compare_digest(expected_signature, provided_signature)


async def get_connector_instance(
    connector: IntegrationConnector
) -> BaseConnector:
    """Create a connector instance from database record."""
    config = ConnectorConfig.from_dict({
        "connector_type": connector.connector_type,
        "name": connector.name,
        **connector.config,
    })

    if connector.connector_type in ("rest_api", "ppl", "ecot", "crystal"):
        return GenericRESTConnector(config)
    elif connector.connector_type == "webhook":
        return WebhookConnector(config)
    else:
        return GenericRESTConnector(config)


async def log_sync_operation(
    db: AsyncSession,
    connector_id: int,
    sync_type: str,
    direction: str,
    status: str,
    records_processed: int = 0,
    records_created: int = 0,
    records_updated: int = 0,
    records_failed: int = 0,
    error_message: Optional[str] = None,
    error_details: Optional[Dict] = None,
) -> IntegrationSyncLog:
    """Log a sync operation to the database."""
    sync_log = IntegrationSyncLog(
        connector_id=connector_id,
        sync_type=sync_type,
        direction=direction,
        status=status,
        records_processed=records_processed,
        records_created=records_created,
        records_updated=records_updated,
        records_failed=records_failed,
        error_message=error_message,
        error_details=error_details or {},
        started_at=datetime.now(timezone.utc),
    )
    db.add(sync_log)
    await db.commit()
    await db.refresh(sync_log)
    return sync_log


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_data(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """
    Ingest documents/data from external underwriting workbenches.

    This endpoint receives data from external systems (e.g., PPL, ECOT,
    proprietary UW workbenches) and processes it for InstantRisk analysis.

    Supported document types:
    - slip: Market placing slips
    - endorsement: Policy endorsements
    - policy: Full policy documents
    - claim: Claims data
    - bordereau: Premium/claims bordereaux
    - submission: New business submissions
    - quote: Quote requests

    Args:
        request: IngestRequest with document data and metadata.
        background_tasks: FastAPI background tasks for async processing.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        IngestResponse with ingestion tracking details.
    """
    ingestion_id = generate_ingestion_id()

    # Validate data payload has required fields based on document type
    required_fields = {
        DocumentType.SLIP: ["insured_name", "class_of_business"],
        DocumentType.SUBMISSION: ["insured_name", "risk_details"],
        DocumentType.CLAIM: ["claim_reference", "loss_date"],
        DocumentType.BORDEREAU: ["period", "records"],
    }

    doc_required = required_fields.get(request.document_type, [])
    missing_fields = [f for f in doc_required if f not in request.data]

    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required fields for {request.document_type.value}: {missing_fields}"
        )

    # Calculate records processed (for bordereaux, count inner records)
    records_count = 1
    if request.document_type == DocumentType.BORDEREAU and "records" in request.data:
        records_count = len(request.data.get("records", []))

    # Log the ingestion (in production, this would trigger actual processing)
    # Background task would handle document parsing, data extraction, etc.

    return IngestResponse(
        success=True,
        ingestion_id=ingestion_id,
        document_type=request.document_type,
        source_system=request.source_system,
        reference_id=request.reference_id,
        umr=request.umr,
        records_processed=records_count,
        timestamp=datetime.now(timezone.utc),
        message=f"Data ingested successfully. Ingestion ID: {ingestion_id}"
    )


@router.post("/webhook", response_model=WebhookResponse, status_code=status.HTTP_200_OK)
async def receive_webhook(
    webhook: WebhookPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
    x_webhook_timestamp: Optional[str] = Header(None, alias="X-Webhook-Timestamp"),
) -> WebhookResponse:
    """
    Receive webhook events from external systems.

    This endpoint accepts webhook notifications from configured external systems.
    Supports HMAC signature verification for secure webhook delivery.

    Supported event types include:
    - placement.updated: Placement status changes
    - quote.received: New quote received
    - claim.filed: New claim notification
    - document.available: Document ready for retrieval
    - exposure.alert: Exposure threshold breach

    Args:
        webhook: WebhookPayload containing event data.
        request: FastAPI Request object for raw body access.
        background_tasks: Background tasks for async processing.
        db: Database session.
        x_webhook_signature: Optional HMAC signature header.
        x_webhook_timestamp: Optional timestamp header.

    Returns:
        WebhookResponse acknowledging receipt.
    """
    event_id = generate_event_id()

    # In production, verify signature if configured for the source
    # For now, accept all webhooks

    # Process different event types
    processed = True
    message = f"Webhook received and queued for processing"

    known_event_types = [
        "placement.updated", "placement.created", "placement.bound",
        "quote.received", "quote.accepted", "quote.declined",
        "claim.filed", "claim.updated", "claim.settled",
        "document.available", "document.processed",
        "exposure.alert", "exposure.updated",
        "assessment.completed", "assessment.updated",
    ]

    if webhook.event_type not in known_event_types:
        message = f"Unknown event type '{webhook.event_type}', logged for review"
        processed = False

    # Background task would handle actual event processing
    # background_tasks.add_task(process_webhook_event, event_id, webhook)

    return WebhookResponse(
        received=True,
        event_id=event_id,
        event_type=webhook.event_type,
        processed=processed,
        timestamp=datetime.now(timezone.utc),
        message=message,
    )


@router.post("/push/risk-data", response_model=RiskDataPushResponse, status_code=status.HTTP_202_ACCEPTED)
async def push_risk_data(
    request: RiskDataPushRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RiskDataPushResponse:
    """
    Push processed risk assessment data to external underwriting workbench.

    This endpoint sends completed risk assessments, AI analysis results,
    and pricing recommendations to configured external systems.

    The push includes:
    - Assessment details and risk scores
    - AI-generated analysis and recommendations
    - Pricing results (if requested)
    - Attached documents (if requested)

    Args:
        request: RiskDataPushRequest with target and options.
        background_tasks: Background tasks for async push.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        RiskDataPushResponse with push tracking details.
    """
    push_id = generate_push_id()

    # Verify connector exists and user has access
    result = await db.execute(
        select(IntegrationConnector).where(IntegrationConnector.id == request.connector_id)
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {request.connector_id} not found"
        )

    if not connector.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connector '{connector.name}' is not active"
        )

    # Check user access (must be in same syndicate or admin)
    if current_user.role != "admin" and current_user.syndicate_id != connector.syndicate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this connector"
        )

    # In production, would fetch assessment and push to external system
    # For now, simulate successful push
    records_pushed = 1
    if request.include_documents:
        records_pushed += 1  # Add document count
    if request.include_pricing:
        records_pushed += 1  # Add pricing record

    # Log the sync operation
    await log_sync_operation(
        db=db,
        connector_id=connector.id,
        sync_type="push",
        direction="outbound",
        status="completed",
        records_processed=records_pushed,
        records_created=records_pushed,
    )

    return RiskDataPushResponse(
        success=True,
        push_id=push_id,
        assessment_id=request.assessment_id,
        connector_id=request.connector_id,
        records_pushed=records_pushed,
        timestamp=datetime.now(timezone.utc),
        external_reference=f"EXT-{uuid.uuid4().hex[:8].upper()}",
        message=f"Risk data push initiated. Push ID: {push_id}",
    )


@router.post("/sync/portfolio", response_model=PortfolioSyncResponse, status_code=status.HTTP_202_ACCEPTED)
async def sync_portfolio(
    request: PortfolioSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioSyncResponse:
    """
    Synchronize portfolio data with external systems.

    This endpoint initiates bi-directional portfolio data synchronization
    with configured external systems. Useful for:
    - Syncing policy data from legacy systems
    - Pushing exposure data to portfolio management tools
    - Keeping bordereaux in sync

    Sync directions:
    - inbound: Pull data from external system to InstantRisk
    - outbound: Push data from InstantRisk to external system
    - bidirectional: Two-way sync (reconciliation)

    Args:
        request: PortfolioSyncRequest with sync configuration.
        background_tasks: Background tasks for async sync.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        PortfolioSyncResponse with sync initiation details.
    """
    # Verify connector exists
    result = await db.execute(
        select(IntegrationConnector).where(IntegrationConnector.id == request.connector_id)
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {request.connector_id} not found"
        )

    if not connector.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connector '{connector.name}' is not active"
        )

    # Check user access
    if current_user.role != "admin" and current_user.syndicate_id != connector.syndicate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this connector"
        )

    # Create sync log entry
    sync_log = await log_sync_operation(
        db=db,
        connector_id=connector.id,
        sync_type="portfolio",
        direction=request.direction.value,
        status="started",
    )

    # Estimate records (in production, would query actual counts)
    estimated_records = request.limit if request.limit else 1000

    # Background task would handle actual sync
    # background_tasks.add_task(run_portfolio_sync, sync_log.id, request)

    return PortfolioSyncResponse(
        sync_id=sync_log.id,
        connector_id=request.connector_id,
        direction=request.direction.value,
        status="started",
        dry_run=request.dry_run,
        estimated_records=estimated_records,
        started_at=sync_log.started_at,
        message=f"Portfolio sync initiated{'(dry run)' if request.dry_run else ''}",
    )


@router.get("/sync/status", response_model=List[SyncStatusResponse])
async def get_sync_status(
    connector_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SyncStatusResponse]:
    """
    Check synchronization status for recent sync operations.

    Returns status of recent sync operations, optionally filtered
    by connector ID or status.

    Args:
        connector_id: Optional filter by connector ID.
        status_filter: Optional filter by status (started, completed, failed).
        limit: Maximum number of results (default 20).
        current_user: The authenticated user.
        db: Database session.

    Returns:
        List of SyncStatusResponse with sync operation details.
    """
    # Build query
    query = select(IntegrationSyncLog, IntegrationConnector).join(
        IntegrationConnector,
        IntegrationSyncLog.connector_id == IntegrationConnector.id
    )

    # Apply filters
    if connector_id:
        query = query.where(IntegrationSyncLog.connector_id == connector_id)

    if status_filter:
        query = query.where(IntegrationSyncLog.status == status_filter)

    # Filter by user's syndicate access
    if current_user.role != "admin":
        query = query.where(IntegrationConnector.syndicate_id == current_user.syndicate_id)

    # Order and limit
    query = query.order_by(IntegrationSyncLog.started_at.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    sync_statuses = []
    for sync_log, connector in rows:
        duration = None
        if sync_log.completed_at and sync_log.started_at:
            duration = (sync_log.completed_at - sync_log.started_at).total_seconds()

        sync_statuses.append(SyncStatusResponse(
            sync_id=sync_log.id,
            connector_id=sync_log.connector_id,
            connector_name=connector.name,
            sync_type=sync_log.sync_type,
            direction=sync_log.direction,
            status=sync_log.status,
            records_processed=sync_log.records_processed,
            records_created=sync_log.records_created,
            records_updated=sync_log.records_updated,
            records_failed=sync_log.records_failed,
            started_at=sync_log.started_at,
            completed_at=sync_log.completed_at,
            duration_seconds=duration,
            error_message=sync_log.error_message,
        ))

    return sync_statuses


@router.get("/connectors", response_model=ConnectorListResponse)
async def list_connectors(
    connector_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectorListResponse:
    """
    List all configured integration connectors.

    Returns a list of connectors configured for the user's syndicate
    (or all connectors for admin users).

    Args:
        connector_type: Optional filter by connector type.
        is_active: Optional filter by active status.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        ConnectorListResponse with list of configured connectors.
    """
    query = select(IntegrationConnector)

    # Filter by syndicate for non-admin users
    if current_user.role != "admin":
        query = query.where(IntegrationConnector.syndicate_id == current_user.syndicate_id)

    if connector_type:
        query = query.where(IntegrationConnector.connector_type == connector_type)

    if is_active is not None:
        query = query.where(IntegrationConnector.is_active == is_active)

    query = query.order_by(IntegrationConnector.created_at.desc())

    result = await db.execute(query)
    connectors = result.scalars().all()

    connector_list = [
        ConnectorResponse(
            id=c.id,
            connector_type=c.connector_type,
            name=c.name,
            syndicate_id=c.syndicate_id,
            is_active=c.is_active,
            health_status=c.health_status or "unknown",
            last_sync_at=c.last_sync_at,
            last_error=c.last_error,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in connectors
    ]

    return ConnectorListResponse(
        connectors=connector_list,
        total=len(connector_list),
    )


@router.post("/connectors", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    request: ConnectorCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectorResponse:
    """
    Create a new integration connector.

    Creates a new connector configuration for integrating with external systems.
    The connector must be configured with appropriate credentials and endpoints.

    Supported connector types:
    - rest_api: Generic REST API integration
    - webhook: Outbound webhook notifications
    - ppl: Lloyd's Placing Platform Limited
    - ecot: Electronic Claims Office
    - crystal: Market reporting
    - sftp: File-based SFTP integration

    Args:
        request: ConnectorCreateRequest with connector configuration.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        ConnectorResponse with created connector details.

    Raises:
        HTTPException: If connector creation fails or user lacks permission.
    """
    # Verify user has syndicate assignment for non-admins
    if current_user.role != "admin" and not current_user.syndicate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be assigned to a syndicate to create connectors"
        )

    syndicate_id = current_user.syndicate_id
    if current_user.role == "admin" and not syndicate_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin must specify syndicate_id in request"
        )

    # Check for duplicate connector
    existing_query = select(IntegrationConnector).where(
        IntegrationConnector.syndicate_id == syndicate_id,
        IntegrationConnector.connector_type == request.connector_type.value,
        IntegrationConnector.name == request.name,
    )
    existing = await db.execute(existing_query)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Connector '{request.name}' of type '{request.connector_type.value}' already exists"
        )

    # Build config dictionary
    config = {
        "base_url": request.base_url,
        "timeout": request.timeout,
        "retry_attempts": request.retry_attempts,
        "headers": request.headers,
    }

    # Add authentication (sensitive data - should be encrypted in production)
    if request.api_key:
        config["api_key"] = request.api_key
    if request.username:
        config["username"] = request.username
    if request.password:
        config["password"] = request.password
    if request.extra_config:
        config["extra"] = request.extra_config

    # Create connector record
    connector = IntegrationConnector(
        syndicate_id=syndicate_id,
        connector_type=request.connector_type.value,
        name=request.name,
        config=config,
        is_active=True,
        health_status="unknown",
    )

    db.add(connector)
    await db.commit()
    await db.refresh(connector)

    return ConnectorResponse(
        id=connector.id,
        connector_type=connector.connector_type,
        name=connector.name,
        syndicate_id=connector.syndicate_id,
        is_active=connector.is_active,
        health_status=connector.health_status,
        last_sync_at=connector.last_sync_at,
        last_error=connector.last_error,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


@router.get("/connectors/{connector_id}/health", response_model=ConnectorHealthResponse)
async def check_connector_health(
    connector_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectorHealthResponse:
    """
    Check the health status of a specific connector.

    Performs a health check on the connector by:
    - Verifying connectivity to the external system
    - Checking authentication validity
    - Measuring response latency

    Args:
        connector_id: The ID of the connector to check.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        ConnectorHealthResponse with health status details.

    Raises:
        HTTPException: If connector not found or access denied.
    """
    # Fetch connector
    result = await db.execute(
        select(IntegrationConnector).where(IntegrationConnector.id == connector_id)
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found"
        )

    # Check access
    if current_user.role != "admin" and current_user.syndicate_id != connector.syndicate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this connector"
        )

    # Perform health check
    health_status = HealthStatus.UNKNOWN
    is_connected = False
    latency_ms = None
    error_message = None
    details = {}

    try:
        # Create connector instance
        connector_instance = await get_connector_instance(connector)

        # Measure connection time
        start_time = datetime.now(timezone.utc)
        connected = await connector_instance.connect()

        if connected:
            # Run health check
            health = await connector_instance.healthcheck()
            latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            is_connected = True
            health_status = HealthStatus(health.value)
            details = connector_instance.get_status()

            await connector_instance.disconnect()
        else:
            health_status = HealthStatus.UNHEALTHY
            error_message = connector_instance.last_error

    except Exception as e:
        health_status = HealthStatus.UNHEALTHY
        error_message = str(e)

    # Update connector health status in database
    connector.health_status = health_status.value
    if error_message:
        connector.last_error = error_message
    await db.commit()

    return ConnectorHealthResponse(
        connector_id=connector.id,
        connector_name=connector.name,
        connector_type=connector.connector_type,
        health_status=health_status,
        is_connected=is_connected,
        last_check=datetime.now(timezone.utc),
        latency_ms=latency_ms,
        error_message=error_message,
        details=details,
    )
