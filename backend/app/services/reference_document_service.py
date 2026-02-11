"""
Reference Document Service — pgvector edition.

Handles training documents for RAG-enhanced document generation.
Uses PostgreSQL pgvector for vector storage and semantic search.
"""

import hashlib
import logging
import numpy as np
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.models.reference_document import ReferenceDocument
from app.services.ocr_service import ocr_service

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "llmware/industry-bert-insurance-v0.1"
EMBEDDING_DIM = 768


class ReferenceDocumentService:
    """Service for managing reference/training documents with pgvector RAG."""

    def __init__(self):
        self.embedding_model = None
        self._model_loaded = False
        self._sync_engine = None

    def _load_model(self) -> bool:
        """Load the embedding model."""
        if self._model_loaded:
            return True
        try:
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
            self._model_loaded = True
            logger.info(f"Loaded embedding model: {EMBEDDING_MODEL}")
            return True
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            return False

    def _get_sync_engine(self):
        """Get a synchronous database engine."""
        if self._sync_engine is None:
            from app.config import settings
            sync_url = settings.sync_database_url
            if "+psycopg2" not in sync_url:
                sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")
            from sqlalchemy import create_engine
            self._sync_engine = create_engine(sync_url, pool_pre_ping=True)
        return self._sync_engine

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

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

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

        # Delete vectors from pgvector table
        try:
            engine = self._get_sync_engine()
            from sqlalchemy import text as sql_text
            with engine.begin() as conn:
                conn.execute(sql_text("""
                    DELETE FROM ref_doc_vectors WHERE document_id = :doc_id
                """), {"doc_id": doc_id})
        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}")

        await db.delete(doc)
        await db.commit()
        return True

    async def process_document(
        self,
        db: AsyncSession,
        doc_id: int
    ) -> Dict[str, Any]:
        """Process document: OCR extraction + vectorization."""
        doc = await self.get_document(db, doc_id)
        if not doc:
            return {"success": False, "error": "Document not found"}

        try:
            doc.status = "processing"
            await db.commit()

            ocr_result = await self._extract_text(doc.file_path)
            if not ocr_result.get("text"):
                doc.mark_failed("OCR extraction failed")
                await db.commit()
                return {"success": False, "error": "OCR extraction failed"}

            doc.ocr_text = ocr_result.get("text")
            doc.quality_score = ocr_result.get("confidence", 0) / 100.0

            doc.content_hash = hashlib.sha256(doc.ocr_text.encode()).hexdigest()

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
            result = await ocr_service.process_file(file_path)
            return result
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return {"text": "", "confidence": 0}

    async def _vectorize_document(self, doc: ReferenceDocument) -> List[str]:
        """Chunk text and store vectors in pgvector."""
        if not self._load_model():
            return []

        if not doc.ocr_text:
            return []

        chunks = self._chunk_text(doc.ocr_text, chunk_size=1000, overlap=100)
        if not chunks:
            return []

        vector_ids = []
        engine = self._get_sync_engine()
        from sqlalchemy import text as sql_text

        try:
            embeddings = self.embedding_model.encode(chunks, show_progress_bar=False)
            now = datetime.now(timezone.utc)

            with engine.begin() as conn:
                for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                    vector_id = f"{doc.id}_{idx}"
                    vector_ids.append(vector_id)
                    embedding = emb.tolist() if isinstance(emb, np.ndarray) else list(emb)

                    conn.execute(sql_text("""
                        INSERT INTO ref_doc_vectors
                            (document_id, chunk_index, chunk_text, category,
                             risk_categories, title, file_name, embedding, created_at)
                        VALUES
                            (:document_id, :chunk_index, :chunk_text, :category,
                             :risk_categories, :title, :file_name, :embedding, :created_at)
                    """), {
                        "document_id": doc.id,
                        "chunk_index": idx,
                        "chunk_text": chunk[:500],
                        "category": doc.category,
                        "risk_categories": str(doc.risk_categories) if doc.risk_categories else "[]",
                        "title": doc.title,
                        "file_name": doc.file_name,
                        "embedding": str(embedding),
                        "created_at": now,
                    })

            logger.info(f"Stored {len(vector_ids)} vectors for document {doc.id}")

        except Exception as e:
            logger.error(f"pgvector upsert error: {e}")
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
        """Semantic search across reference documents using pgvector."""
        if not self._load_model():
            return []

        try:
            emb = self.embedding_model.encode(query, show_progress_bar=False)
            query_embedding = emb.tolist() if isinstance(emb, np.ndarray) else list(emb)

            engine = self._get_sync_engine()
            from sqlalchemy import text as sql_text

            # Build query with optional filters
            where_clauses = []
            params = {"query_vec": str(query_embedding), "limit": limit, "min_score": min_score}

            if category:
                where_clauses.append("category = :category")
                params["category"] = category

            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            sql = sql_text(f"""
                SELECT document_id, title, category, chunk_text, file_name,
                       1 - (embedding <=> :query_vec) AS score
                FROM ref_doc_vectors
                {where_sql}
                ORDER BY embedding <=> :query_vec
                LIMIT :limit
            """)

            with engine.connect() as conn:
                result = conn.execute(sql, params)
                rows = result.fetchall()

            results = []
            for row in rows:
                score = float(row[5]) if row[5] else 0
                if score >= min_score:
                    results.append({
                        "document_id": row[0],
                        "title": row[1],
                        "category": row[2],
                        "chunk_text": row[3],
                        "similarity_score": score,
                        "file_name": row[4]
                    })

            return results

        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []

    async def get_rag_context(
        self,
        query: str,
        risk_category: str = None,
        limit: int = 3
    ) -> str:
        """Get RAG context for document generation."""
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
