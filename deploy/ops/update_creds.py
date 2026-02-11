import re

files = [
    r'C:\Users\maani\parametriks-risk-engine\infrastructure\deploy_backend.py',
    r'C:\Users\maani\parametriks-risk-engine\infrastructure\deploy_frontend.py',
    r'C:\Users\maani\parametriks-risk-engine\infrastructure\setup_cloudfront.py',
]

new_creds = {
    'AWS_ACCESS_KEY_ID': os.environ.get('AWS_ACCESS_KEY_ID', ''),
    'AWS_SECRET_ACCESS_KEY': os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    'AWS_SESSION_TOKEN': os.environ.get('AWS_SESSION_TOKEN', ''),
}

for fpath in files:
    with open(fpath, 'r') as f:
        content = f.read()

    for key, new_val in new_creds.items():
        # Match: KEY = "value" or KEY = 'value'
        pattern = re.compile(r'(' + re.escape(key) + r'\s*=\s*)(["\'])(.*?)\2', re.DOTALL)
        match = pattern.search(content)
        if match:
            old_val = match.group(3)
            quote = match.group(2)
            content = content.replace(match.group(0), match.group(1) + quote + new_val + quote)
            print(f'{fpath}: replaced {key} (old={old_val[:30]}...)')
        else:
            print(f'{fpath}: WARNING - {key} not found!')

    with open(fpath, 'w') as f:
        f.write(content)

print('\nDone. All credentials updated.')
