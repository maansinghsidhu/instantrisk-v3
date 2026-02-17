"""
Launch SageMaker Training Job for InstantRisk Engine

This script:
1. Prepares training data splits (80/10/10)
2. Creates sourcedir.tar.gz with training script + requirements
3. Uploads training data + sourcedir to S3
4. Launches SageMaker training job on ml.g5.xlarge GPU
5. Monitors job status
"""

import os
import json
import time
import tarfile
import tempfile
import boto3
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_REGION = "us-east-1"
AWS_ACCOUNT = "995306061991"
SAGEMAKER_ROLE_ARN = f"arn:aws:iam::{AWS_ACCOUNT}:role/SageMakerExecutionRole"
S3_BUCKET = f"instantrisk-documents-{AWS_ACCOUNT}"
S3_PREFIX = "ml-training"

# Training Configuration
INSTANCE_TYPE = "ml.g5.xlarge"  # GPU instance
INSTANCE_COUNT = 1
MAX_RUNTIME_SECONDS = 8 * 3600  # 8 hours (10 epochs with 157K records)
VOLUME_SIZE_GB = 50

# Model Configuration
BASE_MODEL = "llmware/industry-bert-insurance-v0.1"
NUM_EPOCHS = 10
BATCH_SIZE = 16
LEARNING_RATE = 2e-5


def prepare_training_data(base_dir):
    """
    Combine all JSONL files and create train/val/test splits.

    Args:
        base_dir: Path to backend directory

    Returns:
        Paths to train.jsonl, val.jsonl, test.jsonl
    """
    logger.info("Preparing training data splits...")

    embeddings_dir = Path(base_dir) / "app" / "data" / "training_data" / "embeddings"
    output_dir = Path(base_dir) / "app" / "data" / "training_data" / "splits"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect all JSONL files (exclude .bak files)
    all_data = []
    jsonl_files = [f for f in embeddings_dir.glob("*.jsonl") if ".bak" not in f.name]

    logger.info(f"Found {len(jsonl_files)} JSONL files")

    for jsonl_file in jsonl_files:
        count = 0
        logger.info(f"Loading {jsonl_file.name}...")
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    # Ensure required fields
                    if 'text' in data:
                        all_data.append(data)
                        count += 1
                except json.JSONDecodeError:
                    continue
        logger.info(f"  -> {count} records")

    logger.info(f"Total records: {len(all_data)}")

    # Shuffle and split
    import random
    random.seed(42)
    random.shuffle(all_data)

    total = len(all_data)
    train_end = int(0.8 * total)
    val_end = int(0.9 * total)

    train_data = all_data[:train_end]
    val_data = all_data[train_end:val_end]
    test_data = all_data[val_end:]

    logger.info(f"Train: {len(train_data)}, Val: {len(val_data)}, Test: {len(test_data)}")

    # Write splits
    train_file = output_dir / "train.jsonl"
    val_file = output_dir / "val.jsonl"
    test_file = output_dir / "test.jsonl"

    for file_path, data in [(train_file, train_data), (val_file, val_data), (test_file, test_data)]:
        with open(file_path, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(json.dumps(item) + '\n')
        logger.info(f"Wrote {file_path}")

    return train_file, val_file, test_file


def create_sourcedir_tarball(base_dir):
    """
    Create sourcedir.tar.gz containing training script + requirements.
    SageMaker training toolkit expects this format.
    """
    scripts_dir = Path(base_dir) / "scripts"
    tarball_path = scripts_dir / "sourcedir.tar.gz"

    with tarfile.open(tarball_path, "w:gz") as tar:
        # Add training script
        script_path = scripts_dir / "train_sagemaker.py"
        tar.add(str(script_path), arcname="train_sagemaker.py")
        logger.info(f"Added train_sagemaker.py to tarball")

        # Add requirements
        req_path = scripts_dir / "requirements_sagemaker.txt"
        tar.add(str(req_path), arcname="requirements.txt")
        logger.info(f"Added requirements.txt to tarball")

    logger.info(f"Created sourcedir tarball: {tarball_path} ({tarball_path.stat().st_size} bytes)")
    return tarball_path


def upload_to_s3(local_path, s3_path):
    """Upload file to S3."""
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    logger.info(f"Uploading {local_path} to s3://{S3_BUCKET}/{s3_path}")
    s3_client.upload_file(str(local_path), S3_BUCKET, s3_path)
    return f"s3://{S3_BUCKET}/{s3_path}"


def launch_training_job(base_dir):
    """Launch SageMaker training job."""
    logger.info("Launching SageMaker training job...")

    # 1. Prepare data splits
    train_file, val_file, test_file = prepare_training_data(base_dir)

    # 2. Upload training data to S3
    upload_to_s3(train_file, f"{S3_PREFIX}/training-data/train.jsonl")
    upload_to_s3(val_file, f"{S3_PREFIX}/training-data/val.jsonl")
    upload_to_s3(test_file, f"{S3_PREFIX}/training-data/test.jsonl")

    # 3. Create and upload sourcedir tarball
    tarball_path = create_sourcedir_tarball(base_dir)
    sourcedir_s3 = upload_to_s3(tarball_path, f"{S3_PREFIX}/code/sourcedir.tar.gz")

    # 4. Create SageMaker training job
    sagemaker_client = boto3.client('sagemaker', region_name=AWS_REGION)

    job_name = f"instantrisk-engine-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    training_params = {
        "TrainingJobName": job_name,
        "RoleArn": SAGEMAKER_ROLE_ARN,

        "AlgorithmSpecification": {
            "TrainingImage": f"763104351884.dkr.ecr.{AWS_REGION}.amazonaws.com/pytorch-training:2.1.0-gpu-py310",
            "TrainingInputMode": "File",
            "EnableSageMakerMetricsTimeSeries": True,
            "MetricDefinitions": [
                {"Name": "train:loss", "Regex": "Epoch \\d+ .* avg_loss=(\\S+)"},
                {"Name": "train:clause_loss", "Regex": "clause=(\\S+)"},
                {"Name": "train:appetite_loss", "Regex": "appetite=(\\S+)"},
                {"Name": "train:pricing_loss", "Regex": "pricing=(\\S+)"},
                {"Name": "train:intent_loss", "Regex": "intent=(\\S+)"},
                {"Name": "val:loss", "Regex": "Val .* avg_loss=(\\S+)"},
            ]
        },

        "InputDataConfig": [
            {
                "ChannelName": "training",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{S3_BUCKET}/{S3_PREFIX}/training-data/",
                        "S3DataDistributionType": "FullyReplicated"
                    }
                },
                "ContentType": "application/jsonl",
                "CompressionType": "None"
            }
        ],

        "OutputDataConfig": {
            "S3OutputPath": f"s3://{S3_BUCKET}/{S3_PREFIX}/output/"
        },

        "ResourceConfig": {
            "InstanceType": INSTANCE_TYPE,
            "InstanceCount": INSTANCE_COUNT,
            "VolumeSizeInGB": VOLUME_SIZE_GB
        },

        "StoppingCondition": {
            "MaxRuntimeInSeconds": MAX_RUNTIME_SECONDS
        },

        "HyperParameters": {
            "model_name": BASE_MODEL,
            "num_epochs": str(NUM_EPOCHS),
            "batch_size": str(BATCH_SIZE),
            "learning_rate": str(LEARNING_RATE),
            "sagemaker_program": "train_sagemaker.py",
            "sagemaker_submit_directory": sourcedir_s3
        },

        "EnableInterContainerTrafficEncryption": False,
        "EnableNetworkIsolation": False,
        "EnableManagedSpotTraining": False
    }

    logger.info(f"Creating training job: {job_name}")
    response = sagemaker_client.create_training_job(**training_params)

    logger.info(f"Training job ARN: {response['TrainingJobArn']}")
    logger.info(f"\nTraining job launched successfully!")
    logger.info(f"Job name: {job_name}")
    logger.info(f"Instance: {INSTANCE_TYPE}")
    logger.info(f"Epochs: {NUM_EPOCHS}")
    logger.info(f"Expected duration: 4-8 hours")
    logger.info(f"\nMonitor at: https://console.aws.amazon.com/sagemaker/home?region={AWS_REGION}#/jobs/{job_name}")

    return job_name


def monitor_job(job_name):
    """Monitor SageMaker job status."""
    sagemaker_client = boto3.client('sagemaker', region_name=AWS_REGION)

    logger.info(f"\nMonitoring job: {job_name}")
    logger.info("Status updates every 60 seconds...\n")

    while True:
        response = sagemaker_client.describe_training_job(TrainingJobName=job_name)
        status = response['TrainingJobStatus']
        secondary = response.get('SecondaryStatus', '')

        if status == 'Completed':
            logger.info(f"Training completed successfully!")
            logger.info(f"Model output: {response['ModelArtifacts']['S3ModelArtifacts']}")
            break
        elif status == 'Failed':
            logger.error(f"Training failed: {response.get('FailureReason', 'Unknown')}")
            break
        elif status == 'Stopped':
            logger.warning(f"Training stopped")
            break
        else:
            logger.info(f"Status: {status} ({secondary})")

        time.sleep(60)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python launch_sagemaker_training.py <backend_dir> [--monitor]")
        sys.exit(1)

    base_dir = sys.argv[1]
    monitor = "--monitor" in sys.argv

    try:
        job_name = launch_training_job(base_dir)

        if monitor:
            monitor_job(job_name)
        else:
            logger.info("\nTo monitor job, run:")
            logger.info(f"python {__file__} {base_dir} --monitor")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
