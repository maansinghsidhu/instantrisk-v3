"""
RAG Indexer - Load insurance datasets into Qdrant with vector embeddings.

Indexes 112k+ insurance records from JSONL files into Qdrant for semantic search:
- 34k insurance clauses (BIMCO, LMA, Lloyd's)
- 78k Q&A pairs from industry experts
- 13 policy documents
- 208 regulatory documents

Uses fastembed with BAAI/bge-small-en-v1.5 (384-dim) for ONNX-based embeddings.
"""

import json
import logging
import hashlib
import os
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Data paths - use /app inside Docker, fallback to local dev path
DATA_BASE = Path("/app/app/data") if Path("/app/app/data").exists() else Path("app/data")
TRAINING_DATA_DIR = DATA_BASE / "training_data"

# Qdrant settings
COLLECTION_NAME = "insurance_rag"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

# Files to index
RAG_SOURCES = [
    {
        "path": TRAINING_DATA_DIR / "embeddings/clauses_for_rag.jsonl",
        "type": "clause",
        "text_field": "text",
        "max_records": None,
    },
    {
        "path": TRAINING_DATA_DIR / "embeddings/policies_for_rag.jsonl",
        "type": "policy",
        "text_field": "text",
        "max_records": None,
    },
    {
        "path": TRAINING_DATA_DIR / "embeddings/regulatory_for_rag.jsonl",
        "type": "regulatory",
        "text_field": "text",
        "max_records": None,
    },
    {
        "path": TRAINING_DATA_DIR / "chat_finetune/insurance_qa_train.jsonl",
        "type": "qa",
        "text_field": None,  # Special format: messages array
        "max_records": None,
    },
]

BATCH_SIZE = 100


class RAGIndexer:
    """Indexes insurance data into Qdrant with vector embeddings."""

    def __init__(self):
        self.qdrant_client = None
        self.embedding_model = None
        self._initialized = False

    def _initialize(self):
        """Lazy initialization of Qdrant client and embedding model."""
        if self._initialized:
            return True

        try:
            from qdrant_client import QdrantClient

            host = os.getenv("QDRANT_HOST", "localhost")
            port = int(os.getenv("QDRANT_PORT", 6333))  # HTTP REST API port
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

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts using fastembed."""
        embeddings = list(self.embedding_model.embed(texts))
        return [emb.tolist() if isinstance(emb, np.ndarray) else list(emb) for emb in embeddings]

    def _embed_query(self, query: str) -> List[float]:
        """Generate embedding for a single query."""
        embeddings = list(self.embedding_model.query_embed(query))
        emb = embeddings[0]
        return emb.tolist() if isinstance(emb, np.ndarray) else list(emb)

    def _ensure_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        from qdrant_client.http import models as qdrant_models

        collections = self.qdrant_client.get_collections().collections
        if any(c.name == COLLECTION_NAME for c in collections):
            return

        self.qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qdrant_models.VectorParams(
                size=EMBEDDING_DIM,
                distance=qdrant_models.Distance.COSINE,
            ),
        )
        logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")

    def _extract_text(self, record: Dict, source_type: str) -> Optional[str]:
        """Extract searchable text from a record based on its type."""
        if source_type == "qa":
            # Messages format: [system, user, assistant]
            messages = record.get("messages", [])
            user_msg = ""
            assistant_msg = ""
            for msg in messages:
                if msg.get("role") == "user":
                    user_msg = msg.get("content", "")
                elif msg.get("role") == "assistant":
                    assistant_msg = msg.get("content", "")
            if user_msg or assistant_msg:
                return f"Q: {user_msg}\nA: {assistant_msg}"
            return None
        else:
            return record.get("text", "")

    def _extract_metadata(self, record: Dict, source_type: str) -> Dict[str, Any]:
        """Extract metadata from a record."""
        meta = {"type": source_type}

        if source_type == "qa":
            messages = record.get("messages", [])
            for msg in messages:
                if msg.get("role") == "user":
                    meta["question"] = msg.get("content", "")[:200]
                    break
        else:
            if "category" in record:
                meta["category"] = record["category"]
            if "source" in record:
                meta["source"] = record["source"]
            if "metadata" in record and isinstance(record["metadata"], dict):
                if "name" in record["metadata"]:
                    meta["name"] = record["metadata"]["name"]

        return meta

    def _generate_point_id(self, text: str, index: int) -> int:
        """Generate a deterministic point ID from text content."""
        hash_input = f"{text[:200]}:{index}"
        return int(hashlib.md5(hash_input.encode()).hexdigest()[:15], 16)

    def get_collection_count(self) -> int:
        """Get the number of points in the collection."""
        if not self._initialize():
            return 0
        try:
            info = self.qdrant_client.get_collection(COLLECTION_NAME)
            return info.points_count
        except Exception:
            return 0

    def is_indexed(self) -> bool:
        """Check if data has already been indexed."""
        count = self.get_collection_count()
        return count > 1000  # Threshold to consider indexed

    def index_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Index all insurance data into Qdrant.

        Args:
            force: If True, recreate collection even if data exists.

        Returns:
            Dict with indexing statistics.
        """
        if not self._initialize():
            return {"error": "Failed to initialize Qdrant or embedding model"}

        from qdrant_client.http import models as qdrant_models

        if force:
            # Delete existing collection
            try:
                self.qdrant_client.delete_collection(COLLECTION_NAME)
                logger.info(f"Deleted existing collection: {COLLECTION_NAME}")
            except Exception:
                pass

        self._ensure_collection()

        if not force and self.is_indexed():
            count = self.get_collection_count()
            logger.info(f"Collection already indexed with {count} points. Use force=True to re-index.")
            return {"status": "already_indexed", "points": count}

        stats = {"total_indexed": 0, "errors": 0, "sources": {}}
        global_index = 0

        for source in RAG_SOURCES:
            source_path = source["path"]
            source_type = source["type"]

            if not source_path.exists():
                logger.warning(f"RAG source not found: {source_path}")
                continue

            logger.info(f"Indexing {source_type} from {source_path.name}...")
            source_count = 0
            batch_texts = []
            batch_metadata = []
            batch_ids = []

            with open(source_path, "r") as f:
                for i, line in enumerate(f):
                    if source["max_records"] and i >= source["max_records"]:
                        break

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        stats["errors"] += 1
                        continue

                    text = self._extract_text(record, source_type)
                    if not text or len(text.strip()) < 10:
                        continue

                    # Truncate very long texts for embedding
                    embed_text = text[:512]

                    metadata = self._extract_metadata(record, source_type)
                    metadata["full_text"] = text[:2000]  # Store more text in payload

                    point_id = self._generate_point_id(text, global_index)
                    global_index += 1

                    batch_texts.append(embed_text)
                    batch_metadata.append(metadata)
                    batch_ids.append(point_id)

                    if len(batch_texts) >= BATCH_SIZE:
                        try:
                            embeddings = self._embed_texts(batch_texts)
                            points = [
                                qdrant_models.PointStruct(
                                    id=batch_ids[j],
                                    vector=embeddings[j],
                                    payload=batch_metadata[j],
                                )
                                for j in range(len(batch_texts))
                            ]
                            self.qdrant_client.upsert(
                                collection_name=COLLECTION_NAME,
                                points=points,
                            )
                            source_count += len(batch_texts)
                        except Exception as e:
                            logger.error(f"Error indexing batch: {e}")
                            stats["errors"] += len(batch_texts)

                        batch_texts = []
                        batch_metadata = []
                        batch_ids = []

                        if source_count % 5000 == 0:
                            logger.info(f"  ...indexed {source_count} {source_type} records")

            # Index remaining batch
            if batch_texts:
                try:
                    embeddings = self._embed_texts(batch_texts)
                    points = [
                        qdrant_models.PointStruct(
                            id=batch_ids[j],
                            vector=embeddings[j],
                            payload=batch_metadata[j],
                        )
                        for j in range(len(batch_texts))
                    ]
                    self.qdrant_client.upsert(
                        collection_name=COLLECTION_NAME,
                        points=points,
                    )
                    source_count += len(batch_texts)
                except Exception as e:
                    logger.error(f"Error indexing final batch: {e}")
                    stats["errors"] += len(batch_texts)

            stats["sources"][source_type] = source_count
            stats["total_indexed"] += source_count
            logger.info(f"Indexed {source_count} {source_type} records")

        stats["status"] = "completed"
        logger.info(f"RAG indexing complete: {stats['total_indexed']} total points, {stats['errors']} errors")
        return stats

    def search(self, query: str, top_k: int = 5, doc_type: Optional[str] = None) -> List[Dict]:
        """
        Semantic search over indexed insurance data.

        Args:
            query: Search query text.
            top_k: Number of results to return.
            doc_type: Optional filter by type (clause, qa, policy, regulatory, claim).

        Returns:
            List of search results with text, metadata, and score.
        """
        if not self._initialize():
            return []

        from qdrant_client.http import models as qdrant_models

        try:
            query_vector = self._embed_query(query)

            search_filter = None
            if doc_type:
                search_filter = qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="type",
                            match=qdrant_models.MatchValue(value=doc_type),
                        )
                    ]
                )

            results = self.qdrant_client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                query_filter=search_filter,
                limit=top_k,
            )

            return [
                {
                    "text": hit.payload.get("full_text", ""),
                    "type": hit.payload.get("type", ""),
                    "category": hit.payload.get("category", ""),
                    "name": hit.payload.get("name", ""),
                    "question": hit.payload.get("question", ""),
                    "source": hit.payload.get("source", "knowledge_base"),
                    "score": hit.score,
                }
                for hit in results.points
            ]

        except Exception as e:
            logger.error(f"Qdrant search error: {e}")
            return []

    def add_documents(self, documents: List[Dict[str, Any]], doc_type: str = "claim") -> int:
        """
        Add new documents to the index (e.g., claims data).

        Args:
            documents: List of dicts with 'text' and optional metadata.
            doc_type: Document type label.

        Returns:
            Number of documents indexed.
        """
        if not self._initialize():
            return 0

        from qdrant_client.http import models as qdrant_models

        self._ensure_collection()
        count = 0
        batch_texts = []
        batch_metadata = []
        batch_ids = []
        base_index = self.get_collection_count()

        for i, doc in enumerate(documents):
            text = doc.get("text", "")
            if not text or len(text.strip()) < 10:
                continue

            embed_text = text[:512]
            metadata = {"type": doc_type, "full_text": text[:2000]}
            for key in ["category", "source", "name", "claim_id", "policyholder", "cause", "amount"]:
                if key in doc:
                    metadata[key] = str(doc[key])

            point_id = self._generate_point_id(text, base_index + i)
            batch_texts.append(embed_text)
            batch_metadata.append(metadata)
            batch_ids.append(point_id)

            if len(batch_texts) >= BATCH_SIZE:
                try:
                    embeddings = self._embed_texts(batch_texts)
                    points = [
                        qdrant_models.PointStruct(
                            id=batch_ids[j],
                            vector=embeddings[j],
                            payload=batch_metadata[j],
                        )
                        for j in range(len(batch_texts))
                    ]
                    self.qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
                    count += len(batch_texts)
                except Exception as e:
                    logger.error(f"Error adding documents batch: {e}")

                batch_texts = []
                batch_metadata = []
                batch_ids = []

        if batch_texts:
            try:
                embeddings = self._embed_texts(batch_texts)
                points = [
                    qdrant_models.PointStruct(
                        id=batch_ids[j],
                        vector=embeddings[j],
                        payload=batch_metadata[j],
                    )
                    for j in range(len(batch_texts))
                ]
                self.qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
                count += len(batch_texts)
            except Exception as e:
                logger.error(f"Error adding final documents batch: {e}")

        logger.info(f"Added {count} {doc_type} documents to index")
        return count


# Singleton instance
rag_indexer = RAGIndexer()
