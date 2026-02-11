"""
RAG Indexer — pgvector edition.

Indexes insurance datasets (ACORD, CUAD, JeTech) into PostgreSQL with
pgvector embeddings for semantic search.

Uses sentence-transformers with llmware/industry-bert-insurance-v0.1 (768-dim).
"""

import json
import logging
import hashlib
import os
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Data paths
DATA_BASE = Path("/app/app/data") if Path("/app/app/data").exists() else Path("app/data")
TRAINING_DATA_DIR = DATA_BASE / "training_data"

# Embedding settings
EMBEDDING_MODEL = "llmware/industry-bert-insurance-v0.1"
EMBEDDING_DIM = 768
BATCH_SIZE = 100

# All 7 real datasets
RAG_SOURCES = [
    {
        "path": TRAINING_DATA_DIR / "embeddings/acord_clauses.jsonl",
        "type": "acord",
        "text_field": "text",
    },
    {
        "path": TRAINING_DATA_DIR / "embeddings/cuad_clauses.jsonl",
        "type": "cuad",
        "text_field": "text",
    },
    {
        "path": TRAINING_DATA_DIR / "embeddings/jetech_blocks.jsonl",
        "type": "underwriting_block",
        "text_field": "text",
    },
    {
        "path": TRAINING_DATA_DIR / "embeddings/ledgar_provisions.jsonl",
        "type": "ledgar",
        "text_field": "text",
    },
    {
        "path": TRAINING_DATA_DIR / "embeddings/maud_clauses.jsonl",
        "type": "maud",
        "text_field": "text",
    },
    {
        "path": TRAINING_DATA_DIR / "embeddings/insurance_qa.jsonl",
        "type": "insurance_qa",
        "text_field": "text",
    },
]


class RAGIndexer:
    """Indexes insurance data into PostgreSQL via pgvector."""

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
        """Get a synchronous database engine for bulk operations."""
        if self._sync_engine is None:
            from app.config import settings
            # Convert async URL to sync
            sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
            if "postgresql://" in sync_url and "+psycopg2" not in sync_url:
                sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")
            from sqlalchemy import create_engine
            self._sync_engine = create_engine(sync_url, pool_pre_ping=True)
        return self._sync_engine

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
        return [emb.tolist() if isinstance(emb, np.ndarray) else list(emb) for emb in embeddings]

    def _embed_query(self, query: str) -> List[float]:
        """Generate embedding for a single query."""
        emb = self.embedding_model.encode(query, show_progress_bar=False)
        return emb.tolist() if isinstance(emb, np.ndarray) else list(emb)

    def _text_hash(self, text: str) -> str:
        """Generate a hash for deduplication."""
        return hashlib.sha256(text[:500].encode()).hexdigest()

    def get_collection_count(self) -> int:
        """Get the number of indexed vectors."""
        try:
            engine = self._get_sync_engine()
            from sqlalchemy import text
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM rag_vectors"))
                return result.scalar() or 0
        except Exception:
            return 0

    def is_indexed(self) -> bool:
        """Check if data has been indexed (threshold: 1000 records)."""
        return self.get_collection_count() > 1000

    def index_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Index all insurance datasets into PostgreSQL via pgvector.

        Args:
            force: If True, delete existing data and re-index.
        """
        if not self._load_model():
            return {"error": "Failed to load embedding model"}

        engine = self._get_sync_engine()
        from sqlalchemy import text

        if force:
            with engine.begin() as conn:
                conn.execute(text("TRUNCATE TABLE rag_vectors"))
                logger.info("Truncated rag_vectors table")

        if not force and self.is_indexed():
            count = self.get_collection_count()
            logger.info(f"Already indexed with {count} vectors. Use force=True to re-index.")
            return {"status": "already_indexed", "points": count}

        stats = {"total_indexed": 0, "errors": 0, "sources": {}}

        for source in RAG_SOURCES:
            source_path = source["path"]
            source_type = source["type"]

            if not source_path.exists():
                logger.warning(f"RAG source not found: {source_path}")
                continue

            logger.info(f"Indexing {source_type} from {source_path.name}...")
            source_count = 0
            batch_records = []

            with open(source_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        stats["errors"] += 1
                        continue

                    text = record.get("text", "")
                    if not text or len(text.strip()) < 10:
                        continue

                    batch_records.append((record, source_type))

                    if len(batch_records) >= BATCH_SIZE:
                        indexed = self._index_batch(engine, batch_records)
                        source_count += indexed
                        batch_records = []

                        if source_count % 1000 == 0:
                            logger.info(f"  ...indexed {source_count} {source_type} records")

            # Index remaining batch
            if batch_records:
                indexed = self._index_batch(engine, batch_records)
                source_count += indexed

            stats["sources"][source_type] = source_count
            stats["total_indexed"] += source_count
            logger.info(f"Indexed {source_count} {source_type} records")

        stats["status"] = "completed"
        logger.info(f"RAG indexing complete: {stats['total_indexed']} total, {stats['errors']} errors")
        return stats

    def _index_batch(self, engine, batch_records: List) -> int:
        """Index a batch of records into rag_vectors."""
        from sqlalchemy import text as sql_text

        texts = []
        records_to_insert = []

        for record, source_type in batch_records:
            raw_text = record.get("text", "")
            embed_text = raw_text[:512]
            full_text = raw_text[:2000]
            text_hash = self._text_hash(raw_text)

            metadata = record.get("metadata", {})
            category = record.get("category", "")
            source = record.get("source", "")
            name = metadata.get("name", "") if isinstance(metadata, dict) else ""

            texts.append(embed_text)
            records_to_insert.append({
                "text_hash": text_hash,
                "text_preview": embed_text,
                "full_text": full_text,
                "doc_type": source_type,
                "category": category,
                "source": source,
                "name": name,
                "embedding": None,  # filled below
                "created_at": datetime.now(timezone.utc),
            })

        try:
            embeddings = self._embed_texts(texts)
            for i, emb in enumerate(embeddings):
                records_to_insert[i]["embedding"] = str(emb)

            with engine.begin() as conn:
                for rec in records_to_insert:
                    try:
                        conn.execute(sql_text("""
                            INSERT INTO rag_vectors
                                (text_hash, text_preview, full_text, doc_type, category, source, name, embedding, created_at)
                            VALUES
                                (:text_hash, :text_preview, :full_text, :doc_type, :category, :source, :name, :embedding, :created_at)
                            ON CONFLICT (text_hash) DO NOTHING
                        """), rec)
                    except Exception:
                        pass  # skip duplicates

            return len(records_to_insert)
        except Exception as e:
            logger.error(f"Error indexing batch: {e}")
            return 0

    def search(self, query: str, top_k: int = 5, doc_type: Optional[str] = None) -> List[Dict]:
        """
        Semantic search over indexed insurance data using pgvector cosine similarity.

        Args:
            query: Search query text.
            top_k: Number of results.
            doc_type: Optional filter (acord, cuad, underwriting_block).

        Returns:
            List of results with text, metadata, and score.
        """
        if not self._load_model():
            return []

        try:
            query_vector = self._embed_query(query)
            engine = self._get_sync_engine()
            from sqlalchemy import text as sql_text

            if doc_type:
                sql = sql_text("""
                    SELECT full_text, doc_type, category, source, name, question,
                           1 - (embedding <=> :query_vec) AS score
                    FROM rag_vectors
                    WHERE doc_type = :doc_type
                    ORDER BY embedding <=> :query_vec
                    LIMIT :limit
                """)
                params = {"query_vec": str(query_vector), "doc_type": doc_type, "limit": top_k}
            else:
                sql = sql_text("""
                    SELECT full_text, doc_type, category, source, name, question,
                           1 - (embedding <=> :query_vec) AS score
                    FROM rag_vectors
                    ORDER BY embedding <=> :query_vec
                    LIMIT :limit
                """)
                params = {"query_vec": str(query_vector), "limit": top_k}

            with engine.connect() as conn:
                result = conn.execute(sql, params)
                rows = result.fetchall()

            return [
                {
                    "text": row[0] or "",
                    "type": row[1] or "",
                    "category": row[2] or "",
                    "source": row[3] or "knowledge_base",
                    "name": row[4] or "",
                    "question": row[5] or "",
                    "score": float(row[6]) if row[6] else 0,
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"pgvector search error: {e}")
            return []

    def add_documents(self, documents: List[Dict[str, Any]], doc_type: str = "claim") -> int:
        """Add new documents to the index (e.g., claims data)."""
        if not self._load_model():
            return 0

        engine = self._get_sync_engine()
        batch_records = [(doc, doc_type) for doc in documents if doc.get("text", "").strip()]

        count = 0
        for i in range(0, len(batch_records), BATCH_SIZE):
            batch = batch_records[i:i + BATCH_SIZE]
            count += self._index_batch(engine, batch)

        logger.info(f"Added {count} {doc_type} documents to index")
        return count


# Singleton
rag_indexer = RAGIndexer()
