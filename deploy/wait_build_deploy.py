"""Wait for CodeBuild, register task def, deploy to ECS."""
import boto3
import json
import time
import sys

region = "us-east-1"
cb = boto3.client("codebuild", region_name=region)
ecs = boto3.client("ecs", region_name=region)

build_id = sys.argv[1] if len(sys.argv) > 1 else None
if not build_id:
    # Get latest build
    builds = cb.list_builds_for_project(projectName="instantrisk-backend", sortOrder="DESCENDING")
    build_id = builds["ids"][0]

print(f"Monitoring build: {build_id}")

# Wait for build
while True:
    time.sleep(15)
    resp = cb.batch_get_builds(ids=[build_id])
    b = resp["builds"][0]
    st = b["buildStatus"]
    ph = b.get("currentPhase", "?")
    print(f"  {st} | {ph}")
    sys.stdout.flush()
    if st in ("SUCCEEDED", "FAILED", "STOPPED", "FAULT", "TIMED_OUT"):
        break

if st != "SUCCEEDED":
    print(f"BUILD FAILED: {st}")
    for phase in b.get("phases", []):
        if phase.get("phaseStatus") == "FAILED":
            for ctx in phase.get("contexts", []):
                print(f"  {ctx.get('message', '')}")
    sys.exit(1)

print("Build succeeded!")

# Register task def
with open(r"C:\Users\maani\instantrisk-v2\backend-container-def.json") as f:
    cdef = json.load(f)
cdefs = cdef if isinstance(cdef, list) else [cdef]

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
print("Monitoring deployment...")

for i in range(40):
    time.sleep(15)
    try:
        desc = ecs.describe_services(cluster="instantrisk", services=["instantrisk-backend"])
        svc = desc["services"][0]
        parts = []
        for d in svc.get("deployments", []):
            s = d["status"]
            r = d.get("runningCount", 0)
            des = d.get("desiredCount", 0)
            ro = d.get("rolloutState", "?")
            rv = d["taskDefinition"].split(":")[-1]
            parts.append(f"[{s}]v{rv}={r}/{des}({ro})")
        print(f"  {' | '.join(parts)}")
        sys.stdout.flush()

        primary = [d for d in svc["deployments"] if d["status"] == "PRIMARY"]
        if primary:
            p = primary[0]
            if p.get("runningCount", 0) >= 1 and p.get("rolloutState") == "COMPLETED":
                print("\nSUCCESS: Deployment complete!")

                # Test login
                import urllib.request
                alb = "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com"
                try:
                    login_data = json.dumps({"email": "demo@instantrisk.com", "password": "Demo2026pass"}).encode()
                    req = urllib.request.Request(f"{alb}/api/v1/auth/login", data=login_data, method="POST")
                    req.add_header("Content-Type", "application/json")
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        body = json.loads(resp.read().decode())
                        print(f"Login: {resp.status} OK - {body.get('user', {}).get('email', '?')}")
                except urllib.error.HTTPError as e:
                    err = e.read().decode()[:200]
                    print(f"Login: {e.code} - {err}")
                except Exception as e:
                    print(f"Login: ERROR - {e}")

                sys.exit(0)
            if p.get("rolloutState") == "FAILED":
                print(f"\nFAILED: {p.get('rolloutStateReason', '')}")
                sys.exit(1)
    except Exception as e:
        print(f"  Error: {e}")

print("Timeout. Check ECS console.")
