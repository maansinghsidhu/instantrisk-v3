"""
User Training Documents Service — pgvector edition.

Stores and retrieves user-uploaded training documents in PostgreSQL with
pgvector embeddings for semantic search.

Uses sentence-transformers with llmware/industry-bert-insurance-v0.1 (768-dim).
"""

import io
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "llmware/industry-bert-insurance-v0.1"
EMBEDDING_DIM = 768
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


class QdrantService:
    """Service for managing user training documents with pgvector embeddings."""

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
        """Get a synchronous database engine for operations."""
        if self._sync_engine is None:
            from app.config import settings
            sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
            if "postgresql://" in sync_url and "+psycopg2" not in sync_url:
                sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")
            from sqlalchemy import create_engine
            self._sync_engine = create_engine(sync_url, pool_pre_ping=True)
        return self._sync_engine

    def _extract_text_from_content(self, content: bytes, content_type: str, filename: str) -> str:
        """Extract text from various document formats."""
        text = ""

        try:
            if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
                try:
                    import fitz
                    doc = fitz.open(stream=content, filetype="pdf")
                    for page in doc:
                        text += page.get_text()
                    doc.close()
                except Exception as e:
                    logger.warning(f"PyMuPDF failed, trying pdfplumber: {e}")
                    try:
                        import pdfplumber
                        with pdfplumber.open(io.BytesIO(content)) as pdf:
                            for page in pdf.pages:
                                page_text = page.extract_text()
                                if page_text:
                                    text += page_text + "\n"
                    except Exception as e2:
                        logger.error(f"PDF extraction failed: {e2}")

            elif content_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                   "application/msword"] or filename.lower().endswith((".docx", ".doc")):
                try:
                    from docx import Document
                    doc = Document(io.BytesIO(content))
                    for para in doc.paragraphs:
                        text += para.text + "\n"
                except Exception as e:
                    logger.error(f"DOCX extraction failed: {e}")

            elif content_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   "application/vnd.ms-excel"] or filename.lower().endswith((".xlsx", ".xls")):
                try:
                    import pandas as pd
                    df = pd.read_excel(io.BytesIO(content))
                    text = df.to_string()
                except Exception as e:
                    logger.error(f"Excel extraction failed: {e}")

            elif content_type in ["text/plain", "text/csv"] or filename.lower().endswith((".txt", ".csv")):
                try:
                    text = content.decode("utf-8")
                except UnicodeDecodeError:
                    text = content.decode("latin-1", errors="ignore")

            else:
                try:
                    text = content.decode("utf-8")
                except UnicodeDecodeError:
                    text = content.decode("latin-1", errors="ignore")

        except Exception as e:
            logger.error(f"Text extraction failed for {filename}: {e}")

        return text.strip()

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks for better retrieval."""
        if len(text) <= CHUNK_SIZE:
            return [text] if text.strip() else []

        chunks = []
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk = text[start:end]

            if end < len(text):
                newline_pos = chunk.rfind("\n\n")
                if newline_pos > CHUNK_SIZE // 2:
                    end = start + newline_pos + 2
                    chunk = text[start:end]
                else:
                    for sep in [". ", "! ", "? ", "\n"]:
                        sep_pos = chunk.rfind(sep)
                        if sep_pos > CHUNK_SIZE // 2:
                            end = start + sep_pos + len(sep)
                            chunk = text[start:end]
                            break

            if chunk.strip():
                chunks.append(chunk.strip())

            start = end - CHUNK_OVERLAP

        return chunks

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
        return [emb.tolist() if isinstance(emb, np.ndarray) else list(emb) for emb in embeddings]

    def _embed_query(self, query: str) -> List[float]:
        """Generate embedding for a single query."""
        emb = self.embedding_model.encode(query, show_progress_bar=False)
        return emb.tolist() if isinstance(emb, np.ndarray) else list(emb)

    async def get_training_documents(self, user_id: str) -> List[Dict]:
        """Get list of training documents for a user (metadata only)."""
        if not self._load_model():
            return []

        try:
            engine = self._get_sync_engine()
            from sqlalchemy import text as sql_text

            with engine.connect() as conn:
                result = conn.execute(sql_text("""
                    SELECT DISTINCT ON (doc_id)
                        doc_id, filename, category, uploaded_at, size_bytes, chunk_count
                    FROM user_doc_vectors
                    WHERE user_id = :user_id
                    ORDER BY doc_id, uploaded_at DESC
                """), {"user_id": user_id})
                rows = result.fetchall()

            # Also get actual chunk counts per doc
            chunk_counts = {}
            with engine.connect() as conn:
                result = conn.execute(sql_text("""
                    SELECT doc_id, COUNT(*) as cnt
                    FROM user_doc_vectors
                    WHERE user_id = :user_id
                    GROUP BY doc_id
                """), {"user_id": user_id})
                for row in result.fetchall():
                    chunk_counts[row[0]] = row[1]

            docs = []
            for row in rows:
                doc_id = row[0]
                docs.append({
                    "id": doc_id,
                    "filename": row[1],
                    "category": row[2],
                    "uploaded_at": row[3].isoformat() if row[3] else None,
                    "processed": True,
                    "size_bytes": row[4] or 0,
                    "chunk_count": chunk_counts.get(doc_id, 0),
                })

            return docs

        except Exception as e:
            logger.error(f"Failed to get training documents: {e}")
            return []

    async def count_training_docs(self, user_id: str) -> int:
        """Get count of unique training documents for a user."""
        docs = await self.get_training_documents(user_id)
        return len(docs)

    async def add_training_document(
        self,
        doc_id: str,
        filename: str,
        content: bytes,
        category: str,
        user_id: str,
        content_type: str = None
    ) -> Dict:
        """Add a training document: extract text, chunk, embed, store in pgvector."""
        if not self._load_model():
            return {"processed": False, "error": "Embedding model not available"}

        try:
            text = self._extract_text_from_content(content, content_type or "", filename)
            if not text:
                return {"processed": False, "error": "Could not extract text from document"}

            logger.info(f"Extracted {len(text)} chars from {filename}")

            chunks = self._chunk_text(text)
            if not chunks:
                return {"processed": False, "error": "No text chunks generated"}

            logger.info(f"Created {len(chunks)} chunks from {filename}")

            embeddings = self._embed_texts(chunks)
            now = datetime.now(timezone.utc)

            engine = self._get_sync_engine()
            from sqlalchemy import text as sql_text

            with engine.begin() as conn:
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    conn.execute(sql_text("""
                        INSERT INTO user_doc_vectors
                            (user_id, doc_id, filename, category, content_type,
                             size_bytes, chunk_index, chunk_count, text, embedding, uploaded_at)
                        VALUES
                            (:user_id, :doc_id, :filename, :category, :content_type,
                             :size_bytes, :chunk_index, :chunk_count, :text, :embedding, :uploaded_at)
                    """), {
                        "user_id": user_id,
                        "doc_id": doc_id,
                        "filename": filename,
                        "category": category,
                        "content_type": content_type,
                        "size_bytes": len(content),
                        "chunk_index": i,
                        "chunk_count": len(chunks),
                        "text": chunk,
                        "embedding": str(embedding),
                        "uploaded_at": now,
                    })

            logger.info(f"Training document stored: {filename} ({len(chunks)} chunks)")

            return {
                "processed": True,
                "doc_id": doc_id,
                "chunks": len(chunks),
                "text_length": len(text),
            }

        except Exception as e:
            logger.error(f"Failed to add training document: {e}")
            raise

    async def delete_training_document(self, doc_id: str, user_id: str) -> bool:
        """Delete all chunks of a training document."""
        try:
            engine = self._get_sync_engine()
            from sqlalchemy import text as sql_text

            with engine.begin() as conn:
                conn.execute(sql_text("""
                    DELETE FROM user_doc_vectors
                    WHERE doc_id = :doc_id AND user_id = :user_id
                """), {"doc_id": doc_id, "user_id": user_id})

            logger.info(f"Training document deleted: {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete training document: {e}")
            return False

    async def search_similar(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        category: str = None
    ) -> List[Dict]:
        """Search for similar documents using pgvector cosine similarity."""
        if not self._load_model():
            return []

        try:
            query_vector = self._embed_query(query)
            engine = self._get_sync_engine()
            from sqlalchemy import text as sql_text

            if category:
                sql = sql_text("""
                    SELECT text, filename, category, doc_id,
                           1 - (embedding <=> :query_vec) AS score
                    FROM user_doc_vectors
                    WHERE user_id = :user_id AND category = :category
                    ORDER BY embedding <=> :query_vec
                    LIMIT :limit
                """)
                params = {"query_vec": str(query_vector), "user_id": user_id, "category": category, "limit": limit}
            else:
                sql = sql_text("""
                    SELECT text, filename, category, doc_id,
                           1 - (embedding <=> :query_vec) AS score
                    FROM user_doc_vectors
                    WHERE user_id = :user_id
                    ORDER BY embedding <=> :query_vec
                    LIMIT :limit
                """)
                params = {"query_vec": str(query_vector), "user_id": user_id, "limit": limit}

            with engine.connect() as conn:
                result = conn.execute(sql, params)
                rows = result.fetchall()

            return [
                {
                    "text": row[0] or "",
                    "filename": row[1] or "",
                    "category": row[2] or "",
                    "doc_id": row[3] or "",
                    "score": float(row[4]) if row[4] else 0,
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Training doc search error: {e}")
            return []

    async def get_training_status(self, user_id: str) -> Dict:
        """Get training status for a user."""
        docs = await self.get_training_documents(user_id)
        total_chunks = sum(d.get("chunk_count", 0) for d in docs)

        return {
            "documents_count": len(docs),
            "total_chunks": total_chunks,
            "is_ready": len(docs) > 0,
            "last_updated": docs[0]["uploaded_at"] if docs else None,
        }


# Singleton instance
qdrant_service = QdrantService()
