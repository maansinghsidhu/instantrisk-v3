"""
Training API Router - Upload documents to improve AI analysis
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import Optional, List
from datetime import datetime
import uuid
import logging

from app.core.security import get_current_user
from app.models.user import User
from app.services.qdrant_service import qdrant_service
from app.services.insurance_model_service import insurance_model_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/documents")
async def get_training_documents(
    current_user: User = Depends(get_current_user)
):
    """Get list of uploaded training documents."""
    try:
        # Get documents from Qdrant training collection
        documents = await qdrant_service.get_training_documents(
            user_id=str(current_user.id)
        )

        return {
            "documents": documents,
            "total": len(documents)
        }
    except Exception as e:
        logger.error(f"Failed to get training documents: {e}")
        return {"documents": [], "total": 0}


@router.post("/upload")
async def upload_training_document(
    file: UploadFile = File(...),
    category: str = Form("policy"),
    current_user: User = Depends(get_current_user)
):
    """Upload a document for AI training."""
    try:
        # Read file content
        content = await file.read()

        # Generate document ID
        doc_id = str(uuid.uuid4())

        # Store document metadata and content in Qdrant for RAG
        result = await qdrant_service.add_training_document(
            doc_id=doc_id,
            filename=file.filename,
            content=content,
            category=category,
            user_id=str(current_user.id),
            content_type=file.content_type
        )

        logger.info(f"Training document uploaded: {file.filename} by user {current_user.email}")

        return {
            "success": True,
            "document_id": doc_id,
            "filename": file.filename,
            "category": category,
            "processed": result.get("processed", False)
        }

    except Exception as e:
        logger.error(f"Failed to upload training document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}")
async def delete_training_document(
    doc_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a training document."""
    try:
        await qdrant_service.delete_training_document(
            doc_id=doc_id,
            user_id=str(current_user.id)
        )

        return {"success": True, "message": "Document deleted"}

    except Exception as e:
        logger.error(f"Failed to delete training document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_training_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get training status for current user.

    Returns:
        - documents_count: Number of training documents uploaded
        - total_chunks: Total text chunks indexed for RAG
        - is_ready: Whether user has enough training data for document generation
        - last_updated: When training data was last updated
    """
    try:
        status = await qdrant_service.get_training_status(
            user_id=str(current_user.id)
        )
        return status
    except Exception as e:
        logger.error(f"Failed to get training status: {e}")
        return {
            "documents_count": 0,
            "total_chunks": 0,
            "is_ready": False,
            "last_updated": None,
            "error": str(e)
        }


@router.post("/search")
async def search_training_documents(
    query: str,
    limit: int = 5,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Search training documents by semantic similarity.

    Use this to find relevant training documents for a given query.
    Results are filtered to only show the current user's documents.
    """
    try:
        results = await qdrant_service.search_similar(
            query=query,
            user_id=str(current_user.id),
            limit=limit,
            category=category
        )
        return {
            "results": results,
            "count": len(results),
            "query": query
        }
    except Exception as e:
        logger.error(f"Failed to search training documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-status")
async def get_model_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get InstantRisk Engine model status.

    Returns base model availability and user's personal model training status.
    """
    base_model_available = insurance_model_service.is_available

    # Check user's training data for personal model readiness
    user_model_status = "not_available"
    user_chunks = 0
    try:
        status = await qdrant_service.get_training_status(
            user_id=str(current_user.id)
        )
        user_chunks = status.get("total_chunks", 0)
        if user_chunks >= 50:
            user_model_status = "ready_to_train"
        elif user_chunks > 0:
            user_model_status = "insufficient_data"
        else:
            user_model_status = "no_data"
    except Exception as e:
        logger.warning(f"Failed to check user model status: {e}")

    return {
        "base_model": {
            "available": base_model_available,
            "name": "InstantRisk Engine v1",
        },
        "user_model": {
            "status": user_model_status,
            "chunks": user_chunks,
            "minimum_chunks": 50,
        },
    }


@router.post("/predict")
async def predict_risk(
    risk_description: str,
    current_user: User = Depends(get_current_user)
):
    """
    Run InstantRisk Engine predictions on a risk description.

    Returns clause recommendations, appetite assessment, pricing band, and intent.
    """
    if not insurance_model_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="InstantRisk Engine model is not loaded"
        )

    try:
        result = insurance_model_service.predict_all(risk_description)
        return {
            "success": True,
            "predictions": result,
        }
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
