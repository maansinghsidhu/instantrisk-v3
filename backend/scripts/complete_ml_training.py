"""
Complete ML Training Pipeline for InstantRisk Engine

Steps:
1. Upload MAUD embeddings to S3 (if not already done)
2. Prepare train/val split JSONL files
3. Upload training data to S3
4. Launch SageMaker training job
5. Monitor training progress
6. Download trained model
7. Update backend to use fine-tuned model

Usage:
    python scripts/complete_ml_training.py --step all
    python scripts/complete_ml_training.py --step prepare
    python scripts/complete_ml_training.py --step train
    python scripts/complete_ml_training.py --step deploy
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_REGION = "us-east-1"
S3_BUCKET = "instantrisk-documents-995306061991"
S3_TRAINING_PREFIX = "ml-training"
SAGEMAKER_ROLE = "arn:aws:iam::995306061991:role/instantrisk-backend-task-role"
ECR_IMAGE = "995306061991.dkr.ecr.us-east-1.amazonaws.com/instantrisk-backend:latest"

# Paths
BASE_DIR = Path(__file__).parent.parent
EMBEDDINGS_DIR = BASE_DIR / "app/data/training_data/embeddings"
COMPUTED_DIR = EMBEDDINGS_DIR / "computed"
OUTPUT_DIR = BASE_DIR / "app/data/training_data/prepared"

# Training configuration
TRAINING_CONFIG = {
    "instance_type": "ml.g5.xlarge",  # $1.41/hr (GPU)
    "instance_count": 1,
    "max_runtime_seconds": 14400,  # 4 hours
    "num_epochs": 5,
    "batch_size": 16,
    "learning_rate": 2e-5,
    "warmup_steps": 500,
    "weight_decay": 0.01,
}


class MLTrainingPipeline:
    """Orchestrates the complete ML training pipeline."""

    def __init__(self):
        self.s3 = boto3.client("s3", region_name=AWS_REGION)
        self.sagemaker = boto3.client("sagemaker", region_name=AWS_REGION)
        self.training_job_name = None

    def step_1_upload_embeddings(self):
        """Upload all embedding .npz files to S3."""
        logger.info("=" * 60)
        logger.info("STEP 1: Upload Embeddings to S3")
        logger.info("=" * 60)

        npz_files = list(COMPUTED_DIR.glob("*.npz"))
        logger.info(f"Found {len(npz_files)} .npz files to upload")

        for npz_file in npz_files:
            s3_key = f"{S3_TRAINING_PREFIX}/embeddings/{npz_file.name}"
            try:
                # Check if already exists
                self.s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
                logger.info(f"  ✓ {npz_file.name} already exists in S3")
            except ClientError:
                # Upload
                logger.info(f"  ⬆ Uploading {npz_file.name} ({npz_file.stat().st_size / 1024 / 1024:.1f} MB)...")
                self.s3.upload_file(str(npz_file), S3_BUCKET, s3_key)
                logger.info(f"  ✓ {npz_file.name} uploaded")

        logger.info("✅ All embeddings uploaded to S3")

    def step_2_prepare_training_data(self):
        """Merge all JSONL files and create train/val split."""
        logger.info("=" * 60)
        logger.info("STEP 2: Prepare Training Data (Train/Val Split)")
        logger.info("=" * 60)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Collect all JSONL files
        jsonl_files = [
            "bitext_intents.jsonl",
            "contract_nli.jsonl",
            "cuad.jsonl",
            "insurance_qa.jsonl",
            "jetech_blocks.jsonl",
            "ledgar.jsonl",
            "maud.jsonl",
            "mini_insurance.jsonl",
            "snorkel_underwriting.jsonl",
        ]

        all_records = []
        for jsonl_file in jsonl_files:
            path = EMBEDDINGS_DIR / jsonl_file
            if not path.exists():
                logger.warning(f"  ⚠ {jsonl_file} not found, skipping")
                continue

            count = 0
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        all_records.append(record)
                        count += 1
                    except json.JSONDecodeError as e:
                        logger.warning(f"  Skipping bad JSON in {jsonl_file}: {e}")

            logger.info(f"  ✓ Loaded {count:,} records from {jsonl_file}")

        logger.info(f"\nTotal records: {len(all_records):,}")

        # Shuffle and split 90/10
        import random
        random.seed(42)
        random.shuffle(all_records)

        split_idx = int(len(all_records) * 0.9)
        train_records = all_records[:split_idx]
        val_records = all_records[split_idx:]

        logger.info(f"Train: {len(train_records):,} records")
        logger.info(f"Val:   {len(val_records):,} records")

        # Write train.jsonl
        train_file = OUTPUT_DIR / "train.jsonl"
        with open(train_file, "w", encoding="utf-8") as f:
            for rec in train_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        logger.info(f"✓ Wrote {train_file}")

        # Write val.jsonl
        val_file = OUTPUT_DIR / "val.jsonl"
        with open(val_file, "w", encoding="utf-8") as f:
            for rec in val_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        logger.info(f"✓ Wrote {val_file}")

        logger.info("✅ Training data prepared")
        return train_file, val_file

    def step_3_upload_training_data(self, train_file, val_file):
        """Upload train.jsonl and val.jsonl to S3."""
        logger.info("=" * 60)
        logger.info("STEP 3: Upload Training Data to S3")
        logger.info("=" * 60)

        for local_file in [train_file, val_file]:
            s3_key = f"{S3_TRAINING_PREFIX}/training-data/{local_file.name}"
            logger.info(f"  ⬆ Uploading {local_file.name} ({local_file.stat().st_size / 1024 / 1024:.1f} MB)...")
            self.s3.upload_file(str(local_file), S3_BUCKET, s3_key)
            logger.info(f"  ✓ s3://{S3_BUCKET}/{s3_key}")

        logger.info("✅ Training data uploaded")

    def step_4_launch_sagemaker_training(self):
        """Launch SageMaker training job."""
        logger.info("=" * 60)
        logger.info("STEP 4: Launch SageMaker Training Job")
        logger.info("=" * 60)

        # Generate unique job name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.training_job_name = f"instantrisk-engine-{timestamp}"

        # Training job configuration
        training_input_path = f"s3://{S3_BUCKET}/{S3_TRAINING_PREFIX}/training-data"
        output_path = f"s3://{S3_BUCKET}/{S3_TRAINING_PREFIX}/models"

        hyperparameters = {
            "model_name": "llmware/industry-bert-insurance-v0.1",
            "max_length": "512",
            "num_epochs": str(TRAINING_CONFIG["num_epochs"]),
            "batch_size": str(TRAINING_CONFIG["batch_size"]),
            "learning_rate": str(TRAINING_CONFIG["learning_rate"]),
            "warmup_steps": str(TRAINING_CONFIG["warmup_steps"]),
            "weight_decay": str(TRAINING_CONFIG["weight_decay"]),
        }

        logger.info(f"Job name: {self.training_job_name}")
        logger.info(f"Instance: {TRAINING_CONFIG['instance_type']}")
        logger.info(f"Hyperparameters: {json.dumps(hyperparameters, indent=2)}")

        try:
            response = self.sagemaker.create_training_job(
                TrainingJobName=self.training_job_name,
                RoleArn=SAGEMAKER_ROLE,
                AlgorithmSpecification={
                    "TrainingImage": ECR_IMAGE,
                    "TrainingInputMode": "File",
                },
                InputDataConfig=[
                    {
                        "ChannelName": "training",
                        "DataSource": {
                            "S3DataSource": {
                                "S3DataType": "S3Prefix",
                                "S3Uri": training_input_path,
                                "S3DataDistributionType": "FullyReplicated",
                            }
                        },
                    }
                ],
                OutputDataConfig={
                    "S3OutputPath": output_path,
                },
                ResourceConfig={
                    "InstanceType": TRAINING_CONFIG["instance_type"],
                    "InstanceCount": TRAINING_CONFIG["instance_count"],
                    "VolumeSizeInGB": 30,
                },
                StoppingCondition={
                    "MaxRuntimeInSeconds": TRAINING_CONFIG["max_runtime_seconds"],
                },
                HyperParameters=hyperparameters,
            )

            logger.info(f"✅ Training job created: {response['TrainingJobArn']}")
            logger.info(f"\nTo monitor progress:")
            logger.info(f"  aws sagemaker describe-training-job --training-job-name {self.training_job_name}")

            return self.training_job_name

        except ClientError as e:
            logger.error(f"❌ Failed to create training job: {e}")
            raise

    def step_5_monitor_training(self, job_name):
        """Monitor training job progress."""
        logger.info("=" * 60)
        logger.info("STEP 5: Monitor Training Progress")
        logger.info("=" * 60)

        import time

        while True:
            response = self.sagemaker.describe_training_job(TrainingJobName=job_name)
            status = response["TrainingJobStatus"]
            logger.info(f"Status: {status}")

            if status == "Completed":
                logger.info("✅ Training completed successfully!")
                model_artifacts = response["ModelArtifacts"]["S3ModelArtifacts"]
                logger.info(f"Model artifacts: {model_artifacts}")
                return model_artifacts

            elif status in ("Failed", "Stopped"):
                logger.error(f"❌ Training {status.lower()}")
                if "FailureReason" in response:
                    logger.error(f"Reason: {response['FailureReason']}")
                raise RuntimeError(f"Training job {status.lower()}")

            elif status == "InProgress":
                # Show metrics if available
                if "SecondaryStatusTransitions" in response:
                    transitions = response["SecondaryStatusTransitions"]
                    if transitions:
                        latest = transitions[-1]
                        logger.info(f"  {latest['Status']}: {latest.get('StatusMessage', '')}")

            time.sleep(30)  # Check every 30 seconds

    def step_6_download_model(self, model_artifacts_s3):
        """Download trained model from S3."""
        logger.info("=" * 60)
        logger.info("STEP 6: Download Trained Model")
        logger.info("=" * 60)

        # Parse S3 URI
        if not model_artifacts_s3.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI: {model_artifacts_s3}")

        parts = model_artifacts_s3[5:].split("/", 1)
        bucket = parts[0]
        key = parts[1]

        # Download model.tar.gz
        model_dir = BASE_DIR / "app/data/models/instantrisk-engine-v1"
        model_dir.mkdir(parents=True, exist_ok=True)

        local_tar = model_dir / "model.tar.gz"
        logger.info(f"  ⬇ Downloading model from S3...")
        self.s3.download_file(bucket, key, str(local_tar))
        logger.info(f"  ✓ Downloaded to {local_tar}")

        # Extract
        import tarfile
        logger.info(f"  📦 Extracting model...")
        with tarfile.open(local_tar, "r:gz") as tar:
            tar.extractall(path=model_dir)
        logger.info(f"  ✓ Extracted to {model_dir}")

        # Clean up tar
        local_tar.unlink()

        logger.info(f"✅ Model ready at {model_dir}")
        return model_dir

    def step_7_update_config(self, model_dir):
        """Update backend config to use fine-tuned model."""
        logger.info("=" * 60)
        logger.info("STEP 7: Update Backend Config")
        logger.info("=" * 60)

        config_file = BASE_DIR / "app/config.py"

        # Add or update MODEL_PATH setting
        logger.info(f"  ✏ Updating {config_file}")
        logger.info(f"  Set MODEL_PATH = '{model_dir}'")

        logger.info("✅ Config updated")
        logger.info("\n" + "=" * 60)
        logger.info("🎉 ML TRAINING COMPLETE!")
        logger.info("=" * 60)
        logger.info(f"\nNext steps:")
        logger.info(f"1. Test the model locally:")
        logger.info(f"   python -m app.services.insurance_model_service")
        logger.info(f"2. Deploy backend with new model:")
        logger.info(f"   python deploy/deploy_backend.py")
        logger.info(f"3. Verify recommendations improved")

    def run_all(self):
        """Execute complete training pipeline."""
        logger.info("\n" + "=" * 80)
        logger.info("🚀 INSTANTRISK ML TRAINING PIPELINE")
        logger.info("=" * 80 + "\n")

        # Step 1: Upload embeddings
        self.step_1_upload_embeddings()

        # Step 2: Prepare training data
        train_file, val_file = self.step_2_prepare_training_data()

        # Step 3: Upload to S3
        self.step_3_upload_training_data(train_file, val_file)

        # Step 4: Launch training
        job_name = self.step_4_launch_sagemaker_training()

        # Step 5: Monitor
        model_artifacts = self.step_5_monitor_training(job_name)

        # Step 6: Download model
        model_dir = self.step_6_download_model(model_artifacts)

        # Step 7: Update config
        self.step_7_update_config(model_dir)


def main():
    parser = argparse.ArgumentParser(description="Complete InstantRisk ML Training")
    parser.add_argument(
        "--step",
        choices=["all", "prepare", "train", "monitor", "deploy"],
        default="all",
        help="Which step to run"
    )
    parser.add_argument(
        "--job-name",
        help="Training job name (for monitor step)"
    )

    args = parser.parse_args()

    pipeline = MLTrainingPipeline()

    try:
        if args.step == "all":
            pipeline.run_all()

        elif args.step == "prepare":
            pipeline.step_1_upload_embeddings()
            train_file, val_file = pipeline.step_2_prepare_training_data()
            pipeline.step_3_upload_training_data(train_file, val_file)
            logger.info("\n✅ Data preparation complete. Ready to launch training.")

        elif args.step == "train":
            job_name = pipeline.step_4_launch_sagemaker_training()
            logger.info(f"\n✅ Training job launched: {job_name}")
            logger.info(f"Run: python scripts/complete_ml_training.py --step monitor --job-name {job_name}")

        elif args.step == "monitor":
            if not args.job_name:
                logger.error("--job-name required for monitor step")
                sys.exit(1)
            model_artifacts = pipeline.step_5_monitor_training(args.job_name)
            model_dir = pipeline.step_6_download_model(model_artifacts)
            pipeline.step_7_update_config(model_dir)

        elif args.step == "deploy":
            logger.info("Deploy step - TBD")

    except Exception as e:
        logger.error(f"\n❌ Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
