"""
Upload RAG source JSONL files to S3 for the rag_indexer to download on container startup.
Uploads to: s3://instantrisk-pipeline-artifacts-995306061991/training-data/
"""
import os
import boto3
from pathlib import Path

AWS_REGION = "us-east-1"
S3_BUCKET = "instantrisk-pipeline-artifacts-995306061991"
S3_PREFIX = "training-data"

BACKEND_DIR = Path(__file__).parent.parent / "backend"
EMBEDDINGS_DIR = BACKEND_DIR / "app" / "data" / "training_data" / "embeddings"

# The 6 RAG source files that rag_indexer.py expects
RAG_FILES = [
    "acord_clauses.jsonl",
    "cuad_clauses.jsonl",
    "jetech_blocks.jsonl",
    "ledgar_provisions.jsonl",
    "maud.jsonl",
    "insurance_qa.jsonl",
]

def main():
    s3 = boto3.client("s3", region_name=AWS_REGION)

    for filename in RAG_FILES:
        local_path = EMBEDDINGS_DIR / filename
        if not local_path.exists():
            print(f"  SKIP {filename} (not found)")
            continue

        s3_key = f"{S3_PREFIX}/{filename}"
        size_mb = local_path.stat().st_size / 1024 / 1024
        print(f"  Uploading {filename} ({size_mb:.1f} MB) to s3://{S3_BUCKET}/{s3_key}")
        s3.upload_file(str(local_path), S3_BUCKET, s3_key)
        print(f"  Done: {filename}")

    print("\nAll RAG files uploaded successfully!")


if __name__ == "__main__":
    main()
