"""
InstantRisk V2 - Reference Document Pydantic Schemas

This module defines Pydantic schemas for reference document
operations and API responses.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class ReferenceDocumentBase(BaseModel):
    """Base schema with common reference document fields."""
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None
    category: str = "other"


class ReferenceDocumentCreate(ReferenceDocumentBase):
    """
    Schema for creating a reference document (metadata only).
    File is uploaded separately via multipart form.

    Attributes:
        title: Title/name of the document.
        description: Description of the document content.
        category: Category (policy_wording, guidelines, etc.).
        tags: Searchable tags.
        risk_categories: Related risk categories (property, cyber, etc.).
        jurisdiction: Applicable jurisdiction.
        effective_date: When document became effective.
        expiry_date: When document expires.
    """
    tags: List[str] = []
    risk_categories: List[str] = []
    jurisdiction: Optional[str] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None


class ReferenceDocumentUpdate(BaseModel):
    """Schema for updating a reference document."""
    title: Optional[str] = Field(None, min_length=3, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    risk_categories: Optional[List[str]] = None
    jurisdiction: Optional[str] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    is_active: Optional[bool] = None


class ReferenceDocumentResponse(ReferenceDocumentBase):
    """Schema for reference document response data."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    uploaded_by: UUID
    syndicate_id: Optional[int] = None
    file_path: str
    file_name: str
    file_size: int
    mime_type: Optional[str] = None
    chunk_count: int
    tags: List[str] = []
    risk_categories: List[str] = []
    jurisdiction: Optional[str] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    is_active: bool
    is_verified: bool
    quality_score: Optional[float] = None
    retrieval_count: int
    created_at: datetime
    processed_at: Optional[datetime] = None


class ReferenceDocumentListResponse(BaseModel):
    """Schema for paginated reference document list response."""
    items: List[ReferenceDocumentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ReferenceDocumentCategoryResponse(BaseModel):
    """Schema for reference document category with counts."""
    category: str
    display_name: str
    count: int


class SemanticSearchRequest(BaseModel):
    """Schema for semantic search request."""
    query: str = Field(..., min_length=3, max_length=1000)
    limit: int = Field(5, ge=1, le=20)
    risk_categories: Optional[List[str]] = None
    category: Optional[str] = None
    min_score: float = Field(0.5, ge=0.0, le=1.0)


class SemanticSearchResult(BaseModel):
    """Schema for a single semantic search result."""
    document_id: int
    title: str
    category: str
    chunk_text: str
    similarity_score: float
    file_name: str


class SemanticSearchResponse(BaseModel):
    """Schema for semantic search response."""
    query: str
    results: List[SemanticSearchResult]
    total_results: int
    processing_time_ms: float


class ProcessingStatusResponse(BaseModel):
    """Schema for document processing status."""
    document_id: int
    status: str
    progress_percentage: int = 0
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    chunk_count: int = 0
    quality_score: Optional[float] = None
