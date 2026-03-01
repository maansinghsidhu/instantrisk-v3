"""
Deploy v136: Fix stale DB session in _run_opendraft_job causing stuck "processing" jobs.

Changes vs v135:
- document_generation.py: Restructured _run_opendraft_job() to use short-lived DB sessions
  for each phase (mark processing, run pipeline, save results) instead of holding one session
  open for the entire 2-10 minute pipeline. Added asyncio.wait_for() with 10-minute timeout.
  Error handling now uses fresh sessions, preventing silent failure when completion commit fails
  on a stale connection. Upgraded error logging from debug to error level.

Steps: zip -> S3 -> CodeBuild -> ECR -> ECS task def -> ECS service -> health check
"""

import boto3
import os
import time
import sys
import zipfile
from pathlib import Path

VERSION = "v136"
AWS_REGION = "us-east-1"
ACCOUNT_ID = "995306061991"
S3_BUCKET = "instantrisk-documents-995306061991"
S3_BACKEND_KEY = "backend-source.zip"
S3_FRONTEND_KEY = "codebuild/frontend-source.zip"
ECR_REPO = "instantrisk-backend"
ECS_CLUSTER = "instantrisk"
ECS_SERVICE = "instantrisk-backend"
CODEBUILD_BACKEND = "instantrisk-backend"
CODEBUILD_FRONTEND = "instantrisk-frontend"
TASK_FAMILY = "instantrisk-backend"
EFS_ID = "fs-090ad3238b9702fb0"
EFS_VOLUME_NAME = "efs-models"
EFS_MOUNT_PATH = "/mnt/efs"

SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent / "backend"
FRONTEND_DIR = SCRIPT_DIR.parent / "frontend"

print("=" * 70)
print("InstantRisk %s Deployment" % VERSION)
print("Fix stale DB session — generation jobs now complete reliably")
print("=" * 70)

# Use AWS SSO profile — do NOT use explicit env var credentials
session = boto3.Session(profile_name="maani-sandbox", region_name=AWS_REGION)
sts = session.client("sts")
identity = sts.get_caller_identity()
print("Account: %s" % identity["Account"])
print("User: %s" % identity["Arn"].split("/")[-1])

# Step 1: Backend zip
print("\n[1/8] Creating backend zip...")
zip_path = SCRIPT_DIR / ("backend-%s.zip" % VERSION)

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
print("  Created %s (%.1f MB, %d files)" % (zip_path.name, size_mb, file_count))

# Step 2: Frontend zip
print("\n[2/8] Creating frontend zip...")
fzip_path = SCRIPT_DIR / ("frontend-%s.zip" % VERSION)

F_SKIP_DIRS = {
    "__pycache__",
    ".git",
    ".dart_tool",
    ".flutter-plugins",
    "build",
    "node_modules",
}

f_count = 0
with zipfile.ZipFile(str(fzip_path), "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(FRONTEND_DIR):
        dirs[:] = [d for d in dirs if d not in F_SKIP_DIRS]
        for file in files:
            fp = os.path.join(root, file)
            arc = os.path.relpath(fp, FRONTEND_DIR).replace(os.sep, "/")
            zf.write(fp, arc)
            f_count += 1

f_size_mb = fzip_path.stat().st_size / 1024 / 1024
print("  Created %s (%.1f MB, %d files)" % (fzip_path.name, f_size_mb, f_count))

# Step 3: Upload to S3
print("\n[3/8] Uploading to S3...")
s3 = session.client("s3")
s3.upload_file(str(zip_path), S3_BUCKET, S3_BACKEND_KEY)
print("  Backend uploaded to s3://%s/%s" % (S3_BUCKET, S3_BACKEND_KEY))
s3.upload_file(str(fzip_path), S3_BUCKET, S3_FRONTEND_KEY)
print("  Frontend uploaded to s3://%s/%s" % (S3_BUCKET, S3_FRONTEND_KEY))

# Step 4: Trigger CodeBuilds
print("\n[4/8] Triggering CodeBuilds...")
codebuild = session.client("codebuild")

backend_build_id = None
frontend_build_id = None

try:
    r = codebuild.start_build(projectName=CODEBUILD_BACKEND)
    backend_build_id = r["build"]["id"]
    print("  Backend build: %s" % backend_build_id)
except Exception as e:
    print("  Backend build FAILED to start: %s" % e)

try:
    r = codebuild.start_build(projectName=CODEBUILD_FRONTEND)
    frontend_build_id = r["build"]["id"]
    print("  Frontend build: %s" % frontend_build_id)
except Exception as e:
    print("  Frontend build FAILED to start: %s" % e)

# Step 5: Wait for backend build
if backend_build_id:
    print("\n[5/8] Waiting for backend build...")
    while True:
        r = codebuild.batch_get_builds(ids=[backend_build_id])
        build = r["builds"][0]
        status = build["buildStatus"]
        phase = build.get("currentPhase", "")
        if status == "SUCCEEDED":
            print("  Backend build SUCCEEDED")
            break
        elif status in ["FAILED", "FAULT", "STOPPED", "TIMED_OUT"]:
            print("  Backend build FAILED: %s" % status)
            logs = build.get("logs", {})
            if logs.get("deepLink"):
                print("  Logs: %s" % logs["deepLink"])
            sys.exit(1)
        print("    Phase: %s ..." % phase)
        time.sleep(20)
else:
    print("\n[5/8] Skipped (no backend build ID)")

# Step 6: Update ECS
print("\n[6/8] Updating ECS service...")
ecr = session.client("ecr")
ecs = session.client("ecs")

resp = ecr.describe_images(repositoryName=ECR_REPO, filter={"tagStatus": "TAGGED"})
images = sorted(resp["imageDetails"], key=lambda x: x["imagePushedAt"], reverse=True)
latest_tag = images[0]["imageTags"][0]
image_uri = "%s.dkr.ecr.%s.amazonaws.com/%s:%s" % (
    ACCOUNT_ID,
    AWS_REGION,
    ECR_REPO,
    latest_tag,
)
print("  Image: %s" % image_uri)

current = ecs.describe_task_definition(taskDefinition=TASK_FAMILY)
current_def = current["taskDefinition"]
container = current_def["containerDefinitions"][0]
container["image"] = image_uri

mounts = [
    m
    for m in container.get("mountPoints", [])
    if m.get("sourceVolume") != EFS_VOLUME_NAME
]
mounts.append(
    {
        "sourceVolume": EFS_VOLUME_NAME,
        "containerPath": EFS_MOUNT_PATH,
        "readOnly": False,
    }
)
container["mountPoints"] = mounts

volumes = [
    {
        "name": EFS_VOLUME_NAME,
        "efsVolumeConfiguration": {
            "fileSystemId": EFS_ID,
            "rootDirectory": "/",
            "transitEncryption": "ENABLED",
        },
    }
]

reg = ecs.register_task_definition(
    family=TASK_FAMILY,
    taskRoleArn=current_def.get("taskRoleArn", ""),
    executionRoleArn=current_def.get("executionRoleArn", ""),
    networkMode=current_def.get("networkMode", "awsvpc"),
    containerDefinitions=[container],
    volumes=volumes,
    requiresCompatibilities=current_def.get("requiresCompatibilities", ["FARGATE"]),
    cpu=current_def.get("cpu", "1024"),
    memory=current_def.get("memory", "2048"),
)
new_rev = reg["taskDefinition"]["revision"]
new_arn = reg["taskDefinition"]["taskDefinitionArn"]
print("  Registered: %s:%d" % (TASK_FAMILY, new_rev))

ecs.update_service(
    cluster=ECS_CLUSTER,
    service=ECS_SERVICE,
    taskDefinition=new_arn,
    forceNewDeployment=True,
)
print("  Service update initiated, waiting...")

for i in range(90):
    resp = ecs.describe_services(cluster=ECS_CLUSTER, services=[ECS_SERVICE])
    service = resp["services"][0]
    deps = service["deployments"]
    if len(deps) == 1 and deps[0]["status"] == "PRIMARY":
        r = deps[0]["runningCount"]
        d = deps[0]["desiredCount"]
        if r == d and r > 0:
            print("  Running: %d/%d - stable" % (r, d))
            break
    primary = [x for x in deps if x["status"] == "PRIMARY"]
    if primary:
        p = primary[0]
        print("  Primary: %d/%d..." % (p["runningCount"], p["desiredCount"]))
    time.sleep(10)
else:
    print("  WARNING: ECS deployment timed out")

# Step 7: Wait for frontend
if frontend_build_id:
    print("\n[7/8] Waiting for frontend build...")
    while True:
        r = codebuild.batch_get_builds(ids=[frontend_build_id])
        build = r["builds"][0]
        status = build["buildStatus"]
        phase = build.get("currentPhase", "")
        if status == "SUCCEEDED":
            print("  Frontend build SUCCEEDED")
            break
        elif status in ["FAILED", "FAULT", "STOPPED", "TIMED_OUT"]:
            print("  Frontend build %s" % status)
            logs = build.get("logs", {})
            if logs.get("deepLink"):
                print("  Logs: %s" % logs["deepLink"])
            break
        print("    Phase: %s ..." % phase)
        time.sleep(20)
else:
    print("\n[7/8] Skipped (no frontend build ID)")

# Step 8: Health check
print("\n[8/8] Health check...")
import urllib.request

ALB = "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com"
try:
    time.sleep(5)
    req = urllib.request.urlopen(ALB + "/health", timeout=15)
    print("  %s/health -> %s OK" % (ALB, req.status))
except Exception as e:
    print("  Health check: %s" % e)

print("\n" + "=" * 70)
print("DEPLOYMENT %s COMPLETE" % VERSION)
print("=" * 70)
print("Task def: %s:%d" % (TASK_FAMILY, new_rev))
print("Image:    %s" % image_uri)
print("ALB:      %s" % ALB)
