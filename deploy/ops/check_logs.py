"""Check ECS logs for login error"""
import boto3
from datetime import datetime, timedelta

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

logs = session.client('logs')

print("=" * 60)
print("Recent ECS Logs (last 2 minutes)")
print("=" * 60)

# Get logs from last 2 minutes
start_time = int((datetime.utcnow() - timedelta(minutes=2)).timestamp() * 1000)

try:
    resp = logs.filter_log_events(
        logGroupName='/ecs/instantrisk-backend',
        startTime=start_time,
        limit=50,
        interleaved=True
    )
    for event in resp.get('events', []):
        ts = datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%H:%M:%S')
        msg = event['message']
        print(f"[{ts}] {msg}")
except Exception as e:
    print(f"Logs error: {e}")

print("\n" + "=" * 60)
print("Search for ERROR and Exception")
print("=" * 60)

try:
    resp = logs.filter_log_events(
        logGroupName='/ecs/instantrisk-backend',
        startTime=start_time,
        filterPattern="?ERROR ?Exception ?Traceback ?error",
        limit=20,
        interleaved=True
    )
    for event in resp.get('events', []):
        ts = datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%H:%M:%S')
        msg = event['message']
        print(f"[{ts}] {msg}")
except Exception as e:
    print(f"Error search error: {e}")
