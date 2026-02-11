"""
Qdrant Vector Database Service - For User Training Documents

Stores and retrieves user-uploaded training documents in Qdrant for RAG.
Uses fastembed with BAAI/bge-small-en-v1.5 (384-dim) for ONNX-based embeddings.
"""

import os
import io
import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

# Qdrant settings - separate collection for user training docs
TRAINING_COLLECTION = "user_training_documents"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
CHUNK_SIZE = 500  # Characters per chunk
CHUNK_OVERLAP = 50


class QdrantService:
    """Service for managing user training documents with vector embeddings."""

    def __init__(self):
        self.qdrant_client = None
        self.embedding_model = None
        self._initialized = False

    def _initialize(self) -> bool:
        """Lazy initialization of Qdrant client and embedding model."""
        if self._initialized:
            return True

        try:
            from qdrant_client import QdrantClient

            host = os.getenv("QDRANT_HOST", "localhost")
            port = int(os.getenv("QDRANT_PORT", 6333))
            self.qdrant_client = QdrantClient(host=host, port=port)
            logger.info(f"Connected to Qdrant at {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            return False

        try:
            from fastembed import TextEmbedding
            self.embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL)
            logger.info(f"Loaded fastembed model: {EMBEDDING_MODEL}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            return False

        self._initialized = True
        return True

    def _ensure_collection(self):
        """Create Qdrant collection for training docs if it doesn't exist."""
        from qdrant_client.http import models as qdrant_models

        collections = self.qdrant_client.get_collections().collections
        if any(c.name == TRAINING_COLLECTION for c in collections):
            return

        self.qdrant_client.create_collection(
            collection_name=TRAINING_COLLECTION,
            vectors_config=qdrant_models.VectorParams(
                size=EMBEDDING_DIM,
                distance=qdrant_models.Distance.COSINE,
            ),
        )
        logger.info(f"Created Qdrant collection: {TRAINING_COLLECTION}")

    def _extract_text_from_content(self, content: bytes, content_type: str, filename: str) -> str:
        """Extract text from various document formats."""
        text = ""

        try:
            # PDF extraction
            if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
                try:
                    import fitz  # PyMuPDF
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

            # Word document extraction
            elif content_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                   "application/msword"] or filename.lower().endswith((".docx", ".doc")):
                try:
                    from docx import Document
                    doc = Document(io.BytesIO(content))
                    for para in doc.paragraphs:
                        text += para.text + "\n"
                except Exception as e:
                    logger.error(f"DOCX extraction failed: {e}")

            # Excel extraction
            elif content_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   "application/vnd.ms-excel"] or filename.lower().endswith((".xlsx", ".xls")):
                try:
                    import pandas as pd
                    df = pd.read_excel(io.BytesIO(content))
                    text = df.to_string()
                except Exception as e:
                    logger.error(f"Excel extraction failed: {e}")

            # Plain text
            elif content_type in ["text/plain", "text/csv"] or filename.lower().endswith((".txt", ".csv")):
                try:
                    text = content.decode("utf-8")
                except UnicodeDecodeError:
                    text = content.decode("latin-1", errors="ignore")

            # Fallback: try to decode as text
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

            # Try to break at sentence/paragraph boundary
            if end < len(text):
                # Look for paragraph break
                newline_pos = chunk.rfind("\n\n")
                if newline_pos > CHUNK_SIZE // 2:
                    end = start + newline_pos + 2
                    chunk = text[start:end]
                else:
                    # Look for sentence break
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
        """Generate embeddings for a list of texts using fastembed."""
        embeddings = list(self.embedding_model.embed(texts))
        return [emb.tolist() if isinstance(emb, np.ndarray) else list(emb) for emb in embeddings]

    def _embed_query(self, query: str) -> List[float]:
        """Generate embedding for a single query."""
        embeddings = list(self.embedding_model.query_embed(query))
        emb = embeddings[0]
        return emb.tolist() if isinstance(emb, np.ndarray) else list(emb)

    def _generate_point_id(self, text: str, doc_id: str, chunk_idx: int) -> int:
        """Generate a deterministic point ID from doc and chunk."""
        hash_input = f"{doc_id}:{chunk_idx}:{text[:100]}"
        return int(hashlib.md5(hash_input.encode()).hexdigest()[:15], 16)

    async def get_training_documents(self, user_id: str) -> List[Dict]:
        """Get list of training documents for a user (metadata only)."""
        if not self._initialize():
            return []

        try:
            from qdrant_client.http import models as qdrant_models

            # Get unique doc_ids for this user
            results = self.qdrant_client.scroll(
                collection_name=TRAINING_COLLECTION,
                scroll_filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="user_id",
                            match=qdrant_models.MatchValue(value=user_id),
                        )
                    ]
                ),
                limit=1000,
                with_payload=True,
                with_vectors=False,
            )

            # Group by doc_id to get unique documents
            docs_map = {}
            for point in results[0]:
                doc_id = point.payload.get("doc_id")
                if doc_id and doc_id not in docs_map:
                    docs_map[doc_id] = {
                        "id": doc_id,
                        "filename": point.payload.get("filename"),
                        "category": point.payload.get("category"),
                        "uploaded_at": point.payload.get("uploaded_at"),
                        "processed": True,
                        "size_bytes": point.payload.get("size_bytes", 0),
                        "chunk_count": 0,
                    }
                if doc_id:
                    docs_map[doc_id]["chunk_count"] += 1

            return list(docs_map.values())

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
        """
        Add a training document for AI improvement.

        Extracts text, creates chunks, generates embeddings, and stores in Qdrant.
        """
        if not self._initialize():
            return {"processed": False, "error": "Qdrant not available"}

        from qdrant_client.http import models as qdrant_models

        try:
            self._ensure_collection()

            # Extract text from document
            text = self._extract_text_from_content(content, content_type or "", filename)
            if not text:
                return {"processed": False, "error": "Could not extract text from document"}

            logger.info(f"Extracted {len(text)} chars from {filename}")

            # Chunk the text
            chunks = self._chunk_text(text)
            if not chunks:
                return {"processed": False, "error": "No text chunks generated"}

            logger.info(f"Created {len(chunks)} chunks from {filename}")

            # Generate embeddings for all chunks
            embeddings = self._embed_texts(chunks)

            # Create points for Qdrant
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                point_id = self._generate_point_id(chunk, doc_id, i)
                points.append(
                    qdrant_models.PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "doc_id": doc_id,
                            "user_id": user_id,
                            "filename": filename,
                            "category": category,
                            "content_type": content_type,
                            "size_bytes": len(content),
                            "uploaded_at": datetime.utcnow().isoformat(),
                            "chunk_index": i,
                            "chunk_count": len(chunks),
                            "text": chunk,
                        },
                    )
                )

            # Upsert to Qdrant
            self.qdrant_client.upsert(
                collection_name=TRAINING_COLLECTION,
                points=points,
            )

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
        if not self._initialize():
            return False

        from qdrant_client.http import models as qdrant_models

        try:
            self.qdrant_client.delete(
                collection_name=TRAINING_COLLECTION,
                points_selector=qdrant_models.FilterSelector(
                    filter=qdrant_models.Filter(
                        must=[
                            qdrant_models.FieldCondition(
                                key="doc_id",
                                match=qdrant_models.MatchValue(value=doc_id),
                            ),
                            qdrant_models.FieldCondition(
                                key="user_id",
                                match=qdrant_models.MatchValue(value=user_id),
                            ),
                        ]
                    )
                ),
            )
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
        """
        Search for similar documents using vector similarity.

        Filters by user_id to only search user's own training documents.
        """
        if not self._initialize():
            return []

        from qdrant_client.http import models as qdrant_models

        try:
            query_vector = self._embed_query(query)

            # Build filter
            must_conditions = [
                qdrant_models.FieldCondition(
                    key="user_id",
                    match=qdrant_models.MatchValue(value=user_id),
                )
            ]

            if category:
                must_conditions.append(
                    qdrant_models.FieldCondition(
                        key="category",
                        match=qdrant_models.MatchValue(value=category),
                    )
                )

            results = self.qdrant_client.query_points(
                collection_name=TRAINING_COLLECTION,
                query=query_vector,
                query_filter=qdrant_models.Filter(must=must_conditions),
                limit=limit,
            )

            return [
                {
                    "text": hit.payload.get("text", ""),
                    "filename": hit.payload.get("filename", ""),
                    "category": hit.payload.get("category", ""),
                    "doc_id": hit.payload.get("doc_id", ""),
                    "score": hit.score,
                }
                for hit in results.points
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
