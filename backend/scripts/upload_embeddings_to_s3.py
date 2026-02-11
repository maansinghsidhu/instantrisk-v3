"""
Upload pre-computed embedding JSONL files to S3.

After running precompute_embeddings.py locally, run this to upload
the large JSONL files (with embeddings) to S3 so the Fargate indexer
can download them at index time instead of computing embeddings on CPU.

Usage:
    python scripts/upload_embeddings_to_s3.py
"""

import boto3
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent
DATA_DIR = BACKEND_DIR / "app" / "data" / "training_data" / "embeddings"

S3_BUCKET = "instantrisk-pipeline-artifacts-995306061991"
S3_PREFIX = "training-data/"
REGION = "us-east-1"

DATASETS = [
    "acord_clauses.jsonl",
    "cuad_clauses.jsonl",
    "jetech_blocks.jsonl",
    "ledgar_provisions.jsonl",
    "maud_clauses.jsonl",
    "insurance_qa.jsonl",
]


def main():
    s3 = boto3.client("s3", region_name=REGION)

    total_size = 0
    uploaded = 0

    for filename in DATASETS:
        local_path = DATA_DIR / filename
        if not local_path.exists():
            print(f"SKIP: {filename} not found")
            continue

        file_size = local_path.stat().st_size
        size_mb = file_size / 1024 / 1024

        # Only upload files that have embeddings (>10 MB indicates embeddings present)
        if size_mb < 10:
            print(f"SKIP: {filename} ({size_mb:.1f} MB) - too small, likely no embeddings")
            continue

        s3_key = f"{S3_PREFIX}{filename}"
        print(f"Uploading {filename} ({size_mb:.0f} MB) -> s3://{S3_BUCKET}/{s3_key}...")

        s3.upload_file(
            str(local_path),
            S3_BUCKET,
            s3_key,
            Callback=ProgressCallback(file_size, filename),
        )

        total_size += file_size
        uploaded += 1
        print(f"  Done: {filename}")

    print(f"\n{'='*60}")
    print(f"Uploaded {uploaded} files ({total_size / 1024 / 1024:.0f} MB total)")
    print(f"{'='*60}")


class ProgressCallback:
    def __init__(self, total_size, filename):
        self.total_size = total_size
        self.uploaded = 0
        self.filename = filename

    def __call__(self, bytes_amount):
        self.uploaded += bytes_amount
        pct = self.uploaded / self.total_size * 100
        mb = self.uploaded / 1024 / 1024
        total_mb = self.total_size / 1024 / 1024
        print(f"  {self.filename}: {mb:.0f}/{total_mb:.0f} MB ({pct:.0f}%)", end="\r")


if __name__ == "__main__":
    main()
