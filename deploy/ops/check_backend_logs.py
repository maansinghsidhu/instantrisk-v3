import boto3
import os
import time

# AWS credentials should be set via environment before running
# AWS_SECRET_ACCESS_KEY removed - set via environment
# AWS_SESSION_TOKEN removed - set via environment

logs = boto3.client('logs', region_name='us-east-1')

log_group = '/ecs/instantrisk-backend'

# Get recent log streams
streams = logs.describe_log_streams(
    logGroupName=log_group,
    orderBy='LastEventTime',
    descending=True,
    limit=3
)

print("Checking backend logs for errors...")
print("=" * 60)

for stream in streams['logStreams']:
    stream_name = stream['logStreamName']
    print(f"\nLog stream: {stream_name}")
    print("-" * 60)

    # Get recent events
    events = logs.get_log_events(
        logGroupName=log_group,
        logStreamName=stream_name,
        limit=100,
        startFromHead=False
    )

    # Look for errors related to reports, analysis, json
    for event in events['events']:
        msg = event['message'].lower()
        if any(x in msg for x in ['error', 'exception', 'invalid', 'json', 'report', 'analysis', 'bedrock']):
            timestamp = time.strftime('%H:%M:%S', time.localtime(event['timestamp']/1000))
            print(f"[{timestamp}] {event['message'][:300]}")
