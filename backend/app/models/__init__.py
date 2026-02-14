"""
InstantRisk V3 - Database Models

This module exports all SQLAlchemy models for the application.
"""

from app.models.user import User, ApprovalStatus
from app.models.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from app.models.feature_limits import TIER_LIMITS, get_tier_limits, get_feature_access
from app.models.syndicate import Syndicate
from app.models.document import Document
from app.models.assessment import Assessment
from app.models.upload_session import UploadSession
from app.models.template import Template, TemplateFavorite
from app.models.reference_document import ReferenceDocument
from app.models.generated_document import GeneratedDocument, DocumentGenerationJob

# V3 Lloyd's Market Models
from app.models.lloyds import (
    UniqueMarketReference,
    SubscriptionPlacement,
    SyndicateLine,
    PlacementActivityLog,
    ExposureSnapshot,
    ExposureAggregate,
    EventAccumulation,
    DataQualityReport,
    PricingModel,
    PricingResult,
    Quote,
    ComplianceSubmission,
    ComplianceRule,
    AuditLog,
    AIDecisionLog,
    IntegrationConnector,
    IntegrationSyncLog,
)

# V3 RBAC Models
from app.models.rbac import (
    Permission,
    Role,
    Team,
    TeamMembership,
    TeamType,
    UserPermissionCache,
    role_permissions,
)

# V3 Extraction Models
from app.models.extraction import (
    DocumentExtraction,
    ExtractionCorrection,
    TrainingSample,
    ExtractionAccuracyMetric,
    ExtractionPattern,
    ExtractionConfidenceLevel,
    ExtractionStatus,
    CorrectionType,
)

# V3 Exposure Loss/Claims Models
from app.models.exposure_loss import (
    ExposureLoss,
    ExposureClaim,
    LossType,
    ClaimStatus,
)

# V3 Sanctions Screening Models
from app.models.sanctions import (
    SanctionsScreening,
    SanctionsEntity,
    SanctionsAlert,
    ScreeningLevel,
    ScreeningStatus,
)

# Share Link Model
from app.models.share_link import ShareLink

__all__ = [
    # Core models
    "User",
    "ApprovalStatus",
    # Subscription models
    "Subscription",
    "SubscriptionTier",
    "SubscriptionStatus",
    "TIER_LIMITS",
    "get_tier_limits",
    "get_feature_access",
    "Syndicate",
    "Document",
    "Assessment",
    "UploadSession",
    "Template",
    "TemplateFavorite",
    "ReferenceDocument",
    "GeneratedDocument",
    "DocumentGenerationJob",
    # V3 Lloyd's models
    "UniqueMarketReference",
    "SubscriptionPlacement",
    "SyndicateLine",
    "PlacementActivityLog",
    "ExposureSnapshot",
    "ExposureAggregate",
    "EventAccumulation",
    "DataQualityReport",
    "PricingModel",
    "PricingResult",
    "Quote",
    "ComplianceSubmission",
    "ComplianceRule",
    "AuditLog",
    "AIDecisionLog",
    "IntegrationConnector",
    "IntegrationSyncLog",
    # V3 RBAC models
    "Permission",
    "Role",
    "Team",
    "TeamMembership",
    "TeamType",
    "UserPermissionCache",
    "role_permissions",
    # V3 Extraction models
    "DocumentExtraction",
    "ExtractionCorrection",
    "TrainingSample",
    "ExtractionAccuracyMetric",
    "ExtractionPattern",
    "ExtractionConfidenceLevel",
    "ExtractionStatus",
    "CorrectionType",
    # V3 Exposure Loss/Claims models
    "ExposureLoss",
    "ExposureClaim",
    "LossType",
    "ClaimStatus",
    # V3 Sanctions Screening models
    "SanctionsScreening",
    "SanctionsEntity",
    "SanctionsAlert",
    "ScreeningLevel",
    "ScreeningStatus",
    # Share Link model
    "ShareLink",
]

from app.models.chat import ChatMessage, ChatConversation, ChatFeedback

# ClaimSense Claims
from app.models.claims import ClaimRecord, ClaimsSyncLog

# Loss Run Models
from app.models.loss_run import BenchmarkLossRun, InsuredLossRun, LossRunSummary

# pgvector Models (RAG knowledge base, user training docs, reference docs)
from app.models.vector_store import RAGVector, UserDocVector, RefDocVector

# Per-user ML adapter tracking
from app.models.user_model import UserModelAdapter

