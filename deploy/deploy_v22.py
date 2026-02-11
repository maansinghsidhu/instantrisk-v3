"""Deploy v22: Add chat_messages table migration."""
import os, zipfile, boto3, json, time, sys, urllib.request, urllib.error

# AWS credentials should be set via environment before running
# AWS_SECRET_ACCESS_KEY removed - set via environment
# AWS_SESSION_TOKEN removed - set via environment

region = 'us-east-1'
s3 = boto3.client('s3', region_name=region)
cb = boto3.client('codebuild', region_name=region)
ecs = boto3.client('ecs', region_name=region)
bucket = 'instantrisk-documents-995306061991'

# Zip
src = r'C:\Users\maani\instantrisk-v2\backend-merged'
zippath = r'C:\Users\maani\instantrisk-v2\backend-source.zip'
skip = {'__pycache__', '.venv', '.git', 'node_modules', '.pytest_cache'}
with zipfile.ZipFile(zippath, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith('.pyc'):
                continue
            full = os.path.join(root, f)
            arcname = os.path.relpath(full, src).replace(os.sep, '/')
            zf.write(full, arcname)
print(f'Zip: {os.path.getsize(zippath)/1024/1024:.1f}MB')
sys.stdout.flush()

# Upload
s3.upload_file(zippath, bucket, 'codebuild/backend-source.zip')
print('Uploaded to S3')
sys.stdout.flush()

# Build
resp = cb.start_build(projectName='instantrisk-backend')
build_id = resp['build']['id']
print(f'Build: {build_id}')
sys.stdout.flush()

# Wait for build
while True:
    time.sleep(15)
    b = cb.batch_get_builds(ids=[build_id])['builds'][0]
    st = b['buildStatus']
    ph = b.get('currentPhase', '?')
    print(f'  {st} | {ph}')
    sys.stdout.flush()
    if st in ('SUCCEEDED', 'FAILED', 'STOPPED', 'FAULT', 'TIMED_OUT'):
        break

if st != 'SUCCEEDED':
    print(f'BUILD FAILED: {st}')
    sys.exit(1)
print('Build succeeded!')
sys.stdout.flush()

# Register task def
with open(r'C:\Users\maani\instantrisk-v2\backend-container-def.json') as f:
    cdef = json.load(f)
cdefs = cdef if isinstance(cdef, list) else [cdef]

current = ecs.describe_task_definition(taskDefinition='instantrisk-backend')['taskDefinition']
td = ecs.register_task_definition(
    family='instantrisk-backend',
    taskRoleArn=current['taskRoleArn'],
    executionRoleArn=current['executionRoleArn'],
    networkMode='awsvpc',
    requiresCompatibilities=['FARGATE'],
    cpu=current['cpu'],
    memory=current['memory'],
    containerDefinitions=cdefs,
)
rev = td['taskDefinition']['revision']
arn = td['taskDefinition']['taskDefinitionArn']
print(f'Task def v{rev}: {arn}')
sys.stdout.flush()

# Update service
ecs.update_service(cluster='instantrisk', service='instantrisk-backend',
                   taskDefinition=arn, forceNewDeployment=True)
print(f'Service updated to v{rev}')
print('Monitoring deployment...')
sys.stdout.flush()

# Monitor
for i in range(60):
    time.sleep(15)
    try:
        desc = ecs.describe_services(cluster='instantrisk', services=['instantrisk-backend'])
        svc = desc['services'][0]
        parts = []
        for d in svc.get('deployments', []):
            s = d['status']
            r = d.get('runningCount', 0)
            des = d.get('desiredCount', 0)
            ro = d.get('rolloutState', '?')
            rv = d['taskDefinition'].split(':')[-1]
            parts.append(f'[{s}]v{rv}={r}/{des}({ro})')
        print(f'  {" | ".join(parts)}')
        sys.stdout.flush()

        primary = [d for d in svc['deployments'] if d['status'] == 'PRIMARY']
        if primary:
            p = primary[0]
            if p.get('runningCount', 0) >= 1 and p.get('rolloutState') == 'COMPLETED':
                print('\nSUCCESS: Deployment complete!')
                alb = 'http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com'
                time.sleep(5)
                # Test login
                try:
                    login_data = json.dumps({'email': 'demo@instantrisk.com', 'password': 'Demo2026pass'}).encode()
                    req = urllib.request.Request(f'{alb}/api/v1/auth/login', data=login_data, method='POST')
                    req.add_header('Content-Type', 'application/json')
                    with urllib.request.urlopen(req, timeout=10) as resp2:
                        body = json.loads(resp2.read().decode())
                        print(f'Login: {resp2.status} OK - {body.get("user", {}).get("email", "?")}')
                        token = body.get('access_token', '')
                except urllib.error.HTTPError as e:
                    err = e.read().decode()[:500]
                    print(f'Login: {e.code} - {err}')
                    token = ''
                except Exception as e:
                    print(f'Login: ERROR - {e}')
                    token = ''

                # Test chat endpoint
                if token:
                    try:
                        chat_data = json.dumps({'messages': [{'role': 'user', 'content': 'Hello'}]}).encode()
                        req = urllib.request.Request(f'{alb}/api/v1/chat/', data=chat_data, method='POST')
                        req.add_header('Content-Type', 'application/json')
                        req.add_header('Authorization', f'Bearer {token}')
                        with urllib.request.urlopen(req, timeout=60) as resp3:
                            chat_body = json.loads(resp3.read().decode())
                            msg = chat_body.get('message', '')[:100]
                            print(f'Chat: {resp3.status} OK - {msg}...')
                    except urllib.error.HTTPError as e:
                        err = e.read().decode()[:500]
                        print(f'Chat: {e.code} - {err}')
                    except Exception as e:
                        print(f'Chat: ERROR - {e}')

                sys.exit(0)
            if p.get('rolloutState') == 'FAILED':
                print(f'\nFAILED: {p.get("rolloutStateReason", "")}')
                sys.exit(1)
    except Exception as e:
        print(f'  Error: {e}')

print('Timeout.')
