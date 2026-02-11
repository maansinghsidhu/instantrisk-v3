"""
InstantRisk V2 - Pydantic Schemas

This module exports all Pydantic schemas for request/response validation.
"""

from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    TokenResponse,
    TokenRefresh
)
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentUpdate,
    AssessmentResponse,
    AssessmentListResponse,
    AssessmentDecisionUpdate
)
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateListResponse,
    TemplateCategoryResponse,
    TemplatePreviewResponse,
    TemplateAutoSelectRequest,
    TemplateAutoSelectResponse,
)
from app.schemas.reference_document import (
    ReferenceDocumentCreate,
    ReferenceDocumentUpdate,
    ReferenceDocumentResponse,
    ReferenceDocumentListResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.schemas.generated_document import (
    DocumentSuggestion,
    DocumentSuggestionResponse,
    GenerationJobCreate,
    GenerationJobProgress,
    GenerationJobResponse,
    GeneratedDocumentCreate,
    GeneratedDocumentUpdate,
    GeneratedDocumentResponse,
    GeneratedDocumentListResponse,
    PrefillRequest,
    PrefillResponse,
    ComplianceReport,
    FinalizeRequest,
    FinalizeResponse,
)
# V3 Lloyd's Market Schemas
from app.schemas.lloyds import (
    # UMR
    UMRCreate,
    UMRResponse,
    # Subscription/Placing
    PlacementCreate,
    PlacementResponse,
    SyndicateLineRequest,
    SyndicateLineResponse,
    SigningSchedule,
    # Exposure
    ExposureByZone,
    ExposureByPeril,
    ExposureDashboard,
    EventAccumulationRequest,
    EventAccumulationResponse,
    # Compliance
    PMDRRequest,
    PMDRResponse,
    RDSScenario,
    RDSResponse,
    ComplianceSubmissionStatus,
    # Data Quality
    DataQualityScore,
    DataQualityIssue,
    DataQualityReport,
    # Integration
    ConnectorConfig,
    ConnectorStatus,
    IngestRequest,
    IngestResponse,
    # Pricing/Quote
    PricingRequest,
    PricingResponse,
    QuoteCreate,
    QuoteResponse,
)

# V3 RBAC Schemas
from app.schemas.rbac import (
    # Permission schemas
    PermissionCreate,
    PermissionResponse,
    PermissionBrief,
    # Role schemas
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleBrief,
    RoleListResponse,
    # Team schemas
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    TeamDetailResponse,
    TeamListResponse,
    TeamMemberBrief,
    # Membership schemas
    TeamMemberAdd,
    TeamMemberUpdate,
    TeamMembershipResponse,
    TeamMembershipListResponse,
    # Permission check schemas
    UserPermissionsResponse,
    PermissionCheckRequest,
    PermissionCheckResponse,
    BulkPermissionCheckRequest,
    BulkPermissionCheckResponse,
)

__all__ = [
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "TokenResponse",
    "TokenRefresh",
    # Assessment
    "AssessmentCreate",
    "AssessmentUpdate",
    "AssessmentResponse",
    "AssessmentListResponse",
    "AssessmentDecisionUpdate",
    # Template
    "TemplateCreate",
    "TemplateUpdate",
    "TemplateResponse",
    "TemplateListResponse",
    "TemplateCategoryResponse",
    "TemplatePreviewResponse",
    "TemplateAutoSelectRequest",
    "TemplateAutoSelectResponse",
    # Reference Document
    "ReferenceDocumentCreate",
    "ReferenceDocumentUpdate",
    "ReferenceDocumentResponse",
    "ReferenceDocumentListResponse",
    "SemanticSearchRequest",
    "SemanticSearchResponse",
    # Generated Document
    "DocumentSuggestion",
    "DocumentSuggestionResponse",
    "GenerationJobCreate",
    "GenerationJobProgress",
    "GenerationJobResponse",
    "GeneratedDocumentCreate",
    "GeneratedDocumentUpdate",
    "GeneratedDocumentResponse",
    "GeneratedDocumentListResponse",
    "PrefillRequest",
    "PrefillResponse",
    "ComplianceReport",
    "FinalizeRequest",
    "FinalizeResponse",
    # V3 Lloyd's Market Schemas
    # UMR
    "UMRCreate",
    "UMRResponse",
    # Subscription/Placing
    "PlacementCreate",
    "PlacementResponse",
    "SyndicateLineRequest",
    "SyndicateLineResponse",
    "SigningSchedule",
    # Exposure
    "ExposureByZone",
    "ExposureByPeril",
    "ExposureDashboard",
    "EventAccumulationRequest",
    "EventAccumulationResponse",
    # Compliance
    "PMDRRequest",
    "PMDRResponse",
    "RDSScenario",
    "RDSResponse",
    "ComplianceSubmissionStatus",
    # Data Quality
    "DataQualityScore",
    "DataQualityIssue",
    "DataQualityReport",
    # Integration
    "ConnectorConfig",
    "ConnectorStatus",
    "IngestRequest",
    "IngestResponse",
    # Pricing/Quote
    "PricingRequest",
    "PricingResponse",
    "QuoteCreate",
    "QuoteResponse",
    # V3 RBAC Schemas
    # Permission schemas
    "PermissionCreate",
    "PermissionResponse",
    "PermissionBrief",
    # Role schemas
    "RoleCreate",
    "RoleUpdate",
    "RoleResponse",
    "RoleBrief",
    "RoleListResponse",
    # Team schemas
    "TeamCreate",
    "TeamUpdate",
    "TeamResponse",
    "TeamDetailResponse",
    "TeamListResponse",
    "TeamMemberBrief",
    # Membership schemas
    "TeamMemberAdd",
    "TeamMemberUpdate",
    "TeamMembershipResponse",
    "TeamMembershipListResponse",
    # Permission check schemas
    "UserPermissionsResponse",
    "PermissionCheckRequest",
    "PermissionCheckResponse",
    "BulkPermissionCheckRequest",
    "BulkPermissionCheckResponse",
]
