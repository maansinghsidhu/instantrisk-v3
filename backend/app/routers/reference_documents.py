"""
Reference Documents Router - Training Documents for RAG

Endpoints for uploading and managing reference documents
used for AI-enhanced document generation.
"""

import os
import uuid
import hashlib
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.reference_document import (
    ReferenceDocumentCreate,
    ReferenceDocumentUpdate,
    ReferenceDocumentResponse,
    ReferenceDocumentListResponse,
    ReferenceDocumentCategoryResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResult,
    ProcessingStatusResponse
)
from app.services.reference_document_service import reference_document_service
from app.config import settings

router = APIRouter()

# Upload directory
UPLOAD_DIR = os.path.join(settings.upload_dir, "reference_docs")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=ReferenceDocumentResponse)
async def upload_reference_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    category: str = Form("other"),
    tags: Optional[str] = Form(None),  # Comma-separated
    risk_categories: Optional[str] = Form(None),  # Comma-separated
    jurisdiction: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a reference document for training/RAG.

    The document will be processed in the background:
    1. OCR text extraction
    2. Text chunking
    3. Vector embedding
    4. Storage in Qdrant

    Args:
        file: The document file (PDF, DOCX, TXT)
        title: Document title
        description: Optional description
        category: Category (policy_wording, guidelines, previous_contracts, etc.)
        tags: Comma-separated tags
        risk_categories: Comma-separated risk categories
        jurisdiction: Applicable jurisdiction
    """
    # Validate file type
    allowed_types = ["application/pdf", "text/plain",
                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                     "application/msword"]
    if file.content_type not in allowed_types:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    # Save file
    file_ext = os.path.splitext(file.filename)[1] or ".pdf"
    unique_name = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    content = await file.read()
    file_size = len(content)

    with open(file_path, "wb") as f:
        f.write(content)

    # Parse tags and risk_categories
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    risk_list = [r.strip() for r in risk_categories.split(",")] if risk_categories else []

    # Create database record
    doc = await reference_document_service.create_document(
        db=db,
        user_id=current_user.id,
        title=title,
        description=description,
        category=category,
        file_path=file_path,
        file_name=file.filename,
        file_size=file_size,
        mime_type=file.content_type,
        tags=tag_list,
        risk_categories=risk_list,
        jurisdiction=jurisdiction
    )

    # Process in background (OCR + vectorization)
    background_tasks.add_task(
        reference_document_service.process_document,
        db,
        doc.id
    )

    return ReferenceDocumentResponse.model_validate(doc)


@router.get("/", response_model=ReferenceDocumentListResponse)
async def list_reference_documents(
    category: Optional[str] = None,
    risk_category: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List reference documents with filtering and pagination.

    Args:
        category: Filter by category
        risk_category: Filter by risk category
        status: Filter by processing status (pending, processing, vectorized, failed)
        search: Search in title and description
        page: Page number
        page_size: Items per page
    """
    result = await reference_document_service.list_documents(
        db=db,
        user_id=current_user.id,
        category=category,
        risk_category=risk_category,
        status=status,
        search_query=search,
        page=page,
        page_size=page_size
    )

    return ReferenceDocumentListResponse(
        items=[ReferenceDocumentResponse.model_validate(doc) for doc in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        pages=result["pages"]
    )


@router.get("/categories", response_model=List[ReferenceDocumentCategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all categories with document counts."""
    categories = await reference_document_service.get_categories(db, current_user.id)
    return [ReferenceDocumentCategoryResponse(**cat) for cat in categories]


@router.get("/{doc_id}", response_model=ReferenceDocumentResponse)
async def get_reference_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single reference document by ID."""
    doc = await reference_document_service.get_document(db, doc_id, current_user.id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return ReferenceDocumentResponse.model_validate(doc)


@router.put("/{doc_id}", response_model=ReferenceDocumentResponse)
async def update_reference_document(
    doc_id: int,
    update_data: ReferenceDocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a reference document's metadata."""
    doc = await reference_document_service.update_document(
        db=db,
        doc_id=doc_id,
        user_id=current_user.id,
        **update_data.model_dump(exclude_unset=True)
    )
    if not doc:
        raise HTTPException(404, "Document not found")
    return ReferenceDocumentResponse.model_validate(doc)


@router.delete("/{doc_id}")
async def delete_reference_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a reference document and its vectors."""
    success = await reference_document_service.delete_document(db, doc_id, current_user.id)
    if not success:
        raise HTTPException(404, "Document not found")
    return {"message": "Document deleted successfully"}


@router.post("/{doc_id}/process", response_model=ProcessingStatusResponse)
async def process_document(
    doc_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger processing (OCR + vectorization) for a document.
    Use this to reprocess a failed document.
    """
    doc = await reference_document_service.get_document(db, doc_id, current_user.id)
    if not doc:
        raise HTTPException(404, "Document not found")

    # Process in background
    background_tasks.add_task(
        reference_document_service.process_document,
        db,
        doc_id
    )

    return ProcessingStatusResponse(
        document_id=doc_id,
        status="processing",
        progress_percentage=0,
        current_step="Starting OCR extraction..."
    )


@router.get("/{doc_id}/status", response_model=ProcessingStatusResponse)
async def get_processing_status(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the processing status of a document."""
    doc = await reference_document_service.get_document(db, doc_id, current_user.id)
    if not doc:
        raise HTTPException(404, "Document not found")

    progress = 0
    current_step = None

    if doc.status == "pending":
        progress = 0
        current_step = "Waiting to process"
    elif doc.status == "processing":
        progress = 50
        current_step = "Processing..."
    elif doc.status == "vectorized":
        progress = 100
        current_step = "Complete"
    elif doc.status == "failed":
        progress = 0
        current_step = "Failed"

    return ProcessingStatusResponse(
        document_id=doc_id,
        status=doc.status,
        progress_percentage=progress,
        current_step=current_step,
        error_message=doc.error_message,
        chunk_count=doc.chunk_count,
        quality_score=doc.quality_score
    )


@router.post("/search", response_model=SemanticSearchResponse)
async def semantic_search(
    request: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Semantic search across reference documents.

    Uses vector similarity to find relevant document chunks
    for RAG-enhanced document generation.
    """
    import time
    start_time = time.time()

    results = await reference_document_service.semantic_search(
        query=request.query,
        limit=request.limit,
        risk_categories=request.risk_categories,
        category=request.category,
        min_score=request.min_score
    )

    processing_time = (time.time() - start_time) * 1000

    return SemanticSearchResponse(
        query=request.query,
        results=[SemanticSearchResult(**r) for r in results],
        total_results=len(results),
        processing_time_ms=processing_time
    )
