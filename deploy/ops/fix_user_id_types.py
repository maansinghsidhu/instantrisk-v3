"""Fix user_id type from int to str (UUID) in auth and approval routers"""
import os
import re

ROUTERS_DIR = r'C:\Users\maani\instantrisk-v2\backend-merged\app\routers'

files_to_fix = ['auth.py', 'approval.py']

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    original = content

    # Replace user_id: int with user_id: str in function signatures
    content = re.sub(r'user_id:\s*int\b', 'user_id: str', content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

print("="*60)
print("Fixing user_id type: int -> str (UUID)")
print("="*60)

for filename in files_to_fix:
    filepath = os.path.join(ROUTERS_DIR, filename)
    if os.path.exists(filepath):
        if fix_file(filepath):
            print(f"[FIXED] {filename}")
        else:
            print(f"[SKIP]  {filename}")
    else:
        print(f"[MISS]  {filename}")

print("="*60)
