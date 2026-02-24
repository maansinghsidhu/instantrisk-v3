"""
Step 1: Zip backend, upload to S3, trigger CodeBuild only.
Prints the build ID so we can poll separately.
"""

import boto3, os, zipfile
from pathlib import Path

AWS_REGION = "us-east-1"
S3_BUCKET = "instantrisk-documents-995306061991"
S3_BACKEND_KEY = "backend-source.zip"
CODEBUILD_BACKEND = "instantrisk-backend"

SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent / "backend"

SKIP_EXT = {
    ".pt",
    ".safetensors",
    ".bin",
    ".pyc",
    ".pyo",
    ".log",
    ".jsonl",
    ".npz",
    ".bak",
}
SKIP_DIRS = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    "venv",
    "node_modules",
    "scripts",
    "computed",
    "splits",
}
SKIP_FRAGS = [
    "training_data",
    "insurance_data",
    "data/models",
    "app/data/models",
    "app/data/training_data",
]

session = boto3.Session(region_name=AWS_REGION)

print("[1/3] Zipping backend...")
zip_path = SCRIPT_DIR / "backend-latest.zip"
file_count = 0
with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(BACKEND_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(root, BACKEND_DIR).replace(os.sep, "/")
        if any(f in rel for f in SKIP_FRAGS):
            dirs[:] = []
            continue
        for file in files:
            if os.path.splitext(file)[1].lower() in SKIP_EXT:
                continue
            fp = os.path.join(root, file)
            arc = os.path.relpath(fp, BACKEND_DIR).replace(os.sep, "/")
            zf.write(fp, arc)
            file_count += 1

size_mb = zip_path.stat().st_size / 1024 / 1024
print(f"  {file_count} files, {size_mb:.1f} MB")

# Verify app/data/*.py are included
data_py = (
    [n for n in zf.namelist() if n.startswith("app/data/") and n.endswith(".py")]
    if False
    else []
)
import zipfile as zf2

with zf2.ZipFile(str(zip_path)) as check:
    data_py = [
        n for n in check.namelist() if n.startswith("app/data/") and n.endswith(".py")
    ]
print(f"  app/data/*.py included: {data_py}")

print("[2/3] Uploading to S3...")
s3 = session.client("s3")
s3.upload_file(str(zip_path), S3_BUCKET, S3_BACKEND_KEY)
print(f"  Uploaded to s3://{S3_BUCKET}/{S3_BACKEND_KEY}")

print("[3/3] Triggering CodeBuild...")
cb = session.client("codebuild")
r = cb.start_build(projectName=CODEBUILD_BACKEND)
build_id = r["build"]["id"]
print(f"  Build ID: {build_id}")
print(f"\nDONE. Poll with: aws codebuild batch-get-builds --ids '{build_id}'")
