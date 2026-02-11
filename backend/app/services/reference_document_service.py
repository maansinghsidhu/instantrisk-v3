"""
Reference Document Service
Handles training documents for RAG-enhanced document generation.
Integrates with Qdrant for vector storage and semantic search.
"""

import os
import hashlib
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload

from app.models.reference_document import ReferenceDocument
from app.services.ocr_service import ocr_service
from app.config import settings

logger = logging.getLogger(__name__)

# Qdrant settings
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))  # HTTP REST API port
COLLECTION_NAME = "reference_documents"
EMBEDDING_DIM = 384  # For sentence-transformers mini models

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qdrant_models
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning("Qdrant client not available. RAG features disabled.")

try:
    from fastembed import TextEmbedding
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("Fastembed not available. Using fallback embeddings.")


class ReferenceDocumentService:
    """Service for managing reference/training documents with RAG."""

    def __init__(self):
        self.qdrant_client = None
        self.embedding_model = None
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize Qdrant and embedding model."""
        if QDRANT_AVAILABLE:
            try:
                self.qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
                self._ensure_collection()
                logger.info(f"Connected to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}")

        if EMBEDDINGS_AVAILABLE:
            try:
                self.embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
                logger.info("Loaded fastembed model: BAAI/bge-small-en-v1.5")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")

    def _ensure_collection(self):
        """Ensure Qdrant collection exists."""
        if not self.qdrant_client:
            return

        try:
            collections = self.qdrant_client.get_collections().collections
            if not any(c.name == COLLECTION_NAME for c in collections):
                self.qdrant_client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=qdrant_models.VectorParams(
                        size=EMBEDDING_DIM,
                        distance=qdrant_models.Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")

    async def create_document(
        self,
        db: AsyncSession,
        user_id: str,
        title: str,
        file_path: str,
        file_name: str,
        file_size: int,
        category: str = "other",
        description: str = None,
        mime_type: str = None,
        tags: List[str] = None,
        risk_categories: List[str] = None,
        syndicate_id: int = None,
        jurisdiction: str = None
    ) -> ReferenceDocument:
        """Create a new reference document record."""
        doc = ReferenceDocument(
            title=title,
            description=description,
            category=category,
            uploaded_by=user_id,
            syndicate_id=syndicate_id,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            tags=tags or [],
            risk_categories=risk_categories or [],
            jurisdiction=jurisdiction,
            status="pending"
        )

        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        return doc

    async def get_document(
        self,
        db: AsyncSession,
        doc_id: int,
        user_id: str = None
    ) -> Optional[ReferenceDocument]:
        """Get a reference document by ID."""
        query = select(ReferenceDocument).where(ReferenceDocument.id == doc_id)

        if user_id:
            query = query.where(ReferenceDocument.uploaded_by == user_id)

        result = await db.execute(query)
        return result.scalars().first()

    async def list_documents(
        self,
        db: AsyncSession,
        user_id: str,
        category: str = None,
        risk_category: str = None,
        status: str = None,
        search_query: str = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List reference documents with filtering and pagination."""
        query = select(ReferenceDocument).where(
            ReferenceDocument.uploaded_by == user_id,
            ReferenceDocument.is_active == True
        )

        if category:
            query = query.where(ReferenceDocument.category == category)

        if risk_category:
            query = query.where(ReferenceDocument.risk_categories.contains([risk_category]))

        if status:
            query = query.where(ReferenceDocument.status == status)

        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.where(
                ReferenceDocument.title.ilike(search_pattern) |
                ReferenceDocument.description.ilike(search_pattern)
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        query = query.order_by(ReferenceDocument.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size
        }

    async def update_document(
        self,
        db: AsyncSession,
        doc_id: int,
        user_id: str,
        **updates
    ) -> Optional[ReferenceDocument]:
        """Update a reference document."""
        doc = await self.get_document(db, doc_id, user_id)
        if not doc:
            return None

        for key, value in updates.items():
            if hasattr(doc, key) and value is not None:
                setattr(doc, key, value)

        await db.commit()
        await db.refresh(doc)
        return doc

    async def delete_document(
        self,
        db: AsyncSession,
        doc_id: int,
        user_id: str
    ) -> bool:
        """Delete a reference document and its vectors."""
        doc = await self.get_document(db, doc_id, user_id)
        if not doc:
            return False

        # Delete vectors from Qdrant
        if doc.vector_ids and self.qdrant_client:
            try:
                self.qdrant_client.delete(
                    collection_name=COLLECTION_NAME,
                    points_selector=qdrant_models.PointIdsList(
                        points=doc.vector_ids
                    )
                )
            except Exception as e:
                logger.error(f"Failed to delete vectors: {e}")

        # Delete from database
        await db.delete(doc)
        await db.commit()
        return True

    async def process_document(
        self,
        db: AsyncSession,
        doc_id: int
    ) -> Dict[str, Any]:
        """
        Process document: OCR extraction + vectorization.
        """
        doc = await self.get_document(db, doc_id)
        if not doc:
            return {"success": False, "error": "Document not found"}

        try:
            # Update status
            doc.status = "processing"
            await db.commit()

            # Step 1: OCR extraction
            ocr_result = await self._extract_text(doc.file_path)
            if not ocr_result.get("text"):
                doc.mark_failed("OCR extraction failed")
                await db.commit()
                return {"success": False, "error": "OCR extraction failed"}

            doc.ocr_text = ocr_result.get("text")
            doc.quality_score = ocr_result.get("confidence", 0) / 100.0

            # Step 2: Compute content hash
            doc.content_hash = hashlib.sha256(doc.ocr_text.encode()).hexdigest()

            # Step 3: Vectorize and store
            vector_ids = await self._vectorize_document(doc)
            doc.mark_vectorized(vector_ids, len(vector_ids))

            await db.commit()
            await db.refresh(doc)

            return {
                "success": True,
                "document_id": doc.id,
                "status": doc.status,
                "chunk_count": doc.chunk_count,
                "quality_score": doc.quality_score
            }

        except Exception as e:
            logger.error(f"Document processing error: {e}")
            doc.mark_failed(str(e))
            await db.commit()
            return {"success": False, "error": str(e)}

    async def _extract_text(self, file_path: str) -> Dict[str, Any]:
        """Extract text from document using OCR service."""
        try:
            # Read file from MinIO or local path
            result = await ocr_service.process_file(file_path)
            return result
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return {"text": "", "confidence": 0}

    async def _vectorize_document(self, doc: ReferenceDocument) -> List[str]:
        """Chunk text and store vectors in Qdrant."""
        if not self.qdrant_client or not self.embedding_model:
            return []

        if not doc.ocr_text:
            return []

        # Chunk the text
        chunks = self._chunk_text(doc.ocr_text, chunk_size=1000, overlap=100)
        if not chunks:
            return []

        vector_ids = []
        points = []

        for idx, chunk in enumerate(chunks):
            vector_id = f"{doc.id}_{idx}"
            vector_ids.append(vector_id)

            # Generate embedding
            import numpy as np
            emb = list(self.embedding_model.embed([chunk]))[0]
            embedding = emb.tolist() if isinstance(emb, np.ndarray) else list(emb)

            points.append(qdrant_models.PointStruct(
                id=vector_id,
                vector=embedding,
                payload={
                    "document_id": doc.id,
                    "chunk_index": idx,
                    "chunk_text": chunk[:500],  # Store truncated for retrieval
                    "category": doc.category,
                    "risk_categories": doc.risk_categories,
                    "title": doc.title,
                    "file_name": doc.file_name
                }
            ))

        # Batch upsert to Qdrant
        try:
            self.qdrant_client.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )
            logger.info(f"Stored {len(points)} vectors for document {doc.id}")
        except Exception as e:
            logger.error(f"Qdrant upsert error: {e}")
            return []

        return vector_ids

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 100
    ) -> List[str]:
        """Split text into overlapping chunks."""
        if not text:
            return []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to end at a sentence boundary
            if end < len(text):
                for sep in ['. ', '.\n', '\n\n', '\n']:
                    boundary = text.rfind(sep, start + chunk_size // 2, end)
                    if boundary > start:
                        end = boundary + len(sep)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    async def semantic_search(
        self,
        query: str,
        limit: int = 5,
        risk_categories: List[str] = None,
        category: str = None,
        min_score: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across reference documents.
        Returns relevant chunks for RAG.
        """
        if not self.qdrant_client or not self.embedding_model:
            return []

        try:
            # Generate query embedding
            import numpy as np
            emb = list(self.embedding_model.query_embed(query))[0]
            query_embedding = emb.tolist() if isinstance(emb, np.ndarray) else list(emb)

            # Build filter
            filter_conditions = []
            if risk_categories:
                for rc in risk_categories:
                    filter_conditions.append(
                        qdrant_models.FieldCondition(
                            key="risk_categories",
                            match=qdrant_models.MatchAny(any=risk_categories)
                        )
                    )
            if category:
                filter_conditions.append(
                    qdrant_models.FieldCondition(
                        key="category",
                        match=qdrant_models.MatchValue(value=category)
                    )
                )

            search_filter = None
            if filter_conditions:
                search_filter = qdrant_models.Filter(
                    must=filter_conditions
                )

            # Search
            results = self.qdrant_client.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_embedding,
                limit=limit,
                query_filter=search_filter,
                score_threshold=min_score
            )

            return [
                {
                    "document_id": hit.payload.get("document_id"),
                    "title": hit.payload.get("title"),
                    "category": hit.payload.get("category"),
                    "chunk_text": hit.payload.get("chunk_text"),
                    "similarity_score": hit.score,
                    "file_name": hit.payload.get("file_name")
                }
                for hit in results
            ]

        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []

    async def get_rag_context(
        self,
        query: str,
        risk_category: str = None,
        limit: int = 3
    ) -> str:
        """
        Get RAG context for document generation.
        Returns concatenated relevant chunks.
        """
        results = await self.semantic_search(
            query=query,
            limit=limit,
            risk_categories=[risk_category] if risk_category else None,
            min_score=0.6
        )

        if not results:
            return ""

        context_parts = []
        for r in results:
            context_parts.append(
                f"[From: {r['title']}]\n{r['chunk_text']}"
            )

        return "\n\n---\n\n".join(context_parts)

    async def get_categories(self, db: AsyncSession, user_id: str) -> List[Dict[str, Any]]:
        """Get categories with document counts."""
        query = select(
            ReferenceDocument.category,
            func.count(ReferenceDocument.id).label("count")
        ).where(
            ReferenceDocument.uploaded_by == user_id,
            ReferenceDocument.is_active == True
        ).group_by(ReferenceDocument.category)

        result = await db.execute(query)
        categories = result.all()

        category_names = {
            "policy_wording": "Policy Wordings",
            "guidelines": "Guidelines",
            "previous_contracts": "Previous Contracts",
            "market_data": "Market Data",
            "regulatory": "Regulatory",
            "clauses": "Clauses",
            "endorsements": "Endorsements",
            "other": "Other"
        }

        return [
            {
                "category": cat,
                "display_name": category_names.get(cat, cat.title()),
                "count": count
            }
            for cat, count in categories
        ]


# Singleton instance
reference_document_service = ReferenceDocumentService()
