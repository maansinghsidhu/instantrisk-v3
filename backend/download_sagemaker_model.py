"""
Download and integrate the fine-tuned InstantRisk Engine model from SageMaker.

Usage:
    python download_sagemaker_model.py --job instantrisk-engine-20260217-195607

This script:
1. Checks the SageMaker training job status
2. Downloads model.tar.gz from S3 when training completes
3. Extracts to app/data/models/instantrisk-engine-v1-final/
4. Verifies model files (model.pt, config.json, tokenizer files)

Run with fresh AWS credentials (SSO or env vars).
"""

import argparse
import json
import os
import sys
import tarfile
import time

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
FINAL_MODEL_DIR = os.path.join(REPO_ROOT, "app", "data", "models", "instantrisk-engine-v1-final")
BEST_MODEL_DIR = os.path.join(REPO_ROOT, "app", "data", "models", "instantrisk-engine-v1-best")


def get_sagemaker_client():
    """Get boto3 SageMaker client using current credentials."""
    try:
        import boto3
        return boto3.client("sagemaker", region_name="us-east-1")
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3")
        sys.exit(1)


def check_job_status(job_name: str) -> dict:
    """Check SageMaker training job status and return full job info."""
    sm = get_sagemaker_client()
    try:
        resp = sm.describe_training_job(TrainingJobName=job_name)
        return {
            "status": resp["TrainingJobStatus"],
            "secondary_status": resp.get("SecondaryStatus", ""),
            "model_artifacts": resp.get("ModelArtifacts", {}).get("S3ModelArtifacts", ""),
            "failure_reason": resp.get("FailureReason", ""),
            "training_end_time": str(resp.get("TrainingEndTime", "")),
        }
    except Exception as e:
        print(f"ERROR checking job status: {e}")
        sys.exit(1)


def wait_for_completion(job_name: str, poll_interval: int = 300) -> str:
    """
    Poll SageMaker job every poll_interval seconds until completed.
    Returns the S3 model artifacts URI.
    """
    print(f"Monitoring job: {job_name}")
    print(f"Polling every {poll_interval} seconds...")

    while True:
        info = check_job_status(job_name)
        status = info["status"]
        secondary = info["secondary_status"]

        print(f"  [{time.strftime('%H:%M:%S')}] Status: {status} / {secondary}")

        if status == "Completed":
            print(f"Training completed! Model artifacts: {info['model_artifacts']}")
            return info["model_artifacts"]
        elif status in ("Failed", "Stopped"):
            print(f"Training {status}: {info['failure_reason']}")
            sys.exit(1)
        else:
            print(f"  Still training... waiting {poll_interval}s")
            time.sleep(poll_interval)


def download_and_extract(s3_uri: str, target_dir: str):
    """
    Download model.tar.gz from S3 and extract to target_dir.
    Handles nested directory structure from SageMaker output.
    """
    import boto3

    # Parse S3 URI
    parts = s3_uri.replace("s3://", "").split("/", 1)
    bucket = parts[0]
    key = parts[1]

    # Download
    local_tar = os.path.join(os.path.dirname(target_dir), "model.tar.gz")
    print(f"Downloading s3://{bucket}/{key} ...")
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.download_file(bucket, key, local_tar)
    print(f"Downloaded to {local_tar}")

    # Extract to a temp dir first
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"Extracting to {tmp_dir} ...")
        with tarfile.open(local_tar, "r:gz") as tar:
            tar.extractall(tmp_dir)

        # Find the model.pt file (may be in a nested subdir)
        model_root = None
        for root, dirs, files in os.walk(tmp_dir):
            if "model.pt" in files:
                model_root = root
                break

        if model_root is None:
            print(f"ERROR: model.pt not found in extracted archive")
            print(f"Extracted files: {os.listdir(tmp_dir)}")
            sys.exit(1)

        print(f"Found model.pt in: {model_root}")

        # Copy to target dir
        import shutil
        os.makedirs(target_dir, exist_ok=True)
        for filename in os.listdir(model_root):
            src = os.path.join(model_root, filename)
            dst = os.path.join(target_dir, filename)
            shutil.copy2(src, dst)
            print(f"  Copied: {filename}")

    # Clean up tar
    os.remove(local_tar)
    print(f"Extracted to: {target_dir}")


def verify_model_files(model_dir: str) -> bool:
    """Verify all required model files exist."""
    required_files = ["model.pt", "config.json"]
    optional_files = ["tokenizer.json", "tokenizer_config.json"]

    print(f"\nVerifying model files in {model_dir}:")
    all_ok = True

    for f in required_files:
        path = os.path.join(model_dir, f)
        if os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"  [OK] {f} ({size_mb:.1f} MB)")
        else:
            print(f"  [MISSING] {f} - REQUIRED")
            all_ok = False

    for f in optional_files:
        path = os.path.join(model_dir, f)
        if os.path.exists(path):
            size_kb = os.path.getsize(path) / 1024
            print(f"  [OK] {f} ({size_kb:.1f} KB)")
        else:
            print(f"  [MISSING] {f} - optional but recommended")

    # Verify config.json has expected keys
    config_path = os.path.join(model_dir, "config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)

        expected_keys = ["base_model", "num_clause_labels", "num_intent_labels", "clause_labels"]
        for key in expected_keys:
            if key in config:
                val = config[key]
                if isinstance(val, list):
                    print(f"  [OK] config.{key}: {len(val)} items")
                else:
                    print(f"  [OK] config.{key}: {val}")
            else:
                print(f"  [MISSING] config.{key}")
                all_ok = False

    return all_ok


def show_current_status():
    """Show the status of existing model files."""
    print("Current model status:")
    for name, path in [("final", FINAL_MODEL_DIR), ("best", BEST_MODEL_DIR)]:
        if os.path.exists(path):
            files = os.listdir(path)
            model_size = 0
            if "model.pt" in files:
                model_size = os.path.getsize(os.path.join(path, "model.pt")) / (1024 * 1024)
            print(f"  [{name}] {path}")
            print(f"    Files: {files}")
            print(f"    model.pt size: {model_size:.1f} MB")
        else:
            print(f"  [{name}] NOT FOUND: {path}")


def main():
    parser = argparse.ArgumentParser(description="Download InstantRisk Engine model from SageMaker")
    parser.add_argument("--job", default="instantrisk-engine-20260217-195607",
                        help="SageMaker training job name")
    parser.add_argument("--poll-interval", type=int, default=300,
                        help="Polling interval in seconds (default: 300 = 5 min)")
    parser.add_argument("--status-only", action="store_true",
                        help="Only check job status, don't download")
    parser.add_argument("--check-local", action="store_true",
                        help="Show local model status only")
    parser.add_argument("--target", choices=["final", "best"], default="final",
                        help="Which model directory to update (default: final)")
    args = parser.parse_args()

    print("=" * 60)
    print("InstantRisk Engine - SageMaker Model Downloader")
    print("=" * 60)

    if args.check_local:
        show_current_status()
        return

    # Check job status
    info = check_job_status(args.job)
    print(f"\nJob: {args.job}")
    print(f"Status: {info['status']} / {info['secondary_status']}")

    if args.status_only:
        if info["status"] == "Completed":
            print(f"Model artifacts: {info['model_artifacts']}")
        elif info["failure_reason"]:
            print(f"Failure: {info['failure_reason']}")
        show_current_status()
        return

    # Handle each status
    if info["status"] == "Completed":
        s3_uri = info["model_artifacts"]
        print(f"\nTraining already completed.")
        print(f"Model artifacts: {s3_uri}")
    elif info["status"] in ("InProgress", "Stopping"):
        print(f"\nTraining in progress. Starting poll loop...")
        s3_uri = wait_for_completion(args.job, args.poll_interval)
    else:
        print(f"\nERROR: Job in unexpected state: {info['status']}")
        if info["failure_reason"]:
            print(f"Failure: {info['failure_reason']}")
        sys.exit(1)

    # Download and extract
    target_dir = FINAL_MODEL_DIR if args.target == "final" else BEST_MODEL_DIR
    print(f"\nDownloading model to: {target_dir}")
    download_and_extract(s3_uri, target_dir)

    # Verify
    ok = verify_model_files(target_dir)
    if ok:
        print("\nModel integration complete!")
        print(f"Restart the backend to load the new model.")
    else:
        print("\nWARNING: Some files are missing. Model may not load correctly.")
        sys.exit(1)


if __name__ == "__main__":
    main()
