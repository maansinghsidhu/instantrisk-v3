"""
InstantRisk V2 - Generated Document Pydantic Schemas

This module defines Pydantic schemas for document generation
operations and API responses.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_serializer


# ===== Document Suggestions =====


class DocumentSuggestion(BaseModel):
    """Schema for a single document suggestion."""

    document_type: str
    template_id: Optional[int] = None
    template_key: str
    template_name: str
    priority: int = Field(1, ge=1, le=5)
    mandatory: bool = False
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    reason: str


class LMAClauseSuggestion(BaseModel):
    """Schema for a suggested LMA clause."""

    id: str
    name: str
    mandatory: bool = False
    category: str
    selected: bool = False
    reason: str
    text_preview: Optional[str] = None


class DocumentSuggestionResponse(BaseModel):
    """Schema for document suggestions from AI."""

    assessment_id: UUID
    risk_category: Optional[str] = None
    decision: Optional[str] = None
    suggested_documents: List[DocumentSuggestion]
    bundle_name: str
    total_estimated_time_seconds: int
    ai_analysis: Optional[Dict[str, Any]] = None
    lma_clauses: Optional[List[LMAClauseSuggestion]] = None


# ===== Generation Job =====


class GenerationJobCreate(BaseModel):
    """Schema for creating a document generation job."""

    document_types: List[str]
    template_ids: Optional[Dict[str, int]] = None  # document_type -> template_id
    use_custom_templates: bool = False
    clause_ids: Optional[List[str]] = None  # Selected LMA clause IDs to include
    language: Optional[str] = None  # Target language code (en, de, fr, etc.)


class GenerationStepProgress(BaseModel):
    """Schema for a single generation step."""

    agent: str
    description: str
    percentage: int
    status: str  # 'pending', 'running', 'completed'


class GenerationJobProgress(BaseModel):
    """Schema for generation job progress update."""

    job_id: str
    status: str
    current_agent: Optional[str] = None
    current_agent_description: Optional[str] = None
    progress_percentage: int = 0
    completed_documents: int = 0
    total_documents: int = 0
    current_document: Optional[str] = None
    estimated_remaining_seconds: Optional[int] = None
    steps: Optional[List[GenerationStepProgress]] = None
    error_message: Optional[str] = None


class GenerationJobResponse(BaseModel):
    """Schema for generation job response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    assessment_id: Any
    status: str
    total_documents: Optional[int] = None
    completed_documents: int = 0
    current_agent: Optional[str] = None
    current_agent_description: Optional[str] = None
    progress_percentage: int = 0
    agent_outputs: Optional[Dict[str, Any]] = None
    document_suggestions: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @field_serializer("assessment_id")
    def serialize_assessment_id(self, v):
        return str(v) if v else None


# ===== Generated Document =====


class GeneratedDocumentBase(BaseModel):
    """Base schema for generated documents."""

    document_type: str
    title: str = Field(..., min_length=3, max_length=500)


class GeneratedDocumentCreate(GeneratedDocumentBase):
    """Schema for creating a generated document."""

    template_id: Optional[int] = None
    draft_content: Dict[str, Any] = {}
    data_mappings: Dict[str, Any] = {}


class GeneratedDocumentUpdate(BaseModel):
    """Schema for updating a generated document."""

    title: Optional[str] = Field(None, min_length=3, max_length=500)
    final_content: Optional[Dict[str, Any]] = None


class GeneratedDocumentResponse(GeneratedDocumentBase):
    """Schema for generated document response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: Any

    @field_serializer("assessment_id")
    def serialize_assessment_id(self, v):
        return str(v) if v else None

    generation_job_id: Optional[str] = None
    template_id: Optional[int] = None
    version: int = 1
    status: str = "draft"
    draft_content: Optional[Dict[str, Any]] = {}
    final_content: Optional[Dict[str, Any]] = {}
    data_mappings: Optional[Dict[str, Any]] = {}
    ai_suggestions: Optional[Dict[str, Any]] = {}
    compliance_report: Optional[Dict[str, Any]] = {}
    placeholders_remaining: int = 0
    ai_confidence: Optional[float] = None
    pdf_path: Optional[str] = None
    pdf_file_name: Optional[str] = None
    generation_method: str = "ai_prefill"
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    finalized_at: Optional[datetime] = None

    # Computed fields
    download_url: Optional[str] = None
    preview_url: Optional[str] = None


class GeneratedDocumentListResponse(BaseModel):
    """Schema for list of generated documents."""

    items: List[GeneratedDocumentResponse]
    total: int


# ===== Prefill =====


class PrefillRequest(BaseModel):
    """Schema for requesting AI prefill data."""

    template_id: int
    include_rag: bool = True  # Use reference documents for enhancement


class PrefillFieldMapping(BaseModel):
    """Schema for a single field mapping."""

    value: Any
    source: str  # assessment, document, computed, rag, manual_required
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    transformation_applied: Optional[str] = None
    requires_review: bool = False
    alternatives: Optional[List[Any]] = None


class PrefillResponse(BaseModel):
    """Schema for AI prefill response."""

    template_id: int
    template_name: str
    field_mappings: Dict[str, PrefillFieldMapping]
    unmapped_fields: List[str]
    data_conflicts: List[Dict[str, Any]]
    completion_percentage: int = Field(0, ge=0, le=100)
    rag_context_used: bool = False
    rag_sources: List[str] = []


# ===== Compliance =====


class ComplianceIssue(BaseModel):
    """Schema for a compliance issue."""

    section: str
    issue: str
    severity: str  # critical, major, minor
    resolution: str


class ComplianceReport(BaseModel):
    """Schema for compliance check report."""

    passed: bool
    score: int = Field(0, ge=0, le=100)
    critical_issues: List[ComplianceIssue] = []
    warnings: List[str] = []
    completeness: Dict[str, Any] = {}
    regulatory_notes: List[str] = []
    approved_for_generation: bool = False
    manual_review_required: bool = False
    review_reason: Optional[str] = None


# ===== Finalize =====


class FinalizeRequest(BaseModel):
    """Schema for finalizing a document to PDF."""

    final_content: Optional[Dict[str, Any]] = None
    include_watermark: bool = False
    include_signatures: bool = True


class FinalizeResponse(BaseModel):
    """Schema for finalize response."""

    document_id: int
    status: str
    pdf_url: str
    pdf_file_name: str
    pdf_file_size: int
    finalized_at: datetime
