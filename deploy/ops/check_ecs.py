"""Check ECS status"""
import boto3

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

ecs = session.client('ecs')

print("ECS Backend Service Status:")
try:
    resp = ecs.describe_services(cluster='instantrisk', services=['instantrisk-backend'])
    svc = resp['services'][0]
    print(f"  Status: {svc['status']}")
    print(f"  Running: {svc['runningCount']}/{svc['desiredCount']}")
    print(f"  Deployments: {len(svc['deployments'])}")
    for d in svc['deployments']:
        print(f"    - {d['status']}: {d['runningCount']}/{d['desiredCount']}")
except Exception as e:
    print(f"Error: {e}")

# Check ALB target health
elbv2 = session.client('elbv2')
print("\nALB Target Health:")
try:
    # Find target group
    tgs = elbv2.describe_target_groups()
    for tg in tgs['TargetGroups']:
        if 'instantrisk' in tg['TargetGroupName'].lower():
            print(f"  Target Group: {tg['TargetGroupName']}")
            health = elbv2.describe_target_health(TargetGroupArn=tg['TargetGroupArn'])
            for t in health['TargetHealthDescriptions']:
                print(f"    - {t['Target']['Id']}: {t['TargetHealth']['State']}")
except Exception as e:
    print(f"Error: {e}")
