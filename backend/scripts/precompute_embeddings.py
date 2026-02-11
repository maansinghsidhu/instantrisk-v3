"""
Pre-compute embeddings for RAG datasets locally.

Reads JSONL files, generates 768-dim embeddings using llmware/industry-bert-insurance-v0.1,
and writes new JSONL files with "embedding" field included. This eliminates the need for
the Fargate task to compute embeddings at index time (30min -> 1min).

Usage:
    pip install sentence-transformers
    python scripts/precompute_embeddings.py
"""

import json
import os
import sys
import time
from pathlib import Path

# Add parent to path so we can find the data
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent
DATA_DIR = BACKEND_DIR / "app" / "data" / "training_data" / "embeddings"

EMBEDDING_MODEL = "llmware/industry-bert-insurance-v0.1"
BATCH_SIZE = 256  # Larger batches for local machine with more RAM

DATASETS = [
    "acord_clauses.jsonl",
    "cuad_clauses.jsonl",
    "jetech_blocks.jsonl",
    "ledgar_provisions.jsonl",
    "maud_clauses.jsonl",
    "insurance_qa.jsonl",
]


def main():
    from sentence_transformers import SentenceTransformer
    import numpy as np

    print(f"Loading model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"Model loaded. Embedding dim: {model.get_sentence_embedding_dimension()}")

    total_embedded = 0
    start_time = time.time()

    for filename in DATASETS:
        input_path = DATA_DIR / filename
        if not input_path.exists():
            print(f"SKIP: {filename} not found")
            continue

        # Read all records
        records = []
        texts = []
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = record.get("text", "")
                if not text or len(text.strip()) < 10:
                    continue
                records.append(record)
                texts.append(text[:512])  # Same truncation as rag_indexer

        print(f"\n{'='*60}")
        print(f"Embedding {filename}: {len(records)} records")
        print(f"{'='*60}")

        # Batch encode
        all_embeddings = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            embeddings = model.encode(batch, show_progress_bar=False, batch_size=BATCH_SIZE)
            all_embeddings.extend(embeddings)
            done = min(i + BATCH_SIZE, len(texts))
            pct = done / len(texts) * 100
            print(f"  {done}/{len(texts)} ({pct:.0f}%)", end="\r")

        print(f"  {len(texts)}/{len(texts)} (100%) - Done!")

        # Write back with embeddings
        output_path = input_path  # Overwrite in place
        with open(output_path, "w", encoding="utf-8") as f:
            for record, emb in zip(records, all_embeddings):
                if isinstance(emb, np.ndarray):
                    emb = emb.tolist()
                record["embedding"] = emb
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        file_size = output_path.stat().st_size / 1024 / 1024
        print(f"  Written: {output_path.name} ({file_size:.1f} MB)")
        total_embedded += len(records)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"COMPLETE: {total_embedded} records embedded in {elapsed:.0f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
