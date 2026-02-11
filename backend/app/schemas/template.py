"""
InstantRisk V2 - Template Pydantic Schemas

This module defines Pydantic schemas for template-related
CRUD operations and API responses.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class TemplateFieldDefinition(BaseModel):
    """Schema for a template field definition."""
    name: str
    label: str
    type: str = "text"  # text, number, date, select, textarea
    required: bool = False
    placeholder: Optional[str] = None
    options: Optional[List[str]] = None  # For select fields
    validation: Optional[Dict[str, Any]] = None
    default_value: Optional[Any] = None


class TemplateSectionDefinition(BaseModel):
    """Schema for a template section definition."""
    name: str
    title: str
    fields: List[str] = []  # List of field names in this section
    order: int = 0


class TemplateBase(BaseModel):
    """Base schema with common template fields."""
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    category: str = "custom"
    document_type: str = "other"


class TemplateCreate(TemplateBase):
    """
    Schema for creating a new template.

    Attributes:
        name: Display name of the template.
        description: Description of the template.
        category: Category (lloyds, commercial, specialty, custom).
        document_type: Type of document (slip, policy, certificate, etc.).
        fields: Field definitions for dynamic form.
        sections: Section definitions for document structure.
        tags: Searchable tags.
    """
    template_key: Optional[str] = None  # Auto-generated if not provided
    fields: Dict[str, TemplateFieldDefinition] = {}
    sections: List[TemplateSectionDefinition] = []
    sample_data: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    is_public: bool = False


class TemplateUpdate(BaseModel):
    """Schema for updating an existing template."""
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    document_type: Optional[str] = None
    fields: Optional[Dict[str, Any]] = None
    sections: Optional[List[Dict[str, Any]]] = None
    sample_data: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None


class TemplateResponse(TemplateBase):
    """Schema for template response data."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_key: str
    version: str
    is_system: bool
    created_by: Optional[UUID] = None
    fields: Dict[str, Any] = {}
    sections: List[Dict[str, Any]] = []
    sample_data: Dict[str, Any] = {}
    master_file_path: Optional[str] = None
    is_active: bool
    is_public: bool
    tags: List[str] = []
    use_count: int
    created_at: datetime
    updated_at: datetime
    is_favorite: bool = False  # Computed field


class TemplateListResponse(BaseModel):
    """Schema for paginated template list response."""
    items: List[TemplateResponse]
    total: int
    page: int
    page_size: int
    pages: int


class TemplateCategoryResponse(BaseModel):
    """Schema for template category with counts."""
    category: str
    display_name: str
    count: int
    icon: Optional[str] = None


class TemplatePreviewRequest(BaseModel):
    """Schema for template preview with sample data."""
    template_id: int
    sample_data: Optional[Dict[str, Any]] = None


class TemplatePreviewResponse(BaseModel):
    """Schema for template preview response."""
    template_id: int
    template_name: str
    preview_html: str
    preview_data: Dict[str, Any]
    fields_with_values: Dict[str, Any]
    missing_fields: List[str]


class TemplateAutoSelectRequest(BaseModel):
    """Schema for auto-selecting a template based on assessment."""
    risk_category: str
    document_type: Optional[str] = None
    assessment_id: Optional[str] = None


class TemplateAutoSelectResponse(BaseModel):
    """Schema for auto-select response."""
    recommended_template: Optional[TemplateResponse] = None
    alternatives: List[TemplateResponse] = []
    confidence: float = 0.0
    reason: str = ""


class TemplateImportRequest(BaseModel):
    """Schema for importing a template from file."""
    name: str
    description: Optional[str] = None
    category: str = "custom"
    document_type: str = "other"
    tags: List[str] = []
