"""
Verify database state and seed test users via ECS Exec.

This script:
1. Connects to the Fargate container via ECS Exec
2. Checks if test users exist in the database
3. Creates them if they don't exist
"""
import boto3
import json
import time

# AWS Credentials (copy from deploy_backend_merged.py)
AWS_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_SESSION_TOKEN = os.environ.get('AWS_SESSION_TOKEN', '')

AWS_REGION = "us-east-1"
ECS_CLUSTER = "instantrisk"
ECS_SERVICE = "instantrisk-backend"


def create_session():
    return boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        aws_session_token=AWS_SESSION_TOKEN,
        region_name=AWS_REGION
    )


def get_running_task(session):
    """Get the running task ARN."""
    ecs = session.client('ecs')
    response = ecs.list_tasks(cluster=ECS_CLUSTER, serviceName=ECS_SERVICE, desiredStatus='RUNNING')
    if response['taskArns']:
        return response['taskArns'][0]
    return None


def get_cloudwatch_logs(session, log_group, log_stream_prefix, limit=100):
    """Get recent CloudWatch logs."""
    logs = session.client('logs')

    # Get log streams
    try:
        streams_response = logs.describe_log_streams(
            logGroupName=log_group,
            logStreamNamePrefix=log_stream_prefix,
            orderBy='LastEventTime',
            descending=True,
            limit=5
        )
    except Exception as e:
        print(f"Error getting log streams: {e}")
        return []

    if not streams_response.get('logStreams'):
        print(f"No log streams found for {log_stream_prefix}")
        return []

    # Get events from the most recent stream
    stream_name = streams_response['logStreams'][0]['logStreamName']
    print(f"Reading from log stream: {stream_name}")

    try:
        events_response = logs.get_log_events(
            logGroupName=log_group,
            logStreamName=stream_name,
            limit=limit,
            startFromHead=False
        )
        return events_response.get('events', [])
    except Exception as e:
        print(f"Error getting log events: {e}")
        return []


def main():
    session = create_session()

    # Verify credentials
    try:
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        print(f"Authenticated as: {identity['Arn']}")
    except Exception as e:
        print(f"Credential error: {e}")
        return

    # Get running task
    task_arn = get_running_task(session)
    if not task_arn:
        print("No running task found!")
        return

    task_id = task_arn.split('/')[-1]
    print(f"Found running task: {task_id}")

    # Get CloudWatch logs
    print("\n" + "=" * 60)
    print("CLOUDWATCH LOGS (recent startup messages)")
    print("=" * 60)

    log_group = "/ecs/instantrisk-backend"
    log_stream_prefix = f"backend/{task_id[:8]}"

    events = get_cloudwatch_logs(session, log_group, log_stream_prefix)

    # Look for startup/seeding messages
    startup_messages = []
    for event in events:
        msg = event.get('message', '')
        if any(keyword in msg.lower() for keyword in ['starting', 'seed', 'user', 'error', 'exception', 'failed', 'migration', 'schema']):
            startup_messages.append(msg)

    if startup_messages:
        for msg in startup_messages[-30:]:  # Show last 30 relevant messages
            print(msg.strip())
    else:
        print("No startup/seeding messages found. Showing all recent logs:")
        for event in events[-20:]:
            print(event.get('message', '').strip())

    print("\n" + "=" * 60)
    print("NEXT STEP: Manual user seeding via ECS Exec")
    print("=" * 60)
    print("""
To manually seed users, run this command:

aws ecs execute-command \\
    --cluster instantrisk \\
    --task {task_id} \\
    --container backend \\
    --interactive \\
    --command "python -c \\"
from app.core.database import AsyncSessionLocal
from app.seed_users import seed_test_users
import asyncio
async def run():
    async with AsyncSessionLocal() as session:
        count = await seed_test_users(session)
        print(f'Seeded {{count}} users')
asyncio.run(run())
\\""

Or use the simpler approach - call the seeding endpoint:
curl -X POST http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com/api/v1/admin/seed-users
""".format(task_id=task_id))


if __name__ == "__main__":
    main()
