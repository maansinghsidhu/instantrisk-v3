"""
Training API Router - Upload documents, train per-user ML adapters, run predictions
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from typing import Optional, List
from datetime import datetime
import uuid
import logging

from app.core.security import get_current_user
from app.models.user import User
from app.services.qdrant_service import qdrant_service
from app.services.insurance_model_service import insurance_model_service
from app.services.user_model_service import user_model_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/documents")
async def get_training_documents(
    current_user: User = Depends(get_current_user)
):
    """Get list of uploaded training documents."""
    try:
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
        content = await file.read()
        doc_id = str(uuid.uuid4())

        result = await qdrant_service.add_training_document(
            doc_id=doc_id,
            filename=file.filename,
            content=content,
            category=category,
            user_id=str(current_user.id),
            content_type=file.content_type
        )

        logger.info(f"Training document uploaded: {file.filename} by user {current_user.email}")

        # Check if user now has enough data for adapter training
        status = await qdrant_service.get_training_status(user_id=str(current_user.id))
        can_train = status.get("total_chunks", 0) >= 50

        return {
            "success": True,
            "document_id": doc_id,
            "filename": file.filename,
            "category": category,
            "processed": result.get("processed", False),
            "chunks_created": result.get("chunks", 0),
            "can_train_adapter": can_train,
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

        # Invalidate user's adapter cache since training data changed
        user_model_service.invalidate_cache(str(current_user.id))

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
        - is_ready: Whether user has enough training data
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

    Returns base model availability, user's personal adapter status,
    and training data readiness.
    """
    base_model_available = insurance_model_service.is_available
    user_id = str(current_user.id)

    # Check user's training data
    user_model_status = "no_data"
    user_chunks = 0
    try:
        status = await qdrant_service.get_training_status(user_id=user_id)
        user_chunks = status.get("total_chunks", 0)
    except Exception as e:
        logger.warning(f"Failed to check user training status: {e}")

    # Check adapter status
    adapter_info = user_model_service.get_adapter_info(user_id)
    has_adapter = adapter_info is not None

    if has_adapter:
        user_model_status = "ready"
        # Check if adapter is stale (user has uploaded more data since training)
        adapter_chunks = adapter_info.get("training_chunks", 0)
        if user_chunks > adapter_chunks + 20:
            user_model_status = "stale"
    elif user_chunks >= 50:
        user_model_status = "ready_to_train"
    elif user_chunks > 0:
        user_model_status = "insufficient_data"

    return {
        "base_model": {
            "available": base_model_available,
            "name": "InstantRisk Engine v1",
        },
        "user_model": {
            "status": user_model_status,
            "has_adapter": has_adapter,
            "chunks": user_chunks,
            "minimum_chunks": 50,
            "adapter_info": {
                "training_samples": adapter_info.get("training_samples", 0),
                "best_loss": adapter_info.get("best_loss"),
                "trained_at": adapter_info.get("trained_at"),
                "adapter_size_kb": adapter_info.get("adapter_size_kb"),
            } if adapter_info else None,
        },
    }


@router.post("/retrain")
async def retrain_user_model(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Train or retrain the user's personal ML adapter.

    Requires at least 50 document chunks. Training runs in the background
    and typically takes 1-5 minutes depending on data volume.
    """
    user_id = str(current_user.id)

    # Check if base model is available
    if not insurance_model_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="InstantRisk Engine base model is not loaded"
        )

    # Check minimum data requirement
    try:
        status = await qdrant_service.get_training_status(user_id=user_id)
        total_chunks = status.get("total_chunks", 0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check training data: {e}")

    if total_chunks < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 50 document chunks for adapter training. "
                   f"You have {total_chunks}. Upload more documents first."
        )

    # Run training in background
    def _train():
        try:
            result = user_model_service.train_adapter(user_id)
            if result["success"]:
                logger.info(f"User adapter trained for {current_user.email}: "
                           f"{result['training_samples']} samples, loss={result['best_loss']}")
            else:
                logger.warning(f"User adapter training failed for {current_user.email}: "
                             f"{result.get('error')}")
        except Exception as e:
            logger.error(f"User adapter training error for {current_user.email}: {e}")

    background_tasks.add_task(_train)

    return {
        "success": True,
        "message": "Adapter training started in background",
        "chunks_available": total_chunks,
    }


@router.delete("/adapter")
async def delete_user_adapter(
    current_user: User = Depends(get_current_user)
):
    """Delete the user's personal ML adapter."""
    user_id = str(current_user.id)
    deleted = user_model_service.delete_adapter(user_id)

    if deleted:
        return {"success": True, "message": "Adapter deleted"}
    else:
        return {"success": False, "message": "No adapter found"}


@router.post("/predict")
async def predict_risk(
    risk_description: str,
    current_user: User = Depends(get_current_user)
):
    """
    Run InstantRisk Engine predictions on a risk description.

    Returns clause recommendations, appetite assessment, pricing band, and intent.
    If user has a trained adapter, predictions are personalized.
    """
    if not insurance_model_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="InstantRisk Engine model is not loaded"
        )

    try:
        result = insurance_model_service.predict_all(
            risk_description,
            user_id=str(current_user.id),
        )
        return {
            "success": True,
            "predictions": result,
        }
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
