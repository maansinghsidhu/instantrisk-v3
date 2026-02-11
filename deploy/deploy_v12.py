"""
Deploy v12: Fix ALB health check + move health endpoints before routers.

Steps:
1. Create zip with forward slashes
2. Upload to S3
3. Update ALB target group health check path to /api/v1/health/live
4. Start CodeBuild
5. Wait for build
6. Register task def v12
7. Update ECS service
8. Wait for stabilization
"""
import boto3
import json
import time
import sys
import os
import zipfile

region = "us-east-1"
s3 = boto3.client("s3", region_name=region)
cb = boto3.client("codebuild", region_name=region)
ecs = boto3.client("ecs", region_name=region)
elbv2 = boto3.client("elbv2", region_name=region)

BUCKET = "instantrisk-documents-995306061991"
KEY = "codebuild/backend-source.zip"
SRC_DIR = os.path.join(os.path.dirname(__file__), "backend-merged")
ZIP_PATH = os.path.join(os.path.dirname(__file__), "backend-source.zip")

# Step 1: Create zip with forward slashes
print("Creating zip file...")
count = 0
with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(SRC_DIR):
        # Skip __pycache__, .git, .venv, .env
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", ".venv", "node_modules", ".mypy_cache")]
        for f in files:
            if f == ".env":
                continue
            full = os.path.join(root, f)
            arcname = os.path.relpath(full, SRC_DIR).replace(os.sep, "/")
            zf.write(full, arcname)
            count += 1
print(f"  Zipped {count} files")

# Step 2: Upload to S3
print("Uploading to S3...")
s3.upload_file(ZIP_PATH, BUCKET, KEY)
print("  Done.")

# Step 3: Update ALB target group health check
print("Updating ALB target group health check...")
try:
    tgs = elbv2.describe_target_groups(Names=["instantrisk-backend-tg"])
    tg_arn = tgs["TargetGroups"][0]["TargetGroupArn"]
    current_path = tgs["TargetGroups"][0].get("HealthCheckPath", "?")
    print(f"  Current health check path: {current_path}")

    if current_path != "/api/v1/health/live":
        elbv2.modify_target_group(
            TargetGroupArn=tg_arn,
            HealthCheckPath="/api/v1/health/live",
            HealthCheckIntervalSeconds=30,
            HealthyThresholdCount=2,
            UnhealthyThresholdCount=3,
        )
        print("  Updated to: /api/v1/health/live")
    else:
        print("  Already set to /api/v1/health/live")
except Exception as e:
    print(f"  Warning: Could not update target group: {e}")
    print("  Continuing with deployment...")

# Step 4: Start CodeBuild
print("Starting CodeBuild...")
build = cb.start_build(projectName="instantrisk-backend")
build_id = build["build"]["id"]
print(f"  Build: {build_id}")

# Step 5: Wait for build
while True:
    time.sleep(15)
    resp = cb.batch_get_builds(ids=[build_id])
    b = resp["builds"][0]
    st = b["buildStatus"]
    ph = b.get("currentPhase", "?")
    print(f"  {st} | {ph}")
    if st in ("SUCCEEDED", "FAILED", "STOPPED", "FAULT", "TIMED_OUT"):
        break

if st != "SUCCEEDED":
    print(f"BUILD FAILED: {st}")
    # Try to get build logs
    try:
        logs_info = b.get("logs", {})
        if logs_info.get("deepLink"):
            print(f"  Logs: {logs_info['deepLink']}")
    except:
        pass
    sys.exit(1)

print("Build succeeded!")

# Step 6: Register task def
print("Registering task definition...")
with open(os.path.join(os.path.dirname(__file__), "backend-container-def.json")) as f:
    cdef = json.load(f)
if isinstance(cdef, list):
    cdefs = cdef
else:
    cdefs = [cdef]

current = ecs.describe_task_definition(taskDefinition="instantrisk-backend")["taskDefinition"]
td = ecs.register_task_definition(
    family="instantrisk-backend",
    taskRoleArn=current["taskRoleArn"],
    executionRoleArn=current["executionRoleArn"],
    networkMode="awsvpc",
    requiresCompatibilities=["FARGATE"],
    cpu=current["cpu"],
    memory=current["memory"],
    containerDefinitions=cdefs,
)
rev = td["taskDefinition"]["revision"]
arn = td["taskDefinition"]["taskDefinitionArn"]
print(f"  Task def v{rev}: {arn}")

# Step 7: Update service
print("Updating ECS service...")
ecs.update_service(
    cluster="instantrisk",
    service="instantrisk-backend",
    taskDefinition=arn,
    forceNewDeployment=True,
)
print(f"  Service updated to v{rev}")

# Step 8: Wait for stabilization
print("Waiting for stabilization...")
for i in range(40):  # 10 minutes
    time.sleep(15)
    try:
        desc = ecs.describe_services(cluster="instantrisk", services=["instantrisk-backend"])
        svc = desc["services"][0]
        for d in svc.get("deployments", []):
            s = d["status"]
            r = d.get("runningCount", 0)
            des = d.get("desiredCount", 0)
            ro = d.get("rolloutState", "?")
            rv = d["taskDefinition"].split(":")[-1]
            print(f"  [{s}] v{rv} running={r}/{des} rollout={ro}")

        primary = [d for d in svc["deployments"] if d["status"] == "PRIMARY"]
        if primary:
            p = primary[0]
            if p.get("runningCount", 0) >= p.get("desiredCount", 1) and p.get("rolloutState") == "COMPLETED":
                print("\nSUCCESS: Service stabilized!")
                # Verify health endpoint
                print("\nVerifying ALB health...")
                try:
                    import urllib.request
                    url = "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com/api/v1/health"
                    req = urllib.request.Request(url, method="GET")
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        print(f"  GET /api/v1/health -> {resp.status}: {resp.read().decode()}")
                except Exception as e:
                    print(f"  Health check verification: {e}")
                sys.exit(0)
            if p.get("rolloutState") == "FAILED":
                reason = p.get("rolloutStateReason", "")
                print(f"\nFAILED: {reason}")
                sys.exit(1)
    except Exception as e:
        print(f"  Error: {e}")
    print()

print("Timeout. Check ECS console.")
