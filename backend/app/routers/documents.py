"""
InstantRisk V2 - Documents Router

This module provides endpoints for document upload, management,
and OCR processing.
"""

import hashlib
import uuid
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.document import Document, DocumentStatus, DocumentType
from app.services.ocr_service import OCRService

# Security imports
from app.utils import validate_file, FileValidationError, scan_file_content, sanitize_filename
from app.middleware import log_file_blocked, log_malware_detected
import logging

logger = logging.getLogger("documents")

router = APIRouter()


def get_file_extension(filename: str) -> str:
    """
    Extract file extension from filename.

    Args:
        filename: The original filename.

    Returns:
        str: The file extension including the dot.
    """
    if "." in filename:
        return "." + filename.rsplit(".", 1)[1].lower()
    return ""


def calculate_checksum(content: bytes) -> str:
    """
    Calculate SHA256 checksum of file content.

    Args:
        content: File content as bytes.

    Returns:
        str: SHA256 checksum hex string.
    """
    return hashlib.sha256(content).hexdigest()


async def process_document_ocr(document_id: int, db: AsyncSession):
    """
    Background task to process document with OCR.

    Args:
        document_id: ID of the document to process.
        db: Database session.
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        return

    try:
        document.mark_processing()
        await db.commit()

        # Initialize OCR service and process
        ocr_service = OCRService()
        ocr_result = await ocr_service.process_document(document.file_path)

        document.mark_completed(
            ocr_text=ocr_result["text"],
            confidence=ocr_result["confidence"]
        )
        document.extracted_data = ocr_result.get("extracted_data", {})
        document.ocr_language = ocr_result.get("language", "en")

        await db.commit()

    except Exception as e:
        document.mark_failed(str(e))
        await db.commit()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: "Request",
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.OTHER),
    assessment_id: Optional[str] = Form(None),
    ocr_language: str = Form("en"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Upload a document for processing.

    Args:
        request: FastAPI request object.
        background_tasks: FastAPI background tasks.
        file: The uploaded file.
        document_type: Type of insurance document.
        assessment_id: Optional related assessment ID.
        ocr_language: Language for OCR processing.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        dict: Upload confirmation with document ID.

    Raises:
        HTTPException: If file type is not allowed, malicious, or too large.
    """
    # Get client IP for logging
    client_ip = getattr(request.state, "client_ip", request.client.host if request.client else "unknown")

    # Sanitize filename
    safe_filename = sanitize_filename(file.filename)

    # Validate file extension
    extension = get_file_extension(safe_filename)
    if extension not in settings.ALLOWED_EXTENSIONS:
        await log_file_blocked(safe_filename, "Extension not allowed", client_ip, current_user.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > settings.MAX_UPLOAD_SIZE:
        await log_file_blocked(safe_filename, "File too large", client_ip, current_user.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB"
        )

    # Security validation: MIME type, embedded scripts, macros
    try:
        await validate_file(content, safe_filename)
    except FileValidationError as e:
        await log_file_blocked(safe_filename, e.message, client_ip, current_user.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File validation failed: {e.message}"
        )

    # Antivirus scan
    is_clean, scan_message = await scan_file_content(content, safe_filename)
    if not is_clean:
        await log_malware_detected(safe_filename, scan_message, client_ip, current_user.id)
        logger.critical(f"MALWARE BLOCKED: {safe_filename} from user {current_user.id} - {scan_message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File rejected: potential security threat detected"
        )

    # Generate unique file path
    file_id = str(uuid.uuid4())
    file_path = f"documents/{current_user.id}/{file_id}{extension}"

    # Calculate checksum
    checksum = calculate_checksum(content)

    # Save file to disk
    storage_dir = Path(settings.resolved_upload_dir) / "documents" / str(current_user.id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    full_path = storage_dir / f"{file_id}{extension}"
    with open(full_path, "wb") as f:
        f.write(content)

    # Create document record
    document = Document(
        filename=safe_filename,
        file_path=file_path,
        file_size=len(content),
        mime_type=file.content_type,
        document_type=document_type,
        uploaded_by=current_user.id,
        assessment_id=assessment_id,
        ocr_language=ocr_language,
        checksum=checksum,
        status=DocumentStatus.PENDING
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Queue OCR processing as background task
    background_tasks.add_task(process_document_ocr, document.id, db)

    return {
        "message": "Document uploaded successfully",
        "document_id": document.id,
        "filename": document.filename,
        "status": document.status.value
    }


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get document details by ID.

    Args:
        document_id: The document ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        dict: Document details.

    Raises:
        HTTPException: If document not found or access denied.
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Check access (user can only see their own documents unless admin)
    if document.uploaded_by != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return {
        "id": document.id,
        "filename": document.filename,
        "file_size": document.file_size,
        "mime_type": document.mime_type,
        "document_type": document.document_type.value,
        "status": document.status.value,
        "ocr_confidence": document.ocr_confidence,
        "ocr_language": document.ocr_language,
        "extracted_data": document.extracted_data,
        "error_message": document.error_message,
        "created_at": document.created_at.isoformat(),
        "processed_at": document.processed_at.isoformat() if document.processed_at else None
    }


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download a document file.

    Args:
        document_id: The document ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        FileResponse: The document file.
    """
    from fastapi.responses import FileResponse
    import os

    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Check access
    if document.uploaded_by != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Check if file exists
    if not os.path.exists(document.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on server"
        )

    return FileResponse(
        path=document.file_path,
        filename=document.filename,
        media_type=document.mime_type or "application/octet-stream"
    )


@router.get("/{document_id}/text")
async def get_document_text(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get extracted OCR text from a document.

    Args:
        document_id: The document ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        dict: Extracted text and metadata.

    Raises:
        HTTPException: If document not found or not processed.
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Check access
    if document.uploaded_by != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document not processed. Status: {document.status.value}"
        )

    return {
        "document_id": document.id,
        "text": document.ocr_text,
        "confidence": document.ocr_confidence,
        "language": document.ocr_language
    }


@router.get("/")
async def list_documents(
    assessment_id: Optional[str] = None,
    status: Optional[DocumentStatus] = None,
    document_type: Optional[DocumentType] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    List documents with optional filters.

    Args:
        assessment_id: Filter by assessment ID.
        status: Filter by processing status.
        document_type: Filter by document type.
        page: Page number (1-indexed).
        page_size: Number of items per page.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        dict: Paginated list of documents.
    """
    # Build query
    query = select(Document)

    # Filter by user unless admin
    if current_user.role != "admin":
        query = query.where(Document.uploaded_by == current_user.id)

    # Apply filters
    if assessment_id:
        query = query.where(Document.assessment_id == assessment_id)
    if status:
        query = query.where(Document.status == status)
    if document_type:
        query = query.where(Document.document_type == document_type)

    # Order by creation date (newest first)
    query = query.order_by(Document.created_at.desc())

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    documents = result.scalars().all()

    return {
        "items": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "document_type": doc.document_type.value,
                "status": doc.status.value,
                "created_at": doc.created_at.isoformat()
            }
            for doc in documents
        ],
        "page": page,
        "page_size": page_size
    }


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a document.

    Args:
        document_id: The document ID to delete.
        current_user: The authenticated user.
        db: Database session.

    Raises:
        HTTPException: If document not found or access denied.
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Check access (only owner or admin can delete)
    if document.uploaded_by != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # TODO: Delete from MinIO storage
    # minio_client.remove_object(settings.MINIO_BUCKET, document.file_path)

    await db.delete(document)
    await db.commit()


@router.post("/{document_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    ocr_language: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Reprocess a document with OCR.

    Args:
        document_id: The document ID to reprocess.
        background_tasks: FastAPI background tasks.
        ocr_language: Optional new language for OCR.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        dict: Reprocessing confirmation.

    Raises:
        HTTPException: If document not found or access denied.
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Check access
    if document.uploaded_by != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Update language if provided
    if ocr_language:
        document.ocr_language = ocr_language

    # Reset status
    document.status = DocumentStatus.PENDING
    document.error_message = None
    await db.commit()

    # Queue reprocessing
    background_tasks.add_task(process_document_ocr, document.id, db)

    return {
        "message": "Document queued for reprocessing",
        "document_id": document.id
    }
