"""Deploy backend with JWT secret fix."""
import boto3
import json

REGION = "us-east-1"
CLUSTER = "instantrisk"
SERVICE = "instantrisk-backend"
FAMILY = "instantrisk-backend"

def main():
    ecs = boto3.client("ecs", region_name=REGION)

    # Get current task definition to preserve settings
    print("1. Getting current task definition...")
    resp = ecs.describe_task_definition(taskDefinition=FAMILY)
    current_td = resp["taskDefinition"]
    print(f"   Current revision: {current_td['revision']}")

    # Load updated container definition from file
    print("2. Loading updated container definition...")
    with open("backend-container-def.json") as f:
        container_defs = json.load(f)

    # Check JWT_SECRET_KEY is present
    env_names = [e["name"] for e in container_defs[0].get("environment", [])]
    if "JWT_SECRET_KEY" not in env_names:
        print("   ERROR: JWT_SECRET_KEY not found in container definition!")
        return
    print("   JWT_SECRET_KEY found in environment")

    # Register new task definition
    print("3. Registering new task definition...")
    resp = ecs.register_task_definition(
        family=FAMILY,
        taskRoleArn=current_td["taskRoleArn"],
        executionRoleArn=current_td["executionRoleArn"],
        networkMode=current_td["networkMode"],
        containerDefinitions=container_defs,
        requiresCompatibilities=current_td["requiresCompatibilities"],
        cpu=current_td["cpu"],
        memory=current_td["memory"],
    )
    new_rev = resp["taskDefinition"]["revision"]
    new_arn = resp["taskDefinition"]["taskDefinitionArn"]
    print(f"   Registered: {FAMILY}:{new_rev}")

    # Update service to use new task definition
    print("4. Updating service with new task definition...")
    ecs.update_service(
        cluster=CLUSTER,
        service=SERVICE,
        taskDefinition=new_arn,
        forceNewDeployment=True,
    )
    print(f"   Service updated, deploying {FAMILY}:{new_rev}")

    # Wait for deployment
    print("5. Waiting for deployment (this may take 2-3 minutes)...")
    waiter = ecs.get_waiter("services_stable")
    try:
        waiter.wait(
            cluster=CLUSTER,
            services=[SERVICE],
            WaiterConfig={"Delay": 15, "MaxAttempts": 20},
        )
        print("   Service is stable!")
    except Exception as e:
        print(f"   Waiter timed out (may still be deploying): {e}")
        print("   Check: aws ecs describe-services --cluster instantrisk --services instantrisk-backend")

    print("\nDone! JWT secret is now configured.")
    print("Test: curl -X POST https://<ALB>/api/v1/auth/login -H 'Content-Type: application/json' -d '{\"email\":\"demo@instantrisk.com\",\"password\":\"Demo2026pass\"}'")

if __name__ == "__main__":
    main()
