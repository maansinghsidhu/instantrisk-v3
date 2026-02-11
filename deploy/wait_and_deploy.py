"""Wait for current CodeBuild to finish, then force redeploy ECS."""
import boto3
import json
import time
import sys
import os

region = "us-east-1"
cb = boto3.client("codebuild", region_name=region)
ecs = boto3.client("ecs", region_name=region)

# Step 1: Wait for current build
print("Checking latest CodeBuild...")
builds = cb.list_builds_for_project(projectName="instantrisk-backend", sortOrder="DESCENDING")
build_id = builds["ids"][0]
print(f"Build: {build_id}")

while True:
    b = cb.batch_get_builds(ids=[build_id])["builds"][0]
    st = b["buildStatus"]
    ph = b.get("currentPhase", "?")
    print(f"  {st} | {ph}")
    if st in ("SUCCEEDED", "FAILED", "STOPPED", "FAULT", "TIMED_OUT"):
        break
    time.sleep(15)

if st != "SUCCEEDED":
    print(f"Build failed: {st}")
    sys.exit(1)

print("Build succeeded! ECR image updated.")

# Step 2: Force redeploy (task def v9 already registered, just force new deployment)
print("\nForcing new deployment...")
ecs.update_service(
    cluster="instantrisk",
    service="instantrisk-backend",
    forceNewDeployment=True,
)
print("Deployment triggered.")

# Step 3: Wait for stabilization
print("Waiting for stabilization...")
sys.stdout.flush()
for i in range(30):
    time.sleep(20)
    try:
        desc = ecs.describe_services(cluster="instantrisk", services=["instantrisk-backend"])
        svc = desc["services"][0]
        lines = []
        for d in svc.get("deployments", []):
            s = d["status"]
            r = d.get("runningCount", 0)
            des = d.get("desiredCount", 0)
            ro = d.get("rolloutState", "?")
            rv = d["taskDefinition"].split(":")[-1]
            lines.append(f"[{s}] v{rv} running={r}/{des} rollout={ro}")
        print(f"  {i*20}s: {' | '.join(lines)}")
        sys.stdout.flush()

        primary = [d for d in svc["deployments"] if d["status"] == "PRIMARY"]
        if primary:
            p = primary[0]
            if p.get("runningCount", 0) >= p.get("desiredCount", 1) and p.get("rolloutState") == "COMPLETED":
                print("\nSERVICE STABILIZED SUCCESSFULLY!")
                sys.exit(0)
            if p.get("rolloutState") == "FAILED":
                reason = p.get("rolloutStateReason", "")
                print(f"\nDEPLOYMENT FAILED: {reason}")
                # Check stopped tasks
                tasks = ecs.list_tasks(cluster="instantrisk", serviceName="instantrisk-backend", desiredStatus="STOPPED")
                if tasks.get("taskArns"):
                    details = ecs.describe_tasks(cluster="instantrisk", tasks=tasks["taskArns"][:2])
                    for t in details["tasks"]:
                        tid = t["taskArn"].split("/")[-1]
                        sr = t.get("stoppedReason", "")
                        print(f"  Task {tid}: {sr}")
                        for c in t.get("containers", []):
                            if c.get("exitCode") is not None:
                                print(f"    Container exit={c['exitCode']} reason={c.get('reason','')}")
                sys.exit(1)
    except Exception as e:
        print(f"  Error: {e}")
        sys.stdout.flush()

print("\nTimeout. Check CloudWatch logs or ECS console.")
