"""
pgvector Models — Replaces Qdrant collections with PostgreSQL tables.

Three tables:
1. rag_vectors — main knowledge base (ACORD, CUAD, JeTech)
2. user_doc_vectors — per-user uploaded training documents
3. ref_doc_vectors — reference documents for RAG-enhanced doc gen
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class RAGVector(Base):
    __tablename__ = "rag_vectors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    text_hash = Column(String(64), unique=True, nullable=False)
    text_preview = Column(Text)       # first 512 chars (used for embedding)
    full_text = Column(Text)          # up to 2000 chars (returned in search)
    doc_type = Column(String(50), index=True)  # acord, cuad, underwriting_block
    category = Column(String(100))
    source = Column(String(100))
    name = Column(String(200))
    question = Column(String(500))    # for QA type records
    embedding = Column(Vector(768), nullable=False)
    created_at = Column(DateTime)

    __table_args__ = (
        Index("ix_rag_vectors_embedding_hnsw", "embedding",
              postgresql_using="hnsw",
              postgresql_with={"m": 16, "ef_construction": 64},
              postgresql_ops={"embedding": "vector_cosine_ops"}),
    )


class UserDocVector(Base):
    __tablename__ = "user_doc_vectors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), index=True, nullable=False)
    doc_id = Column(String(36), index=True, nullable=False)
    filename = Column(String(255))
    category = Column(String(100))
    content_type = Column(String(100))
    size_bytes = Column(Integer)
    chunk_index = Column(Integer)
    chunk_count = Column(Integer)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=False)
    uploaded_at = Column(DateTime)

    __table_args__ = (
        Index("ix_user_doc_vectors_embedding_hnsw", "embedding",
              postgresql_using="hnsw",
              postgresql_with={"m": 16, "ef_construction": 64},
              postgresql_ops={"embedding": "vector_cosine_ops"}),
    )


class RefDocVector(Base):
    __tablename__ = "ref_doc_vectors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, index=True)
    chunk_index = Column(Integer)
    chunk_text = Column(Text)
    category = Column(String(100))
    risk_categories = Column(JSONB)
    title = Column(String(255))
    file_name = Column(String(255))
    embedding = Column(Vector(768), nullable=False)
    created_at = Column(DateTime)

    __table_args__ = (
        Index("ix_ref_doc_vectors_embedding_hnsw", "embedding",
              postgresql_using="hnsw",
              postgresql_with={"m": 16, "ef_construction": 64},
              postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
