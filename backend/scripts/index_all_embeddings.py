"""
Index all precomputed embeddings into PostgreSQL pgvector (rag_vectors table).

This script loads all .npz files from the computed embeddings directory and
indexes them into the rag_vectors table for RAG-based retrieval.

Supports:
- Batch insertion with SQLAlchemy
- Deduplication by text_hash
- Progress reporting
- Verification of indexing

Usage:
    python scripts/index_all_embeddings.py
"""

import json
import sys
import os
import logging
import numpy as np
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
EMBEDDINGS_DIR = BASE_DIR / "app" / "data" / "training_data" / "embeddings" / "computed"

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not set")
    sys.exit(1)

# Convert async URL to sync if needed
if "+asyncpg" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")

# Batch size for insertions
BATCH_SIZE = 500


def get_doc_type_from_filename(filename: str) -> str:
    """Map filename to doc_type for rag_vectors table."""
    mapping = {
        "bitext_intents": "intent",
        "insurance_qa": "qa",
        "jetech_blocks": "underwriting_block",
        "mini_insurance": "insurance_text",
    }

    for key, value in mapping.items():
        if key in filename:
            return value

    return "unknown"


def index_embeddings_file(session, npz_file: Path):
    """
    Index embeddings from a single .npz file into rag_vectors table.

    Args:
        session: SQLAlchemy session
        npz_file: Path to .npz file containing embeddings and metadata

    Returns:
        Number of records inserted
    """
    logger.info(f"Processing: {npz_file.name}")

    # Load embeddings and metadata
    with np.load(npz_file, allow_pickle=True) as data:
        embeddings = data["embeddings"]
        metadata_json = str(data["metadata"])
        metadata = json.loads(metadata_json)

    logger.info(f"  Loaded {len(embeddings):,} embeddings")

    # Determine doc_type from filename
    doc_type = get_doc_type_from_filename(npz_file.stem)
    logger.info(f"  Doc type: {doc_type}")

    # Prepare records for insertion
    records = []
    inserted_count = 0
    skipped_count = 0

    for i, (embedding, meta) in enumerate(zip(embeddings, metadata)):
        text_hash = meta.get("text_hash")
        text_preview = meta.get("text_preview", "")
        full_text = meta.get("full_text", text_preview)
        category = meta.get("category", "")
        source = meta.get("source", "")

        # Extract additional fields if available
        meta_dict = meta.get("metadata", {})
        name = meta_dict.get("name", "")
        question = meta_dict.get("question", "")

        # Convert embedding to list for PostgreSQL
        embedding_list = embedding.tolist()

        record = {
            "text_hash": text_hash,
            "text_preview": text_preview,
            "full_text": full_text,
            "doc_type": doc_type,
            "category": category,
            "source": source,
            "name": name,
            "question": question,
            "embedding": embedding_list,
            "created_at": datetime.utcnow(),
        }

        records.append(record)

        # Insert in batches
        if len(records) >= BATCH_SIZE:
            try:
                # Use INSERT ... ON CONFLICT DO NOTHING for deduplication
                stmt = text("""
                    INSERT INTO rag_vectors
                    (text_hash, text_preview, full_text, doc_type, category, source, name, question, embedding, created_at)
                    VALUES
                    (:text_hash, :text_preview, :full_text, :doc_type, :category, :source, :name, :question, :embedding, :created_at)
                    ON CONFLICT (text_hash) DO NOTHING
                """)

                result = session.execute(stmt, records)
                session.commit()

                # Track how many were actually inserted
                batch_inserted = result.rowcount
                inserted_count += batch_inserted
                skipped_count += len(records) - batch_inserted

                logger.info(f"    Progress: {i+1:,} / {len(embeddings):,} ({100*(i+1)/len(embeddings):.1f}%) - Inserted: {inserted_count:,}, Skipped: {skipped_count:,}")

            except Exception as e:
                logger.error(f"Failed to insert batch: {e}")
                session.rollback()

            records = []

    # Insert remaining records
    if records:
        try:
            stmt = text("""
                INSERT INTO rag_vectors
                (text_hash, text_preview, full_text, doc_type, category, source, name, question, embedding, created_at)
                VALUES
                (:text_hash, :text_preview, :full_text, :doc_type, :category, :source, :name, :question, :embedding, :created_at)
                ON CONFLICT (text_hash) DO NOTHING
            """)

            result = session.execute(stmt, records)
            session.commit()

            batch_inserted = result.rowcount
            inserted_count += batch_inserted
            skipped_count += len(records) - batch_inserted

        except Exception as e:
            logger.error(f"Failed to insert final batch: {e}")
            session.rollback()

    logger.info(f"  Completed: Inserted {inserted_count:,}, Skipped {skipped_count:,} (duplicates)")

    return inserted_count


def verify_indexing(session):
    """Verify that embeddings were indexed correctly."""
    logger.info("\nVerifying indexing...")

    # Count total vectors
    result = session.execute(text("SELECT COUNT(*) FROM rag_vectors"))
    total_count = result.scalar()
    logger.info(f"  Total vectors in rag_vectors: {total_count:,}")

    # Count by doc_type
    result = session.execute(text("""
        SELECT doc_type, COUNT(*) as count
        FROM rag_vectors
        GROUP BY doc_type
        ORDER BY count DESC
    """))

    logger.info("\n  Breakdown by doc_type:")
    for row in result:
        logger.info(f"    {row[0]}: {row[1]:,}")

    # Check if HNSW index exists
    result = session.execute(text("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'rag_vectors'
        AND indexname LIKE '%hnsw%'
    """))

    hnsw_indexes = result.fetchall()
    if hnsw_indexes:
        logger.info(f"\n  HNSW index found: {hnsw_indexes[0][0]}")
    else:
        logger.warning("\n  WARNING: No HNSW index found. Vector search may be slow.")
        logger.info("  Run migrations to create the HNSW index.")

    return total_count


def main():
    """Index all embeddings into rag_vectors table."""
    logger.info("=" * 70)
    logger.info("INDEXING EMBEDDINGS INTO PGVECTOR")
    logger.info("=" * 70)

    # Check if embeddings directory exists
    if not EMBEDDINGS_DIR.exists():
        logger.error(f"Embeddings directory not found: {EMBEDDINGS_DIR}")
        logger.info("Run precompute_embeddings.py first")
        return 1

    # Find all .npz files
    npz_files = list(EMBEDDINGS_DIR.glob("*.npz"))

    if not npz_files:
        logger.error(f"No .npz files found in {EMBEDDINGS_DIR}")
        logger.info("Run precompute_embeddings.py first")
        return 1

    logger.info(f"Found {len(npz_files)} .npz files to index")
    for f in sorted(npz_files):
        logger.info(f"  - {f.name}")

    # Create database engine and session
    logger.info(f"\nConnecting to database...")
    engine = create_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Test connection
    try:
        result = session.execute(text("SELECT version()"))
        version = result.scalar()
        logger.info(f"  PostgreSQL version: {version.split(',')[0]}")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return 1

    # Check if rag_vectors table exists
    try:
        result = session.execute(text("SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = 'rag_vectors')"))
        table_exists = result.scalar()

        if not table_exists:
            logger.error("rag_vectors table does not exist")
            logger.info("Run database migrations first: alembic upgrade head")
            return 1

        logger.info("  rag_vectors table found")

    except Exception as e:
        logger.error(f"Failed to check for rag_vectors table: {e}")
        return 1

    # Index each file
    total_inserted = 0
    start_time = datetime.now()

    for npz_file in sorted(npz_files):
        try:
            count = index_embeddings_file(session, npz_file)
            total_inserted += count
        except Exception as e:
            logger.error(f"Failed to index {npz_file.name}: {e}")

    elapsed = datetime.now() - start_time

    # Verify indexing
    total_count = verify_indexing(session)

    # Close session
    session.close()

    # Summary
    print("\n" + "=" * 70)
    print("INDEXING SUMMARY")
    print("=" * 70)
    print(f"  Files processed: {len(npz_files)}")
    print(f"  Records inserted: {total_inserted:,}")
    print(f"  Total vectors in DB: {total_count:,}")
    print(f"  Time: {elapsed}")
    print("=" * 70)

    if total_count > 0:
        logger.info("\nIndexing completed successfully!")
        return 0
    else:
        logger.error("\nIndexing failed - no vectors in database")
        return 1


if __name__ == "__main__":
    sys.exit(main())
