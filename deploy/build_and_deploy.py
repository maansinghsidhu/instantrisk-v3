"""Build and deploy backend to ECS."""
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

# Upload
print("Uploading to S3...")
s3.upload_file("backend-source.zip", BUCKET, KEY)
print("Done.")

# Build
print("Starting CodeBuild...")
build = cb.start_build(projectName="instantrisk-backend")
build_id = build["build"]["id"]
print(f"Build: {build_id}")

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
    sys.exit(1)

print("Build succeeded!")

# Register task def
with open("backend-container-def.json") as f:
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
print(f"Task def v{rev}: {arn}")

# Update service
ecs.update_service(
    cluster="instantrisk",
    service="instantrisk-backend",
    taskDefinition=arn,
    forceNewDeployment=True,
)
print(f"Service updated to v{rev}")

# Wait for stabilization
print("Waiting for stabilization...")
for i in range(30):
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
                sys.exit(0)
            if p.get("rolloutState") == "FAILED":
                print(f"\nFAILED: {p.get('rolloutStateReason', '')}")
                sys.exit(1)
    except Exception as e:
        print(f"  Error: {e}")
    print()

print("Timeout. Check ECS console.")
