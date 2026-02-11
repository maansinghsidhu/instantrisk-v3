"""Deploy backend: Upload to S3 -> CodeBuild -> Register task def -> Update ECS service."""
import boto3
import json
import time
import sys

region = "us-east-1"
s3 = boto3.client("s3", region_name=region)
cb = boto3.client("codebuild", region_name=region)
ecs = boto3.client("ecs", region_name=region)

BUCKET = "instantrisk-documents-995306061991"
KEY = "codebuild/backend-source.zip"
CLUSTER = "instantrisk"
SERVICE = "instantrisk-backend"
CONTAINER_DEF_FILE = "backend-container-def.json"
ECR_IMAGE = "995306061991.dkr.ecr.us-east-1.amazonaws.com/instantrisk-backend:latest"

# Step 1: Upload to S3
print("=" * 60)
print("STEP 1: Uploading source zip to S3")
print("=" * 60)
s3.upload_file("backend-source.zip", BUCKET, KEY)
size = s3.head_object(Bucket=BUCKET, Key=KEY)["ContentLength"]
print(f"Uploaded to s3://{BUCKET}/{KEY} ({size} bytes)")

# Step 2: Start CodeBuild
print("\n" + "=" * 60)
print("STEP 2: Starting CodeBuild")
print("=" * 60)
build = cb.start_build(projectName="instantrisk-backend")
build_id = build["build"]["id"]
print(f"Build started: {build_id}")

# Step 3: Wait for build
while True:
    time.sleep(15)
    resp = cb.batch_get_builds(ids=[build_id])
    b = resp["builds"][0]
    status = b["buildStatus"]
    phase = b.get("currentPhase", "UNKNOWN")
    print(f"  Status: {status} | Phase: {phase}")
    if status != "IN_PROGRESS":
        break

if status != "SUCCEEDED":
    print(f"\nBUILD FAILED: {status}")
    for p in b.get("phases", []):
        if p.get("phaseStatus") == "FAILED":
            print(f"  Failed phase: {p['phaseType']}")
            for ctx in p.get("contexts", []):
                print(f"    {ctx.get('message', '')}")
    sys.exit(1)

print("\nCodeBuild SUCCEEDED!")

# Step 4: Register new task definition
print("\n" + "=" * 60)
print("STEP 3: Registering new ECS task definition")
print("=" * 60)

with open(CONTAINER_DEF_FILE) as f:
    container_def = json.load(f)

# container_def may be a list or a single dict
if isinstance(container_def, list):
    container_defs = container_def
else:
    container_defs = [container_def]

# Get current task def to preserve settings
current = ecs.describe_task_definition(taskDefinition=SERVICE)["taskDefinition"]

task_def = ecs.register_task_definition(
    family=SERVICE,
    taskRoleArn=current["taskRoleArn"],
    executionRoleArn=current["executionRoleArn"],
    networkMode="awsvpc",
    requiresCompatibilities=["FARGATE"],
    cpu=current["cpu"],
    memory=current["memory"],
    containerDefinitions=container_defs,
)
revision = task_def["taskDefinition"]["revision"]
task_arn = task_def["taskDefinition"]["taskDefinitionArn"]
print(f"Registered: {task_arn} (revision {revision})")

# Step 5: Update ECS service
print("\n" + "=" * 60)
print("STEP 4: Updating ECS service")
print("=" * 60)

ecs.update_service(
    cluster=CLUSTER,
    service=SERVICE,
    taskDefinition=task_arn,
    forceNewDeployment=True,
)
print(f"Service {SERVICE} updated to revision {revision}")

# Step 6: Wait for stabilization
print("\n" + "=" * 60)
print("STEP 5: Waiting for service to stabilize (up to 5 min)")
print("=" * 60)

for i in range(20):
    time.sleep(15)
    try:
        desc = ecs.describe_services(cluster=CLUSTER, services=[SERVICE])
        svc = desc["services"][0]
        deployments = svc.get("deployments", [])
        primary = [d for d in deployments if d["status"] == "PRIMARY"]
        if primary:
            p = primary[0]
            running = p.get("runningCount", 0)
            desired = p.get("desiredCount", 1)
            rollout = p.get("rolloutState", "UNKNOWN")
            print(f"  Running: {running}/{desired} | Rollout: {rollout}")
            if running >= desired and rollout == "COMPLETED":
                print("\nService stabilized successfully!")
                sys.exit(0)
            if rollout == "FAILED":
                print("\nDeployment FAILED!")
                reason = p.get("rolloutStateReason", "unknown")
                print(f"  Reason: {reason}")
                sys.exit(1)
    except Exception as e:
        print(f"  Check failed: {e}")

print("\nTimeout waiting for stabilization. Check ECS console.")
# Check if tasks are running
try:
    tasks = ecs.list_tasks(cluster=CLUSTER, serviceName=SERVICE)
    task_arns = tasks.get("taskArns", [])
    if task_arns:
        details = ecs.describe_tasks(cluster=CLUSTER, tasks=task_arns)
        for t in details["tasks"]:
            status = t.get("lastStatus", "UNKNOWN")
            reason = t.get("stoppedReason", "")
            print(f"  Task {t['taskArn'].split('/')[-1]}: {status}")
            if reason:
                print(f"    Stopped reason: {reason}")
            for c in t.get("containers", []):
                exit_code = c.get("exitCode")
                c_reason = c.get("reason", "")
                if exit_code is not None:
                    print(f"    Container exit code: {exit_code}")
                if c_reason:
                    print(f"    Container reason: {c_reason}")
except Exception as e:
    print(f"  Could not get task details: {e}")
