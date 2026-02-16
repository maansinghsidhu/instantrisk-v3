"""
AWS SageMaker Processing Job - Compute embeddings with GPU for speed.

Launches a SageMaker Processing job with ml.g4dn.xlarge (GPU instance):
- Uploads JSONL files to S3
- Runs embedding computation on GPU
- Downloads computed embeddings back to S3
- Optionally downloads to local

Cost: ~$0.50 for ~2 hours of compute time
"""

import boto3
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Paths
BASE_DIR = Path(__file__).parent.parent
INPUT_DIR = BASE_DIR / "app" / "data" / "training_data" / "embeddings"
OUTPUT_DIR = INPUT_DIR / "computed"

# AWS settings
REGION = "us-east-1"
S3_BUCKET = "instantrisk-pipeline-artifacts-995306061991"
S3_PREFIX = "embeddings/input"
S3_OUTPUT_PREFIX = "embeddings/computed"

# Sag

eMaker settings
ROLE_ARN = "arn:aws:iam::995306061991:role/SageMakerExecutionRole"  # Update with your role
INSTANCE_TYPE = "ml.g4dn.xlarge"  # GPU instance, cost-effective
INSTANCE_COUNT = 1


def upload_to_s3(local_dir: Path, s3_bucket: str, s3_prefix: str):
    """Upload JSONL files to S3."""
    s3 = boto3.client("s3", region_name=REGION)

    jsonl_files = list(local_dir.glob("*.jsonl"))
    print(f"Uploading {len(jsonl_files)} JSONL files to s3://{s3_bucket}/{s3_prefix}/")

    for file in jsonl_files:
        s3_key = f"{s3_prefix}/{file.name}"
        print(f"  Uploading {file.name}...")
        s3.upload_file(str(file), s3_bucket, s3_key)
        print(f"    → s3://{s3_bucket}/{s3_key}")

    return len(jsonl_files)


def create_processing_script():
    """Create the processing script that runs on SageMaker."""
    script = '''#!/usr/bin/env python3
import json
import os
import sys
import numpy as np
import hashlib
from pathlib import Path

# Install dependencies
print("Installing dependencies...")
os.system("pip install -q sentence-transformers torch transformers")

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "llmware/industry-bert-insurance-v0.1"
BATCH_SIZE = 128  # GPU can handle larger batches

def load_model():
    print(f"Loading model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    model = model.to(device)
    return model

def process_file(model, input_file, output_file):
    print(f"Processing: {input_file.name}")

    # Read records
    records = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    print(f"  Loaded {len(records):,} records")

    # Extract text
    texts = []
    metadata = []

    for record in records:
        text = record.get("text", "")[:512]
        full_text = record.get("text", "")[:2000]
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        texts.append(text)
        metadata.append({
            "text_hash": text_hash,
            "text_preview": text,
            "full_text": full_text,
            "category": record.get("category", ""),
            "source": record.get("source", ""),
            "metadata": record.get("metadata", {}),
        })

    # Compute embeddings
    print(f"  Computing embeddings (batch_size={BATCH_SIZE})...")
    embeddings = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=True, convert_to_numpy=True)

    print(f"  Computed {embeddings.shape[0]:,} embeddings")

    # Save
    os.makedirs(output_file.parent, exist_ok=True)
    np.savez_compressed(
        output_file,
        embeddings=embeddings,
        metadata=json.dumps(metadata),
    )

    print(f"  Saved: {output_file}")
    return len(embeddings)

def main():
    input_dir = Path("/opt/ml/processing/input")
    output_dir = Path("/opt/ml/processing/output")

    jsonl_files = list(input_dir.glob("*.jsonl"))
    print(f"Found {len(jsonl_files)} JSONL files")

    model = load_model()

    results = {}
    for jsonl_file in sorted(jsonl_files):
        output_file = output_dir / f"{jsonl_file.stem}.npz"
        count = process_file(model, jsonl_file, output_file)
        results[jsonl_file.stem] = count

    print("\\n" + "=" * 60)
    print("EMBEDDING COMPUTATION COMPLETE")
    print("=" * 60)
    for name, count in results.items():
        print(f"  {name}: {count:,} embeddings")
    print(f"Total: {sum(results.values()):,} embeddings")

    return 0

if __name__ == "__main__":
    sys.exit(main())
'''

    script_path = BASE_DIR / "scripts" / "sagemaker_embed.py"
    with open(script_path, "w") as f:
        f.write(script)

    return script_path


def launch_sagemaker_job():
    """Launch SageMaker Processing job."""
    sagemaker = boto3.client("sagemaker", region_name=REGION)

    job_name = f"instantrisk-embeddings-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    print(f"\nLaunching SageMaker Processing job: {job_name}")
    print(f"  Instance: {INSTANCE_TYPE}")
    print(f"  Input: s3://{S3_BUCKET}/{S3_PREFIX}/")
    print(f"  Output: s3://{S3_BUCKET}/{S3_OUTPUT_PREFIX}/")

    processing_config = {
        "ProcessingJobName": job_name,
        "RoleArn": ROLE_ARN,
        "ProcessingResources": {
            "ClusterConfig": {
                "InstanceCount": INSTANCE_COUNT,
                "InstanceType": INSTANCE_TYPE,
                "VolumeSizeInGB": 30,
            }
        },
        "AppSpecification": {
            "ImageUri": f"763104351884.dkr.ecr.{REGION}.amazonaws.com/pytorch-training:2.0.1-gpu-py310",
            "ContainerEntrypoint": ["python3", "/opt/ml/processing/input/code/sagemaker_embed.py"],
        },
        "ProcessingInputs": [
            {
                "InputName": "data",
                "S3Input": {
                    "S3Uri": f"s3://{S3_BUCKET}/{S3_PREFIX}/",
                    "LocalPath": "/opt/ml/processing/input",
                    "S3DataType": "S3Prefix",
                    "S3InputMode": "File",
                }
            },
            {
                "InputName": "code",
                "S3Input": {
                    "S3Uri": f"s3://{S3_BUCKET}/code/sagemaker_embed.py",
                    "LocalPath": "/opt/ml/processing/input/code",
                    "S3DataType": "S3Prefix",
                    "S3InputMode": "File",
                }
            },
        ],
        "ProcessingOutputConfig": {
            "Outputs": [
                {
                    "OutputName": "embeddings",
                    "S3Output": {
                        "S3Uri": f"s3://{S3_BUCKET}/{S3_OUTPUT_PREFIX}/",
                        "LocalPath": "/opt/ml/processing/output",
                        "S3UploadMode": "EndOfJob",
                    }
                }
            ]
        },
        "StoppingCondition": {
            "MaxRuntimeInSeconds": 7200,  # 2 hours max
        },
    }

    response = sagemaker.create_processing_job(**processing_config)

    print(f"\n✓ Job launched: {job_name}")
    print(f"  Status: https://console.aws.amazon.com/sagemaker/home?region={REGION}#/processing-jobs/{job_name}")
    print(f"\nMonitoring job (this may take 10-30 minutes)...")

    # Wait for completion
    waiter = sagemaker.get_waiter("processing_job_completed_or_stopped")
    waiter.wait(ProcessingJobName=job_name)

    # Get final status
    response = sagemaker.describe_processing_job(ProcessingJobName=job_name)
    status = response["ProcessingJobStatus"]

    if status == "Completed":
        print(f"\n✓ Job completed successfully!")
        print(f"  Output: s3://{S3_BUCKET}/{S3_OUTPUT_PREFIX}/")
        return True
    else:
        print(f"\n✗ Job failed with status: {status}")
        if "FailureReason" in response:
            print(f"  Reason: {response['FailureReason']}")
        return False


def download_from_s3(s3_bucket: str, s3_prefix: str, local_dir: Path):
    """Download computed embeddings from S3."""
    s3 = boto3.client("s3", region_name=REGION)

    os.makedirs(local_dir, exist_ok=True)

    # List all .npz files
    response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=s3_prefix)

    if "Contents" not in response:
        print("No output files found")
        return 0

    count = 0
    for obj in response["Contents"]:
        key = obj["Key"]
        if key.endswith(".npz"):
            filename = Path(key).name
            local_file = local_dir / filename
            print(f"  Downloading {filename}...")
            s3.download_file(s3_bucket, key, str(local_file))
            count += 1

    return count


def main():
    print("=" * 70)
    print("AWS SAGEMAKER EMBEDDING COMPUTATION")
    print("=" * 70)

    # Step 1: Upload JSONL files to S3
    print("\n[1/5] Uploading JSONL files to S3...")
    file_count = upload_to_s3(INPUT_DIR, S3_BUCKET, S3_PREFIX)
    print(f"✓ Uploaded {file_count} files")

    # Step 2: Create processing script
    print("\n[2/5] Creating processing script...")
    script_path = create_processing_script()
    print(f"✓ Created {script_path}")

    # Upload script to S3
    s3 = boto3.client("s3", region_name=REGION)
    s3.upload_file(str(script_path), S3_BUCKET, "code/sagemaker_embed.py")
    print(f"✓ Uploaded to s3://{S3_BUCKET}/code/sagemaker_embed.py")

    # Step 3: Launch SageMaker job
    print("\n[3/5] Launching SageMaker Processing job...")
    success = launch_sagemaker_job()

    if not success:
        print("\n✗ Job failed. Check CloudWatch logs for details.")
        return 1

    # Step 4: Download results
    print("\n[4/5] Downloading computed embeddings...")
    count = download_from_s3(S3_BUCKET, S3_OUTPUT_PREFIX, OUTPUT_DIR)
    print(f"✓ Downloaded {count} embedding files")

    # Step 5: Summary
    print("\n[5/5] Complete!")
    print("=" * 70)
    print(f"Computed embeddings saved to: {OUTPUT_DIR}")
    print(f"S3 location: s3://{S3_BUCKET}/{S3_OUTPUT_PREFIX}/")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
