"""
Precompute embeddings for all training datasets using insurance-BERT.

Uses sentence-transformers with llmware/industry-bert-insurance-v0.1 (768-dim).
Can run locally or on AWS (SageMaker Processing, EC2 with GPU).

For speed: Use AWS EC2 with GPU (g4dn.xlarge or g5.xlarge recommended).
"""

import json
import os
import sys
import logging
import numpy as np
import hashlib
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
INPUT_DIR = BASE_DIR / "app" / "data" / "training_data" / "embeddings"
OUTPUT_DIR = INPUT_DIR / "computed"

# Model settings
EMBEDDING_MODEL = "llmware/industry-bert-insurance-v0.1"
EMBEDDING_DIM = 768
BATCH_SIZE = 64  # Adjust based on available memory


def load_model():
    """Load the embedding model."""
    from sentence_transformers import SentenceTransformer

    logger.info(f"Loading model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    logger.info(f"Model loaded. Embedding dimension: {EMBEDDING_DIM}")

    # Check if GPU is available
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    if device == "cuda":
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")

    model = model.to(device)
    return model


def compute_embeddings_for_file(model, input_file: Path, output_file: Path):
    """
    Compute embeddings for a single JSONL file.

    Saves as .npz with:
    - embeddings: numpy array of shape (N, 768)
    - metadata: JSON array with text_hash, text_preview, category, source
    """
    logger.info(f"Processing: {input_file.name}")

    # Read all records
    records = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    if not records:
        logger.warning(f"No records in {input_file.name}")
        return 0

    logger.info(f"  Loaded {len(records):,} records")

    # Extract text for embedding
    texts = []
    metadata = []

    for record in records:
        text = record.get("text", "")[:512]  # First 512 chars for embedding
        full_text = record.get("text", "")[:2000]  # Full text up to 2000 chars

        # Compute text hash for deduplication
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()

        texts.append(text)
        metadata.append({
            "text_hash": text_hash,
            "text_preview": text,
            "full_text": full_text,
            "category": record.get("category", ""),
            "source": record.get("source", ""),
            "metadata": record.get("metadata", {}),
        })

    # Compute embeddings in batches
    logger.info(f"  Computing embeddings (batch_size={BATCH_SIZE})...")
    embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i+BATCH_SIZE]
        batch_embeddings = model.encode(batch, show_progress_bar=False, convert_to_numpy=True)
        embeddings.append(batch_embeddings)

        if (i // BATCH_SIZE + 1) % 10 == 0:
            logger.info(f"    Processed {i+len(batch):,} / {len(texts):,} ({100*(i+len(batch))/len(texts):.1f}%)")

    embeddings = np.vstack(embeddings)
    logger.info(f"  Computed {embeddings.shape[0]:,} embeddings of dimension {embeddings.shape[1]}")

    # Save as .npz
    os.makedirs(output_file.parent, exist_ok=True)
    np.savez_compressed(
        output_file,
        embeddings=embeddings,
        metadata=json.dumps(metadata),  # Store as JSON string
    )

    # Also save metadata as separate JSON for easy inspection
    metadata_file = output_file.with_suffix('.json')
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"  Saved: {output_file}")
    logger.info(f"  Size: {output_file.stat().st_size / 1024 / 1024:.1f} MB")

    return len(embeddings)


def main():
    """Compute embeddings for all JSONL files."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Find all JSONL files
    jsonl_files = list(INPUT_DIR.glob("*.jsonl"))

    if not jsonl_files:
        logger.error(f"No .jsonl files found in {INPUT_DIR}")
        logger.info("Run process_raw_datasets.py or download_datasets.py first")
        return 1

    logger.info(f"Found {len(jsonl_files)} JSONL files to process")

    # Load model once
    model = load_model()

    # Process each file
    results = {}
    start_time = datetime.now()

    for jsonl_file in sorted(jsonl_files):
        output_file = OUTPUT_DIR / f"{jsonl_file.stem}.npz"

        # Skip if already computed (unless --force flag)
        if output_file.exists() and "--force" not in sys.argv:
            logger.info(f"Skipping {jsonl_file.name} (already computed)")
            # Load count from metadata
            with np.load(output_file, allow_pickle=True) as data:
                metadata = json.loads(str(data["metadata"]))
                results[jsonl_file.stem] = len(metadata)
            continue

        try:
            count = compute_embeddings_for_file(model, jsonl_file, output_file)
            results[jsonl_file.stem] = count
        except Exception as e:
            logger.error(f"Failed to process {jsonl_file.name}: {e}")
            results[jsonl_file.stem] = 0

    elapsed = datetime.now() - start_time

    # Summary
    print("\n" + "=" * 70)
    print("EMBEDDING COMPUTATION SUMMARY")
    print("=" * 70)
    for name, count in sorted(results.items()):
        status = "✓" if count > 0 else "✗"
        print(f"  {status} {name}: {count:,} embeddings")
    print(f"\n  Total: {sum(results.values()):,} embeddings")
    print(f"  Time: {elapsed}")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 70)

    return 0 if sum(results.values()) > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
